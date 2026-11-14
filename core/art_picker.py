"""Janela de capa e ícone + editor de banner de pasta (port de PicoDex CoverPicker / BannerEditor).

Divisão de trabalho, igual à PicoDex:

- O Python fornece as **imagens de origem** como data URLs (o catálogo
  libretro-thumbnails, logos libretro, SteamGridDB, o ícone embutido do ROM, a
  arte atual do cartão). Downloads só para os hosts permitidos em
  :mod:`core.pico_artwork`; a UI nunca busca nada na rede.
- A UI **compõe** a imagem num canvas (capa esticada para 106×96 como as capas
  da comunidade; ícone encaixado em 32×32 sem esticar) e devolve os pixels RGBA.
- O Python **codifica** no formato do Pico Launcher, confere com as mesmas regras
  do launcher, guarda o resultado numa área temporária (token) e devolve a
  prévia decodificada do próprio BMP: o que aparece é o que vai para o cartão.
- Salvar grava capa e ícone juntos (``.partial`` → confere → ``os.replace``).

Créditos: PicoDex de rasalopa (MIT).
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

from core.cache import CACHE_DIR
from core.privacy import redact_text

COVER_W, COVER_H, COVER_VISIBLE_W = 128, 96, 106
ICON = 32
_MAX_RGBA_B64 = 400_000
_STAGE_MAX = 64
_THUMB_SIDE = 96
_MAX_RESULTS = 48
_MAX_THUMBS = 48
_DOWNLOAD_WORKERS = 6
_NEIGHBOURS = 2

_stage: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
_stage_lock = threading.Lock()


class ArtPickerError(RuntimeError):
    pass


# --------------------------------------------------------------------------- #
# util
# --------------------------------------------------------------------------- #


def _sniff_mime(data: bytes) -> Optional[str]:
    if data.startswith(b"\x89PNG"):
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:2] == b"BM":
        return "image/bmp"
    return None


def _data_url(data: bytes, mime: Optional[str] = None) -> Optional[str]:
    mime = mime or _sniff_mime(data)
    if not mime:
        return None
    return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")


def _png_url(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def _stage_put(entry: dict[str, Any]) -> str:
    token = secrets.token_urlsafe(12)
    with _stage_lock:
        _stage[token] = entry
        while len(_stage) > _STAGE_MAX:
            _stage.popitem(last=False)
    return token


def _stage_get(token: Any, kind: str) -> dict[str, Any]:
    with _stage_lock:
        entry = _stage.get(str(token or ""))
    if not entry or entry.get("kind") != kind:
        raise ArtPickerError("A prévia expirou; escolha a imagem de novo.")
    return entry


def _download(url: str) -> Optional[bytes]:
    from core.pico_artwork import _http_get

    return _http_get(url)


def _parallel(fn, items: list, workers: int = _DOWNLOAD_WORKERS) -> list:
    if not items:
        return []
    with ThreadPoolExecutor(max_workers=min(workers, len(items))) as pool:
        return list(pool.map(fn, items))


# --------------------------------------------------------------------------- #
# codificação (o que a UI compôs → formato do launcher)
# --------------------------------------------------------------------------- #


def _decode_rgba(rgba_b64: Any, w: int, h: int) -> bytes:
    if not isinstance(rgba_b64, str) or len(rgba_b64) > _MAX_RGBA_B64:
        raise ArtPickerError("Imagem inválida.")
    try:
        raw = base64.b64decode(rgba_b64, validate=True)
    except (ValueError, TypeError) as e:
        raise ArtPickerError("Imagem inválida.") from e
    if len(raw) != w * h * 4:
        raise ArtPickerError("Tamanho de imagem inesperado.")
    return raw


def encode_art(kind: str, rgba_b64: Any) -> dict[str, Any]:
    """Codifica os pixels compostos pela UI. ``kind``: ``cover`` (128×96) ou ``icon`` (32×32)."""
    from core.pico_bmp import (
        bmp_to_preview_png,
        decode_bmp_rgba,
        rgba_to_cover_bmp,
        rgba_to_icon_bmp,
        rgba_to_png,
        validate_launcher_cover_bmp,
        validate_launcher_icon_bmp,
    )

    if kind == "cover":
        rgba = _decode_rgba(rgba_b64, COVER_W, COVER_H)
        # A UI já esticou para 106×96 sobre preto; só recorta e quantiza.
        visible = bytearray(COVER_VISIBLE_W * COVER_H * 4)
        for y in range(COVER_H):
            src = y * COVER_W * 4
            visible[y * COVER_VISIBLE_W * 4 : (y + 1) * COVER_VISIBLE_W * 4] = rgba[src : src + COVER_VISIBLE_W * 4]
        bmp = rgba_to_cover_bmp(COVER_VISIBLE_W, COVER_H, bytes(visible))
        problem = validate_launcher_cover_bmp(bmp)
        w, h, dec = decode_bmp_rgba(bmp)
        crop = bytearray(COVER_VISIBLE_W * h * 4)
        for y in range(h):
            crop[y * COVER_VISIBLE_W * 4 : (y + 1) * COVER_VISIBLE_W * 4] = dec[y * w * 4 : y * w * 4 + COVER_VISIBLE_W * 4]
        preview = _png_url(rgba_to_png(COVER_VISIBLE_W, h, bytes(crop)))
        token = _stage_put({"kind": "cover", "bmp": bmp})
    elif kind == "icon":
        rgba = _decode_rgba(rgba_b64, ICON, ICON)
        bmp = rgba_to_icon_bmp(ICON, ICON, rgba)
        problem = validate_launcher_icon_bmp(bmp)
        quantized = icon_bmp_rgba(bmp)
        preview = _png_url(bmp_to_preview_png(bmp))
        token = _stage_put({"kind": "icon", "bmp": bmp, "rgba": quantized})
    else:
        raise ArtPickerError("Tipo de arte inválido.")
    if problem:
        raise ArtPickerError(f"A imagem gerada não passou na conferência do launcher: {problem}")
    return {"success": True, "token": token, "preview": preview}


def icon_bmp_rgba(bmp: bytes) -> bytes:
    """RGBA 32×32 de um ícone 4 bpp do launcher, com o índice 0 transparente."""
    import struct

    data_off = struct.unpack_from("<I", bmp, 10)[0]
    height = struct.unpack_from("<i", bmp, 22)[0]
    pal = [bmp[54 + i * 4 : 58 + i * 4] for i in range(16)]
    out = bytearray(ICON * ICON * 4)
    for row in range(ICON):
        y = ICON - 1 - row if height > 0 else row
        base = data_off + row * (ICON // 2)
        for x in range(ICON):
            byte = bmp[base + x // 2]
            idx = (byte >> 4) if x % 2 == 0 else (byte & 0xF)
            if idx == 0:
                continue
            b, g, r = pal[idx][0], pal[idx][1], pal[idx][2]
            o = (y * ICON + x) * 4
            out[o : o + 4] = bytes((r, g, b, 255))
    return bytes(out)


# --------------------------------------------------------------------------- #
# contexto do jogo
# --------------------------------------------------------------------------- #


def _game(mount_path: str, rel: str) -> dict[str, Any]:
    from core.pico_artwork import _resolve_game

    err, meta = _resolve_game(mount_path, rel)
    if err or not meta:
        raise ArtPickerError(err or "Jogo não encontrado.")
    return meta


def _launcher_notes(mount_path: str) -> dict[str, Any]:
    from core.routedex import identify_launcher

    l = identify_launcher(mount_path)
    stock_130 = l.get("variant") == "official" and l.get("version") == "v1.3.0"
    return {"variant": l.get("variant"), "version": l.get("version"), "custom_icons_ignored": stock_130}


def _find_art(mount_path: str, folder: str, basename: str, system, code: Optional[str], ext: str) -> Optional[str]:
    """``findArt`` da PicoDex: user/<arquivo>.<ext> primeiro, depois nds|gba/<CODE>.<ext>."""
    from core.picodex_rules import is_usable_game_code

    base = os.path.join(mount_path, "_pico", folder)
    user = os.path.join(base, "user", f"{basename}.{ext}")
    if os.path.isfile(user):
        return user
    if system is not None and system.cover_keying == "gamecode" and is_usable_game_code(code):
        sub = "nds" if system.id == "nds" else "gba"
        p = os.path.join(base, sub, f"{code.upper()}.{ext}")
        if os.path.isfile(p):
            return p
    return None


def _rom_icon_png(path: str) -> Optional[bytes]:
    from core.pico_bmp import rgba_to_png
    from core.routedex import RouteDexError, decode_icon_rgba, rom_banner_icon

    try:
        bitmap, palette = rom_banner_icon(path)
    except (RouteDexError, OSError):
        return None
    return rgba_to_png(ICON, ICON, decode_icon_rgba(bitmap, palette))


def _neighbours(full: str) -> dict[str, list[str]]:
    """Os vizinhos na lista do launcher (mesma pasta, ordem por nome)."""
    from core.dspico import LIBRARY_FILE_EXTS

    folder, me = os.path.dirname(full), os.path.basename(full)
    try:
        names = sorted(
            (n for n in os.listdir(folder) if not n.startswith(".") and os.path.splitext(n)[1].lower() in LIBRARY_FILE_EXTS),
            key=str.lower,
        )
    except OSError:
        return {"before": [], "after": []}
    stems = [os.path.splitext(n)[0] for n in names]
    try:
        i = names.index(me)
    except ValueError:
        return {"before": [], "after": []}
    return {"before": stems[max(0, i - _NEIGHBOURS) : i], "after": stems[i + 1 : i + 1 + _NEIGHBOURS]}


def picker_context(mount_path: str, rel: str) -> dict[str, Any]:
    """Tudo o que a janela de capa e ícone mostra antes de buscar algo."""
    from core.pico_bmp import bmp_to_preview_png, validate_launcher_cover_bmp, validate_launcher_icon_bmp
    from core.picodex_rules import resolve_art_target, system_for_extension

    meta = _game(mount_path, rel)
    basename = meta["basename"]
    system = system_for_extension(basename)
    code = meta.get("game_code")
    title = os.path.splitext(basename)[0]
    notes = _launcher_notes(mount_path)

    cover = None
    cpath = _find_art(mount_path, "covers", basename, system, code, "bmp")
    if cpath:
        try:
            with open(cpath, "rb") as f:
                data = f.read()
            bad = validate_launcher_cover_bmp(data, launcher="enhanced" if notes["variant"] == "enhanced" else "stock")
            cover = {"preview": None if bad else _png_url(bmp_to_preview_png(data)), "invalid": bad,
                     "rel": os.path.relpath(cpath, mount_path).replace(os.sep, "/")}
        except (OSError, ValueError) as e:
            cover = {"preview": None, "invalid": redact_text(str(e)), "rel": None}

    icon: dict[str, Any] = {"kind": "none", "preview": None}
    bpath = _find_art(mount_path, "banners", basename, system, code, "bnr")
    ipath = _find_art(mount_path, "icons", basename, system, code, "bmp")
    if bpath:
        from core.pico_bmp import rgba_to_png
        from core.routedex import RouteDexError, decode_icon_rgba, parse_banner

        try:
            with open(bpath, "rb") as f:
                info = parse_banner(f.read())
            icon = {"kind": "banner", "preview": _png_url(rgba_to_png(ICON, ICON, decode_icon_rgba(info["bitmap"], info["palette"]))),
                    "rel": os.path.relpath(bpath, mount_path).replace(os.sep, "/")}
        except (OSError, RouteDexError):
            icon = {"kind": "banner", "preview": None, "rel": os.path.relpath(bpath, mount_path).replace(os.sep, "/")}
    elif ipath:
        try:
            with open(ipath, "rb") as f:
                data = f.read()
            bad = validate_launcher_icon_bmp(data)
            icon = {"kind": "invalid" if bad else "custom", "preview": None if bad else _png_url(bmp_to_preview_png(data)),
                    "reason": bad, "rel": os.path.relpath(ipath, mount_path).replace(os.sep, "/")}
        except (OSError, ValueError):
            icon = {"kind": "invalid", "preview": None}
    elif system is not None and system.id == "nds":
        png = _rom_icon_png(meta["full"])
        if png:
            icon = {"kind": "builtin", "preview": _png_url(png)}

    def target(folder: str) -> str:
        p = resolve_art_target(mount_path, folder, basename, system, code)
        return os.path.relpath(p, mount_path).replace(os.sep, "/")

    return {
        "success": True,
        "rel": rel,
        "file_name": basename,
        "title": title,
        "rom_title": meta.get("title"),
        "game_code": code,
        "system": {"id": system.id, "label": system.label, "repo": system.libretro_repo} if system else None,
        "cover": cover,
        "icon": icon,
        "targets": {"cover": target("covers"), "icon": target("icons")},
        "neighbours": _neighbours(meta["full"]),
        "launcher": notes,
        "is_nds": bool(system and system.id == "nds"),
    }


# --------------------------------------------------------------------------- #
# catálogo libretro (capas e logos)
# --------------------------------------------------------------------------- #


def catalog_search(
    repo: str, query: str, kind: str = "boxarts", title: str = "", game_code: str = "", system_id: str = "", file_name: str = ""
) -> dict[str, Any]:
    """Busca instantânea no catálogo (cache local de 7 dias), como o CoverPicker."""
    from core.picodex_rules import CatalogError, fetch_catalog, pick_boxart, region_prefs_for, search_catalog

    try:
        names = fetch_catalog(repo, kind=kind)
    except CatalogError as e:
        return {"success": False, "error": str(e), "results": []}
    q = (query or "").strip()
    results = search_catalog(names, q, _MAX_RESULTS) if q else []
    suggested = None
    if title:
        suggested = pick_boxart(title, names, region_prefs_for(system_id, game_code or None, file_name or title))
        if suggested and (not q or q.lower() == title.lower()):
            results = [suggested] + [n for n in results if n != suggested]
    return {
        "success": True,
        "kind": kind,
        "total": len(names),
        "suggested": suggested,
        "results": [{"name": n, "label": n[:-4] if n.lower().endswith(".png") else n} for n in results[:_MAX_RESULTS]],
    }


def _thumb_cache_path(repo: str, name: str, kind: str) -> str:
    digest = hashlib.sha256(f"{repo}/{kind}/{name}".encode("utf-8")).hexdigest()[:32]
    return os.path.join(CACHE_DIR, "libretro_thumbs", f"{digest}.png")


def _thumb_for(args: tuple[str, str, str]) -> tuple[str, Optional[str]]:
    from core.pico_bmp import image_bytes_to_preview_png
    from core.picodex_rules import thumb_url

    repo, name, kind = args
    path = _thumb_cache_path(repo, name, kind)
    try:
        with open(path, "rb") as f:
            return name, _png_url(f.read())
    except OSError:
        pass
    data = _download(thumb_url(repo, name, kind))
    if not data:
        return name, None
    try:
        png = image_bytes_to_preview_png(data, _THUMB_SIDE)
    except (ValueError, OSError):
        return name, None
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".partial"
        with open(tmp, "wb") as f:
            f.write(png)
        os.replace(tmp, path)
    except OSError:
        pass
    return name, _png_url(png)


def catalog_thumbs(repo: str, names: Any, kind: str = "boxarts") -> dict[str, Any]:
    """Miniaturas (≤96 px) das entradas pedidas, baixadas em paralelo e guardadas no cache."""
    from core.picodex_rules import CATALOG_KINDS, _REPO_RE

    if not _REPO_RE.match(repo or "") or kind not in CATALOG_KINDS or not isinstance(names, list):
        return {"success": False, "error": "Pedido inválido.", "thumbs": {}}
    wanted = [str(n) for n in names[:_MAX_THUMBS] if isinstance(n, str) and n.endswith(".png") and "/" not in n]
    out = dict(_parallel(_thumb_for, [(repo, n, kind) for n in wanted]))
    return {"success": True, "thumbs": out}


def catalog_image(repo: str, name: str, kind: str = "boxarts") -> dict[str, Any]:
    """A imagem inteira de uma entrada, para a UI compor a capa ou o ícone."""
    from core.picodex_rules import CATALOG_KINDS, _REPO_RE, thumb_url

    if not _REPO_RE.match(repo or "") or kind not in CATALOG_KINDS or not isinstance(name, str) or "/" in name:
        return {"success": False, "error": "Pedido inválido."}
    data = _download(thumb_url(repo, name, kind))
    url = _data_url(data) if data else None
    if not url:
        return {"success": False, "error": "Esta arte não está mais disponível ou não pôde ser baixada."}
    return {"success": True, "image": url}


def remote_image(url: str) -> dict[str, Any]:
    """Uma imagem de fonte permitida (SteamGridDB, GameTDB, libretro) como data URL."""
    from core.pico_artwork import _url_allowed

    if not isinstance(url, str) or not _url_allowed(url):
        return {"success": False, "error": "Fonte de imagem não permitida."}
    data = _download(url)
    out = _data_url(data) if data else None
    if not out:
        return {"success": False, "error": "A imagem não pôde ser baixada."}
    return {"success": True, "image": out}


def host_image(path: str) -> dict[str, Any]:
    """Uma imagem do computador (PNG, JPG, WebP, GIF, BMP) como data URL para compor."""
    try:
        if os.path.getsize(path) > 16 * 1024 * 1024:
            return {"success": False, "error": "Imagem grande demais (máximo 16 MB)."}
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        return {"success": False, "error": redact_text(f"Não foi possível ler a imagem: {e}")}
    out = _data_url(data)
    if not out:
        return {"success": False, "error": "Formato não reconhecido. Use PNG, JPG, WebP, GIF ou BMP."}
    return {"success": True, "image": out}


# --------------------------------------------------------------------------- #
# fontes de ícone: ROM, SteamGridDB, logos libretro (o "da capa" é feito na UI)
# --------------------------------------------------------------------------- #


def _sgdb_icons(term: str, limit: int = 6) -> list[dict[str, Any]]:
    from core.steamgriddb import candidate_assets, has_api_key

    if not term or not has_api_key():
        return []
    try:
        assets = candidate_assets(term, "icon", limit=limit)
    except Exception:
        return []
    urls = [a.get("url") for a in assets if isinstance(a.get("url"), str)][:limit]
    datas = _parallel(_download, urls)
    out = []
    for url, data in zip(urls, datas):
        img = _data_url(data) if data else None
        if img and not img.startswith("data:image/bmp"):
            out.append({"source": "steamgriddb", "label": "SteamGridDB", "image": img})
    return out


def _logo_icons(repos: list[str], query: str, title: str = "", limit: int = 4) -> list[dict[str, Any]]:
    from core.picodex_rules import CatalogError, fetch_catalog, pick_boxart, search_catalog, thumb_url

    picks: list[tuple[str, str]] = []
    for repo in repos:
        try:
            names = fetch_catalog(repo, kind="logos")
        except CatalogError:
            continue
        found: list[str] = []
        best = pick_boxart(title, names) if title else None
        if best:
            found.append(best)
        for n in search_catalog(names, query or title, limit):
            if n not in found:
                found.append(n)
        picks.extend((repo, n) for n in found[:limit])
    picks = picks[:limit * 2]
    datas = _parallel(lambda p: _download(thumb_url(p[0], p[1], "logos")), picks)
    out = []
    for (repo, name), data in zip(picks, datas):
        img = _data_url(data) if data else None
        if img:
            out.append({"source": "logos", "label": name[:-4] if name.endswith(".png") else name, "image": img})
    return out


def icon_sources(mount_path: str, rel: str, query: str = "") -> dict[str, Any]:
    """Imagens candidatas a ícone de um jogo (a UI encaixa cada uma em 32×32)."""
    from core.picodex_rules import system_for_extension
    from core.steamgriddb import has_api_key, search_term_from_rom

    meta = _game(mount_path, rel)
    system = system_for_extension(meta["basename"])
    title = os.path.splitext(meta["basename"])[0]
    q = (query or "").strip() or title
    out: list[dict[str, Any]] = []
    if system is not None and system.id == "nds":
        png = _rom_icon_png(meta["full"])
        if png:
            out.append({"source": "rom", "label": "Ícone do próprio jogo", "image": _png_url(png), "exact": True})
    term = q if query else (search_term_from_rom(meta["basename"], title=meta.get("title")) or title)
    out.extend(_sgdb_icons(term))
    if system is not None:
        out.extend(_logo_icons([system.libretro_repo], q, title))
    return {"success": True, "sources": out, "steamgriddb_key": has_api_key()}


# --------------------------------------------------------------------------- #
# gravar capa + ícone de um jogo
# --------------------------------------------------------------------------- #


def _write_verified(path: str, data: bytes) -> None:
    """``.partial`` → fsync → relê e confere → ``os.replace`` (verify-before-replace)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    partial = path + ".partial"
    try:
        with open(partial, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        with open(partial, "rb") as f:
            if hashlib.sha256(f.read()).digest() != hashlib.sha256(data).digest():
                raise ArtPickerError("A cópia gravada no cartão não confere; nada foi substituído.")
        os.replace(partial, path)
    finally:
        if os.path.exists(partial):
            try:
                os.remove(partial)
            except OSError:
                pass


def save_art(mount_path: str, rel: str, cover_token: Any = None, icon_token: Any = None, log=None) -> dict[str, Any]:
    from core.logging_util import emit_log
    from core.picodex_rules import resolve_art_target, system_for_extension
    from core.sdio import sync_volume

    if not cover_token and not icon_token:
        raise ArtPickerError("Escolha uma capa ou um ícone primeiro.")
    meta = _game(mount_path, rel)
    system = system_for_extension(meta["basename"])
    code = meta.get("game_code")
    plan: list[tuple[str, bytes]] = []
    if cover_token:
        plan.append((resolve_art_target(mount_path, "covers", meta["basename"], system, code), _stage_get(cover_token, "cover")["bmp"]))
    if icon_token:
        plan.append((resolve_art_target(mount_path, "icons", meta["basename"], system, code), _stage_get(icon_token, "icon")["bmp"]))
    written = []
    for path, data in plan:
        _write_verified(path, data)
        written.append(os.path.relpath(path, mount_path).replace(os.sep, "/"))
    try:
        sync_volume(mount_path)
    except Exception:
        pass
    for p in written:
        emit_log(log, f"✅ Arte gravada: /{p}")
    return {"success": True, "written": written}


# --------------------------------------------------------------------------- #
# banner de pasta (Games/<pasta>/banner.bnr)
# --------------------------------------------------------------------------- #


def _folder(mount_path: str, rel_folder: str) -> str:
    from core.routedex import resolve_card_path

    folder = resolve_card_path(mount_path, rel_folder)
    if not os.path.isdir(folder) or folder == os.path.realpath(mount_path):
        raise ArtPickerError("Escolha uma pasta do cartão (não a raiz).")
    return folder


def banner_context(mount_path: str, rel_folder: str) -> dict[str, Any]:
    from core.pico_bmp import rgba_to_png
    from core.picodex_rules import SYSTEMS
    from core.routedex import RouteDexError, decode_icon_rgba, parse_banner

    folder = _folder(mount_path, rel_folder)
    rel = os.path.relpath(folder, mount_path).replace(os.sep, "/")
    current = None
    bnr = os.path.join(folder, "banner.bnr")
    if os.path.isfile(bnr):
        try:
            with open(bnr, "rb") as f:
                info = parse_banner(f.read())
            current = {"title": info["title"], "crc_ok": info["crc_ok"],
                       "icon": _png_url(rgba_to_png(ICON, ICON, decode_icon_rgba(info["bitmap"], info["palette"])))}
        except (OSError, RouteDexError) as e:
            current = {"title": "", "crc_ok": False, "icon": None, "error": redact_text(str(e))}
    name = os.path.basename(folder)
    # Pastas por sistema compartilhadas (gb = Game Boy + Color; ws, ngp idem).
    shared = []
    parent = os.path.relpath(os.path.dirname(folder), mount_path).replace(os.sep, "/")
    if parent.lower() == "games":
        shared = [s.label for s in SYSTEMS if s.games_dir.lower() == name.lower()]
    games = []
    try:
        for n in sorted(os.listdir(folder), key=str.lower):
            if n.startswith(".") or os.path.splitext(n)[1].lower() not in (".nds", ".dsi", ".srl"):
                continue
            games.append(n)
    except OSError:
        pass
    # Pasta de sistema: o nome do sistema (ou dos sistemas que a dividem).
    default_title = " / ".join(shared) if shared else name
    return {
        "success": True,
        "folder": rel,
        "name": name,
        "current": current,
        "shared_systems": shared if len(shared) > 1 else [],
        "default_title": (current or {}).get("title") or default_title,
        "default_query": shared[0] if shared else name,
        "games": games[:400],
        "launcher": _launcher_notes(mount_path),
    }


def banner_icon_sources(mount_path: str, rel_folder: str, query: str = "", game: str = "") -> dict[str, Any]:
    """Ícones candidatos para o banner: um jogo da pasta, SteamGridDB e logos libretro."""
    from core.picodex_rules import SYSTEMS, system_for_extension
    from core.steamgriddb import has_api_key

    folder = _folder(mount_path, rel_folder)
    name = os.path.basename(folder)
    out: list[dict[str, Any]] = []
    if game:
        rom = os.path.join(folder, os.path.basename(str(game)))
        png = _rom_icon_png(rom) if os.path.isfile(rom) else None
        if not png:
            return {"success": False, "error": "Este jogo não tem ícone no banner do ROM.", "sources": []}
        return {"success": True, "sources": [{"source": "rom", "label": os.path.splitext(os.path.basename(rom))[0], "image": _png_url(png), "exact": True}]}
    shared = [s.label for s in SYSTEMS if s.games_dir.lower() == name.lower()]
    q = (query or "").strip() or (shared[0] if shared else name)
    out.extend(_sgdb_icons(q))
    repos: list[str] = []
    for s in SYSTEMS:
        if s.games_dir.lower() == name.lower() and s.libretro_repo not in repos:
            repos.append(s.libretro_repo)
    if not repos:
        try:
            for n in os.listdir(folder):
                s = system_for_extension(n)
                if s and s.libretro_repo not in repos:
                    repos.append(s.libretro_repo)
        except OSError:
            pass
    out.extend(_logo_icons(repos[:2], q))
    return {"success": True, "sources": out, "steamgriddb_key": has_api_key()}


def save_banner(mount_path: str, rel_folder: str, title: str, icon_token: Any = None, keep_icon: bool = False, log=None) -> dict[str, Any]:
    from core.logging_util import emit_log
    from core.routedex import RouteDexError, build_banner, encode_icon_rgba, parse_banner
    from core.sdio import sync_volume

    folder = _folder(mount_path, rel_folder)
    bnr = os.path.join(folder, "banner.bnr")
    if keep_icon:
        try:
            with open(bnr, "rb") as f:
                info = parse_banner(f.read())
        except (OSError, RouteDexError) as e:
            raise ArtPickerError("Não há ícone atual para manter; escolha um.") from e
        bitmap, palette = info["bitmap"], info["palette"]
    else:
        entry = _stage_get(icon_token, "icon")
        bitmap, palette = encode_icon_rgba(entry["rgba"])
    try:
        data = build_banner(bitmap, palette, title)
    except RouteDexError as e:
        raise ArtPickerError(str(e)) from e
    _write_verified(bnr, data)
    try:
        sync_volume(mount_path)
    except Exception:
        pass
    rel = os.path.relpath(bnr, mount_path).replace(os.sep, "/")
    emit_log(log, f"✅ Banner de pasta gravado: /{rel}")
    return {"success": True, "written": rel}
