#!/usr/bin/env python3
"""
Route 1 Kit — App desktop multiplataforma (pywebview + HTML/CSS/JS).
"""

import json
import os
import sys
import threading
import webbrowser
from collections import deque
from functools import wraps

import webview

def _resolve_base_dir():
    """Raiz do app: pasta do fonte, ou _MEIPASS quando empacotado (PyInstaller)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _resolve_base_dir()
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core import __version__
from core.about import build_about_payload, is_allowed_external_url
from core.artwork import (
    fetch_rom_artwork as do_fetch_rom_artwork,
    generate_twilight_artwork_batch as do_generate_twilight_artwork_batch,
    install_boxarts as do_install_boxarts,
)
from core.cleaner import backup_drive, clean_macos_metadata
from core.disks import format_sd_card, get_mounted_drives, is_safe_mount_path
from core.exploits import setup_nand_backup_stage, setup_unlaunch_stage
from core.homebrew_catalog import build_catalog_payload
from core.inspect_sd import inspect_sd_card, quarantine_dcim as do_quarantine_dcim
from core.privacy import expand_user_path, redact_path, redact_text
from core.rom_cleaner import normalize_layout, organize_roms_directory
from core.rom_manager import (
    browse_roms as do_browse_roms,
    default_saves_backup_dir,
    delete_roms as do_delete_roms,
    import_roms as do_import_roms,
    list_rom_dir as do_list_rom_dir,
    list_rom_tree as do_list_rom_tree,
    list_roms as do_list_roms,
    mkdir_rom_dir as do_mkdir_rom_dir,
    move_roms as do_move_roms,
    normalize_save_mode,
    rom_details as do_rom_details,
    set_rom_artwork as do_set_rom_artwork,
)
from core.sd_utils import (
    copy_nand_backup as do_copy_nand_backup,
    format_sd_report as do_sd_report,
    install_cheats as do_install_cheats,
    install_homebrew as do_install_homebrew,
    setup_godmode9i as do_setup_godmode9i,
)
from core.sdio import preflight
from core.dspico import (
    browse_dspico_games as do_browse_dspico_games,
    delete_dspico_games as do_delete_dspico_games,
    ensure_emunand_skeleton as do_ensure_emunand_skeleton,
    flash_dspico_firmware as do_flash_dspico_firmware,
    get_dspico_settings as do_get_dspico_settings,
    import_biosnds7 as do_import_biosnds7,
    import_dspico_games as do_import_dspico_games,
    import_twl_font as do_import_twl_font,
    install_dspico_package,
    inspect_dspico as do_inspect_dspico,
    is_rp2_volume,
    list_rp2_volumes as do_list_rp2_volumes,
    mkdir_dspico_games as do_mkdir_dspico_games,
    move_dspico_games as do_move_dspico_games,
    normalize_dspico_layout,
    official_links as dspico_official_links,
    organize_dspico_sd as do_organize_dspico_sd,
    set_dspico_settings as do_set_dspico_settings,
)
from core.dspico_emulators import (
    install_dspico_emulators as do_install_dspico_emulators,
    list_emulators as do_list_dspico_emulators,
)
from core.cache import dspico_firmware_uf2_ready
from core.hiya import install_hiya_cfw
from core.pico_artwork import (
    apply_dspico_artwork_url as do_apply_dspico_artwork_url,
    get_dspico_game_artwork as do_get_dspico_game_artwork,
    search_dspico_artwork as do_search_dspico_artwork,
    set_dspico_artwork_file as do_set_dspico_artwork_file,
)
from core.twilight import install_gei_kernel, install_r4_kernel, probe_kernels

LOG_MAX = 500
SYSTEM_LOGS = deque(maxlen=LOG_MAX)
LOG_LOCK = threading.Lock()
OP_LOCK = threading.Lock()
_LOG_SEQ = 0

# Fronteira UI↔Python: rejeitar tipos inesperados.
_TRUE_LITERALS = frozenset({"1", "true", "yes", "on"})
_FALSE_LITERALS = frozenset({"0", "false", "no", "off", ""})


def add_log(msg):
    global _LOG_SEQ
    safe_msg = redact_text(msg)
    with LOG_LOCK:
        _LOG_SEQ += 1
        SYSTEM_LOGS.append({"id": _LOG_SEQ, "msg": safe_msg})
    try:
        from services import web_events

        web_events.emit("log", {"message": safe_msg})
    except ImportError:
        pass
    except Exception:
        pass


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
            try:
                try:
                    from services import web_events

                    web_events.emit("busy", {"busy": True, "op": fn.__name__})
                except Exception:
                    pass
                # Preflight dentro do lock: evita I/O paralelo no cartão com outra op.
                if not skip_preflight:
                    ok, msg, _drive = preflight(mount_path, min_free_mb=min_free_mb)
                    if not ok:
                        return _reject(msg)
                return fn(self, mount_path, *args, **kwargs)
            except Exception as e:
                add_log(f"❌ Erro na operação: {redact_text(e)}")
                return _reject(e)
            finally:
                try:
                    from services import web_events

                    web_events.emit("busy", {"busy": False, "op": fn.__name__})
                except Exception:
                    pass
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
    """Fachada de domínio para a UI nativa (e testes)."""

    def __init__(self):
        self._picker = None

    def set_file_picker(self, picker):
        """Injecta FilePickerPort (diálogos nativos Qt)."""
        self._picker = picker

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

    def get_about(self):
        """Metadados da tela Sobre + última entrada do CHANGELOG.md."""
        try:
            return build_about_payload(BASE_DIR)
        except Exception as e:
            return _reject(e)

    def open_external_url(self, url):
        """Abre URL allowlisted no browser do sistema (Sobre / GameBrew)."""
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
        try:
            return inspect_sd_card(mount_path)
        except Exception as e:
            return _reject(e)
        finally:
            OP_LOCK.release()

    def probe_kernels(self):
        try:
            return probe_kernels()
        except Exception as e:
            return {
                "success": False,
                "error": redact_text(e),
                "gei": None,
                "r4": [],
            }

    @_run_mount_op(min_free_mb=1)
    def quarantine_dcim(self, mount_path):
        success, msg = do_quarantine_dcim(mount_path, log_callback=add_log)
        return _api_result(success, msg)

    @_run_mount_op(min_free_mb=8)
    def setup_nand_dump(self, mount_path, has_facebook=True):
        flag, err = _as_bool(has_facebook, default=True)
        if err:
            return _reject(err)
        setup_nand_backup_stage(
            mount_path,
            has_facebook=flag,
            log_callback=add_log,
        )
        return {
            "success": True,
            "message": "Etapa 1 (Memory Pit + dumpTool) configurada com sucesso!",
        }

    @_run_mount_op(min_free_mb=64)
    def setup_unlaunch(self, mount_path):
        setup_unlaunch_stage(mount_path, log_callback=add_log)
        return {
            "success": True,
            "message": "Etapa 2 (TWiLight Menu++ & Unlaunch) configurada com sucesso!",
        }

    @_run_mount_op(min_free_mb=8)
    def setup_gei(self, mount_path):
        success, msg = install_gei_kernel(mount_path, log_callback=add_log)
        return _api_result(success, msg)

    @_run_mount_op(min_free_mb=8)
    def setup_dspico(self, mount_path):
        success, msg = install_dspico_package(mount_path, log_callback=add_log)
        return _api_result(success, msg)

    def get_dspico_official_links(self):
        """URLs oficiais LNH (só allowlist)."""
        return {"success": True, "links": dspico_official_links()}

    def inspect_dspico(self, mount_path):
        """Checklist / estado do microSD DSPico (leitura sob OP_LOCK)."""
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
        try:
            return do_inspect_dspico(mount_path)
        except Exception as e:
            return _reject(e)
        finally:
            OP_LOCK.release()

    def browse_dspico_games(self, mount_path, rel_dir=""):
        mount_path, err = _as_path_str(mount_path, label="caminho do cartão")
        if err:
            return _reject(err)
        if not is_safe_mount_path(mount_path):
            return _reject(
                "Unidade não reconhecida como volume removível/USB/SD."
            )
        if not OP_LOCK.acquire(blocking=False):
            return _reject("Outra operação já está em andamento. Aguarde.")
        try:
            rel = rel_dir if isinstance(rel_dir, str) else ""
            if "\x00" in rel:
                return _reject("Pasta inválida.")
            return do_browse_dspico_games(mount_path, rel)
        except Exception as e:
            return _reject(e)
        finally:
            OP_LOCK.release()

    @_run_mount_op(min_free_mb=8)
    def import_dspico_games(self, mount_path, host_paths=None, dest_rel_dir=""):
        if host_paths is None:
            host_paths = []
        if not isinstance(host_paths, (list, tuple)):
            return _reject("Lista de ficheiros inválida.")
        expanded = []
        for raw in host_paths:
            if not isinstance(raw, str):
                continue
            p, err = _as_path_str(raw, label="ficheiro")
            if err:
                continue
            expanded.append(expand_user_path(p) if p.startswith("~") else p)
        if not expanded:
            return _reject("Nenhum ficheiro válido seleccionado.")
        dest = dest_rel_dir if isinstance(dest_rel_dir, str) else ""
        if "\x00" in dest:
            return _reject("Destino inválido.")
        success, msg, stats = do_import_dspico_games(
            mount_path, expanded, dest_rel_dir=dest, log_callback=add_log
        )
        result = _api_result(success, msg)
        result["stats"] = stats or {}
        return result

    @_run_mount_op(min_free_mb=1)
    def delete_dspico_games(self, mount_path, rel_paths=None):
        if rel_paths is None:
            rel_paths = []
        if not isinstance(rel_paths, (list, tuple)):
            return _reject("Lista inválida.")
        cleaned = [p for p in rel_paths if isinstance(p, str) and p.strip()]
        success, msg, stats = do_delete_dspico_games(
            mount_path, cleaned, log_callback=add_log
        )
        result = _api_result(success, msg)
        result["stats"] = stats or {}
        return result

    @_run_mount_op(min_free_mb=1)
    def move_dspico_games(self, mount_path, rel_paths=None, dest_rel_dir=""):
        if rel_paths is None:
            rel_paths = []
        if not isinstance(rel_paths, (list, tuple)):
            return _reject("Lista inválida.")
        cleaned = [p for p in rel_paths if isinstance(p, str) and p.strip()]
        dest = dest_rel_dir if isinstance(dest_rel_dir, str) else ""
        if "\x00" in dest:
            return _reject("Destino inválido.")
        success, msg, stats = do_move_dspico_games(
            mount_path, cleaned, dest_rel_dir=dest, log_callback=add_log
        )
        result = _api_result(success, msg)
        result["stats"] = stats or {}
        return result

    @_run_mount_op(min_free_mb=4)
    def organize_dspico(self, mount_path, layout="games"):
        """Remove conteúdo de outros sistemas e organiza jogos no layout DSPico."""
        mode = normalize_dspico_layout(layout)
        if mode is None:
            return _reject(
                "Layout inválido. Use: franchise, platform, games ou root."
            )
        success, msg, stats = do_organize_dspico_sd(
            mount_path, layout=mode, log_callback=add_log
        )
        result = _api_result(success, msg)
        result["stats"] = stats or {}
        return result

    @_run_mount_op(min_free_mb=1)
    def mkdir_dspico_games(self, mount_path, parent_rel="", name=""):
        parent = parent_rel if isinstance(parent_rel, str) else ""
        folder = name if isinstance(name, str) else ""
        if "\x00" in parent or "\x00" in folder:
            return _reject("Nome inválido.")
        success, msg, stats = do_mkdir_dspico_games(
            mount_path, parent, folder, log_callback=add_log
        )
        result = _api_result(success, msg)
        result.update(stats or {})
        return result

    def get_dspico_game_artwork(self, mount_path, rel_path=""):
        """Estado actual de capa/ícone Pico Launcher para um jogo em Games/."""
        mount_path, err = _as_path_str(mount_path, label="caminho do cartão")
        if err:
            return _reject(err)
        if not is_safe_mount_path(mount_path):
            return _reject(
                "Unidade não reconhecida como volume removível/USB/SD."
            )
        rel, err = _as_path_str(rel_path, label="caminho do jogo")
        if err:
            return _reject(err)
        if "\x00" in rel:
            return _reject("Caminho do jogo inválido.")
        try:
            return do_get_dspico_game_artwork(
                mount_path, rel.replace("\\", "/").lstrip("/")
            )
        except Exception as e:
            return _reject(e)

    def search_dspico_artwork(
        self, mount_path, rel_path="", kind="cover", query=""
    ):
        """Pesquisa capas/ícones online (GameTDB + Libretro) com pré-visualizações.

        Só rede + leitura — não segura OP_LOCK (a gravação usa apply/set).
        """
        mount_path, err = _as_path_str(mount_path, label="caminho do cartão")
        if err:
            return _reject(err)
        if not is_safe_mount_path(mount_path):
            return _reject(
                "Unidade não reconhecida como volume removível/USB/SD."
            )
        rel, err = _as_path_str(rel_path, label="caminho do jogo")
        if err:
            return _reject(err)
        if "\x00" in rel:
            return _reject("Caminho do jogo inválido.")
        kind_s = kind if isinstance(kind, str) else "cover"
        q = query if isinstance(query, str) else ""
        if "\x00" in kind_s or "\x00" in q:
            return _reject("Parâmetros inválidos.")
        try:
            return do_search_dspico_artwork(
                mount_path,
                rel.replace("\\", "/").lstrip("/"),
                kind=kind_s.strip().lower(),
                query=q,
                log_callback=add_log,
            )
        except Exception as e:
            return _reject(e)

    @_run_mount_op(min_free_mb=1)
    def apply_dspico_artwork_url(
        self, mount_path, rel_path="", kind="cover", url=""
    ):
        """Aplica capa/ícone a partir de URL allowlisted (converte para BMP Pico)."""
        rel, err = _as_path_str(rel_path, label="caminho do jogo")
        if err:
            return _reject(err)
        if "\x00" in rel:
            return _reject("Caminho do jogo inválido.")
        kind_s, err = _as_path_str(kind, label="tipo de arte")
        if err:
            return _reject(err)
        url_s, err = _as_path_str(url, label="URL")
        if err:
            return _reject(err)
        success, msg, stats = do_apply_dspico_artwork_url(
            mount_path,
            rel.replace("\\", "/").lstrip("/"),
            kind_s.strip().lower(),
            url_s.strip(),
            log_callback=add_log,
        )
        result = _api_result(success, msg)
        result["stats"] = stats or {}
        return result

    @_run_mount_op(min_free_mb=1)
    def set_dspico_artwork(self, mount_path, rel_path="", kind="cover", source_path=""):
        """Grava capa/ícone Pico a partir de PNG/BMP local."""
        rel, err = _as_path_str(rel_path, label="caminho do jogo")
        if err:
            return _reject(err)
        if "\x00" in rel:
            return _reject("Caminho do jogo inválido.")
        kind_s, err = _as_path_str(kind, label="tipo de arte")
        if err:
            return _reject(err)
        src, err = _as_path_str(source_path, label="imagem")
        if err:
            return _reject(err)
        src = expand_user_path(src) if src.startswith("~") else src
        success, msg, stats = do_set_dspico_artwork_file(
            mount_path,
            rel.replace("\\", "/").lstrip("/"),
            kind_s.strip().lower(),
            src,
            log_callback=add_log,
        )
        result = _api_result(success, msg)
        result["stats"] = stats or {}
        return result

    @_run_mount_op(min_free_mb=1)
    def ensure_dspico_emunand(self, mount_path):
        success, msg, stats = do_ensure_emunand_skeleton(
            mount_path, log_callback=add_log
        )
        result = _api_result(success, msg)
        result["checklist"] = stats or {}
        return result

    def pick_dspico_bios_file(self):
        """Escolher dump local biosnds7.rom (não descarrega da rede)."""
        if self._picker is None:
            return _reject("Diálogo de ficheiros indisponível.")
        try:
            cancelled, paths = self._picker.open_files(
                caption="BIOS ARM7",
                filters=("BIOS ARM7 (*.rom *.bin)", "Todos os ficheiros (*.*)"),
                multiple=False,
            )
        except Exception as e:
            return _reject(e)
        if cancelled or not paths:
            return {"success": True, "cancelled": True, "path": ""}
        return {
            "success": True,
            "cancelled": False,
            "path": redact_path(paths[0]),
        }

    def pick_dspico_font_file(self):
        """Escolher TWLFontTable.dat local."""
        if self._picker is None:
            return _reject("Diálogo de ficheiros indisponível.")
        try:
            cancelled, paths = self._picker.open_files(
                caption="TWLFontTable",
                filters=("TWLFontTable (*.dat)", "Todos os ficheiros (*.*)"),
                multiple=False,
            )
        except Exception as e:
            return _reject(e)
        if cancelled or not paths:
            return {"success": True, "cancelled": True, "path": ""}
        return {
            "success": True,
            "cancelled": False,
            "path": redact_path(paths[0]),
        }

    @_run_mount_op(min_free_mb=1)
    def import_dspico_bios(self, mount_path, source_path=""):
        source_path, err = _as_path_str(source_path, label="caminho do BIOS")
        if err:
            return _reject(err)
        src = expand_user_path(source_path) if source_path.startswith("~") else source_path
        success, msg = do_import_biosnds7(mount_path, src, log_callback=add_log)
        return _api_result(success, msg)

    @_run_mount_op(min_free_mb=1)
    def import_dspico_twl_font(self, mount_path, source_path=""):
        source_path, err = _as_path_str(source_path, label="caminho da fonte")
        if err:
            return _reject(err)
        src = expand_user_path(source_path) if source_path.startswith("~") else source_path
        success, msg = do_import_twl_font(mount_path, src, log_callback=add_log)
        return _api_result(success, msg)

    def get_dspico_settings(self, mount_path):
        mount_path, err = _as_path_str(mount_path, label="caminho do cartão")
        if err:
            return _reject(err)
        if not is_safe_mount_path(mount_path):
            return _reject(
                "Unidade não reconhecida como volume removível/USB/SD."
            )
        if not OP_LOCK.acquire(blocking=False):
            return _reject("Outra operação já está em andamento. Aguarde.")
        try:
            return do_get_dspico_settings(mount_path)
        except Exception as e:
            return _reject(e)
        finally:
            OP_LOCK.release()

    @_run_mount_op(min_free_mb=1)
    def set_dspico_settings(self, mount_path, patch=None):
        if patch is None:
            patch = {}
        if not isinstance(patch, dict):
            return _reject("Patch de settings inválido.")
        success, msg = do_set_dspico_settings(
            mount_path, patch, log_callback=add_log
        )
        return _api_result(success, msg)

    def list_dspico_emulators(self):
        """Catálogo de emuladores Pico-Launcher (pins SHA-256)."""
        try:
            return do_list_dspico_emulators()
        except Exception as e:
            return _reject(e)

    @_run_mount_op(min_free_mb=16)
    def install_dspico_emulators(self, mount_path, emulator_ids=None):
        if emulator_ids is None:
            emulator_ids = []
        if not isinstance(emulator_ids, (list, tuple)):
            return _reject("Lista de emuladores inválida.")
        clean_ids = []
        for raw in emulator_ids:
            if not isinstance(raw, str):
                continue
            eid = raw.strip()
            if not eid or "\x00" in eid:
                continue
            clean_ids.append(eid)
        if not clean_ids:
            return _reject("Seleccione pelo menos um emulador.")
        success, msg, details = do_install_dspico_emulators(
            mount_path, clean_ids, log_callback=add_log
        )
        result = _api_result(success, msg)
        if isinstance(details, dict):
            result.update(details)
        return result

    def list_rp2_volumes(self):
        """Volumes BOOTSEL RPI-RP2 (não é SD do cartucho)."""
        if not OP_LOCK.acquire(blocking=False):
            return _reject("Outra operação já está em andamento. Aguarde.")
        try:
            vols = do_list_rp2_volumes()
            return {
                "success": True,
                "volumes": vols,
                "firmware_uf2_ready": dspico_firmware_uf2_ready(),
            }
        except Exception as e:
            return _reject(e)
        finally:
            OP_LOCK.release()

    def flash_dspico_firmware(self, rp2_mount_path):
        """Grava UF2 oficial LNH no RPI-RP2 — sem path de ficheiro da UI."""
        rp2_mount_path, err = _as_path_str(
            rp2_mount_path, label="caminho do volume RPI-RP2"
        )
        if err:
            return _reject(err)
        if not is_rp2_volume(rp2_mount_path):
            return _reject("Volume não reconhecido como RPI-RP2 (BOOTSEL).")
        if not OP_LOCK.acquire(blocking=False):
            return _reject("Outra operação já está em andamento. Aguarde.")
        try:
            success, msg = do_flash_dspico_firmware(
                rp2_mount_path, log_callback=add_log
            )
            return _api_result(success, msg)
        except Exception as e:
            return _reject(e)
        finally:
            OP_LOCK.release()

    def pick_dspico_rom_files(self):
        """Diálogo para ROMs DSPico (.nds/.dsi/.ids)."""
        if self._picker is None:
            return _reject("Diálogo de ficheiros indisponível.")
        try:
            cancelled, paths = self._picker.open_files(
                caption="ROMs DSPico",
                filters=("ROMs DS/DSi (*.nds *.dsi *.ids)", "Todos os ficheiros (*.*)"),
                multiple=True,
            )
        except Exception as e:
            return _reject(e)
        if cancelled or not paths:
            return {"success": True, "cancelled": True, "paths": []}
        return {
            "success": True,
            "cancelled": False,
            "paths": [redact_path(p) for p in paths],
        }

    @_run_mount_op(min_free_mb=512)
    def setup_hiya(self, mount_path, nand_path="", update_only=False):
        nand_path, err = _as_path_str(nand_path, label="caminho do nand.bin") if nand_path else ("", None)
        if err:
            return _reject(err)
        # nand_path opcional: string vazia = auto-detectar no cartão
        if nand_path is None:
            nand_path = ""
        flag, err = _as_bool(update_only, default=False)
        if err:
            return _reject(err)
        success, msg = install_hiya_cfw(
            mount_path,
            nand_path=nand_path or "",
            update_only=flag,
            log_callback=add_log,
        )
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
            mount_path, source_dir, log_callback=add_log
        )
        return _api_result(success, msg)

    @_run_mount_op(min_free_mb=4)
    def organize_roms(self, mount_path, layout="console"):
        mode = normalize_layout(layout)
        if mode is None:
            return _reject(
                "Layout inválido. Use: console, franchise ou both."
            )
        success, msg = organize_roms_directory(
            mount_path, log_callback=add_log, layout=mode
        )
        return _api_result(success, msg)

    def list_roms(self, mount_path):
        """Lista jogos/apps em /roms/ (leitura; OP_LOCK)."""
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
        try:
            return do_list_roms(mount_path)
        except Exception as e:
            return _reject(e)
        finally:
            OP_LOCK.release()

    def list_rom_dir(self, mount_path, rel_dir=""):
        """Lista pastas + ROMs num nível sob /roms/."""
        mount_path, err = _as_path_str(mount_path, label="caminho do cartão")
        if err:
            return _reject(err)
        if not is_safe_mount_path(mount_path):
            return _reject(
                "Unidade não reconhecida como volume removível/USB/SD. "
                "Atualize a lista e selecione o cartão novamente."
            )
        if rel_dir is None:
            rel_dir = ""
        if not isinstance(rel_dir, str):
            return _reject("Pasta relativa inválida.")
        if "\x00" in rel_dir:
            return _reject("Pasta relativa inválida.")
        if not OP_LOCK.acquire(blocking=False):
            return _reject("Outra operação já está em andamento. Aguarde.")
        try:
            return do_list_rom_dir(mount_path, rel_dir)
        except Exception as e:
            return _reject(e)
        finally:
            OP_LOCK.release()

    def list_rom_tree(self, mount_path):
        """Árvore de pastas sob /roms/."""
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
        try:
            return do_list_rom_tree(mount_path)
        except Exception as e:
            return _reject(e)
        finally:
            OP_LOCK.release()

    def browse_roms(self, mount_path, rel_dir=""):
        """Pasta actual + árvore numa só aquisição de OP_LOCK (evita falso 'em andamento')."""
        mount_path, err = _as_path_str(mount_path, label="caminho do cartão")
        if err:
            return _reject(err)
        if not is_safe_mount_path(mount_path):
            return _reject(
                "Unidade não reconhecida como volume removível/USB/SD. "
                "Atualize a lista e selecione o cartão novamente."
            )
        if rel_dir is None:
            rel_dir = ""
        if not isinstance(rel_dir, str) or "\x00" in rel_dir:
            return _reject("Pasta relativa inválida.")
        if not OP_LOCK.acquire(blocking=False):
            return _reject("Outra operação já está em andamento. Aguarde.")
        try:
            return do_browse_roms(mount_path, rel_dir)
        except Exception as e:
            return _reject(e)
        finally:
            OP_LOCK.release()

    def rom_details(self, mount_path, rel_path=""):
        """Detalhes de um jogo (capa, ícone, como corre) — leitura sob OP_LOCK."""
        mount_path, err = _as_path_str(mount_path, label="caminho do cartão")
        if err:
            return _reject(err)
        if not is_safe_mount_path(mount_path):
            return _reject(
                "Unidade não reconhecida como volume removível/USB/SD. "
                "Atualize a lista e selecione o cartão novamente."
            )
        rel, err = _as_path_str(rel_path, label="caminho do jogo")
        if err:
            return _reject(err)
        if "\x00" in rel:
            return _reject("Caminho do jogo inválido.")
        if not OP_LOCK.acquire(blocking=False):
            return _reject("Outra operação já está em andamento. Aguarde.")
        try:
            return do_rom_details(mount_path, rel.replace("\\", "/").lstrip("/"))
        except Exception as e:
            return _reject(e)
        finally:
            OP_LOCK.release()

    @_run_mount_op(min_free_mb=1)
    def set_rom_artwork(self, mount_path, rel_path="", kind="boxart", source_path=""):
        """Grava capa ou ícone PNG no TWiLight (boxart/icons)."""
        rel, err = _as_path_str(rel_path, label="caminho do jogo")
        if err:
            return _reject(err)
        if "\x00" in rel:
            return _reject("Caminho do jogo inválido.")
        kind_s, err = _as_path_str(kind, label="tipo de arte")
        if err:
            return _reject(err)
        src, err = _as_path_str(source_path, label="imagem")
        if err:
            return _reject(err)
        src = expand_user_path(src) if src.startswith("~") else src
        success, msg, stats = do_set_rom_artwork(
            mount_path,
            rel.replace("\\", "/").lstrip("/"),
            kind_s.strip().lower(),
            src,
            log_callback=add_log,
        )
        result = _api_result(success, msg)
        result["stats"] = stats or {}
        return result

    def pick_image_file(self):
        """Diálogo para escolher PNG/BMP (capa/ícone TWiLight ou DSPico)."""
        if self._picker is None:
            return _reject("Diálogo de ficheiros indisponível.")
        try:
            cancelled, paths = self._picker.open_files(
                caption="Imagem",
                filters=(
                    "Imagens (*.png *.bmp)",
                    "PNG (*.png)",
                    "BMP (*.bmp)",
                    "Todos os ficheiros (*.*)",
                ),
                multiple=False,
            )
        except Exception as e:
            return _reject(e)
        if cancelled or not paths:
            return {"success": True, "cancelled": True, "path": ""}
        return {
            "success": True,
            "cancelled": False,
            "path": redact_path(paths[0]),
        }

    @_run_mount_op(min_free_mb=1)
    def mkdir_rom_dir(self, mount_path, parent_rel="", name=""):
        parent = parent_rel if isinstance(parent_rel, str) else ""
        if "\x00" in parent:
            return _reject("Pasta pai inválida.")
        folder, err = _as_path_str(name, label="nome da pasta")
        if err:
            return _reject(err)
        success, msg, stats = do_mkdir_rom_dir(
            mount_path, parent, folder, log_callback=add_log
        )
        result = _api_result(success, msg)
        result["stats"] = stats or {}
        return result

    @_run_mount_op(min_free_mb=1)
    def move_roms(self, mount_path, rel_paths=None, dest_rel_dir=""):
        if rel_paths is None:
            rel_paths = []
        if not isinstance(rel_paths, (list, tuple)):
            return _reject("Lista de jogos inválida.")
        cleaned = []
        for raw in rel_paths:
            if not isinstance(raw, str):
                continue
            p, err = _as_path_str(raw, label="caminho relativo")
            if err:
                continue
            cleaned.append(p.replace("\\", "/").lstrip("/"))
        if not cleaned:
            return _reject("Nenhum jogo seleccionado.")
        dest = dest_rel_dir if isinstance(dest_rel_dir, str) else ""
        if "\x00" in dest:
            return _reject("Destino inválido.")
        success, msg, stats = do_move_roms(
            mount_path, cleaned, dest_rel_dir=dest, log_callback=add_log
        )
        result = _api_result(success, msg)
        result["stats"] = stats or {}
        return result

    def pick_rom_files(self):
        """Diálogo multi-ficheiro para escolher ROMs no computador."""
        if self._picker is None:
            return _reject("Diálogo de ficheiros indisponível.")
        try:
            cancelled, paths = self._picker.open_files(
                caption="Importar ROMs",
                filters=(
                    "ROMs (*.nds *.dsi *.ids *.gba *.gb *.gbc *.nes *.sfc *.smc "
                    "*.md *.gen *.sms *.gg *.pce *.col *.a26 *.ws *.ngp)",
                    "Todos os ficheiros (*.*)",
                ),
                multiple=True,
            )
        except Exception as e:
            return _reject(e)
        if cancelled or not paths:
            return {"success": True, "cancelled": True, "paths": []}
        return {
            "success": True,
            "cancelled": False,
            "paths": [redact_path(p) for p in paths],
        }

    def pick_folder(self):
        """Diálogo para escolher pasta (ex.: backup de saves)."""
        if self._picker is None:
            return _reject("Diálogo de pastas indisponível.")
        try:
            cancelled, folder = self._picker.open_folder(caption="Escolher pasta")
        except Exception as e:
            return _reject(e)
        if cancelled or not folder:
            return {"success": True, "cancelled": True, "path": ""}
        return {
            "success": True,
            "cancelled": False,
            "path": redact_path(folder),
        }

    def default_saves_backup_dir(self):
        """Pasta padrão sugerida para backup de saves (redigida)."""
        try:
            return {
                "success": True,
                "path": redact_path(default_saves_backup_dir()),
            }
        except Exception as e:
            return _reject(e)

    @_run_mount_op(min_free_mb=8)
    def import_roms(self, mount_path, host_paths=None, layout="console", dest_rel_dir=""):
        mode = normalize_layout(layout)
        if mode is None:
            return _reject("Layout inválido. Use: console, franchise ou both.")
        if host_paths is None:
            host_paths = []
        if not isinstance(host_paths, (list, tuple)):
            return _reject("Lista de ficheiros inválida.")
        expanded = []
        for raw in host_paths:
            if not isinstance(raw, str):
                continue
            p, err = _as_path_str(raw, label="ficheiro")
            if err:
                continue
            expanded.append(expand_user_path(p) if p.startswith("~") else p)
        if not expanded:
            return _reject("Nenhum ficheiro válido seleccionado.")
        dest = dest_rel_dir if isinstance(dest_rel_dir, str) else ""
        if "\x00" in dest:
            return _reject("Destino inválido.")
        success, msg, stats = do_import_roms(
            mount_path,
            expanded,
            layout=mode,
            dest_rel_dir=dest,
            log_callback=add_log,
        )
        result = _api_result(success, msg)
        result["stats"] = stats or {}
        return result

    @_run_mount_op(min_free_mb=1)
    def delete_roms(
        self,
        mount_path,
        rel_paths=None,
        save_mode="delete",
        backup_dir="",
        remove_boxart=True,
    ):
        mode = normalize_save_mode(save_mode)
        if mode is None:
            return _reject("Modo de save inválido. Use: delete, backup ou keep.")
        if rel_paths is None:
            rel_paths = []
        if not isinstance(rel_paths, (list, tuple)):
            return _reject("Lista de jogos inválida.")
        cleaned_rels = []
        for raw in rel_paths:
            if not isinstance(raw, str):
                continue
            p, err = _as_path_str(raw, label="caminho relativo")
            if err:
                continue
            cleaned_rels.append(p.replace("\\", "/").lstrip("/"))
        if not cleaned_rels:
            return _reject("Nenhum jogo seleccionado.")

        backup = ""
        if mode == "backup":
            if backup_dir:
                backup, err = _as_path_str(backup_dir, label="pasta de backup")
                if err:
                    return _reject(err)
                backup = expand_user_path(backup) if backup.startswith("~") else backup
            else:
                backup = default_saves_backup_dir()

        flag, err = _as_bool(remove_boxart, default=True)
        if err:
            return _reject(err)

        success, msg, stats = do_delete_roms(
            mount_path,
            cleaned_rels,
            save_mode=mode,
            backup_dir=backup,
            remove_boxart=flag,
            log_callback=add_log,
        )
        result = _api_result(success, msg)
        result["stats"] = stats or {}
        return result

    @_run_mount_op(min_free_mb=1)
    def sd_report(self, mount_path):
        success, msg = do_sd_report(mount_path, log_callback=add_log)
        return _api_result(success, msg)

    @_run_mount_op(min_free_mb=4)
    def setup_godmode9i(self, mount_path):
        success, msg = do_setup_godmode9i(mount_path, log_callback=add_log)
        return _api_result(success, msg)

    @_run_mount_op(min_free_mb=16)
    def install_homebrew(self, mount_path, app_id):
        app_id, err = _as_path_str(app_id, label="aplicação")
        if err:
            return _reject(err)
        success, msg = do_install_homebrew(
            mount_path, app_id, log_callback=add_log
        )
        return _api_result(success, msg)

    @_run_mount_op(min_free_mb=64)
    def install_cheats(self, mount_path):
        success, msg = do_install_cheats(mount_path, log_callback=add_log)
        return _api_result(success, msg)

    @_run_mount_op(min_free_mb=1)
    def copy_nand_backup(self, mount_path):
        success, msg = do_copy_nand_backup(mount_path, log_callback=add_log)
        return _api_result(success, msg)

    @_run_mount_op(min_free_mb=32)
    def install_boxarts(self, mount_path):
        success, msg = do_install_boxarts(mount_path, log_callback=add_log)
        return _api_result(success, msg)

    @_run_mount_op(min_free_mb=2)
    def fetch_rom_artwork(self, mount_path, rel_path=""):
        """Descarrega capa/ícone (GameTDB ou Libretro) para um jogo em /roms/."""
        rel, err = _as_path_str(rel_path, label="caminho do jogo")
        if err:
            return _reject(err)
        if "\x00" in rel:
            return _reject("Caminho do jogo inválido.")
        success, msg, stats = do_fetch_rom_artwork(
            mount_path,
            rel.replace("\\", "/").lstrip("/"),
            log_callback=add_log,
        )
        result = _api_result(success, msg)
        result["stats"] = stats or {}
        return result

    @_run_mount_op(min_free_mb=1)
    def backup(self, mount_path):
        success, path = backup_drive(mount_path, log_callback=add_log)
        shown = redact_path(path) if path else path
        if success:
            return {"success": True, "message": f"Backup salvo em: {shown}"}
        return {
            "success": False,
            "error": f"Backup incompleto ou falhou. Pasta parcial: {shown}",
        }

    @_run_mount_op(min_free_mb=1)
    def clean_sd(self, mount_path):
        success, msg = clean_macos_metadata(mount_path, log_callback=add_log)
        out = _api_result(success, msg)
        # clean_sd historicamente devolve message também em falha
        if not success:
            out["message"] = out.get("error")
        return out

    @_run_mount_op(min_free_mb=1, skip_preflight=True)
    def format_sd(self, mount_path):
        # Formatação: não exigir FAT no preflight (o objetivo é converter para FAT32).
        # Ainda valida removível via is_safe_mount_path no decorator e format_sd_card.
        add_log(f"Formatando unidade {mount_path} em FAT32 (cluster 32 KB)...")
        if sys.platform == "darwin":
            add_log(
                "No macOS, pode abrir uma janela do Terminal para confirmares "
                "a palavra-passe do sudo (cluster 32 KB)."
            )
        ok, msg, _drive = preflight(mount_path, min_free_mb=1, require_fat=False)
        if not ok:
            return _reject(msg)
        success, msg = format_sd_card(mount_path)
        add_log(msg)
        return _api_result(success, msg)

    # --- Actualizações DSPico / Utilidades / prefs --------------------------

    def check_dspico_updates(self, mount_path=""):
        from core.updates import check_dspico_updates as _check

        path = ""
        if isinstance(mount_path, str) and mount_path.strip():
            path, err = _as_path_str(mount_path, label="caminho do cartão")
            if err:
                return _reject(err)
        try:
            return _check(path or "", log_callback=add_log)
        except Exception as e:
            return _reject(e)

    @_run_mount_op(min_free_mb=8)
    def install_dspico_component(self, mount_path, component, channel="pinned"):
        from core.updates import install_dspico_component as _install

        if not isinstance(component, str) or not component.strip():
            return _reject("Componente inválido.")
        if not isinstance(channel, str) or channel.strip().lower() not in (
            "pinned",
            "latest",
        ):
            return _reject("Canal inválido (pinned ou latest).")
        return _install(
            mount_path,
            component.strip(),
            channel.strip().lower(),
            log_callback=add_log,
        )

    @_run_mount_op(min_free_mb=4)
    def install_dspico_usb_apps(self, mount_path):
        from core.updates import install_dspico_component as _install

        return _install(
            mount_path,
            "dspico-usb-examples",
            "latest",
            log_callback=add_log,
        )

    def list_pico_themes(self, mount_path):
        from core.pico_themes import list_pico_themes as _list

        path, err = _as_path_str(mount_path, label="caminho do cartão")
        if err:
            return _reject(err)
        if not is_safe_mount_path(path):
            return _reject("Unidade não reconhecida como volume removível/USB/SD.")
        try:
            res = _list(path)
            if res.get("success") and "active" not in res:
                res["active"] = res.get("active_theme") or ""
            return res
        except Exception as e:
            return _reject(e)

    @_run_mount_op(min_free_mb=1)
    def set_pico_theme(self, mount_path, theme_folder):
        from core.pico_themes import set_pico_theme as _set

        if not isinstance(theme_folder, str) or not theme_folder.strip():
            return _reject("Pasta de tema inválida.")
        ok, msg, stats = _set(mount_path, theme_folder.strip())
        out = _api_result(ok, msg)
        out.update(stats or {})
        return out

    @_run_mount_op(min_free_mb=2)
    def import_pico_theme(self, mount_path, source_path):
        from core.pico_themes import import_pico_theme as _import

        src, err = _as_path_str(source_path, label="fonte do tema")
        if err:
            return _reject(err)
        src = expand_user_path(src) if src.startswith("~") else src
        ok, msg, stats = _import(mount_path, src)
        out = _api_result(ok, msg)
        out.update(stats or {})
        return out

    @_run_mount_op(min_free_mb=1)
    def create_pico_material_theme(
        self, mount_path, name, r=109, g=139, b=255, dark=True
    ):
        from core.pico_themes import create_pico_material_theme as _create

        if not isinstance(name, str) or not name.strip():
            return _reject("Nome do tema inválido.")
        dark_b, err = _as_bool(dark, default=True)
        if err:
            return _reject(err)
        try:
            ri, gi, bi = int(r), int(g), int(b)
        except (TypeError, ValueError):
            return _reject("Cor RGB inválida.")
        ok, msg, stats = _create(mount_path, name.strip(), ri, gi, bi, dark=bool(dark_b))
        out = _api_result(ok, msg)
        out.update(stats or {})
        return out

    @_run_mount_op(min_free_mb=8)
    def generate_dspico_artwork_batch(self, mount_path):
        """Lote isolado DSPico: capas + ícones Pico (BMP) com missing[]."""
        from core.pico_artwork import generate_dspico_artwork_batch as _batch

        return _batch(mount_path, log_callback=add_log)

    @_run_mount_op(min_free_mb=8)
    def generate_dspico_covers_batch(self, mount_path):
        """Alias compatível — mesma implementação que generate_dspico_artwork_batch."""
        from core.pico_artwork import generate_dspico_artwork_batch as _batch

        return _batch(mount_path, log_callback=add_log)

    @_run_mount_op(min_free_mb=8)
    def generate_twilight_artwork_batch(self, mount_path):
        """Lote isolado TWiLight: boxart + ícones PNG com missing[]."""
        return do_generate_twilight_artwork_batch(mount_path, log_callback=add_log)

    def get_prefs(self):
        path = os.path.join(_user_data_dir(), "prefs.json")
        try:
            if not os.path.isfile(path):
                return {"success": True, "prefs": {}}
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {"success": True, "prefs": {}}
            return {"success": True, "prefs": data}
        except Exception as e:
            return _reject(e)

    def set_prefs(self, prefs):
        if not isinstance(prefs, dict):
            return _reject("Preferências inválidas.")
        # Allowlist superficial — UI só grava chaves simples.
        clean = {}
        for k, v in list(prefs.items())[:64]:
            if not isinstance(k, str) or len(k) > 64:
                continue
            if isinstance(v, (str, int, float, bool)) or v is None:
                if isinstance(v, str) and len(v) > 2048:
                    continue
                clean[k] = v
        path = os.path.join(_user_data_dir(), "prefs.json")
        partial = path + ".partial"
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(partial, "w", encoding="utf-8") as f:
                json.dump(clean, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(partial, path)
            return {"success": True, "prefs": clean}
        except Exception as e:
            try:
                if os.path.isfile(partial):
                    os.remove(partial)
            except OSError:
                pass
            return _reject(e)


def _user_data_dir() -> str:
    """Pasta de dados do utilizador (localStorage / prefs)."""
    if sys.platform == "darwin":
        root = os.path.expanduser("~/Library/Application Support/Route1Kit")
    elif sys.platform.startswith("win"):
        root = os.path.join(
            os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"),
            "Route1Kit",
        )
    else:
        root = os.path.join(
            os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"),
            "Route1Kit",
        )
    try:
        os.makedirs(root, exist_ok=True)
    except OSError:
        pass
    return root


def start_app():
    from services import web_events
    from services.file_picker import FilePickerPort

    index_path = os.path.join(BASE_DIR, "static", "index.html")
    api = Api()
    picker = FilePickerPort()
    api.set_file_picker(picker)
    web_events.start()

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

    storage = _user_data_dir()
    # Mesma cor do tema padrão (Studio Escuro, --c-bg) para não piscar branco
    # antes do HTML carregar.
    window = webview.create_window(
        "Route 1 Kit",
        url=index_path,
        js_api=api,
        width=1180,
        height=820,
        min_size=(960, 640),
        background_color="#0F1116",
    )
    picker.set_window(window)

    def on_closing():
        # Threads js_api não são daemon: fechar a meio de uma op deixa o processo
        # vivo (e o cartão a meio). Cancelar o fecho até a op terminar.
        if OP_LOCK.locked():
            add_log(
                "⚠️ Operação em andamento — aguarde terminar antes de fechar a janela."
            )
            return False
        try:
            web_events.stop(timeout=0.5)
        except Exception:
            pass
        return True

    window.events.closing += on_closing
    try:
        webview.start(
            icon=icon_path,
            private_mode=False,
            storage_path=storage,
        )
    finally:
        try:
            web_events.stop(timeout=1.0)
        except Exception:
            pass


if __name__ == "__main__":
    # Necessário em builds Windows (PyInstaller) para evitar reentrada do bootloader.
    if sys.platform.startswith("win"):
        import multiprocessing

        multiprocessing.freeze_support()
    start_app()
