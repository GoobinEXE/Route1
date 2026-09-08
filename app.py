#!/usr/bin/env python3
"""
DSi SD Studio — App desktop multiplataforma (pywebview).
"""

import os
import sys
import threading
from collections import deque
from functools import wraps

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import webview

from core.cleaner import backup_drive, clean_macos_metadata
from core.disks import format_sd_card, get_mounted_drives, is_safe_mount_path
from core.exploits import setup_nand_backup_stage, setup_unlaunch_stage
from core.rom_cleaner import organize_roms_directory
from core.twilight import install_gei_kernel

LOG_MAX = 500
SYSTEM_LOGS = deque(maxlen=LOG_MAX)
LOG_LOCK = threading.Lock()
OP_LOCK = threading.Lock()
_LOG_SEQ = 0


def add_log(msg):
    global _LOG_SEQ
    with LOG_LOCK:
        _LOG_SEQ += 1
        SYSTEM_LOGS.append({"id": _LOG_SEQ, "msg": msg})


def _run_mount_op(require_safe=True):
    """Decorator: valida mount_path, serializa operações e padroniza erros."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(self, mount_path, *args, **kwargs):
            if not mount_path:
                return {"success": False, "error": "Caminho do cartão não especificado."}
            if require_safe and not is_safe_mount_path(mount_path):
                return {
                    "success": False,
                    "error": (
                        "Unidade não reconhecida como volume removível/USB/SD. "
                        "Atualize a lista e selecione o cartão novamente."
                    ),
                }
            if not OP_LOCK.acquire(blocking=False):
                return {
                    "success": False,
                    "error": "Outra operação já está em andamento. Aguarde.",
                }
            try:
                return fn(self, mount_path, *args, **kwargs)
            except Exception as e:
                add_log(f"❌ Erro na operação: {e}")
                return {"success": False, "error": str(e)}
            finally:
                OP_LOCK.release()

        return wrapper

    return decorator


class Api:
    """Bridge JS ↔ Python exposta via pywebview.js_api."""

    def get_disks(self):
        drives = get_mounted_drives()
        return {"success": True, "drives": drives}

    def get_logs(self, since=0):
        try:
            since_id = int(since or 0)
        except (TypeError, ValueError):
            since_id = 0
        with LOG_LOCK:
            sliced = [e["msg"] for e in SYSTEM_LOGS if e["id"] > since_id]
            next_id = _LOG_SEQ
        return {"logs": sliced, "next_index": next_id}

    def clear_logs(self):
        with LOG_LOCK:
            SYSTEM_LOGS.clear()
        return {"success": True}

    @_run_mount_op()
    def setup_nand_dump(self, mount_path, has_facebook=True):
        setup_nand_backup_stage(
            mount_path,
            has_facebook=bool(has_facebook),
            log_callback=add_log,
        )
        return {
            "success": True,
            "message": "Etapa 1 (Memory Pit + dumpTool) configurada com sucesso!",
        }

    @_run_mount_op()
    def setup_unlaunch(self, mount_path):
        setup_unlaunch_stage(mount_path, log_callback=add_log)
        return {
            "success": True,
            "message": "Etapa 2 (TWiLight Menu++ & Unlaunch) configurada com sucesso!",
        }

    @_run_mount_op()
    def setup_gei(self, mount_path):
        success, msg = install_gei_kernel(mount_path, log_callback=add_log)
        return {
            "success": success,
            "message": msg if success else None,
            "error": None if success else msg,
        }

    @_run_mount_op()
    def organize_roms(self, mount_path):
        success, msg = organize_roms_directory(mount_path, log_callback=add_log)
        return {
            "success": success,
            "message": msg if success else None,
            "error": None if success else msg,
        }

    @_run_mount_op()
    def backup(self, mount_path):
        success, path = backup_drive(mount_path, log_callback=add_log)
        return {"success": success, "message": f"Backup salvo em: {path}"}

    @_run_mount_op()
    def clean_sd(self, mount_path):
        success, msg = clean_macos_metadata(mount_path, log_callback=add_log)
        return {"success": success, "message": msg}

    @_run_mount_op()
    def format_sd(self, mount_path):
        add_log(f"Formatando unidade {mount_path} em FAT32...")
        success, msg = format_sd_card(mount_path)
        add_log(msg)
        return {
            "success": success,
            "message": msg if success else None,
            "error": None if success else msg,
        }


def start_app():
    index_path = os.path.join(BASE_DIR, "static", "index.html")
    api = Api()

    print("\n=======================================================")
    print("  DSi SD Studio — App Desktop")
    print("  Feche a janela para encerrar.")
    print("=======================================================\n")
    add_log("DSi SD Studio iniciado (pywebview).")

    icon_path = os.path.join(BASE_DIR, "static", "assets", "app-icon-256.png")
    if not os.path.isfile(icon_path):
        icon_path = os.path.join(BASE_DIR, "static", "assets", "app-icon.png")
    if not os.path.isfile(icon_path):
        icon_path = None

    webview.create_window(
        "DSi SD Studio",
        url=index_path,
        js_api=api,
        width=1100,
        height=800,
        min_size=(900, 600),
        background_color="#F0F2F5",
    )
    webview.start(icon=icon_path)


if __name__ == "__main__":
    start_app()
