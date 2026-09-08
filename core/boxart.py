"""Download / importação de boxarts para TWiLight Menu++."""

from __future__ import annotations

import os
import shutil
import time
import urllib.error
import urllib.request
import zipfile

from core.cache import USER_AGENT
from core.disks import is_safe_mount_path
from core.logging_util import emit_log
from core.privacy import redact_path
from core.rom_cleaner import get_nds_header_info
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

_PNG_MIN = 64
_DOWNLOAD_TIMEOUT = 30
_INTER_REQUEST_DELAY = 0.15


def tid_region(game_code: str) -> str:
    code = (game_code or "").strip().upper()
    if len(code) < 4:
        return "US"
    return _TID_REGION.get(code[3], "US")


def boxart_urls_for_tid(game_code: str) -> list[str]:
    """URLs candidatas GameTDB coverS para um TID."""
    code = (game_code or "").strip().upper()
    if len(code) != 4 or not code.isalnum():
        return []
    region = tid_region(code)
    regions = [region]
    for extra in ("US", "EN", "JA"):
        if extra not in regions:
            regions.append(extra)
    return [f"https://art.gametdb.com/ds/coverS/{reg}/{code}.png" for reg in regions]


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
    partial = f"{dest}.partial"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=_DOWNLOAD_TIMEOUT) as resp, open(
            partial, "wb"
        ) as out:  # nosec B310
            shutil.copyfileobj(resp, out)
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


def _scan_rom_tids(mount_path: str) -> list[tuple[str, str]]:
    """Lista (tid, rom_path) sob /roms/nds/."""
    nds_dir = os.path.join(mount_path, "roms", "nds")
    if not os.path.isdir(nds_dir):
        return []
    out: list[tuple[str, str]] = []
    seen = set()
    try:
        for name in os.listdir(nds_dir):
            low = name.lower()
            if not low.endswith((".nds", ".dsi", ".ids")):
                continue
            path = os.path.join(nds_dir, name)
            if not os.path.isfile(path):
                continue
            _title, code, _unit, _maker = get_nds_header_info(path)
            if not code or len(code.strip()) != 4:
                continue
            tid = code.strip().upper()
            if not tid.isalnum() or tid in ("####", "0000"):
                continue
            if tid in seen:
                continue
            seen.add(tid)
            out.append((tid, path))
    except OSError:
        return out
    return out


def _safe_under(root: str, path: str) -> bool:
    try:
        root_r = os.path.realpath(root)
        path_r = os.path.realpath(path)
        return os.path.commonpath([root_r, path_r]) == root_r
    except (ValueError, OSError):
        return False


def _import_local_pack(boxart_dir: str, log) -> int:
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
                len(os.path.splitext(name)[0]) == 4 or ".nds.png" in low or ".dsi.png" in low
            ):
                if not _looks_like_png(path):
                    continue
                dest_name = name
                # TID.png preferido
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
            elif low.endswith(".zip") and ("boxart" in low or "cover" in low or "gametdb" in low):
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
                            with zf.open(info) as src, open(dest + ".partial", "wb") as out:
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


def install_boxarts(mount_path: str, log_callback=None) -> tuple[bool, str]:
    """
    Descarrega capas GameTDB para /_nds/TWiLightMenu/boxart/{TID}.png
    e/ou importa packs locais de Downloads/Desktop.
    """
    log = lambda msg: emit_log(log_callback, msg)
    if not is_safe_mount_path(mount_path):
        return False, "Unidade não reconhecida como volume removível/USB/SD."

    log("=== Instalar boxarts / capas ===")
    boxart_dir = os.path.join(mount_path, "_nds", "TWiLightMenu", "boxart")
    os.makedirs(boxart_dir, exist_ok=True)

    imported = _import_local_pack(boxart_dir, log)
    if imported:
        log(f"Importadas {imported} capa(s) de Downloads/Desktop.")

    roms = _scan_rom_tids(mount_path)
    if not roms and imported == 0:
        return (
            False,
            "Nenhum jogo em /roms/nds/ nem pack de capas em Downloads/Desktop. "
            "Organize os jogos primeiro.",
        )

    ok = skip = missing = errors = 0
    for tid, _rom in roms:
        dest = os.path.join(boxart_dir, f"{tid}.png")
        if os.path.isfile(dest) and _looks_like_png(dest):
            skip += 1
            continue
        urls = boxart_urls_for_tid(tid)
        got = False
        for url in urls:
            if _download_png(url, dest):
                got = True
                ok += 1
                log(f"✅ Capa {tid}")
                break
            time.sleep(_INTER_REQUEST_DELAY)
        if not got:
            missing += 1
            log(f"⚠️ Sem capa para {tid}")
        time.sleep(_INTER_REQUEST_DELAY)

    try:
        sync_volume(mount_path)
    except Exception:
        pass

    log(
        "Ative «mostrar capas» nas definições do TWiLight Menu++ no consola "
        "se ainda não estiver ativo."
    )
    msg = (
        f"Boxarts: {ok} novas, {skip} já existiam, {missing} em falta"
        + (f", {imported} importadas" if imported else "")
        + "."
    )
    log(f"✅ {msg}")
    # Sucesso se algo foi obtido ou já havia capas / import
    if ok + skip + imported == 0 and missing:
        return False, msg + " Nenhuma capa disponível (rede ou GameTDB)."
    return True, msg
