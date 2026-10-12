"""Capas e ícones para Pico Launcher (DSPico): pesquisa + gravação BMP em /_pico/."""

from __future__ import annotations

import base64
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Optional

from concurrent.futures import ThreadPoolExecutor

from core.artwork import (
    _fetch_first_ok,
    boxart_urls_for_tid,
    is_nds_family_platform,
    jsdelivr_libretro_urls,
    libretro_name_candidates,
    libretro_platform_key,
    libretro_sanitize_name,
    libretro_urls,
)
from core.cache import USER_AGENT
from core.disks import is_safe_mount_path
from core.dspico import (
    GAME_EXTS,
    GAMES_DIRNAME,
    RETRO_EXTS,
    ROMS_DIRNAME,
    _RETRO_PLATFORM,
    _resolve_under_games,
    _resolve_under_roms_folder,
)
from core.logging_util import emit_log
from core.pico_bmp import (
    bmp_to_preview_png,
    image_bytes_to_pico_bmp,
    image_bytes_to_preview_png,
)
from core.privacy import redact_path
from core.rom_cleaner import get_nds_header_info
from core.sdio import sync_volume

LogFn = Callable[[str], None]

ART_KINDS = frozenset({"cover", "icon"})
_ALLOWED_HOSTS = frozenset(
    {"art.gametdb.com", "thumbnails.libretro.com", "cdn.jsdelivr.net"}
)
_DOWNLOAD_TIMEOUT = 25
_PROBE_TIMEOUT = 12
_MAX_CANDIDATES = 24
_MAX_PROBE_ATTEMPTS = 48
_BATCH_MAX_CANDIDATES = 8
_BATCH_DOWNLOAD_TIMEOUT = 8
_BATCH_HTTP_WORKERS = 3
_INTER_DELAY = 0.08
# Capas/ícones são imagens pequenas; sem teto um redirect/stream pode encher o disco.
_MAX_DOWNLOAD_BYTES = 2 * 1024 * 1024
_MAX_PROBE_BYTES = 256


def _emit_batch_progress(payload: dict[str, Any]) -> None:
    """Push best-effort para a UI (não bloqueia o lote)."""
    from core.progress import emit_progress

    emit_progress(payload)

_REGION_SUFFIXES = (
    "",
    " (USA)",
    " (Europe)",
    " (Japan)",
    " (USA, Europe)",
    " (World)",
    " (En,Fr,De,Es,It)",
    " (USA) (Rev 1)",
)

_TID_RE = re.compile(r"^[A-Za-z0-9]{4}$")


def _valid_tid(game_code: Optional[str]) -> Optional[str]:
    code = (game_code or "").replace("\x00", "").strip().upper()
    if len(code) != 4 or not code.isalnum() or code in ("####", "0000"):
        return None
    return code


def _safe_under(root: str, path: str) -> bool:
    try:
        root_r = os.path.realpath(root)
        path_r = os.path.realpath(path)
        return os.path.commonpath([root_r, path_r]) == root_r
    except (ValueError, OSError):
        return False


def _pico_asset_dir(mount_path: str, kind: str, bucket: str) -> str:
    """kind: cover|icon → /_pico/covers|icons / bucket (nds|user)."""
    folder = "covers" if kind == "cover" else "icons"
    return os.path.join(mount_path, "_pico", folder, bucket)


def _dest_paths(
    mount_path: str,
    basename: str,
    tid: Optional[str],
    kind: str,
    *,
    code_bucket: str = "nds",
) -> list[str]:
    """Destinos: TID em nds|gba/ depois user/ por nome do ficheiro (Customization.md)."""
    out: list[str] = []
    if tid:
        bucket = code_bucket if code_bucket in ("nds", "gba") else "nds"
        out.append(
            os.path.join(_pico_asset_dir(mount_path, kind, bucket), f"{tid}.bmp")
        )
    out.append(
        os.path.join(_pico_asset_dir(mount_path, kind, "user"), f"{basename}.bmp")
    )
    return out


def resolve_existing_art(
    mount_path: str, basename: str, tid: Optional[str], kind: str
) -> Optional[str]:
    """Prioridade Pico: user > código (nds/ ou gba/)."""
    user = os.path.join(_pico_asset_dir(mount_path, kind, "user"), f"{basename}.bmp")
    if os.path.isfile(user) and os.path.getsize(user) > 64:
        return user
    if tid:
        for bucket in ("nds", "gba"):
            by_tid = os.path.join(
                _pico_asset_dir(mount_path, kind, bucket), f"{tid}.bmp"
            )
            if os.path.isfile(by_tid) and os.path.getsize(by_tid) > 64:
                return by_tid
    return None


def _gba_game_code(path: str) -> Optional[str]:
    """Lê o game code interno GBA (offset 0xAC), se válido."""
    try:
        with open(path, "rb") as f:
            f.seek(0xAC)
            raw = f.read(4)
    except OSError:
        return None
    if len(raw) != 4:
        return None
    try:
        code = raw.decode("ascii")
    except UnicodeDecodeError:
        return None
    return _valid_tid(code)


def _png_data_url(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def _url_allowed(url: str) -> bool:
    try:
        parts = urllib.parse.urlparse(url)
    except ValueError:
        return False
    if parts.scheme != "https" or not parts.hostname:
        return False
    if parts.hostname.lower() in _ALLOWED_HOSTS:
        return True
    from core.steamgriddb import is_asset_url

    return is_asset_url(url)


def _content_length_ok(resp, *, max_bytes: int) -> bool:
    raw = None
    try:
        headers = getattr(resp, "headers", None)
        if headers is not None:
            raw = headers.get("Content-Length")
    except Exception:
        raw = None
    if raw is None:
        return True
    try:
        return int(raw) <= max_bytes
    except (TypeError, ValueError):
        return True


def _read_capped(resp, *, max_bytes: int) -> Optional[bytes]:
    """Lê no máximo max_bytes+1; None se exceder o teto."""
    if not _content_length_ok(resp, max_bytes=max_bytes):
        return None
    chunks: list[bytes] = []
    total = 0
    limit = max_bytes + 1
    while total < limit:
        try:
            block = resp.read(min(65536, limit - total))
        except (OSError, TimeoutError):
            return None
        if not block:
            break
        chunks.append(block)
        total += len(block)
    if total > max_bytes:
        return None
    return b"".join(chunks) if chunks else None


def _http_get(url: str, timeout: float = _DOWNLOAD_TIMEOUT) -> Optional[bytes]:
    if not _url_allowed(url):
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
            data = _read_capped(resp, max_bytes=_MAX_DOWNLOAD_BYTES)
        return data if data else None
    except (OSError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return None


def _http_exists(url: str) -> bool:
    if not _url_allowed(url):
        return False
    try:
        req = urllib.request.Request(
            url, method="HEAD", headers={"User-Agent": USER_AGENT}
        )
        with urllib.request.urlopen(req, timeout=_PROBE_TIMEOUT) as resp:  # nosec B310
            code = getattr(resp, "status", None) or resp.getcode()
            if not (200 <= int(code) < 300):
                return False
            return _content_length_ok(resp, max_bytes=_MAX_DOWNLOAD_BYTES)
    except (OSError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
        # Alguns CDNs rejeitam HEAD — tentar GET curto via Range
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Range": f"bytes=0-{_MAX_PROBE_BYTES}",
                },
            )
            with urllib.request.urlopen(req, timeout=_PROBE_TIMEOUT) as resp:  # nosec B310
                code = getattr(resp, "status", None) or resp.getcode()
                if int(code) not in (200, 206):
                    return False
                # Descarta o corpo (já limitado pelo Range) sem acumular.
                _ = _read_capped(resp, max_bytes=_MAX_PROBE_BYTES)
                return True
        except (OSError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
            return False


def _search_name_variants(
    query: str, basename: str = "", *, fake_ext: str = ".nds"
) -> list[str]:
    """Candidatos de nome para Libretro a partir da query / ficheiro."""
    out: list[str] = []
    seen: set[str] = set()
    ext = (fake_ext or ".nds").lower()
    if not ext.startswith("."):
        ext = "." + ext

    def _add(raw: str) -> None:
        s = libretro_sanitize_name((raw or "").strip())
        if s and s not in seen:
            seen.add(s)
            out.append(s)

    # Preferir basename real (com extensão) para strip No-Intro correcto.
    bases: list[str] = []
    if basename and str(basename).strip():
        bases.append(str(basename).strip())
    if query and str(query).strip():
        q = str(query).strip()
        bases.append(q if "." in os.path.basename(q) else q + ext)

    for base in bases:
        if not base:
            continue
        # libretro_name_candidates usa só o stem; extensão só serve de contexto.
        name_src = base if "." in os.path.basename(base) else base + ext
        for name in libretro_name_candidates(name_src):
            _add(name)
        stem = libretro_sanitize_name(os.path.splitext(os.path.basename(base))[0])
        if stem:
            for suf in _REGION_SUFFIXES:
                _add(stem + suf)
            words = stem.split()
            for n in range(len(words), 0, -1):
                _add(" ".join(words[:n]))
                if n <= 2:
                    break
    return out[:40]


def _resolve_game(
    mount_path: str, rel_path: str
) -> tuple[Optional[str], Optional[dict[str, Any]]]:
    """Devolve (erro, meta) para um jogo em Games/ ou ROM retro em ROMs/."""
    if not is_safe_mount_path(mount_path):
        return "Unidade não reconhecida como volume removível/USB/SD.", None
    rel = (rel_path or "").replace("\\", "/").lstrip("/")
    if not rel or ".." in rel.split("/"):
        return "Caminho de jogo inválido.", None

    full: Optional[str] = None
    area = "games"
    if rel == ROMS_DIRNAME or rel.startswith(f"{ROMS_DIRNAME}/"):
        full = _resolve_under_roms_folder(mount_path, rel)
        area = "roms"
    elif rel == GAMES_DIRNAME or rel.startswith(f"{GAMES_DIRNAME}/"):
        under = rel[len(GAMES_DIRNAME) :].lstrip("/")
        full = _resolve_under_games(mount_path, under)
        rel = under or rel
    else:
        full = _resolve_under_games(mount_path, rel)

    if not full or not os.path.isfile(full):
        if area == "roms":
            return f"ROM inexistente sob {ROMS_DIRNAME}/.", None
        return f"Jogo inexistente sob {GAMES_DIRNAME}/.", None

    basename = os.path.basename(full)
    ext = os.path.splitext(basename)[1].lower()
    display = os.path.splitext(basename)[0]

    if area == "roms" or ext in RETRO_EXTS:
        if ext not in RETRO_EXTS:
            return "Extensão retro não suportada.", None
        platform = _RETRO_PLATFORM.get(ext, "retro")
        tid = _gba_game_code(full) if platform == "gba" else None
        try:
            show_rel = os.path.relpath(full, mount_path).replace("\\", "/")
        except ValueError:
            show_rel = f"{ROMS_DIRNAME}/{basename}"
        return None, {
            "full": full,
            "rel_path": show_rel,
            "basename": basename,
            "display_name": display,
            "title": display,
            "game_code": tid,
            "platform": platform,
            "area": "roms",
            "code_bucket": "gba" if platform == "gba" else "nds",
        }

    if ext not in GAME_EXTS:
        return "Só jogos NDS/DSi ou ROMs retro (GB/GBC/GBA/SNES) são suportados.", None
    title, code, _unit, _maker = get_nds_header_info(full)
    tid = _valid_tid(code)
    return None, {
        "full": full,
        "rel_path": rel,
        "basename": basename,
        "display_name": display,
        "title": (title or "").strip() or None,
        "game_code": tid,
        "platform": "dsi" if ext == ".dsi" else "nds",
        "area": "games",
        "code_bucket": "nds",
    }


def enrich_dspico_game_entry(
    mount_path: str, entry: dict[str, Any], *, with_preview: bool = False
) -> dict[str, Any]:
    """Adiciona flags (e opcionalmente previews) de arte a um item de browse.

    Não exige is_safe_mount_path — o caller (browse) já opera sobre a montagem.
    Reutiliza ``game_code`` do entry quando válido (evita 2.ª leitura do header NDS).
    """
    rel = (entry.get("rel_path") or "").replace("\\", "/").lstrip("/")
    entry["has_cover"] = False
    entry["has_icon"] = False
    if not rel or ".." in rel.split("/"):
        return entry

    area = (entry.get("area") or "").strip().lower()
    if area == "roms" or rel.startswith(f"{ROMS_DIRNAME}/"):
        full = _resolve_under_roms_folder(mount_path, rel)
    else:
        full = _resolve_under_games(mount_path, rel)
    if not full or not os.path.isfile(full):
        return entry

    basename = os.path.basename(full)
    ext = os.path.splitext(basename)[1].lower()
    tid: Optional[str] = None
    if ext in GAME_EXTS:
        existing = entry.get("game_code")
        if isinstance(existing, str) and existing:
            tid = _valid_tid(existing)
        if not tid:
            _title, code, _unit, _maker = get_nds_header_info(full)
            tid = _valid_tid(code)
    elif ext in RETRO_EXTS:
        if _RETRO_PLATFORM.get(ext) == "gba":
            tid = _gba_game_code(full)
    else:
        return entry

    cover = resolve_existing_art(mount_path, basename, tid, "cover")
    icon = resolve_existing_art(mount_path, basename, tid, "icon")
    entry["has_cover"] = bool(cover)
    entry["has_icon"] = bool(icon)
    if tid:
        entry["game_code"] = tid
    if not with_preview:
        return entry
    entry["cover"] = None
    entry["icon"] = None
    if cover:
        try:
            with open(cover, "rb") as f:
                entry["cover"] = _png_data_url(bmp_to_preview_png(f.read()))
        except (OSError, ValueError):
            pass
    if icon:
        try:
            with open(icon, "rb") as f:
                entry["icon"] = _png_data_url(bmp_to_preview_png(f.read()))
        except (OSError, ValueError):
            pass
    return entry


def get_dspico_game_previews(
    mount_path: str,
    rel_paths: list,
    *,
    max_items: int = 24,
) -> dict[str, Any]:
    """Pré-visualizações BMP→PNG (data-URL) para um subconjunto de jogos.

    Destinado a preenchimento lazy na UI após browse sem ``with_preview``.
    """
    if not isinstance(mount_path, str) or not mount_path.strip():
        return {"success": False, "error": "Caminho do cartão inválido.", "previews": {}}
    if not os.path.isdir(mount_path):
        return {"success": False, "error": "Cartão inexistente.", "previews": {}}
    try:
        limit = int(max_items)
    except (TypeError, ValueError):
        limit = 24
    if limit < 1:
        limit = 1
    if limit > 48:
        limit = 48

    paths: list[str] = []
    if isinstance(rel_paths, list):
        for raw in rel_paths:
            if not isinstance(raw, str) or not raw or "\x00" in raw:
                continue
            rel = raw.replace("\\", "/").lstrip("/")
            if not rel or ".." in rel.split("/"):
                continue
            paths.append(rel)
            if len(paths) >= limit:
                break

    previews: dict[str, Any] = {}
    for rel in paths:
        area = "roms" if rel.startswith(f"{ROMS_DIRNAME}/") else "games"
        entry: dict[str, Any] = {"rel_path": rel, "area": area}
        try:
            enrich_dspico_game_entry(mount_path, entry, with_preview=True)
        except Exception:
            continue
        if not entry.get("cover") and not entry.get("icon"):
            if not entry.get("has_cover") and not entry.get("has_icon"):
                continue
        previews[rel] = {
            "cover": entry.get("cover"),
            "icon": entry.get("icon"),
            "has_cover": bool(entry.get("has_cover")),
            "has_icon": bool(entry.get("has_icon")),
        }
    return {"success": True, "previews": previews}


def _collect_candidate_urls(
    *,
    kind: str,
    platform: str,
    basename: str,
    tid: Optional[str],
    title: Optional[str],
    query: str,
) -> list[dict[str, str]]:
    """Lista ordenada de {url, label, source} a sondar."""
    items: list[dict[str, str]] = []
    seen: set[str] = set()

    def _push(
        url: str, label: str, source: str, *, preview: Optional[str] = None
    ) -> None:
        if not url or url in seen or not _url_allowed(url):
            return
        seen.add(url)
        entry = {"url": url, "label": label, "source": source}
        if preview and _url_allowed(preview):
            entry["preview"] = preview
        items.append(entry)

    from core.steamgriddb import candidate_assets, has_api_key, search_term_from_rom

    lr_kind = "boxart" if kind == "cover" else "icon"
    lr_key = libretro_platform_key(platform)
    nds_family = is_nds_family_platform(platform)
    fake_ext = os.path.splitext(basename or "")[1] or ".nds"
    q = (query or "").strip()

    # 1.ª fonte: SteamGridDB (API → CDN).
    if has_api_key():
        term = search_term_from_rom(basename, title=title, query=q)
        if term:
            for a in candidate_assets(term, kind, game_name=term, limit=12):
                _push(
                    a["url"],
                    str(a.get("label") or f"SteamGridDB · {term}"),
                    "steamgriddb",
                    preview=str(a.get("preview") or a.get("thumb") or ""),
                )

    # GameTDB só para NDS/DSi (URLs /ds/coverS/).
    if kind == "cover" and tid and nds_family:
        for url in boxart_urls_for_tid(tid):
            _push(url, f"GameTDB · {tid}", "gametdb")

    if q and _TID_RE.match(q) and kind == "cover" and nds_family:
        for url in boxart_urls_for_tid(q.upper()):
            _push(url, f"GameTDB · {q.upper()}", "gametdb")

    names = _search_name_variants(q, basename, fake_ext=fake_ext)
    if title:
        for n in _search_name_variants(title, "", fake_ext=fake_ext):
            if n not in names:
                names.append(n)

    if lr_key:
        for name in names:
            for url in libretro_urls(lr_key, name, kind=lr_kind):
                _push(url, name, "libretro")
            for url in jsdelivr_libretro_urls(lr_key, name, kind=lr_kind):
                _push(url, name, "jsdelivr")

    return items


def search_dspico_artwork(
    mount_path: str,
    rel_path: str,
    kind: str = "cover",
    query: str = "",
    log_callback=None,
) -> dict[str, Any]:
    """
    Lista opções de capas/ícones **sem descarregar** bytes para o PC.

    Cada candidato traz `url` / `preview` (URL remota allowlisted). A UI mostra
    a miniatura via <img src>; só `apply_dspico_artwork_url` descarrega a
    escolha do utilizador e grava BMP no cartão SD.
    kind: cover | icon
    """
    log = lambda msg: emit_log(log_callback, msg)
    kind_n = (kind or "cover").strip().lower()
    if kind_n not in ART_KINDS:
        return {"success": False, "error": "Tipo inválido (cover ou icon).", "candidates": []}

    err, meta = _resolve_game(mount_path, rel_path)
    if err or not meta:
        return {"success": False, "error": err or "Jogo inválido.", "candidates": []}

    q = query if isinstance(query, str) else ""
    if "\x00" in q:
        return {"success": False, "error": "Pesquisa inválida.", "candidates": []}
    q = q.strip()[:120]

    # Pré-visualização do que já está no cartão (lê só o SD, sem cache no host).
    current_path = resolve_existing_art(
        mount_path, meta["basename"], meta["game_code"], kind_n
    )
    current_preview = None
    if current_path:
        try:
            with open(current_path, "rb") as f:
                current_preview = _png_data_url(bmp_to_preview_png(f.read()))
        except (OSError, ValueError):
            current_preview = None

    probes = _collect_candidate_urls(
        kind=kind_n,
        platform=meta["platform"],
        basename=meta["basename"],
        tid=meta["game_code"],
        title=meta.get("title"),
        query=q,
    )
    log(
        f"A listar opções de {'capa' if kind_n == 'cover' else 'ícone'} "
        f"para {meta['display_name']}…"
    )

    from core.steamgriddb import has_api_key

    candidates: list[dict[str, Any]] = []
    probed = 0
    for item in probes:
        if len(candidates) >= _MAX_CANDIDATES:
            break
        if probed >= _MAX_PROBE_ATTEMPTS:
            break
        url = item.get("url")
        if not isinstance(url, str) or not _url_allowed(url):
            continue
        probed += 1
        source = item.get("source") or ""
        # SteamGridDB: URLs vindas da API — sem HEAD; restantes fontes: sondar.
        if source != "steamgriddb" and not _http_exists(url):
            continue
        preview = item.get("preview") or url
        if isinstance(preview, str) and not _url_allowed(preview):
            preview = url
        candidates.append(
            {
                "url": url,
                "label": item.get("label") or source or "opção",
                "source": source,
                "preview": preview,
            }
        )

    lr_key = libretro_platform_key(meta.get("platform") or "")
    sgdb_on = has_api_key()
    if candidates:
        msg = (
            f"{len(candidates)} opção(ões) — escolha uma para gravar no cartão."
        )
    elif not sgdb_on and not is_nds_family_platform(meta.get("platform")):
        # Retro sem SGDB: Libretro quase nunca acerta nomes BR — pedir chave.
        msg = (
            "Sem chave SteamGridDB — em Definições (barra lateral) → "
            "secção SteamGridDB, cole a chave e Guarde. "
            "Ou escolha um ficheiro PNG/BMP."
        )
    elif not lr_key and not is_nds_family_platform(meta.get("platform")) and not sgdb_on:
        msg = (
            "Sem fonte online para esta plataforma — "
            "configure SteamGridDB em Definições ou escolha um ficheiro PNG/BMP."
        )
    else:
        msg = (
            "Nenhuma imagem encontrada — tente outro nome/TID "
            "ou escolha um ficheiro PNG/BMP."
        )
    if candidates:
        log(f"✅ {msg}")
    else:
        log(f"⚠️ {msg}")

    return {
        "success": True,
        "message": msg,
        "kind": kind_n,
        "rel_path": meta["rel_path"],
        "display_name": meta["display_name"],
        "game_code": meta["game_code"],
        "platform": meta.get("platform"),
        "area": meta.get("area") or "games",
        "query": q,
        "current": current_preview,
        "candidates": candidates,
        "hints": {
            "cover": (
                "Qualquer PNG/BMP é convertido para BMP 128×96 8-bit "
                "(área útil 106×96) em /_pico/covers/…"
            ),
            "icon": (
                "Qualquer PNG/BMP é convertido para BMP 32×32 4-bit "
                "(cor 0 transparente) em /_pico/icons/…"
            ),
        },
    }


def apply_dspico_artwork_url(
    mount_path: str,
    rel_path: str,
    kind: str,
    url: str,
    log_callback=None,
) -> tuple[bool, str, dict[str, Any]]:
    """
    Descarrega só a URL escolhida (memória) e grava BMP directamente no cartão SD.

    Não usa a cache do Route 1 Kit nem ficheiros temporários no disco do PC —
    o destino final é `/_pico/covers|icons/...` no mount do cartão.
    """
    log = lambda msg: emit_log(log_callback, msg)
    stats: dict[str, Any] = {}
    kind_n = (kind or "cover").strip().lower()
    if kind_n not in ART_KINDS:
        return False, "Tipo inválido (cover ou icon).", stats
    if not isinstance(url, str) or not _url_allowed(url):
        return False, "URL de arte não permitida.", stats

    err, meta = _resolve_game(mount_path, rel_path)
    if err or not meta:
        return False, err or "Jogo inválido.", stats

    log("A descarregar e converter a imagem para o formato Pico…")
    raw = _http_get(url)
    if not raw:
        return False, "Falha ao descarregar a imagem.", stats
    try:
        bmp = image_bytes_to_pico_bmp(raw, kind_n)
    except ValueError as e:
        return False, f"Imagem inválida (conversão): {e}", stats
    # Libertar o PNG/JPEG original antes da escrita no SD.
    del raw

    return _write_pico_bmp(
        mount_path, meta, kind_n, bmp, log=log, stats=stats, note="online"
    )


def set_dspico_artwork_file(
    mount_path: str,
    rel_path: str,
    kind: str,
    source_path: str,
    log_callback=None,
) -> tuple[bool, str, dict[str, Any]]:
    """Converte ficheiro local (PNG/BMP) para BMP Pico e grava."""
    log = lambda msg: emit_log(log_callback, msg)
    stats: dict[str, Any] = {}
    kind_n = (kind or "cover").strip().lower()
    if kind_n not in ART_KINDS:
        return False, "Tipo inválido (cover ou icon).", stats

    err, meta = _resolve_game(mount_path, rel_path)
    if err or not meta:
        return False, err or "Jogo inválido.", stats

    src = (source_path or "").strip()
    if not src or "\x00" in src or not os.path.isfile(src):
        return False, "Ficheiro de imagem inexistente.", stats
    try:
        size = os.path.getsize(src)
    except OSError:
        return False, "Ficheiro de imagem inacessível.", stats
    if size < 64 or size > 12 * 1024 * 1024:
        return False, "Tamanho de imagem inválido.", stats

    try:
        with open(src, "rb") as f:
            raw = f.read()
        bmp = image_bytes_to_pico_bmp(raw, kind_n)
    except (OSError, ValueError) as e:
        return False, f"Não foi possível ler a imagem: {e}", stats

    return _write_pico_bmp(
        mount_path,
        meta,
        kind_n,
        bmp,
        log=log,
        stats=stats,
        note=redact_path(src),
    )


def _write_pico_bmp(
    mount_path: str,
    meta: dict[str, Any],
    kind: str,
    bmp: bytes,
    *,
    log: LogFn,
    stats: dict[str, Any],
    note: str,
    defer_sync: bool = False,
) -> tuple[bool, str, dict[str, Any]]:
    # Retro sem código → só user/{ficheiro}.bmp (Customization.md).
    # GBA com código → gba/{TID}.bmp; NDS → nds/{TID}.bmp.
    code_bucket = meta.get("code_bucket") or "nds"
    if meta.get("area") == "roms" and not meta.get("game_code"):
        dests = _dest_paths(mount_path, meta["basename"], None, kind)
    else:
        dests = _dest_paths(
            mount_path,
            meta["basename"],
            meta.get("game_code"),
            kind,
            code_bucket=code_bucket,
        )
    if not dests:
        return False, "Sem destino de arte.", stats

    # Gravar em todos os destinos canónicos (TID + user) para compatibilidade
    # com modos de lookup diferentes do launcher.
    written: list[str] = []
    seen: set[str] = set()
    for dest in dests:
        if not dest or dest in seen:
            continue
        seen.add(dest)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        partial = dest + ".partial"
        try:
            with open(partial, "wb") as f:
                f.write(bmp)
                f.flush()
                os.fsync(f.fileno())
            if len(bmp) < 64:
                raise OSError("BMP gerado demasiado pequeno.")
            os.replace(partial, dest)
            written.append(dest)
        except OSError as e:
            try:
                if os.path.exists(partial):
                    os.remove(partial)
            except OSError:
                pass
            return False, f"Falha ao gravar arte: {e}", stats

    if not defer_sync:
        try:
            sync_volume(mount_path)
        except Exception:
            pass

    label = "capa" if kind == "cover" else "ícone"
    rel_paths = [
        os.path.relpath(path, mount_path).replace("\\", "/") for path in written
    ]
    rel_dest = rel_paths[0] if rel_paths else ""
    if rel_paths:
        log(
            f"✅ {label.capitalize()} gravada: "
            + ", ".join(f"/{p}" for p in rel_paths)
            + f" ({note})"
        )
    stats["path"] = rel_dest
    stats["paths"] = rel_paths
    stats["kind"] = kind
    if len(rel_paths) > 1:
        return (
            True,
            f"{label.capitalize()} actualizada em {len(rel_paths)} destino(s).",
            stats,
        )
    return True, f"{label.capitalize()} actualizada em /{rel_dest}.", stats


def _batch_candidate_urls(
    *,
    kind: str,
    platform: str,
    basename: str,
    tid: Optional[str],
    title: Optional[str],
) -> list[str]:
    """
    Lista curta para lote: SteamGridDB → GameTDB → Libretro → jsDelivr.
    Sem HEAD — o caller faz GET directo na 1.ª que converter.
    """
    from core.steamgriddb import candidate_assets, has_api_key, search_term_from_rom

    urls: list[str] = []
    seen: set[str] = set()

    def _push(url: str) -> None:
        if not url or url in seen or not _url_allowed(url):
            return
        seen.add(url)
        urls.append(url)

    lr_kind = "boxart" if kind == "cover" else "icon"
    plat = libretro_platform_key(platform)
    nds_family = is_nds_family_platform(platform)
    fake_ext = os.path.splitext(basename or "")[1] or ".nds"

    if has_api_key():
        term = search_term_from_rom(basename, title=title)
        if term:
            for a in candidate_assets(term, kind, limit=4):
                _push(a["url"])
                if len(urls) >= _BATCH_MAX_CANDIDATES:
                    return urls[:_BATCH_MAX_CANDIDATES]

    if kind == "cover" and tid and nds_family:
        for url in boxart_urls_for_tid(tid)[:3]:
            _push(url)

    names: list[str] = []
    for raw in (basename, title or ""):
        if not raw:
            continue
        src = raw if "." in os.path.basename(str(raw)) else f"{raw}{fake_ext}"
        for n in libretro_name_candidates(src):
            if n not in names:
                names.append(n)
        if len(names) >= 3:
            break

    if plat:
        for name in names[:3]:
            for url in libretro_urls(plat, name, kind=lr_kind):
                _push(url)
            for url in jsdelivr_libretro_urls(plat, name, kind=lr_kind):
                _push(url)
            if len(urls) >= _BATCH_MAX_CANDIDATES:
                break

    return urls[:_BATCH_MAX_CANDIDATES]


def _apply_bytes_to_meta(
    mount_path: str,
    meta: dict[str, Any],
    kind: str,
    raw: bytes,
    *,
    log: LogFn,
    defer_sync: bool = True,
) -> bool:
    """Converte bytes → BMP Pico e grava com meta já resolvido."""
    try:
        bmp = image_bytes_to_pico_bmp(raw, kind)
    except ValueError:
        return False
    ok, _msg, _st = _write_pico_bmp(
        mount_path,
        meta,
        kind,
        bmp,
        log=log,
        stats={},
        note="lote",
        defer_sync=defer_sync,
    )
    return ok


def get_dspico_game_artwork(
    mount_path: str, rel_path: str
) -> dict[str, Any]:
    """Estado actual de capa/ícone + metadados do jogo."""
    err, meta = _resolve_game(mount_path, rel_path)
    if err or not meta:
        return {"success": False, "error": err or "Jogo inválido."}
    out: dict[str, Any] = {
        "success": True,
        "rel_path": meta["rel_path"],
        "display_name": meta["display_name"],
        "basename": meta["basename"],
        "game_code": meta["game_code"],
        "title": meta.get("title"),
        "cover": None,
        "icon": None,
        "has_cover": False,
        "has_icon": False,
        "platform": meta.get("platform"),
        "area": meta.get("area") or "games",
        "hints": {
            "cover": (
                "Imagens online ou do PC são convertidas para BMP 128×96 8-bit "
                "em /_pico/covers/…"
            ),
            "icon": (
                "Imagens online ou do PC são convertidas para BMP 32×32 4-bit "
                "(transparência) em /_pico/icons/…"
            ),
        },
    }
    for kind in ("cover", "icon"):
        path = resolve_existing_art(
            mount_path, meta["basename"], meta["game_code"], kind
        )
        if not path:
            continue
        try:
            with open(path, "rb") as f:
                preview = _png_data_url(bmp_to_preview_png(f.read()))
            out[kind] = preview
            out[f"has_{kind}"] = True
        except (OSError, ValueError):
            pass
    return out


def generate_dspico_artwork_batch(
    mount_path: str, log_callback=None, *, max_games: int = 200
) -> dict[str, Any]:
    """
    Gera capas e ícones Pico (BMP) em lote — 1.ª URL válida por kind.
    Não sobrescreve arte já existente. Retorna missing[] para falhas.
    HTTP first-hit paralelo; BMP no SD na thread da op; sync no fim.
    """
    from core.progress import OperationCancelled, ProgressTracker, check_cancelled

    log = lambda msg: emit_log(log_callback, msg)
    try:
        max_n = int(max_games)
    except (TypeError, ValueError):
        max_n = 200
    if max_n < 1:
        max_n = 1
    if max_n > 500:
        max_n = 500

    if not is_safe_mount_path(mount_path):
        return {
            "success": False,
            "error": "Unidade não reconhecida como volume removível/USB/SD.",
            "written": 0,
            "missing": [],
        }

    games_root = os.path.join(mount_path, GAMES_DIRNAME)
    roms_root = os.path.join(mount_path, ROMS_DIRNAME)
    if not os.path.isdir(games_root) and not os.path.isdir(roms_root):
        return {
            "success": False,
            "error": "Pastas Games/ e ROMs/ inexistentes.",
            "written": 0,
            "missing": [],
        }

    roms: list[str] = []
    if os.path.isdir(games_root):
        for root, _dirs, files in os.walk(games_root):
            for name in files:
                ext = os.path.splitext(name)[1].lower()
                if ext not in GAME_EXTS and ext not in RETRO_EXTS:
                    continue
                full = os.path.join(root, name)
                rel = os.path.relpath(full, games_root).replace("\\", "/")
                if ".." in rel.split("/"):
                    continue
                roms.append(rel)
                if len(roms) >= max_n:
                    break
            if len(roms) >= max_n:
                break
    if len(roms) < max_n and os.path.isdir(roms_root):
        for root, _dirs, files in os.walk(roms_root):
            for name in files:
                ext = os.path.splitext(name)[1].lower()
                if ext not in RETRO_EXTS:
                    continue
                full = os.path.join(root, name)
                try:
                    rel = os.path.relpath(full, mount_path).replace("\\", "/")
                except ValueError:
                    continue
                if ".." in rel.split("/"):
                    continue
                roms.append(rel)
                if len(roms) >= max_n:
                    break
            if len(roms) >= max_n:
                break

    written = 0
    skipped = 0
    failed = 0
    missing: list[dict[str, Any]] = []
    scanned = len(roms)

    # Pré-resolver + skip jogos já completos.
    work: list[dict[str, Any]] = []
    for rel in roms:
        err, meta = _resolve_game(mount_path, rel)
        if err or not meta:
            work.append({"rel": rel, "meta": None, "err": err})
            continue
        has_cover = bool(
            resolve_existing_art(
                mount_path, meta["basename"], meta.get("game_code"), "cover"
            )
        )
        has_icon = bool(
            resolve_existing_art(
                mount_path, meta["basename"], meta.get("game_code"), "icon"
            )
        )
        if has_cover and has_icon:
            skipped += 2
            continue
        work.append(
            {
                "rel": rel,
                "meta": meta,
                "err": None,
                "has_cover": has_cover,
                "has_icon": has_icon,
            }
        )

    total = len(work)
    log(
        f"=== Capas e ícones DSPico em lote: {scanned} jogo(s), "
        f"{total} por processar ==="
    )

    tracker = ProgressTracker(
        "dspico_artwork_batch",
        label="A iniciar…",
        total_items=total,
        emit_fn=_emit_batch_progress,
    )
    tracker.cancellable = True
    tracker.skipped = skipped

    def _fetch_kind_bytes(meta: dict[str, Any], kind: str) -> Optional[bytes]:
        probes = _batch_candidate_urls(
            kind=kind,
            platform=meta.get("platform") or "nds",
            basename=meta["basename"],
            tid=meta.get("game_code"),
            title=meta.get("title"),
        )
        if not probes:
            return None
        return _fetch_first_ok(
            probes,
            max_urls=_BATCH_MAX_CANDIDATES,
            timeout=_BATCH_DOWNLOAD_TIMEOUT,
            workers=_BATCH_HTTP_WORKERS,
        )

    def _finish_ok(message: str) -> dict[str, Any]:
        try:
            sync_volume(mount_path)
        except Exception:
            pass
        log(f"✅ {message}" if written else f"⚠️ {message}")
        tracker.written = written
        tracker.skipped = skipped
        tracker.failed = failed
        tracker.finish(message)
        return {
            "success": True,
            "message": message,
            "written": written,
            "skipped": skipped,
            "failed": failed,
            "scanned": scanned,
            "missing": missing,
        }

    if not work:
        return _finish_ok(
            f"{written} arte(s) gravada(s); {skipped} já existiam; "
            f"0 jogo(s) com falhas."
        )

    tracker.tick(force=True)
    try:
        for idx, job in enumerate(work, start=1):
            check_cancelled()
            rel = job["rel"]
            meta = job.get("meta")
            if not meta:
                failed += 2
                missing.append(
                    {
                        "rel_path": rel,
                        "display_name": os.path.basename(rel),
                        "game_code": None,
                        "missing_cover": True,
                        "missing_icon": True,
                    }
                )
                tracker.written = written
                tracker.skipped = skipped
                tracker.failed = failed
                tracker.current = idx
                tracker.set_label(os.path.basename(rel))
                tracker.tick(force=True)
                continue

            display = meta.get("display_name") or meta.get("basename") or rel
            tracker.set_label(display)
            tracker.tick(force=True)

            need_cover = not job.get("has_cover")
            need_icon = not job.get("has_icon")
            cover_raw: Optional[bytes] = None
            icon_raw: Optional[bytes] = None

            if need_cover and need_icon:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    f_c = pool.submit(_fetch_kind_bytes, meta, "cover")
                    f_i = pool.submit(_fetch_kind_bytes, meta, "icon")
                    try:
                        cover_raw = f_c.result()
                    except Exception:
                        cover_raw = None
                    try:
                        icon_raw = f_i.result()
                    except Exception:
                        icon_raw = None
            elif need_cover:
                cover_raw = _fetch_kind_bytes(meta, "cover")
            elif need_icon:
                icon_raw = _fetch_kind_bytes(meta, "icon")

            miss_cover = False
            miss_icon = False

            if need_cover:
                if cover_raw and _apply_bytes_to_meta(
                    mount_path, meta, "cover", cover_raw, log=log, defer_sync=True
                ):
                    written += 1
                else:
                    miss_cover = True
                    failed += 1
            else:
                skipped += 1

            if need_icon:
                if icon_raw and _apply_bytes_to_meta(
                    mount_path, meta, "icon", icon_raw, log=log, defer_sync=True
                ):
                    written += 1
                else:
                    miss_icon = True
                    failed += 1
            else:
                skipped += 1

            if miss_cover or miss_icon:
                missing.append(
                    {
                        "rel_path": rel,
                        "display_name": meta.get("basename") or os.path.basename(rel),
                        "game_code": meta.get("game_code"),
                        "missing_cover": miss_cover,
                        "missing_icon": miss_icon,
                    }
                )
            tracker.written = written
            tracker.skipped = skipped
            tracker.failed = failed
            tracker.current = idx
            tracker.tick(force=True)
    except OperationCancelled as e:
        msg = str(e) or "Operação cancelada pelo utilizador."
        log(f"⚠️ {msg} ({written} gravada(s) antes).")
        tracker.written = written
        tracker.skipped = skipped
        tracker.failed = failed
        tracker.finish(msg)
        try:
            sync_volume(mount_path)
        except Exception:
            pass
        return {
            "success": False,
            "error": msg,
            "message": msg,
            "written": written,
            "skipped": skipped,
            "failed": failed,
            "scanned": scanned,
            "missing": missing,
            "cancelled": True,
        }

    msg = (
        f"{written} arte(s) gravada(s); {skipped} já existiam; "
        f"{len(missing)} jogo(s) com falhas."
    )
    return _finish_ok(msg)


def generate_dspico_covers_batch(
    mount_path: str, log_callback=None, *, max_games: int = 200
) -> dict[str, Any]:
    """Alias compatível — delega para generate_dspico_artwork_batch."""
    return generate_dspico_artwork_batch(
        mount_path, log_callback=log_callback, max_games=max_games
    )
