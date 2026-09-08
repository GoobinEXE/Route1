import json
import os
import plistlib
import re
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
    """Normaliza mount para comparação (realpath; abspath se realpath falhar)."""
    if not path:
        return ""
    try:
        path = os.path.realpath(path)
    except OSError:
        path = os.path.abspath(path)
    if sys.platform == "win32":
        return path.rstrip("\\/") + "\\"
    return path.rstrip("/")


def is_safe_mount_path(mount_path):
    """True se o caminho ainda aparece na lista segura de unidades externas."""
    return resolve_safe_drive(mount_path) is not None


def resolve_safe_drive(mount_path):
    """
    Retorna a entrada de drive segura correspondente a mount_path, ou None.
    Exige is_removable=True e caminho normalizado igual.
    """
    if not mount_path or not isinstance(mount_path, str):
        return None
    if "\x00" in mount_path:
        return None
    if not os.path.exists(mount_path):
        return None
    target = _normalize_mount(mount_path)
    if not target:
        return None
    for d in get_mounted_drives():
        if _normalize_mount(d.get("mount_path", "")) == target and d.get("is_removable"):
            return d
    return None


# Timeouts: listagem/info curtos; formatação/desmontagem mais longos.
_SUBPROC_INFO_TIMEOUT = 30
_SUBPROC_FORMAT_TIMEOUT = 300

# dsi.cfw.guide / Unlaunch: FAT32 com cluster 32 KiB (evita "Clusters too large").
TARGET_CLUSTER_BYTES = 32768
# Setores de 512 bytes × 64 = 32768.
_FAT_SECTORS_PER_CLUSTER_32K = 64


def _resolve_linux_source(mount_path):
    if not shutil.which("findmnt"):
        return None
    try:
        return subprocess.check_output(
            ["findmnt", "-n", "-o", "SOURCE", mount_path],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=_SUBPROC_INFO_TIMEOUT,
        ).strip() or None
    except Exception:
        return None


def _linux_still_mounted(device_or_mount):
    """True se findmnt ainda encontra o device/mount."""
    if not shutil.which("findmnt"):
        return os.path.ismount(device_or_mount) if os.path.isdir(device_or_mount) else False
    try:
        out = subprocess.check_output(
            ["findmnt", "-n", device_or_mount],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=_SUBPROC_INFO_TIMEOUT,
        ).strip()
        return bool(out)
    except Exception:
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
                timeout=_SUBPROC_INFO_TIMEOUT,
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

        # nBufferLength é em TCHARs (caracteres), NÃO em bytes — sizeof()
        # aqui provocaria escrita past-the-end do buffer.
        n_chars = len(buf)
        length = GetLogicalDriveStringsW(n_chars, buf)
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
            # nVolumeNameSize / nFileSystemNameSize também são em TCHARs.
            GetVolumeInformationW(
                ctypes.c_wchar_p(root),
                vol_name_buf,
                len(vol_name_buf),
                None,
                None,
                None,
                fs_name_buf,
                len(fs_name_buf),
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
                timeout=_SUBPROC_INFO_TIMEOUT,
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
                timeout=_SUBPROC_INFO_TIMEOUT,
            ).strip()
        if not source:
            return None
        # Resolver para o disco pai e checar RM
        out = subprocess.check_output(
            ["lsblk", "-n", "-o", "RM", "-p", source],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=_SUBPROC_INFO_TIMEOUT,
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
    name = block.get("name", "") or ""
    # Normalizar para caminho de dispositivo absoluto (ex.: /dev/sdb1)
    if name and not name.startswith("/"):
        device_id = f"/dev/{name}"
    else:
        device_id = name
    drives.append(
        _drive_entry(
            name=os.path.basename(mount) or block.get("name", "SD"),
            mount_path=mount,
            device_id=device_id,
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
                timeout=_SUBPROC_INFO_TIMEOUT,
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
                # Se RM desconhecido, listar sob /media|/run/media mas NÃO marcar removível
                # (format_sd / is_safe_mount_path recusam is_removable=False).
                if rm is None and not (
                    path.startswith("/media/") or path.startswith("/run/media/")
                ):
                    continue
                removable = True if rm is True else False
                seen.add(path)
                drives.append(
                    _drive_entry(
                        name=label,
                        mount_path=path,
                        device_id=_resolve_linux_source(path) or "",
                        fs_type=_linux_fs_type(path),
                        total_bytes=total,
                        free_bytes=free,
                        bus_protocol="USB/SD",
                        is_removable=removable,
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

_VOLUME_NAME_RE = re.compile(r"^[A-Za-z0-9_]{1,11}$")
_WIN_LETTER_RE = re.compile(r"^[D-Z]$")
_MACOS_DISK_ID_RE = re.compile(r"^(disk\d+)(?:s\d+)?$")


def _macos_whole_disk_id(identifier):
    """Extrai o disco inteiro (diskN) de diskN ou diskNsM. Evita split('s')."""
    if not identifier or not isinstance(identifier, str):
        return ""
    m = _MACOS_DISK_ID_RE.fullmatch(identifier.strip())
    return m.group(1) if m else ""


def get_cluster_size_bytes(mount_path: str):
    """
    Tenta ler o tamanho do cluster (allocation unit) do volume montado.
    Retorna int (bytes) ou None se indisponível.
    """
    if not mount_path or not os.path.isdir(mount_path):
        return None
    try:
        if sys.platform == "darwin":
            out = subprocess.check_output(
                ["diskutil", "info", "-plist", mount_path],
                stderr=subprocess.DEVNULL,
                timeout=_SUBPROC_INFO_TIMEOUT,
            )
            data = plistlib.loads(out)
            # Preferir AllocationBlockSize; fallback VolumeAllocationBlockSize.
            for key in ("AllocationBlockSize", "VolumeAllocationBlockSize"):
                val = data.get(key)
                if isinstance(val, int) and val > 0:
                    return val
            return None

        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            root = mount_path
            if len(root) >= 2 and root[1] == ":":
                root = root[:2] + "\\"
            spc = wintypes.DWORD()
            bps = wintypes.DWORD()
            free_c = wintypes.DWORD()
            total_c = wintypes.DWORD()
            ok = ctypes.windll.kernel32.GetDiskFreeSpaceW(
                ctypes.c_wchar_p(root),
                ctypes.byref(spc),
                ctypes.byref(bps),
                ctypes.byref(free_c),
                ctypes.byref(total_c),
            )
            if not ok:
                return None
            if spc.value and bps.value:
                return int(spc.value) * int(bps.value)
            return None

        # Linux: statvfs f_frsize is often the cluster/fragment size on vfat.
        st = os.statvfs(mount_path)
        fr = int(getattr(st, "f_frsize", 0) or 0)
        return fr if fr > 0 else None
    except Exception:
        return None


def _format_sd_macos(mount_path, volume_name, expected_device_id=""):
    try:
        out = subprocess.check_output(
            ["diskutil", "info", "-plist", mount_path],
            stderr=subprocess.DEVNULL,
            timeout=_SUBPROC_INFO_TIMEOUT,
        )
        data = plistlib.loads(out)
        if not _macos_volume_allowed(data):
            return False, "Volume não parece removível/USB/SD — formatação recusada."

        device_id = data.get("DeviceIdentifier") or ""
        if expected_device_id and device_id and expected_device_id != device_id:
            return (
                False,
                f"Dispositivo mudou desde a seleção ({expected_device_id} → {device_id}). "
                "Atualize a lista e tente de novo.",
            )

        parent_disk = data.get("ParentWholeDisk") or device_id
        if not parent_disk:
            return False, "Identificador do disco não encontrado."

        # disk4s1 → disk4. NÃO usar split("s"): "disk" contém "s" → "di".
        raw_id = parent_disk
        parent_disk = _macos_whole_disk_id(parent_disk)
        if not parent_disk:
            return False, f"Identificador de disco inválido: {raw_id}"

        cmd = [
            "diskutil",
            "partitionDisk",
            f"/dev/{parent_disk}",
            "MBR",
            "FAT32",
            volume_name,
            "0b",
        ]
        res = subprocess.run(
            cmd, capture_output=True, text=True, timeout=_SUBPROC_FORMAT_TIMEOUT
        )
        if res.returncode != 0:
            return False, f"Erro ao formatar: {res.stderr or res.stdout}"

        # partitionDisk não garante cluster 32 KB — reforçar com newfs_msdos.
        part_id = f"{parent_disk}s1"
        part_dev = f"/dev/{part_id}"
        rpart_dev = f"/dev/r{part_id}"
        # Desmontar volume (pode ter remontado automaticamente).
        subprocess.run(
            ["diskutil", "unmount", "force", part_dev],
            capture_output=True,
            text=True,
            timeout=_SUBPROC_INFO_TIMEOUT,
            check=False,
        )
        newfs = shutil.which("newfs_msdos") or "/sbin/newfs_msdos"
        nf = subprocess.run(
            [
                newfs,
                "-F",
                "32",
                "-b",
                str(TARGET_CLUSTER_BYTES),
                "-v",
                volume_name,
                rpart_dev,
            ],
            capture_output=True,
            text=True,
            timeout=_SUBPROC_FORMAT_TIMEOUT,
        )
        if nf.returncode != 0:
            # Fallback: tentar sem raw device.
            nf2 = subprocess.run(
                [
                    newfs,
                    "-F",
                    "32",
                    "-b",
                    str(TARGET_CLUSTER_BYTES),
                    "-v",
                    volume_name,
                    part_dev,
                ],
                capture_output=True,
                text=True,
                timeout=_SUBPROC_FORMAT_TIMEOUT,
            )
            if nf2.returncode != 0:
                return (
                    False,
                    "FAT32 criado, mas falhou ao forçar cluster 32 KB: "
                    f"{(nf2.stderr or nf.stderr or nf2.stdout or nf.stdout).strip()}",
                )

        subprocess.run(
            ["diskutil", "mount", part_dev],
            capture_output=True,
            text=True,
            timeout=_SUBPROC_INFO_TIMEOUT,
            check=False,
        )
        return (
            True,
            f"Cartão formatado com sucesso como {volume_name} "
            f"(FAT32, cluster {TARGET_CLUSTER_BYTES // 1024} KB)!",
        )
    except subprocess.TimeoutExpired:
        return False, "Formatação excedeu o tempo limite."
    except Exception as e:
        return False, str(e)


def _format_sd_windows(mount_path, volume_name, expected_device_id=""):
    letter = mount_path.rstrip("\\/")
    if len(letter) >= 2 and letter[1] == ":":
        letter = letter[0].upper()
    else:
        return False, "Letra da unidade inválida."

    if not _WIN_LETTER_RE.match(letter):
        return False, f"Letra de unidade recusada: {letter} (use D–Z, nunca C:)."

    if expected_device_id:
        exp = expected_device_id.rstrip("\\/").upper()
        if exp and exp != f"{letter}:" and exp != letter:
            return (
                False,
                f"Dispositivo mudou desde a seleção ({expected_device_id} → {letter}:). "
                "Atualize a lista e tente de novo.",
            )

    try:
        # Lista de args — sem shell string interpolation
        format_bin = shutil.which("format.com") or shutil.which("format") or "format.com"
        cmd = [
            format_bin,
            f"{letter}:",
            "/FS:FAT32",
            f"/A:{TARGET_CLUSTER_BYTES}",
            f"/V:{volume_name}",
            "/Q",
            "/Y",
        ]
        res = subprocess.run(
            cmd, capture_output=True, text=True, timeout=_SUBPROC_FORMAT_TIMEOUT
        )
        if res.returncode == 0:
            return (
                True,
                f"Cartão formatado com sucesso como {volume_name} "
                f"(FAT32, cluster {TARGET_CLUSTER_BYTES // 1024} KB)!",
            )
        err = (res.stderr or res.stdout or "").strip()
        hint = (
            " Execute o app como Administrador se a formatação falhar por permissão. "
            "Em cartões >32 GB o Windows pode recusar FAT32 — use uma ferramenta "
            "como GUIFormat com allocation 32768."
        )
        return False, f"Erro ao formatar: {err or 'código ' + str(res.returncode)}.{hint}"
    except subprocess.TimeoutExpired:
        return False, "Formatação excedeu o tempo limite."
    except Exception as e:
        return False, str(e)


def _unmount_linux(mount_path, device):
    """Tenta umount; se falhar, tenta udisksctl. Retorna (ok, mensagem)."""
    um = subprocess.run(
        ["umount", mount_path],
        capture_output=True,
        text=True,
        check=False,
        timeout=_SUBPROC_INFO_TIMEOUT,
    )
    if um.returncode == 0 or not _linux_still_mounted(mount_path):
        if not _linux_still_mounted(device) and not _linux_still_mounted(mount_path):
            return True, "ok"
        if um.returncode == 0:
            return True, "ok"

    if shutil.which("udisksctl") and device:
        ud = subprocess.run(
            ["udisksctl", "unmount", "-b", device],
            capture_output=True,
            text=True,
            check=False,
            timeout=_SUBPROC_INFO_TIMEOUT,
        )
        if ud.returncode == 0 or (
            not _linux_still_mounted(mount_path) and not _linux_still_mounted(device)
        ):
            return True, "ok"
        return False, (ud.stderr or ud.stdout or um.stderr or "falha ao desmontar").strip()

    return False, (um.stderr or um.stdout or "falha ao desmontar").strip()


def _format_sd_linux(mount_path, volume_name, expected_device_id=""):
    device = _resolve_linux_source(mount_path)
    if not device:
        return (
            False,
            "Não foi possível determinar o dispositivo do volume. Use um gerenciador de discos.",
        )

    if expected_device_id:
        def _dev_key(d):
            d = (d or "").strip()
            if d.startswith("/dev/"):
                d = d[5:]
            return d

        if _dev_key(expected_device_id) != _dev_key(device):
            return (
                False,
                f"Dispositivo mudou desde a seleção ({expected_device_id} → {device}). "
                "Atualize a lista e tente de novo.",
            )

    if not shutil.which("mkfs.vfat"):
        return False, "mkfs.vfat não encontrado. Instale dosfstools."

    try:
        ok, umsg = _unmount_linux(mount_path, device)
        if not ok:
            return False, f"Não foi possível desmontar o volume antes de formatar: {umsg}"
        if _linux_still_mounted(mount_path) or _linux_still_mounted(device):
            return False, "Volume ainda montado após umount — formatação abortada."

        label = (volume_name or "DSI_SD")[:11]
        res = subprocess.run(
            [
                "mkfs.vfat",
                "-F",
                "32",
                "-s",
                str(_FAT_SECTORS_PER_CLUSTER_32K),
                "-n",
                label,
                device,
            ],
            capture_output=True,
            text=True,
            timeout=_SUBPROC_FORMAT_TIMEOUT,
        )
        if res.returncode == 0:
            return (
                True,
                f"Cartão formatado com sucesso como {label} "
                f"(FAT32, cluster {TARGET_CLUSTER_BYTES // 1024} KB)!",
            )
        err = (res.stderr or res.stdout or "").strip()
        return False, f"Erro ao formatar (pode precisar de sudo): {err or res.returncode}"
    except subprocess.TimeoutExpired:
        return False, "Formatação excedeu o tempo limite."
    except Exception as e:
        return False, str(e)


def format_sd_card(mount_path, volume_name="DSi_SD"):
    """Formata o cartão selecionado para FAT32 com cluster 32 KB (comportamento por SO)."""
    if not _VOLUME_NAME_RE.match(volume_name or ""):
        return False, "Nome de volume inválido (use 1–11 caracteres A-Z, 0-9 ou _)."

    drive = resolve_safe_drive(mount_path)
    if not drive:
        return (
            False,
            "Formatação recusada: o caminho não é um volume removível/USB/SD reconhecido.",
        )

    device_id = drive.get("device_id") or ""
    # Revalidar imediatamente antes da operação destrutiva
    drive2 = resolve_safe_drive(mount_path)
    if not drive2:
        return False, "Volume desapareceu antes da formatação."
    device_id2 = drive2.get("device_id") or device_id
    if device_id and device_id2 and device_id != device_id2:
        return False, "Dispositivo mudou entre validação e formatação — abortado."

    if sys.platform == "darwin":
        return _format_sd_macos(mount_path, volume_name, expected_device_id=device_id2)
    if sys.platform == "win32":
        return _format_sd_windows(mount_path, volume_name, expected_device_id=device_id2)

    # Linux: exigir device_id resolvido e revalidar RM=1
    if not device_id2:
        device_id2 = _resolve_linux_source(mount_path) or ""
    if not device_id2:
        return False, "Não foi possível pinjar o dispositivo Linux (findmnt SOURCE vazio)."
    rm = _linux_is_removable_mount(mount_path)
    if rm is False:
        return False, "Dispositivo não é removível (lsblk RM=0) — formatação abortada."
    if not device_id2.startswith("/dev/"):
        return False, f"Caminho de dispositivo inválido: {device_id2}"
    return _format_sd_linux(mount_path, volume_name, expected_device_id=device_id2)
