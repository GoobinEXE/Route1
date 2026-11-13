"""RouteDex: gestão nativa da biblioteca Pico Launcher no Route Pico.

Port em Python (stdlib) das regras do PicoDex de rasalopa
(https://github.com/rasalopa/picodex, licença MIT, ver
docs/licenses/PicoDex-LICENSE.txt), com diferenças deliberadas:

* ``gamedata.json`` é lido e escrito sem perder campos desconhecidos, e um
  ficheiro que não faz parse nunca é sobrescrito (mesma regra do launcher).
* Toda a escrita no SD é atómica (``.partial`` + fsync + ``os.replace``) e
  toda a remoção guarda primeiro uma cópia no host.
* A versão do Pico Loader / Launcher é identificada offline contra
  ``core/data/pico_manifest.json`` (gerado por ``tools/gen_pico_manifest.py``).

Formatos seguidos (fontes oficiais):

* gamedata.json / screenshots / fundos noturnos: docs Enhanced.md e GameData.md
  de rasalopa/pico-launcher-enhanced.
* banner.bnr / icon.bmp / cover.bmp de pasta: docs/Customization.md do
  Pico Launcher.
* usrcheat.dat: cabeçalho "R4 CheatCode" v0x100 (docs/Cheats.md do Pico
  Launcher; layout como em melonDS ARDatabaseDAT.cpp).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import struct
import time
from collections import OrderedDict
from typing import Any, Callable, Iterable, Optional

from core.cache import CACHE_DIR
from core.dspico import GAME_EXTS, LIBRARY_FILE_EXTS, _COLLECT_SKIP_DIRS
from core.logging_util import emit_log
from core.privacy import redact_path

LogFn = Optional[Callable[[str], None]]

CREDITS = {
    "routedex": {
        "name": "PicoDex",
        "author": "rasalopa",
        "license": "MIT",
        "url": "https://github.com/rasalopa/picodex",
    },
    "enhanced": {
        "name": "Pico Launcher Enhanced / Pico Loader Enhanced",
        "author": "rasalopa",
        "license": "Zlib",
        "url": "https://github.com/rasalopa/pico-launcher-enhanced",
    },
    "upstream": {
        "name": "Pico Launcher / Pico Loader",
        "author": "LNH team",
        "license": "Zlib",
        "url": "https://github.com/LNH-team",
    },
}

PICO_DIR = "_pico"
GAMEDATA_NAME = "gamedata.json"
SCREENSHOTS_DIR = "screenshots"
USRCHEAT_NAME = "usrcheat.dat"

REQUIRED_LOADER_FILES = ("picoLoader7.bin", "picoLoader9.bin", "aplist.bin", "savelist.bin")
OPTIONAL_LOADER_FILES = ("patchlist.bin", "biosnds7.rom")
LOADER_HASHED_FILES = ("picoLoader7.bin", "picoLoader9.bin", "aplist.bin", "savelist.bin", "patchlist.bin")

JUNK_DIR_NAMES = (".Spotlight-V100", ".Trashes", ".fseventsd", ".TemporaryItems")
SAVES_FOLDER = "saves"
MAX_SAVE_SLOT = 9

BANNER_SIZE = 0x840
ICON_BITMAP_SIZE = 0x200
ICON_PALETTE_SIZE = 0x20
_TRANSPARENT_PLACEHOLDER = 0x7C1F
_BG_BYTES = 256 * 192 * 2

_USRCHEAT_MAGIC = b"R4 CheatCode\x00\x01\x00\x00"
_USRCHEAT_MAX_BYTES = 64 * 1024 * 1024

_MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "pico_manifest.json")
_manifest_cache: Optional[dict[str, Any]] = None

_ENHANCED_LAUNCHER_MARKER = b"rasalopa/pico-launcher-enhanced"
_ENHANCED_LOADER_RE = re.compile(rb"Pico Loader Enhanced v([0-9][0-9A-Za-z.\-]{0,20})")
_SHOT_RE = re.compile(r"^shot(\d+)_(top|bot)\.bmp$", re.IGNORECASE)


class RouteDexError(RuntimeError):
    """Erro com mensagem PT pronta para a UI."""


# --------------------------------------------------------------------------- #
# Infra: paths, hashing, escrita atómica, cópia de segurança
# --------------------------------------------------------------------------- #


def _pico(mount_path: str, *parts: str) -> str:
    return os.path.join(mount_path, PICO_DIR, *parts)


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_or_none(path: str) -> Optional[str]:
    try:
        return _sha256_file(path) if os.path.isfile(path) else None
    except OSError:
        return None


def resolve_card_path(mount_path: str, rel: str) -> str:
    """Resolve ``rel`` (posix, relativo à raiz do cartão) sem sair do volume."""
    if not isinstance(rel, str):
        raise RouteDexError("Caminho inválido.")
    clean = rel.replace("\\", "/").strip().strip("/")
    if "\x00" in clean:
        raise RouteDexError("Caminho inválido.")
    parts = [p for p in clean.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise RouteDexError("Caminho fora do cartão.")
    root = os.path.realpath(mount_path)
    full = os.path.realpath(os.path.join(root, *parts)) if parts else root
    if full != root and not full.startswith(root + os.sep):
        raise RouteDexError("Caminho fora do cartão.")
    return full


def _rel(mount_path: str, path: str) -> str:
    return os.path.relpath(path, mount_path).replace(os.sep, "/")


def _atomic_write(path: str, data: bytes) -> None:
    """Escreve ``data`` em ``path`` via .partial + fsync + os.replace e confere o hash."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".partial"
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        with open(tmp, "rb") as f:
            if hashlib.sha256(f.read()).digest() != hashlib.sha256(data).digest():
                raise RouteDexError("Verificação pós-escrita falhou; ficheiro original mantido.")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def _host_backup_dir(label: str) -> str:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(CACHE_DIR, "routedex_backup", f"{stamp}_{label}")
    os.makedirs(path, exist_ok=True)
    return path


def _backup_then_remove(mount_path: str, paths: Iterable[str], label: str, log: LogFn) -> dict[str, Any]:
    """Copia cada ficheiro para o host (mantendo o caminho relativo) e só então remove."""
    backup_root: Optional[str] = None
    removed: list[str] = []
    failed: list[str] = []
    for path in paths:
        rel = _rel(mount_path, path)
        try:
            if os.path.isdir(path):
                if backup_root is None:
                    backup_root = _host_backup_dir(label)
                shutil.copytree(path, os.path.join(backup_root, rel), dirs_exist_ok=True)
                shutil.rmtree(path)
            elif os.path.isfile(path):
                if backup_root is None:
                    backup_root = _host_backup_dir(label)
                dst = os.path.join(backup_root, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(path, dst)
                if _sha256_file(dst) != _sha256_file(path):
                    raise RouteDexError("cópia de segurança não confere")
                os.remove(path)
            else:
                continue
            removed.append(rel)
        except (OSError, RouteDexError) as e:
            failed.append(rel)
            emit_log(log, f"⚠️ Não removido {rel}: {e}")
    return {
        "removed": removed,
        "failed": failed,
        "backup_dir": redact_path(backup_root) if backup_root else "",
    }


# --------------------------------------------------------------------------- #
# Biblioteca: ROMs, saves e lixo numa só passagem
# --------------------------------------------------------------------------- #


def _system_for(ext: str) -> str:
    ext = ext.lower()
    if ext in GAME_EXTS:
        return "nds"
    if ext in (".gba", ".agb"):
        return "gba"
    return "retro"


def read_game_code(path: str, system: str) -> Optional[str]:
    """Game code do cabeçalho (NDS @0x0C, GBA @0xAC) ou None."""
    offset = {"nds": 0x0C, "gba": 0xAC}.get(system)
    if offset is None:
        return None
    try:
        with open(path, "rb") as f:
            f.seek(offset)
            raw = f.read(4)
    except OSError:
        return None
    if len(raw) != 4:
        return None
    try:
        code = raw.decode("ascii")
    except UnicodeDecodeError:
        return None
    return code if is_usable_game_code(code) else None


def is_usable_game_code(code: Optional[str]) -> bool:
    """ASCII imprimível, não vazio e não só '#' (placeholder de homebrew)."""
    if not code:
        return False
    if any(ord(c) < 0x20 or ord(c) >= 0x7F for c in code):
        return False
    return any(c != "#" for c in code)


def _is_junk_file(name: str) -> bool:
    return name.startswith("._") or name == ".DS_Store"


def _fsevents_prevention_only(path: str) -> bool:
    try:
        names = os.listdir(path)
    except OSError:
        return False
    return bool(names) and all(n.lower() == "no_log" for n in names)


def scan_card(mount_path: str) -> dict[str, Any]:
    """Uma passagem pelo cartão: jogos, saves e lixo de metadados macOS."""
    games: list[dict[str, Any]] = []
    saves: list[dict[str, Any]] = []
    junk: list[str] = []
    skip = {s.lower() for s in _COLLECT_SKIP_DIRS} - {".fseventsd", ".trashes", ".spotlight-v100"}
    for root, dirs, files in os.walk(mount_path):
        rel_root = _rel(mount_path, root)
        rel_root = "" if rel_root == "." else rel_root
        keep_dirs = []
        for d in dirs:
            full = os.path.join(root, d)
            if d in JUNK_DIR_NAMES:
                if not (d == ".fseventsd" and _fsevents_prevention_only(full)):
                    junk.append(_rel(mount_path, full))
                continue
            if d.lower() in skip or d.startswith("."):
                continue
            keep_dirs.append(d)
        dirs[:] = keep_dirs
        for name in files:
            if _is_junk_file(name):
                junk.append(f"{rel_root}/{name}" if rel_root else name)
                continue
            if name.startswith("."):
                continue
            stem, ext = os.path.splitext(name)
            low = ext.lower()
            rel = f"{rel_root}/{name}" if rel_root else name
            if low in LIBRARY_FILE_EXTS:
                if not rel_root and name.lower() == "_picoboot.nds":
                    continue
                games.append({"rel": rel, "name": name, "dir": rel_root, "system": _system_for(low)})
            elif low == ".sav" or re.fullmatch(r"\.sav[1-9]", low):
                saves.append({"rel": rel, "name": name, "dir": rel_root})
    # Lixo dentro de /_pico (o walk acima não entra lá).
    pico = _pico(mount_path)
    if os.path.isdir(pico):
        for root, _dirs, files in os.walk(pico):
            for name in files:
                if _is_junk_file(name):
                    junk.append(_rel(mount_path, os.path.join(root, name)))
    games.sort(key=lambda g: g["rel"].lower())
    return {"games": games, "saves": saves, "junk": sorted(set(junk))}


# --------------------------------------------------------------------------- #
# Identificação de versões (launcher / loader) — manifesto offline
# --------------------------------------------------------------------------- #


def load_manifest() -> dict[str, Any]:
    global _manifest_cache
    if _manifest_cache is None:
        try:
            with open(_MANIFEST_PATH, encoding="utf-8") as f:
                data = json.load(f)
            _manifest_cache = data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            _manifest_cache = {}
    return _manifest_cache


def identify_launcher(mount_path: str) -> dict[str, Any]:
    """Que launcher está em /_picoboot.nds: oficial (LNH) ou Enhanced, e versão."""
    path = os.path.join(mount_path, "_picoboot.nds")
    if not os.path.isfile(path):
        return {"present": False, "variant": None, "version": None, "known": False}
    digest = _sha256_or_none(path)
    table = load_manifest().get("launcher") or {}
    for variant in ("official", "enhanced"):
        tag = (table.get(variant) or {}).get(digest or "")
        if tag:
            if tag.startswith("enhanced-"):
                tag = tag[len("enhanced-"):]
            return {"present": True, "variant": variant, "version": tag, "known": True}
    variant = "unknown"
    try:
        with open(path, "rb") as f:
            if _ENHANCED_LAUNCHER_MARKER in f.read(4 * 1024 * 1024):
                variant = "enhanced"
    except OSError:
        pass
    return {"present": True, "variant": variant, "version": None, "known": False}


def _intersect(sets: list[set[str]]) -> set[str]:
    out = set(sets[0]) if sets else set()
    for s in sets[1:]:
        out &= s
    return out


def identify_loader(mount_path: str) -> dict[str, Any]:
    """Port de identifyLoader (PicoDex loaderVersion.ts), ciente do Loader Enhanced.

    status: identified | mixed | unrecognised | no-loader
    variant: official | enhanced (picoLoader7/9 do fork) | None
    """
    manifest = load_manifest()
    loader = manifest.get("loader") or {}
    order = [r.get("tag") for r in loader.get("releases") or [] if isinstance(r, dict)]
    latest_known = order[-1] if order else ""
    files_tbl = loader.get("files") or {}
    builds_tbl = loader.get("builds") or {}
    enh_tbl = (manifest.get("loader_enhanced") or {}).get("files") or {}

    hashes = {name: _sha256_or_none(_pico(mount_path, name)) for name in LOADER_HASHED_FILES}
    missing = [n for n, h in hashes.items() if h is None]
    present = {n: h for n, h in hashes.items() if h is not None}

    enhanced_version: Optional[str] = None
    enhanced_files: list[str] = []
    for name in ("picoLoader7.bin", "picoLoader9.bin"):
        h = present.get(name)
        if h and (enh_tbl.get(name) or {}).get(h):
            enhanced_files.append(name)
            enhanced_version = (enh_tbl[name][h] or [None])[-1] or enhanced_version
            if enhanced_version and enhanced_version.startswith("enhanced-"):
                enhanced_version = enhanced_version[len("enhanced-"):]
    if "picoLoader9.bin" in present and "picoLoader9.bin" not in enhanced_files:
        try:
            with open(_pico(mount_path, "picoLoader9.bin"), "rb") as f:
                m = _ENHANCED_LOADER_RE.search(f.read(1024 * 1024))
            if m:
                enhanced_files.append("picoLoader9.bin")
                enhanced_version = "v" + m.group(1).decode("ascii", "replace")
        except OSError:
            pass
    if enhanced_files and "picoLoader7.bin" in present and "picoLoader7.bin" not in enhanced_files:
        # Loader Enhanced reconhecido pelo 9; o 7 desconhecido conta como do fork.
        if not (files_tbl.get("picoLoader7.bin") or {}).get(present["picoLoader7.bin"]):
            enhanced_files.append("picoLoader7.bin")

    official = {n: h for n, h in present.items() if n not in enhanced_files}
    matches = []
    for name, h in official.items():
        tags = list((files_tbl.get(name) or {}).get(h) or [])
        matches.append({"file": name, "releases": tags})
    recognised = [m for m in matches if m["releases"]]
    unrecognised = [m["file"] for m in matches if not m["releases"]]

    build_sets = [set((builds_tbl.get(m["file"]) or {}).get(official[m["file"]]) or []) for m in recognised]
    build_sets = [s for s in build_sets if s]
    builds = sorted(_intersect(build_sets)) if build_sets else []

    result: dict[str, Any] = {
        "variant": "enhanced" if enhanced_files else ("official" if present else None),
        "enhanced_version": enhanced_version,
        "enhanced_files": sorted(enhanced_files),
        "missing_files": missing,
        "unrecognised_files": unrecognised,
        "builds": builds,
        "latest_known": latest_known,
        "candidates": [],
        "releases_behind": 0,
        "mismatch": None,
    }
    if not present:
        result["status"] = "no-loader"
        return result
    if not recognised:
        result["status"] = "identified" if enhanced_files and not official else "unrecognised"
        return result
    candidates = _intersect([set(m["releases"]) for m in recognised])
    if not candidates:
        best, agreeing = latest_known, -1
        for tag in order:
            n = sum(1 for m in recognised if tag in m["releases"])
            if n >= agreeing:
                best, agreeing = tag, n
        result["status"] = "mixed"
        result["mismatch"] = {
            "best_fit": best,
            "odd_ones_out": [m["file"] for m in recognised if best not in m["releases"]],
            "agreeing": agreeing,
        }
        return result
    ordered = [t for t in order if t in candidates]
    result["status"] = "identified"
    result["candidates"] = ordered
    if ordered and ordered[-1] in order:
        result["releases_behind"] = len(order) - 1 - order.index(ordered[-1])
    return result


# --------------------------------------------------------------------------- #
# gamedata.json (Pico Launcher Enhanced) — leitura/escrita sem perdas
# --------------------------------------------------------------------------- #

_ENTRY_KNOWN = ("gameCode", "favorite", "completed", "launchCount", "playMinutes", "lastPlayed", "path", "saveSlot")


def _count(v: Any) -> int:
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else 0


def _norm_entry(file_name: str, raw: Any) -> dict[str, Any]:
    src = raw if isinstance(raw, dict) else {}
    entry = {
        "fileName": file_name,
        "gameCode": src.get("gameCode") if isinstance(src.get("gameCode"), str) else "",
        "favorite": src.get("favorite") is True,
        "completed": src.get("completed") is True,
        "launchCount": _count(src.get("launchCount")),
        "playMinutes": _count(src.get("playMinutes")),
        "lastPlayed": src.get("lastPlayed") if isinstance(src.get("lastPlayed"), str) else "",
        "path": src.get("path") if isinstance(src.get("path"), str) else "",
        "saveSlot": _count(src.get("saveSlot")) if 0 < _count(src.get("saveSlot")) <= MAX_SAVE_SLOT else 0,
        # Campos que o Route Pico não conhece seguem intactos na reescrita.
        "_extra": OrderedDict((k, v) for k, v in src.items() if k not in _ENTRY_KNOWN),
    }
    return entry


def parse_gamedata(text: str) -> dict[str, Any]:
    """Parse lossless. Levanta RouteDexError se o JSON for inválido."""
    if text.startswith("﻿"):
        text = text[1:]
    try:
        root = json.loads(text, object_pairs_hook=OrderedDict) if text.strip() else OrderedDict()
    except ValueError as e:
        raise RouteDexError(f"gamedata.json inválido ({e.msg}, linha {e.lineno}); não será alterado.") from e
    if not isinstance(root, dict):
        raise RouteDexError("gamedata.json inválido (raiz não é objeto); não será alterado.")
    games = root.get("games")
    entries = [_norm_entry(k, v) for k, v in games.items()] if isinstance(games, dict) else []
    extra_root = OrderedDict((k, v) for k, v in root.items() if k != "games")
    return {"entries": entries, "_root": extra_root}


def serialize_gamedata(data: dict[str, Any]) -> str:
    """Mesmo formato do launcher: indent 2, CRLF, sem newline final, entradas vazias podadas."""
    games: "OrderedDict[str, Any]" = OrderedDict()
    for e in data.get("entries") or []:
        extra = e.get("_extra") or {}
        empty = (
            not e["favorite"]
            and not e["completed"]
            and e["launchCount"] <= 0
            and e["playMinutes"] <= 0
            and e["saveSlot"] <= 0
            and not extra
        )
        if empty:
            continue
        g: "OrderedDict[str, Any]" = OrderedDict()
        if e["gameCode"]:
            g["gameCode"] = e["gameCode"]
        if e["favorite"]:
            g["favorite"] = True
        if e["completed"]:
            g["completed"] = True
        if e["launchCount"] > 0:
            g["launchCount"] = e["launchCount"]
        if e["playMinutes"] > 0:
            g["playMinutes"] = e["playMinutes"]
        if e["lastPlayed"]:
            g["lastPlayed"] = e["lastPlayed"]
        if e["path"]:
            g["path"] = e["path"]
        if e["saveSlot"] > 0:
            g["saveSlot"] = e["saveSlot"]
        g.update(extra)
        games[e["fileName"]] = g
    root: "OrderedDict[str, Any]" = OrderedDict([("games", games)])
    root.update(data.get("_root") or {})
    return json.dumps(root, indent=2, ensure_ascii=False).replace("\n", "\r\n")


def _same_name(a: str, b: str) -> bool:
    """Comparação ASCII case-insensitive (FAT), como sameFileName do PicoDex."""
    if len(a) != len(b):
        return False
    return all(
        (ord(x) + 32 if 0x41 <= ord(x) <= 0x5A else ord(x)) == (ord(y) + 32 if 0x41 <= ord(y) <= 0x5A else ord(y))
        for x, y in zip(a, b)
    )


def load_gamedata(mount_path: str) -> tuple[dict[str, Any], bool]:
    """(dados, existe). Levanta RouteDexError em JSON inválido."""
    path = _pico(mount_path, GAMEDATA_NAME)
    if not os.path.isfile(path):
        return {"entries": [], "_root": OrderedDict()}, False
    with open(path, "rb") as f:
        raw = f.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        raise RouteDexError("gamedata.json não é UTF-8; não será alterado.") from e
    return parse_gamedata(text), True


def save_gamedata(mount_path: str, data: dict[str, Any]) -> None:
    _atomic_write(_pico(mount_path, GAMEDATA_NAME), serialize_gamedata(data).encode("utf-8"))


def _entry_for(data: dict[str, Any], file_name: str, game_code: Optional[str]) -> dict[str, Any]:
    for e in data["entries"]:
        if _same_name(e["fileName"], file_name):
            break
    else:
        e = _norm_entry(file_name, {})
        data["entries"].append(e)
    if is_usable_game_code(game_code):
        e["gameCode"] = game_code
    return e


def _public_entry(e: dict[str, Any]) -> dict[str, Any]:
    return {k: e[k] for k in ("fileName", "gameCode", "favorite", "completed", "launchCount", "playMinutes", "lastPlayed", "saveSlot")}


def gamedata_overview(mount_path: str) -> dict[str, Any]:
    """Biblioteca do cartão unida ao gamedata.json, pronta para a vista RouteDex."""
    launcher = identify_launcher(mount_path)
    scan = scan_card(mount_path)
    try:
        data, exists = load_gamedata(mount_path)
        parse_error = None
    except RouteDexError as e:
        data, exists, parse_error = {"entries": [], "_root": {}}, True, str(e)

    by_name: dict[str, dict[str, Any]] = {}
    for e in data["entries"]:
        by_name.setdefault(e["fileName"].lower(), e)
    library = []
    for g in scan["games"]:
        e = by_name.get(g["name"].lower())
        item = {"rel": g["rel"], "name": g["name"], "dir": g["dir"], "system": g["system"]}
        item.update(_public_entry(e) if e else {
            "fileName": g["name"], "gameCode": "", "favorite": False, "completed": False,
            "launchCount": 0, "playMinutes": 0, "lastPlayed": "", "saveSlot": 0,
        })
        library.append(item)
    on_card = {g["name"].lower() for g in scan["games"]}
    stale = [_public_entry(e) for e in data["entries"] if e["fileName"].lower() not in on_card]

    totals = {"played": 0, "favorites": 0, "completed": 0, "launches": 0, "minutes": 0}
    for e in data["entries"]:
        totals["favorites"] += e["favorite"]
        totals["completed"] += e["completed"]
        if e["launchCount"] > 0:
            totals["played"] += 1
            totals["launches"] += e["launchCount"]
            totals["minutes"] += e["playMinutes"]
    recent = sorted((e for e in data["entries"] if e["lastPlayed"]), key=lambda e: e["lastPlayed"], reverse=True)[:20]
    top = sorted((e for e in data["entries"] if e["launchCount"] > 0), key=lambda e: (-e["launchCount"], -e["playMinutes"]))[:10]
    root = data.get("_root") or {}
    session = None
    if isinstance(root.get("sessionStart"), str) and root.get("sessionStart"):
        session = {"game": root.get("sessionGame") or "", "start": root["sessionStart"]}
    return {
        "success": True,
        "launcher": launcher,
        "enhanced": launcher.get("variant") == "enhanced",
        "exists": exists,
        "parse_error": parse_error,
        "library": library,
        "stale": stale,
        "totals": totals,
        "recent": [_public_entry(e) for e in recent],
        "top": [_public_entry(e) for e in top],
        "session": session,
    }


def _mutate_gamedata(mount_path: str, rel: str, fn: Callable[[dict[str, Any]], None], log: LogFn) -> dict[str, Any]:
    full = resolve_card_path(mount_path, rel)
    if not os.path.isfile(full):
        raise RouteDexError("Jogo não encontrado no cartão.")
    name = os.path.basename(full)
    system = _system_for(os.path.splitext(name)[1])
    data, _exists = load_gamedata(mount_path)  # levanta se inválido: nunca sobrescrever
    entry = _entry_for(data, name, read_game_code(full, system))
    fn(entry)
    save_gamedata(mount_path, data)
    emit_log(log, f"gamedata.json atualizado: {name}")
    return {"success": True, "entry": _public_entry(entry)}


def toggle_flag(mount_path: str, rel: str, flag: str, log: LogFn = None) -> dict[str, Any]:
    if flag not in ("favorite", "completed"):
        raise RouteDexError("Marcação inválida.")

    def apply(e: dict[str, Any]) -> None:
        e[flag] = not e[flag]

    return _mutate_gamedata(mount_path, rel, apply, log)


def set_stats(mount_path: str, rel: str, launch_count: Any, play_minutes: Any, log: LogFn = None) -> dict[str, Any]:
    def as_count(v: Any) -> int:
        try:
            n = int(float(v))
        except (TypeError, ValueError):
            raise RouteDexError("Valor numérico inválido.") from None
        if n < 0 or n > 10_000_000:
            raise RouteDexError("Valor fora do intervalo.")
        return n

    lc, pm = as_count(launch_count), as_count(play_minutes)

    def apply(e: dict[str, Any]) -> None:
        e["launchCount"], e["playMinutes"] = lc, pm

    return _mutate_gamedata(mount_path, rel, apply, log)


def prune_stale_entries(mount_path: str, file_names: list[str], log: LogFn = None) -> dict[str, Any]:
    """Remove entradas de jogos que já não estão no cartão (cópia do JSON fica no host)."""
    wanted = {n.lower() for n in file_names if isinstance(n, str)}
    if not wanted:
        return {"success": True, "removed": 0}
    data, exists = load_gamedata(mount_path)
    if not exists:
        return {"success": True, "removed": 0}
    on_card = {g["name"].lower() for g in scan_card(mount_path)["games"]}
    before = len(data["entries"])
    data["entries"] = [e for e in data["entries"] if not (e["fileName"].lower() in wanted and e["fileName"].lower() not in on_card)]
    removed = before - len(data["entries"])
    if removed:
        backup = _host_backup_dir("gamedata")
        shutil.copy2(_pico(mount_path, GAMEDATA_NAME), os.path.join(backup, GAMEDATA_NAME))
        save_gamedata(mount_path, data)
        emit_log(log, f"{removed} entrada(s) órfã(s) removida(s) do gamedata.json.")
    return {"success": True, "removed": removed}


# --------------------------------------------------------------------------- #
# Saúde do cartão
# --------------------------------------------------------------------------- #


def _stem(name: str) -> str:
    dot = name.rfind(".")
    return name if dot <= 0 else name[:dot]


def _settings_problem(mount_path: str) -> Optional[str]:
    path = _pico(mount_path, "settings.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError as e:
        return f"settings.json ilegível: {e}"
    if raw.startswith(b"\xef\xbb\xbf"):
        return "settings.json começa com BOM UTF-8; o launcher não o lê."
    try:
        obj = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        return f"settings.json inválido: {e}"
    if not isinstance(obj, dict):
        return "settings.json inválido: a raiz não é um objeto."
    return None


def check_health(mount_path: str) -> dict[str, Any]:
    scan = scan_card(mount_path)
    games, saves = scan["games"], scan["saves"]

    owned: dict[str, set[str]] = {}
    for g in games:
        s = owned.setdefault(g["dir"].lower(), set())
        s.add(_stem(g["name"]).lower())
        s.add(g["name"].lower())

    def owned_in(d: str, base: str) -> bool:
        return base in owned.get(d.lower(), set())

    orphan_saves = []
    by_path: dict[str, dict[str, Any]] = {}
    for sv in saves:
        if not sv["name"].lower().endswith(".sav"):
            continue
        by_path[sv["rel"].lower()] = sv
        base = _stem(sv["name"]).lower()
        if owned_in(sv["dir"], base):
            continue
        parent, _, last = sv["dir"].rpartition("/")
        if (last or sv["dir"]).lower() == SAVES_FOLDER and owned_in(parent if last else "", base):
            continue
        orphan_saves.append(sv["rel"])

    duplicate_saves = []
    for g in games:
        d = g["dir"]
        folder = f"{d}/{SAVES_FOLDER}" if d else SAVES_FOLDER
        for base in (_stem(g["name"]), g["name"]):
            nm = f"{base}.sav".lower()
            beside = by_path.get(f"{d}/{nm}".lower() if d else nm)
            inside = by_path.get(f"{folder}/{nm}".lower())
            if beside and inside:
                duplicate_saves.append({"game": g["rel"], "beside": beside["rel"], "in_folder": inside["rel"]})
                break

    expected_user = {f"{g['name'].lower()}.bmp" for g in games}
    orphan_art = []
    for kind in ("covers", "icons"):
        user_dir = _pico(mount_path, kind, "user")
        try:
            names = os.listdir(user_dir)
        except OSError:
            names = []
        for n in names:
            if _is_junk_file(n) or not n.lower().endswith(".bmp"):
                continue
            if n.lower() not in expected_user:
                orphan_art.append(f"{PICO_DIR}/{kind}/user/{n}")

    try:
        pico_names = {n.lower() for n in os.listdir(_pico(mount_path))}
    except OSError:
        pico_names = set()
    missing_required = [n for n in REQUIRED_LOADER_FILES if n.lower() not in pico_names]
    missing_optional = [n for n in OPTIONAL_LOADER_FILES if n.lower() not in pico_names]

    launcher = identify_launcher(mount_path)
    loader = identify_loader(mount_path)
    problems = []
    if not launcher["present"]:
        problems.append("Falta /_picoboot.nds: o DSPico não arranca o Pico Launcher.")
    if missing_required:
        problems.append("Faltam ficheiros obrigatórios do Pico Loader em /_pico: " + ", ".join(missing_required) + ".")
    if loader["status"] == "mixed":
        problems.append("Os ficheiros do Pico Loader vêm de releases diferentes; reinstale o loader.")
    if loader.get("builds") and "DSPICO" not in loader["builds"]:
        problems.append("O Pico Loader no cartão foi feito para outro flashcard (" + ", ".join(loader["builds"]) + ").")
    sp = _settings_problem(mount_path)
    if sp:
        problems.append(sp)
    gd_error = None
    try:
        load_gamedata(mount_path)
    except RouteDexError as e:
        gd_error = str(e)
        problems.append(gd_error)

    return {
        "success": True,
        "launcher": launcher,
        "loader": loader,
        "missing_required": missing_required,
        "missing_optional": missing_optional,
        "junk": scan["junk"],
        "orphan_saves": orphan_saves,
        "duplicate_saves": duplicate_saves,
        "orphan_art": orphan_art,
        "settings_problem": sp,
        "gamedata_problem": gd_error,
        "problems": problems,
        "games_count": len(games),
        "saves_count": len(saves),
    }


def remove_card_items(mount_path: str, rels: list[str], log: LogFn = None) -> dict[str, Any]:
    """Remove itens que o relatório de saúde apontou (lixo, saves órfãos, arte órfã).

    Só aceita caminhos que o próprio relatório devolveria; cada ficheiro vai
    primeiro para ~/.route_1_kit_cache/routedex_backup/.
    """
    if not isinstance(rels, list) or not rels:
        raise RouteDexError("Nada selecionado.")
    report = check_health(mount_path)
    allowed = {r.lower() for r in report["junk"] + report["orphan_saves"] + report["orphan_art"]}
    targets = []
    for rel in rels:
        if not isinstance(rel, str) or rel.strip().strip("/").lower() not in allowed:
            raise RouteDexError("Item não está na lista do relatório de saúde; atualize a verificação.")
        targets.append(resolve_card_path(mount_path, rel))
    out = _backup_then_remove(mount_path, targets, "saude", log)
    emit_log(log, f"Saúde do cartão: {len(out['removed'])} item(ns) removido(s), cópia no host.")
    return {"success": not out["failed"], **out}


# --------------------------------------------------------------------------- #
# Capturas de ecrã (Enhanced: hold START)
# --------------------------------------------------------------------------- #


def list_screenshots(mount_path: str) -> dict[str, Any]:
    folder = _pico(mount_path, SCREENSHOTS_DIR)
    try:
        names = os.listdir(folder)
    except OSError:
        names = []
    numbered: dict[str, dict[str, Any]] = {}
    loose = []
    for n in names:
        if n.startswith(".") or not n.lower().endswith(".bmp"):
            continue
        m = _SHOT_RE.match(n)
        if not m:
            loose.append({"id": n, "number": None, "top": n, "bottom": None})
            continue
        shot = numbered.setdefault(m.group(1), {"id": m.group(1), "number": int(m.group(1)), "top": None, "bottom": None})
        shot["top" if m.group(2).lower() == "top" else "bottom"] = n
    shots = sorted(numbered.values(), key=lambda s: s["number"]) + sorted(loose, key=lambda s: s["id"].lower())
    return {"success": True, "shots": shots, "folder": f"/{PICO_DIR}/{SCREENSHOTS_DIR}"}


def _find_shot(mount_path: str, shot_id: str) -> dict[str, Any]:
    if not isinstance(shot_id, str) or not shot_id:
        raise RouteDexError("Captura inválida.")
    for s in list_screenshots(mount_path)["shots"]:
        if s["id"] == shot_id:
            return s
    raise RouteDexError("Captura não encontrada.")


def screenshot_png(mount_path: str, shot_id: str) -> bytes:
    """As duas telas empilhadas (topo em cima) num único PNG."""
    from core.pico_bmp import decode_bmp_rgba, rgba_to_png

    shot = _find_shot(mount_path, shot_id)
    layers = []
    for key in ("top", "bottom"):
        if shot[key]:
            with open(_pico(mount_path, SCREENSHOTS_DIR, shot[key]), "rb") as f:
                layers.append(decode_bmp_rgba(f.read()))
    if not layers:
        raise RouteDexError("Captura vazia.")
    width = max(w for w, _h, _p in layers)
    height = sum(h for _w, h, _p in layers)
    canvas = bytearray(width * height * 4)
    y0 = 0
    for w, h, px in layers:
        for y in range(h):
            row = px[y * w * 4 : (y + 1) * w * 4]
            o = ((y0 + y) * width) * 4
            canvas[o : o + len(row)] = row
        y0 += h
    return rgba_to_png(width, height, bytes(canvas))


def screenshot_data_url(mount_path: str, shot_id: str) -> str:
    return "data:image/png;base64," + base64.b64encode(screenshot_png(mount_path, shot_id)).decode("ascii")


def export_screenshot(mount_path: str, shot_id: str, dest_path: str) -> dict[str, Any]:
    png = screenshot_png(mount_path, shot_id)
    if not dest_path.lower().endswith(".png"):
        dest_path += ".png"
    tmp = dest_path + ".partial"
    try:
        with open(tmp, "wb") as f:
            f.write(png)
        os.replace(tmp, dest_path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return {"success": True, "path": redact_path(dest_path)}


def delete_screenshot(mount_path: str, shot_id: str, log: LogFn = None) -> dict[str, Any]:
    shot = _find_shot(mount_path, shot_id)
    paths = [_pico(mount_path, SCREENSHOTS_DIR, shot[k]) for k in ("top", "bottom") if shot[k]]
    out = _backup_then_remove(mount_path, paths, "capturas", log)
    return {"success": not out["failed"], **out}


# --------------------------------------------------------------------------- #
# Banners, ícones e capas de pasta
# --------------------------------------------------------------------------- #


def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def _tiled_xy(i: int) -> tuple[int, int]:
    tile, off = i >> 6, i & 63
    return (tile % 4) * 8 + (off % 8), (tile >> 2) * 8 + (off >> 3)


def rom_banner_icon(path: str) -> tuple[bytes, bytes]:
    """(bitmap 0x200, palette 0x20) do banner interno de uma ROM NDS."""
    with open(path, "rb") as f:
        head = f.read(0x6C)
        if len(head) < 0x6C:
            raise RouteDexError("ROM sem cabeçalho NDS.")
        off = struct.unpack_from("<I", head, 0x68)[0]
        if off == 0:
            raise RouteDexError("A ROM não tem banner.")
        f.seek(off)
        blk = f.read(0x240)
    if len(blk) < 0x240:
        raise RouteDexError("Banner da ROM incompleto.")
    return blk[0x20:0x220], blk[0x220:0x240]


def encode_icon_rgba(rgba32: bytes) -> tuple[bytes, bytes]:
    """RGBA 32x32 com ≤15 cores opacas → (bitmap tiled 4bpp, paleta BGR555)."""
    colors: list[tuple[int, int, int]] = []
    index_of: dict[tuple[int, int, int], int] = {}
    keys = []
    for p in range(1024):
        r, g, b, a = rgba32[p * 4 : p * 4 + 4]
        if a < 128:
            keys.append(None)
            continue
        c = (r, g, b)
        if c not in index_of:
            if len(colors) >= 15:
                # Já quantizado a 15 cores; cor nova vai para a mais próxima.
                best = min(range(len(colors)), key=lambda i: sum((x - y) ** 2 for x, y in zip(colors[i], c)))
                index_of[c] = best + 1
            else:
                colors.append(c)
                index_of[c] = len(colors)
        keys.append(c)
    bitmap = bytearray(ICON_BITMAP_SIZE)
    for i in range(1024):
        x, y = _tiled_xy(i)
        c = keys[y * 32 + x]
        idx = index_of[c] if c is not None else 0
        bitmap[i >> 1] |= idx if i % 2 == 0 else idx << 4
    palette = bytearray(ICON_PALETTE_SIZE)
    struct.pack_into("<H", palette, 0, _TRANSPARENT_PLACEHOLDER)
    for i, (r, g, b) in enumerate(colors):
        struct.pack_into("<H", palette, (i + 1) * 2, (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10))
    return bytes(bitmap), bytes(palette)


def decode_icon_rgba(bitmap: bytes, palette: bytes) -> bytes:
    out = bytearray(1024 * 4)
    for i in range(1024):
        byte = bitmap[i >> 1]
        idx = byte & 0xF if i % 2 == 0 else byte >> 4
        if idx == 0:
            continue
        x, y = _tiled_xy(i)
        c = struct.unpack_from("<H", palette, idx * 2)[0]
        o = (y * 32 + x) * 4
        out[o : o + 4] = bytes((((c & 31) * 255) // 31, (((c >> 5) & 31) * 255) // 31, (((c >> 10) & 31) * 255) // 31, 255))
    return bytes(out)


def build_banner(bitmap: bytes, palette: bytes, title: str) -> bytes:
    """banner.bnr v1 (0x840 bytes): ícone + título nas 6 línguas, CRC-16 em 0x02."""
    if len(bitmap) != ICON_BITMAP_SIZE or len(palette) != ICON_PALETTE_SIZE:
        raise RouteDexError("Ícone inválido para banner.")
    title = (title or "").strip()
    if not title:
        raise RouteDexError("Indique um título para a pasta.")
    units = title.encode("utf-16-le")[: 127 * 2]
    banner = bytearray(BANNER_SIZE)
    struct.pack_into("<H", banner, 0, 0x0001)
    banner[0x20:0x220] = bitmap
    banner[0x220:0x240] = palette
    for lang in range(6):
        base = 0x240 + lang * 0x100
        banner[base : base + len(units)] = units
    struct.pack_into("<H", banner, 0x02, crc16_modbus(bytes(banner[0x20:])))
    return bytes(banner)


def parse_banner(data: bytes) -> dict[str, Any]:
    if len(data) < BANNER_SIZE:
        raise RouteDexError("banner.bnr curto demais.")
    title_raw = data[0x340:0x440]  # língua 1 (inglês), como o launcher
    end = 0
    while end + 1 < len(title_raw) and (title_raw[end] or title_raw[end + 1]):
        end += 2
    crc_ok = struct.unpack_from("<H", data, 2)[0] == crc16_modbus(data[0x20:BANNER_SIZE])
    return {"title": title_raw[:end].decode("utf-16-le", "replace"), "crc_ok": crc_ok,
            "bitmap": data[0x20:0x220], "palette": data[0x220:0x240]}


def folder_art_status(mount_path: str, rel_folder: str) -> dict[str, Any]:
    from core.pico_bmp import bmp_to_preview_png, rgba_to_png

    folder = resolve_card_path(mount_path, rel_folder)
    if not os.path.isdir(folder):
        raise RouteDexError("Pasta não encontrada.")
    out: dict[str, Any] = {"success": True, "folder": _rel(mount_path, folder), "banner": None, "icon": False, "cover": None}
    bnr = os.path.join(folder, "banner.bnr")
    if os.path.isfile(bnr):
        with open(bnr, "rb") as f:
            info = parse_banner(f.read())
        png = rgba_to_png(32, 32, decode_icon_rgba(info["bitmap"], info["palette"]))
        out["banner"] = {"title": info["title"], "crc_ok": info["crc_ok"],
                         "icon": "data:image/png;base64," + base64.b64encode(png).decode("ascii")}
    out["icon"] = os.path.isfile(os.path.join(folder, "icon.bmp"))
    cover = os.path.join(folder, "cover.bmp")
    if os.path.isfile(cover):
        with open(cover, "rb") as f:
            out["cover"] = "data:image/png;base64," + base64.b64encode(bmp_to_preview_png(f.read())).decode("ascii")
    roms = []
    try:
        for n in sorted(os.listdir(folder), key=str.lower):
            if os.path.splitext(n)[1].lower() in GAME_EXTS and not n.startswith("."):
                roms.append(n)
    except OSError:
        pass
    out["roms"] = roms
    return out


def write_folder_banner(
    mount_path: str,
    rel_folder: str,
    title: str,
    *,
    rom_name: str = "",
    image_path: str = "",
    log: LogFn = None,
) -> dict[str, Any]:
    """Grava <pasta>/banner.bnr com ícone de uma ROM da pasta ou de uma imagem."""
    from core.pico_bmp import _quantize_icon_rgba, decode_image_rgba

    folder = resolve_card_path(mount_path, rel_folder)
    if not os.path.isdir(folder) or folder == os.path.realpath(mount_path):
        raise RouteDexError("Escolha uma pasta do cartão (não a raiz).")
    if rom_name:
        rom = os.path.join(folder, os.path.basename(rom_name))
        if not os.path.isfile(rom):
            raise RouteDexError("ROM não encontrada na pasta.")
        bitmap, palette = rom_banner_icon(rom)
    elif image_path:
        with open(image_path, "rb") as f:
            w, h, rgba = decode_image_rgba(f.read())
        bitmap, palette = encode_icon_rgba(_quantize_icon_rgba(w, h, rgba, 32))
    else:
        raise RouteDexError("Escolha uma ROM da pasta ou uma imagem para o ícone.")
    data = build_banner(bitmap, palette, title)
    _atomic_write(os.path.join(folder, "banner.bnr"), data)
    emit_log(log, f"banner.bnr gravado em /{_rel(mount_path, folder)}")
    return {"success": True}


def write_folder_cover(mount_path: str, rel_folder: str, image_path: str, log: LogFn = None) -> dict[str, Any]:
    from core.pico_bmp import image_bytes_to_pico_bmp

    folder = resolve_card_path(mount_path, rel_folder)
    if not os.path.isdir(folder) or folder == os.path.realpath(mount_path):
        raise RouteDexError("Escolha uma pasta do cartão (não a raiz).")
    with open(image_path, "rb") as f:
        bmp = image_bytes_to_pico_bmp(f.read(), "cover")
    _atomic_write(os.path.join(folder, "cover.bmp"), bmp)
    emit_log(log, f"cover.bmp gravado em /{_rel(mount_path, folder)}")
    return {"success": True}


def remove_folder_art(mount_path: str, rel_folder: str, kind: str, log: LogFn = None) -> dict[str, Any]:
    names = {"banner": "banner.bnr", "icon": "icon.bmp", "cover": "cover.bmp"}
    if kind not in names:
        raise RouteDexError("Tipo inválido.")
    folder = resolve_card_path(mount_path, rel_folder)
    out = _backup_then_remove(mount_path, [os.path.join(folder, names[kind])], "pasta", log)
    return {"success": not out["failed"], **out}


# --------------------------------------------------------------------------- #
# Fundos noturnos (Enhanced: *_night.bin usados das 20:00 às 6:59)
# --------------------------------------------------------------------------- #

_BUILTIN_THEMES = frozenset({"raspberry", "material"})


def _night_tint(data: bytes) -> bytes:
    """Mesmo cálculo de tools/make_night_bg.py do Enhanced (BGR555, bit 15 preservado)."""
    out = bytearray(data)
    for i in range(0, _BG_BYTES, 2):
        v = out[i] | (out[i + 1] << 8)
        r, g, b = v & 31, (v >> 5) & 31, (v >> 10) & 31
        nv = (v & 0x8000) | int(r * 0.40) | (int(g * 0.48) << 5) | (min(31, int(b * 0.62) + 3) << 10)
        out[i], out[i + 1] = nv & 0xFF, nv >> 8
    return bytes(out)


def list_night_themes(mount_path: str) -> dict[str, Any]:
    root = _pico(mount_path, "themes")
    themes = []
    try:
        names = sorted(os.listdir(root), key=str.lower)
    except OSError:
        names = []
    for n in names:
        d = os.path.join(root, n)
        if n.startswith(".") or not os.path.isdir(d):
            continue
        bgs = {k: os.path.isfile(os.path.join(d, f"{k}.bin")) for k in ("topbg", "bottombg")}
        if not any(bgs.values()):
            continue
        night = {k: os.path.isfile(os.path.join(d, f"{k}_night.bin")) for k in ("topbg", "bottombg")}
        themes.append({"folder": n, "builtin": n.lower() in _BUILTIN_THEMES, "has": bgs, "night": night})
    return {"success": True, "themes": themes}


def _theme_dir(mount_path: str, folder: str) -> str:
    if not isinstance(folder, str) or not folder or "/" in folder or "\\" in folder or folder in (".", ".."):
        raise RouteDexError("Tema inválido.")
    d = _pico(mount_path, "themes", folder)
    if not os.path.isdir(d):
        raise RouteDexError("Tema não encontrado.")
    return d


def generate_night_backgrounds(mount_path: str, folder: str, log: LogFn = None) -> dict[str, Any]:
    d = _theme_dir(mount_path, folder)
    made = []
    for k in ("topbg", "bottombg"):
        src = os.path.join(d, f"{k}.bin")
        if not os.path.isfile(src):
            continue
        with open(src, "rb") as f:
            data = f.read()
        if len(data) != _BG_BYTES:
            raise RouteDexError(f"{k}.bin com tamanho inesperado ({len(data)} bytes; esperado {_BG_BYTES}).")
        _atomic_write(os.path.join(d, f"{k}_night.bin"), _night_tint(data))
        made.append(f"{k}_night.bin")
    if not made:
        raise RouteDexError("O tema não tem topbg.bin nem bottombg.bin.")
    emit_log(log, f"Fundos noturnos gerados no tema {folder}: {', '.join(made)}")
    return {"success": True, "written": made}


def remove_night_backgrounds(mount_path: str, folder: str, log: LogFn = None) -> dict[str, Any]:
    d = _theme_dir(mount_path, folder)
    paths = [os.path.join(d, f"{k}_night.bin") for k in ("topbg", "bottombg")]
    out = _backup_then_remove(mount_path, paths, "noturno", log)
    return {"success": not out["failed"], **out}


# --------------------------------------------------------------------------- #
# Cheats (usrcheat.dat em /_pico)
# --------------------------------------------------------------------------- #


def parse_usrcheat_header(path: str) -> dict[str, Any]:
    """Valida o cabeçalho e conta os jogos da base (lista de entradas a partir de 0x100)."""
    size = os.path.getsize(path)
    if size > _USRCHEAT_MAX_BYTES:
        raise RouteDexError("usrcheat.dat grande demais.")
    with open(path, "rb") as f:
        head = f.read(0x100)
        if len(head) < 0x100 or head[:16] != _USRCHEAT_MAGIC:
            raise RouteDexError("Não é um usrcheat.dat válido (cabeçalho 'R4 CheatCode' v1.0 ausente).")
        name = head[0x10:0x4C].split(b"\x00", 1)[0].decode("utf-8", "replace").strip()
        codes: set[str] = set()
        entries = 0
        first_data = size
        while f.tell() + 16 <= min(size, first_data):
            rec = f.read(16)
            code_raw, _crc, data_off, _zero = struct.unpack("<4sIII", rec)
            if data_off == 0 or code_raw == b"\x00\x00\x00\x00":
                break
            first_data = min(first_data, data_off)
            entries += 1
            try:
                codes.add(code_raw.decode("ascii"))
            except UnicodeDecodeError:
                pass
    return {"name": name, "games": entries, "codes": codes, "size": size}


def cheats_status(mount_path: str) -> dict[str, Any]:
    path = _pico(mount_path, USRCHEAT_NAME)
    if not os.path.isfile(path):
        return {"success": True, "present": False}
    try:
        info = parse_usrcheat_header(path)
    except (OSError, RouteDexError) as e:
        return {"success": True, "present": True, "valid": False, "error": str(e)}
    card_codes = {}
    for g in scan_card(mount_path)["games"]:
        if g["system"] == "nds":
            code = read_game_code(resolve_card_path(mount_path, g["rel"]), "nds")
            if code:
                card_codes[code] = g["name"]
    with_cheats = sorted(n for c, n in card_codes.items() if c in info["codes"])
    return {
        "success": True,
        "present": True,
        "valid": True,
        "name": info["name"],
        "games": info["games"],
        "size": info["size"],
        "card_games_with_cheats": len(with_cheats),
        "card_nds_games": len(card_codes),
    }


def import_usrcheat(mount_path: str, src_path: str, log: LogFn = None) -> dict[str, Any]:
    info = parse_usrcheat_header(src_path)
    dst = _pico(mount_path, USRCHEAT_NAME)
    if os.path.isfile(dst):
        backup = _host_backup_dir("cheats")
        shutil.copy2(dst, os.path.join(backup, USRCHEAT_NAME))
    with open(src_path, "rb") as f:
        _atomic_write(dst, f.read())
    emit_log(log, f"usrcheat.dat instalado ({info['games']} jogos na base).")
    return {"success": True, "name": info["name"], "games": info["games"]}
