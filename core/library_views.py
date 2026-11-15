"""Vistas de biblioteca da PicoDex no Route Pico: visão por sistema, galeria, capas que faltam, estatísticas.

Port de PicoDex ``LibraryView`` / ``SystemGallery`` / ``CoversView`` / ``StatsView``
(rasalopa, MIT). Tudo é leitura, exceto :func:`fetch_missing_covers`, que grava
só capas (nunca ícones: um jogo de DS já traz o seu, e trocar por uma capa
encolhida pioraria o menu) e nunca sobrescreve uma capa existente.

Regra das capas automáticas, como a PicoDex: "melhor nenhuma do que a errada".
Só o par exato do ``pickBoxart`` pelo nome do arquivo e, num jogo de DS cujo
nome não deu par, pelo título gravado dentro do ROM.
"""

from __future__ import annotations

import base64
import os
import threading
from typing import Any, Optional

from core.logging_util import emit_log
from core.privacy import redact_text

_preview_cache: dict[tuple[str, float, int], str] = {}
_preview_lock = threading.Lock()
_PREVIEW_CACHE_MAX = 2000
_MAX_GALLERY_BATCH = 120
_MAX_FETCH = 500


def _png_url(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def _cover_preview(path: str) -> Optional[str]:
    """Prévia PNG da capa (só a área visível de 106×96), com cache por mtime."""
    from core.pico_bmp import decode_bmp_rgba, rgba_to_png

    try:
        st = os.stat(path)
    except OSError:
        return None
    key = (path, st.st_mtime, st.st_size)
    with _preview_lock:
        hit = _preview_cache.get(key)
    if hit:
        return hit
    try:
        with open(path, "rb") as f:
            w, h, rgba = decode_bmp_rgba(f.read())
    except (OSError, ValueError):
        return None
    vw = min(w, 106)
    crop = bytearray(vw * h * 4)
    for y in range(h):
        crop[y * vw * 4 : (y + 1) * vw * 4] = rgba[y * w * 4 : y * w * 4 + vw * 4]
    url = _png_url(rgba_to_png(vw, h, bytes(crop)))
    with _preview_lock:
        if len(_preview_cache) > _PREVIEW_CACHE_MAX:
            _preview_cache.clear()
        _preview_cache[key] = url
    return url


def _library(mount_path: str) -> list[dict[str, Any]]:
    """Jogos do cartão com sistema PicoDex, game code e caminho da capa."""
    from core.pico_artwork import resolve_existing_art
    from core.picodex_rules import system_for_extension
    from core.routedex import read_game_code, scan_card

    out = []
    for g in scan_card(mount_path)["games"]:
        system = system_for_extension(g["name"])
        if system is None:
            continue
        full = os.path.join(mount_path, *g["rel"].split("/"))
        code = read_game_code(full, system.id if system.id in ("nds", "gba") else "") if system.cover_keying == "gamecode" else None
        out.append(
            {
                "rel": g["rel"],
                "name": g["name"],
                "dir": g["dir"],
                "title": os.path.splitext(g["name"])[0],
                "system": system,
                "game_code": code,
                "cover_path": resolve_existing_art(mount_path, g["name"], code, "cover"),
                "full": full,
            }
        )
    return out


def _gamedata_index(mount_path: str) -> tuple[dict[str, dict[str, Any]], Optional[str]]:
    from core.routedex import RouteDexError, _public_entry, load_gamedata

    try:
        data, _exists = load_gamedata(mount_path)
    except RouteDexError as e:
        return {}, str(e)
    index: dict[str, dict[str, Any]] = {}
    for e in data["entries"]:
        index.setdefault(e["fileName"].lower(), _public_entry(e))
    return index, None


# --------------------------------------------------------------------------- #
# Biblioteca: visão por sistema + componentes do cartão
# --------------------------------------------------------------------------- #


def library_overview(mount_path: str) -> dict[str, Any]:
    from core.routedex import identify_launcher, identify_loader

    games = _library(mount_path)
    gd, gd_error = _gamedata_index(mount_path)
    systems: dict[str, dict[str, Any]] = {}
    for g in games:
        s = g["system"]
        row = systems.setdefault(
            s.id,
            {"id": s.id, "label": s.label, "games_dir": s.games_dir, "count": 0, "covered": 0, "favorites": 0, "minutes": 0},
        )
        row["count"] += 1
        row["covered"] += 1 if g["cover_path"] else 0
        e = gd.get(g["name"].lower())
        if e:
            row["favorites"] += 1 if e.get("favorite") else 0
            row["minutes"] += int(e.get("playMinutes") or 0)
    for row in systems.values():
        folder = os.path.join(mount_path, "Games", row["games_dir"])
        row["folder"] = f"Games/{row['games_dir']}" if os.path.isdir(folder) else None
        row["has_banner"] = bool(row["folder"]) and os.path.isfile(os.path.join(folder, "banner.bnr"))
        row["shares_folder_with"] = [
            r["label"] for r in systems.values() if r["id"] != row["id"] and r["games_dir"] == row["games_dir"]
        ]
    launcher = identify_launcher(mount_path)
    boot = os.path.join(mount_path, "_picoboot.nds")
    try:
        launcher["updated"] = os.path.getmtime(boot)
    except OSError:
        launcher["updated"] = None
    loader = identify_loader(mount_path)
    ordered = sorted(systems.values(), key=lambda r: (-r["count"], r["label"]))
    return {
        "success": True,
        "totals": {
            "games": len(games),
            "systems": len(systems),
            "favorites": sum(1 for e in gd.values() if e.get("favorite")),
            "minutes": sum(int(e.get("playMinutes") or 0) for e in gd.values()),
            "covered": sum(1 for g in games if g["cover_path"]),
        },
        "systems": ordered,
        "launcher": launcher,
        "loader": loader,
        "gamedata_problem": gd_error,
    }


# --------------------------------------------------------------------------- #
# Galeria de um sistema
# --------------------------------------------------------------------------- #


def system_gallery(mount_path: str, system_id: str) -> dict[str, Any]:
    """Jogos de um sistema com marcas e estatísticas; as capas vêm por :func:`gallery_covers`."""
    from core.picodex_rules import system_by_id

    system = system_by_id(system_id or "")
    if system is None:
        return {"success": False, "error": "Sistema desconhecido."}
    gd, gd_error = _gamedata_index(mount_path)
    items = []
    for g in _library(mount_path):
        if g["system"].id != system.id:
            continue
        e = gd.get(g["name"].lower()) or {}
        items.append(
            {
                "rel": g["rel"],
                "name": g["name"],
                "title": g["title"],
                "game_code": g["game_code"],
                "has_cover": bool(g["cover_path"]),
                "favorite": bool(e.get("favorite")),
                "completed": bool(e.get("completed")),
                "launchCount": int(e.get("launchCount") or 0),
                "playMinutes": int(e.get("playMinutes") or 0),
                "lastPlayed": e.get("lastPlayed") or "",
            }
        )
    items.sort(key=lambda i: i["title"].lower())
    return {
        "success": True,
        "system": {"id": system.id, "label": system.label, "games_dir": system.games_dir, "is_nds": system.id == "nds"},
        "games": items,
        "gamedata_problem": gd_error,
    }


def gallery_covers(mount_path: str, rels: Any) -> dict[str, Any]:
    """Prévias das capas pedidas (lotes de até 120), para a galeria e as estatísticas."""
    from core.pico_artwork import resolve_existing_art
    from core.picodex_rules import system_for_extension
    from core.routedex import RouteDexError, read_game_code, resolve_card_path

    if not isinstance(rels, list):
        return {"success": False, "error": "Lista inválida.", "covers": {}}
    out: dict[str, Optional[str]] = {}
    for rel in rels[:_MAX_GALLERY_BATCH]:
        if not isinstance(rel, str):
            continue
        try:
            full = resolve_card_path(mount_path, rel)
        except RouteDexError:
            continue
        name = os.path.basename(full)
        system = system_for_extension(name)
        code = None
        if system is not None and system.cover_keying == "gamecode":
            code = read_game_code(full, system.id if system.id in ("nds", "gba") else "")
        path = resolve_existing_art(mount_path, name, code, "cover")
        out[rel] = _cover_preview(path) if path else None
    return {"success": True, "covers": out}


def gallery_covers_by_name(mount_path: str, file_names: Any) -> dict[str, Any]:
    """Prévias por nome de arquivo (as listas do gamedata.json não trazem a pasta)."""
    if not isinstance(file_names, list):
        return {"success": False, "error": "Lista inválida.", "covers": {}}
    wanted = {str(n).lower(): str(n) for n in file_names[:_MAX_GALLERY_BATCH] if isinstance(n, str)}
    out: dict[str, Optional[str]] = {}
    for g in _library(mount_path):
        key = g["name"].lower()
        if key in wanted and wanted[key] not in out:
            out[wanted[key]] = _cover_preview(g["cover_path"]) if g["cover_path"] else None
    return {"success": True, "covers": out}


# --------------------------------------------------------------------------- #
# Capas que faltam (CoversView)
# --------------------------------------------------------------------------- #


def missing_covers(mount_path: str) -> dict[str, Any]:
    games = _library(mount_path)
    missing = []
    for g in games:
        if g["cover_path"]:
            continue
        s = g["system"]
        missing.append(
            {
                "rel": g["rel"],
                "name": g["name"],
                "title": g["title"],
                "system": s.id,
                "system_label": s.label,
                # Sem game code, a capa vai pelo nome do arquivo: renomear o arquivo perde a capa.
                "no_gamecode": s.cover_keying == "gamecode" and not g["game_code"],
            }
        )
    return {"success": True, "total": len(games), "missing": missing}


def _auto_pick(game: dict[str, Any], catalogs: dict[str, list[str]]) -> tuple[Optional[str], bool]:
    from core.picodex_rules import is_degenerate_title, pick_boxart, read_nds_banner_title, region_prefs_for

    s = game["system"]
    names = catalogs.get(s.libretro_repo) or []
    prefs = region_prefs_for(s.id, game["game_code"], game["name"])
    best = None if is_degenerate_title(game["title"]) else pick_boxart(game["title"], names, prefs)
    if best:
        return best, False
    if s.id == "nds":
        banner = read_nds_banner_title(game["full"])
        if banner:
            best = pick_boxart(banner, names, prefs)
            if best:
                return best, True
    return None, False


def fetch_missing_covers(mount_path: str, rels: Any, log=None) -> dict[str, Any]:
    """Baixa e grava capas para os jogos escolhidos (só os que ainda não têm capa)."""
    from concurrent.futures import ThreadPoolExecutor

    from core.art_picker import ArtPickerError, _write_verified
    from core.pico_artwork import _http_get
    from core.pico_bmp import decode_image_rgba, rgba_to_cover_bmp
    from core.picodex_rules import CatalogError, fetch_catalog, resolve_art_target, thumb_url
    from core.progress import OperationCancelled, ProgressTracker, check_cancelled
    from core.sdio import sync_volume

    if not isinstance(rels, list) or not rels:
        return {"success": False, "error": "Escolha os jogos.", "results": []}
    wanted = {str(r) for r in rels[:_MAX_FETCH] if isinstance(r, str)}
    games = [g for g in _library(mount_path) if g["rel"] in wanted and not g["cover_path"]]
    catalogs: dict[str, list[str]] = {}
    catalog_errors: dict[str, str] = {}
    for repo in sorted({g["system"].libretro_repo for g in games}):
        try:
            catalogs[repo] = fetch_catalog(repo)
        except CatalogError as e:
            catalog_errors[repo] = str(e)

    tracker = ProgressTracker("covers_fetch", label="Buscando capas…", total_items=len(games))
    tracker.cancellable = True
    results: list[dict[str, Any]] = []
    plans = []
    for g in games:
        repo = g["system"].libretro_repo
        if repo in catalog_errors:
            results.append({"rel": g["rel"], "status": "error", "error": catalog_errors[repo]})
            continue
        name, via_banner = _auto_pick(g, catalogs)
        if not name:
            results.append({"rel": g["rel"], "status": "no-match"})
            continue
        plans.append((g, name, via_banner))

    def download(plan):
        g, name, _vb = plan
        return _http_get(thumb_url(g["system"].libretro_repo, name, "boxarts"))

    written = 0
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [(p, pool.submit(download, p)) for p in plans]
            for (g, name, via_banner), fut in futures:
                check_cancelled()
                tracker.set_label(g["title"])
                data = fut.result()
                if not data:
                    results.append({"rel": g["rel"], "status": "error", "error": "Download falhou."})
                    tracker.advance_item(label=g["title"], failed=True)
                    continue
                try:
                    w, h, rgba = decode_image_rgba(data)
                    bmp = rgba_to_cover_bmp(w, h, rgba)
                    dest = resolve_art_target(mount_path, "covers", g["name"], g["system"], g["game_code"])
                    _write_verified(dest, bmp)
                except (ValueError, OSError, ArtPickerError) as e:
                    results.append({"rel": g["rel"], "status": "error", "error": redact_text(str(e))})
                    tracker.advance_item(label=g["title"], failed=True)
                    continue
                written += 1
                results.append(
                    {
                        "rel": g["rel"],
                        "status": "written",
                        "match": name[:-4] if name.endswith(".png") else name,
                        "via_banner": via_banner,
                        "preview": _cover_preview(dest),
                    }
                )
                tracker.advance_item(label=g["title"], written=True)
    except OperationCancelled:
        tracker.finish("Cancelado")
        emit_log(log, f"Busca de capas cancelada: {written} gravada(s).")
        return {"success": True, "cancelled": True, "written": written, "results": results}
    finally:
        try:
            sync_volume(mount_path)
        except Exception:
            pass
    no_match = sum(1 for r in results if r["status"] == "no-match")
    failed = sum(1 for r in results if r["status"] == "error")
    msg = f"Capas: {written} gravada(s) · {no_match} sem par no catálogo · {failed} com falha"
    tracker.finish(msg)
    emit_log(log, msg)
    return {"success": True, "written": written, "no_match": no_match, "failed": failed, "results": results}


# --------------------------------------------------------------------------- #
# Estatísticas (StatsView)
# --------------------------------------------------------------------------- #


def play_stats(mount_path: str) -> dict[str, Any]:
    from core.routedex import gamedata_overview

    ov = gamedata_overview(mount_path)
    if not ov.get("success"):
        return ov
    lib = ov.get("library") or []
    rel_by_name = {g["name"].lower(): g["rel"] for g in lib}
    favorites = [
        {"fileName": g["name"], "rel": g["rel"], "playMinutes": g.get("playMinutes", 0), "launchCount": g.get("launchCount", 0)}
        for g in lib
        if g.get("favorite")
    ]

    def with_rel(entries):
        return [dict(e, rel=rel_by_name.get(e["fileName"].lower())) for e in entries]

    return {
        "success": True,
        "enhanced": ov.get("enhanced"),
        "launcher": ov.get("launcher"),
        "parse_error": ov.get("parse_error"),
        "totals": ov.get("totals"),
        "top": with_rel(ov.get("top") or []),
        "recent": with_rel((ov.get("recent") or [])[:10]),
        "favorites": favorites,
    }
