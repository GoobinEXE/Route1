"""Capas e ícones multi-consola para TWiLight Menu++ (GameTDB + Libretro)."""

from __future__ import annotations

import os
import re
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
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

# Pasta TWiLight → nome do sistema no CDN Libretro Thumbnails.
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

_LIBRETRO_BASE = "https://thumbnails.libretro.com"
_JSDELIVR_LIBRETRO_BASE = (
    "https://cdn.jsdelivr.net/gh/libretro-thumbnails"
)
_PNG_MIN = 64
_DOWNLOAD_TIMEOUT = 30
_INTER_REQUEST_DELAY = 0.15
_MAX_DOWNLOAD_BYTES = 2 * 1024 * 1024

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
    """
    system = LIBRETRO_SYSTEMS.get((platform or "").lower())
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
    system = LIBRETRO_SYSTEMS.get((platform or "").lower())
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
            return f.read(8) == b"\x89PNG\r\n\x1a\n"
    except OSError:
        return False


def _download_png(url: str, dest: str) -> bool:
    if not url.startswith("https://"):
        return False
    host = urllib.parse.urlparse(url).hostname or ""
    host = host.lower()
    if host not in {
        "art.gametdb.com",
        "thumbnails.libretro.com",
        "cdn.jsdelivr.net",
    }:
        return False
    partial = f"{dest}.partial"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=_DOWNLOAD_TIMEOUT) as resp, open(
            partial, "wb"
        ) as out:  # nosec B310
            written = 0
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                written += len(chunk)
                if written > _MAX_DOWNLOAD_BYTES:
                    raise OSError("download too large")
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
        if not _looks_like_png(partial):
            try:
                os.remove(partial)
            except OSError:
                pass
            return False
        os.replace(partial, dest)
        return True
    except (OSError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        if os.path.exists(partial):
            try:
                os.remove(partial)
            except OSError:
                pass
        return False


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
                    shutil.copy2(path, dest)
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
                            with zf.open(info) as src, open(
                                dest + ".partial", "wb"
                            ) as out:
                                shutil.copyfileobj(src, out)
                            if _looks_like_png(dest + ".partial"):
                                os.replace(dest + ".partial", dest)
                                imported += 1
                            else:
                                try:
                                    os.remove(dest + ".partial")
                                except OSError:
                                    pass
                except (OSError, zipfile.BadZipFile):
                    log(f"⚠️ Zip de capas inválido: {redact_path(path)}")
    return imported


def _try_download_urls(urls: list[str], dest: str) -> bool:
    for url in urls:
        if _download_png(url, dest):
            return True
        time.sleep(_INTER_REQUEST_DELAY)
    return False


def _fetch_libretro_asset(
    platform: str, basename: str, dest: str, kind: str
) -> bool:
    for candidate in libretro_name_candidates(basename):
        urls = libretro_urls(platform, candidate, kind=kind)
        if _try_download_urls(urls, dest):
            return True
        # 3.ª fonte: espelho jsDelivr (mesmo naming Libretro).
        urls_jd = jsdelivr_libretro_urls(platform, candidate, kind=kind)
        if _try_download_urls(urls_jd, dest):
            return True
    return False


def _nds_family(platform: str) -> bool:
    return (platform or "").lower() in ("nds", "dsi")


def fetch_rom_artwork(
    mount_path: str,
    rel_path: str,
    log_callback=None,
    *,
    force: bool = False,
) -> tuple[bool, str, dict[str, Any]]:
    """
    Descarrega capa (+ ícone Libretro) para um ROM sob /roms/<rel_path>.
    NDS: GameTDB por TID para capa; outras consolas: Libretro.
    """
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

    # --- Capa ---
    if not force and os.path.isfile(box_dest) and _looks_like_png(box_dest):
        stats["skipped_boxart"] = True
        stats["boxart"] = True
    else:
        got = False
        if _nds_family(platform) and tid:
            if _try_download_urls(boxart_urls_for_tid(tid), box_dest):
                got = True
                stats["source_boxart"] = "gametdb"
        if not got and platform in LIBRETRO_SYSTEMS:
            # NDS sem TID (ou fallback): Libretro por nome
            lr_dest = box_dest
            if _nds_family(platform) and tid:
                # Preferir TID.png se GameTDB falhou; também tentar por nome
                lr_dest = os.path.join(box_dir, f"{basename}.png")
            if _fetch_libretro_asset(platform, basename, lr_dest, "boxart"):
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

    # --- Ícone (Named_Titles) — skip NDS se já há banner custom / não forçar ---
    want_icon = platform in LIBRETRO_SYSTEMS and not _nds_family(platform)
    if want_icon:
        if not force and os.path.isfile(icon_dest) and _looks_like_png(icon_dest):
            stats["skipped_icon"] = True
            stats["icon"] = True
        elif _fetch_libretro_asset(platform, basename, icon_dest, "icon"):
            stats["icon"] = True
            stats["source_icon"] = "libretro"
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
    Batch: GameTDB (NDS) + Libretro (outras consolas) + packs locais.
    Grava em /_nds/TWiLightMenu/boxart/ e icons/.
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

    roms = _scan_roms_for_artwork(mount_path)
    # Também garantir TIDs NDS únicos via scan clássico (pastas planas)
    tid_map = {tid: path for tid, path in _scan_rom_tids(mount_path)}

    if not roms and not tid_map and imported == 0:
        return (
            False,
            "Nenhum jogo em /roms/ nem pack de capas em Downloads/Desktop. "
            "Organize os jogos primeiro.",
        )

    ok_box = skip_box = miss_box = 0
    ok_icon = skip_icon = miss_icon = 0
    seen_tid: set[str] = set()
    seen_files: set[str] = set()

    for item in roms:
        platform = item["platform"]
        basename = item["basename"]
        tid = item.get("game_code")
        key = os.path.realpath(item["path"])
        if key in seen_files:
            continue
        seen_files.add(key)

        # Capas NDS por TID
        if _nds_family(platform) and tid:
            if tid in seen_tid:
                pass
            else:
                seen_tid.add(tid)
                dest = os.path.join(boxart_dir, f"{tid}.png")
                if os.path.isfile(dest) and _looks_like_png(dest):
                    skip_box += 1
                elif _try_download_urls(boxart_urls_for_tid(tid), dest):
                    ok_box += 1
                    log(f"✅ Capa GameTDB {tid}")
                elif _fetch_libretro_asset(platform, basename, dest, "boxart"):
                    ok_box += 1
                    log(f"✅ Capa Libretro {basename}")
                else:
                    miss_box += 1
                    log(f"⚠️ Sem capa para {tid} / {basename}")
                time.sleep(_INTER_REQUEST_DELAY)
            continue

        # Outras consolas: Libretro boxart + title icon
        if platform not in LIBRETRO_SYSTEMS:
            continue
        box_dest = os.path.join(boxart_dir, f"{basename}.png")
        if os.path.isfile(box_dest) and _looks_like_png(box_dest):
            skip_box += 1
        elif _fetch_libretro_asset(platform, basename, box_dest, "boxart"):
            ok_box += 1
            log(f"✅ Capa {basename}")
        else:
            miss_box += 1
            log(f"⚠️ Sem capa para {basename}")
        time.sleep(_INTER_REQUEST_DELAY)

        icon_dest = os.path.join(icon_dir, f"{basename}.png")
        if os.path.isfile(icon_dest) and _looks_like_png(icon_dest):
            skip_icon += 1
        elif _fetch_libretro_asset(platform, basename, icon_dest, "icon"):
            ok_icon += 1
            log(f"✅ Ícone {basename}")
        else:
            miss_icon += 1
        time.sleep(_INTER_REQUEST_DELAY)

    # TIDs em pastas planas não apanhados pelo walk (já cobertos) — noop

    try:
        sync_volume(mount_path)
    except Exception:
        pass

    log(
        "No TWiLight Menu++, ative capas/ícones personalizados nas definições "
        "se ainda não estiver ativo."
    )
    msg = (
        f"Capas: {ok_box} novas, {skip_box} já existiam, {miss_box} em falta; "
        f"ícones: {ok_icon} novos, {skip_icon} já existiam, {miss_icon} em falta"
        + (f"; {imported} importadas" if imported else "")
        + "."
    )
    log(f"✅ {msg}")
    if ok_box + skip_box + ok_icon + skip_icon + imported == 0 and (
        miss_box or miss_icon
    ):
        return False, msg + " Nenhuma arte disponível (rede ou bases de dados)."
    return True, msg


def _twilight_candidate_urls(
    platform: str, basename: str, tid: Optional[str], kind: str
) -> list[str]:
    """Ordem: GameTDB (capa NDS), Libretro, jsDelivr."""
    urls: list[str] = []
    seen: set[str] = set()

    def _add(seq: list[str]) -> None:
        for u in seq:
            if u and u not in seen:
                seen.add(u)
                urls.append(u)

    if kind == "boxart" and _nds_family(platform) and tid:
        _add(boxart_urls_for_tid(tid))
    if platform in LIBRETRO_SYSTEMS:
        for name in libretro_name_candidates(basename):
            _add(libretro_urls(platform, name, kind=kind))
            _add(jsdelivr_libretro_urls(platform, name, kind=kind))
    return urls


def generate_twilight_artwork_batch(
    mount_path: str, log_callback=None, *, max_games: int = 200
) -> dict[str, Any]:
    """
    Lote isolado TWiLight: 1.ª URL válida para boxart e ícone sob
    /_nds/TWiLightMenu/{boxart,icons}/. Não toca em pastas DSPico.
    Não sobrescreve arte existente. Retorna missing[] sob /roms/.
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
    log(f"=== Capas e ícones TWiLight em lote: {len(roms)} jogo(s) ===")

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

        miss_cover = False
        miss_icon = False

        # --- Capa ---
        if os.path.isfile(box_dest) and _looks_like_png(box_dest):
            skipped += 1
        else:
            urls = _twilight_candidate_urls(platform, basename, tid, "boxart")
            if urls and _try_download_urls(urls, box_dest):
                written += 1
                log(f"✅ Capa TWiLight {basename}")
            else:
                miss_cover = True
                failed += 1
            time.sleep(_INTER_REQUEST_DELAY)

        # --- Ícone (Named_Titles); NDS também tenta Libretro/jsDelivr ---
        if os.path.isfile(icon_dest) and _looks_like_png(icon_dest):
            skipped += 1
        else:
            urls_i = _twilight_candidate_urls(platform, basename, tid, "icon")
            if urls_i and _try_download_urls(urls_i, icon_dest):
                written += 1
                log(f"✅ Ícone TWiLight {basename}")
            else:
                # NDS sem título Libretro é comum — só marcar se houver sistemas LR
                if platform in LIBRETRO_SYSTEMS:
                    miss_icon = True
                    failed += 1
                else:
                    skipped += 1
            time.sleep(_INTER_REQUEST_DELAY)

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

    try:
        sync_volume(mount_path)
    except Exception:
        pass

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


def install_boxarts(mount_path: str, log_callback=None) -> tuple[bool, str]:
    """Alias compatível com a API antiga."""
    return install_artwork(mount_path, log_callback=log_callback)
