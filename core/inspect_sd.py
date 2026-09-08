"""Inspeção somente-leitura do cartão SD (assistente passo a passo)."""

from __future__ import annotations

import os
import re
from typing import Any, Optional

from core.disks import _normalize_mount, get_mounted_drives, is_safe_mount_path
from core.exploits import _twilight_present

# dumpTool grava pastas DT<hex>/nand.bin (~240 MiB). Aceitar nomes próximos.
_DT_DIR_RE = re.compile(r"^DT[0-9A-Fa-f]{4,}$")
_NAND_MIN_BYTES = 100 * 1024 * 1024  # 100 MiB — dump real ~240 MiB


def _find_drive(mount_path: str) -> Optional[dict]:
    target = _normalize_mount(mount_path)
    for d in get_mounted_drives():
        if _normalize_mount(d.get("mount_path", "")) == target:
            return d
    return None


def _is_fat32(fs_type: Optional[str]) -> bool:
    if not fs_type:
        return False
    fs = fs_type.lower().replace(" ", "").replace("-", "").replace("_", "")
    if "exfat" in fs:
        return False
    return "fat32" in fs or fs in ("msdos", "msdosfat32", "vfat", "fat")


def _find_nand_dumps(mount_path: str) -> list[dict[str, Any]]:
    """Procura DT*/nand.bin na raiz do cartão (padrão dumpTool)."""
    found: list[dict[str, Any]] = []
    try:
        entries = os.listdir(mount_path)
    except OSError:
        return found

    for name in entries:
        if not _DT_DIR_RE.match(name):
            continue
        folder = os.path.join(mount_path, name)
        if not os.path.isdir(folder):
            continue
        nand = os.path.join(folder, "nand.bin")
        if not os.path.isfile(nand):
            continue
        try:
            size = os.path.getsize(nand)
        except OSError:
            continue
        sha1 = os.path.join(folder, "nand.bin.sha1")
        found.append(
            {
                "folder": name,
                # Relativo à raiz do cartão — evita path absoluto na bridge JS.
                "rel_path": f"{name}/nand.bin",
                "size_bytes": size,
                "size_mb": round(size / (1024 * 1024), 1),
                "plausible": size >= _NAND_MIN_BYTES,
                "has_sha1": os.path.isfile(sha1),
            }
        )
    return found


def _count_roms(mount_path: str) -> int:
    roms_root = os.path.join(mount_path, "roms")
    if not os.path.isdir(roms_root):
        return 0
    count = 0
    try:
        for root, dirs, files in os.walk(roms_root):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in files:
                low = f.lower()
                if low.endswith((".nds", ".dsi", ".gba", ".ids")):
                    count += 1
    except OSError:
        return count
    return count


def _exists(mount_path: str, *parts: str) -> bool:
    return os.path.exists(os.path.join(mount_path, *parts))


def inspect_sd_card(mount_path: str) -> dict[str, Any]:
    """
    Lê o estado do cartão sem escrever (sem teste de escrita do preflight).
    """
    if not mount_path:
        return {"success": False, "error": "Caminho do cartão não especificado."}
    if not os.path.isdir(mount_path):
        return {"success": False, "error": "Caminho do cartão inexistente."}
    if not is_safe_mount_path(mount_path):
        return {
            "success": False,
            "error": (
                "Unidade não reconhecida como volume removível/USB/SD. "
                "Atualize a lista e selecione o cartão novamente."
            ),
        }

    drive = _find_drive(mount_path)
    fs_type = (drive or {}).get("fs_type") or "Desconhecido"
    total_gb = (drive or {}).get("total_size_gb")
    free_gb = (drive or {}).get("free_size_gb")
    name = (drive or {}).get("name") or os.path.basename(mount_path.rstrip("/\\")) or mount_path

    nand_dumps = _find_nand_dumps(mount_path)
    has_plausible_nand = any(d.get("plausible") for d in nand_dumps)

    gei_markers = _exists(mount_path, "_DS_MENU.DAT") and _exists(
        mount_path, "_DS_MSHL.NDS"
    )
    r4_markers = (
        _exists(mount_path, "_DS_MENU.DAT")
        or _exists(mount_path, "R4.dat")
        or _exists(mount_path, "_DSMENU.DAT")
        or _exists(mount_path, "R4TF.DAT")
    ) and not gei_markers

    over_32 = False
    if total_gb is not None:
        try:
            over_32 = float(total_gb) > 32.5
        except (TypeError, ValueError):
            over_32 = False

    return {
        "success": True,
        "mount_path": mount_path,
        "name": name,
        "fs_type": fs_type,
        "is_fat32": _is_fat32(fs_type),
        "total_size_gb": total_gb,
        "free_size_gb": free_gb,
        "over_32gb": over_32,
        "has_dcim": os.path.isdir(os.path.join(mount_path, "DCIM")),
        "has_twilight": _twilight_present(mount_path),
        "has_pit": _exists(mount_path, "private", "ds", "app", "484E494A", "pit.bin"),
        "has_boot_nds": os.path.isfile(os.path.join(mount_path, "boot.nds")),
        "has_dumptool": os.path.isfile(os.path.join(mount_path, "dumptool.nds")),
        "has_unlaunch_installer": os.path.isfile(
            os.path.join(mount_path, "unlaunch-installer.dsi")
        ),
        "nand_dumps": nand_dumps,
        "has_nand_dump": has_plausible_nand,
        "gei_markers": gei_markers,
        "r4_markers": r4_markers,
        "roms_count": _count_roms(mount_path),
    }


def quarantine_dcim(mount_path: str, log_callback=None) -> tuple[bool, str]:
    """
    Renomeia DCIM na raiz para DCIM_backup_<n> para o Memory Pit funcionar.
    Não apaga fotos.
    """
    from core.logging_util import emit_log
    from core.sdio import sync_volume

    log = lambda msg: emit_log(log_callback, msg)
    dcim = os.path.join(mount_path, "DCIM")
    if not os.path.isdir(dcim):
        return True, "Nenhuma pasta DCIM na raiz."

    n = 1
    while True:
        dest_name = f"DCIM_backup_{n}"
        dest = os.path.join(mount_path, dest_name)
        if not os.path.exists(dest):
            break
        n += 1

    try:
        os.rename(dcim, dest)
    except OSError as e:
        return False, f"Não foi possível mover DCIM: {e}"

    sync_volume(mount_path)
    log(f"✅ Pasta DCIM renomeada para {dest_name} (fotos preservadas).")
    return True, f"DCIM movida para {dest_name}."
