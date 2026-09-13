#!/usr/bin/env python3
"""
Route 1 Kit — App desktop multiplataforma (pywebview).
"""

import os
import sys
import threading
import time
import webbrowser
from collections import deque
from functools import wraps

def _resolve_base_dir():
    """Raiz do app: pasta do fonte, ou _MEIPASS quando empacotado (PyInstaller)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _resolve_base_dir()
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import webview

from core import __version__
from core.about import build_about_payload, is_allowed_external_url
from core.boxart import install_boxarts as do_install_boxarts
from core.cleaner import backup_drive, clean_macos_metadata
from core.disks import format_sd_card, get_mounted_drives, is_safe_mount_path
from core.exploits import setup_nand_backup_stage, setup_unlaunch_stage
from core.homebrew_catalog import build_catalog_payload
from core.inspect_sd import inspect_sd_card, quarantine_dcim as do_quarantine_dcim
from core.privacy import expand_user_path, redact_path, redact_text
from core.progress import clamp_fraction
from core.rom_cleaner import organize_roms_directory
from core.sd_utils import (
    copy_nand_backup as do_copy_nand_backup,
    format_sd_report as do_sd_report,
    install_cheats as do_install_cheats,
    install_homebrew as do_install_homebrew,
    setup_godmode9i as do_setup_godmode9i,
)
from core.sdio import preflight
from core.twilight import install_gei_kernel, install_r4_kernel, probe_kernels

LOG_MAX = 500
SYSTEM_LOGS = deque(maxlen=LOG_MAX)
LOG_LOCK = threading.Lock()
OP_LOCK = threading.Lock()
_LOG_SEQ = 0

# Progresso da operação em curso (lido pelo poll de logs da UI).
_OP_PROGRESS = {
    "active": False,
    "fraction": 0.0,
    "detail": "",
    "started_at": 0.0,
    "updated_at": 0.0,
}

# pywebview serializa JSON; rejeitar tipos inesperados na fronteira JS↔Python.
_TRUE_LITERALS = frozenset({"1", "true", "yes", "on"})
_FALSE_LITERALS = frozenset({"0", "false", "no", "off", ""})


def add_log(msg):
    global _LOG_SEQ
    with LOG_LOCK:
        _LOG_SEQ += 1
        SYSTEM_LOGS.append({"id": _LOG_SEQ, "msg": redact_text(msg)})


def begin_op_progress(detail="Operação em andamento…"):
    now = time.time()
    with LOG_LOCK:
        _OP_PROGRESS["active"] = True
        _OP_PROGRESS["fraction"] = 0.0
        _OP_PROGRESS["detail"] = redact_text(detail) if detail else ""
        _OP_PROGRESS["started_at"] = now
        _OP_PROGRESS["updated_at"] = now


def set_op_progress(fraction, detail=None):
    """Atualiza fração (0–1) e opcionalmente o detalhe; nunca regride a fração."""
    frac = clamp_fraction(fraction)
    with LOG_LOCK:
        if not _OP_PROGRESS["active"]:
            return
        if frac >= _OP_PROGRESS["fraction"]:
            _OP_PROGRESS["fraction"] = frac
        if detail:
            _OP_PROGRESS["detail"] = redact_text(detail)
        _OP_PROGRESS["updated_at"] = time.time()


def end_op_progress():
    with LOG_LOCK:
        _OP_PROGRESS["active"] = False
        _OP_PROGRESS["fraction"] = 0.0
        _OP_PROGRESS["detail"] = ""
        _OP_PROGRESS["started_at"] = 0.0
        _OP_PROGRESS["updated_at"] = 0.0


def get_op_progress_snapshot():
    with LOG_LOCK:
        if not _OP_PROGRESS["active"]:
            return None
        return {
            "active": True,
            "fraction": float(_OP_PROGRESS["fraction"]),
            "detail": _OP_PROGRESS["detail"],
            "started_at": float(_OP_PROGRESS["started_at"]),
            "updated_at": float(_OP_PROGRESS["updated_at"]),
        }


class OpSink:
    """Callback de log + progresso (passado como log_callback às ops do core)."""

    def __call__(self, msg):
        add_log(msg)

    def progress(self, fraction, detail=None):
        set_op_progress(fraction, detail)


op_sink = OpSink()


def _reject(error):
    return {"success": False, "error": redact_text(error)}


def _as_path_str(value, *, label="caminho"):
    """Exige str não vazia sem NUL (path traversal / injeção via bytes)."""
    if not isinstance(value, str):
        return None, f"{label.capitalize()} inválido (tipo)."
    if "\x00" in value:
        return None, f"{label.capitalize()} inválido."
    cleaned = value.strip()
    if not cleaned:
        return None, f"{label.capitalize()} não especificado."
    return cleaned, None


def _as_bool(value, *, default=None):
    """
    Tipagem estrita para flags vindas do JS.
    Aceita bool nativo; 0/1; e literais comuns em string.
    Rejeita o resto (evita bool('false') == True em Python).
    """
    if isinstance(value, bool):
        return value, None
    if isinstance(value, int) and value in (0, 1):
        return bool(value), None
    if isinstance(value, str):
        low = value.strip().lower()
        if low in _TRUE_LITERALS:
            return True, None
        if low in _FALSE_LITERALS:
            return False, None
    if default is not None and value is None:
        return default, None
    return None, "Flag booleana inválida."


def _run_mount_op(require_safe=True, min_free_mb=32, skip_preflight=False):
    """Decorator: valida mount_path, preflight, serializa operações e padroniza erros."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(self, mount_path, *args, **kwargs):
            mount_path, err = _as_path_str(mount_path, label="caminho do cartão")
            if err:
                return _reject(err)
            if require_safe and not is_safe_mount_path(mount_path):
                return _reject(
                    "Unidade não reconhecida como volume removível/USB/SD. "
                    "Atualize a lista e selecione o cartão novamente."
                )
            if not OP_LOCK.acquire(blocking=False):
                return _reject("Outra operação já está em andamento. Aguarde.")
            begin_op_progress("Operação em andamento…")
            try:
                # Preflight dentro do lock: evita I/O paralelo no cartão com outra op.
                if not skip_preflight:
                    ok, msg, _drive = preflight(mount_path, min_free_mb=min_free_mb)
                    if not ok:
                        return _reject(msg)
                set_op_progress(0.02, "Pré-voo concluído…")
                return fn(self, mount_path, *args, **kwargs)
            except Exception as e:
                add_log(f"❌ Erro na operação: {redact_text(e)}")
                return _reject(e)
            finally:
                end_op_progress()
                OP_LOCK.release()

        return wrapper

    return decorator


def _api_result(success, msg):
    """Padroniza message/error com redação de paths."""
    safe = redact_text(msg) if msg else msg
    return {
        "success": success,
        "message": safe if success else None,
        "error": None if success else safe,
    }


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
        return {
            "logs": sliced,
            "next_index": next_id,
            "progress": get_op_progress_snapshot(),
        }

    def get_about(self):
        """Metadados da tela Sobre + última entrada do CHANGELOG.md."""
        try:
            return build_about_payload(BASE_DIR)
        except Exception as e:
            return _reject(e)

    def open_external_url(self, url):
        """Abre URL allowlisted no browser do sistema (Sobre / GameBrew / Universal-DB)."""
        if not isinstance(url, str):
            return _reject("URL inválida.")
        cleaned = url.strip()
        if not is_allowed_external_url(cleaned):
            return _reject("URL não permitida.")
        try:
            webbrowser.open(cleaned)
            return {"success": True}
        except Exception as e:
            return _reject(e)

    def get_homebrew_catalog(self):
        """Catálogo de apps instaláveis (só leitura)."""
        try:
            return build_catalog_payload()
        except Exception as e:
            return _reject(e)

    def clear_logs(self):
        with LOG_LOCK:
            SYSTEM_LOGS.clear()
        return {"success": True}

    def inspect_sd(self, mount_path):
        """Somente leitura — sem preflight de escrita; ainda exige volume removível.

        Serializa com OP_LOCK (non-blocking): evita snapshot inconsistente
        enquanto outra thread escreve no cartão.
        """
        mount_path, err = _as_path_str(mount_path, label="caminho do cartão")
        if err:
            return _reject(err)
        if not is_safe_mount_path(mount_path):
            return _reject(
                "Unidade não reconhecida como volume removível/USB/SD. "
                "Atualize a lista e selecione o cartão novamente."
            )
        if not OP_LOCK.acquire(blocking=False):
            return _reject("Outra operação já está em andamento. Aguarde.")
        begin_op_progress("A inspecionar o cartão…")
        try:
            set_op_progress(0.15, "A ler o cartão…")
            result = inspect_sd_card(mount_path)
            set_op_progress(1.0, "Inspeção concluída.")
            return result
        except Exception as e:
            return _reject(e)
        finally:
            end_op_progress()
            OP_LOCK.release()

    def probe_kernels(self):
        begin_op_progress("A procurar kernels em Downloads…")
        try:
            set_op_progress(0.2, "A procurar em Downloads…")
            result = probe_kernels()
            set_op_progress(1.0, "Procura concluída.")
            return result
        except Exception as e:
            return {
                "success": False,
                "error": redact_text(e),
                "gei": None,
                "r4": [],
            }
        finally:
            end_op_progress()

    @_run_mount_op(min_free_mb=1)
    def quarantine_dcim(self, mount_path):
        success, msg = do_quarantine_dcim(mount_path, log_callback=op_sink)
        return _api_result(success, msg)

    @_run_mount_op(min_free_mb=8)
    def setup_nand_dump(self, mount_path, has_facebook=True):
        flag, err = _as_bool(has_facebook, default=True)
        if err:
            return _reject(err)
        setup_nand_backup_stage(
            mount_path,
            has_facebook=flag,
            log_callback=op_sink,
        )
        set_op_progress(1.0, "Etapa 1 concluída.")
        return {
            "success": True,
            "message": "Etapa 1 (Memory Pit + dumpTool) configurada com sucesso!",
        }

    @_run_mount_op(min_free_mb=64)
    def setup_unlaunch(self, mount_path):
        setup_unlaunch_stage(mount_path, log_callback=op_sink)
        set_op_progress(1.0, "Etapa 2 concluída.")
        return {
            "success": True,
            "message": "Etapa 2 (TWiLight Menu++ & Unlaunch) configurada com sucesso!",
        }

    @_run_mount_op(min_free_mb=8)
    def setup_gei(self, mount_path):
        success, msg = install_gei_kernel(mount_path, log_callback=op_sink)
        if success:
            set_op_progress(1.0, "Kernel GEi instalado.")
        return _api_result(success, msg)

    @_run_mount_op(min_free_mb=8)
    def setup_r4(self, mount_path, source_dir=""):
        # source_dir vem do JS (pode ser ~/… redigido); tipar + expanduser;
        # allowlist Downloads/cache fica em install_r4_kernel.
        if source_dir is None or source_dir == "":
            source_dir = ""
        else:
            source_dir, err = _as_path_str(source_dir, label="diretório de origem")
            if err:
                return _reject(err)
            source_dir = expand_user_path(source_dir)
        success, msg = install_r4_kernel(
            mount_path, source_dir, log_callback=op_sink
        )
        if success:
            set_op_progress(1.0, "Kernel R4 instalado.")
        return _api_result(success, msg)

    @_run_mount_op(min_free_mb=4)
    def organize_roms(self, mount_path):
        success, msg = organize_roms_directory(mount_path, log_callback=op_sink)
        if success:
            set_op_progress(1.0, "Organização concluída.")
        return _api_result(success, msg)

    @_run_mount_op(min_free_mb=1)
    def sd_report(self, mount_path):
        success, msg = do_sd_report(mount_path, log_callback=op_sink)
        if success:
            set_op_progress(1.0, "Relatório concluído.")
        return _api_result(success, msg)

    @_run_mount_op(min_free_mb=4)
    def setup_godmode9i(self, mount_path):
        success, msg = do_setup_godmode9i(mount_path, log_callback=op_sink)
        if success:
            set_op_progress(1.0, "GodMode9i instalado.")
        return _api_result(success, msg)

    @_run_mount_op(min_free_mb=16)
    def install_homebrew(self, mount_path, app_id):
        app_id, err = _as_path_str(app_id, label="aplicação")
        if err:
            return _reject(err)
        success, msg = do_install_homebrew(
            mount_path, app_id, log_callback=op_sink
        )
        if success:
            set_op_progress(1.0, "App instalado.")
        return _api_result(success, msg)

    @_run_mount_op(min_free_mb=64)
    def install_cheats(self, mount_path):
        success, msg = do_install_cheats(mount_path, log_callback=op_sink)
        if success:
            set_op_progress(1.0, "Cheats instalados.")
        return _api_result(success, msg)

    @_run_mount_op(min_free_mb=1)
    def copy_nand_backup(self, mount_path):
        success, msg = do_copy_nand_backup(mount_path, log_callback=op_sink)
        if success:
            set_op_progress(1.0, "Cópia do dump concluída.")
        return _api_result(success, msg)

    @_run_mount_op(min_free_mb=32)
    def install_boxarts(self, mount_path):
        success, msg = do_install_boxarts(mount_path, log_callback=op_sink)
        if success:
            set_op_progress(1.0, "Boxarts instaladas.")
        return _api_result(success, msg)

    @_run_mount_op(min_free_mb=1)
    def backup(self, mount_path):
        success, path = backup_drive(mount_path, log_callback=op_sink)
        shown = redact_path(path) if path else path
        if success:
            set_op_progress(1.0, "Backup concluído.")
            return {"success": True, "message": f"Backup salvo em: {shown}"}
        return {
            "success": False,
            "error": f"Backup incompleto ou falhou. Pasta parcial: {shown}",
        }

    @_run_mount_op(min_free_mb=1)
    def clean_sd(self, mount_path):
        success, msg = clean_macos_metadata(mount_path, log_callback=op_sink)
        if success:
            set_op_progress(1.0, "Limpeza concluída.")
        out = _api_result(success, msg)
        # clean_sd historicamente devolve message também em falha
        if not success:
            out["message"] = out.get("error")
        return out

    @_run_mount_op(min_free_mb=1, skip_preflight=True)
    def format_sd(self, mount_path):
        # Formatação: não exigir FAT no preflight (o objetivo é converter para FAT32).
        # Ainda valida removível via is_safe_mount_path no decorator e format_sd_card.
        op_sink(f"Formatando unidade {mount_path} em FAT32 (cluster 32 KB)...")
        set_op_progress(0.08, "A preparar formatação…")
        ok, msg, _drive = preflight(mount_path, min_free_mb=1, require_fat=False)
        if not ok:
            return _reject(msg)
        set_op_progress(0.2, "A formatar o cartão (pode demorar)…")
        success, msg = format_sd_card(mount_path)
        op_sink(msg)
        if success:
            set_op_progress(1.0, "Formatação concluída.")
        return _api_result(success, msg)


def start_app():
    index_path = os.path.join(BASE_DIR, "static", "index.html")
    api = Api()

    print("\n=======================================================")
    print(f"  Route 1 Kit {__version__} — App Desktop")
    print("  Feche a janela para encerrar.")
    print("=======================================================\n")
    add_log(f"Route 1 Kit {__version__} iniciado (pywebview).")

    icon_path = None
    for candidate in ("app-icon-512.png", "app-icon-256.png", "app-icon.png"):
        path = os.path.join(BASE_DIR, "static", "assets", candidate)
        if os.path.isfile(path):
            icon_path = path
            break

    # Mesma cor do tema padrão (Studio Escuro, --c-bg) para não piscar branco
    # antes do HTML carregar.
    window = webview.create_window(
        "Route 1 Kit",
        url=index_path,
        js_api=api,
        width=1100,
        height=800,
        min_size=(900, 600),
        background_color="#0F1116",
    )

    def on_closing():
        # Threads js_api não são daemon: fechar a meio de uma op deixa o processo
        # vivo (e o cartão a meio). Cancelar o fecho até a op terminar.
        if OP_LOCK.locked():
            add_log(
                "⚠️ Operação em andamento — aguarde terminar antes de fechar a janela."
            )
            return False
        return True

    window.events.closing += on_closing
    webview.start(icon=icon_path)


if __name__ == "__main__":
    # Necessário em builds Windows (PyInstaller) para evitar reentrada do bootloader.
    if sys.platform.startswith("win"):
        import multiprocessing

        multiprocessing.freeze_support()
    start_app()
