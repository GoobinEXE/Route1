import os
import sys
import shutil
import subprocess
from datetime import datetime

from core.logging_util import emit_log
from core.progress import emit_progress

_BACKUP_IGNORE_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}


def _backup_ignore(_dir, names):
    ignored = []
    for n in names:
        if n in _BACKUP_IGNORE_NAMES or n.startswith("._"):
            ignored.append(n)
    return ignored


def clean_macos_metadata(mount_path, log_callback=None):
    """Remove arquivos ocultos do macOS e lixo comum de cartões SD (multiplataforma)."""
    log = lambda msg: emit_log(log_callback, msg)

    log(f"Iniciando limpeza de metadados em {mount_path}...")
    emit_progress(log_callback, 0.05, "A limpar metadados…")

    if sys.platform == "darwin":
        try:
            emit_progress(log_callback, 0.15, "A executar dot_clean…")
            subprocess.run(
                ["dot_clean", mount_path],
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=120,
            )
            log("✅ dot_clean executado com sucesso.")
        except subprocess.TimeoutExpired:
            log("⚠️ Aviso: dot_clean excedeu o tempo limite.")
        except Exception as e:
            log(f"⚠️ Aviso ao rodar dot_clean: {e}")

    deleted_count = 0
    junk_files = {".DS_Store", "Thumbs.db", "desktop.ini"}
    junk_dirs = {".Spotlight-V100", ".Trashes", ".fseventsd", ".TemporaryItems"}

    # Contagem aproximada para progresso
    walk_roots = []
    for root, dirs, files in os.walk(mount_path, topdown=True):
        walk_roots.append((root, list(dirs), list(files)))
    total_steps = max(1, len(walk_roots))

    for idx, (root, dirs, files) in enumerate(walk_roots):
        for f in files:
            if f.startswith("._") or f in junk_files:
                p = os.path.join(root, f)
                try:
                    os.remove(p)
                    deleted_count += 1
                except Exception:
                    pass
        for d in dirs:
            if d in junk_dirs:
                p = os.path.join(root, d)
                try:
                    shutil.rmtree(p, ignore_errors=True)
                    deleted_count += 1
                except Exception:
                    pass
        if idx % 5 == 0 or idx + 1 == total_steps:
            emit_progress(
                log_callback,
                0.2 + 0.7 * ((idx + 1) / total_steps),
                f"A limpar… {idx + 1}/{total_steps}",
            )

    if sys.platform != "win32":
        try:
            emit_progress(log_callback, 0.95, "A sincronizar…")
            subprocess.run(["sync"], check=False, timeout=60)
        except Exception:
            pass  # best-effort: sync pode falhar/timeout sem invalidar a limpeza

    log(f"✅ Limpeza finalizada! {deleted_count} itens temporários removidos.")
    emit_progress(log_callback, 1.0, "Limpeza concluída.")
    return True, f"{deleted_count} itens limpos com sucesso."


def _count_files(path):
    total = 0
    for _root, _dirs, files in os.walk(path):
        total += len(files)
    return total


def backup_drive(mount_path, log_callback=None):
    """Cria um backup completo do cartão SD no Desktop do usuário."""
    log = lambda msg: emit_log(log_callback, msg)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    vol_name = os.path.basename(mount_path.rstrip("\\/")) or "SD"
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    if not os.path.isdir(desktop):
        for candidate in (
            os.path.join(os.path.expanduser("~"), "Área de Trabalho"),
            os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop"),
            os.path.expanduser("~"),
        ):
            if os.path.isdir(candidate):
                desktop = candidate
                break

    backup_dir = os.path.join(desktop, f"Backup_{vol_name}_{timestamp}")

    log(f"Criando pasta de backup: {backup_dir}")
    emit_progress(log_callback, 0.02, "A criar pasta de backup…")
    os.makedirs(backup_dir, exist_ok=True)

    items = [item for item in os.listdir(mount_path) if not item.startswith(".")]
    total_items = max(1, len(items))
    copied = 0
    file_count = 0
    errors = 0
    for item in items:
        src = os.path.join(mount_path, item)
        dst = os.path.join(backup_dir, item)
        frac = copied / total_items
        emit_progress(
            log_callback,
            0.05 + 0.9 * frac,
            f"A copiar {item}… ({copied}/{total_items})",
        )
        log(f"Copiando: {item} ...")
        try:
            if os.path.isdir(src):
                n_files = _count_files(src)
                # symlinks=True: não seguir links (evita escapar do cartão)
                shutil.copytree(src, dst, ignore=_backup_ignore, symlinks=True)
                file_count += n_files
                log(f"   ↳ {item}/ ({n_files} arquivos)")
            else:
                if item in _BACKUP_IGNORE_NAMES or item.startswith("._"):
                    continue
                shutil.copy2(src, dst, follow_symlinks=False)
                file_count += 1
            copied += 1
        except Exception as e:
            errors += 1
            log(f"⚠️ Erro ao copiar {item}: {e}")

    if errors or copied == 0:
        log(f"❌ Backup incompleto em: {backup_dir} ({copied} itens, {errors} erros)")
        return False, backup_dir

    emit_progress(log_callback, 1.0, "Backup concluído.")
    log(f"✅ Backup concluído em: {backup_dir} ({copied} itens, ~{file_count} arquivos)")
    return True, backup_dir
