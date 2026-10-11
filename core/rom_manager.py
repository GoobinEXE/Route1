"""Gestão de ROMs no cartão: listar, importar (cópia rápida) e remover com saves."""

from __future__ import annotations

import base64
import os
import re
import shutil
from typing import Any, Optional

from core.logging_util import emit_log
from core.privacy import redact_path
from core.rom_cleaner import (
    PLATFORM_BY_EXT,
    SKIP_DIR_NAMES,
    TWILIGHT_ROM_FOLDERS,
    _unique_path,
    classify_nds_kind,
    clean_rom_filename,
    companion_index_keys,
    detect_franchise,
    detect_platform,
    get_nds_header_info,
    is_companion_ext,
    is_save_ext,
    normalize_layout,
    rom_dest_dir,
)
from core.sdio import UndoStack, copy_fast, copy_verified, sync_volume

SAVE_MODES = frozenset({"delete", "backup", "keep"})
SAVE_MODE_ALIASES = {
    "apagar": "delete",
    "remove": "delete",
    "backup_to_path": "backup",
    "backup_saves": "backup",
    "keep_on_sd": "keep",
    "manter": "keep",
}

DEFAULT_BACKUP_DIRNAME = "Route1Kit_Saves"
ARTWORK_KINDS = frozenset({"boxart", "icon"})
MAX_ARTWORK_BYTES = 2 * 1024 * 1024
MAX_PREVIEW_BYTES = 512 * 1024
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

# Como o TWiLight Menu++ corre cada plataforma (texto PT para a gaveta).
RUN_INFO_BY_PLATFORM = {
    "nds": {
        "title": "Nintendo DS (nativo)",
        "body": "Corre no hardware DS/DSi via nds-bootstrap do TWiLight Menu++.",
        "requirements": ["TWiLight Menu++", "nds-bootstrap"],
    },
    "dsi": {
        "title": "DSiWare / DSi",
        "body": "Títulos DSi correm via nds-bootstrap / ambiente DSi do TWiLight.",
        "requirements": ["TWiLight Menu++", "nds-bootstrap"],
    },
    "apps": {
        "title": "Homebrew / app",
        "body": "Aplicação NDS na pasta apps — abre directamente no TWiLight.",
        "requirements": ["TWiLight Menu++"],
    },
    "gba": {
        "title": "Game Boy Advance",
        "body": "Emulado pelo GBARunner2 incluído no TWiLight Menu++.",
        "requirements": ["TWiLight Menu++", "GBARunner2"],
    },
    "gb": {
        "title": "Game Boy",
        "body": "Emulado pelo GameYob (add-on Virtual Console do kit TWiLight).",
        "requirements": ["TWiLight Menu++", "Add-on Virtual Console (GameYob)"],
    },
    "gbc": {
        "title": "Game Boy Color",
        "body": "Emulado pelo GameYob (add-on Virtual Console do kit TWiLight).",
        "requirements": ["TWiLight Menu++", "Add-on Virtual Console (GameYob)"],
    },
    "nes": {
        "title": "NES / Famicom",
        "body": "Emulador NES do add-on Virtual Console no TWiLight.",
        "requirements": ["TWiLight Menu++", "Add-on Virtual Console"],
    },
    "snes": {
        "title": "Super Nintendo",
        "body": "Emulador SNES do add-on Virtual Console no TWiLight.",
        "requirements": ["TWiLight Menu++", "Add-on Virtual Console"],
    },
    "gen": {
        "title": "Mega Drive / Genesis",
        "body": "Emulador Mega Drive do add-on Virtual Console no TWiLight.",
        "requirements": ["TWiLight Menu++", "Add-on Virtual Console"],
    },
    "sms": {
        "title": "Master System",
        "body": "Emulador Master System do add-on Virtual Console no TWiLight.",
        "requirements": ["TWiLight Menu++", "Add-on Virtual Console"],
    },
    "gg": {
        "title": "Game Gear",
        "body": "Emulador Game Gear do add-on Virtual Console no TWiLight.",
        "requirements": ["TWiLight Menu++", "Add-on Virtual Console"],
    },
}

# Extensões de ROM importáveis (ambíguas excluídas — só se pasta de origem conhecida)
IMPORTABLE_EXTS = frozenset(
    ext for ext, plat in PLATFORM_BY_EXT.items() if plat is not None
) | {".ids", ".app", ".srl"}

CONFLICT_RESOLUTIONS = frozenset({"replace", "keep_both", "skip"})
NDS_ROM_EXTS = frozenset({".nds", ".dsi", ".ids", ".app"})


def normalize_save_mode(mode) -> Optional[str]:
    if mode is None or mode == "":
        return "delete"
    if not isinstance(mode, str):
        return None
    low = mode.strip().lower()
    if low in SAVE_MODES:
        return low
    return SAVE_MODE_ALIASES.get(low)


def default_saves_backup_dir() -> str:
    """Pasta padrão no Desktop (ou Documents) para backup de saves."""
    home = os.path.expanduser("~")
    for name in ("Desktop", "Ambiente de Trabalho", "Documents", "Documentos"):
        parent = os.path.join(home, name)
        if os.path.isdir(parent):
            return os.path.join(parent, DEFAULT_BACKUP_DIRNAME)
    return os.path.join(home, DEFAULT_BACKUP_DIRNAME)


def _roms_root(mount_path: str) -> str:
    return os.path.join(mount_path, "roms")


def _resolve_under_roms(mount_path: str, rel_path: str) -> Optional[str]:
    """Resolve rel_path sob /roms/; None se path traversal / fora da árvore."""
    if not isinstance(rel_path, str) or not rel_path.strip():
        return None
    if "\x00" in rel_path:
        return None
    rel = rel_path.replace("\\", "/").lstrip("/")
    if rel.startswith("..") or "/../" in f"/{rel}/":
        return None
    roms = os.path.realpath(_roms_root(mount_path))
    candidate = os.path.realpath(os.path.join(roms, *rel.split("/")))
    try:
        common = os.path.commonpath([roms, candidate])
    except ValueError:
        return None
    if os.path.normcase(common) != os.path.normcase(roms):
        return None
    return candidate


def _format_size(n: int) -> str:
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "?"
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


def _valid_nds_tid(game_code: Optional[str]) -> Optional[str]:
    code = (game_code or "").replace("\x00", "").strip().upper()
    if len(code) != 4 or not code.isalnum():
        return None
    return code


def _strip_unique_name_suffix(name: str) -> str:
    """Remove sufixos de cópia: «Game (2)» / «Game_2» → «Game»."""
    s = (name or "").strip()
    if not s:
        return s
    s = re.sub(r"\s*\(\d+\)$", "", s)
    s = re.sub(r"_\d+$", "", s)
    return s.strip() or name.strip()


def duplicate_key(
    platform: Optional[str],
    game_code: Optional[str],
    clean_name: Optional[str],
) -> Optional[str]:
    """
    Chave de identidade para «mesmo jogo».
    NDS/DSi com TID válido → tid:XXXX; senão platform:nome_limpo.
    """
    tid = _valid_nds_tid(game_code)
    if tid:
        return f"tid:{tid}"
    plat = (platform or "").strip().lower()
    name = _strip_unique_name_suffix((clean_name or "").strip()).lower()
    if not plat or not name:
        return None
    return f"name:{plat}:{name}"


def conflict_id_for(dup_key: str, src_basename: str) -> str:
    base = os.path.basename(src_basename or "").strip() or "?"
    return f"{dup_key}|{base}"


def normalize_conflict_resolutions(raw) -> Optional[dict[str, str]]:
    """Valida mapa conflict_id → replace|keep_both|skip. None se inválido."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        return None
    out: dict[str, str] = {}
    for k, v in raw.items():
        if not isinstance(k, str) or not k.strip():
            continue
        if not isinstance(v, str):
            return None
        low = v.strip().lower()
        if low not in CONFLICT_RESOLUTIONS:
            return None
        out[k.strip()] = low
    return out


def _find_sidecars(rom_path: str, roms_root: str) -> list[dict[str, Any]]:
    """Saves e extras com o mesmo stem (pasta da ROM + /roms/saves/)."""
    stem = os.path.splitext(os.path.basename(rom_path))[0]
    stem_l = stem.lower()
    parent = os.path.dirname(rom_path)
    found: list[dict[str, Any]] = []
    seen: set[str] = set()

    search_dirs = [parent]
    saves_dir = os.path.join(roms_root, "saves")
    if os.path.isdir(saves_dir) and os.path.normcase(saves_dir) != os.path.normcase(parent):
        search_dirs.append(saves_dir)

    for directory in search_dirs:
        try:
            names = os.listdir(directory)
        except OSError:
            continue
        for name in names:
            matched = False
            for key, _suffix in companion_index_keys(name):
                if key == stem_l:
                    matched = True
                    break
            if not matched:
                continue
            ext_l = os.path.splitext(name)[1].lower()
            full = os.path.join(directory, name)
            if not os.path.isfile(full):
                continue
            key = os.path.normcase(os.path.realpath(full))
            if key in seen:
                continue
            seen.add(key)
            try:
                size = os.path.getsize(full)
            except OSError:
                size = 0
            try:
                rel = os.path.relpath(full, roms_root).replace("\\", "/")
            except ValueError:
                rel = name
            found.append(
                {
                    "name": name,
                    "rel_path": rel,
                    "ext": ext_l,
                    "size": size,
                    "is_save": is_save_ext(ext_l),
                }
            )
    return found


def list_roms(mount_path: str) -> dict[str, Any]:
    """Lista jogos/apps sob /roms/ (só leitura)."""
    if not os.path.isdir(mount_path):
        return {"success": False, "error": "Cartão inexistente.", "roms": []}

    roms_root = _roms_root(mount_path)
    if not os.path.isdir(roms_root):
        return {"success": True, "roms": [], "count": 0, "message": "Pasta /roms/ ainda não existe."}

    items: list[dict[str, Any]] = []
    for root, dirs, files in os.walk(roms_root, topdown=True):
        dirs[:] = [d for d in dirs if d not in SKIP_DIR_NAMES and not d.startswith(".")]
        for name in files:
            if name.startswith("._") or name.endswith(".partial") or name == ".DS_Store":
                continue
            ext = os.path.splitext(name)[1].lower()
            if is_companion_ext(ext):
                continue
            if ext not in PLATFORM_BY_EXT and ext not in (".ids", ".app", ".srl"):
                continue
            if PLATFORM_BY_EXT.get(ext) is None and ext not in (".ids", ".app", ".srl"):
                # .bin/.rom ambíguos: só se já estiverem sob pasta de plataforma
                parent = os.path.basename(root).lower()
                known = {v for v in PLATFORM_BY_EXT.values() if v} | set(
                    TWILIGHT_ROM_FOLDERS
                ) | {"dsiware"}
                if parent not in known:
                    continue

            full = os.path.join(root, name)
            if not os.path.isfile(full):
                continue

            header_info = None
            game_code = None
            raw_title = None
            kind = None
            if ext in (".nds", ".dsi", ".ids", ".app"):
                header_info = get_nds_header_info(full)
                raw_title, game_code, _uc, maker = header_info
                kind = classify_nds_kind(raw_title, game_code, maker, name, at_sd_root=False)

            platform = detect_platform(full, name, ext, header_info=header_info, kind=kind)
            if not platform:
                continue

            try:
                size = os.path.getsize(full)
            except OSError:
                size = 0
            try:
                rel = os.path.relpath(full, roms_root).replace("\\", "/")
            except ValueError:
                continue

            sidecars = _find_sidecars(full, roms_root)
            display = clean_rom_filename(name, game_code)
            icon_url = None
            if ext in (".nds", ".dsi", ".ids", ".app"):
                try:
                    from core.nds_icon import nds_icon_data_url

                    icon_url = nds_icon_data_url(full)
                except Exception:
                    icon_url = None
            items.append(
                {
                    "rel_path": rel,
                    "name": name,
                    "display_name": display,
                    "platform": platform,
                    "kind": kind or "game",
                    "game_code": (game_code or "").replace("\x00", "").strip() or None,
                    "title": (raw_title or "").strip() or None,
                    "size": size,
                    "size_label": _format_size(size),
                    "has_save": any(s.get("is_save") for s in sidecars),
                    "sidecars": sidecars,
                    "icon": icon_url,
                }
            )

    items.sort(key=lambda r: ((r.get("platform") or ""), (r.get("display_name") or "").lower()))
    return {"success": True, "roms": items, "count": len(items)}


def _normalize_rel_dir(rel_dir) -> Optional[str]:
    """Normaliza pasta relativa sob /roms/; '' = raiz. None se inválido."""
    if rel_dir is None or rel_dir == "" or rel_dir == ".":
        return ""
    if not isinstance(rel_dir, str):
        return None
    if "\x00" in rel_dir:
        return None
    rel = rel_dir.replace("\\", "/").strip().strip("/")
    if not rel:
        return ""
    if rel.startswith("..") or "/../" in f"/{rel}/" or rel == "..":
        return None
    parts = [p for p in rel.split("/") if p and p != "."]
    for p in parts:
        if p.startswith(".") or p in SKIP_DIR_NAMES:
            return None
    return "/".join(parts)


def _sanitize_dir_name(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00]', "", name or "").strip(" .")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:60]


def _file_entry(full: str, roms_root: str) -> Optional[dict[str, Any]]:
    """Metadados de um ficheiro ROM (None se não for ROM listável)."""
    name = os.path.basename(full)
    if name.startswith("._") or name.endswith(".partial") or name == ".DS_Store":
        return None
    ext = os.path.splitext(name)[1].lower()
    if is_companion_ext(ext):
        return None
    if ext not in PLATFORM_BY_EXT and ext not in (".ids", ".app", ".srl"):
        return None
    if PLATFORM_BY_EXT.get(ext) is None and ext not in (".ids", ".app", ".srl"):
        parent = os.path.basename(os.path.dirname(full)).lower()
        known = {v for v in PLATFORM_BY_EXT.values() if v} | set(
            TWILIGHT_ROM_FOLDERS
        ) | {"dsiware"}
        if parent not in known:
            return None

    header_info = None
    game_code = None
    raw_title = None
    kind = None
    if ext in (".nds", ".dsi", ".ids", ".app"):
        header_info = get_nds_header_info(full)
        raw_title, game_code, _uc, maker = header_info
        kind = classify_nds_kind(raw_title, game_code, maker, name, at_sd_root=False)

    platform = detect_platform(full, name, ext, header_info=header_info, kind=kind)
    if not platform:
        return None

    try:
        size = os.path.getsize(full)
    except OSError:
        size = 0
    try:
        rel = os.path.relpath(full, roms_root).replace("\\", "/")
    except ValueError:
        return None

    sidecars = _find_sidecars(full, roms_root)
    display = clean_rom_filename(name, game_code)
    # Preferir ícone TWiLight custom; senão banner NDS.
    mount_path = os.path.dirname(roms_root)
    icon_url = None
    custom_icon = _custom_icon_path(mount_path, name)
    if custom_icon:
        icon_url = _png_data_url(custom_icon)
    if not icon_url and ext in (".nds", ".dsi", ".ids", ".app"):
        try:
            from core.nds_icon import nds_icon_data_url

            icon_url = nds_icon_data_url(full)
        except Exception:
            icon_url = None
    return {
        "rel_path": rel,
        "name": name,
        "display_name": display,
        "platform": platform,
        "kind": kind or "game",
        "game_code": (game_code or "").replace("\x00", "").strip() or None,
        "title": (raw_title or "").strip() or None,
        "size": size,
        "size_label": _format_size(size),
        "has_save": any(s.get("is_save") for s in sidecars),
        "sidecars": sidecars,
        "type": "file",
        "icon": icon_url,
    }


def list_rom_dir(mount_path: str, rel_dir: str = "") -> dict[str, Any]:
    """Lista pastas e ROMs num nível sob /roms/<rel_dir>."""
    if not os.path.isdir(mount_path):
        return {"success": False, "error": "Cartão inexistente.", "dirs": [], "files": []}

    norm = _normalize_rel_dir(rel_dir)
    if norm is None:
        return {"success": False, "error": "Pasta inválida.", "dirs": [], "files": []}

    roms_root = _roms_root(mount_path)
    if norm:
        target = _resolve_under_roms(mount_path, norm)
        if not target or not os.path.isdir(target):
            return {
                "success": False,
                "error": f"Pasta /roms/{norm}/ inexistente.",
                "dirs": [],
                "files": [],
                "rel_dir": norm,
            }
    else:
        os.makedirs(roms_root, exist_ok=True)
        target = os.path.realpath(roms_root)

    dirs_out: list[dict[str, Any]] = []
    files_out: list[dict[str, Any]] = []
    try:
        names = sorted(os.listdir(target), key=lambda n: n.lower())
    except OSError as e:
        return {"success": False, "error": str(e), "dirs": [], "files": []}

    for name in names:
        if name.startswith(".") or name in SKIP_DIR_NAMES:
            continue
        full = os.path.join(target, name)
        if os.path.isdir(full):
            try:
                child_count = sum(
                    1
                    for c in os.listdir(full)
                    if not c.startswith(".") and c not in SKIP_DIR_NAMES
                )
            except OSError:
                child_count = 0
            try:
                rel = os.path.relpath(full, roms_root).replace("\\", "/")
            except ValueError:
                continue
            dirs_out.append(
                {
                    "name": name,
                    "rel_path": rel,
                    "item_count": child_count,
                    "type": "dir",
                }
            )
        elif os.path.isfile(full):
            entry = _file_entry(full, roms_root)
            if entry:
                files_out.append(entry)

    return {
        "success": True,
        "rel_dir": norm,
        "dirs": dirs_out,
        "files": files_out,
        "count": len(dirs_out) + len(files_out),
    }


def list_rom_tree(mount_path: str) -> dict[str, Any]:
    """Árvore de pastas sob /roms/ (só dirs)."""
    if not os.path.isdir(mount_path):
        return {"success": False, "error": "Cartão inexistente.", "tree": []}

    roms_root = _roms_root(mount_path)
    if not os.path.isdir(roms_root):
        return {
            "success": True,
            "tree": [{"name": "roms", "rel_path": "", "children": []}],
        }

    def walk_dirs(abs_dir: str, rel: str) -> list[dict[str, Any]]:
        children: list[dict[str, Any]] = []
        try:
            names = sorted(os.listdir(abs_dir), key=lambda n: n.lower())
        except OSError:
            return children
        for name in names:
            if name.startswith(".") or name in SKIP_DIR_NAMES:
                continue
            full = os.path.join(abs_dir, name)
            if not os.path.isdir(full):
                continue
            child_rel = f"{rel}/{name}" if rel else name
            children.append(
                {
                    "name": name,
                    "rel_path": child_rel,
                    "children": walk_dirs(full, child_rel),
                }
            )
        return children

    return {
        "success": True,
        "tree": [
            {
                "name": "roms",
                "rel_path": "",
                "children": walk_dirs(roms_root, ""),
            }
        ],
    }


def browse_roms(mount_path: str, rel_dir: str = "") -> dict[str, Any]:
    """
    Snapshot atómico do explorador: pasta actual + árvore.
    Uma só chamada evita corrida de OP_LOCK entre list_rom_dir e list_rom_tree.
    """
    dir_res = list_rom_dir(mount_path, rel_dir)
    if not dir_res.get("success"):
        return dir_res
    tree_res = list_rom_tree(mount_path)
    if not tree_res.get("success"):
        return {
            "success": False,
            "error": tree_res.get("error") or "Falha ao listar árvore.",
            "dirs": [],
            "files": [],
            "tree": [],
        }
    return {
        "success": True,
        "rel_dir": dir_res.get("rel_dir") or "",
        "dirs": dir_res.get("dirs") or [],
        "files": dir_res.get("files") or [],
        "count": dir_res.get("count") or 0,
        "tree": tree_res.get("tree") or [],
    }


def mkdir_rom_dir(
    mount_path: str, parent_rel: str = "", name: str = "", log_callback=None
) -> tuple[bool, str, dict]:
    """Cria subpasta sob /roms/<parent_rel>/<name>."""
    log = lambda msg: emit_log(log_callback, msg)
    parent = _normalize_rel_dir(parent_rel)
    if parent is None:
        return False, "Pasta pai inválida.", {}
    folder = _sanitize_dir_name(name if isinstance(name, str) else "")
    if not folder:
        return False, "Nome de pasta inválido.", {}
    if folder.startswith(".") or folder in SKIP_DIR_NAMES:
        return False, "Nome de pasta reservado.", {}

    roms_root = _roms_root(mount_path)
    if parent:
        base = _resolve_under_roms(mount_path, parent)
        if not base or not os.path.isdir(base):
            return False, f"Pasta /roms/{parent}/ inexistente.", {}
    else:
        os.makedirs(roms_root, exist_ok=True)
        base = roms_root

    dest = os.path.join(base, folder)
    # Revalidar que fica sob roms
    check_rel = f"{parent}/{folder}" if parent else folder
    if _resolve_under_roms(mount_path, check_rel) is None and not os.path.isdir(dest):
        # Antes de criar, validar path conceptual
        pass
    resolved = _resolve_under_roms(mount_path, check_rel)
    # Se ainda não existe, construir e validar parent+name
    if resolved is None:
        candidate = os.path.realpath(os.path.join(base, folder))
        try:
            common = os.path.commonpath([os.path.realpath(roms_root), candidate])
        except ValueError:
            return False, "Caminho fora de /roms/.", {}
        if os.path.normcase(common) != os.path.normcase(os.path.realpath(roms_root)):
            return False, "Caminho fora de /roms/.", {}

    if os.path.exists(dest):
        return False, f"Já existe: /roms/{check_rel}/", {}
    try:
        os.makedirs(dest, exist_ok=False)
        sync_volume(mount_path)
    except OSError as e:
        return False, f"Falha ao criar pasta: {e}", {}
    log(f"📁 Criada /roms/{check_rel}/")
    return True, f"Pasta /roms/{check_rel}/ criada.", {"rel_path": check_rel}


def move_roms(
    mount_path: str,
    rel_paths: list,
    dest_rel_dir: str = "",
    log_callback=None,
) -> tuple[bool, str, dict]:
    """
    Move ROMs (e sidecars com o mesmo stem) para /roms/<dest_rel_dir>/.
    """
    log = lambda msg: emit_log(log_callback, msg)
    dest_norm = _normalize_rel_dir(dest_rel_dir)
    if dest_norm is None:
        return False, "Pasta de destino inválida.", {}

    if not isinstance(rel_paths, (list, tuple)) or not rel_paths:
        return False, "Nenhum item seleccionado.", {}

    roms_root = _roms_root(mount_path)
    if dest_norm:
        dest_dir = _resolve_under_roms(mount_path, dest_norm)
        if not dest_dir or not os.path.isdir(dest_dir):
            return False, f"Destino /roms/{dest_norm}/ inexistente.", {}
    else:
        os.makedirs(roms_root, exist_ok=True)
        dest_dir = os.path.realpath(roms_root)

    moved = 0
    sidecars_moved = 0
    failures = 0
    skipped = 0

    log(f"=== Mover {len(rel_paths)} item(ns) ➔ /roms/{dest_norm or ''}/ ===")

    for rel in rel_paths:
        if not isinstance(rel, str):
            failures += 1
            continue
        src = _resolve_under_roms(mount_path, rel)
        if not src or not os.path.isfile(src):
            log(f"⚠️ Não encontrado: {rel}")
            failures += 1
            continue

        ext = os.path.splitext(src)[1].lower()
        if is_save_ext(ext) or is_companion_ext(ext):
            log(f"⚠️ Ignorado (save/sidecar avulso): {rel}")
            skipped += 1
            continue

        # Já no destino?
        if os.path.normcase(os.path.dirname(src)) == os.path.normcase(dest_dir):
            skipped += 1
            continue

        sidecars = _find_sidecars(src, roms_root)
        # Só sidecars na mesma pasta da ROM (não mover os de /roms/saves/ à distância
        # a menos que estejam ao lado — _find_sidecars inclui saves/; ao mover ROM
        # movemos sidecars na mesma pasta; saves em /roms/saves/ ficam)
        local_sidecars = []
        for sc in sidecars:
            sc_path = _resolve_under_roms(mount_path, sc["rel_path"])
            if sc_path and os.path.isfile(sc_path):
                if os.path.normcase(os.path.dirname(sc_path)) == os.path.normcase(
                    os.path.dirname(src)
                ):
                    local_sidecars.append(sc_path)

        dest_rom = _unique_path(os.path.join(dest_dir, os.path.basename(src)))
        try:
            shutil.move(src, dest_rom)
            moved += 1
            try:
                new_rel = os.path.relpath(dest_rom, roms_root).replace("\\", "/")
            except ValueError:
                new_rel = os.path.basename(dest_rom)
            log(f"📦 {rel} ➔ /roms/{new_rel}")
        except Exception as e:
            failures += 1
            log(f"⚠️ Falha ao mover {rel}: {e}")
            continue

        final_stem = os.path.splitext(os.path.basename(dest_rom))[0]
        for sc_path in local_sidecars:
            sc_ext = os.path.splitext(sc_path)[1]
            sc_dest = _unique_path(os.path.join(dest_dir, f"{final_stem}{sc_ext}"))
            try:
                shutil.move(sc_path, sc_dest)
                sidecars_moved += 1
            except Exception as e:
                failures += 1
                log(f"⚠️ Falha ao mover sidecar: {e}")

        _remove_empty_parents(src, roms_root)

    try:
        sync_volume(mount_path)
    except Exception:
        pass

    dest_label = f"/roms/{dest_norm}/" if dest_norm else "/roms/"
    msg = (
        f"{moved} movido(s)"
        + (f", {sidecars_moved} sidecar(s)" if sidecars_moved else "")
        + (f"; {skipped} ignorado(s)" if skipped else "")
        + (f"; {failures} falha(s)" if failures else "")
        + f" ➔ {dest_label}"
    )
    log(f"✅ {msg}")
    if moved == 0 and failures:
        return False, msg, {"moved": 0, "failures": failures}
    return True, msg, {
        "moved": moved,
        "sidecars": sidecars_moved,
        "skipped": skipped,
        "failures": failures,
    }


def _companion_saves_near(host_path: str) -> list[str]:
    """Ficheiros de save/estado com o mesmo stem ao lado da ROM no computador."""
    stem = os.path.splitext(os.path.basename(host_path))[0]
    stem_l = stem.lower()
    parent = os.path.dirname(host_path)
    out: list[str] = []
    try:
        for name in os.listdir(parent):
            for key, _suffix in companion_index_keys(name):
                if key != stem_l:
                    continue
                if not is_save_ext(os.path.splitext(name)[1]):
                    continue
                full = os.path.join(parent, name)
                if os.path.isfile(full):
                    out.append(full)
                break
    except OSError:
        pass
    return out


def _rom_dup_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "rel_path": item.get("rel_path"),
        "name": item.get("name"),
        "display_name": item.get("display_name") or item.get("name"),
        "platform": item.get("platform"),
        "game_code": item.get("game_code"),
        "size": item.get("size") or 0,
        "size_label": item.get("size_label") or _format_size(item.get("size") or 0),
        "has_save": bool(item.get("has_save")),
    }


def _index_roms_by_dup_key(mount_path: str) -> dict[str, list[dict[str, Any]]]:
    """Indexa ROMs do cartão por chave de duplicata (ignora system)."""
    listed = list_roms(mount_path)
    if not listed.get("success"):
        return {}
    index: dict[str, list[dict[str, Any]]] = {}
    for item in listed.get("roms") or []:
        if not isinstance(item, dict):
            continue
        if (item.get("kind") or "game") == "system":
            continue
        key = duplicate_key(
            item.get("platform"),
            item.get("game_code"),
            item.get("display_name") or clean_rom_filename(
                item.get("name") or "", item.get("game_code")
            ),
        )
        if not key:
            continue
        index.setdefault(key, []).append(_rom_dup_summary(item))
    return index


def find_duplicate_roms(mount_path: str) -> dict[str, Any]:
    """Grupos de jogos iguais sob /roms/ (≥2 ficheiros por chave)."""
    if not os.path.isdir(mount_path):
        return {"success": False, "error": "Cartão inexistente.", "groups": []}
    index = _index_roms_by_dup_key(mount_path)
    groups: list[dict[str, Any]] = []
    for key, items in sorted(index.items(), key=lambda kv: kv[0]):
        if len(items) < 2:
            continue
        label = items[0].get("display_name") or key
        tid = key[4:] if key.startswith("tid:") else None
        if tid:
            label = f"{label} ({tid})"
        groups.append({"key": key, "label": label, "items": items})
    return {"success": True, "groups": groups, "count": len(groups)}


def _collect_import_jobs(
    mount_path: str,
    host_paths: list,
    log=None,
) -> tuple[list[tuple], int, dict, list[str]]:
    """
    Expande arquivos e monta jobs de import.
    Devolve (jobs, skipped, expand_stats, expand_errors).
    Cada job: (src, clean, ext, platform, game_code, raw_title, kind, companions, bytes).
    Caller deve cleanup_expand_staging(expand_stats).
    """
    from core.archive_roms import expand_rom_sources

    jobs: list[tuple] = []
    skipped = 0
    expand_stats: dict = {}
    rom_paths, expand_errors, expand_stats = expand_rom_sources(
        list(host_paths), IMPORTABLE_EXTS
    )
    mount_real = os.path.realpath(mount_path)
    for src in rom_paths:
        if not os.path.isfile(src):
            if log:
                log(f"⚠️ Ignorado (não é ficheiro): {redact_path(src)}")
            skipped += 1
            continue
        try:
            if os.path.commonpath([mount_real, src]) == mount_real:
                if log:
                    log(f"⚠️ Ignorado (já no cartão): {os.path.basename(src)}")
                skipped += 1
                continue
        except ValueError:
            pass

        name = os.path.basename(src)
        ext = os.path.splitext(name)[1].lower()
        if ext not in IMPORTABLE_EXTS and PLATFORM_BY_EXT.get(ext) is None:
            if log:
                log(f"⚠️ Extensão não suportada: {name}")
            skipped += 1
            continue

        header_info = None
        game_code = None
        raw_title = None
        kind = None
        if ext in NDS_ROM_EXTS:
            header_info = get_nds_header_info(src)
            raw_title, game_code, _uc, maker = header_info
            kind = classify_nds_kind(raw_title, game_code, maker, name, at_sd_root=False)
            if kind == "system":
                if log:
                    log(f"⚠️ Ignorado (bootloader/sistema): {name}")
                skipped += 1
                continue

        platform = detect_platform(src, name, ext, header_info=header_info, kind=kind)
        if not platform:
            if log:
                log(f"⚠️ Plataforma desconhecida: {name}")
            skipped += 1
            continue

        clean = clean_rom_filename(name, game_code)
        companions = _companion_saves_near(src)
        job_bytes = 0
        try:
            job_bytes += os.path.getsize(src)
            for c in companions:
                job_bytes += os.path.getsize(c)
        except OSError:
            pass
        jobs.append(
            (src, clean, ext, platform, game_code, raw_title, kind, companions, job_bytes)
        )
    return jobs, skipped, expand_stats, list(expand_errors)


def _remove_existing_rom_files(
    mount_path: str,
    existing_items: list[dict[str, Any]],
    log=None,
) -> None:
    """Apaga ROMs existentes (e sidecars locais) antes de substituir no import."""
    roms_root = _roms_root(mount_path)
    for item in existing_items:
        rel = item.get("rel_path") if isinstance(item, dict) else None
        if not isinstance(rel, str) or not rel.strip():
            continue
        path = _resolve_under_roms(mount_path, rel)
        if not path or not os.path.isfile(path):
            continue
        sidecars = _find_sidecars(path, roms_root)
        try:
            os.remove(path)
            if log:
                log(f"🗑️ Substituir: removido /roms/{rel}")
        except OSError as e:
            if log:
                log(f"⚠️ Não foi possível remover /roms/{rel}: {e}")
            continue
        for sc in sidecars:
            sc_rel = sc.get("rel_path")
            if not sc_rel:
                continue
            sc_path = _resolve_under_roms(mount_path, sc_rel)
            if not sc_path or not os.path.isfile(sc_path):
                continue
            try:
                os.remove(sc_path)
            except OSError:
                pass


def check_rom_import_conflicts(
    mount_path: str,
    host_paths: list,
    layout: str = "console",
    dest_rel_dir: str = "",
) -> dict[str, Any]:
    """Pré-scan de import: conflitos por chave de duplicata (sem escrever)."""
    from core.archive_roms import cleanup_expand_staging

    mode = normalize_layout(layout)
    if mode is None:
        return {"success": False, "error": f"Layout inválido: {layout!r}.", "conflicts": []}
    dest_norm = _normalize_rel_dir(dest_rel_dir) if dest_rel_dir else ""
    if dest_norm is None:
        return {"success": False, "error": "Pasta de destino inválida.", "conflicts": []}
    if dest_norm:
        forced = _resolve_under_roms(mount_path, dest_norm)
        if not forced or not os.path.isdir(forced):
            return {
                "success": False,
                "error": f"Destino /roms/{dest_norm}/ inexistente.",
                "conflicts": [],
            }
    if not isinstance(host_paths, (list, tuple)) or not host_paths:
        return {"success": False, "error": "Nenhum ficheiro seleccionado.", "conflicts": []}
    if not os.path.isdir(mount_path):
        return {"success": False, "error": "Cartão inexistente.", "conflicts": []}

    expand_stats: dict = {}
    try:
        jobs, skipped, expand_stats, expand_errors = _collect_import_jobs(
            mount_path, list(host_paths)
        )
    except Exception as e:
        return {"success": False, "error": f"Falha ao preparar ficheiros: {e}", "conflicts": []}

    try:
        if not jobs:
            return {
                "success": False,
                "error": "Nenhum ROM válido para importar.",
                "conflicts": [],
                "skipped": skipped,
                "expand_errors": expand_errors[:5],
            }
        index = _index_roms_by_dup_key(mount_path)
        conflicts: list[dict[str, Any]] = []
        for job in jobs:
            src, clean, _ext, platform, game_code, _rt, _kind, _comp, _b = job
            key = duplicate_key(platform, game_code, clean)
            if not key:
                continue
            existing = index.get(key) or []
            if not existing:
                continue
            basename = os.path.basename(src)
            conflicts.append(
                {
                    "conflict_id": conflict_id_for(key, basename),
                    "key": key,
                    "src_name": basename,
                    "display_name": clean,
                    "platform": platform,
                    "game_code": _valid_nds_tid(game_code),
                    "existing": existing,
                }
            )
        return {
            "success": True,
            "conflicts": conflicts,
            "job_count": len(jobs),
            "skipped": skipped,
            "has_conflicts": bool(conflicts),
        }
    finally:
        cleanup_expand_staging(expand_stats)


def import_roms(
    mount_path: str,
    host_paths: list,
    layout: str = "console",
    dest_rel_dir: str = "",
    log_callback=None,
    conflict_resolutions=None,
) -> tuple[bool, str, dict]:
    """
    Copia ROMs (e saves companheiros) do host para /roms/ com cópia rápida.
    Se dest_rel_dir for uma pasta existente sob /roms/, grava lá (ignora layout).
    Caso contrário usa rom_dest_dir + layout.

    conflict_resolutions: mapa conflict_id → replace|keep_both|skip.
    Sem entrada para um conflito → keep_both (comportamento histórico).
    """
    from core.archive_roms import cleanup_expand_staging

    log = lambda msg: emit_log(log_callback, msg)
    mode = normalize_layout(layout)
    if mode is None:
        return False, f"Layout inválido: {layout!r}.", {}

    resolutions = normalize_conflict_resolutions(conflict_resolutions)
    if resolutions is None:
        return False, "Resoluções de conflito inválidas.", {}

    forced_dest = None
    dest_norm = _normalize_rel_dir(dest_rel_dir) if dest_rel_dir else ""
    if dest_norm is None:
        return False, "Pasta de destino inválida.", {}
    if dest_norm:
        forced_dest = _resolve_under_roms(mount_path, dest_norm)
        if not forced_dest or not os.path.isdir(forced_dest):
            return False, f"Destino /roms/{dest_norm}/ inexistente.", {}

    if not isinstance(host_paths, (list, tuple)) or not host_paths:
        return False, "Nenhum ficheiro seleccionado.", {}

    roms_root = _roms_root(mount_path)
    os.makedirs(roms_root, exist_ok=True)

    expand_stats: dict = {}
    try:
        jobs, skipped, expand_stats, expand_errors = _collect_import_jobs(
            mount_path, list(host_paths), log=log
        )
    except Exception as e:
        return False, f"Falha ao preparar ficheiros: {e}", {}

    for err in expand_errors:
        log(f"⚠️ {err}")
        skipped += 1
    if expand_stats.get("archives"):
        log(
            f"Arquivos: {expand_stats['archives']} · "
            f"ROMs extraídas: {expand_stats.get('extracted_roms', 0)}"
        )

    if not jobs:
        cleanup_expand_staging(expand_stats)
        return False, "Nenhum ROM válido para importar.", {"skipped": skipped}

    index = _index_roms_by_dup_key(mount_path)
    # Filtrar skips e calcular bytes a copiar
    active_jobs: list[tuple] = []
    total_bytes = 0
    for job in jobs:
        src, clean, ext, platform, game_code, raw_title, kind, companions, job_bytes = job
        key = duplicate_key(platform, game_code, clean)
        cid = conflict_id_for(key, os.path.basename(src)) if key else None
        existing = index.get(key) if key else None
        resolution = "keep_both"
        if existing and cid:
            resolution = resolutions.get(cid, "keep_both")
        if resolution == "skip":
            log(f"⏭️ Ignorado (duplicata): {os.path.basename(src)}")
            skipped += 1
            continue
        active_jobs.append(
            (src, clean, ext, platform, game_code, raw_title, kind, companions, resolution, existing or [])
        )
        total_bytes += job_bytes

    if not active_jobs:
        cleanup_expand_staging(expand_stats)
        return True, f"Nada a importar ({skipped} ignorado(s)).", {
            "imported": 0,
            "skipped": skipped,
        }

    try:
        st = os.statvfs(mount_path)
        free = st.f_bavail * st.f_frsize
        if free < total_bytes + (4 * 1024 * 1024):
            need_mb = (total_bytes / (1024 * 1024)) + 4
            cleanup_expand_staging(expand_stats)
            return (
                False,
                f"Espaço insuficiente no cartão (precisa ~{need_mb:.0f} MB livres).",
                {},
            )
    except (AttributeError, OSError):
        pass

    dest_note = f"pasta=/roms/{dest_norm}/" if forced_dest else f"layout={mode}"
    log(f"=== Importar {len(active_jobs)} ROM(s) (cópia rápida, {dest_note}) ===")
    undo = UndoStack()
    imported = 0
    saves_copied = 0
    failures = 0
    bytes_copied = 0
    replaced = 0

    try:
        for i, (
            src,
            clean,
            ext,
            platform,
            game_code,
            raw_title,
            kind,
            companions,
            resolution,
            existing,
        ) in enumerate(active_jobs, start=1):
            if forced_dest:
                dest_dir = forced_dest
            else:
                franchise = None
                if platform != "apps" and mode in ("franchise", "both"):
                    franchise = detect_franchise(
                        clean,
                        game_code=game_code,
                        raw_title=raw_title,
                        original_name=os.path.basename(src),
                    )
                dest_dir = rom_dest_dir(roms_root, platform, franchise, mode)
            os.makedirs(dest_dir, exist_ok=True)

            out_ext = ext
            if out_ext == ".ids":
                out_ext = ".nds"
            if out_ext == ".app":
                out_ext = ".dsi"

            intended = os.path.join(dest_dir, f"{clean}{out_ext}")
            if resolution == "replace" and existing:
                _remove_existing_rom_files(mount_path, existing, log=log)
                replaced += len(existing)
                dest = intended
            else:
                dest = _unique_path(intended)

            try:
                n = copy_fast(src, dest, log_callback=log_callback)
                undo.push_remove(dest)
                bytes_copied += n
                imported += 1
                try:
                    rel = os.path.relpath(dest, roms_root).replace("\\", "/")
                except ValueError:
                    rel = os.path.basename(dest)
                log(f"📥 [{i}/{len(active_jobs)}] {os.path.basename(src)} ➔ /roms/{rel}")
            except Exception as e:
                failures += 1
                log(f"⚠️ Falha ao copiar {os.path.basename(src)}: {e}")
                continue

            final_stem = os.path.splitext(os.path.basename(dest))[0]
            for sav_src in companions:
                sav_ext = os.path.splitext(sav_src)[1].lower()
                sav_dest = _unique_path(os.path.join(dest_dir, f"{final_stem}{sav_ext}"))
                try:
                    n = copy_fast(sav_src, sav_dest, log_callback=log_callback)
                    undo.push_remove(sav_dest)
                    bytes_copied += n
                    saves_copied += 1
                    log(
                        f"💾 Save ➔ /roms/{os.path.relpath(sav_dest, roms_root).replace(chr(92), '/')}"
                    )
                except Exception as e:
                    failures += 1
                    log(f"⚠️ Falha ao copiar save: {e}")

        sync_volume(mount_path)
    except Exception as e:
        log(f"⚠️ Erro na importação — a reverter cópias deste lote…")
        undo.rollback(log_callback=log_callback, mount_path=mount_path)
        cleanup_expand_staging(expand_stats)
        return False, f"Importação falhou: {e}", {"imported": 0}

    if imported == 0 and failures:
        undo.rollback(log_callback=log_callback, mount_path=mount_path)
        cleanup_expand_staging(expand_stats)
        return False, f"Nenhum ficheiro copiado ({failures} erro(s)).", {"failures": failures}

    mb = bytes_copied / (1024 * 1024)
    msg = (
        f"{imported} jogo(s) importado(s) ({mb:.1f} MB)"
        + (f", {saves_copied} save(s)" if saves_copied else "")
        + (f"; {replaced} substituído(s)" if replaced else "")
        + (f"; {skipped} ignorado(s)" if skipped else "")
        + (f"; {failures} falha(s)" if failures else "")
        + "."
    )
    if expand_stats.get("archives"):
        msg = msg.rstrip(".") + f"; {expand_stats['archives']} arquivo(s)."
    log(f"✅ {msg}")
    ok = imported > 0
    cleanup_expand_staging(expand_stats)
    return ok, msg, {
        "imported": imported,
        "saves": saves_copied,
        "skipped": skipped,
        "failures": failures,
        "bytes": bytes_copied,
        "replaced": replaced,
        "archives": expand_stats.get("archives", 0),
    }


def _twilight_asset_dir(mount_path: str, kind: str) -> str:
    """kind: boxart | icons"""
    name = "boxart" if kind == "boxart" else "icons"
    return os.path.join(mount_path, "_nds", "TWiLightMenu", name)


def _boxart_path(mount_path: str, game_code: Optional[str]) -> Optional[str]:
    """Capa por TID (se existir no cartão)."""
    code = _valid_nds_tid(game_code)
    if not code:
        return None
    path = os.path.join(_twilight_asset_dir(mount_path, "boxart"), f"{code}.png")
    return path if os.path.isfile(path) else None


def _boxart_candidates(mount_path: str, rom_basename: str, game_code: Optional[str]) -> list[str]:
    """Candidatos de capa: TID.png depois {filename.ext}.png."""
    box_dir = _twilight_asset_dir(mount_path, "boxart")
    out: list[str] = []
    code = _valid_nds_tid(game_code)
    if code:
        out.append(os.path.join(box_dir, f"{code}.png"))
    if rom_basename:
        out.append(os.path.join(box_dir, f"{rom_basename}.png"))
    return out


def _resolve_boxart_file(
    mount_path: str, rom_basename: str, game_code: Optional[str]
) -> Optional[str]:
    for path in _boxart_candidates(mount_path, rom_basename, game_code):
        if os.path.isfile(path):
            return path
    return None


def _custom_icon_path(mount_path: str, rom_basename: str) -> Optional[str]:
    if not rom_basename:
        return None
    path = os.path.join(_twilight_asset_dir(mount_path, "icons"), f"{rom_basename}.png")
    return path if os.path.isfile(path) else None


def _is_png_file(path: str, max_bytes: int = MAX_ARTWORK_BYTES) -> tuple[bool, str]:
    if not isinstance(path, str) or not path.strip():
        return False, "Caminho de imagem inválido."
    if not os.path.isfile(path):
        return False, "Ficheiro de imagem inexistente."
    try:
        size = os.path.getsize(path)
    except OSError as e:
        return False, f"Não foi possível ler a imagem: {e}"
    if size <= 0:
        return False, "Imagem vazia."
    if size > max_bytes:
        return False, f"Imagem demasiado grande (máx. {max_bytes // (1024 * 1024)} MB)."
    try:
        with open(path, "rb") as f:
            magic = f.read(8)
    except OSError as e:
        return False, f"Não foi possível ler a imagem: {e}"
    if magic != PNG_MAGIC:
        return False, "Só são aceites ficheiros PNG."
    return True, ""


def _png_data_url(path: Optional[str]) -> Optional[str]:
    if not path or not os.path.isfile(path):
        return None
    try:
        size = os.path.getsize(path)
        if size <= 0 or size > MAX_PREVIEW_BYTES:
            return None
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return None
    if not data.startswith(PNG_MAGIC):
        return None
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def run_info_for_platform(platform: Optional[str]) -> dict[str, Any]:
    plat = (platform or "").strip().lower()
    info = RUN_INFO_BY_PLATFORM.get(plat)
    if info:
        return {
            "title": info["title"],
            "body": info["body"],
            "requirements": list(info["requirements"]),
        }
    label = plat.upper() if plat else "desconhecida"
    return {
        "title": f"Plataforma {label}",
        "body": (
            "O TWiLight Menu++ tenta abrir este ficheiro com o emulador "
            "associado à pasta/extensão, se o add-on Virtual Console estiver instalado."
        ),
        "requirements": ["TWiLight Menu++"],
    }


def _artwork_dest_path(
    mount_path: str,
    rom_basename: str,
    game_code: Optional[str],
    kind: str,
) -> Optional[str]:
    if kind == "icon":
        if not rom_basename:
            return None
        return os.path.join(_twilight_asset_dir(mount_path, "icons"), f"{rom_basename}.png")
    if kind == "boxart":
        code = _valid_nds_tid(game_code)
        if code:
            return os.path.join(_twilight_asset_dir(mount_path, "boxart"), f"{code}.png")
        if rom_basename:
            return os.path.join(
                _twilight_asset_dir(mount_path, "boxart"), f"{rom_basename}.png"
            )
    return None


def rom_details(mount_path: str, rel_path: str) -> dict[str, Any]:
    """Metadados + capa/ícone TWiLight + como corre (só leitura)."""
    if not os.path.isdir(mount_path):
        return {"success": False, "error": "Cartão inexistente."}
    if not isinstance(rel_path, str) or not rel_path.strip():
        return {"success": False, "error": "Caminho do jogo inválido."}

    roms_root = _roms_root(mount_path)
    full = _resolve_under_roms(mount_path, rel_path.replace("\\", "/").lstrip("/"))
    if not full or not os.path.isfile(full):
        return {"success": False, "error": "Jogo não encontrado em /roms/."}

    entry = _file_entry(full, roms_root)
    if not entry:
        return {"success": False, "error": "Ficheiro não é uma ROM listável."}

    basename = os.path.basename(full)
    game_code = entry.get("game_code")
    box_file = _resolve_boxart_file(mount_path, basename, game_code)
    icon_file = _custom_icon_path(mount_path, basename)
    banner_icon = entry.get("icon")

    box_rel = None
    if box_file:
        try:
            box_rel = os.path.relpath(box_file, mount_path).replace("\\", "/")
        except ValueError:
            box_rel = None
    icon_rel = None
    if icon_file:
        try:
            icon_rel = os.path.relpath(icon_file, mount_path).replace("\\", "/")
        except ValueError:
            icon_rel = None

    return {
        "success": True,
        "rom": entry,
        "boxart": _png_data_url(box_file),
        "boxart_rel": box_rel,
        "custom_icon": _png_data_url(icon_file),
        "custom_icon_rel": icon_rel,
        "display_icon": _png_data_url(icon_file) or banner_icon,
        "run_info": run_info_for_platform(entry.get("platform")),
        "hints": {
            "boxart": (
                "PNG recomendado ~128×115 (NDS) ou proporção de capa da plataforma. "
                "Guardado em /_nds/TWiLightMenu/boxart/."
            ),
            "icon": (
                "PNG 32×32 com ≤15 cores + transparência para o TWiLight converter bem. "
                "Guardado em /_nds/TWiLightMenu/icons/{nome.ext}.png."
            ),
        },
    }


def set_rom_artwork(
    mount_path: str,
    rel_path: str,
    kind: str,
    source_path: str,
    log_callback=None,
) -> tuple[bool, str, dict]:
    """
    Copia PNG do PC para boxart/ ou icons/ do TWiLight (verify + replace).
    kind: 'boxart' | 'icon'
    """
    log = lambda msg: emit_log(log_callback, msg)
    if not isinstance(kind, str) or kind not in ARTWORK_KINDS:
        return False, "Tipo de arte inválido (boxart ou icon).", {}
    if not isinstance(rel_path, str) or not rel_path.strip():
        return False, "Caminho do jogo inválido.", {}

    full = _resolve_under_roms(mount_path, rel_path.replace("\\", "/").lstrip("/"))
    if not full or not os.path.isfile(full):
        return False, "Jogo não encontrado em /roms/.", {}

    ok_png, png_err = _is_png_file(source_path)
    if not ok_png:
        return False, png_err, {}

    basename = os.path.basename(full)
    game_code = None
    ext = os.path.splitext(basename)[1].lower()
    if ext in (".nds", ".dsi", ".ids", ".app", ".srl"):
        _t, game_code, _u, _m = get_nds_header_info(full)

    dest = _artwork_dest_path(mount_path, basename, game_code, kind)
    if not dest:
        return False, "Não foi possível determinar o destino da arte.", {}

    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        copy_verified(source_path, dest, log_callback=log_callback)
        sync_volume(mount_path)
    except Exception as e:
        return False, f"Falha ao gravar arte: {e}", {}

    try:
        rel_asset = os.path.relpath(dest, mount_path).replace("\\", "/")
    except ValueError:
        rel_asset = os.path.basename(dest)

    label = "capa" if kind == "boxart" else "ícone"
    msg = f"{label.capitalize()} actualizada ➔ /{rel_asset}"
    log(f"✅ {msg}")
    return True, msg, {
        "kind": kind,
        "dest_rel": rel_asset,
        "preview": _png_data_url(dest),
    }


def _remove_empty_parents(path: str, stop_dir: str) -> None:
    """Remove pastas vazias até stop_dir (exclusive)."""
    try:
        stop = os.path.realpath(stop_dir)
        current = os.path.dirname(os.path.realpath(path))
    except OSError:
        return
    while True:
        try:
            if os.path.normcase(current) == os.path.normcase(stop):
                break
            if not current.startswith(stop):
                break
            os.rmdir(current)
            current = os.path.dirname(current)
        except OSError:
            break


def _cleanup_ghosts_near(rom_path: str) -> int:
    """Remove .partial / AppleDouble fantasma ao lado da ROM."""
    parent = os.path.dirname(rom_path)
    base = os.path.basename(rom_path)
    removed = 0
    ghosts = [
        rom_path + ".partial",
        os.path.join(parent, "._" + base),
        os.path.join(parent, ".DS_Store"),
    ]
    for g in ghosts:
        if os.path.isfile(g):
            try:
                os.remove(g)
                removed += 1
            except OSError:
                pass
    return removed


def delete_roms(
    mount_path: str,
    rel_paths: list,
    save_mode: str = "delete",
    backup_dir: str = "",
    remove_boxart: bool = True,
    log_callback=None,
) -> tuple[bool, str, dict]:
    """
    Remove ROMs de /roms/ e trata saves conforme save_mode:
    - delete: apaga saves/sidecars
    - backup: copia saves para backup_dir (ou pasta padrão) e apaga no SD
    - keep: move saves para /roms/saves/
    """
    log = lambda msg: emit_log(log_callback, msg)
    mode = normalize_save_mode(save_mode)
    if mode is None:
        return False, f"Modo de save inválido: {save_mode!r}.", {}

    if not isinstance(rel_paths, (list, tuple)) or not rel_paths:
        return False, "Nenhum jogo seleccionado.", {}

    roms_root = _roms_root(mount_path)
    if not os.path.isdir(roms_root):
        return False, "Pasta /roms/ inexistente.", {}

    host_backup = ""
    if mode == "backup":
        if isinstance(backup_dir, str) and backup_dir.strip():
            host_backup = backup_dir.strip()
        else:
            host_backup = default_saves_backup_dir()
        try:
            os.makedirs(host_backup, exist_ok=True)
        except OSError as e:
            return False, f"Não foi possível criar pasta de backup: {e}", {}
        log(f"Backup de saves em: {redact_path(host_backup)}")

    keep_dir = os.path.join(roms_root, "saves")
    deleted = 0
    saves_deleted = 0
    saves_backed = 0
    saves_kept = 0
    ghosts = 0
    boxarts = 0
    failures = 0

    log(f"=== Remover {len(rel_paths)} item(ns) (saves={mode}) ===")

    for rel in rel_paths:
        if not isinstance(rel, str):
            failures += 1
            continue
        rom_path = _resolve_under_roms(mount_path, rel)
        if not rom_path or not os.path.isfile(rom_path):
            log(f"⚠️ Não encontrado: {rel}")
            failures += 1
            continue

        ext = os.path.splitext(rom_path)[1].lower()
        if is_save_ext(ext) or is_companion_ext(ext):
            log(f"⚠️ Ignorado (é um save/sidecar, não ROM): {rel}")
            failures += 1
            continue

        game_code = None
        if ext in (".nds", ".dsi", ".ids", ".app", ".srl"):
            _t, game_code, _u, _m = get_nds_header_info(rom_path)

        sidecars = _find_sidecars(rom_path, roms_root)
        stem = os.path.splitext(os.path.basename(rom_path))[0]

        # Tratar saves primeiro
        for sc in sidecars:
            sc_path = _resolve_under_roms(mount_path, sc["rel_path"])
            if not sc_path or not os.path.isfile(sc_path):
                continue
            is_save = bool(sc.get("is_save"))
            try:
                if mode == "keep" and is_save:
                    os.makedirs(keep_dir, exist_ok=True)
                    dest = _unique_path(os.path.join(keep_dir, os.path.basename(sc_path)))
                    if os.path.abspath(sc_path) != os.path.abspath(dest):
                        shutil.move(sc_path, dest)
                    saves_kept += 1
                    log(f"💾 Save mantido ➔ /roms/saves/{os.path.basename(dest)}")
                elif mode == "backup" and is_save:
                    dest_dir = os.path.join(host_backup, stem)
                    os.makedirs(dest_dir, exist_ok=True)
                    dest = _unique_path(os.path.join(dest_dir, os.path.basename(sc_path)))
                    copy_fast(sc_path, dest)
                    os.remove(sc_path)
                    saves_backed += 1
                    log(f"💾 Save backup ➔ {redact_path(dest)}")
                else:
                    # delete mode, ou sidecar não-save em qualquer modo
                    os.remove(sc_path)
                    if is_save:
                        saves_deleted += 1
                    log(f"🗑️ Removido sidecar: {sc['rel_path']}")
            except Exception as e:
                failures += 1
                log(f"⚠️ Falha no sidecar {sc.get('name')}: {e}")

        ghosts += _cleanup_ghosts_near(rom_path)

        try:
            os.remove(rom_path)
            deleted += 1
            log(f"🗑️ Removido: /roms/{rel}")
        except Exception as e:
            failures += 1
            log(f"⚠️ Falha ao apagar {rel}: {e}")
            continue

        if remove_boxart:
            ba = _boxart_path(mount_path, game_code)
            if ba:
                try:
                    os.remove(ba)
                    boxarts += 1
                except OSError:
                    pass

        _remove_empty_parents(rom_path, roms_root)

    # Limpar .partial órfãos sob /roms/
    for root, _dirs, files in os.walk(roms_root):
        for name in files:
            if name.endswith(".partial") or name.startswith("._"):
                try:
                    os.remove(os.path.join(root, name))
                    ghosts += 1
                except OSError:
                    pass

    try:
        sync_volume(mount_path)
    except Exception:
        pass

    parts = [f"{deleted} jogo(s) removido(s)"]
    if saves_deleted:
        parts.append(f"{saves_deleted} save(s) apagado(s)")
    if saves_backed:
        parts.append(f"{saves_backed} save(s) em backup")
    if saves_kept:
        parts.append(f"{saves_kept} save(s) em /roms/saves/")
    if boxarts:
        parts.append(f"{boxarts} capa(s)")
    if ghosts:
        parts.append(f"{ghosts} residual(is) limpo(s)")
    if failures:
        parts.append(f"{failures} falha(s)")
    msg = "; ".join(parts) + "."
    log(f"✅ {msg}")
    ok = deleted > 0 or (not rel_paths)
    if deleted == 0 and failures:
        return False, msg, {"deleted": 0, "failures": failures}
    return True, msg, {
        "deleted": deleted,
        "saves_deleted": saves_deleted,
        "saves_backed": saves_backed,
        "saves_kept": saves_kept,
        "boxarts": boxarts,
        "ghosts": ghosts,
        "failures": failures,
        "backup_dir": redact_path(host_backup) if host_backup else "",
    }
