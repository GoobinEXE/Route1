import array
import fcntl
import json
import os
import plistlib
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile

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
_MACOS_SLICE_RE = re.compile(r"^disk\d+s\d+$")
_NEWFS_MSDOS_BINS = ("/sbin/newfs_msdos", "/usr/sbin/newfs_msdos")
_DISKUTIL_BIN = "/usr/sbin/diskutil"
_AUTHOPEN_BIN = "/usr/libexec/authopen"
_HDIUTIL_BIN = "/usr/bin/hdiutil"
# Só nós de fatia FAT: /dev/diskNsM ou /dev/rdiskNsM (nunca disco inteiro).
_MACOS_DEV_NODE_RE = re.compile(r"^/dev/r?disk\d+s\d+$")
_MACOS_ATTACHED_DISK_RE = re.compile(r"^/dev/disk\d+$")


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


def _macos_newfs_bin():
    found = shutil.which("newfs_msdos") or "/sbin/newfs_msdos"
    if found in _NEWFS_MSDOS_BINS:
        return found
    return "/sbin/newfs_msdos"


def _macos_newfs_argv(newfs_bin, volume_name, dev):
    return [
        newfs_bin,
        "-F",
        "32",
        "-b",
        str(TARGET_CLUSTER_BYTES),
        "-v",
        volume_name,
        dev,
    ]


def _macos_newfs_needs_privilege(returncode, stderr, stdout):
    """True se newfs falhou por permissão ou volume ainda montado (não por geometria)."""
    if returncode == 0:
        return False
    text = f"{stderr or ''} {stdout or ''}".lower()
    hints = (
        "permission denied",
        "operation not permitted",
        "not permitted",
        "resource busy",
        "device busy",
    )
    return any(h in text for h in hints)


def _macos_admin_cancelled(text):
    t = (text or "").lower()
    return (
        "user canceled" in t
        or "user cancelled" in t
        or "cancelou" in t
        or "(-128)" in t
        or "authorization canceled" in t
        or "authorization cancelled" in t
    )


def _macos_admin_newfs_shell(newfs_bin, volume_name, parent_disk, part_id):
    """
    Shell elevado (legado): desmontar + newfs na mesma invocação.
    Preferir authopen — osascript+root ainda leva EPERM em /dev/rdisk no macOS moderno.
    Só chamar com parent_disk/part_id/volume_name já validados (allowlist).
    """
    return (
        f"{_DISKUTIL_BIN} unmountDisk force /dev/{parent_disk} && "
        f"{newfs_bin} -F 32 -b {int(TARGET_CLUSTER_BYTES)} "
        f"-v {volume_name} /dev/r{part_id}"
    )


def _macos_run_admin_shell(shell_cmd):
    """Corre um comando allowlisted com o diálogo de administrador do macOS."""
    timeout_s = int(_SUBPROC_FORMAT_TIMEOUT)
    script = (
        f"with timeout of {timeout_s} seconds\n"
        f"do shell script {json.dumps(shell_cmd)} with administrator privileges\n"
        "end timeout"
    )
    osa = shutil.which("osascript") or "/usr/bin/osascript"
    return subprocess.run(
        [osa, "-e", script],
        capture_output=True,
        text=True,
        timeout=timeout_s + 90,
    )


def _macos_recv_scm_rights(sock, max_fds=16):
    """Recebe FDs via SCM_RIGHTS; devolve o primeiro e fecha extras."""
    itemsize = array.array("i").itemsize
    bufsize = socket.CMSG_SPACE(max_fds * itemsize)
    try:
        _msg, ancdata, _flags, _addr = sock.recvmsg(4096, bufsize)
    except OSError as e:
        return None, f"authopen (recvmsg): {e}"
    received = []
    for level, typ, data in ancdata:
        if level != socket.SOL_SOCKET or typ != socket.SCM_RIGHTS:
            continue
        nbytes = len(data) - (len(data) % itemsize)
        if nbytes <= 0:
            continue
        arr = array.array("i")
        arr.frombytes(data[:nbytes])
        received.extend(int(x) for x in arr)
    if not received:
        return None, "authopen não devolveu descritor do dispositivo"
    first = received[0]
    for extra in received[1:]:
        try:
            os.close(extra)
        except OSError:
            pass
    return first, ""


def _macos_authopen_rdwr(dev_path, timeout_s=None):
    """
    Abre /dev/rdiskNsM (ou disk) via authopen -stdoutpipe.
    Diálogo nativo de autorização de disco; evita EPERM do osascript+root.
    Retorna (fd|None, erro).
    """
    if not _MACOS_DEV_NODE_RE.fullmatch(dev_path or ""):
        return None, "dispositivo fora da allowlist"
    if not os.path.exists(_AUTHOPEN_BIN):
        return None, "authopen indisponível neste macOS"
    timeout_s = int(timeout_s if timeout_s is not None else _SUBPROC_FORMAT_TIMEOUT)
    parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    proc = None
    try:
        parent.settimeout(float(timeout_s))
        # stdout=socket: authopen envia o FD autorizado via SCM_RIGHTS.
        proc = subprocess.Popen(
            [_AUTHOPEN_BIN, "-stdoutpipe", "-o", str(int(os.O_RDWR)), dev_path],
            stdin=subprocess.DEVNULL,
            stdout=child,
            stderr=subprocess.PIPE,
            text=True,
        )
        child.close()
        child = None
        fd, err = _macos_recv_scm_rights(parent)
        try:
            stderr = proc.communicate(timeout=min(60, timeout_s))[1] or ""
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate(timeout=5)
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
            return None, "autorização de disco excedeu o tempo limite"
        if fd is None:
            detail = (stderr or err or "").strip()
            if proc.returncode and not detail:
                detail = f"authopen saiu com código {proc.returncode}"
            return None, detail or err or "falha na autorização do disco"
        return fd, ""
    except Exception as e:
        return None, f"authopen: {type(e).__name__}"
    finally:
        try:
            parent.close()
        except OSError:
            pass
        if child is not None:
            try:
                child.close()
            except OSError:
                pass
        if proc is not None and proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass


def _macos_partition_total_size(part_id):
    """TotalSize (bytes) da fatia via diskutil; None se indisponível."""
    if not _MACOS_SLICE_RE.fullmatch(part_id or ""):
        return None
    try:
        out = subprocess.check_output(
            ["diskutil", "info", "-plist", f"/dev/{part_id}"],
            stderr=subprocess.DEVNULL,
            timeout=_SUBPROC_INFO_TIMEOUT,
        )
        data = plistlib.loads(out)
        size = data.get("TotalSize")
        if isinstance(size, int) and size >= 1024 * 1024:
            return size
    except Exception:
        return None
    return None


def _macos_fat32_prefix_from_bpb(path):
    """Bytes do prefixo FS (reservado + FATs + 1 cluster raiz) a partir do BPB."""
    try:
        with open(path, "rb") as f:
            bpb = f.read(512)
    except OSError:
        return None
    if len(bpb) < 512 or bpb[510:512] != b"\x55\xaa":
        return None
    bps = struct.unpack_from("<H", bpb, 11)[0]
    reserved = struct.unpack_from("<H", bpb, 14)[0]
    nfats = int(bpb[16])
    sec_per_clust = int(bpb[13])
    fatsz16 = struct.unpack_from("<H", bpb, 22)[0]
    fatsz = fatsz16 or struct.unpack_from("<I", bpb, 36)[0]
    if bps <= 0 or reserved <= 0 or nfats <= 0 or fatsz <= 0 or sec_per_clust <= 0:
        return None
    # Inclui 1 cluster de dados (raiz FAT32) além das FATs.
    sectors = reserved + (nfats * fatsz) + sec_per_clust
    return int(sectors) * int(bps)


def _macos_image_payload_bytes(path, size_cap):
    """
    Quanto copiar da imagem sparse para o dispositivo.
    Preferir SEEK_HOLE; fallback BPB; teto size_cap.
    """
    end = None
    try:
        with open(path, "rb") as f:
            hole = os.lseek(f.fileno(), 0, os.SEEK_HOLE)
            if isinstance(hole, int) and hole >= 512:
                end = hole
    except OSError:
        end = None
    if end is None:
        end = _macos_fat32_prefix_from_bpb(path)
    if end is None or end < 512:
        end = min(int(size_cap), 128 * 1024 * 1024)
    return min(int(end), int(size_cap))


def _macos_copy_to_fd(src_path, dest_fd, nbytes):
    """Copia nbytes do ficheiro para o FD (já posicionado). Retorna (ok, erro|bytes)."""
    copied = 0
    try:
        os.lseek(dest_fd, 0, os.SEEK_SET)
        with open(src_path, "rb") as src:
            while copied < nbytes:
                chunk = src.read(min(1024 * 1024, nbytes - copied))
                if not chunk:
                    break
                offset = 0
                while offset < len(chunk):
                    n = os.write(dest_fd, chunk[offset:])
                    if n <= 0:
                        return False, "escrita no dispositivo devolveu 0"
                    offset += n
                    copied += n
        try:
            fcntl.fcntl(dest_fd, fcntl.F_FULLFSYNC)
        except OSError:
            os.fsync(dest_fd)
        return True, copied
    except OSError as e:
        return False, f"escrita no dispositivo: {e}"


def _macos_parse_hdiutil_attach_dev(stdout):
    """Extrai /dev/diskN do stdout do hdiutil attach."""
    for line in (stdout or "").splitlines():
        token = (line.strip().split() or [""])[0]
        if _MACOS_ATTACHED_DISK_RE.fullmatch(token):
            return token
    return ""


def _macos_build_fat32_sparse_image(newfs_bin, volume_name, size_bytes):
    """
    Cria imagem sparse, anexa com hdiutil (CRawDiskImage) e corre newfs_msdos.
    No macOS moderno newfs recusa ficheiros comuns (Cannot get partition offset).
    Retorna (path|None, erro). Caller apaga o path em sucesso.
    """
    if newfs_bin not in _NEWFS_MSDOS_BINS:
        return None, "binário newfs_msdos inválido"
    if not _VOLUME_NAME_RE.fullmatch(volume_name or ""):
        return None, "nome de volume inválido"
    try:
        size_bytes = int(size_bytes)
    except (TypeError, ValueError):
        return None, "tamanho da partição inválido"
    # FAT32 com cluster 32 KB exige >= ~65525 clusters (~2.1 GiB).
    min_fat32 = 65525 * int(TARGET_CLUSTER_BYTES)
    if size_bytes < min_fat32:
        return None, (
            f"partição demasiado pequena para FAT32/32 KB "
            f"({size_bytes} bytes; mínimo ~{min_fat32})"
        )

    hdiutil = shutil.which("hdiutil") or _HDIUTIL_BIN
    if not os.path.exists(hdiutil):
        return None, "hdiutil indisponível"

    img_path = None
    attached = ""
    success = False
    try:
        tmp = tempfile.NamedTemporaryFile(
            prefix="r1k_fat32_", suffix=".img", delete=False
        )
        img_path = tmp.name
        tmp.close()
        with open(img_path, "wb") as img:
            img.truncate(size_bytes)

        att = subprocess.run(
            [
                hdiutil,
                "attach",
                "-imagekey",
                "diskimage-class=CRawDiskImage",
                "-nomount",
                img_path,
            ],
            capture_output=True,
            text=True,
            timeout=_SUBPROC_INFO_TIMEOUT,
        )
        if att.returncode != 0:
            return None, (att.stderr or att.stdout or "hdiutil attach falhou").strip()
        attached = _macos_parse_hdiutil_attach_dev(att.stdout)
        if not attached:
            return None, "hdiutil attach não devolveu /dev/diskN"

        nf = subprocess.run(
            _macos_newfs_argv(newfs_bin, volume_name, attached),
            capture_output=True,
            text=True,
            timeout=_SUBPROC_FORMAT_TIMEOUT,
        )
        if nf.returncode != 0:
            return None, (nf.stderr or nf.stdout or "newfs_msdos (imagem) falhou").strip()
        success = True
        return img_path, ""
    except subprocess.TimeoutExpired:
        return None, "criação da imagem FAT32 excedeu o tempo limite"
    except Exception as e:
        return None, f"imagem FAT32: {type(e).__name__}"
    finally:
        if attached:
            subprocess.run(
                [hdiutil, "detach", attached, "-force"],
                capture_output=True,
                text=True,
                timeout=_SUBPROC_INFO_TIMEOUT,
                check=False,
            )
        if img_path and not success:
            try:
                os.remove(img_path)
            except OSError:
                pass


def _macos_newfs_with_authopen(newfs_bin, volume_name, dev_path):
    """
    Formata FAT32 32 KB sem newfs direto no /dev (EPERM mesmo com root/osascript).

    1) imagem sparse + hdiutil attach + newfs (newfs recusa ficheiros crus)
    2) authopen abre o dispositivo com FD autorizado
    3) copia o prefixo FS para o FD (/dev/fd/N reabre e perde a auth)
    """
    if not _MACOS_DEV_NODE_RE.fullmatch(dev_path or ""):
        return False, "dispositivo fora da allowlist"
    if not _VOLUME_NAME_RE.fullmatch(volume_name or ""):
        return False, "nome de volume inválido"
    if newfs_bin not in _NEWFS_MSDOS_BINS:
        return False, "binário newfs_msdos inválido"

    m = re.fullmatch(r"/dev/r?(disk\d+s\d+)", dev_path)
    if not m:
        return False, "dispositivo fora da allowlist"
    part_id = m.group(1)
    size = _macos_partition_total_size(part_id)
    if not size:
        return False, "tamanho da partição indisponível"

    img_path = None
    fd = None
    try:
        img_path, err = _macos_build_fat32_sparse_image(newfs_bin, volume_name, size)
        if not img_path:
            return False, err or "falha ao criar imagem FAT32"

        payload = _macos_image_payload_bytes(img_path, size)

        fd, err = _macos_authopen_rdwr(dev_path)
        if fd is None:
            return False, err or "falha na autorização do disco"

        ok, detail = _macos_copy_to_fd(img_path, fd, payload)
        if not ok:
            return False, str(detail)
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "newfs_msdos (imagem) excedeu o tempo limite"
    except Exception as e:
        return False, f"newfs via authopen: {type(e).__name__}"
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if img_path:
            try:
                os.remove(img_path)
            except OSError:
                pass


def _macos_first_fat_slice(parent_disk):
    """Identificador diskNsM da partição FAT após partitionDisk; fallback s1."""
    fallback = f"{parent_disk}s1"
    try:
        out = subprocess.check_output(
            ["diskutil", "list", "-plist", f"/dev/{parent_disk}"],
            stderr=subprocess.DEVNULL,
            timeout=_SUBPROC_INFO_TIMEOUT,
        )
        data = plistlib.loads(out)
        candidates = []
        for item in data.get("AllDisksAndPartitions") or []:
            for part in item.get("Partitions") or []:
                ident = part.get("DeviceIdentifier") or ""
                if not _MACOS_SLICE_RE.fullmatch(ident):
                    continue
                content = (part.get("Content") or "").upper()
                if "FAT" in content or "DOS_FAT" in content:
                    return ident
                candidates.append(ident)
        if candidates:
            return candidates[0]
        for ident in data.get("AllDisks") or []:
            if isinstance(ident, str) and _MACOS_SLICE_RE.fullmatch(ident):
                return ident
    except Exception:
        pass
    return fallback


def _macos_force_cluster32(parent_disk, part_id, volume_name):
    """
    Força FAT32 com cluster 32 KB via newfs_msdos.
    Sem privilégios o newfs falha (diskutil já criou o FAT32); nesse caso usa
    hdiutil+newfs numa imagem e grava o prefixo via authopen.
    Retorna (ok, mensagem_de_erro).
    """
    if _macos_whole_disk_id(parent_disk) != parent_disk:
        return False, "identificador de disco inválido"
    if not _MACOS_SLICE_RE.fullmatch(part_id or ""):
        return False, "identificador de partição inválido"
    if not _VOLUME_NAME_RE.fullmatch(volume_name or ""):
        return False, "nome de volume inválido"
    if not part_id.startswith(parent_disk + "s"):
        return False, "partição não pertence ao disco selecionado"

    newfs = _macos_newfs_bin()
    rpart = f"/dev/r{part_id}"
    part = f"/dev/{part_id}"
    whole = f"/dev/{parent_disk}"

    subprocess.run(
        ["diskutil", "unmountDisk", "force", whole],
        capture_output=True,
        text=True,
        timeout=_SUBPROC_INFO_TIMEOUT,
        check=False,
    )

    nf = subprocess.run(
        _macos_newfs_argv(newfs, volume_name, rpart),
        capture_output=True,
        text=True,
        timeout=_SUBPROC_FORMAT_TIMEOUT,
    )
    if nf.returncode == 0:
        return True, ""

    nf2 = subprocess.run(
        _macos_newfs_argv(newfs, volume_name, part),
        capture_output=True,
        text=True,
        timeout=_SUBPROC_FORMAT_TIMEOUT,
    )
    if nf2.returncode == 0:
        return True, ""

    last_err = (nf2.stderr or nf.stderr or nf2.stdout or nf.stdout or "").strip()
    need_priv = _macos_newfs_needs_privilege(
        nf.returncode, nf.stderr, nf.stdout
    ) or _macos_newfs_needs_privilege(nf2.returncode, nf2.stderr, nf2.stdout)
    if not need_priv:
        return False, last_err

    # macOS moderno: osascript+root → EPERM; /dev/fd/N perde authopen;
    # newfs em ficheiro → "Cannot get partition offset". Fluxo:
    # hdiutil+newfs (1×) → authopen FD → copiar prefixo FAT.
    size = _macos_partition_total_size(part_id)
    if not size:
        return False, "tamanho da partição indisponível"

    img_path, img_err = _macos_build_fat32_sparse_image(newfs, volume_name, size)
    if not img_path:
        return False, img_err or "falha ao criar imagem FAT32"

    try:
        payload = _macos_image_payload_bytes(img_path, size)
        auth_err = ""
        for dev in (rpart, part):
            fd, aerr = _macos_authopen_rdwr(dev)
            if fd is None:
                auth_err = aerr or auth_err
                if _macos_admin_cancelled(aerr or ""):
                    return (
                        False,
                        "autorização de acesso ao disco cancelada — "
                        "no macOS o cluster 32 KB exige autorização.",
                    )
                continue
            try:
                ok, detail = _macos_copy_to_fd(img_path, fd, payload)
            finally:
                try:
                    os.close(fd)
                except OSError:
                    pass
            if ok:
                return True, ""
            auth_err = str(detail) if detail else auth_err

        return False, auth_err or last_err
    finally:
        try:
            os.remove(img_path)
        except OSError:
            pass


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
        part_id = _macos_first_fat_slice(parent_disk)
        part_dev = f"/dev/{part_id}"
        cluster_ok = False
        cluster_err = "falha ao forçar cluster 32 KB"
        try:
            cluster_ok, cluster_err = _macos_force_cluster32(
                parent_disk, part_id, volume_name
            )
        finally:
            # Remontar mesmo em falha — senão o cartão fica invisível no Finder.
            # Não deixar TimeoutExpired do mount mascarar o erro do cluster.
            try:
                subprocess.run(
                    ["diskutil", "mount", part_dev],
                    capture_output=True,
                    text=True,
                    timeout=_SUBPROC_INFO_TIMEOUT,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                pass
        if not cluster_ok:
            return (
                False,
                "FAT32 criado, mas falhou ao forçar cluster 32 KB: "
                f"{cluster_err or 'newfs_msdos recusou o dispositivo'}",
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
