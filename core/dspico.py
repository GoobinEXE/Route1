"""Pacote DSPico: Pico Launcher + Loader oficiais LNH, Games/, emunand, settings, UF2."""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import tempfile
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
from core.dspico_emulators import count_installed_emulators
from core.logging_util import emit_log
from core.privacy import redact_path
from core.rom_cleaner import (
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
GAME_EXTS = frozenset({".nds", ".dsi", ".ids"})
SETTINGS_FILENAME = "settings.json"

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

# Não recolher jogos dentro destas pastas (sistema / CFW / emunand / emuladores).
# Nota: `roms`/`ROMs` NÃO entra aqui — jogos NDS em /roms/ do TWiLight são
# resgatados; a pasta em si é preservada em _KEEP_DIR_NAMES (emuladores Pico).
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


def _count_games(mount_path: str) -> int:
    """Conta .nds/.dsi/.ids em Games/ e também soltos na raiz (exceto launcher)."""
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
                if os.path.splitext(f)[1].lower() in GAME_EXTS:
                    n += 1
    try:
        for f in os.listdir(mount_path):
            if _is_picoboot(f) or f.startswith("."):
                continue
            full = os.path.join(mount_path, f)
            if not os.path.isfile(full):
                continue
            if os.path.splitext(f)[1].lower() in GAME_EXTS:
                n += 1
    except OSError:
        pass
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
    log = lambda msg: emit_log(log_callback, msg)
    log("=== Instalando pacote DSPico (Pico Launcher + Loader oficiais LNH) ===")

    try:
        assert_dspico_cache_key("pico_launcher")
        assert_dspico_cache_key("pico_loader_dspico")
        launcher_zip = ensure_cached("pico_launcher", log_callback)
        loader_zip = ensure_cached("pico_loader_dspico", log_callback)
        launcher_dir = _extract_zip_safe(
            launcher_zip, os.path.join(CACHE_DIR, "Pico_Launcher"), log_callback
        )
        loader_dir = _extract_zip_safe(
            loader_zip, os.path.join(CACHE_DIR, "Pico_Loader_DSPICO"), log_callback
        )
    except Exception as e:
        return False, f"Não foi possível obter o pacote DSPico: {e}"

    assembled = os.path.join(CACHE_DIR, "DSPico_SD_ready")
    try:
        _assemble_dspico_staging(launcher_dir, loader_dir, assembled)
    except Exception as e:
        return False, str(e)

    if not dspico_markers_ok(assembled):
        return False, "Árvore DSPico montada incompleta após assemble."

    undo = UndoStack()
    baks: list[Optional[str]] = []
    try:
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

        log(
            "🎉 MicroSD DSPico pronto. Insira no cartucho "
            "(firmware .uf2 oficial LNH já deve estar gravado)."
        )
        return True, "Pacote DSPico instalado no microSD."
    except Exception as e:
        log(f"⚠️ Falha ao instalar DSPico — revertendo: {e}")
        undo.rollback(log_callback, mount_path=mount_path)
        return False, str(e)


# --- Games/ -----------------------------------------------------------------


def browse_dspico_games(mount_path: str, rel_dir: str = "") -> dict[str, Any]:
    """Lista pastas e jogos num nível sob Games/."""
    if not os.path.isdir(mount_path):
        return {
            "success": False,
            "error": "Cartão inexistente.",
            "dirs": [],
            "files": [],
        }

    norm = _normalize_rel_dir(rel_dir)
    if norm is None:
        return {
            "success": False,
            "error": "Pasta inválida.",
            "dirs": [],
            "files": [],
        }

    games_root = _games_root(mount_path)
    if norm:
        target = _resolve_under_games(mount_path, norm)
        if not target or not os.path.isdir(target):
            return {
                "success": False,
                "error": f"Pasta Games/{norm}/ inexistente.",
                "dirs": [],
                "files": [],
                "rel_dir": norm,
            }
    else:
        os.makedirs(games_root, exist_ok=True)
        target = os.path.realpath(games_root)

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
                rel = os.path.relpath(full, games_root).replace("\\", "/")
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
            if name.endswith(".partial") or name == ".DS_Store":
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext not in GAME_EXTS:
                continue
            if is_companion_ext(ext):
                continue
            try:
                size = os.path.getsize(full)
            except OSError:
                size = 0
            try:
                rel = os.path.relpath(full, games_root).replace("\\", "/")
            except ValueError:
                continue
            entry = {
                "name": name,
                "rel_path": rel,
                "display_name": os.path.splitext(name)[0],
                "size": size,
                "size_label": _format_size(size),
                "type": "file",
                "ext": ext,
            }
            try:
                from core.pico_artwork import enrich_dspico_game_entry

                enrich_dspico_game_entry(mount_path, entry, with_preview=True)
            except Exception:
                entry["has_cover"] = False
                entry["has_icon"] = False
            files_out.append(entry)

    return {
        "success": True,
        "rel_dir": norm,
        "dirs": dirs_out,
        "files": files_out,
        "count": len(dirs_out) + len(files_out),
        "root_label": GAMES_DIRNAME,
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


def import_dspico_games(
    mount_path: str,
    source_paths: list,
    dest_rel_dir: str = "",
    log_callback=None,
) -> tuple[bool, str, dict]:
    """Copia ROMs .nds/.dsi/.ids do host para Games/."""
    log = lambda msg: emit_log(log_callback, msg)
    if not isinstance(source_paths, list) or not source_paths:
        return False, "Nenhum ficheiro seleccionado.", {}

    dest_norm = _normalize_rel_dir(dest_rel_dir)
    if dest_norm is None:
        return False, "Pasta de destino inválida.", {}

    games_root = _games_root(mount_path)
    os.makedirs(games_root, exist_ok=True)
    if dest_norm:
        dest_dir = _resolve_under_games(mount_path, dest_norm)
        if not dest_dir or not os.path.isdir(dest_dir):
            return False, f"Destino Games/{dest_norm}/ inexistente.", {}
    else:
        dest_dir = games_root

    undo = UndoStack()
    copied = 0
    skipped = 0
    errors: list[str] = []

    log(f"=== Importar {len(source_paths)} ficheiro(s) → Games/{dest_norm or ''} ===")

    for raw in source_paths:
        if not isinstance(raw, str) or not raw.strip() or "\x00" in raw:
            skipped += 1
            continue
        src = os.path.realpath(os.path.expanduser(raw.strip()))
        if not os.path.isfile(src):
            errors.append(f"Inexistente: {redact_path(src)}")
            skipped += 1
            continue
        ext = os.path.splitext(src)[1].lower()
        if ext not in GAME_EXTS:
            errors.append(f"Extensão não suportada: {os.path.basename(src)}")
            skipped += 1
            continue

        base_name = os.path.basename(src)
        dest = os.path.join(dest_dir, base_name)
        # unique if exists
        if os.path.exists(dest):
            stem, e = os.path.splitext(base_name)
            n = 2
            while True:
                cand = os.path.join(dest_dir, f"{stem}_{n}{e}")
                if not os.path.exists(cand):
                    dest = cand
                    break
                n += 1

        try:
            common = os.path.commonpath(
                [os.path.realpath(games_root), os.path.realpath(os.path.dirname(dest))]
            )
        except ValueError:
            errors.append("Destino fora de Games/.")
            skipped += 1
            continue
        if os.path.normcase(common) != os.path.normcase(os.path.realpath(games_root)):
            errors.append("Destino fora de Games/.")
            skipped += 1
            continue

        try:
            copy_fast(src, dest, log_callback=log_callback)
            undo.push_remove(dest)
            copied += 1
            rel = os.path.relpath(dest, games_root).replace("\\", "/")
            log(f"📥 {base_name} → Games/{rel}")

            # sidecars .sav próximos
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
                                copy_fast(sav_src, sav_dest, log_callback=log_callback)
                                undo.push_remove(sav_dest)
                        break
        except Exception as e:
            errors.append(f"{base_name}: {e}")
            skipped += 1

    sync_volume(mount_path)
    stats = {"copied": copied, "skipped": skipped, "errors": len(errors)}
    if copied == 0 and errors:
        return False, errors[0], stats
    msg = f"{copied} jogo(s) em Games/."
    if skipped:
        msg += f" {skipped} ignorado(s)."
    return True, msg, stats


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

    sync_volume(mount_path)
    stats = {"removed": removed, "errors": len(errors)}
    if removed == 0:
        return False, (errors[0] if errors else "Nada removido."), stats
    return True, f"{removed} ficheiro(s) removido(s).", stats


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


def _dspico_platform(ext: str, unitcode) -> str:
    """Pasta de plataforma no DSPico: nds ou dsi."""
    try:
        uc = int(unitcode) if unitcode is not None else 0
    except (TypeError, ValueError):
        uc = 0
    if ext == ".dsi" or uc == 2:
        return "dsi"
    return "nds"


def _dspico_dest_dir(
    mount_path: str, platform: str, franchise: Optional[str], layout: str
) -> str:
    """Directório de destino absoluto conforme o layout DSPico."""
    if layout == LAYOUT_ROOT:
        return mount_path
    games = _games_root(mount_path)
    if layout == LAYOUT_GAMES:
        return games
    if layout == LAYOUT_PLATFORM:
        return os.path.join(games, platform or "nds")
    # franchise
    folder = franchise or UNKNOWN_FRANCHISE
    cleaned = _sanitize_dir_name(folder) or UNKNOWN_FRANCHISE
    return os.path.join(games, cleaned)


def _is_picoboot(name: str) -> bool:
    return (name or "").lower() == _PICOBOOT_NAME


def _should_skip_collect_dir(name: str) -> bool:
    if not name or name.startswith("."):
        return True
    low = name.lower()
    return low in _COLLECT_SKIP_DIRS or low in _SKIP_DIR_LOWER


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
        # limpar lixo macOS antes de rmdir
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


def organize_dspico_sd(
    mount_path: str, layout=LAYOUT_GAMES, log_callback=None
) -> tuple[bool, str, dict]:
    """
    Limpa o microSD de conteúdo de outros sistemas e organiza jogos NDS/DSi.

    Mantém o necessário para DSPico: `_picoboot.nds`, `_pico/`, `Games/`,
    emunand (`photo/`, `shared1/`, `shared2/`, `sys/`), e suporte a emuladores
    (`ROMs/`, `_gba/`, `Emulators/`, `data/`, `snemul.cfg`).

    Layouts:
    - franchise: Games/<franquia>/
    - platform:  Games/nds/ ou Games/dsi/
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

    if not isinstance(mount_path, str) or not mount_path.strip():
        return False, "Caminho do cartão inválido.", {}
    if not os.path.isdir(mount_path):
        return False, "Cartão inexistente.", {}

    mount_norm = mount_path.rstrip("/\\")
    games_root = _games_root(mount_path)
    if mode != LAYOUT_ROOT:
        os.makedirs(games_root, exist_ok=True)

    # --- 1) Recolher jogos e companions ------------------------------------
    rom_candidates = []  # (name, full, ext, platform, game_code, raw_title)
    companion_candidates = []  # (name, full)

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

            if ext not in GAME_EXTS:
                continue

            header = get_nds_header_info(full)
            raw_title, game_code, unitcode, maker = header
            kind = classify_nds_kind(
                raw_title, game_code, maker, f, at_sd_root=at_sd_root
            )
            if kind == "system":
                continue
            if _is_picoboot(f):
                continue

            plat = _dspico_platform(ext, unitcode)
            rom_candidates.append(
                (f, full, ext, plat, game_code, raw_title)
            )

    log(
        f"Encontrados: {len(rom_candidates)} jogo(s) e "
        f"{len(companion_candidates)} save(s)/sidecar(s)."
    )

    companions_by_stem: dict[str, list] = {}
    for comp_name, comp_path in companion_candidates:
        for key, suffix in companion_index_keys(comp_name):
            companions_by_stem.setdefault(key, []).append(
                (comp_name, comp_path, suffix)
            )

    handled_companions: set[str] = set()
    kept_paths: set[str] = set()
    organized = 0
    companions_moved = 0
    move_failures = 0
    counts: dict[str, int] = {}

    # Sempre preservar launcher + _pico
    pico_boot = os.path.join(mount_path, _PICOBOOT_NAME)
    if os.path.isfile(pico_boot):
        kept_paths.add(os.path.realpath(pico_boot))
    pico_dir = _pico_dir(mount_path)
    if os.path.isdir(pico_dir):
        kept_paths.add(os.path.realpath(pico_dir))

    for original_name, full_path, ext, platform, game_code, raw_title in rom_candidates:
        if not os.path.exists(full_path):
            continue

        clean_name = clean_rom_filename(original_name, game_code)
        out_ext = ".nds" if ext == ".ids" else ext

        franchise = None
        if mode == LAYOUT_FRANCHISE:
            franchise = detect_franchise(
                clean_name,
                game_code=game_code,
                raw_title=raw_title,
                original_name=original_name,
            )

        dest_dir = _dspico_dest_dir(mount_path, platform, franchise, mode)
        try:
            os.makedirs(dest_dir, exist_ok=True)
        except OSError as e:
            move_failures += 1
            log(f"⚠️ Falha ao criar pasta para {original_name}: {e}")
            continue

        target = os.path.join(dest_dir, f"{clean_name}{out_ext}")
        try:
            new_path = _safe_move(full_path, target)
            organized += 1
            kept_paths.add(os.path.realpath(new_path))
            try:
                if mode == LAYOUT_ROOT:
                    rel = os.path.basename(new_path)
                else:
                    rel = os.path.relpath(new_path, games_root).replace("\\", "/")
            except ValueError:
                rel = os.path.basename(new_path)
            where = rel if mode == LAYOUT_ROOT else f"Games/{rel}"
            if os.path.abspath(full_path) != os.path.abspath(new_path):
                log(f"🎮 {original_name} → {where}")
            else:
                log(f"🎮 {where} (já no lugar)")

            if mode == LAYOUT_FRANCHISE:
                bucket = franchise or UNKNOWN_FRANCHISE
            elif mode == LAYOUT_PLATFORM:
                bucket = platform
            elif mode == LAYOUT_ROOT:
                bucket = "raiz"
            else:
                bucket = "Games"
            counts[bucket] = counts.get(bucket, 0) + 1
        except Exception as e:
            move_failures += 1
            log(f"⚠️ Falha ao mover {original_name}: {e}")
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

    # --- 2) Remover conteúdo de outros sistemas ----------------------------
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

        # Resgatar jogos ainda dentro de pastas a apagar (falhas parciais)
        if os.path.isdir(full) and not os.path.islink(full):
            for walk_root, dirs, files in os.walk(full, topdown=True):
                dirs[:] = [d for d in dirs if not _should_skip_collect_dir(d)]
                for f in files:
                    if f.startswith(".") or f.endswith(".partial"):
                        continue
                    ext = os.path.splitext(f)[1].lower()
                    if ext not in GAME_EXTS:
                        continue
                    if _is_picoboot(f):
                        continue
                    src = os.path.join(walk_root, f)
                    header = get_nds_header_info(src)
                    raw_title, game_code, unitcode, _maker = header
                    plat = _dspico_platform(ext, unitcode)
                    clean_name = clean_rom_filename(f, game_code)
                    out_ext = ".nds" if ext == ".ids" else ext
                    franchise = None
                    if mode == LAYOUT_FRANCHISE:
                        franchise = detect_franchise(
                            clean_name,
                            game_code=game_code,
                            raw_title=raw_title,
                            original_name=f,
                        )
                    dest_dir = _dspico_dest_dir(
                        mount_path, plat, franchise, mode
                    )
                    try:
                        os.makedirs(dest_dir, exist_ok=True)
                        new_path = _safe_move(
                            src, os.path.join(dest_dir, f"{clean_name}{out_ext}")
                        )
                        kept_paths.add(os.path.realpath(new_path))
                        organized += 1
                        log(f"🎮 (resgate) {f} → layout DSPico")
                    except Exception as e:
                        move_failures += 1
                        log(f"⚠️ Resgate falhou para {f}: {e}")

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

    # Garantir Games/ (estrutura do pacote) mesmo em layout root
    os.makedirs(games_root, exist_ok=True)

    # Preservar pastas de emunand se existirem (já em _KEEP_DIR_NAMES)
    # Limpar lixo macOS sob Games/
    junk_removed = 0
    if os.path.isdir(games_root):
        for walk_root, dirs, files in os.walk(games_root):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in files:
                if f.startswith("._") or f == ".DS_Store":
                    try:
                        os.remove(os.path.join(walk_root, f))
                        junk_removed += 1
                    except OSError:
                        pass

    empty_removed = _prune_empty_under(games_root, preserve_root=True)

    sync_volume(mount_path)

    stats = {
        "organized": organized,
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
            log(f"   - {bucket}: {n} jogo(s)")
    log(f"   - {organized} jogo(s) organizados; {companions_moved} save(s).")
    log(f"   - {removed_foreign} item(ns) de outros sistemas removido(s).")
    log(f"   - {empty_removed} pasta(s) vazia(s); {junk_removed} lixo macOS.")

    detail = ", ".join(f"{n} {p}" for p, n in sorted(counts.items())) or "0"
    where = labels.get(mode, mode)
    msg = (
        f"{organized} jogo(s) ({detail}); "
        f"{companions_moved} save(s); "
        f"{removed_foreign} item(ns) de outros sistemas removido(s). "
        f"Layout: {where}."
    )
    if move_failures and organized == 0 and rom_candidates:
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
