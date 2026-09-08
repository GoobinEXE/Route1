import json
import os
import plistlib
import shutil
import subprocess
import sys

# Capacidade acima disso quase certamente não é cartão SD / pendrive típico de DSi.
MAX_SAFE_VOLUME_GB = 256


def _drive_entry(
    name,
    mount_path,
    device_id="",
    fs_type="Desconhecido",
    total_bytes=0,
    free_bytes=0,
    bus_protocol="",
    is_removable=True,
):
    return {
        "name": name,
        "mount_path": mount_path,
        "device_id": device_id,
        "fs_type": fs_type or "Desconhecido",
        "total_size_gb": round(total_bytes / (1024**3), 2) if total_bytes else 0,
        "free_size_gb": round(free_bytes / (1024**3), 2) if free_bytes else 0,
        "bus_protocol": bus_protocol or "",
        "is_removable": bool(is_removable),
    }


def _statvfs_sizes(mount_path):
    st = os.statvfs(mount_path)
    total = st.f_blocks * st.f_frsize
    free = st.f_bavail * st.f_frsize
    return total, free


def _within_size_limit(total_bytes):
    if not total_bytes:
        return True
    return (total_bytes / (1024**3)) <= MAX_SAFE_VOLUME_GB


def _normalize_mount(path):
    if not path:
        return ""
    path = os.path.abspath(path)
    if sys.platform == "win32":
        return path.rstrip("\\/") + "\\"
    return path.rstrip("/")


def is_safe_mount_path(mount_path):
    """True se o caminho ainda aparece na lista segura de unidades externas."""
    target = _normalize_mount(mount_path)
    if not target or not os.path.exists(mount_path):
        return False
    for d in get_mounted_drives():
        if _normalize_mount(d.get("mount_path", "")) == target and d.get("is_removable"):
            return True
    return False


# --- macOS -----------------------------------------------------------------


_MAC_SAFE_BUS = {
    "USB",
    "Secure Digital",
    "SD",
    "Secure Digital Card",
}


def _macos_volume_allowed(data):
    removable = bool(data.get("Removable") or data.get("RemovableMedia"))
    bus = (data.get("BusProtocol") or "").strip()
    bus_ok = bus in _MAC_SAFE_BUS or bus.upper() == "USB"
    internal = bool(data.get("Internal"))
    ejectable = bool(data.get("Ejectable"))
    total = data.get("TotalSize", 0) or 0
    if not _within_size_limit(total):
        return False
    # Preferir removível / USB / SD; aceitar ejectable não-interno (leitores SD)
    if removable or bus_ok:
        return True
    if ejectable and not internal and bus_ok:
        return True
    return False


def _get_mounted_drives_macos():
    drives = []
    try:
        volumes = os.listdir("/Volumes")
    except Exception as e:
        print(f"Erro ao listar drives: {e}")
        return drives

    for vol in volumes:
        if vol == "Macintosh HD" or vol.startswith("."):
            continue

        mount_path = os.path.join("/Volumes", vol)
        if not os.path.ismount(mount_path):
            continue

        try:
            out = subprocess.check_output(
                ["diskutil", "info", "-plist", mount_path],
                stderr=subprocess.DEVNULL,
            )
            data = plistlib.loads(out)
            if not _macos_volume_allowed(data):
                continue
            drives.append(
                _drive_entry(
                    name=vol,
                    mount_path=mount_path,
                    device_id=data.get("DeviceIdentifier", ""),
                    fs_type=data.get("FilesystemType", "Desconhecido"),
                    total_bytes=data.get("TotalSize", 0) or 0,
                    free_bytes=data.get("FreeSpace", 0) or 0,
                    bus_protocol=data.get("BusProtocol", ""),
                    is_removable=True,
                )
            )
        except Exception:
            # Sem diskutil info confiável: não assumir removível
            pass

    return drives


# --- Windows ---------------------------------------------------------------


def _windows_bus_type(root):
    """
    Consulta BusType via IOCTL_STORAGE_QUERY_PROPERTY.
    Retorna inteiro BusType ou None.
    BusType: 7=USB, 8=RAID, 11=SATA, 12=SD, 13=MMC, 17=NVMe, ...
    """
    try:
        import ctypes
        from ctypes import wintypes

        GENERIC_READ = 0x80000000
        FILE_SHARE_READ = 0x00000001
        FILE_SHARE_WRITE = 0x00000002
        OPEN_EXISTING = 3
        IOCTL_STORAGE_QUERY_PROPERTY = 0x002D1400

        class STORAGE_PROPERTY_QUERY(ctypes.Structure):
            _fields_ = [
                ("PropertyId", wintypes.DWORD),
                ("QueryType", wintypes.DWORD),
                ("AdditionalParameters", ctypes.c_byte * 1),
            ]

        class STORAGE_DEVICE_DESCRIPTOR(ctypes.Structure):
            _fields_ = [
                ("Version", wintypes.DWORD),
                ("Size", wintypes.DWORD),
                ("DeviceType", ctypes.c_byte),
                ("DeviceTypeModifier", ctypes.c_byte),
                ("RemovableMedia", ctypes.c_byte),
                ("CommandQueueing", ctypes.c_byte),
                ("VendorIdOffset", wintypes.DWORD),
                ("ProductIdOffset", wintypes.DWORD),
                ("ProductRevisionOffset", wintypes.DWORD),
                ("SerialNumberOffset", wintypes.DWORD),
                ("BusType", ctypes.c_byte),
                ("RawPropertiesLength", wintypes.DWORD),
            ]

        letter = root.rstrip("\\/")
        if len(letter) < 2 or letter[1] != ":":
            return None
        path = f"\\\\.\\{letter[0]}:"

        CreateFileW = ctypes.windll.kernel32.CreateFileW
        CreateFileW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        CreateFileW.restype = wintypes.HANDLE

        handle = CreateFileW(
            path,
            GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            0,
            None,
        )
        INVALID = wintypes.HANDLE(-1).value
        if handle == INVALID or handle is None:
            return None

        try:
            query = STORAGE_PROPERTY_QUERY()
            query.PropertyId = 0  # StorageDeviceProperty
            query.QueryType = 0  # PropertyStandardQuery
            buf_size = 1024
            buf = ctypes.create_string_buffer(buf_size)
            returned = wintypes.DWORD(0)
            DeviceIoControl = ctypes.windll.kernel32.DeviceIoControl
            ok = DeviceIoControl(
                handle,
                IOCTL_STORAGE_QUERY_PROPERTY,
                ctypes.byref(query),
                ctypes.sizeof(query),
                buf,
                buf_size,
                ctypes.byref(returned),
                None,
            )
            if not ok:
                return None
            desc = STORAGE_DEVICE_DESCRIPTOR.from_buffer_copy(buf.raw)
            return int(desc.BusType)
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:
        return None


_WIN_SAFE_BUS = {7, 12, 13}  # USB, SD, MMC


def _get_mounted_drives_windows():
    drives = []
    try:
        import ctypes
        from ctypes import wintypes

        GetDriveTypeW = ctypes.windll.kernel32.GetDriveTypeW
        GetDiskFreeSpaceExW = ctypes.windll.kernel32.GetDiskFreeSpaceExW
        GetVolumeInformationW = ctypes.windll.kernel32.GetVolumeInformationW
        GetLogicalDriveStringsW = ctypes.windll.kernel32.GetLogicalDriveStringsW

        GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
        GetDriveTypeW.restype = wintypes.UINT

        buf = ctypes.create_unicode_buffer(254)
        length = GetLogicalDriveStringsW(ctypes.sizeof(buf), buf)
        if not length:
            return drives

        raw = buf[:length].split("\x00")
        for root in raw:
            if not root:
                continue
            # DRIVE_REMOVABLE = 2, DRIVE_FIXED = 3
            dtype = GetDriveTypeW(root)
            if dtype not in (2, 3):
                continue
            if root.upper().startswith("C:"):
                continue

            free_bytes = ctypes.c_ulonglong(0)
            total_bytes = ctypes.c_ulonglong(0)
            GetDiskFreeSpaceExW(
                ctypes.c_wchar_p(root),
                None,
                ctypes.byref(total_bytes),
                ctypes.byref(free_bytes),
            )

            if not _within_size_limit(total_bytes.value):
                continue

            is_removable = dtype == 2
            bus_type = _windows_bus_type(root)
            bus_label = "USB/SD"
            if dtype == 3:
                # FIXED: só se bus for USB/SD/MMC
                if bus_type not in _WIN_SAFE_BUS:
                    continue
                is_removable = True
                if bus_type == 7:
                    bus_label = "USB"
                elif bus_type in (12, 13):
                    bus_label = "SD/MMC"
            elif bus_type in _WIN_SAFE_BUS:
                if bus_type == 7:
                    bus_label = "USB"
                elif bus_type in (12, 13):
                    bus_label = "SD/MMC"

            vol_name_buf = ctypes.create_unicode_buffer(261)
            fs_name_buf = ctypes.create_unicode_buffer(261)
            GetVolumeInformationW(
                ctypes.c_wchar_p(root),
                vol_name_buf,
                ctypes.sizeof(vol_name_buf),
                None,
                None,
                None,
                fs_name_buf,
                ctypes.sizeof(fs_name_buf),
            )

            label = vol_name_buf.value or root.rstrip("\\")
            drives.append(
                _drive_entry(
                    name=label,
                    mount_path=root if root.endswith("\\") else root + "\\",
                    device_id=root.rstrip("\\"),
                    fs_type=fs_name_buf.value or "Desconhecido",
                    total_bytes=total_bytes.value,
                    free_bytes=free_bytes.value,
                    bus_protocol=bus_label,
                    is_removable=is_removable,
                )
            )
    except Exception as e:
        print(f"Erro ao listar drives (Windows): {e}")

    return drives


# --- Linux -----------------------------------------------------------------


def _linux_mount_candidates():
    paths = []
    user = os.environ.get("USER") or os.environ.get("USERNAME") or ""
    for base in (f"/media/{user}", f"/run/media/{user}", "/media", "/mnt"):
        if os.path.isdir(base):
            paths.append(base)
    return paths


def _linux_fs_type(mount_path):
    if shutil.which("findmnt"):
        try:
            out = subprocess.check_output(
                ["findmnt", "-n", "-o", "FSTYPE", mount_path],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            if out:
                return out
        except Exception:
            pass
    return "vfat"


def _linux_is_removable_mount(mount_path):
    """Usa lsblk/findmnt para confirmar RM=1 no dispositivo."""
    if not shutil.which("lsblk"):
        return None  # desconhecido
    try:
        source = None
        if shutil.which("findmnt"):
            source = subprocess.check_output(
                ["findmnt", "-n", "-o", "SOURCE", mount_path],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        if not source:
            return None
        # Resolver para o disco pai e checar RM
        out = subprocess.check_output(
            ["lsblk", "-n", "-o", "RM", "-p", source],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        # Pode retornar várias linhas (part + disk); qualquer 1 basta
        for line in out.splitlines():
            if line.strip() in ("1", "true", "True"):
                return True
        return False
    except Exception:
        return None


def _collect_lsblk_removable(block, drives, seen):
    children = block.get("children") or []
    for child in children:
        _collect_lsblk_removable(child, drives, seen)

    mount = block.get("mountpoint")
    if not mount or mount in seen:
        return
    if block.get("type") not in ("part", "disk"):
        return
    rm = block.get("rm")
    if str(rm) not in ("1", "true", "True"):
        return

    try:
        total, free = _statvfs_sizes(mount)
    except Exception:
        total, free = 0, 0
    if not _within_size_limit(total):
        return

    seen.add(mount)
    drives.append(
        _drive_entry(
            name=os.path.basename(mount) or block.get("name", "SD"),
            mount_path=mount,
            device_id=block.get("name", ""),
            fs_type=block.get("fstype") or "vfat",
            total_bytes=total,
            free_bytes=free,
            bus_protocol="USB/SD",
            is_removable=True,
        )
    )


def _get_mounted_drives_linux():
    drives = []
    seen = set()

    # Preferir lsblk (flag RM confiável)
    if shutil.which("lsblk"):
        try:
            out = subprocess.check_output(
                ["lsblk", "-J", "-o", "NAME,SIZE,FSTYPE,MOUNTPOINT,RM,TYPE"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            data = json.loads(out)
            for block in data.get("blockdevices", []):
                _collect_lsblk_removable(block, drives, seen)
            if drives:
                return drives
        except Exception as e:
            print(f"Erro ao listar drives (lsblk): {e}")

    # Fallback: pastas de mídia, mas só se RM confirmado (ou desconhecido e <256GB)
    for base in _linux_mount_candidates():
        try:
            entries = os.listdir(base)
        except Exception:
            continue

        for name in entries:
            if name.startswith("."):
                continue
            mount_path = os.path.join(base, name)

            candidates = []
            if os.path.ismount(mount_path):
                candidates.append((name, mount_path))
            elif os.path.isdir(mount_path):
                try:
                    for child in os.listdir(mount_path):
                        child_path = os.path.join(mount_path, child)
                        if os.path.ismount(child_path):
                            candidates.append((child, child_path))
                except Exception:
                    pass

            for label, path in candidates:
                if path in seen:
                    continue
                rm = _linux_is_removable_mount(path)
                if rm is False:
                    continue
                try:
                    total, free = _statvfs_sizes(path)
                except Exception:
                    continue
                if not _within_size_limit(total):
                    continue
                # Se RM desconhecido, só aceitar se estiver sob /media|/run/media do usuário
                if rm is None and not (
                    path.startswith("/media/") or path.startswith("/run/media/")
                ):
                    continue
                seen.add(path)
                drives.append(
                    _drive_entry(
                        name=label,
                        mount_path=path,
                        fs_type=_linux_fs_type(path),
                        total_bytes=total,
                        free_bytes=free,
                        bus_protocol="USB/SD",
                        is_removable=True,
                    )
                )

    return drives


def get_mounted_drives():
    """Retorna unidades externas / cartões SD montados (macOS, Windows, Linux)."""
    if sys.platform == "darwin":
        return _get_mounted_drives_macos()
    if sys.platform == "win32":
        return _get_mounted_drives_windows()
    return _get_mounted_drives_linux()


# --- Formatação ------------------------------------------------------------


def _format_sd_macos(mount_path, volume_name):
    try:
        out = subprocess.check_output(
            ["diskutil", "info", "-plist", mount_path],
            stderr=subprocess.DEVNULL,
        )
        data = plistlib.loads(out)
        if not _macos_volume_allowed(data):
            return False, "Volume não parece removível/USB/SD — formatação recusada."

        parent_disk = data.get("ParentWholeDisk") or data.get("DeviceIdentifier")
        if not parent_disk:
            return False, "Identificador do disco não encontrado."

        if "s" in parent_disk and parent_disk.startswith("disk"):
            parent_disk = parent_disk.split("s")[0]

        cmd = [
            "diskutil",
            "partitionDisk",
            f"/dev/{parent_disk}",
            "MBR",
            "FAT32",
            volume_name,
            "0b",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            return True, f"Cartão formatado com sucesso como {volume_name} (FAT32)!"
        return False, f"Erro ao formatar: {res.stderr or res.stdout}"
    except Exception as e:
        return False, str(e)


def _format_sd_windows(mount_path, volume_name):
    letter = mount_path.rstrip("\\/")
    if len(letter) >= 2 and letter[1] == ":":
        letter = letter[0]
    else:
        return False, "Letra da unidade inválida."

    try:
        cmd = [
            "cmd",
            "/c",
            f"format {letter}: /FS:FAT32 /V:{volume_name} /Q /Y",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            return True, f"Cartão formatado com sucesso como {volume_name} (FAT32)!"
        err = (res.stderr or res.stdout or "").strip()
        hint = " Execute o app como Administrador se a formatação falhar por permissão."
        return False, f"Erro ao formatar: {err or 'código ' + str(res.returncode)}.{hint}"
    except Exception as e:
        return False, str(e)


def _format_sd_linux(mount_path, volume_name):
    device = None
    if shutil.which("findmnt"):
        try:
            device = subprocess.check_output(
                ["findmnt", "-n", "-o", "SOURCE", mount_path],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except Exception:
            device = None

    if not device:
        return (
            False,
            "Não foi possível determinar o dispositivo do volume. Use um gerenciador de discos.",
        )

    if not shutil.which("mkfs.vfat"):
        return False, "mkfs.vfat não encontrado. Instale dosfstools."

    try:
        subprocess.run(
            ["umount", mount_path], capture_output=True, text=True, check=False
        )
        label = (volume_name or "DSI_SD")[:11]
        res = subprocess.run(
            ["mkfs.vfat", "-F", "32", "-n", label, device],
            capture_output=True,
            text=True,
        )
        if res.returncode == 0:
            return True, f"Cartão formatado com sucesso como {label} (FAT32)!"
        err = (res.stderr or res.stdout or "").strip()
        return False, f"Erro ao formatar (pode precisar de sudo): {err or res.returncode}"
    except Exception as e:
        return False, str(e)


def format_sd_card(mount_path, volume_name="DSi_SD"):
    """Formata o cartão selecionado para FAT32 (comportamento por SO)."""
    if not is_safe_mount_path(mount_path):
        return (
            False,
            "Formatação recusada: o caminho não é um volume removível/USB/SD reconhecido.",
        )
    if sys.platform == "darwin":
        return _format_sd_macos(mount_path, volume_name)
    if sys.platform == "win32":
        return _format_sd_windows(mount_path, volume_name)
    return _format_sd_linux(mount_path, volume_name)
