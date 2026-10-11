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

from core.artwork import (
    LIBRETRO_SYSTEMS,
    boxart_urls_for_tid,
    jsdelivr_libretro_urls,
    libretro_name_candidates,
    libretro_sanitize_name,
    libretro_urls,
)
from core.cache import USER_AGENT
from core.disks import is_safe_mount_path
from core.dspico import GAME_EXTS, GAMES_DIRNAME, _resolve_under_games
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
_MAX_CANDIDATES = 16
_INTER_DELAY = 0.08
# Capas/ícones são imagens pequenas; sem teto um redirect/stream pode encher o disco.
_MAX_DOWNLOAD_BYTES = 2 * 1024 * 1024
_MAX_PROBE_BYTES = 256

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
    mount_path: str, basename: str, tid: Optional[str], kind: str
) -> list[str]:
    """Destinos preferidos: TID (nds/) depois user/ por nome."""
    out: list[str] = []
    if tid:
        out.append(os.path.join(_pico_asset_dir(mount_path, kind, "nds"), f"{tid}.bmp"))
    out.append(
        os.path.join(_pico_asset_dir(mount_path, kind, "user"), f"{basename}.bmp")
    )
    return out


def resolve_existing_art(
    mount_path: str, basename: str, tid: Optional[str], kind: str
) -> Optional[str]:
    """Prioridade Pico: user > nds (TID)."""
    user = os.path.join(_pico_asset_dir(mount_path, kind, "user"), f"{basename}.bmp")
    if os.path.isfile(user) and os.path.getsize(user) > 64:
        return user
    if tid:
        by_tid = os.path.join(_pico_asset_dir(mount_path, kind, "nds"), f"{tid}.bmp")
        if os.path.isfile(by_tid) and os.path.getsize(by_tid) > 64:
            return by_tid
    return None


def _png_data_url(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def _url_allowed(url: str) -> bool:
    try:
        parts = urllib.parse.urlparse(url)
    except ValueError:
        return False
    if parts.scheme != "https" or not parts.hostname:
        return False
    return parts.hostname.lower() in _ALLOWED_HOSTS


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


def _search_name_variants(query: str, basename: str = "") -> list[str]:
    """Candidatos de nome para Libretro a partir da query / ficheiro."""
    out: list[str] = []
    seen: set[str] = set()

    def _add(raw: str) -> None:
        s = libretro_sanitize_name((raw or "").strip())
        if s and s not in seen:
            seen.add(s)
            out.append(s)

    for base in (query, os.path.splitext(basename)[0]):
        if not base or not str(base).strip():
            continue
        for name in libretro_name_candidates(str(base) + ".nds"):
            _add(name)
        stem = libretro_sanitize_name(os.path.splitext(str(base))[0])
        if stem:
            for suf in _REGION_SUFFIXES:
                _add(stem + suf)
            # Truncar palavras (similares)
            words = stem.split()
            for n in range(len(words), 0, -1):
                _add(" ".join(words[:n]))
                if n <= 2:
                    break
    return out[:40]


def _resolve_game(
    mount_path: str, rel_path: str
) -> tuple[Optional[str], Optional[dict[str, Any]]]:
    """Devolve (erro, meta) para um jogo em Games/."""
    if not is_safe_mount_path(mount_path):
        return "Unidade não reconhecida como volume removível/USB/SD.", None
    rel = (rel_path or "").replace("\\", "/").lstrip("/")
    if not rel or ".." in rel.split("/"):
        return "Caminho de jogo inválido.", None
    full = _resolve_under_games(mount_path, rel)
    if not full or not os.path.isfile(full):
        return f"Jogo inexistente sob {GAMES_DIRNAME}/.", None
    basename = os.path.basename(full)
    ext = os.path.splitext(basename)[1].lower()
    if ext not in GAME_EXTS:
        return "Só jogos .nds / .dsi / .ids são suportados.", None
    title, code, _unit, _maker = get_nds_header_info(full)
    tid = _valid_tid(code)
    return None, {
        "full": full,
        "rel_path": rel,
        "basename": basename,
        "display_name": os.path.splitext(basename)[0],
        "title": (title or "").strip() or None,
        "game_code": tid,
        "platform": "nds",
    }


def enrich_dspico_game_entry(
    mount_path: str, entry: dict[str, Any], *, with_preview: bool = False
) -> dict[str, Any]:
    """Adiciona flags (e opcionalmente previews) de arte a um item de browse.

    Não exige is_safe_mount_path — o caller (browse) já opera sobre a montagem.
    """
    rel = (entry.get("rel_path") or "").replace("\\", "/").lstrip("/")
    entry["has_cover"] = False
    entry["has_icon"] = False
    if not rel or ".." in rel.split("/"):
        return entry
    full = _resolve_under_games(mount_path, rel)
    if not full or not os.path.isfile(full):
        return entry
    basename = os.path.basename(full)
    ext = os.path.splitext(basename)[1].lower()
    if ext not in GAME_EXTS:
        return entry
    _title, code, _unit, _maker = get_nds_header_info(full)
    tid = _valid_tid(code)
    cover = resolve_existing_art(mount_path, basename, tid, "cover")
    icon = resolve_existing_art(mount_path, basename, tid, "icon")
    entry["has_cover"] = bool(cover)
    entry["has_icon"] = bool(icon)
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

    def _push(url: str, label: str, source: str) -> None:
        if not url or url in seen or not _url_allowed(url):
            return
        seen.add(url)
        items.append({"url": url, "label": label, "source": source})

    lr_kind = "boxart" if kind == "cover" else "icon"

    if kind == "cover" and tid:
        for url in boxart_urls_for_tid(tid):
            _push(url, f"GameTDB · {tid}", "gametdb")

    # Query explícita (TID de 4 letras)
    q = (query or "").strip()
    if q and _TID_RE.match(q) and kind == "cover":
        for url in boxart_urls_for_tid(q.upper()):
            _push(url, f"GameTDB · {q.upper()}", "gametdb")

    names = _search_name_variants(q, basename)
    if title:
        for n in _search_name_variants(title, ""):
            if n not in names:
                names.append(n)

    if platform not in LIBRETRO_SYSTEMS:
        platform = "nds"

    for name in names:
        for url in libretro_urls(platform, name, kind=lr_kind):
            _push(url, name, "libretro")
        for url in jsdelivr_libretro_urls(platform, name, kind=lr_kind):
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
        f"para {meta['display_name']} (sem descarregar)…"
    )

    candidates: list[dict[str, Any]] = []
    for item in probes:
        if len(candidates) >= _MAX_CANDIDATES:
            break
        url = item.get("url")
        if not isinstance(url, str) or not _url_allowed(url):
            continue
        # preview = URL remota (a WebView carrega; o Python não grava no disco do PC)
        candidates.append(
            {
                "url": url,
                "label": item.get("label") or item.get("source") or "opção",
                "source": item.get("source") or "",
                "preview": url,
            }
        )

    msg = (
        f"{len(candidates)} opção(ões) — escolha uma para gravar no cartão."
        if candidates
        else "Nenhuma URL candidata — tente outro nome ou TID na pesquisa."
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
        "query": q,
        "current": current_preview,
        "candidates": candidates,
        "hints": {
            "cover": (
                "Pico Launcher: BMP 128×96 8-bit em /_pico/covers/nds/{TID}.bmp "
                "ou /_pico/covers/user/{ficheiro}.bmp."
            ),
            "icon": (
                "Pico Launcher: BMP 32×32 4-bit em /_pico/icons/nds/{TID}.bmp "
                "ou /_pico/icons/user/{ficheiro}.bmp (cor 0 = transparente)."
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

    log("A descarregar a capa escolhida directamente para o cartão…")
    raw = _http_get(url)
    if not raw:
        return False, "Falha ao descarregar a imagem.", stats
    try:
        bmp = image_bytes_to_pico_bmp(raw, kind_n)
    except ValueError as e:
        return False, f"Imagem inválida: {e}", stats
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
) -> tuple[bool, str, dict[str, Any]]:
    dests = _dest_paths(mount_path, meta["basename"], meta["game_code"], kind)
    if not dests:
        return False, "Sem destino de arte.", stats

    # Preferir TID quando existe; gravar só o primeiro destino canónico
    dest = dests[0]
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
    except OSError as e:
        try:
            if os.path.exists(partial):
                os.remove(partial)
        except OSError:
            pass
        return False, f"Falha ao gravar arte: {e}", stats

    try:
        sync_volume(mount_path)
    except Exception:
        pass

    label = "capa" if kind == "cover" else "ícone"
    rel_dest = os.path.relpath(dest, mount_path).replace("\\", "/")
    log(f"✅ {label.capitalize()} gravada: /{rel_dest} ({note})")
    stats["path"] = rel_dest
    stats["kind"] = kind
    return True, f"{label.capitalize()} actualizada em /{rel_dest}.", stats


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
        "hints": {
            "cover": (
                "Pesquisa GameTDB (por código) e Libretro Thumbnails (por nome). "
                "Pode pesquisar outro título ou escolher um PNG/BMP no PC."
            ),
            "icon": (
                "Pesquisa Libretro Named_Titles / escolha manual. "
                "No DS o ícone do banner é o padrão se não houver custom."
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
    """
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

    games_root = os.path.join(mount_path, "Games")
    if not os.path.isdir(games_root):
        return {
            "success": False,
            "error": "Pasta Games/ inexistente.",
            "written": 0,
            "missing": [],
        }

    roms: list[str] = []
    for root, _dirs, files in os.walk(games_root):
        for name in files:
            low = name.lower()
            if low.endswith((".nds", ".dsi", ".ids")):
                full = os.path.join(root, name)
                rel = os.path.relpath(full, games_root).replace("\\", "/")
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
    log(f"=== Capas e ícones DSPico em lote: {len(roms)} jogo(s) ===")

    def _try_kind(rel: str, meta: dict[str, Any], kind: str) -> str:
        """Retorna 'written' | 'skipped' | 'failed'."""
        nonlocal written, skipped
        existing = resolve_existing_art(
            mount_path, meta["basename"], meta.get("game_code"), kind
        )
        if existing:
            skipped += 1
            return "skipped"
        probes = _collect_candidate_urls(
            kind=kind,
            platform=meta.get("platform") or "nds",
            basename=meta["basename"],
            tid=meta.get("game_code"),
            title=meta.get("title"),
            query="",
        )
        for item in probes:
            url = item.get("url")
            if not isinstance(url, str) or not _url_allowed(url):
                continue
            if not _http_exists(url):
                time.sleep(_INTER_DELAY)
                continue
            ok, _msg, _st = apply_dspico_artwork_url(
                mount_path, rel, kind, url, log_callback=log_callback
            )
            time.sleep(_INTER_DELAY)
            if ok:
                written += 1
                return "written"
        return "failed"

    for rel in roms:
        err, meta = _resolve_game(mount_path, rel)
        if err or not meta:
            failed += 1
            missing.append(
                {
                    "rel_path": rel,
                    "display_name": os.path.basename(rel),
                    "game_code": None,
                    "missing_cover": True,
                    "missing_icon": True,
                }
            )
            continue
        cover_st = _try_kind(rel, meta, "cover")
        icon_st = _try_kind(rel, meta, "icon")
        miss_cover = cover_st == "failed"
        miss_icon = icon_st == "failed"
        if miss_cover or miss_icon:
            failed += int(miss_cover) + int(miss_icon)
            missing.append(
                {
                    "rel_path": rel,
                    "display_name": meta.get("basename") or os.path.basename(rel),
                    "game_code": meta.get("game_code"),
                    "missing_cover": miss_cover,
                    "missing_icon": miss_icon,
                }
            )

    msg = (
        f"{written} arte(s) gravada(s); {skipped} já existiam; "
        f"{len(missing)} jogo(s) com falhas."
    )
    log(f"✅ {msg}" if written else f"⚠️ {msg}")
    return {
        "success": True,
        "message": msg,
        "written": written,
        "skipped": skipped,
        "failed": failed,
        "scanned": len(roms),
        "missing": missing,
    }


def generate_dspico_covers_batch(
    mount_path: str, log_callback=None, *, max_games: int = 200
) -> dict[str, Any]:
    """Alias compatível — delega para generate_dspico_artwork_batch."""
    return generate_dspico_artwork_batch(
        mount_path, log_callback=log_callback, max_games=max_games
    )
