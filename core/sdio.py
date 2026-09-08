"""I/O seguro no cartão SD: cópia verificada, sync e preflight."""

from __future__ import annotations

import os
import sys
import tempfile
from typing import Callable, Optional

from core.cache import _sha256_file
from core.disks import get_mounted_drives, _normalize_mount
from core.logging_util import emit_log

_WRITE_TEST_NAME = ".route_1_kit_write_test"

# FAT / exFAT aceitos para cartões DSi (exFAT funciona no DSi com Unlaunch/TWiLight).
_ALLOWED_FS = {
    "fat",
    "fat16",
    "fat32",
    "vfat",
    "msdos",
    "ms-dos",
    "exfat",
    "msdos_fat",
}


def sync_volume(mount_path: str) -> None:
    """Força flush dos dados para o meio físico."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            GENERIC_READ = 0x80000000
            GENERIC_WRITE = 0x40000000
            FILE_SHARE_READ = 0x00000001
            FILE_SHARE_WRITE = 0x00000002
            OPEN_EXISTING = 3
            letter = mount_path.rstrip("\\/")
            if len(letter) >= 2 and letter[1] == ":":
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
                    GENERIC_READ | GENERIC_WRITE,
                    FILE_SHARE_READ | FILE_SHARE_WRITE,
                    None,
                    OPEN_EXISTING,
                    0,
                    None,
                )
                INVALID = wintypes.HANDLE(-1).value
                if handle != INVALID and handle is not None:
                    try:
                        ctypes.windll.kernel32.FlushFileBuffers(handle)
                    finally:
                        ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            pass
        return

    try:
        os.sync()
    except (AttributeError, OSError):
        pass


def copy_verified(
    src: str,
    dst: str,
    expected_sha256: Optional[str] = None,
    log_callback=None,
) -> str:
    """
    Copia src → dst de forma atômica e verifica SHA-256 no parcial
    *antes* do replace — assim um destino já existente nunca é destruído
    se a integridade falhar.
    Em falha remove apenas o `.partial`. Retorna o digest SHA-256.
    """
    if not os.path.isfile(src):
        raise FileNotFoundError(f"Origem inexistente: {src}")

    if expected_sha256 is None:
        expected_sha256 = _sha256_file(src)
    expected_sha256 = expected_sha256.lower()

    parent = os.path.dirname(dst) or "."
    os.makedirs(parent, exist_ok=True)
    partial = f"{dst}.partial"
    try:
        with open(src, "rb") as fin, open(partial, "wb") as fout:
            while True:
                chunk = fin.read(1024 * 1024)
                if not chunk:
                    break
                fout.write(chunk)
            fout.flush()
            os.fsync(fout.fileno())
        # Verificar o parcial antes de promover — preserva dst antigo em mismatch.
        actual = _sha256_file(partial)
        if actual != expected_sha256:
            raise RuntimeError(
                f"Integridade pós-cópia falhou em {dst}: "
                f"esperado {expected_sha256[:12]}…, obtido {actual[:12]}…"
            )
        os.replace(partial, dst)
        emit_log(log_callback, f"✅ Verificado no SD: {os.path.basename(dst)}")
        return actual
    except Exception:
        if os.path.exists(partial):
            try:
                os.remove(partial)
            except OSError:
                pass
        raise


def copytree_verified(src_dir: str, dst_dir: str, log_callback=None) -> int:
    """Copia árvore de arquivos com verificação SHA-256 por arquivo. Retorna contagem."""
    count = 0
    for root, _dirs, files in os.walk(src_dir):
        rel = os.path.relpath(root, src_dir)
        target_root = dst_dir if rel == "." else os.path.join(dst_dir, rel)
        os.makedirs(target_root, exist_ok=True)
        for name in files:
            if name.startswith("._") or name == ".DS_Store":
                continue
            s = os.path.join(root, name)
            d = os.path.join(target_root, name)
            copy_verified(s, d, log_callback=log_callback)
            count += 1
    return count


class UndoStack:
    """Lista de ações de rollback (callables sem argumentos), LIFO."""

    def __init__(self):
        self._actions: list[Callable[[], None]] = []

    def push(self, action: Callable[[], None]) -> None:
        self._actions.append(action)

    def push_remove(self, path: str) -> None:
        """Remove path no rollback se existir (ficheiro ou pasta)."""

        def _undo(p=path):
            if os.path.isdir(p):
                import shutil

                shutil.rmtree(p, ignore_errors=True)
            elif os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass

        self._actions.append(_undo)

    def push_restore_file(self, bak: str, dst: str) -> None:
        """Restaura dst a partir de bak (move) no rollback."""

        def _undo(b=bak, d=dst):
            if os.path.exists(b):
                import shutil

                shutil.move(b, d)

        self._actions.append(_undo)

    def rollback(self, log_callback=None, mount_path: Optional[str] = None) -> None:
        while self._actions:
            action = self._actions.pop()
            try:
                action()
            except Exception as e:
                emit_log(log_callback, f"⚠️ Rollback parcial: {e}")
        if mount_path:
            try:
                sync_volume(mount_path)
            except Exception:
                pass  # best-effort: flush após reverter o cartão


def preflight(
    mount_path: str,
    *,
    min_free_mb: int = 32,
    require_fat: bool = True,
) -> tuple[bool, str, Optional[dict]]:
    """
    Checagens antes de escrever no cartão.
    Retorna (ok, mensagem, drive_entry ou None).
    """
    target = _normalize_mount(mount_path)
    if not target or not os.path.exists(mount_path):
        return False, "Caminho do cartão inexistente.", None

    # Recusar raiz do sistema / home
    forbidden = {"/", "/System", "/Users", os.path.expanduser("~")}
    if sys.platform == "win32":
        forbidden |= {"C:\\", "C:/"}
    if target in {_normalize_mount(p) for p in forbidden if p}:
        return False, "Caminho do sistema recusado.", None

    drive = None
    for d in get_mounted_drives():
        if _normalize_mount(d.get("mount_path", "")) == target:
            drive = d
            break

    if not drive:
        return (
            False,
            "Unidade não reconhecida como volume removível/USB/SD.",
            None,
        )
    if not drive.get("is_removable"):
        return (
            False,
            "Unidade listada mas não marcada como removível — operação recusada.",
            drive,
        )

    if require_fat:
        fs = (drive.get("fs_type") or "").lower().replace(" ", "_")
        # Aceitar "Desconhecido" se o SO não reportou; ainda assim testamos escrita
        if fs and fs not in ("desconhecido", "unknown") and fs not in _ALLOWED_FS:
            # Alguns macOS reportam "MS-DOS (FAT32)" etc.
            normalized = fs.replace("(", "").replace(")", "").replace("-", "")
            aliases = {
                "msdosfat32": True,
                "msdosfat16": True,
                "msdosfat": True,
                "dos_fat_32": True,
            }
            ok_fs = any(tok in fs for tok in ("fat", "exfat", "msdos", "vfat"))
            if not ok_fs and not aliases.get(normalized):
                return (
                    False,
                    f"Sistema de arquivos '{drive.get('fs_type')}' não é FAT/exFAT. "
                    "Formate o cartão em FAT32 antes de continuar.",
                    drive,
                )

    free_gb = drive.get("free_size_gb") or 0
    try:
        free_gb_f = float(free_gb)
    except (TypeError, ValueError):
        free_gb_f = 0.0
    if free_gb_f * 1024 < min_free_mb:
        # Fallback via statvfs
        try:
            st = os.statvfs(mount_path)
            free_bytes = st.f_bavail * st.f_frsize
            if free_bytes < min_free_mb * 1024 * 1024:
                return (
                    False,
                    f"Espaço livre insuficiente (precisa de ~{min_free_mb} MB).",
                    drive,
                )
        except Exception:
            pass

    # Teste de escrita
    test_path = os.path.join(mount_path, _WRITE_TEST_NAME)
    write_err = None
    try:
        with open(test_path, "wb") as f:
            f.write(b"ok")
            f.flush()
            os.fsync(f.fileno())
    except OSError as e:
        write_err = e
    finally:
        # Sempre tentar remover o ficheiro de teste (mesmo se fsync falhou).
        try:
            if os.path.exists(test_path):
                os.remove(test_path)
        except OSError:
            pass  # best-effort cleanup do probe

    if write_err is not None:
        return False, f"Cartão não gravável: {write_err}", drive
    if os.path.exists(test_path):
        return False, "Cartão não gravável: não foi possível limpar ficheiro de teste.", drive

    return True, "ok", drive
