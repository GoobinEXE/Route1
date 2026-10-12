"""Pacote DSPico: Pico Launcher + Loader oficiais LNH, Games/, emunand, settings, UF2."""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import tempfile
import time
import zipfile
from typing import Any, Optional

from core.cache import (
    CACHE_DIR,
    DSPICO_CACHE_KEYS,
    PIN_META,
    dspico_firmware_uf2_ready,
    ensure_cached,
    ensure_cache_dir,
)
from core.dspico_emulators import (
    count_installed_emulators,
    retro_platform_map,
    retro_rom_dirs_map,
)
from core.logging_util import emit_log
from core.privacy import redact_path
from core.rom_cleaner import (
    JUNK_EXTS,
    SKIP_DIR_NAMES,
    SYSTEM_ROOT_NAMES,
    UNKNOWN_FRANCHISE,
    classify_nds_kind,
    clean_rom_filename,
    companion_index_keys,
    detect_franchise,
    get_nds_header_info,
    is_companion_ext,
)
from core.rom_manager import (
    conflict_id_for,
    duplicate_key,
    normalize_conflict_resolutions,
)
from core.sdio import UndoStack, copy_fast, sync_volume
from core.twilight import _cleanup_baks, _is_safe_archive_member, _stage_dir_copy, _stage_file_copy

# --- Fontes oficiais (LNH-team + manual de referência) ----------------------

LNH_ORG = "LNH-team"
LNH_GITHUB_PREFIX = f"https://github.com/{LNH_ORG}/"

# Manual de utilizador ChiScart (quick start / FAQ) — referência junto ao GUIDE LNH.
DSPICO_USER_MANUAL_URL = (
    "https://www.chiscart.com/manuals/DS_Pico_user_manual_87a632eec6.pdf"
)

DSPICO_OFFICIAL_LINKS = {
    "dspico_user_manual": DSPICO_USER_MANUAL_URL,
    "pico_launcher": f"{LNH_GITHUB_PREFIX}pico-launcher",
    "pico_loader": f"{LNH_GITHUB_PREFIX}pico-loader",
    "dspico_firmware": f"{LNH_GITHUB_PREFIX}dspico-firmware",
    "dspico_hardware": f"{LNH_GITHUB_PREFIX}dspico-hardware",
    "dspico_guide": f"{LNH_GITHUB_PREFIX}dspico/blob/develop/GUIDE.md",
    "pico_launcher_usage": (
        f"{LNH_GITHUB_PREFIX}pico-launcher/blob/develop/docs/Usage.md"
    ),
}

GAMES_DIRNAME = "Games"
APPS_DIRNAME = "Apps"
ROMS_DIRNAME = "ROMs"  # legado / BIOS de emuladores; organize não promove jogos aqui
GAME_EXTS = frozenset({".nds", ".dsi", ".ids", ".srl", ".app"})
# Extensão → pasta Games/<plat>/ — derivado do catálogo de emuladores Pico.
_RETRO_PLATFORM: dict[str, str] = retro_platform_map()
RETRO_EXTS = frozenset(_RETRO_PLATFORM.keys())
# Legado: pastas /ROMs/… que o instalador ainda cria (BIOS / ROMPath).
RETRO_ROM_DIRS: dict[str, str] = retro_rom_dirs_map()
IMPORT_EXTS = GAME_EXTS | RETRO_EXTS
LIBRARY_FILE_EXTS = GAME_EXTS | RETRO_EXTS
SETTINGS_FILENAME = "settings.json"


def _emit_import_progress(payload: dict) -> None:
    """Push best-effort para a barra de progresso da UI."""
    from core.progress import emit_progress

    emit_progress(payload)


def _unique_dest_path(dest_dir: str, base_name: str) -> str:
    dest = os.path.join(dest_dir, base_name)
    if not os.path.exists(dest):
        return dest
    stem, ext = os.path.splitext(base_name)
    n = 2
    while True:
        cand = os.path.join(dest_dir, f"{stem}_{n}{ext}")
        if not os.path.exists(cand):
            return cand
        n += 1


def _apps_root(mount_path: str) -> str:
    return os.path.join(_games_root(mount_path), APPS_DIRNAME)


def _nds_out_ext(ext: str) -> str:
    """Normaliza extensão NDS/DSi à saída (.ids/.srl → .nds, .app → .dsi)."""
    low = (ext or "").lower()
    if low in (".ids", ".srl"):
        return ".nds"
    if low == ".app":
        return ".dsi"
    return low


def _dest_dir_for_import(
    mount_path: str,
    ext: str,
    games_dest_dir: str,
    *,
    nds_kind: Optional[str] = None,
) -> tuple[Optional[str], Optional[str]]:
    """
    Devolve (dest_dir, bucket) onde bucket é 'games' | 'apps' | 'retro'.
    NDS/DSi e retro vão para Games/ (apps → Games/Apps/).
    """
    low = (ext or "").lower()
    if low in GAME_EXTS:
        if nds_kind == "app":
            return _apps_root(mount_path), "apps"
        return games_dest_dir, "games"
    if low in RETRO_EXTS:
        return games_dest_dir, "retro"
    return None, None

# Layouts de organização DSPico (escolha do utilizador)
LAYOUT_FRANCHISE = "franchise"  # Games/<franquia>/
LAYOUT_PLATFORM = "platform"  # Games/nds/ ou Games/dsi/
LAYOUT_GAMES = "games"  # soltos em Games/
LAYOUT_ROOT = "root"  # soltos na raiz ao lado do launcher
LAYOUT_MODES = frozenset(
    {LAYOUT_FRANCHISE, LAYOUT_PLATFORM, LAYOUT_GAMES, LAYOUT_ROOT}
)
LAYOUT_ALIASES = {
    "console": LAYOUT_PLATFORM,
    "plataforma": LAYOUT_PLATFORM,
    "franquia": LAYOUT_FRANCHISE,
    "flat": LAYOUT_GAMES,
    "loose": LAYOUT_GAMES,
    "games_flat": LAYOUT_GAMES,
    "sd_root": LAYOUT_ROOT,
    "raiz": LAYOUT_ROOT,
    "launcher": LAYOUT_ROOT,
}

# Pastas/ficheiros essenciais do pacote DSPico (+ emunand + emuladores Pico)
_KEEP_DIR_NAMES = frozenset(
    {
        "_pico",
        "games",
        "photo",
        "shared1",
        "shared2",
        "sys",
        "roms",
        "_gba",
        "emulators",
        "data",
        "system volume information",
        ".trash",
        ".trashes",
        ".fseventsd",
        ".spotlight-v100",
    }
)
_KEEP_ROOT_FILES = frozenset({"_picoboot.nds", "snemul.cfg"})
_PICOBOOT_NAME = "_picoboot.nds"

# Não descer nestas pastas ao recolher (sistema DSPico / emunand / emuladores).
# Pastas estrangeiras (_nds, MOONSHL, …) e ROMs/ SÃO varridas para migrar jogos.
_COLLECT_SKIP_DIRS = frozenset(
    {
        "_pico",
        "photo",
        "shared1",
        "shared2",
        "sys",
        "title",
        "ticket",
        "private",
        "emulators",
        "_gba",
        "data",
        "system volume information",
        ".trash",
        ".trashes",
        ".fseventsd",
        ".spotlight-v100",
    }
)
_SKIP_DIR_LOWER = frozenset(s.lower() for s in SKIP_DIR_NAMES)

SETTINGS_ALLOWED_KEYS = frozenset(
    {
        "language",
        "romBrowserLayout",
        "romBrowserSortMode",
        "theme",
        "lastUsedFilePath",
        "fileAssociations",
    }
)
SETTINGS_LAYOUTS = frozenset(
    {
        "Horizontal",
        "Vertical",
        "BannerList",
        "Coverflow",
    }
)
SETTINGS_SORT_MODES = frozenset({"NameAscending", "NameDescending"})

EMUNAND_DIRS = (
    "photo",
    "shared1",
    os.path.join("shared2", "0000"),
    "sys",
)

_RP2_NAMES = frozenset({"rpi-rp2", "rp2350"})
_DIR_NAME_RE = re.compile(r'[<>:"/\\|?*\x00]')


def official_links() -> dict[str, str]:
    """URLs oficiais LNH + manual de referência ChiScart para a UI (allowlist)."""
    return dict(DSPICO_OFFICIAL_LINKS)


def pinned_package_versions() -> dict[str, Any]:
    """Tags/assets pinados dos pacotes DSPico."""
    out: dict[str, Any] = {}
    for key in ("pico_launcher", "pico_loader_dspico"):
        meta = PIN_META.get(key) or {}
        out[key] = {
            "repo": meta.get("repo"),
            "tag": meta.get("tag"),
            "asset": meta.get("asset"),
            "cache_key": key,
        }
    out["dspico_firmware_uf2"] = {
        "repo": f"{LNH_ORG}/dspico-firmware",
        "ready": dspico_firmware_uf2_ready(),
        "cache_key": "dspico_firmware_uf2",
        "note": (
            None
            if dspico_firmware_uf2_ready()
            else "Asset .uf2 ainda não publicado nas releases oficiais LNH."
        ),
    }
    return out


def assert_dspico_cache_key(key: str) -> None:
    if key not in DSPICO_CACHE_KEYS:
        raise ValueError(f"Chave de cache DSPico não allowlisted: {key!r}")


def dspico_markers_ok(mount_path: str) -> bool:
    """True se o SD tem o layout mínimo do Pico Launcher para DSPico."""
    return (
        os.path.isfile(os.path.join(mount_path, "_picoboot.nds"))
        and os.path.isfile(os.path.join(mount_path, "_pico", "picoLoader7.bin"))
        and os.path.isfile(os.path.join(mount_path, "_pico", "picoLoader9.bin"))
    )


def _games_root(mount_path: str) -> str:
    return os.path.join(mount_path, GAMES_DIRNAME)


def _pico_dir(mount_path: str) -> str:
    return os.path.join(mount_path, "_pico")


def _normalize_rel_dir(rel_dir) -> Optional[str]:
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


def _resolve_under_games(mount_path: str, rel_path: str) -> Optional[str]:
    """Resolve rel_path sob Games/; None se path traversal."""
    if not isinstance(rel_path, str):
        return None
    if "\x00" in rel_path:
        return None
    rel = rel_path.replace("\\", "/").lstrip("/")
    games = os.path.realpath(_games_root(mount_path))
    if not rel:
        return games
    if rel.startswith("..") or "/../" in f"/{rel}/":
        return None
    candidate = os.path.realpath(os.path.join(games, *rel.split("/")))
    try:
        common = os.path.commonpath([games, candidate])
    except ValueError:
        return None
    if os.path.normcase(common) != os.path.normcase(games):
        return None
    return candidate


def _sanitize_dir_name(name: str) -> str:
    cleaned = _DIR_NAME_RE.sub("", name or "").strip(" .")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:60]


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


# Cache curto: inspect/browse no USB MSC evitam walks repetidos na mesma sessão.
_GAMES_COUNT_CACHE: dict[str, tuple[float, int]] = {}
_GAMES_COUNT_TTL_S = 5.0
_DUP_INDEX_CACHE: dict[str, tuple[float, dict[str, list[dict[str, Any]]]]] = {}
_DUP_INDEX_TTL_S = 30.0


def invalidate_dspico_library_caches(mount_path: Optional[str] = None) -> None:
    """Invalida contagens/índices após escrita na biblioteca DSPico."""
    if mount_path is None:
        _GAMES_COUNT_CACHE.clear()
        _DUP_INDEX_CACHE.clear()
        return
    try:
        key = os.path.realpath(mount_path)
    except OSError:
        key = mount_path
    _GAMES_COUNT_CACHE.pop(key, None)
    _DUP_INDEX_CACHE.pop(key, None)


def _count_games(mount_path: str) -> int:
    """Conta jogos (NDS + retro) em Games/ e soltos na raiz (exceto launcher)."""
    try:
        cache_key = os.path.realpath(mount_path)
    except OSError:
        cache_key = mount_path
    now = time.monotonic()
    hit = _GAMES_COUNT_CACHE.get(cache_key)
    if hit and now - hit[0] < _GAMES_COUNT_TTL_S:
        return hit[1]

    n = 0
    root = _games_root(mount_path)
    if os.path.isdir(root):
        for walk_root, dirs, files in os.walk(root):
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".") and d.lower() not in _SKIP_DIR_LOWER
            ]
            for f in files:
                if f.startswith(".") or f.endswith(".partial"):
                    continue
                if os.path.splitext(f)[1].lower() in LIBRARY_FILE_EXTS:
                    n += 1
    try:
        for f in os.listdir(mount_path):
            if _is_picoboot(f) or f.startswith("."):
                continue
            full = os.path.join(mount_path, f)
            if not os.path.isfile(full):
                continue
            if os.path.splitext(f)[1].lower() in LIBRARY_FILE_EXTS:
                n += 1
    except OSError:
        pass
    _GAMES_COUNT_CACHE[cache_key] = (now, n)
    return n


def inspect_dspico(mount_path: str) -> dict[str, Any]:
    """Relatório estruturado do microSD DSPico (só leitura)."""
    if not isinstance(mount_path, str) or not mount_path.strip():
        return {"success": False, "error": "Caminho do cartão inválido."}
    if not os.path.isdir(mount_path):
        return {"success": False, "error": "Cartão inexistente."}

    pico = _pico_dir(mount_path)
    files = {
        "picoboot": os.path.isfile(os.path.join(mount_path, "_picoboot.nds")),
        "picoLoader7": os.path.isfile(os.path.join(pico, "picoLoader7.bin")),
        "picoLoader9": os.path.isfile(os.path.join(pico, "picoLoader9.bin")),
        "aplist": os.path.isfile(os.path.join(pico, "aplist.bin")),
        "savelist": os.path.isfile(os.path.join(pico, "savelist.bin")),
        "patchlist": os.path.isfile(os.path.join(pico, "patchlist.bin")),
        "biosnds7": os.path.isfile(os.path.join(pico, "biosnds7.rom")),
        "settings": os.path.isfile(os.path.join(pico, SETTINGS_FILENAME)),
        "twl_font": os.path.isfile(
            os.path.join(mount_path, "sys", "TWLFontTable.dat")
        ),
    }
    emunand = {
        "photo": os.path.isdir(os.path.join(mount_path, "photo")),
        "shared1": os.path.isdir(os.path.join(mount_path, "shared1")),
        "shared2_0000": os.path.isdir(
            os.path.join(mount_path, "shared2", "0000")
        ),
        "sys": os.path.isdir(os.path.join(mount_path, "sys")),
    }
    markers_ok = dspico_markers_ok(mount_path)
    games_count = _count_games(mount_path)
    settings_summary: Optional[dict[str, Any]] = None
    if files["settings"]:
        try:
            raw = get_dspico_settings(mount_path)
            if raw.get("success"):
                settings_summary = {
                    k: raw["settings"].get(k)
                    for k in (
                        "language",
                        "romBrowserLayout",
                        "romBrowserSortMode",
                        "theme",
                    )
                    if k in (raw.get("settings") or {})
                }
        except Exception:
            settings_summary = None

    checklist = [
        {"id": "picoboot", "ok": files["picoboot"], "label": "_picoboot.nds"},
        {
            "id": "loader",
            "ok": files["picoLoader7"] and files["picoLoader9"],
            "label": "Pico Loader (7/9)",
        },
        {
            "id": "lists",
            "ok": files["aplist"] and files["savelist"],
            "label": "aplist + savelist",
        },
        {"id": "games_dir", "ok": os.path.isdir(_games_root(mount_path)), "label": "Games/"},
        {
            "id": "bios",
            "ok": files["biosnds7"],
            "label": "biosnds7.rom (DSiWare / secure area)",
            "optional": True,
        },
        {
            "id": "emunand",
            "ok": all(emunand.values()) and files["twl_font"],
            "label": "Emunand DSiWare",
            "optional": True,
        },
    ]

    emu_info = count_installed_emulators(mount_path)
    checklist.append(
        {
            "id": "emulators",
            "ok": bool(emu_info.get("ok")),
            "label": (
                f"Emuladores ({emu_info.get('argv_nds', 0)} argv, "
                f"{emu_info.get('manual_nds', 0)} manuais, "
                f"{emu_info.get('associations', 0)} associações)"
            ),
            "optional": True,
        }
    )

    return {
        "success": True,
        "has_dspico": markers_ok,
        "markers_ok": markers_ok,
        "files": files,
        "emunand": emunand,
        "games_count": games_count,
        "games_dir": GAMES_DIRNAME,
        "settings_summary": settings_summary,
        "emulators": emu_info,
        "checklist": checklist,
        "packages": pinned_package_versions(),
        "firmware_uf2_ready": dspico_firmware_uf2_ready(),
        "official_links": official_links(),
    }


def _extract_zip_safe(archive_path: str, extract_dir: str, log_callback=None) -> str:
    """Extrai zip com validação anti zip-slip; devolve o diretório de extração."""
    emit_log(log_callback, f"Extraindo {os.path.basename(archive_path)}...")
    ensure_cache_dir()
    os.makedirs(extract_dir, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=CACHE_DIR, prefix="zip_extract_") as tmp:
        with zipfile.ZipFile(archive_path, "r") as zf:
            for info in zf.infolist():
                name = info.filename
                if not _is_safe_archive_member(name, tmp):
                    raise RuntimeError(f"Zip rejeitado (caminho inseguro): {name!r}")
            zf.extractall(tmp)

        root_real = os.path.realpath(tmp)
        for walk_root, dirs, files in os.walk(tmp):
            for name in dirs + files:
                full = os.path.join(walk_root, name)
                real = os.path.realpath(full)
                try:
                    common = os.path.commonpath([root_real, real])
                except ValueError as e:
                    raise RuntimeError(f"Extração zip escapou do diretório: {full}") from e
                if common != root_real:
                    raise RuntimeError(f"Extração zip escapou do diretório: {full}")
                if os.path.islink(full):
                    raise RuntimeError(f"Symlink rejeitado na extração: {full}")

        staging = extract_dir.rstrip("/\\") + f".staging_{os.getpid()}"
        old = extract_dir.rstrip("/\\") + ".bak_promote"
        try:
            if os.path.isdir(staging):
                shutil.rmtree(staging, ignore_errors=True)
            if os.path.isdir(old):
                shutil.rmtree(old, ignore_errors=True)
            shutil.copytree(tmp, staging)
            if os.path.isdir(extract_dir):
                os.rename(extract_dir, old)
            os.rename(staging, extract_dir)
            if os.path.isdir(old):
                shutil.rmtree(old, ignore_errors=True)
        except Exception:
            if os.path.isdir(staging):
                shutil.rmtree(staging, ignore_errors=True)
            if not os.path.isdir(extract_dir) and os.path.isdir(old):
                try:
                    os.rename(old, extract_dir)
                except OSError:
                    try:
                        shutil.copytree(old, extract_dir)
                        shutil.rmtree(old, ignore_errors=True)
                    except OSError:
                        pass
            raise

    return extract_dir


def _find_file(root: str, names: tuple[str, ...]) -> Optional[str]:
    """Procura ficheiro por nome (case-insensitive) sob root."""
    wanted = {n.lower() for n in names}
    for walk_root, _dirs, files in os.walk(root):
        for f in files:
            if f.lower() in wanted:
                return os.path.join(walk_root, f)
    return None


def _find_dir(root: str, dirname: str) -> Optional[str]:
    target = dirname.lower()
    for walk_root, dirs, _files in os.walk(root):
        for d in dirs:
            if d.lower() == target:
                return os.path.join(walk_root, d)
    direct = os.path.join(root, dirname)
    if os.path.isdir(direct):
        return direct
    return None


def _assemble_dspico_staging(launcher_dir: str, loader_dir: str, staging: str) -> None:
    """Monta a árvore final DSPico em staging."""
    if os.path.isdir(staging):
        shutil.rmtree(staging)
    os.makedirs(staging, exist_ok=True)

    launcher_nds = _find_file(launcher_dir, ("LAUNCHER.nds", "_picoboot.nds"))
    if not launcher_nds:
        raise RuntimeError("LAUNCHER.nds não encontrado no pacote Pico Launcher.")

    pico_src = _find_dir(launcher_dir, "_pico")
    if not pico_src:
        pico_src = os.path.join(launcher_dir, "_pico")
    if not os.path.isdir(pico_src):
        raise RuntimeError("Pasta _pico não encontrada no pacote Pico Launcher.")

    shutil.copy2(launcher_nds, os.path.join(staging, "_picoboot.nds"))
    shutil.copytree(pico_src, os.path.join(staging, "_pico"))

    pico_dst = os.path.join(staging, "_pico")
    os.makedirs(pico_dst, exist_ok=True)

    loader7 = _find_file(loader_dir, ("picoLoader7.bin",))
    loader9 = _find_file(
        loader_dir,
        ("picoLoader9.bin", "picoLoader9_DSPICO.bin", "picoloader9.bin"),
    )
    aplist = _find_file(loader_dir, ("aplist.bin",))
    savelist = _find_file(loader_dir, ("savelist.bin",))
    patchlist = _find_file(loader_dir, ("patchlist.bin",))

    missing = []
    if not loader7:
        missing.append("picoLoader7.bin")
    if not loader9:
        missing.append("picoLoader9.bin")
    if not aplist:
        missing.append("aplist.bin")
    if not savelist:
        missing.append("savelist.bin")
    if missing:
        raise RuntimeError(
            "Pacote Pico Loader DSPICO incompleto — faltando: " + ", ".join(missing)
        )

    shutil.copy2(loader7, os.path.join(pico_dst, "picoLoader7.bin"))
    shutil.copy2(loader9, os.path.join(pico_dst, "picoLoader9.bin"))
    shutil.copy2(aplist, os.path.join(pico_dst, "aplist.bin"))
    shutil.copy2(savelist, os.path.join(pico_dst, "savelist.bin"))
    if patchlist:
        shutil.copy2(patchlist, os.path.join(pico_dst, "patchlist.bin"))

    os.makedirs(os.path.join(staging, GAMES_DIRNAME), exist_ok=True)


def install_dspico_package(mount_path: str, log_callback=None) -> tuple[bool, str]:
    """
    Prepara o microSD do DSPico com Pico Launcher + Loader oficiais pinados.
    O firmware .uf2 do cartucho não é gravado aqui.
    """
    from core.progress import ProgressTracker

    log = lambda msg: emit_log(log_callback, msg)
    log("=== Instalando pacote DSPico (Pico Launcher + Loader oficiais LNH) ===")
    tracker = ProgressTracker(
        "setup_dspico",
        label="A preparar…",
        total_items=5,
    )
    tracker.set_phase("download", label="A obter pacotes oficiais…")

    try:
        assert_dspico_cache_key("pico_launcher")
        assert_dspico_cache_key("pico_loader_dspico")
        launcher_zip = ensure_cached("pico_launcher", log_callback)
        tracker.advance_item(label="Launcher obtido", written=True)
        loader_zip = ensure_cached("pico_loader_dspico", log_callback)
        tracker.advance_item(label="Loader obtido", written=True)
        tracker.set_phase("extract", label="A extrair pacotes…")
        launcher_dir = _extract_zip_safe(
            launcher_zip, os.path.join(CACHE_DIR, "Pico_Launcher"), log_callback
        )
        loader_dir = _extract_zip_safe(
            loader_zip, os.path.join(CACHE_DIR, "Pico_Loader_DSPICO"), log_callback
        )
        tracker.advance_item(label="Pacotes extraídos", written=True)
    except Exception as e:
        tracker.finish("Falha ao obter pacote")
        return False, f"Não foi possível obter o pacote DSPico: {e}"

    assembled = os.path.join(CACHE_DIR, "DSPico_SD_ready")
    try:
        tracker.set_phase("assemble", label="A montar árvore DSPico…")
        _assemble_dspico_staging(launcher_dir, loader_dir, assembled)
        tracker.advance_item(label="Árvore montada", written=True)
    except Exception as e:
        tracker.finish("Falha ao montar árvore")
        return False, str(e)

    if not dspico_markers_ok(assembled):
        tracker.finish("Árvore incompleta")
        return False, "Árvore DSPico montada incompleta após assemble."

    undo = UndoStack()
    baks: list[Optional[str]] = []
    try:
        tracker.set_phase("copy", label="A gravar no cartão…")
        bak = _stage_file_copy(
            undo,
            os.path.join(assembled, "_picoboot.nds"),
            os.path.join(mount_path, "_picoboot.nds"),
            log_callback,
        )
        baks.append(bak)
        log("✅ _picoboot.nds copiado e verificado.")

        n = _stage_dir_copy(
            undo,
            os.path.join(assembled, "_pico"),
            os.path.join(mount_path, "_pico"),
            log_callback,
        )
        log(f"✅ Pasta _pico copiada ({n} arquivos verificados).")

        games = _games_root(mount_path)
        if not os.path.isdir(games):
            os.makedirs(games, exist_ok=True)
            undo.push_remove(games)
            log("✅ Pasta Games/ criada (coloque as ROMs aqui).")

        sync_volume(mount_path)
        _cleanup_baks(baks)

        if not dspico_markers_ok(mount_path):
            raise RuntimeError("Validação pós-install falhou (markers DSPico).")

        tracker.advance_item(label="Cartão pronto", written=True)
        log(
            "🎉 MicroSD DSPico pronto. Insira no cartucho "
            "(firmware .uf2 oficial LNH já deve estar gravado)."
        )
        tracker.finish("Pacote DSPico instalado")
        return True, "Pacote DSPico instalado no microSD."
    except Exception as e:
        log(f"⚠️ Falha ao instalar DSPico — revertendo: {e}")
        undo.rollback(log_callback, mount_path=mount_path)
        tracker.finish("Falha na instalação")
        return False, str(e)


# --- Games/ -----------------------------------------------------------------


def _roms_root(mount_path: str) -> str:
    return os.path.join(mount_path, ROMS_DIRNAME)


def _parse_library_cwd(rel_dir: str) -> Optional[tuple[str, str, str]]:
    """Devolve (area, under, nav) ou None se inválido.

    area: "root" | "games" | "roms"
    under: caminho relativo à pasta Games/ ou ROMs/
    nav: caminho de navegação ("" | "Games" | "Games/…" | "ROMs" | "ROMs/…")
    """
    norm = _normalize_rel_dir(rel_dir)
    if norm is None:
        return None
    if not norm:
        return ("root", "", "")
    parts = norm.split("/")
    head = parts[0]
    if head == GAMES_DIRNAME:
        under = "/".join(parts[1:])
        return ("games", under, norm)
    if head == ROMS_DIRNAME:
        under = "/".join(parts[1:])
        return ("roms", under, norm)
    # Legado: paths relativos a Games/ sem prefixo.
    return ("games", norm, f"{GAMES_DIRNAME}/{norm}" if norm else GAMES_DIRNAME)


def _count_visible_children(path: str, allowed_exts: Optional[frozenset] = None) -> int:
    try:
        names = os.listdir(path)
    except OSError:
        return 0
    n = 0
    for c in names:
        if c.startswith(".") or c in SKIP_DIR_NAMES:
            continue
        full = os.path.join(path, c)
        if os.path.isdir(full):
            n += 1
        elif os.path.isfile(full):
            if c.endswith(".partial") or c == ".DS_Store":
                continue
            ext = os.path.splitext(c)[1].lower()
            if allowed_exts is not None and ext not in allowed_exts:
                continue
            if is_companion_ext(ext):
                continue
            n += 1
    return n


def browse_dspico_games(mount_path: str, rel_dir: str = "") -> dict[str, Any]:
    """Lista pastas e jogos sob Games/ (NDS + retro); ROMs/ só se existir (legado)."""
    if not os.path.isdir(mount_path):
        return {
            "success": False,
            "error": "Cartão inexistente.",
            "dirs": [],
            "files": [],
        }

    parsed = _parse_library_cwd(rel_dir)
    if parsed is None:
        return {
            "success": False,
            "error": "Pasta inválida.",
            "dirs": [],
            "files": [],
        }
    area, under, nav = parsed

    dirs_out: list[dict[str, Any]] = []
    files_out: list[dict[str, Any]] = []

    if area == "root":
        games_root = _games_root(mount_path)
        roms_root = _roms_root(mount_path)
        os.makedirs(games_root, exist_ok=True)
        dirs_out.append(
            {
                "name": GAMES_DIRNAME,
                "rel_path": GAMES_DIRNAME,
                "item_count": _count_visible_children(games_root, LIBRARY_FILE_EXTS),
                "type": "dir",
                "area": "games",
            }
        )
        # Legado: mostrar ROMs/ só se a pasta já existir no cartão.
        if os.path.isdir(roms_root):
            n_roms = _count_visible_children(roms_root, RETRO_EXTS)
            if n_roms > 0 or any(
                not n.startswith(".")
                for n in (os.listdir(roms_root) if os.path.isdir(roms_root) else [])
            ):
                dirs_out.append(
                    {
                        "name": ROMS_DIRNAME,
                        "rel_path": ROMS_DIRNAME,
                        "item_count": n_roms,
                        "type": "dir",
                        "area": "roms",
                    }
                )
        return {
            "success": True,
            "rel_dir": "",
            "nav": "",
            "area": "root",
            "dirs": dirs_out,
            "files": files_out,
            "count": len(dirs_out),
            "root_label": "biblioteca",
        }

    if area == "games":
        games_root = _games_root(mount_path)
        if under:
            target = _resolve_under_games(mount_path, under)
            if not target or not os.path.isdir(target):
                return {
                    "success": False,
                    "error": f"Pasta Games/{under}/ inexistente.",
                    "dirs": [],
                    "files": [],
                    "rel_dir": under,
                    "nav": nav,
                    "area": "games",
                }
        else:
            os.makedirs(games_root, exist_ok=True)
            target = os.path.realpath(games_root)
        allowed = LIBRARY_FILE_EXTS
        root_for_rel = games_root
        nav_prefix = GAMES_DIRNAME
    else:
        roms_root = _roms_root(mount_path)
        if under:
            target = _resolve_under_roms_folder(mount_path, under)
            if not target or not os.path.isdir(target):
                return {
                    "success": False,
                    "error": f"Pasta ROMs/{under}/ inexistente.",
                    "dirs": [],
                    "files": [],
                    "rel_dir": under,
                    "nav": nav,
                    "area": "roms",
                }
        else:
            if not os.path.isdir(roms_root):
                return {
                    "success": False,
                    "error": "Pasta ROMs/ inexistente.",
                    "dirs": [],
                    "files": [],
                    "rel_dir": under,
                    "nav": nav,
                    "area": "roms",
                }
            target = os.path.realpath(roms_root)
        allowed = RETRO_EXTS
        root_for_rel = roms_root
        nav_prefix = ROMS_DIRNAME

    try:
        names = sorted(os.listdir(target), key=lambda n: n.lower())
    except OSError as e:
        return {"success": False, "error": str(e), "dirs": [], "files": []}

    for name in names:
        if name.startswith(".") or name in SKIP_DIR_NAMES:
            continue
        full = os.path.join(target, name)
        if os.path.isdir(full):
            child_count = _count_visible_children(full, allowed)
            try:
                rel_under = os.path.relpath(full, root_for_rel).replace("\\", "/")
            except ValueError:
                continue
            dirs_out.append(
                {
                    "name": name,
                    "rel_path": f"{nav_prefix}/{rel_under}",
                    "item_count": child_count,
                    "type": "dir",
                    "area": area,
                }
            )
        elif os.path.isfile(full):
            if name.endswith(".partial") or name == ".DS_Store":
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext not in allowed:
                continue
            if is_companion_ext(ext):
                continue
            try:
                size = os.path.getsize(full)
            except OSError:
                size = 0
            try:
                rel_under = os.path.relpath(full, root_for_rel).replace("\\", "/")
            except ValueError:
                continue
            display = os.path.splitext(name)[0]
            game_code = None
            kind = None
            platform = _RETRO_PLATFORM.get(ext, "retro")
            if area == "games":
                if ext in GAME_EXTS:
                    raw_title, game_code, unitcode, maker = get_nds_header_info(full)
                    kind = classify_nds_kind(
                        raw_title, game_code, maker, name, at_sd_root=False
                    )
                    display = clean_rom_filename(name, game_code) or display
                    platform = _dspico_platform(ext, unitcode)
                else:
                    kind = "retro"
                    display = clean_rom_filename(name, None) or display
                op_rel = rel_under
            else:
                kind = "retro"
                op_rel = f"{ROMS_DIRNAME}/{rel_under}"
            entry: dict[str, Any] = {
                "name": name,
                "rel_path": op_rel,
                "nav_path": f"{nav_prefix}/{rel_under}",
                "display_name": display,
                "size": size,
                "size_label": _format_size(size),
                "type": "file",
                "ext": ext,
                "game_code": (game_code or "").replace("\x00", "").strip() or None,
                "kind": kind or "game",
                "platform": platform,
                "area": area,
            }
            try:
                from core.pico_artwork import enrich_dspico_game_entry

                # Sem preview síncrono: UI pede thumbs sob demanda (USB MSC lento).
                enrich_dspico_game_entry(mount_path, entry, with_preview=False)
            except Exception:
                entry["has_cover"] = False
                entry["has_icon"] = False
            files_out.append(entry)

    return {
        "success": True,
        "rel_dir": under,
        "nav": nav,
        "area": area,
        "dirs": dirs_out,
        "files": files_out,
        "count": len(dirs_out) + len(files_out),
        "root_label": nav_prefix,
    }


def mkdir_dspico_games(
    mount_path: str, parent_rel: str = "", name: str = "", log_callback=None
) -> tuple[bool, str, dict]:
    log = lambda msg: emit_log(log_callback, msg)
    parent = _normalize_rel_dir(parent_rel)
    if parent is None:
        return False, "Pasta pai inválida.", {}
    folder = _sanitize_dir_name(name if isinstance(name, str) else "")
    if not folder:
        return False, "Nome de pasta inválido.", {}
    if folder.startswith(".") or folder in SKIP_DIR_NAMES:
        return False, "Nome de pasta reservado.", {}

    games_root = _games_root(mount_path)
    if parent:
        base = _resolve_under_games(mount_path, parent)
        if not base or not os.path.isdir(base):
            return False, f"Pasta Games/{parent}/ inexistente.", {}
    else:
        os.makedirs(games_root, exist_ok=True)
        base = games_root

    check_rel = f"{parent}/{folder}" if parent else folder
    dest = os.path.join(base, folder)
    games_real = os.path.realpath(games_root)
    parent_real = os.path.realpath(base)
    candidate = os.path.join(parent_real, folder)
    try:
        common = os.path.commonpath([games_real, candidate])
    except ValueError:
        return False, "Caminho fora de Games/.", {}
    if os.path.normcase(common) != os.path.normcase(games_real):
        return False, "Caminho fora de Games/.", {}

    if os.path.exists(dest):
        return False, f"Já existe: Games/{check_rel}/", {}
    try:
        os.makedirs(dest, exist_ok=False)
    except OSError as e:
        return False, f"Não foi possível criar pasta: {e}", {}
    log(f"📁 Criada Games/{check_rel}/")
    return True, f"Pasta Games/{check_rel}/ criada.", {"rel_path": check_rel}


def _retro_platform_for_ext(ext: str) -> Optional[str]:
    return _RETRO_PLATFORM.get((ext or "").lower())


def _dspico_entry_meta(full: str, name: str, ext: str, *, under_games: bool) -> Optional[dict]:
    """Metadados de um ROM no cartão DSPico para detecção de duplicatas."""
    game_code = None
    kind = None
    platform = None
    display = os.path.splitext(name)[0]
    if ext in GAME_EXTS:
        raw_title, game_code, unitcode, maker = get_nds_header_info(full)
        kind = classify_nds_kind(raw_title, game_code, maker, name, at_sd_root=False)
        if kind == "system":
            return None
        display = clean_rom_filename(name, game_code) or display
        platform = _dspico_platform(ext, unitcode)
    elif ext in RETRO_EXTS:
        platform = _retro_platform_for_ext(ext)
        display = clean_rom_filename(name, None) or display
        kind = "retro"
    else:
        return None
    key = duplicate_key(platform, game_code, display)
    if not key:
        return None
    try:
        size = os.path.getsize(full)
    except OSError:
        size = 0
    return {
        "name": name,
        "display_name": display,
        "platform": platform,
        "game_code": (game_code or "").replace("\x00", "").strip() or None,
        "kind": kind or "game",
        "size": size,
        "size_label": _format_size(size),
        "ext": ext,
        "dup_key": key,
        "full": full,
        "under_games": under_games,
    }


def _index_dspico_by_dup_key(
    mount_path: str, *, use_cache: bool = True
) -> dict[str, list[dict[str, Any]]]:
    """Indexa Games/ (NDS + retro) e ROMs/ legado por chave de duplicata."""
    try:
        cache_key = os.path.realpath(mount_path)
    except OSError:
        cache_key = mount_path
    now = time.monotonic()
    if use_cache:
        hit = _DUP_INDEX_CACHE.get(cache_key)
        if hit and now - hit[0] < _DUP_INDEX_TTL_S:
            return hit[1]

    index: dict[str, list[dict[str, Any]]] = {}
    games_root = _games_root(mount_path)
    if os.path.isdir(games_root):
        for root, dirs, files in os.walk(games_root, topdown=True):
            dirs[:] = [
                d for d in dirs if d not in SKIP_DIR_NAMES and not d.startswith(".")
            ]
            for name in files:
                if name.startswith(".") or name.endswith(".partial"):
                    continue
                ext = os.path.splitext(name)[1].lower()
                if ext not in LIBRARY_FILE_EXTS:
                    continue
                full = os.path.join(root, name)
                meta = _dspico_entry_meta(full, name, ext, under_games=True)
                if not meta:
                    continue
                try:
                    rel = os.path.relpath(full, games_root).replace("\\", "/")
                except ValueError:
                    continue
                item = {
                    "rel_path": rel,
                    "scope": "games",
                    "name": meta["name"],
                    "display_name": meta["display_name"],
                    "platform": meta["platform"],
                    "game_code": meta["game_code"],
                    "size": meta["size"],
                    "size_label": meta["size_label"],
                }
                index.setdefault(meta["dup_key"], []).append(item)

    roms_root = os.path.join(mount_path, "ROMs")
    if os.path.isdir(roms_root):
        for root, dirs, files in os.walk(roms_root, topdown=True):
            dirs[:] = [
                d for d in dirs if d not in SKIP_DIR_NAMES and not d.startswith(".")
            ]
            for name in files:
                if name.startswith(".") or name.endswith(".partial"):
                    continue
                ext = os.path.splitext(name)[1].lower()
                if ext not in RETRO_EXTS:
                    continue
                full = os.path.join(root, name)
                meta = _dspico_entry_meta(full, name, ext, under_games=False)
                if not meta:
                    continue
                try:
                    rel = os.path.relpath(full, mount_path).replace("\\", "/")
                except ValueError:
                    continue
                item = {
                    "rel_path": rel,
                    "scope": "retro",
                    "name": meta["name"],
                    "display_name": meta["display_name"],
                    "platform": meta["platform"],
                    "game_code": None,
                    "size": meta["size"],
                    "size_label": meta["size_label"],
                }
                index.setdefault(meta["dup_key"], []).append(item)
    _DUP_INDEX_CACHE[cache_key] = (now, index)
    return index


def find_duplicate_dspico_games(mount_path: str) -> dict[str, Any]:
    """Grupos de jogos iguais em Games/ e ROMs/ (≥2 por chave)."""
    if not os.path.isdir(mount_path):
        return {"success": False, "error": "Cartão inexistente.", "groups": []}
    index = _index_dspico_by_dup_key(mount_path)
    groups: list[dict[str, Any]] = []
    for key, items in sorted(index.items(), key=lambda kv: kv[0]):
        if len(items) < 2:
            continue
        label = items[0].get("display_name") or key
        if key.startswith("tid:"):
            label = f"{label} ({key[4:]})"
        groups.append({"key": key, "label": label, "items": items})
    return {"success": True, "groups": groups, "count": len(groups)}


def _import_src_dup_info(src: str, ext: str) -> tuple[Optional[str], Optional[str], str]:
    """Devolve (dup_key, game_code, display_name) para um ficheiro a importar."""
    name = os.path.basename(src)
    if ext in GAME_EXTS:
        raw_title, game_code, _uc, maker = get_nds_header_info(src)
        kind = classify_nds_kind(raw_title, game_code, maker, name, at_sd_root=False)
        if kind == "system":
            return None, None, name
        display = clean_rom_filename(name, game_code) or os.path.splitext(name)[0]
        platform = "dsi" if ext == ".dsi" else "nds"
        return duplicate_key(platform, game_code, display), game_code, display
    if ext in RETRO_EXTS:
        platform = _retro_platform_for_ext(ext)
        display = os.path.splitext(name)[0]
        return duplicate_key(platform, None, display), None, display
    return None, None, name


def _remove_dspico_existing(
    mount_path: str, existing_items: list[dict[str, Any]], log=None
) -> None:
    for item in existing_items:
        if not isinstance(item, dict):
            continue
        rel = item.get("rel_path")
        scope = item.get("scope") or "games"
        if not isinstance(rel, str) or not rel.strip():
            continue
        if scope == "retro":
            path = os.path.realpath(os.path.join(mount_path, *rel.split("/")))
            try:
                common = os.path.commonpath(
                    [os.path.realpath(mount_path), path]
                )
            except ValueError:
                continue
            if os.path.normcase(common) != os.path.normcase(
                os.path.realpath(mount_path)
            ):
                continue
            # Retro deve estar sob ROMs/
            try:
                r_common = os.path.commonpath(
                    [os.path.realpath(os.path.join(mount_path, "ROMs")), path]
                )
            except ValueError:
                continue
            if os.path.normcase(r_common) != os.path.normcase(
                os.path.realpath(os.path.join(mount_path, "ROMs"))
            ):
                continue
        else:
            path = _resolve_under_games(mount_path, rel)
            if not path:
                continue
        if not os.path.isfile(path):
            continue
        try:
            os.remove(path)
            if log:
                label = f"Games/{rel}" if scope != "retro" else rel
                log(f"🗑️ Substituir: removido {label}")
        except OSError as e:
            if log:
                log(f"⚠️ Não foi possível remover {rel}: {e}")
            continue
        # sidecars same stem (Games only)
        if scope != "retro":
            stem = os.path.splitext(os.path.basename(path))[0].lower()
            parent = os.path.dirname(path)
            try:
                for name in os.listdir(parent):
                    for key, _ in companion_index_keys(name):
                        if key == stem:
                            side = os.path.join(parent, name)
                            if os.path.isfile(side):
                                try:
                                    os.remove(side)
                                except OSError:
                                    pass
                            break
            except OSError:
                pass


def check_dspico_import_conflicts(
    mount_path: str,
    source_paths: list,
    dest_rel_dir: str = "",
) -> dict[str, Any]:
    """Pré-scan de import DSPico (sem escrever)."""
    from core.archive_roms import cleanup_expand_staging, expand_rom_sources

    if not isinstance(source_paths, list) or not source_paths:
        return {"success": False, "error": "Nenhum ficheiro seleccionado.", "conflicts": []}
    dest_norm = _normalize_rel_dir(dest_rel_dir)
    if dest_norm is None:
        return {"success": False, "error": "Pasta de destino inválida.", "conflicts": []}
    if dest_norm:
        games_dest = _resolve_under_games(mount_path, dest_norm)
        if not games_dest or not os.path.isdir(games_dest):
            return {
                "success": False,
                "error": f"Destino Games/{dest_norm}/ inexistente.",
                "conflicts": [],
            }
    if not os.path.isdir(mount_path):
        return {"success": False, "error": "Cartão inexistente.", "conflicts": []}

    expand_stats: dict = {}
    try:
        rom_paths, expand_errors, expand_stats = expand_rom_sources(
            source_paths, IMPORT_EXTS
        )
    except Exception as e:
        return {"success": False, "error": f"Falha ao preparar ficheiros: {e}", "conflicts": []}

    try:
        if not rom_paths:
            return {
                "success": False,
                "error": "Nenhum ROM válido para importar.",
                "conflicts": [],
                "expand_errors": expand_errors[:5],
            }
        index = _index_dspico_by_dup_key(mount_path)
        conflicts: list[dict[str, Any]] = []
        for src in rom_paths:
            if not os.path.isfile(src):
                continue
            base_name = os.path.basename(src)
            ext = os.path.splitext(base_name)[1].lower()
            if ext not in IMPORT_EXTS:
                continue
            key, game_code, display = _import_src_dup_info(src, ext)
            if not key:
                continue
            existing = index.get(key) or []
            if not existing:
                continue
            conflicts.append(
                {
                    "conflict_id": conflict_id_for(key, base_name),
                    "key": key,
                    "src_name": base_name,
                    "display_name": display,
                    "platform": existing[0].get("platform"),
                    "game_code": (game_code or "").replace("\x00", "").strip() or None,
                    "existing": [
                        {k: v for k, v in e.items() if k != "full"} for e in existing
                    ],
                }
            )
        return {
            "success": True,
            "conflicts": conflicts,
            "job_count": len(rom_paths),
            "has_conflicts": bool(conflicts),
        }
    finally:
        cleanup_expand_staging(expand_stats)


def import_dspico_games(
    mount_path: str,
    source_paths: list,
    dest_rel_dir: str = "",
    log_callback=None,
    conflict_resolutions=None,
) -> tuple[bool, str, dict]:
    """
    Copia ROMs do host para Games/ (NDS, apps em Games/Apps/, retro).
    Aceita arquivos zip/7z/rar. Emite progresso para a UI.
    conflict_resolutions: mapa conflict_id → replace|keep_both|skip.
    """
    from core.archive_roms import cleanup_expand_staging, expand_rom_sources

    log = lambda msg: emit_log(log_callback, msg)
    if not isinstance(source_paths, list) or not source_paths:
        return False, "Nenhum ficheiro seleccionado.", {}

    resolutions = normalize_conflict_resolutions(conflict_resolutions)
    if resolutions is None:
        return False, "Resoluções de conflito inválidas.", {}

    dest_norm = _normalize_rel_dir(dest_rel_dir)
    if dest_norm is None:
        return False, "Pasta de destino inválida.", {}

    games_root = _games_root(mount_path)
    os.makedirs(games_root, exist_ok=True)
    if dest_norm:
        games_dest = _resolve_under_games(mount_path, dest_norm)
        if not games_dest or not os.path.isdir(games_dest):
            return False, f"Destino Games/{dest_norm}/ inexistente.", {}
    else:
        games_dest = games_root

    mount_real = os.path.realpath(mount_path)
    undo = UndoStack()
    copied = 0
    skipped = 0
    errors: list[str] = []
    expand_stats: dict = {}
    games_n = 0
    apps_n = 0
    retro_n = 0
    replaced = 0

    log(f"=== Importar {len(source_paths)} item(ns) para Games/ ===")
    try:
        rom_paths, expand_errors, expand_stats = expand_rom_sources(
            source_paths, IMPORT_EXTS
        )
    except Exception as e:
        return False, f"Falha ao preparar ficheiros: {e}", {}
    errors.extend(expand_errors)
    if expand_stats.get("archives"):
        log(
            f"Arquivos: {expand_stats['archives']} · "
            f"ROMs extraídas: {expand_stats.get('extracted_roms', 0)}"
        )
    if not rom_paths:
        cleanup_expand_staging(expand_stats)
        msg = "Nenhum ROM válido para importar."
        if errors:
            msg += " " + "; ".join(errors[:3])
        return False, msg, {"skipped": skipped, "errors": errors}

    index = _index_dspico_by_dup_key(mount_path)
    total = len(rom_paths)
    total_bytes = 0
    for src in rom_paths:
        try:
            total_bytes += max(0, int(os.path.getsize(src)))
        except OSError:
            pass

    from core.progress import ProgressTracker

    tracker = ProgressTracker(
        "dspico_import_games",
        label="A iniciar…",
        total_items=total,
        total_bytes=total_bytes,
        emit_fn=_emit_import_progress,
    )

    try:
        tracker.tick(force=True)
        for _idx, src in enumerate(rom_paths, start=1):
            base_name = os.path.basename(src)
            try:
                src_size = max(0, int(os.path.getsize(src)))
            except OSError:
                src_size = 0
            ext = os.path.splitext(base_name)[1].lower()
            nds_kind = None
            if ext in GAME_EXTS:
                raw_title, game_code, _uc, maker = get_nds_header_info(src)
                nds_kind = classify_nds_kind(
                    raw_title, game_code, maker, base_name, at_sd_root=False
                )
                if nds_kind == "system":
                    log(f"⏭️ Ignorado (sistema): {base_name}")
                    skipped += 1
                    tracker.advance_item(
                        bytes_delta=src_size, label=base_name, skipped=True
                    )
                    continue
            dest_dir, bucket = _dest_dir_for_import(
                mount_path, ext, games_dest, nds_kind=nds_kind
            )
            tracker.set_label(base_name)
            tracker.tick(force=True)
            if not dest_dir or not bucket:
                errors.append(f"Extensão não suportada: {base_name}")
                skipped += 1
                tracker.advance_item(
                    bytes_delta=src_size, label=base_name, skipped=True
                )
                continue

            dup_key, _gc, _disp = _import_src_dup_info(src, ext)
            existing = index.get(dup_key) if dup_key else None
            cid = conflict_id_for(dup_key, base_name) if dup_key else None
            resolution = "keep_both"
            if existing and cid:
                resolution = resolutions.get(cid, "keep_both")
            if resolution == "skip":
                log(f"⏭️ Ignorado (duplicata): {base_name}")
                skipped += 1
                tracker.advance_item(
                    bytes_delta=src_size, label=base_name, skipped=True
                )
                continue

            try:
                os.makedirs(dest_dir, exist_ok=True)
            except OSError as e:
                errors.append(f"{base_name}: pasta destino — {e}")
                skipped += 1
                tracker.advance_item(
                    bytes_delta=src_size, label=base_name, skipped=True
                )
                continue

            out_name = base_name
            if ext in GAME_EXTS:
                out_name = os.path.splitext(base_name)[0] + _nds_out_ext(ext)

            if resolution == "replace" and existing:
                _remove_dspico_existing(mount_path, existing, log=log)
                replaced += len(existing)
                dest = os.path.join(dest_dir, out_name)
            else:
                dest = _unique_dest_path(dest_dir, out_name)
            try:
                dest_parent = os.path.realpath(os.path.dirname(dest))
                common = os.path.commonpath([mount_real, dest_parent])
            except ValueError:
                errors.append(f"{base_name}: destino fora do cartão.")
                skipped += 1
                tracker.advance_item(
                    bytes_delta=src_size, label=base_name, skipped=True
                )
                continue
            if os.path.normcase(common) != os.path.normcase(mount_real):
                errors.append(f"{base_name}: destino fora do cartão.")
                skipped += 1
                tracker.advance_item(
                    bytes_delta=src_size, label=base_name, skipped=True
                )
                continue
            try:
                g_common = os.path.commonpath(
                    [os.path.realpath(games_root), dest_parent]
                )
            except ValueError:
                errors.append("Destino fora de Games/.")
                skipped += 1
                tracker.advance_item(
                    bytes_delta=src_size, label=base_name, skipped=True
                )
                continue
            if os.path.normcase(g_common) != os.path.normcase(
                os.path.realpath(games_root)
            ):
                errors.append("Destino fora de Games/.")
                skipped += 1
                tracker.advance_item(
                    bytes_delta=src_size, label=base_name, skipped=True
                )
                continue

            try:
                copy_fast(src, dest, log_callback=log_callback)
                undo.push_remove(dest)
                copied += 1
                if bucket == "apps":
                    apps_n += 1
                elif bucket == "retro":
                    retro_n += 1
                else:
                    games_n += 1
                rel = os.path.relpath(dest, games_root).replace("\\", "/")
                log(f"📥 {base_name} → Games/{rel}")
                tracker.advance_item(
                    bytes_delta=src_size, label=base_name, written=True
                )

                stem = os.path.splitext(src)[0]
                src_dir = os.path.dirname(src)
                try:
                    near = os.listdir(src_dir)
                except OSError:
                    near = []
                stem_l = os.path.basename(stem).lower()
                for name in near:
                    for key, _suf in companion_index_keys(name):
                        if key == stem_l:
                            sav_src = os.path.join(src_dir, name)
                            if os.path.isfile(sav_src):
                                sav_dest = os.path.join(
                                    os.path.dirname(dest), name
                                )
                                if not os.path.exists(sav_dest):
                                    copy_fast(
                                        sav_src,
                                        sav_dest,
                                        log_callback=log_callback,
                                    )
                                    undo.push_remove(sav_dest)
                            break
            except Exception as e:
                errors.append(f"{base_name}: {e}")
                skipped += 1
                tracker.advance_item(
                    bytes_delta=src_size, label=base_name, failed=True
                )

        invalidate_dspico_library_caches(mount_path)
        sync_volume(mount_path)
        stats = {
            "copied": copied,
            "skipped": skipped,
            "errors": len(errors),
            "archives": expand_stats.get("archives", 0),
            "extracted_roms": expand_stats.get("extracted_roms", 0),
            "games": games_n,
            "apps": apps_n,
            "retro": retro_n,
            "replaced": replaced,
        }
        tracker.written = copied
        tracker.skipped = skipped
        if copied == 0 and errors:
            tracker.finish(errors[0])
            return False, errors[0], stats
        if copied == 0:
            msg = f"Nada a importar ({skipped} ignorado(s))."
            tracker.finish(msg)
            return True, msg, stats
        parts = []
        if games_n:
            parts.append(f"{games_n} jogo(s)")
        if apps_n:
            parts.append(f"{apps_n} app(s)")
        if retro_n:
            parts.append(f"{retro_n} retro")
        msg = f"{copied} ficheiro(s) importado(s) para Games/"
        if parts:
            msg += " (" + ", ".join(parts) + ")"
        msg += "."
        if replaced:
            msg += f" {replaced} substituído(s)."
        if expand_stats.get("archives"):
            msg += f" ({expand_stats['archives']} arquivo(s))"
        if skipped:
            msg += f" {skipped} ignorado(s)."
        tracker.finish(msg)
        return True, msg, stats
    finally:
        cleanup_expand_staging(expand_stats)


def _resolve_under_roms_folder(mount_path: str, rel_path: str) -> Optional[str]:
    """Resolve rel_path sob ROMs/; aceita com ou sem prefixo ROMs/."""
    if not isinstance(rel_path, str) or "\x00" in rel_path:
        return None
    rel = rel_path.replace("\\", "/").lstrip("/")
    if rel.startswith("ROMs/"):
        rel = rel[5:]
    if not rel or rel.startswith("..") or "/../" in f"/{rel}/":
        return None
    roms = os.path.realpath(os.path.join(mount_path, "ROMs"))
    candidate = os.path.realpath(os.path.join(roms, *rel.split("/")))
    try:
        common = os.path.commonpath([roms, candidate])
    except ValueError:
        return None
    if os.path.normcase(common) != os.path.normcase(roms):
        return None
    return candidate


def delete_dspico_games(
    mount_path: str, rel_paths: list, log_callback=None
) -> tuple[bool, str, dict]:
    log = lambda msg: emit_log(log_callback, msg)
    if not isinstance(rel_paths, list) or not rel_paths:
        return False, "Nada seleccionado.", {}

    removed = 0
    errors: list[str] = []
    for rel in rel_paths:
        if not isinstance(rel, str):
            continue
        target = _resolve_under_games(mount_path, rel)
        if not target or not os.path.isfile(target):
            errors.append(f"Não encontrado: {rel}")
            continue
        try:
            os.remove(target)
            removed += 1
            log(f"🗑️ Removido: Games/{rel}")
            # sidecars same stem
            stem = os.path.splitext(os.path.basename(target))[0].lower()
            parent = os.path.dirname(target)
            try:
                for name in os.listdir(parent):
                    for key, _ in companion_index_keys(name):
                        if key == stem:
                            side = os.path.join(parent, name)
                            if os.path.isfile(side):
                                os.remove(side)
                            break
            except OSError:
                pass
        except OSError as e:
            errors.append(str(e))

    invalidate_dspico_library_caches(mount_path)
    sync_volume(mount_path)
    stats = {"removed": removed, "errors": len(errors)}
    if removed == 0:
        return False, (errors[0] if errors else "Nada removido."), stats
    return True, f"{removed} ficheiro(s) removido(s).", stats


def delete_dspico_retro_roms(
    mount_path: str, rel_paths: list, log_callback=None
) -> tuple[bool, str, dict]:
    """Apaga ROMs retro sob /ROMs/ (paths relativos ao mount ou a ROMs/)."""
    log = lambda msg: emit_log(log_callback, msg)
    if not isinstance(rel_paths, list) or not rel_paths:
        return False, "Nada seleccionado.", {}
    removed = 0
    errors: list[str] = []
    for rel in rel_paths:
        if not isinstance(rel, str):
            continue
        target = _resolve_under_roms_folder(mount_path, rel)
        if not target or not os.path.isfile(target):
            errors.append(f"Não encontrado: {rel}")
            continue
        try:
            os.remove(target)
            removed += 1
            try:
                show = os.path.relpath(target, mount_path).replace("\\", "/")
            except ValueError:
                show = os.path.basename(target)
            log(f"🗑️ Removido: /{show}")
        except OSError as e:
            errors.append(str(e))
    invalidate_dspico_library_caches(mount_path)
    sync_volume(mount_path)
    stats = {"removed": removed, "errors": len(errors)}
    if removed == 0:
        return False, (errors[0] if errors else "Nada removido."), stats
    return True, f"{removed} ROM(s) retro removido(s).", stats


def move_dspico_games(
    mount_path: str,
    rel_paths: list,
    dest_rel_dir: str = "",
    log_callback=None,
) -> tuple[bool, str, dict]:
    log = lambda msg: emit_log(log_callback, msg)
    dest_norm = _normalize_rel_dir(dest_rel_dir)
    if dest_norm is None:
        return False, "Destino inválido.", {}
    if not isinstance(rel_paths, list) or not rel_paths:
        return False, "Nada seleccionado.", {}

    games_root = _games_root(mount_path)
    if dest_norm:
        dest_dir = _resolve_under_games(mount_path, dest_norm)
        if not dest_dir or not os.path.isdir(dest_dir):
            return False, f"Destino Games/{dest_norm}/ inexistente.", {}
    else:
        dest_dir = games_root

    moved = 0
    errors: list[str] = []
    for rel in rel_paths:
        if not isinstance(rel, str):
            continue
        src = _resolve_under_games(mount_path, rel)
        if not src or not os.path.isfile(src):
            errors.append(f"Não encontrado: {rel}")
            continue
        dest = os.path.join(dest_dir, os.path.basename(src))
        if os.path.normcase(os.path.realpath(src)) == os.path.normcase(
            os.path.realpath(dest)
        ):
            continue
        if os.path.exists(dest):
            errors.append(f"Já existe: {os.path.basename(dest)}")
            continue
        try:
            shutil.move(src, dest)
            moved += 1
            log(f"📦 {rel} → Games/{dest_norm or ''}/")
        except OSError as e:
            errors.append(str(e))

    invalidate_dspico_library_caches(mount_path)
    sync_volume(mount_path)
    stats = {"moved": moved, "errors": len(errors)}
    if moved == 0 and errors:
        return False, errors[0], stats
    return True, f"{moved} item(ns) movido(s).", stats


# --- Organizar pastas (só DSPico) -------------------------------------------


def normalize_dspico_layout(layout) -> Optional[str]:
    """Normaliza layout DSPico; default = games. None se inválido."""
    if layout is None or layout == "":
        return LAYOUT_GAMES
    if not isinstance(layout, str):
        return None
    low = layout.strip().lower()
    if low in LAYOUT_MODES:
        return low
    return LAYOUT_ALIASES.get(low)


def _unique_path(dest_path: str) -> str:
    if not os.path.exists(dest_path):
        return dest_path
    base, ext = os.path.splitext(dest_path)
    n = 2
    while True:
        candidate = f"{base} ({n}){ext}"
        if not os.path.exists(candidate):
            return candidate
        n += 1


def _safe_move(src: str, dst: str) -> str:
    if os.path.abspath(src) == os.path.abspath(dst):
        return dst
    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    dst = _unique_path(dst)
    shutil.move(src, dst)
    return dst


def _dspico_platform(ext: str, unitcode=None) -> str:
    """Pasta de plataforma: nds/dsi ou plataforma retro (gb, gba, nes, …)."""
    low = (ext or "").lower()
    if low in RETRO_EXTS:
        return _RETRO_PLATFORM.get(low, "retro")
    try:
        uc = int(unitcode) if unitcode is not None else 0
    except (TypeError, ValueError):
        uc = 0
    if low == ".dsi" or low == ".app" or uc == 2:
        return "dsi"
    return "nds"


def _dspico_dest_dir(
    mount_path: str, platform: str, franchise: Optional[str], layout: str
) -> str:
    """Directório de destino absoluto conforme o layout DSPico (jogos + retro)."""
    if layout == LAYOUT_ROOT:
        return mount_path
    games = _games_root(mount_path)
    if layout == LAYOUT_GAMES:
        return games
    if layout == LAYOUT_PLATFORM:
        return os.path.join(games, platform or "nds")
    folder = franchise or UNKNOWN_FRANCHISE
    cleaned = _sanitize_dir_name(folder) or UNKNOWN_FRANCHISE
    return os.path.join(games, cleaned)


def _is_picoboot(name: str) -> bool:
    return (name or "").lower() == _PICOBOOT_NAME


def _should_skip_collect_dir(name: str) -> bool:
    """Só pastas de sistema DSPico — entra em _nds/MOONSHL/ROMs para migrar jogos.

    ROMs/BIOS fica intacta (BIOS proprietária / dumps do utilizador).
    """
    if not name or name.startswith("."):
        return True
    low = name.lower()
    if low == "bios":
        return True
    return low in _COLLECT_SKIP_DIRS


def _prune_empty_under(root: str, *, preserve_root: bool = True) -> int:
    """Remove pastas vazias sob root (bottom-up). Devolve quantas removeu."""
    if not os.path.isdir(root):
        return 0
    removed = 0
    for walk_root, dirs, files in os.walk(root, topdown=False):
        if preserve_root and os.path.normcase(os.path.realpath(walk_root)) == os.path.normcase(
            os.path.realpath(root)
        ):
            continue
        try:
            entries = os.listdir(walk_root)
        except OSError:
            continue
        meaningful = [
            e
            for e in entries
            if e not in (".DS_Store",) and not e.startswith("._")
        ]
        if meaningful:
            continue
        for e in entries:
            try:
                os.remove(os.path.join(walk_root, e))
            except OSError:
                pass
        try:
            os.rmdir(walk_root)
            removed += 1
        except OSError:
            pass
    return removed


def _remove_path_best_effort(path: str, log) -> bool:
    try:
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        return True
    except OSError as e:
        log(f"⚠️ Não foi possível remover {os.path.basename(path)}: {e}")
        return False


def _ensure_dir_cached(path: str, created: set[str], log) -> bool:
    """makedirs uma vez por destino; devolve False se falhar."""
    try:
        real = os.path.realpath(path)
    except OSError:
        real = path
    if real in created:
        return True
    try:
        os.makedirs(path, exist_ok=True)
        created.add(real)
        return True
    except OSError as e:
        log(f"⚠️ Falha ao criar pasta: {e}")
        return False


def organize_dspico_sd(
    mount_path: str, layout=LAYOUT_GAMES, log_callback=None
) -> tuple[bool, str, dict]:
    """
    Limpa o microSD de conteúdo de outros sistemas e organiza jogos.

    Mantém: `_picoboot.nds`, `_pico/`, `Games/`, emunand, `Emulators/`,
    `_gba/`, `data/`, `snemul.cfg`, e `ROMs/` se existir (BIOS legado).

    NDS/DSi e ROMs retro de todos os emuladores Pico seguem o mesmo layout
    em `Games/` (apps → `Games/Apps/`). Não cria pasta `ROMs/` para jogos;
    `ROMs/BIOS` (se existir) é preservada.

    Layouts:
    - franchise: Games/<franquia>/
    - platform:  Games/<plat>/ (nds, dsi, gba, genesis, 2600, …)
    - games:     soltos em Games/
    - root:      soltos na raiz ao lado do launcher
    """
    log = lambda msg: emit_log(log_callback, msg)

    mode = normalize_dspico_layout(layout)
    if mode is None:
        return (
            False,
            f"Layout inválido: {layout!r}. Use: franchise, platform, games ou root.",
            {},
        )

    labels = {
        LAYOUT_FRANCHISE: "por franquia em Games/",
        LAYOUT_PLATFORM: "por plataforma em Games/",
        LAYOUT_GAMES: "soltos em Games/",
        LAYOUT_ROOT: "soltos na raiz (ao lado do launcher)",
    }
    log(f"=== Organizar DSPico ({labels.get(mode, mode)}) ===")
    from core.progress import ProgressTracker

    tracker = ProgressTracker(
        "dspico_organize",
        label="A varrer o cartão…",
        emit_fn=_emit_import_progress,
    )
    tracker.set_phase("scan", label="A varrer o cartão…")

    if not isinstance(mount_path, str) or not mount_path.strip():
        return False, "Caminho do cartão inválido.", {}
    if not os.path.isdir(mount_path):
        return False, "Cartão inexistente.", {}

    mount_norm = mount_path.rstrip("/\\")
    games_root = _games_root(mount_path)
    roms_root = _roms_root(mount_path)
    apps_root = _apps_root(mount_path)
    if mode != LAYOUT_ROOT:
        os.makedirs(games_root, exist_ok=True)

    # candidates: (name, full, ext, kind, platform, game_code, raw_title)
    # kind: game | app | retro
    candidates: list[tuple] = []
    companion_candidates: list[tuple] = []
    header_cache: dict[str, tuple] = {}

    for root, dirs, files in os.walk(mount_path, topdown=True):
        dirs[:] = [d for d in dirs if not _should_skip_collect_dir(d)]
        at_sd_root = root.rstrip("/\\") == mount_norm

        for f in files:
            if f.startswith(".") or f.endswith(".partial") or f == ".DS_Store":
                continue
            full = os.path.join(root, f)
            ext = os.path.splitext(f)[1].lower()
            low = f.lower()

            if at_sd_root and (_is_picoboot(f) or low in SYSTEM_ROOT_NAMES):
                continue

            if is_companion_ext(ext):
                companion_candidates.append((f, full))
                continue

            if ext in RETRO_EXTS:
                plat = _dspico_platform(ext)
                candidates.append((f, full, ext, "retro", plat, None, None))
                continue

            if ext not in GAME_EXTS:
                continue
            if _is_picoboot(f):
                continue

            try:
                real = os.path.realpath(full)
            except OSError:
                real = full
            if real in header_cache:
                header = header_cache[real]
            else:
                header = get_nds_header_info(full)
                header_cache[real] = header
            raw_title, game_code, unitcode, maker = header
            kind = classify_nds_kind(
                raw_title, game_code, maker, f, at_sd_root=at_sd_root
            )
            if kind == "system":
                continue
            if kind != "app":
                kind = "game"
            plat = _dspico_platform(ext, unitcode)
            candidates.append(
                (f, full, ext, kind, plat, game_code, raw_title)
            )

    n_games = sum(1 for c in candidates if c[3] == "game")
    n_apps = sum(1 for c in candidates if c[3] == "app")
    n_retro = sum(1 for c in candidates if c[3] == "retro")
    log(
        f"Encontrados: {n_games} jogo(s), {n_apps} app(s), "
        f"{n_retro} retro, {len(companion_candidates)} save(s)."
    )
    total_bytes = 0
    for _c in candidates:
        try:
            total_bytes += max(0, int(os.path.getsize(_c[1])))
        except OSError:
            pass
    tracker.set_totals(items=len(candidates), bytes=total_bytes)
    tracker.set_phase("move", label="A organizar jogos…")

    companions_by_stem: dict[str, list] = {}
    for comp_name, comp_path in companion_candidates:
        for key, suffix in companion_index_keys(comp_name):
            companions_by_stem.setdefault(key, []).append(
                (comp_name, comp_path, suffix)
            )

    handled_companions: set[str] = set()
    kept_paths: set[str] = set()
    dirs_created: set[str] = set()
    organized = 0
    games_moved = 0
    apps_moved = 0
    retro_moved = 0
    companions_moved = 0
    move_failures = 0
    counts: dict[str, int] = {}

    pico_boot = os.path.join(mount_path, _PICOBOOT_NAME)
    if os.path.isfile(pico_boot):
        kept_paths.add(os.path.realpath(pico_boot))
    pico_dir = _pico_dir(mount_path)
    if os.path.isdir(pico_dir):
        kept_paths.add(os.path.realpath(pico_dir))

    for i, (original_name, full_path, ext, kind, platform, game_code, raw_title) in enumerate(
        candidates, start=1
    ):
        if not os.path.exists(full_path):
            tracker.advance_item(label=original_name, skipped=True)
            continue
        try:
            item_size = max(0, int(os.path.getsize(full_path)))
        except OSError:
            item_size = 0

        clean_name = clean_rom_filename(original_name, game_code)
        out_ext = _nds_out_ext(ext) if ext in GAME_EXTS else ext

        if kind == "app":
            dest_dir = apps_root
            bucket = APPS_DIRNAME
        else:
            franchise = None
            if mode == LAYOUT_FRANCHISE:
                franchise = detect_franchise(
                    clean_name,
                    game_code=game_code,
                    raw_title=raw_title,
                    original_name=original_name,
                )
            dest_dir = _dspico_dest_dir(mount_path, platform, franchise, mode)
            if mode == LAYOUT_FRANCHISE:
                bucket = franchise or UNKNOWN_FRANCHISE
            elif mode == LAYOUT_PLATFORM:
                bucket = platform
            elif mode == LAYOUT_ROOT:
                bucket = "raiz"
            else:
                bucket = "Games"

        if not _ensure_dir_cached(dest_dir, dirs_created, log):
            move_failures += 1
            tracker.advance_item(
                bytes_delta=item_size, label=original_name, failed=True
            )
            continue

        target = os.path.join(dest_dir, f"{clean_name}{out_ext}")
        try:
            new_path = _safe_move(full_path, target)
            organized += 1
            if kind == "app":
                apps_moved += 1
            elif kind == "retro":
                retro_moved += 1
            else:
                games_moved += 1
            kept_paths.add(os.path.realpath(new_path))
            try:
                if mode == LAYOUT_ROOT and kind != "app":
                    rel = os.path.basename(new_path)
                    where = rel
                else:
                    rel = os.path.relpath(new_path, games_root).replace("\\", "/")
                    where = f"Games/{rel}"
            except ValueError:
                where = os.path.basename(new_path)
            icon = "🧩" if kind == "app" else ("🕹" if kind == "retro" else "🎮")
            if os.path.abspath(full_path) != os.path.abspath(new_path):
                log(f"{icon} {original_name} → {where}")
            else:
                log(f"{icon} {where} (já no lugar)")
            counts[bucket] = counts.get(bucket, 0) + 1
            tracker.advance_item(
                bytes_delta=item_size, label=original_name, written=True
            )
        except Exception as e:
            move_failures += 1
            log(f"⚠️ Falha ao mover {original_name}: {e}")
            tracker.advance_item(
                bytes_delta=item_size, label=original_name, failed=True
            )
            continue

        rom_dir = os.path.dirname(new_path)
        stem_original = os.path.splitext(original_name)[0]
        final_stem = os.path.splitext(os.path.basename(new_path))[0]
        for key in {stem_original.lower(), clean_name.lower(), final_stem.lower()}:
            for comp_name, comp_path, suffix in companions_by_stem.get(key, []):
                if comp_path in handled_companions or not os.path.exists(comp_path):
                    continue
                target_comp = os.path.join(rom_dir, f"{final_stem}{suffix}")
                try:
                    new_comp = _safe_move(comp_path, target_comp)
                    handled_companions.add(comp_path)
                    companions_moved += 1
                    kept_paths.add(os.path.realpath(new_comp))
                    log(f"💾 {comp_name} → junto do jogo")
                except Exception as e:
                    move_failures += 1
                    log(f"⚠️ Falha ao mover {comp_name}: {e}")

    # --- Remover conteúdo de outros sistemas (sem segundo walk de resgate) ---
    tracker.set_phase("clean", label="A limpar outros sistemas…")
    removed_foreign = 0
    foreign_errors = 0
    try:
        top_names = os.listdir(mount_path)
    except OSError as e:
        return False, f"Não foi possível listar o cartão: {e}", {}

    for name in top_names:
        if name in (".", ".."):
            continue
        full = os.path.join(mount_path, name)
        low = name.lower()

        if low in _KEEP_DIR_NAMES:
            continue
        if low in _KEEP_ROOT_FILES:
            continue

        try:
            real = os.path.realpath(full)
        except OSError:
            real = full
        if real in kept_paths:
            continue

        label = f"{name}/" if os.path.isdir(full) else name
        log(f"🧹 Removendo (outro sistema): {label}")
        if _remove_path_best_effort(full, log):
            removed_foreign += 1
        else:
            foreign_errors += 1

    os.makedirs(games_root, exist_ok=True)

    junk_removed = 0
    if os.path.isdir(games_root):
        for walk_root, dirs, files in os.walk(games_root):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if f.startswith("._") or f == ".DS_Store" or ext in JUNK_EXTS:
                    try:
                        os.remove(os.path.join(walk_root, f))
                        junk_removed += 1
                    except OSError:
                        pass

    empty_removed = _prune_empty_under(games_root, preserve_root=True)
    if os.path.isdir(roms_root):
        empty_removed += _prune_empty_under(roms_root, preserve_root=True)
        # Remover ROMs/ se ficou vazia (BIOS/resto preservados pelo prune)
        try:
            if not os.listdir(roms_root):
                os.rmdir(roms_root)
                empty_removed += 1
                log("🧹 Pasta ROMs/ vazia removida.")
        except OSError:
            pass

    invalidate_dspico_library_caches(mount_path)
    sync_volume(mount_path)
    tracker.phase = "done"
    tracker.finish("Concluído")

    stats = {
        "organized": organized,
        "games": games_moved,
        "apps": apps_moved,
        "retro": retro_moved,
        "companions": companions_moved,
        "removed_foreign": removed_foreign,
        "empty_dirs": empty_removed,
        "junk": junk_removed,
        "move_failures": move_failures,
        "foreign_errors": foreign_errors,
        "layout": mode,
        "counts": counts,
    }

    log("✅ Organização DSPico concluída.")
    if counts:
        for bucket, n in sorted(counts.items()):
            log(f"   - {bucket}: {n}")
    log(
        f"   - {games_moved} jogo(s), {apps_moved} app(s), {retro_moved} retro; "
        f"{companions_moved} save(s)."
    )
    log(f"   - {removed_foreign} item(ns) de outros sistemas removido(s).")
    log(f"   - {empty_removed} pasta(s) vazia(s); {junk_removed} lixo.")

    detail = ", ".join(f"{n} {p}" for p, n in sorted(counts.items())) or "0"
    where = labels.get(mode, mode)
    msg = (
        f"{organized} ficheiro(s) ({detail}); "
        f"{apps_moved} app(s) em Games/{APPS_DIRNAME}/; "
        f"{companions_moved} save(s); "
        f"{removed_foreign} item(ns) de outros sistemas removido(s). "
        f"Layout: {where}."
    )
    if move_failures and organized == 0 and candidates:
        return False, f"Organização falhou ({move_failures} erro(s)). {msg}", stats
    if move_failures or foreign_errors:
        return (
            True,
            f"{msg} ({move_failures + foreign_errors} aviso(s) — veja o log.)",
            stats,
        )
    return True, msg, stats


# --- Emunand ----------------------------------------------------------------


def ensure_emunand_skeleton(
    mount_path: str, log_callback=None
) -> tuple[bool, str, dict]:
    """Cria pastas oficiais de emunand (vazias) no microSD."""
    log = lambda msg: emit_log(log_callback, msg)
    created: list[str] = []
    undo = UndoStack()
    try:
        pico = _pico_dir(mount_path)
        os.makedirs(pico, exist_ok=True)
        for rel in EMUNAND_DIRS:
            path = os.path.join(mount_path, rel)
            if not os.path.isdir(path):
                os.makedirs(path, exist_ok=True)
                undo.push_remove(path)
                created.append(rel.replace("\\", "/"))
                log(f"📁 Criada {rel}/")
        sync_volume(mount_path)
        checklist = {
            "biosnds7": os.path.isfile(os.path.join(pico, "biosnds7.rom")),
            "twl_font": os.path.isfile(
                os.path.join(mount_path, "sys", "TWLFontTable.dat")
            ),
            "dirs_created": created,
        }
        msg = (
            f"Skeleton emunand pronto ({len(created)} pasta(s) novas)."
            if created
            else "Pastas emunand já existiam."
        )
        msg += " Importe biosnds7.rom e TWLFontTable.dat dos seus dumps."
        return True, msg, checklist
    except Exception as e:
        undo.rollback(log_callback, mount_path=mount_path)
        return False, str(e), {}


def import_biosnds7(
    mount_path: str, source_path: str, log_callback=None
) -> tuple[bool, str]:
    """Copia dump local do BIOS ARM7 DS para /_pico/biosnds7.rom (sem download)."""
    return _import_named_file(
        mount_path,
        source_path,
        dest_rel=os.path.join("_pico", "biosnds7.rom"),
        label="biosnds7.rom",
        log_callback=log_callback,
    )


def import_twl_font(
    mount_path: str, source_path: str, log_callback=None
) -> tuple[bool, str]:
    """Copia TWLFontTable.dat para /sys/ (dump próprio do utilizador)."""
    sys_dir = os.path.join(mount_path, "sys")
    os.makedirs(sys_dir, exist_ok=True)
    return _import_named_file(
        mount_path,
        source_path,
        dest_rel=os.path.join("sys", "TWLFontTable.dat"),
        label="TWLFontTable.dat",
        log_callback=log_callback,
    )


def _import_named_file(
    mount_path: str,
    source_path: str,
    *,
    dest_rel: str,
    label: str,
    log_callback=None,
) -> tuple[bool, str]:
    log = lambda msg: emit_log(log_callback, msg)
    if not isinstance(source_path, str) or not source_path.strip() or "\x00" in source_path:
        return False, f"Caminho de {label} inválido."
    src = os.path.realpath(os.path.expanduser(source_path.strip()))
    if not os.path.isfile(src):
        return False, f"Ficheiro não encontrado: {redact_path(src)}"
    try:
        size = os.path.getsize(src)
    except OSError as e:
        return False, str(e)
    if size < 16 or size > 16 * 1024 * 1024:
        return False, f"{label}: tamanho inválido."

    dest = os.path.join(mount_path, dest_rel)
    dest_parent = os.path.dirname(dest)
    os.makedirs(dest_parent, exist_ok=True)
    # Garantir destino sob mount
    try:
        common = os.path.commonpath(
            [os.path.realpath(mount_path), os.path.realpath(dest_parent)]
        )
    except ValueError:
        return False, "Destino fora do cartão."
    if os.path.normcase(common) != os.path.normcase(os.path.realpath(mount_path)):
        return False, "Destino fora do cartão."

    undo = UndoStack()
    try:
        bak = None
        if os.path.isfile(dest):
            bak = dest + f".bak_{os.getpid()}"
            shutil.copy2(dest, bak)
            undo.push_restore_file(bak, dest)
        copy_fast(src, dest, log_callback=log_callback)
        if bak is None:
            undo.push_remove(dest)
        sync_volume(mount_path)
        if bak and os.path.isfile(bak):
            try:
                os.remove(bak)
            except OSError:
                pass
        log(f"✅ {label} instalado.")
        return True, f"{label} copiado para o microSD."
    except Exception as e:
        undo.rollback(log_callback, mount_path=mount_path)
        return False, str(e)


# --- Settings ---------------------------------------------------------------


def get_dspico_settings(mount_path: str) -> dict[str, Any]:
    path = os.path.join(_pico_dir(mount_path), SETTINGS_FILENAME)
    if not os.path.isfile(path):
        return {
            "success": True,
            "settings": {},
            "exists": False,
            "path": f"/_pico/{SETTINGS_FILENAME}",
            "allowed_keys": sorted(SETTINGS_ALLOWED_KEYS),
            "layouts": sorted(SETTINGS_LAYOUTS),
            "sort_modes": sorted(SETTINGS_SORT_MODES),
        }
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return {"success": False, "error": f"settings.json inválido: {e}"}
    if not isinstance(data, dict):
        return {"success": False, "error": "settings.json: raíz deve ser objecto."}
    return {
        "success": True,
        "settings": data,
        "exists": True,
        "path": f"/_pico/{SETTINGS_FILENAME}",
        "allowed_keys": sorted(SETTINGS_ALLOWED_KEYS),
        "layouts": sorted(SETTINGS_LAYOUTS),
        "sort_modes": sorted(SETTINGS_SORT_MODES),
    }


def set_dspico_settings(
    mount_path: str, patch: dict, log_callback=None
) -> tuple[bool, str]:
    """Atualiza chaves allowlisted em /_pico/settings.json (merge)."""
    log = lambda msg: emit_log(log_callback, msg)
    if not isinstance(patch, dict):
        return False, "Patch de settings inválido."

    clean: dict[str, Any] = {}
    for key, value in patch.items():
        if key not in SETTINGS_ALLOWED_KEYS:
            return False, f"Chave de settings não permitida: {key!r}"
        if key == "romBrowserLayout" and value not in SETTINGS_LAYOUTS:
            return False, f"Layout inválido: {value!r}"
        if key == "romBrowserSortMode" and value not in SETTINGS_SORT_MODES:
            return False, f"Ordenação inválida: {value!r}"
        if key == "language" and not isinstance(value, str):
            return False, "language deve ser string."
        if key == "theme" and not isinstance(value, str):
            return False, "theme deve ser string."
        if key == "lastUsedFilePath" and not isinstance(value, str):
            return False, "lastUsedFilePath deve ser string."
        if key == "fileAssociations" and not isinstance(value, (dict, list)):
            return False, "fileAssociations inválido."
        clean[key] = value

    pico = _pico_dir(mount_path)
    os.makedirs(pico, exist_ok=True)
    path = os.path.join(pico, SETTINGS_FILENAME)

    current: dict[str, Any] = {}
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                current = loaded
        except (OSError, json.JSONDecodeError):
            current = {}

    current.update(clean)
    partial = path + ".partial"
    undo = UndoStack()
    bak = None
    try:
        if os.path.isfile(path):
            bak = path + f".bak_{os.getpid()}"
            shutil.copy2(path, bak)
            undo.push_restore_file(bak, path)
        with open(partial, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(partial, path)
        if bak is None:
            undo.push_remove(path)
        sync_volume(mount_path)
        if bak and os.path.isfile(bak):
            try:
                os.remove(bak)
            except OSError:
                pass
        log("✅ settings.json actualizado.")
        return True, "Definições Pico Launcher guardadas."
    except Exception as e:
        try:
            if os.path.exists(partial):
                os.remove(partial)
        except OSError:
            pass
        undo.rollback(log_callback, mount_path=mount_path)
        return False, str(e)


# --- Firmware UF2 / RPI-RP2 -------------------------------------------------


def list_rp2_volumes() -> list[dict[str, str]]:
    """
    Detecta volumes BOOTSEL do RP2040 (RPI-RP2).
    Não passa por is_safe_mount_path de SD — volume especial de flash.
    """
    found: list[dict[str, str]] = []
    system = platform.system()

    candidates: list[str] = []
    if system == "Darwin":
        vol_root = "/Volumes"
        try:
            names = os.listdir(vol_root)
        except OSError:
            names = []
        for name in names:
            if name.startswith("."):
                continue
            candidates.append(os.path.join(vol_root, name))
    elif system == "Windows":
        import string

        for letter in string.ascii_uppercase:
            root = f"{letter}:\\"
            if os.path.isdir(root):
                candidates.append(root)
    else:
        for base in ("/media", "/run/media", "/mnt"):
            if not os.path.isdir(base):
                continue
            try:
                for user_or_vol in os.listdir(base):
                    p1 = os.path.join(base, user_or_vol)
                    if not os.path.isdir(p1):
                        continue
                    # /media/USER/VOL or /mnt/VOL
                    try:
                        children = os.listdir(p1)
                    except OSError:
                        children = []
                    # Se parece volume directo
                    if _looks_like_rp2(p1):
                        candidates.append(p1)
                        continue
                    for child in children:
                        candidates.append(os.path.join(p1, child))
            except OSError:
                continue

    seen: set[str] = set()
    for path in candidates:
        if not os.path.isdir(path):
            continue
        real = os.path.realpath(path)
        if real in seen:
            continue
        if not _looks_like_rp2(path):
            continue
        seen.add(real)
        found.append(
            {
                "name": os.path.basename(path.rstrip("/\\")) or path,
                "mount_path": path,
            }
        )
    return found


def _looks_like_rp2(mount_path: str) -> bool:
    base = os.path.basename(mount_path.rstrip("/\\")).lower()
    if base in _RP2_NAMES:
        return True
    # Marcadores típicos do volume UF2 BOOTSEL
    info_uf2 = os.path.join(mount_path, "INFO_UF2.TXT")
    index = os.path.join(mount_path, "INDEX.HTM")
    if os.path.isfile(info_uf2) or (
        os.path.isfile(index) and base.startswith("rpi")
    ):
        return True
    return False


def is_rp2_volume(mount_path: str) -> bool:
    if not isinstance(mount_path, str) or not mount_path.strip() or "\x00" in mount_path:
        return False
    path = mount_path.strip()
    if not os.path.isdir(path):
        return False
    return _looks_like_rp2(path)


def flash_dspico_firmware(
    rp2_mount_path: str, log_callback=None
) -> tuple[bool, str]:
    """
    Descarrega DSpico.uf2 oficial pinado (LNH) e copia para o volume RPI-RP2.
    Sem path de UF2 da UI — só cache pinado.
    """
    log = lambda msg: emit_log(log_callback, msg)

    if not dspico_firmware_uf2_ready():
        return (
            False,
            "Firmware .uf2 oficial ainda não está disponível nas releases "
            "LNH-team/dspico-firmware. Compile via o GUIDE oficial ou aguarde "
            "publicação do asset; builds de terceiros não são suportados.",
        )

    if not is_rp2_volume(rp2_mount_path):
        return False, "Volume não parece RPI-RP2 (BOOTSEL)."

    assert_dspico_cache_key("dspico_firmware_uf2")
    try:
        uf2_path = ensure_cached("dspico_firmware_uf2", log_callback)
    except Exception as e:
        return False, f"Não foi possível obter o UF2 oficial: {e}"

    dest_name = os.path.basename(uf2_path)
    if not dest_name.lower().endswith(".uf2"):
        dest_name = "DSpico.uf2"
    dest = os.path.join(rp2_mount_path, dest_name)

    log("=== Gravando firmware DSPico oficial no RPI-RP2 ===")
    try:
        # Cópia directa — o RP2040 ejeta ao aceitar o UF2
        with open(uf2_path, "rb") as src, open(dest, "wb") as out:
            shutil.copyfileobj(src, out, length=1024 * 1024)
            out.flush()
            try:
                os.fsync(out.fileno())
            except OSError:
                pass  # volume pode desaparecer a meio
        log("✅ UF2 oficial enviado. O volume RPI-RP2 deve ejectar sozinho.")
        return True, "Firmware DSPico oficial gravado no cartucho."
    except OSError as e:
        # Eject durante escrita é comum e frequentemente = sucesso
        msg = str(e).lower()
        if "no such" in msg or "eject" in msg or "input/output" in msg:
            log("ℹ️ Volume RPI-RP2 desapareceu (normal após flash).")
            return True, "Firmware enviado (volume RPI-RP2 ejectou)."
        return False, f"Falha ao gravar UF2: {e}"
