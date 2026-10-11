"""Gestão de temas do Pico Launcher em /_pico/themes."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import zipfile
from typing import Any, Optional

from core.dspico import get_dspico_settings, set_dspico_settings
from core.logging_util import emit_log
from core.pico_bmp import rgba_to_icon_bmp
from core.privacy import redact_text
from core.sdio import UndoStack, sync_volume
from core.twilight import _is_safe_archive_member

_THEME_NAME_RE = re.compile(r"^[A-Za-z0-9._\- ]{1,64}$")
_CUSTOM_REQUIRED_FILES = frozenset(
    {
        "bannerListCell.bin",
        "bannerListCellPltt.bin",
        "bannerListCellSelected.bin",
        "bannerListCellSelectedPltt.bin",
        "bottombg.bin",
        "gridcell.bin",
        "gridcellPltt.bin",
        "gridcellSelected.bin",
        "gridcellPlttSelected.bin",
        "scrim.bin",
        "scrimPltt.bin",
        "topbg.bin",
    }
)


def _themes_root(mount_path: str) -> str:
    return os.path.join(mount_path, "_pico", "themes")


def _safe_theme_folder(name: str) -> Optional[str]:
    if not isinstance(name, str):
        return None
    clean = name.strip().strip("/\\")
    if not clean or clean in {".", ".."} or "/" in clean or "\\" in clean:
        return None
    if not _THEME_NAME_RE.match(clean):
        return None
    return clean


def _safe_join(root: str, *parts: str) -> Optional[str]:
    try:
        base = os.path.realpath(root)
        full = os.path.realpath(os.path.join(base, *parts))
        if os.path.commonpath([base, full]) != base:
            return None
        return full
    except (ValueError, OSError):
        return None


def _json_load(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("theme.json deve ter objeto na raiz.")
    return data


def _color_ok(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    for k in ("r", "g", "b"):
        v = obj.get(k)
        if not isinstance(v, int) or v < 0 or v > 255:
            return False
    return True


def _validate_theme_folder(folder_path: str) -> tuple[bool, str, Optional[dict[str, Any]]]:
    theme_json = os.path.join(folder_path, "theme.json")
    if not os.path.isfile(theme_json):
        return False, "theme.json em falta.", None
    try:
        data = _json_load(theme_json)
    except Exception as e:
        return False, f"theme.json inválido: {e}", None

    kind = str(data.get("type") or "").strip().lower()
    if kind not in {"material", "custom"}:
        return False, "type inválido (use material ou custom).", None
    if "name" in data and not isinstance(data.get("name"), str):
        return False, "name do tema deve ser string.", None
    if "primaryColor" in data and not _color_ok(data.get("primaryColor")):
        return False, "primaryColor inválida no theme.json.", None
    if "darkTheme" in data and not isinstance(data.get("darkTheme"), bool):
        return False, "darkTheme deve ser booleano.", None

    if kind == "custom":
        present = set(os.listdir(folder_path))
        missing = sorted(name for name in _CUSTOM_REQUIRED_FILES if name not in present)
        if missing:
            return False, "Tema custom incompleto: " + ", ".join(missing), None

    return True, "ok", data


def _write_json_atomic(path: str, data: dict[str, Any], undo: UndoStack) -> None:
    bak = None
    if os.path.isfile(path):
        bak = path + f".bak_{os.getpid()}"
        shutil.copy2(path, bak)
        undo.push_restore_file(bak, path)
    else:
        undo.push_remove(path)

    partial = path + ".partial"
    with open(partial, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(partial, path)
    if bak and os.path.isfile(bak):
        try:
            os.remove(bak)
        except OSError:
            pass


def list_pico_themes(mount_path: str) -> dict[str, Any]:
    """Lista temas válidos em /_pico/themes e tema activo em settings.json."""
    try:
        root = _themes_root(mount_path)
        os.makedirs(root, exist_ok=True)
        settings = get_dspico_settings(mount_path)
        active = ""
        if settings.get("success") and isinstance(settings.get("settings"), dict):
            raw = settings["settings"].get("theme")
            active = str(raw).strip() if isinstance(raw, str) else ""

        items: list[dict[str, Any]] = []
        for name in sorted(os.listdir(root), key=str.lower):
            folder = _safe_join(root, name)
            if not folder or not os.path.isdir(folder):
                continue
            ok, err, data = _validate_theme_folder(folder)
            if not ok:
                continue
            items.append(
                {
                    "folder": name,
                    "type": str((data or {}).get("type") or ""),
                    "name": str((data or {}).get("name") or name),
                    "description": str((data or {}).get("description") or ""),
                    "author": str((data or {}).get("author") or ""),
                    "active": name == active,
                }
            )
        return {"success": True, "themes": items, "active_theme": active}
    except Exception as e:
        return {"success": False, "error": redact_text(e), "themes": []}


def set_pico_theme(mount_path: str, theme_folder: str) -> tuple[bool, str, dict[str, Any]]:
    """Define o tema activo no /_pico/settings.json (campo theme)."""
    stats: dict[str, Any] = {}
    try:
        folder = _safe_theme_folder(theme_folder or "")
        if not folder:
            return False, "Nome de pasta de tema inválido.", stats
        root = _themes_root(mount_path)
        target = _safe_join(root, folder)
        if not target or not os.path.isdir(target):
            return False, "Tema não encontrado.", stats
        ok, err, _data = _validate_theme_folder(target)
        if not ok:
            return False, err, stats

        ok_set, msg = set_dspico_settings(mount_path, {"theme": folder})
        if not ok_set:
            return False, msg, stats
        sync_volume(mount_path)
        stats["theme"] = folder
        return True, f"Tema activo definido para '{folder}'.", stats
    except Exception as e:
        return False, redact_text(e), stats


def _extract_theme_source(source_path: str) -> tuple[str, bool]:
    src = os.path.realpath(os.path.expanduser(source_path))
    if os.path.isdir(src):
        return src, False
    if os.path.isfile(src) and src.lower().endswith(".zip"):
        tmp = tempfile.mkdtemp(prefix="pico_theme_")
        try:
            with zipfile.ZipFile(src, "r") as zf:
                for info in zf.infolist():
                    if not _is_safe_archive_member(info.filename, tmp):
                        raise RuntimeError(
                            f"Zip rejeitado (caminho inseguro): {info.filename!r}"
                        )
                zf.extractall(tmp)
        except Exception:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        return tmp, True
    raise RuntimeError("Fonte do tema inválida (use pasta ou ZIP).")


def _pick_theme_folder(extracted_root: str) -> str:
    direct = os.path.join(extracted_root, "theme.json")
    if os.path.isfile(direct):
        return extracted_root
    candidates = []
    for name in os.listdir(extracted_root):
        path = os.path.join(extracted_root, name)
        if os.path.isdir(path) and os.path.isfile(os.path.join(path, "theme.json")):
            candidates.append(path)
    if len(candidates) == 1:
        return candidates[0]
    raise RuntimeError("Não foi possível localizar uma única pasta de tema válida.")


def import_pico_theme(
    mount_path: str, source_path: str
) -> tuple[bool, str, dict[str, Any]]:
    """Importa tema (pasta/ZIP) para /_pico/themes/<folder> após validação."""
    stats: dict[str, Any] = {}
    extracted_tmp = None
    undo = UndoStack()
    try:
        if not isinstance(source_path, str) or not source_path.strip():
            return False, "Caminho de origem inválido.", stats
        source_root, is_tmp = _extract_theme_source(source_path.strip())
        extracted_tmp = source_root if is_tmp else None
        theme_folder_src = _pick_theme_folder(source_root)
        ok, err, data = _validate_theme_folder(theme_folder_src)
        if not ok:
            return False, err, stats

        root = _themes_root(mount_path)
        os.makedirs(root, exist_ok=True)
        preferred = _safe_theme_folder(os.path.basename(theme_folder_src))
        if not preferred:
            preferred = _safe_theme_folder(str((data or {}).get("name") or "theme"))
        if not preferred:
            preferred = "theme"
        target = _safe_join(root, preferred)
        if not target:
            return False, "Destino de tema inválido.", stats

        bak = None
        staging = tempfile.mkdtemp(prefix="theme_stage_", dir=root)
        try:
            staging_target = os.path.join(staging, preferred)
            shutil.copytree(theme_folder_src, staging_target)
            if os.path.isdir(target):
                bak = target + f".bak_{os.getpid()}"
                os.replace(target, bak)
                undo.push(lambda b=bak, t=target: os.path.isdir(b) and os.replace(b, t))
            else:
                undo.push_remove(target)
            os.replace(staging_target, target)
        finally:
            shutil.rmtree(staging, ignore_errors=True)

        sync_volume(mount_path)
        if bak and os.path.isdir(bak):
            shutil.rmtree(bak, ignore_errors=True)
        stats["theme_folder"] = preferred
        stats["theme_type"] = str((data or {}).get("type") or "")
        return True, f"Tema '{preferred}' importado com sucesso.", stats
    except Exception as e:
        try:
            undo.rollback(None, mount_path=mount_path)
        except Exception:
            pass
        return False, redact_text(e), stats
    finally:
        if extracted_tmp:
            shutil.rmtree(extracted_tmp, ignore_errors=True)


def create_pico_material_theme(
    mount_path: str,
    name: str,
    r: int,
    g: int,
    b: int,
    dark: bool = True,
) -> tuple[bool, str, dict[str, Any]]:
    """Cria tema material com ícone sólido em /_pico/themes/<name>/."""
    stats: dict[str, Any] = {}
    try:
        folder = _safe_theme_folder(name or "")
        if not folder:
            return False, "Nome do tema inválido.", stats
        rgb = []
        for value in (r, g, b):
            if not isinstance(value, int) or value < 0 or value > 255:
                return False, "Cor RGB inválida (0-255).", stats
            rgb.append(value)

        root = _themes_root(mount_path)
        os.makedirs(root, exist_ok=True)
        target = _safe_join(root, folder)
        if not target:
            return False, "Destino inválido.", stats
        if os.path.exists(target):
            return False, "Já existe tema com esse nome.", stats

        undo = UndoStack()
        os.makedirs(target, exist_ok=False)
        undo.push_remove(target)

        payload = {
            "type": "material",
            "name": folder,
            "description": "Tema material criado pelo Route 1 Kit.",
            "author": "Route 1 Kit",
            "primaryColor": {"r": rgb[0], "g": rgb[1], "b": rgb[2]},
            "darkTheme": bool(dark),
        }
        _write_json_atomic(os.path.join(target, "theme.json"), payload, undo)

        rgba = bytes((rgb[0], rgb[1], rgb[2], 255)) * (32 * 32)
        icon_bmp = rgba_to_icon_bmp(32, 32, rgba)
        icon_path = os.path.join(target, "icon.bmp")
        with open(icon_path + ".partial", "wb") as f:
            f.write(icon_bmp)
            f.flush()
            os.fsync(f.fileno())
        os.replace(icon_path + ".partial", icon_path)
        undo.push_remove(icon_path)

        sync_volume(mount_path)
        stats["theme_folder"] = folder
        return True, f"Tema material '{folder}' criado.", stats
    except Exception as e:
        return False, redact_text(e), stats
