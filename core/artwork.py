"""Capas e ícones multi-consola para TWiLight Menu++.

Ordem: SteamGridDB (principal) → GameTDB (NDS) → Libretro → jsDelivr.
"""

from __future__ import annotations

import os
import re
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Optional

from core.cache import USER_AGENT
from core.disks import is_safe_mount_path
from core.logging_util import emit_log
from core.privacy import redact_path
from core.rom_cleaner import (
    PLATFORM_BY_EXT,
    detect_platform,
    get_nds_header_info,
)
from core.sdio import sync_volume

# GameTDB S Covers — região pela 4.ª letra do TID (padrão TwilightBoxart / wiki).
_TID_REGION = {
    "E": "US",
    "P": "EN",
    "J": "JA",
    "K": "KO",
    "C": "ZH",
    "V": "EU",
    "U": "AU",
    "D": "DE",
    "F": "FR",
    "I": "IT",
    "S": "ES",
    "H": "NL",
    "X": "EU",
    "Y": "EU",
    "Z": "EU",
    "W": "ZH",
}

# Pasta TWiLight / chave canónica → nome do sistema no CDN Libretro Thumbnails.
LIBRETRO_SYSTEMS: dict[str, str] = {
    "nds": "Nintendo - Nintendo DS",
    "dsi": "Nintendo - Nintendo DS",
    "gba": "Nintendo - Game Boy Advance",
    "gb": "Nintendo - Game Boy",
    "gbc": "Nintendo - Game Boy Color",
    "nes": "Nintendo - Nintendo Entertainment System",
    "fds": "Nintendo - Family Computer Disk System",
    "snes": "Nintendo - Super Nintendo Entertainment System",
    "gen": "Sega - Mega Drive - Genesis",
    "sms": "Sega - Master System - Mark III",
    "gg": "Sega - Game Gear",
    "sg": "Sega - SG-1000",
    "tg16": "NEC - PC Engine - TurboGrafx 16",
    "pce": "NEC - PC Engine - TurboGrafx 16",
    "a26": "Atari - 2600",
    "a52": "Atari - 5200",
    "a78": "Atari - 7800",
    "col": "Coleco - ColecoVision",
    "cpc": "Amstrad - CPC",
    "msx": "Microsoft - MSX",
    "ngp": "SNK - Neo Geo Pocket",
    "ws": "Bandai - WonderSwan",
    "int": "Mattel - Intellivision",
    "min": "Nintendo - Pokemon Mini",
    "m5": "Sord - M5",
    "xex": "Atari - 8-bit",
}

# Chaves de pasta DSPico (_RETRO_PLATFORM) → chave canónica LIBRETRO_SYSTEMS.
# Sem entrada: plataforma sem CDN Libretro conhecido (não cair para NDS).
PLATFORM_LIBRETRO_ALIAS: dict[str, str] = {
    "genesis": "gen",
    "2600": "a26",
    "5200": "a52",
    "7800": "a78",
    "coleco": "col",
    "800": "xex",
}


def libretro_platform_key(platform: Optional[str]) -> Optional[str]:
    """Normaliza plataforma DSPico/TWiLight para chave em LIBRETRO_SYSTEMS.

    Devolve None se não houver sistema Libretro conhecido — o caller não deve
    forçar "nds" para ROMs retro desconhecidas.
    """
    raw = (platform or "").strip().lower()
    if not raw:
        return None
    key = PLATFORM_LIBRETRO_ALIAS.get(raw, raw)
    if key in LIBRETRO_SYSTEMS:
        return key
    return None


def is_nds_family_platform(platform: Optional[str]) -> bool:
    """True para NDS/DSi (GameTDB DS aplicável)."""
    key = libretro_platform_key(platform) or (platform or "").strip().lower()
    return key in ("nds", "dsi")

_LIBRETRO_BASE = "https://thumbnails.libretro.com"
_JSDELIVR_LIBRETRO_BASE = (
    "https://cdn.jsdelivr.net/gh/libretro-thumbnails"
)
_PNG_MIN = 64
_DOWNLOAD_TIMEOUT = 30
_BATCH_DOWNLOAD_TIMEOUT = 8
_INTER_REQUEST_DELAY = 0.15
_BATCH_MISS_DELAY = 0.05
_BATCH_MAX_URLS = 6
_BATCH_HTTP_WORKERS = 3
_MAX_DOWNLOAD_BYTES = 2 * 1024 * 1024
_ART_HOSTS = frozenset(
    {
        "art.gametdb.com",
        "thumbnails.libretro.com",
        "cdn.jsdelivr.net",
    }
)
_PNG_SIG = b"\x89PNG\r\n\x1a\n"

# Caracteres proibidos nos nomes Libretro → underscore.
_LIBRETRO_BAD = re.compile(r"[&\*/:`\\|]")
# Tags finais (região / dump) para gerar candidatos alternativos.
_TRAILING_TAG = re.compile(
    r"\s*[\(\[][^\)\]]+[\)\]]\s*$",
)

LogFn = Callable[[str], None]


def tid_region(game_code: str) -> str:
    code = (game_code or "").strip().upper()
    if len(code) < 4:
        return "US"
    return _TID_REGION.get(code[3], "US")


def boxart_urls_for_tid(game_code: str) -> list[str]:
    """URLs candidatas GameTDB coverS para um TID NDS."""
    code = (game_code or "").strip().upper()
    if len(code) != 4 or not code.isalnum():
        return []
    region = tid_region(code)
    regions = [region]
    for extra in ("US", "EN", "JA"):
        if extra not in regions:
            regions.append(extra)
    return [f"https://art.gametdb.com/ds/coverS/{reg}/{code}.png" for reg in regions]


def libretro_sanitize_name(name: str) -> str:
    """Aplica a regra de naming dos thumbnails Libretro."""
    return _LIBRETRO_BAD.sub("_", (name or "").strip())


def libretro_name_candidates(filename: str) -> list[str]:
    """
    Candidatos de nome a partir do ficheiro ROM (sem extensão).
    Mantém tags No-Intro; depois remove tags finais progressivamente.
    """
    stem = os.path.splitext(os.path.basename(filename or ""))[0].strip()
    if not stem:
        return []
    out: list[str] = []
    seen: set[str] = set()

    def _add(raw: str) -> None:
        s = libretro_sanitize_name(raw)
        if s and s not in seen:
            seen.add(s)
            out.append(s)

    _add(stem)
    cur = stem
    for _ in range(6):
        nxt = _TRAILING_TAG.sub("", cur).strip()
        if not nxt or nxt == cur:
            break
        _add(nxt)
        cur = nxt
    return out


def libretro_urls(
    platform: str, game_name: str, kind: str = "boxart"
) -> list[str]:
    """
    URLs Libretro para capa (Named_Boxarts) ou ícone/título (Named_Titles).
    kind: 'boxart' | 'icon'
    Aceita chaves canónicas ou aliases DSPico (ex. genesis → gen).
    """
    key = libretro_platform_key(platform)
    system = LIBRETRO_SYSTEMS.get(key) if key else None
    if not system or not game_name:
        return []
    systems = [system] if isinstance(system, str) else list(system)
    folder = "Named_Boxarts" if kind == "boxart" else "Named_Titles"
    out: list[str] = []
    enc_name = urllib.parse.quote(f"{game_name}.png", safe="")
    for sys_name in systems:
        enc_sys = urllib.parse.quote(sys_name, safe="")
        out.append(f"{_LIBRETRO_BASE}/{enc_sys}/{folder}/{enc_name}")
    return out


def jsdelivr_libretro_urls(
    platform: str, game_name: str, kind: str = "boxart"
) -> list[str]:
    """
    Espelho público jsDelivr dos libretro-thumbnails (3.ª fonte, sem API key).
    kind: 'boxart' | 'icon'
    """
    key = libretro_platform_key(platform)
    system = LIBRETRO_SYSTEMS.get(key) if key else None
    if not system or not game_name:
        return []
    systems = [system] if isinstance(system, str) else list(system)
    folder = "Named_Boxarts" if kind == "boxart" else "Named_Titles"
    out: list[str] = []
    # jsDelivr: path segments encoded; @master pin do branch.
    enc_name = urllib.parse.quote(f"{game_name}.png", safe="")
    for sys_name in systems:
        # Espaços e hífens no nome do repo (ex. Nintendo - Nintendo DS)
        enc_sys = urllib.parse.quote(sys_name, safe="")
        out.append(
            f"{_JSDELIVR_LIBRETRO_BASE}/{enc_sys}@master/{folder}/{enc_name}"
        )
    return out


def _looks_like_png(path: str) -> bool:
    try:
        if os.path.getsize(path) < _PNG_MIN:
            return False
        with open(path, "rb") as f:
            return f.read(8) == _PNG_SIG
    except OSError:
        return False


def _png_bytes_ok(data: Optional[bytes]) -> bool:
    return bool(
        data
        and len(data) >= _PNG_MIN
        and len(data) <= _MAX_DOWNLOAD_BYTES
        and data[:8] == _PNG_SIG
    )


def _emit_batch_progress(payload: dict[str, Any]) -> None:
    """Push best-effort para a UI (não bloqueia o lote)."""
    from core.progress import emit_progress

    emit_progress(payload)


def _url_host_allowed(url: str) -> bool:
    if not url.startswith("https://"):
        return False
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    if host in _ART_HOSTS:
        return True
    from core.steamgriddb import is_asset_url

    return is_asset_url(url)


def _download_png_bytes(
    url: str, *, timeout: Optional[float] = None
) -> Optional[bytes]:
    """GET HTTPS allowlisted → bytes PNG válidos, ou None."""
    if not _url_host_allowed(url):
        return None
    to = _DOWNLOAD_TIMEOUT if timeout is None else float(timeout)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=to) as resp:  # nosec B310
            chunks: list[bytes] = []
            written = 0
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                written += len(chunk)
                if written > _MAX_DOWNLOAD_BYTES:
                    return None
                chunks.append(chunk)
        data = b"".join(chunks)
        return data if _png_bytes_ok(data) else None
    except (OSError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return None


def _normalize_twilight_png(data: bytes, kind: str) -> Optional[bytes]:
    """Redimensiona/ajusta PNG|BMP → PNG no formato TWiLight (capa ou ícone)."""
    kind_n = (kind or "").strip().lower()
    if kind_n not in ("boxart", "icon"):
        return None
    try:
        from core.pico_bmp import image_bytes_to_twilight_png

        out = image_bytes_to_twilight_png(data, kind_n)
    except ValueError:
        return None
    return out if _png_bytes_ok(out) else None


def _write_png_bytes(
    data: bytes, dest: str, *, kind: Optional[str] = None
) -> bool:
    """Grava PNG validado via .partial + os.replace.

    Se ``kind`` for boxart|icon, redimensiona e ajusta (paleta/tamanho)
    antes de gravar — aplica-se a downloads e ficheiros locais.
    """
    payload = data
    if kind in ("boxart", "icon"):
        normalized = _normalize_twilight_png(data, kind)
        if not normalized:
            return False
        payload = normalized
    elif not _png_bytes_ok(payload):
        return False
    partial = f"{dest}.partial"
    try:
        with open(partial, "wb") as out:
            out.write(payload)
            out.flush()
            os.fsync(out.fileno())
        os.replace(partial, dest)
        return True
    except OSError:
        if os.path.exists(partial):
            try:
                os.remove(partial)
            except OSError:
                pass
        return False


def _fetch_first_ok(
    urls: list[str],
    *,
    max_urls: Optional[int] = None,
    timeout: Optional[float] = None,
    workers: int = _BATCH_HTTP_WORKERS,
) -> Optional[bytes]:
    """
    Descarrega candidatas em paralelo; devolve o 1.º PNG válido.
    Sem sleep entre misses — o pool substitui o pacing sequencial.
    """
    if not urls:
        return None
    try:
        cap = len(urls) if max_urls is None else max(0, int(max_urls))
    except (TypeError, ValueError):
        cap = len(urls)
    seq = [u for u in urls[:cap] if _url_host_allowed(u)]
    if not seq:
        return None
    to = _BATCH_DOWNLOAD_TIMEOUT if timeout is None else float(timeout)
    try:
        n_workers = max(1, min(int(workers), len(seq)))
    except (TypeError, ValueError):
        n_workers = min(_BATCH_HTTP_WORKERS, len(seq))

    if n_workers == 1 or len(seq) == 1:
        for url in seq:
            data = _download_png_bytes(url, timeout=to)
            if data:
                return data
        return None

    # first-hit: ao 1.º sucesso, deixa de esperar pelos outros
    # (shutdown wait=False — urlopen em curso pode ainda terminar em background).
    pool = ThreadPoolExecutor(max_workers=n_workers)
    try:
        futures = {
            pool.submit(_download_png_bytes, url, timeout=to): url for url in seq
        }
        for fut in as_completed(futures):
            try:
                data = fut.result()
            except Exception:
                data = None
            if data:
                for other in futures:
                    if other is not fut:
                        other.cancel()
                return data
    finally:
        try:
            pool.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            # Python sem cancel_futures (não esperado em 3.10+)
            pool.shutdown(wait=False)
    return None


def _download_png(
    url: str,
    dest: str,
    *,
    timeout: Optional[float] = None,
    kind: Optional[str] = None,
) -> bool:
    data = _download_png_bytes(url, timeout=timeout)
    if not data:
        return False
    return _write_png_bytes(data, dest, kind=kind)


def _twilight_dir(mount_path: str, kind: str) -> str:
    name = "boxart" if kind == "boxart" else "icons"
    return os.path.join(mount_path, "_nds", "TWiLightMenu", name)


def _valid_nds_tid(game_code: Optional[str]) -> Optional[str]:
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


def _scan_rom_tids(mount_path: str) -> list[tuple[str, str]]:
    """Lista (tid, rom_path) sob /roms/nds/ e /roms/dsi/."""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for sub in ("nds", "dsi"):
        nds_dir = os.path.join(mount_path, "roms", sub)
        if not os.path.isdir(nds_dir):
            continue
        try:
            names = os.listdir(nds_dir)
        except OSError:
            continue
        for name in names:
            low = name.lower()
            if not low.endswith((".nds", ".dsi", ".ids")):
                continue
            path = os.path.join(nds_dir, name)
            if not os.path.isfile(path):
                continue
            _title, code, _unit, _maker = get_nds_header_info(path)
            tid = _valid_nds_tid(code)
            if not tid or tid in seen:
                continue
            seen.add(tid)
            out.append((tid, path))
    return out


def _rom_ext_ok(name: str) -> bool:
    ext = os.path.splitext(name)[1].lower()
    if ext in PLATFORM_BY_EXT:
        return PLATFORM_BY_EXT.get(ext) is not None or ext in (".bin", ".rom")
    return ext in (".ids", ".app", ".srl")


def _scan_roms_for_artwork(mount_path: str) -> list[dict[str, Any]]:
    """
    Lista ROMs sob /roms/ com metadados para download de arte.
    Cada item: platform, basename, path, game_code (NDS).
    """
    roms_root = os.path.join(mount_path, "roms")
    if not os.path.isdir(roms_root):
        return []
    items: list[dict[str, Any]] = []
    try:
        for dirpath, dirnames, filenames in os.walk(roms_root):
            dirnames[:] = [
                d
                for d in dirnames
                if not d.startswith(".") and d != "__MACOSX"
            ]
            for name in filenames:
                if name.startswith("._") or name.endswith(".partial"):
                    continue
                if not _rom_ext_ok(name):
                    continue
                full = os.path.join(dirpath, name)
                if not os.path.isfile(full):
                    continue
                ext = os.path.splitext(name)[1].lower()
                header = None
                game_code = None
                kind = None
                if ext in (".nds", ".dsi", ".ids", ".app"):
                    header = get_nds_header_info(full)
                    _t, game_code, _u, _m = header
                platform = detect_platform(
                    full, name, ext, header_info=header, kind=kind
                )
                if not platform or platform in ("apps", "bios", "saves"):
                    continue
                items.append(
                    {
                        "platform": platform,
                        "basename": name,
                        "path": full,
                        "game_code": _valid_nds_tid(game_code),
                    }
                )
    except OSError:
        return items
    return items


def _import_local_pack(boxart_dir: str, log: LogFn) -> int:
    """Importa PNGs / zip de capas de Downloads/Desktop."""
    home = os.path.expanduser("~")
    roots = [
        os.path.join(home, "Downloads"),
        os.path.join(home, "Desktop"),
        os.path.join(home, "Transferências"),
        os.path.join(home, "Ambiente de Trabalho"),
    ]
    imported = 0
    for root in roots:
        if not os.path.isdir(root):
            continue
        try:
            names = os.listdir(root)
        except OSError:
            continue
        for name in names:
            path = os.path.join(root, name)
            if not _safe_under(root, path) or not os.path.isfile(path):
                continue
            low = name.lower()
            if low.endswith(".png") and (
                len(os.path.splitext(name)[0]) == 4
                or ".nds.png" in low
                or ".dsi.png" in low
            ):
                if not _looks_like_png(path):
                    continue
                dest_name = name
                stem = os.path.splitext(name)[0]
                if len(stem) == 4 and stem.isalnum():
                    dest_name = f"{stem.upper()}.png"
                dest = os.path.join(boxart_dir, dest_name)
                if os.path.exists(dest):
                    continue
                try:
                    with open(path, "rb") as srcf:
                        raw = srcf.read()
                    if _write_png_bytes(raw, dest, kind="boxart"):
                        imported += 1
                except OSError:
                    continue
            elif low.endswith(".zip") and (
                "boxart" in low or "cover" in low or "gametdb" in low
            ):
                try:
                    with zipfile.ZipFile(path, "r") as zf:
                        for info in zf.infolist():
                            if info.is_dir():
                                continue
                            base = os.path.basename(info.filename)
                            if not base.lower().endswith(".png"):
                                continue
                            if ".." in info.filename.replace("\\", "/"):
                                continue
                            dest = os.path.join(boxart_dir, base)
                            if os.path.exists(dest):
                                continue
                            try:
                                with zf.open(info) as src:
                                    raw = src.read(_MAX_DOWNLOAD_BYTES + 1)
                            except (OSError, RuntimeError):
                                continue
                            if len(raw) > _MAX_DOWNLOAD_BYTES:
                                continue
                            if _write_png_bytes(raw, dest, kind="boxart"):
                                imported += 1
                except (OSError, zipfile.BadZipFile):
                    log(f"⚠️ Zip de capas inválido: {redact_path(path)}")
    return imported


def _try_download_urls(
    urls: list[str],
    dest: str,
    *,
    max_urls: Optional[int] = None,
    timeout: Optional[float] = None,
    miss_delay: Optional[float] = None,
    parallel: bool = False,
    kind: Optional[str] = None,
) -> bool:
    """Tenta URLs em ordem (ou first-hit paralelo). Delay só entre misses sequenciais."""
    if parallel:
        data = _fetch_first_ok(urls, max_urls=max_urls, timeout=timeout)
        return bool(data and _write_png_bytes(data, dest, kind=kind))
    delay = _INTER_REQUEST_DELAY if miss_delay is None else float(miss_delay)
    seq = urls if max_urls is None else urls[: max(0, int(max_urls))]
    for i, url in enumerate(seq):
        if _download_png(url, dest, timeout=timeout, kind=kind):
            return True
        if i + 1 < len(seq) and delay > 0:
            time.sleep(delay)
    return False


def _fetch_libretro_asset(
    platform: str, basename: str, dest: str, kind: str
) -> bool:
    for candidate in libretro_name_candidates(basename):
        urls = libretro_urls(platform, candidate, kind=kind)
        if _try_download_urls(urls, dest, kind=kind):
            return True
        # 3.ª fonte: espelho jsDelivr (mesmo naming Libretro).
        urls_jd = jsdelivr_libretro_urls(platform, candidate, kind=kind)
        if _try_download_urls(urls_jd, dest, kind=kind):
            return True
    return False


def _nds_family(platform: str) -> bool:
    return is_nds_family_platform(platform)


def fetch_rom_artwork(
    mount_path: str,
    rel_path: str,
    log_callback=None,
    *,
    force: bool = False,
) -> tuple[bool, str, dict[str, Any]]:
    """
    Descarrega capa (+ ícone) para um ROM sob /roms/<rel_path>.
    Ordem: SteamGridDB → GameTDB (NDS) → Libretro / jsDelivr.
    """
    from core.steamgriddb import (
        fetch_asset_png_bytes,
        has_api_key,
        search_term_from_rom,
    )

    log = lambda msg: emit_log(log_callback, msg)
    stats: dict[str, Any] = {
        "boxart": False,
        "icon": False,
        "skipped_boxart": False,
        "skipped_icon": False,
        "source_boxart": None,
        "source_icon": None,
    }
    if not is_safe_mount_path(mount_path):
        return False, "Unidade não reconhecida como volume removível/USB/SD.", stats

    rel = (rel_path or "").replace("\\", "/").lstrip("/")
    if not rel or ".." in rel.split("/"):
        return False, "Caminho de ROM inválido.", stats

    roms_root = os.path.join(mount_path, "roms")
    full = os.path.realpath(os.path.join(roms_root, rel))
    if not _safe_under(roms_root, full) or not os.path.isfile(full):
        return False, "ROM inexistente sob /roms/.", stats

    basename = os.path.basename(full)
    ext = os.path.splitext(basename)[1].lower()
    header = None
    game_code = None
    if ext in (".nds", ".dsi", ".ids", ".app"):
        header = get_nds_header_info(full)
        _t, game_code, _u, _m = header
    platform = detect_platform(full, basename, ext, header_info=header)
    if not platform:
        return False, "Plataforma da ROM não reconhecida.", stats

    tid = _valid_nds_tid(game_code)
    box_dir = _twilight_dir(mount_path, "boxart")
    icon_dir = _twilight_dir(mount_path, "icons")
    os.makedirs(box_dir, exist_ok=True)
    os.makedirs(icon_dir, exist_ok=True)

    if _nds_family(platform) and tid:
        box_dest = os.path.join(box_dir, f"{tid}.png")
    else:
        box_dest = os.path.join(box_dir, f"{basename}.png")
    icon_dest = os.path.join(icon_dir, f"{basename}.png")
    sgdb_term = search_term_from_rom(basename)

    # --- Capa ---
    if not force and os.path.isfile(box_dest) and _looks_like_png(box_dest):
        stats["skipped_boxart"] = True
        stats["boxart"] = True
    else:
        got = False
        if has_api_key() and sgdb_term:
            png = fetch_asset_png_bytes(sgdb_term, "boxart")
            if png and _write_png_bytes(png, box_dest, kind="boxart"):
                got = True
                stats["source_boxart"] = "steamgriddb"
        if not got and _nds_family(platform) and tid:
            if _try_download_urls(
                boxart_urls_for_tid(tid), box_dest, kind="boxart"
            ):
                got = True
                stats["source_boxart"] = "gametdb"
        lr_plat = libretro_platform_key(platform)
        if not got and lr_plat:
            # NDS sem TID (ou fallback): Libretro por nome
            lr_dest = box_dest
            if _nds_family(platform) and tid:
                # Preferir TID.png se GameTDB falhou; também tentar por nome
                lr_dest = os.path.join(box_dir, f"{basename}.png")
            if _fetch_libretro_asset(lr_plat, basename, lr_dest, "boxart"):
                got = True
                stats["source_boxart"] = "libretro"
                if lr_dest != box_dest and not (
                    os.path.isfile(box_dest) and _looks_like_png(box_dest)
                ):
                    try:
                        shutil.copy2(lr_dest, box_dest)
                    except OSError:
                        pass
        if got:
            stats["boxart"] = True
            log(f"✅ Capa: {basename}")
        else:
            log(f"⚠️ Sem capa para {basename}")

    # --- Ícone: SteamGridDB (todas as plataformas) → Libretro Named_Titles ---
    lr_plat = libretro_platform_key(platform)
    want_icon = bool(lr_plat) or has_api_key()
    if want_icon:
        if not force and os.path.isfile(icon_dest) and _looks_like_png(icon_dest):
            stats["skipped_icon"] = True
            stats["icon"] = True
        else:
            got_icon = False
            if has_api_key() and sgdb_term:
                png = fetch_asset_png_bytes(sgdb_term, "icon")
                if png and _write_png_bytes(png, icon_dest, kind="icon"):
                    got_icon = True
                    stats["source_icon"] = "steamgriddb"
            if not got_icon and lr_plat and _fetch_libretro_asset(
                lr_plat, basename, icon_dest, "icon"
            ):
                got_icon = True
                stats["source_icon"] = "libretro"
            if got_icon:
                stats["icon"] = True
                log(f"✅ Ícone: {basename}")
            else:
                log(f"⚠️ Sem ícone para {basename}")

    try:
        sync_volume(mount_path)
    except Exception:
        pass

    if stats["boxart"] or stats["icon"]:
        parts = []
        if stats["boxart"]:
            parts.append("capa" + (" (já existia)" if stats["skipped_boxart"] else ""))
        if stats["icon"]:
            parts.append("ícone" + (" (já existia)" if stats["skipped_icon"] else ""))
        return True, "Arte: " + ", ".join(parts) + ".", stats
    return False, "Nenhuma arte encontrada para este jogo (rede ou nome).", stats


def install_artwork(mount_path: str, log_callback=None) -> tuple[bool, str]:
    """
    Batch: SteamGridDB → GameTDB (NDS) → Libretro + packs locais.
    Delega o download em lote para generate_twilight_artwork_batch.
    """
    log = lambda msg: emit_log(log_callback, msg)
    if not is_safe_mount_path(mount_path):
        return False, "Unidade não reconhecida como volume removível/USB/SD."

    log("=== Instalar capas e ícones (multi-consola) ===")
    boxart_dir = _twilight_dir(mount_path, "boxart")
    icon_dir = _twilight_dir(mount_path, "icons")
    os.makedirs(boxart_dir, exist_ok=True)
    os.makedirs(icon_dir, exist_ok=True)

    imported = _import_local_pack(boxart_dir, log)
    if imported:
        log(f"Importadas {imported} capa(s) de Downloads/Desktop.")

    roms_root = os.path.join(mount_path, "roms")
    if not os.path.isdir(roms_root):
        if imported:
            try:
                sync_volume(mount_path)
            except Exception:
                pass
            msg = f"{imported} capa(s) importadas de Downloads/Desktop."
            log(f"✅ {msg}")
            return True, msg
        return (
            False,
            "Nenhum jogo em /roms/ nem pack de capas em Downloads/Desktop. "
            "Organize os jogos primeiro.",
        )

    res = generate_twilight_artwork_batch(mount_path, log_callback=log_callback)
    if not isinstance(res, dict):
        return False, "Falha ao instalar capas."
    if not res.get("success"):
        err = res.get("error") or res.get("message") or "Falha ao instalar capas."
        return False, str(err)

    log(
        "No TWiLight Menu++, ative capas/ícones personalizados nas definições "
        "se ainda não estiver ativo."
    )
    msg = str(res.get("message") or "Capas e ícones actualizados.")
    if imported:
        msg = f"{msg} ({imported} importada(s) localmente)."
    written = int(res.get("written") or 0)
    skipped = int(res.get("skipped") or 0)
    if written + skipped + imported == 0 and res.get("missing"):
        return False, msg + " Nenhuma arte disponível (rede ou bases de dados)."
    return True, msg


def _twilight_candidate_urls(
    platform: str,
    basename: str,
    tid: Optional[str],
    kind: str,
    *,
    query: str = "",
) -> list[str]:
    """Ordem CDN: GameTDB (capa NDS), Libretro, jsDelivr.

    SteamGridDB é resolvido via API (não entra nesta lista de URLs estáticas).
    """
    urls: list[str] = []
    seen: set[str] = set()

    def _add(seq: list[str]) -> None:
        for u in seq:
            if u and u not in seen:
                seen.add(u)
                urls.append(u)

    if kind == "boxart" and _nds_family(platform) and tid:
        _add(boxart_urls_for_tid(tid))
    q = (query or "").strip()
    if kind == "boxart" and _nds_family(platform) and q and len(q) == 4 and q.isalnum():
        _add(boxart_urls_for_tid(q.upper()))

    lr_plat = libretro_platform_key(platform)
    if lr_plat:
        name_sources = [basename]
        if q and not (len(q) == 4 and q.isalnum()):
            name_sources.insert(0, q if "." in q else f"{q}.rom")
        names: list[str] = []
        for src in name_sources:
            for n in libretro_name_candidates(src):
                if n not in names:
                    names.append(n)
        for name in names:
            _add(libretro_urls(lr_plat, name, kind=kind))
            _add(jsdelivr_libretro_urls(lr_plat, name, kind=kind))
    return urls


def generate_twilight_artwork_batch(
    mount_path: str, log_callback=None, *, max_games: int = 200
) -> dict[str, Any]:
    """
    Lote isolado TWiLight: 1.ª URL válida para boxart e ícone sob
    /_nds/TWiLightMenu/{boxart,icons}/. Não toca em pastas DSPico.
    Não sobrescreve arte existente. Retorna missing[] sob /roms/.
    HTTP em paralelo (first-hit); escritas no SD na thread da op.
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

    roms_root = os.path.join(mount_path, "roms")
    if not os.path.isdir(roms_root):
        return {
            "success": False,
            "error": "Pasta /roms/ inexistente.",
            "written": 0,
            "missing": [],
        }

    boxart_dir = _twilight_dir(mount_path, "boxart")
    icon_dir = _twilight_dir(mount_path, "icons")
    os.makedirs(boxart_dir, exist_ok=True)
    os.makedirs(icon_dir, exist_ok=True)

    all_roms = _scan_roms_for_artwork(mount_path)
    roms = all_roms[:max_n]
    written = 0
    skipped = 0
    failed = 0
    missing: list[dict[str, Any]] = []

    # Pré-filtro: jogos já completos não entram no loop de rede.
    work: list[dict[str, Any]] = []
    for item in roms:
        platform = item["platform"]
        basename = item["basename"]
        tid = item.get("game_code")
        full = item["path"]
        try:
            rel = os.path.relpath(full, roms_root).replace("\\", "/")
        except ValueError:
            continue
        if ".." in rel.split("/"):
            continue
        if _nds_family(platform) and tid:
            box_dest = os.path.join(boxart_dir, f"{tid}.png")
        else:
            box_dest = os.path.join(boxart_dir, f"{basename}.png")
        icon_dest = os.path.join(icon_dir, f"{basename}.png")
        has_box = os.path.isfile(box_dest) and _looks_like_png(box_dest)
        has_icon = os.path.isfile(icon_dest) and _looks_like_png(icon_dest)
        needs_icon = bool(libretro_platform_key(platform))
        if has_box and (has_icon or not needs_icon):
            skipped += 2  # capa + ícone (ou ícone N/A)
            continue
        work.append(
            {
                "item": item,
                "rel": rel,
                "box_dest": box_dest,
                "icon_dest": icon_dest,
                "has_box": has_box,
                "has_icon": has_icon,
                "needs_icon": needs_icon,
            }
        )

    total = len(work)
    scanned = len(roms)
    log(
        f"=== Capas e ícones TWiLight em lote: {scanned} jogo(s), "
        f"{total} por processar ==="
    )

    tracker = ProgressTracker(
        "twilight_artwork_batch",
        label="A iniciar…",
        total_items=total,
        emit_fn=_emit_batch_progress,
    )
    tracker.cancellable = True
    tracker.skipped = skipped

    def _fetch_kind(platform: str, basename: str, tid: Optional[str], kind: str):
        from core.steamgriddb import fetch_asset_png_bytes, has_api_key, search_term_from_rom

        if has_api_key():
            term = search_term_from_rom(basename)
            if term:
                png = fetch_asset_png_bytes(term, kind)
                if png:
                    return png
        urls = _twilight_candidate_urls(platform, basename, tid, kind)
        if not urls:
            return None
        return _fetch_first_ok(
            urls,
            max_urls=_BATCH_MAX_URLS,
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
        msg = (
            f"{written} arte(s) gravada(s); {skipped} já existiam; "
            f"0 jogo(s) com falhas."
        )
        return _finish_ok(msg)

    tracker.tick(force=True)
    try:
        for idx, job in enumerate(work, start=1):
            check_cancelled()
            item = job["item"]
            platform = item["platform"]
            basename = item["basename"]
            tid = item.get("game_code")
            rel = job["rel"]
            box_dest = job["box_dest"]
            icon_dest = job["icon_dest"]
            need_box = not job["has_box"]
            need_icon = bool(job["needs_icon"] and not job["has_icon"])

            miss_cover = False
            miss_icon = False
            tracker.set_label(basename)
            tracker.tick(force=True)

            box_bytes: Optional[bytes] = None
            icon_bytes: Optional[bytes] = None

            if need_box and need_icon:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    f_box = pool.submit(
                        _fetch_kind, platform, basename, tid, "boxart"
                    )
                    f_icon = pool.submit(
                        _fetch_kind, platform, basename, tid, "icon"
                    )
                    try:
                        box_bytes = f_box.result()
                    except Exception:
                        box_bytes = None
                    try:
                        icon_bytes = f_icon.result()
                    except Exception:
                        icon_bytes = None
            elif need_box:
                box_bytes = _fetch_kind(platform, basename, tid, "boxart")
            elif need_icon:
                icon_bytes = _fetch_kind(platform, basename, tid, "icon")

            if need_box:
                if box_bytes and _write_png_bytes(
                    box_bytes, box_dest, kind="boxart"
                ):
                    written += 1
                    log(f"✅ Capa TWiLight {basename}")
                else:
                    miss_cover = True
                    failed += 1
            else:
                skipped += 1

            if need_icon:
                if icon_bytes and _write_png_bytes(
                    icon_bytes, icon_dest, kind="icon"
                ):
                    written += 1
                    log(f"✅ Ícone TWiLight {basename}")
                else:
                    miss_icon = True
                    failed += 1
            else:
                # Já existia, ou plataforma sem ícone Libretro.
                skipped += 1

            if miss_cover or miss_icon:
                missing.append(
                    {
                        "rel_path": rel,
                        "display_name": basename,
                        "game_code": tid,
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


def install_boxarts(mount_path: str, log_callback=None) -> tuple[bool, str]:
    """Alias compatível com a API antiga."""
    return install_artwork(mount_path, log_callback=log_callback)


_SEARCH_MAX_CANDIDATES = 24
_SEARCH_MAX_PROBES = 48
_SEARCH_PROBE_TIMEOUT = 12


def _http_url_exists(url: str) -> bool:
    """HEAD (ou GET Range) para filtrar candidatas mortas na pesquisa TWiLight."""
    if not isinstance(url, str) or not url.startswith("https://"):
        return False
    if not _url_host_allowed(url):
        return False
    try:
        req = urllib.request.Request(
            url, method="HEAD", headers={"User-Agent": USER_AGENT}
        )
        with urllib.request.urlopen(req, timeout=_SEARCH_PROBE_TIMEOUT) as resp:  # nosec B310
            code = getattr(resp, "status", None) or resp.getcode()
            return 200 <= int(code) < 300
    except (OSError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": USER_AGENT, "Range": "bytes=0-255"},
            )
            with urllib.request.urlopen(req, timeout=_SEARCH_PROBE_TIMEOUT) as resp:  # nosec B310
                code = getattr(resp, "status", None) or resp.getcode()
                if int(code) not in (200, 206):
                    return False
                resp.read(256)
                return True
        except (OSError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
            return False


def _resolve_twilight_rom(
    mount_path: str, rel_path: str
) -> tuple[Optional[str], Optional[dict[str, Any]]]:
    if not is_safe_mount_path(mount_path):
        return "Unidade não reconhecida como volume removível/USB/SD.", None
    rel = (rel_path or "").replace("\\", "/").lstrip("/")
    if not rel or ".." in rel.split("/"):
        return "Caminho de ROM inválido.", None
    roms_root = os.path.join(mount_path, "roms")
    full = os.path.realpath(os.path.join(roms_root, rel))
    try:
        root_r = os.path.realpath(roms_root)
        if os.path.commonpath([root_r, full]) != root_r or not os.path.isfile(full):
            return "ROM inexistente sob /roms/.", None
    except (ValueError, OSError):
        return "ROM inexistente sob /roms/.", None
    basename = os.path.basename(full)
    ext = os.path.splitext(basename)[1].lower()
    header = None
    game_code = None
    if ext in (".nds", ".dsi", ".ids", ".app", ".srl"):
        header = get_nds_header_info(full)
        _t, game_code, _u, _m = header
    platform = detect_platform(full, basename, ext, header_info=header)
    if not platform:
        return "Plataforma da ROM não reconhecida.", None
    tid = None
    if game_code:
        code = (game_code or "").replace("\x00", "").strip().upper()
        if len(code) == 4 and code.isalnum() and code not in ("####", "0000"):
            tid = code
    try:
        show_rel = os.path.relpath(full, roms_root).replace("\\", "/")
    except ValueError:
        show_rel = rel
    return None, {
        "full": full,
        "rel_path": show_rel,
        "basename": basename,
        "display_name": os.path.splitext(basename)[0],
        "game_code": tid,
        "platform": platform,
    }


def search_rom_artwork(
    mount_path: str,
    rel_path: str,
    kind: str = "boxart",
    query: str = "",
    log_callback=None,
) -> dict[str, Any]:
    """Lista candidatas online (URLs) para capa/ícone TWiLight — sem gravar."""
    log = lambda msg: emit_log(log_callback, msg)
    kind_n = (kind or "boxart").strip().lower()
    if kind_n not in ("boxart", "icon"):
        return {
            "success": False,
            "error": "Tipo inválido (boxart ou icon).",
            "candidates": [],
        }
    err, meta = _resolve_twilight_rom(mount_path, rel_path)
    if err or not meta:
        return {"success": False, "error": err or "ROM inválida.", "candidates": []}

    q = query if isinstance(query, str) else ""
    if "\x00" in q:
        return {"success": False, "error": "Pesquisa inválida.", "candidates": []}
    q = q.strip()[:120]

    from core.steamgriddb import candidate_assets, has_api_key, search_term_from_rom

    probes = _twilight_candidate_urls(
        meta["platform"],
        meta["basename"],
        meta["game_code"],
        kind_n,
        query=q,
    )
    log(
        f"A listar opções de {'capa' if kind_n == 'boxart' else 'ícone'} "
        f"TWiLight para {meta['display_name']}…"
    )

    # Preview actual no cartão
    box_dir = _twilight_dir(mount_path, "boxart")
    icon_dir = _twilight_dir(mount_path, "icons")
    current = None
    if kind_n == "boxart":
        if meta["game_code"]:
            cand = os.path.join(box_dir, f"{meta['game_code']}.png")
            if os.path.isfile(cand) and _looks_like_png(cand):
                current = cand
        if not current:
            cand = os.path.join(box_dir, f"{meta['basename']}.png")
            if os.path.isfile(cand) and _looks_like_png(cand):
                current = cand
    else:
        cand = os.path.join(icon_dir, f"{meta['basename']}.png")
        if os.path.isfile(cand) and _looks_like_png(cand):
            current = cand

    current_preview = None
    if current:
        try:
            with open(current, "rb") as f:
                data = f.read()
            if data.startswith(b"\x89PNG"):
                import base64

                current_preview = (
                    "data:image/png;base64,"
                    + base64.b64encode(data).decode("ascii")
                )
        except OSError:
            current_preview = None

    candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    # 1.ª fonte: SteamGridDB (URLs já validadas pela API — sem HEAD).
    sgdb_term = search_term_from_rom(
        meta["basename"], query=q
    ) or meta["display_name"]
    if has_api_key() and sgdb_term:
        for item in candidate_assets(
            sgdb_term, kind_n, game_name=meta["display_name"], limit=12
        ):
            url = item.get("url")
            if not isinstance(url, str) or url in seen_urls:
                continue
            seen_urls.add(url)
            candidates.append(
                {
                    "url": url,
                    "label": item.get("label") or f"SteamGridDB · {meta['display_name']}",
                    "source": "steamgriddb",
                    "preview": item.get("preview") or url,
                }
            )
            if len(candidates) >= _SEARCH_MAX_CANDIDATES:
                break

    probed = 0
    for url in probes:
        if len(candidates) >= _SEARCH_MAX_CANDIDATES:
            break
        if probed >= _SEARCH_MAX_PROBES:
            break
        probed += 1
        if url in seen_urls or not _http_url_exists(url):
            continue
        seen_urls.add(url)
        host = (urllib.parse.urlparse(url).hostname or "").lower()
        source = (
            "gametdb"
            if "gametdb" in host
            else ("jsdelivr" if "jsdelivr" in host else "libretro")
        )
        label = meta["display_name"]
        if source == "gametdb" and meta["game_code"]:
            label = f"GameTDB · {meta['game_code']}"
        candidates.append(
            {
                "url": url,
                "label": label,
                "source": source,
                "preview": url,
            }
        )

    if candidates:
        msg = f"{len(candidates)} opção(ões) — escolha uma para gravar no cartão."
    elif not libretro_platform_key(meta["platform"]) and not _nds_family(
        meta["platform"]
    ) and not has_api_key():
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
        "platform": meta["platform"],
        "query": q,
        "current": current_preview,
        "candidates": candidates,
        "hints": {
            "boxart": (
                "PNG 128×115 em /_nds/TWiLightMenu/boxart/ "
                "(redimensionado automaticamente). "
                "SteamGridDB, GameTDB (NDS) ou Libretro. Local: PNG ou BMP."
            ),
            "icon": (
                "PNG 32×32 (≤16 cores) em /_nds/TWiLightMenu/icons/ "
                "(ajustado automaticamente). "
                "SteamGridDB ou Libretro. Local: PNG ou BMP."
            ),
        },
    }


def apply_rom_artwork_url(
    mount_path: str,
    rel_path: str,
    kind: str,
    url: str,
    log_callback=None,
) -> tuple[bool, str, dict[str, Any]]:
    """Descarrega URL allowlisted e grava PNG TWiLight."""
    log = lambda msg: emit_log(log_callback, msg)
    stats: dict[str, Any] = {}
    kind_n = (kind or "boxart").strip().lower()
    if kind_n not in ("boxart", "icon"):
        return False, "Tipo inválido (boxart ou icon).", stats
    if not isinstance(url, str) or not url.startswith("https://"):
        return False, "URL de arte não permitida.", stats
    if not _url_host_allowed(url):
        return False, "URL de arte não permitida.", stats

    err, meta = _resolve_twilight_rom(mount_path, rel_path)
    if err or not meta:
        return False, err or "ROM inválida.", stats

    if kind_n == "boxart" and _nds_family(meta["platform"]) and meta["game_code"]:
        dest = os.path.join(
            _twilight_dir(mount_path, "boxart"), f"{meta['game_code']}.png"
        )
    elif kind_n == "boxart":
        dest = os.path.join(
            _twilight_dir(mount_path, "boxart"), f"{meta['basename']}.png"
        )
    else:
        dest = os.path.join(
            _twilight_dir(mount_path, "icons"), f"{meta['basename']}.png"
        )

    os.makedirs(os.path.dirname(dest), exist_ok=True)
    log("A descarregar e ajustar a imagem para o cartão…")
    if not _download_png(url, dest, kind=kind_n):
        return False, "Falha ao descarregar ou converter a imagem.", stats
    try:
        sync_volume(mount_path)
    except Exception:
        pass
    try:
        rel_dest = os.path.relpath(dest, mount_path).replace("\\", "/")
    except ValueError:
        rel_dest = os.path.basename(dest)
    label = "capa" if kind_n == "boxart" else "ícone"
    msg = f"{label.capitalize()} actualizada em /{rel_dest}."
    log(f"✅ {msg}")
    stats["path"] = rel_dest
    stats["kind"] = kind_n
    return True, msg, stats
