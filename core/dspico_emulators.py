"""Emuladores para Pico-Launcher (DSPico): catálogo, pastas ROMs e fileAssociations.

Segue o guia Sanrax «Emulators on Pico-Launcher»:
https://sanrax.github.io/flashcart-guides/tutorials/emulators-pico/

Downloads via core.cache (SHA-256 pinados). BIOS proprietária nunca é descarregada.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import zipfile
from typing import Any, Optional

from core.cache import (
    CACHE_DIR,
    DSPICO_EMU_CACHE_KEYS,
    PINNED_SHA256,
    URLS,
    ensure_cache_dir,
    ensure_cached,
)
from core.logging_util import emit_log
from core.sdio import UndoStack, copy_fast, sync_volume
from core.twilight import _is_safe_archive_member

# --- Catálogo ---------------------------------------------------------------

_ASSOC = lambda path: {"appPath": path}  # noqa: E731


def _entry(
    *,
    id: str,
    label: str,
    category: str,
    cache_key: str,
    nds_dest: str,
    install_mode: str = "argv",
    archive: bool = False,
    nds_member: Optional[str] = None,
    associations: Optional[dict] = None,
    rom_dirs: Optional[list] = None,
    extra_dirs: Optional[list] = None,
    copy_trees: Optional[list] = None,
    extra_cache_files: Optional[list] = None,
    bios_notes: str = "",
    conflict_group: Optional[str] = None,
    association_priority: int = 0,
    patch_snemul_cfg: bool = False,
    popular: bool = False,
) -> dict[str, Any]:
    return {
        "id": id,
        "label": label,
        "category": category,
        "cache_key": cache_key,
        "nds_dest": nds_dest,
        "install_mode": install_mode,
        "archive": archive,
        "nds_member": nds_member,
        "associations": associations or {},
        "rom_dirs": rom_dirs or [],
        "extra_dirs": extra_dirs or [],
        "copy_trees": copy_trees or [],
        "extra_cache_files": extra_cache_files or [],
        "bios_notes": bios_notes,
        "conflict_group": conflict_group,
        "association_priority": association_priority,
        "patch_snemul_cfg": patch_snemul_cfg,
        "popular": popular,
    }


EMULATOR_CATALOG: list[dict[str, Any]] = [
    # --- Nintendo ---
    _entry(
        id="gbarunner3",
        label="GBARunner3",
        category="nintendo",
        cache_key="emu_gbarunner3",
        archive=True,
        nds_member="GBARunner3.nds",
        nds_dest="_pico/emulators/GBARunner3.nds",
        associations={"gba": _ASSOC("/_pico/emulators/GBARunner3.nds")},
        rom_dirs=["ROMs/GBA"],
        extra_dirs=["_gba"],
        copy_trees=[("_gba", "_gba")],
        bios_notes=(
            "GBARunner3 exige bios.bin (dump da BIOS GBA) em /_gba/. "
            "O app não descarrega BIOS proprietária."
        ),
        conflict_group="gba",
        association_priority=20,
        popular=True,
    ),
    _entry(
        id="gbarunner2",
        label="GBARunner2 (DSL Enhanced)",
        category="nintendo",
        cache_key="emu_gbarunner2",
        archive=False,
        nds_dest="_pico/emulators/GBARunner2_arm9dldi_ds.nds",
        associations={
            "gba": _ASSOC("/_pico/emulators/GBARunner2_arm9dldi_ds.nds")
        },
        rom_dirs=["ROMs/GBA"],
        extra_dirs=["_gba"],
        bios_notes=(
            "Opcional: bios.bin em /_gba/ (sem BIOS usa open-source, menos compatível)."
        ),
        conflict_group="gba",
        association_priority=10,
        popular=True,
    ),
    _entry(
        id="gameyob",
        label="GameYob (GB/GBC)",
        category="nintendo",
        cache_key="emu_gameyob",
        archive=True,
        nds_member="gameyob.nds",
        nds_dest="_pico/emulators/gameyob.nds",
        associations={
            "gb": _ASSOC("/_pico/emulators/gameyob.nds"),
            "gbc": _ASSOC("/_pico/emulators/gameyob.nds"),
        },
        rom_dirs=["ROMs/GB"],
        bios_notes=(
            "Opcional: gbc_bios.bin em /ROMs/GB (sem BIOS, só grayscale)."
        ),
        popular=True,
    ),
    _entry(
        id="nesds",
        label="nesDS",
        category="nintendo",
        cache_key="emu_nesds",
        archive=False,
        nds_dest="_pico/emulators/nesDS.nds",
        associations={"nes": _ASSOC("/_pico/emulators/nesDS.nds")},
        rom_dirs=["ROMs/NES"],
        popular=True,
    ),
    # --- Atari ---
    _entry(
        id="stellads",
        label="StellaDS (Atari 2600)",
        category="atari",
        cache_key="emu_stellads",
        archive=False,
        nds_dest="_pico/emulators/StellaDS.nds",
        associations={"a26": _ASSOC("/_pico/emulators/StellaDS.nds")},
        rom_dirs=["ROMs/2600"],
    ),
    _entry(
        id="a5200ds",
        label="A5200DS (Atari 5200)",
        category="atari",
        cache_key="emu_a5200ds",
        archive=False,
        nds_dest="_pico/emulators/A5200DS.nds",
        associations={"a52": _ASSOC("/_pico/emulators/A5200DS.nds")},
        rom_dirs=["ROMs/5200", "ROMs/BIOS"],
        bios_notes="Opcional: 5200.rom em /ROMs/BIOS.",
    ),
    _entry(
        id="a7800ds",
        label="A7800DS (Atari 7800)",
        category="atari",
        cache_key="emu_a7800ds",
        archive=False,
        nds_dest="_pico/emulators/A7800DS.nds",
        associations={"a78": _ASSOC("/_pico/emulators/A7800DS.nds")},
        rom_dirs=["ROMs/7800", "ROMs/BIOS"],
        bios_notes="Opcional: highscore.rom em /ROMs/BIOS (high scores).",
    ),
    _entry(
        id="a8ds",
        label="A8DS (Atari 800/400)",
        category="atari",
        cache_key="emu_a8ds",
        archive=False,
        nds_dest="_pico/emulators/A8DS.nds",
        associations={
            "car": _ASSOC("/_pico/emulators/A8DS.nds"),
            "xex": _ASSOC("/_pico/emulators/A8DS.nds"),
            "atr": _ASSOC("/_pico/emulators/A8DS.nds"),
            "atx": _ASSOC("/_pico/emulators/A8DS.nds"),
        },
        rom_dirs=["ROMs/800", "ROMs/BIOS"],
        bios_notes=(
            "Opcional: atarixl.rom, atariosb.rom, ataribas.rom, a5200.rom em /ROMs/BIOS."
        ),
    ),
    # --- Sega ---
    _entry(
        id="picodrive_twl",
        label="PicoDriveTWL (Genesis/MD)",
        category="sega",
        cache_key="emu_picodrive_twl",
        archive=False,
        nds_dest="_pico/emulators/PicoDriveTWL.nds",
        associations={
            "gen": _ASSOC("/_pico/emulators/PicoDriveTWL.nds"),
            "smd": _ASSOC("/_pico/emulators/PicoDriveTWL.nds"),
            "md": _ASSOC("/_pico/emulators/PicoDriveTWL.nds"),
        },
        rom_dirs=["ROMs/Genesis"],
        popular=True,
    ),
    _entry(
        id="s8ds",
        label="S8DS (SMS / Game Gear)",
        category="sega",
        cache_key="emu_s8ds",
        archive=True,
        nds_member="S8DS.nds",
        nds_dest="_pico/emulators/S8DS.nds",
        associations={
            "sms": _ASSOC("/_pico/emulators/S8DS.nds"),
            "gg": _ASSOC("/_pico/emulators/S8DS.nds"),
            "sg": _ASSOC("/_pico/emulators/S8DS.nds"),
            "sc": _ASSOC("/_pico/emulators/S8DS.nds"),
        },
        rom_dirs=["ROMs/SMS", "ROMs/GG", "ROMs/BIOS"],
        extra_dirs=["data/S8DS"],
        popular=True,
    ),
    # --- Misc ---
    _entry(
        id="ngpds",
        label="NGPDS (NeoGeo Pocket)",
        category="misc",
        cache_key="emu_ngpds",
        archive=True,
        nds_member="NGPDS.nds",
        nds_dest="_pico/emulators/NGPDS.nds",
        associations={
            "ngp": _ASSOC("/_pico/emulators/NGPDS.nds"),
            "ngc": _ASSOC("/_pico/emulators/NGPDS.nds"),
        },
        rom_dirs=["ROMs/NGPocket", "ROMs/BIOS"],
        extra_dirs=["data/NGPDS"],
        extra_cache_files=[
            ("emu_ngpds_settings", "data/NGPDS/settings.cfg"),
        ],
        bios_notes=(
            "BIOS NGP: ngp-color-bios.ngp e ngp-bnw-bios.ngp em /ROMs/BIOS."
        ),
    ),
    _entry(
        id="nitrografx",
        label="NitroGrafx (PC-Engine/TG16)",
        category="misc",
        cache_key="emu_nitrografx",
        archive=True,
        nds_member="NitroGrafx.nds",
        nds_dest="_pico/emulators/NitroGrafx.nds",
        associations={
            "pce": _ASSOC("/_pico/emulators/NitroGrafx.nds"),
            "iso": _ASSOC("/_pico/emulators/NitroGrafx.nds"),
            "cue": _ASSOC("/_pico/emulators/NitroGrafx.nds"),
        },
        rom_dirs=["ROMs/TurboGrafx"],
        extra_dirs=["data/NitroGrafx"],
        bios_notes="Opcional: BIOS CD-ROM em /ROMs/TurboGrafx para jogos CD.",
    ),
    _entry(
        id="colecods",
        label="ColecoDS",
        category="misc",
        cache_key="emu_colecods",
        archive=False,
        nds_dest="_pico/emulators/ColecoDS.nds",
        associations={
            "col": _ASSOC("/_pico/emulators/ColecoDS.nds"),
            "cas": _ASSOC("/_pico/emulators/ColecoDS.nds"),
            "com": _ASSOC("/_pico/emulators/ColecoDS.nds"),
            "cv": _ASSOC("/_pico/emulators/ColecoDS.nds"),
            "ddp": _ASSOC("/_pico/emulators/ColecoDS.nds"),
            "dsk": _ASSOC("/_pico/emulators/ColecoDS.nds"),
            "mtx": _ASSOC("/_pico/emulators/ColecoDS.nds"),
            "msx": _ASSOC("/_pico/emulators/ColecoDS.nds"),
            "m5": _ASSOC("/_pico/emulators/ColecoDS.nds"),
            "pen": _ASSOC("/_pico/emulators/ColecoDS.nds"),
            "pv": _ASSOC("/_pico/emulators/ColecoDS.nds"),
            "pv1": _ASSOC("/_pico/emulators/ColecoDS.nds"),
        },
        rom_dirs=["ROMs/Coleco", "ROMs/BIOS"],
        bios_notes="Recomendado: coleco.rom em /ROMs/BIOS.",
    ),
    _entry(
        id="nintv_ds",
        label="NINTV-DS (Intellivision)",
        category="misc",
        cache_key="emu_nintv_ds",
        archive=False,
        nds_dest="_pico/emulators/NINTV-DS.nds",
        associations={"int": _ASSOC("/_pico/emulators/NINTV-DS.nds")},
        rom_dirs=["ROMs/INTV", "ROMs/BIOS"],
        bios_notes=(
            "Obrigatório: grom.bin e exec.bin em /ROMs/BIOS "
            "(CRC32 683A4158 / CBCE86F7)."
        ),
    ),
    # --- Manual (sem argv) ---
    _entry(
        id="snemulds_06a",
        label="SNEmulDS 0.6a",
        category="manual",
        cache_key="emu_snemulds_06a",
        install_mode="manual",
        archive=True,
        nds_member="SNEmulDS.nds",
        nds_dest="Emulators/SNEmulDS.nds",
        rom_dirs=["ROMs/SNES"],
        patch_snemul_cfg=True,
        bios_notes="Lançamento manual: abrir SNEmulDS.nds em /Emulators/.",
    ),
    _entry(
        id="snemulds_06d",
        label="SNEmulDS 0.6d (Coto)",
        category="manual",
        cache_key="emu_snemulds_06d",
        install_mode="manual",
        archive=True,
        nds_member="SNEmulDS.nds",
        nds_dest="Emulators/SNEmulDS.nds",
        rom_dirs=["ROMs/SNES"],
        bios_notes="Lançamento manual: abrir SNEmulDS.nds em /Emulators/.",
    ),
    _entry(
        id="jenesisds",
        label="jEnesisDS (Genesis — manual)",
        category="manual",
        cache_key="emu_jenesisds",
        install_mode="manual",
        archive=True,
        nds_member="jEnesisDS.nds",
        nds_dest="Emulators/jEnesisDS.nds",
        rom_dirs=["ROMs/Genesis"],
        bios_notes="Lançamento manual; ROMs .gen/.bin/.smd (não .md).",
    ),
    _entry(
        id="neods",
        label="NeoDS (NeoGeo — manual)",
        category="manual",
        cache_key="emu_neods",
        install_mode="manual",
        archive=False,
        nds_dest="Emulators/NeoDS.nds",
        rom_dirs=["ROMs/NeoGeo"],
        extra_dirs=["data/NeoDS"],
        extra_cache_files=[("emu_neods_ini", "data/NeoDS/_NeoDS.ini")],
        bios_notes=(
            "Lançamento manual. ROMs devem estar em formato .neo "
            "(conversão necessária)."
        ),
    ),
]

_CATALOG_BY_ID = {e["id"]: e for e in EMULATOR_CATALOG}
_SAFE_REL_RE = re.compile(r"^[A-Za-z0-9._\-]+(?:/[A-Za-z0-9._\-]+)*$")


def _pin_ready(cache_key: str) -> bool:
    if cache_key not in DSPICO_EMU_CACHE_KEYS:
        return False
    if not PINNED_SHA256.get(cache_key):
        return False
    if cache_key not in URLS:
        return False
    return True


def catalog_by_id(emu_id: str) -> Optional[dict[str, Any]]:
    return _CATALOG_BY_ID.get(emu_id)


def probe_emulator_installed(mount_path: str, entry: dict[str, Any]) -> bool:
    """True se o NDS de destino do emulador existe no cartão."""
    if not mount_path or not isinstance(mount_path, str):
        return False
    rel = (entry or {}).get("nds_dest") or ""
    if not _safe_rel(rel):
        return False
    full = os.path.join(mount_path, *rel.replace("\\", "/").split("/"))
    try:
        mount_r = os.path.realpath(mount_path)
        full_r = os.path.realpath(full)
        if os.path.commonpath([mount_r, full_r]) != mount_r:
            return False
    except (ValueError, OSError):
        return False
    return os.path.isfile(full_r)


def list_emulators(mount_path: Optional[str] = None) -> dict[str, Any]:
    """Catálogo para a UI; com mount_path, marca installed por NDS no cartão."""
    probe = bool(mount_path and isinstance(mount_path, str) and mount_path.strip())
    items = []
    for e in EMULATOR_CATALOG:
        ready = _pin_ready(e["cache_key"])
        for ck, _dest in e.get("extra_cache_files") or []:
            if not _pin_ready(ck):
                ready = False
                break
        installed = probe_emulator_installed(mount_path or "", e) if probe else False
        items.append(
            {
                "id": e["id"],
                "label": e["label"],
                "category": e["category"],
                "install_mode": e["install_mode"],
                "available": ready,
                "installed": installed,
                "popular": bool(e.get("popular")),
                "bios_notes": e.get("bios_notes") or "",
                "rom_dirs": list(e.get("rom_dirs") or []),
                "conflict_group": e.get("conflict_group"),
                "associations": sorted((e.get("associations") or {}).keys()),
            }
        )
    return {
        "success": True,
        "emulators": items,
        "categories": [
            {"id": "nintendo", "label": "Nintendo"},
            {"id": "atari", "label": "Atari"},
            {"id": "sega", "label": "Sega"},
            {"id": "misc", "label": "Outros"},
            {"id": "manual", "label": "Só lançamento manual"},
        ],
        "guide_url": (
            "https://sanrax.github.io/flashcart-guides/tutorials/emulators-pico/"
        ),
    }


def _safe_rel(rel: str) -> bool:
    if not rel or not isinstance(rel, str):
        return False
    if ".." in rel or rel.startswith("/") or "\\" in rel or "\x00" in rel:
        return False
    return bool(_SAFE_REL_RE.match(rel.replace("\\", "/")))


def _find_member(root: str, basename: str) -> Optional[str]:
    want = basename.lower()
    for walk_root, _dirs, files in os.walk(root):
        for name in files:
            if name.lower() == want and not name.startswith("."):
                return os.path.join(walk_root, name)
    return None


def _extract_zip_to_tmp(archive_path: str, log_callback=None) -> str:
    """Extrai zip para pasta temporária; devolve path (caller limpa com rmtree)."""
    try:
        ensure_cache_dir()
        tmp = tempfile.mkdtemp(dir=CACHE_DIR, prefix="emu_zip_")
    except OSError:
        tmp = tempfile.mkdtemp(prefix="emu_zip_")
    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            for info in zf.infolist():
                name = info.filename
                if name.startswith("__MACOSX/") or "/__MACOSX/" in name:
                    continue
                if not _is_safe_archive_member(name, tmp):
                    raise RuntimeError(f"Zip rejeitado (caminho inseguro): {name!r}")
            for info in zf.infolist():
                name = info.filename
                if name.startswith("__MACOSX/") or "/__MACOSX/" in name:
                    continue
                zf.extract(info, tmp)
        return tmp
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


def _copy_with_undo(
    src: str, dest: str, undo: UndoStack, log_callback=None
) -> None:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    bak = None
    if os.path.isfile(dest):
        bak = dest + f".bak_{os.getpid()}"
        shutil.copy2(dest, bak)
        undo.push_restore_file(bak, dest)
    copy_fast(src, dest, log_callback=log_callback)
    if bak is None:
        undo.push_remove(dest)
    elif bak and os.path.isfile(bak):
        try:
            os.remove(bak)
        except OSError:
            pass


def _ensure_settings_stub(mount_path: str, log) -> str:
    pico = os.path.join(mount_path, "_pico")
    os.makedirs(pico, exist_ok=True)
    path = os.path.join(pico, "settings.json")
    if os.path.isfile(path):
        return path
    data = {"fileAssociations": {}}
    partial = path + ".partial"
    with open(partial, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(partial, path)
    log("Criado stub /_pico/settings.json com fileAssociations.")
    return path


def _read_settings(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_settings(path: str, data: dict, undo: UndoStack) -> None:
    bak = None
    if os.path.isfile(path):
        bak = path + f".bak_{os.getpid()}"
        shutil.copy2(path, bak)
        undo.push_restore_file(bak, path)
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


def _resolve_gba_association_winners(
    selected: list[dict[str, Any]],
) -> set[str]:
    """IDs que devem escrever a associação .gba (maior priority no grupo)."""
    by_group: dict[str, list[dict]] = {}
    for e in selected:
        g = e.get("conflict_group")
        if not g:
            continue
        by_group.setdefault(g, []).append(e)
    winners: set[str] = set()
    for _g, group in by_group.items():
        best = max(group, key=lambda x: int(x.get("association_priority") or 0))
        winners.add(best["id"])
    return winners


def _patch_snemul_cfg_text(text: str) -> str:
    lines = text.splitlines()
    out = []
    found = False
    for line in lines:
        if re.match(r"(?i)^\s*ROMPath\s*=", line):
            out.append("ROMPath = /ROMs/SNES")
            found = True
        else:
            out.append(line)
    if not found:
        out.append("ROMPath = /ROMs/SNES")
    return "\n".join(out) + ("\n" if text.endswith("\n") or not text else "")


def install_dspico_emulators(
    mount_path: str,
    emulator_ids,
    log_callback=None,
) -> tuple[bool, str, dict]:
    """Instala emuladores seleccionados no microSD DSPico."""
    log = lambda msg: emit_log(log_callback, msg)

    if not isinstance(mount_path, str) or not mount_path.strip():
        return False, "Caminho do cartão inválido.", {}
    if not os.path.isdir(mount_path):
        return False, "Cartão inexistente.", {}

    pico = os.path.join(mount_path, "_pico")
    if not os.path.isdir(pico):
        return (
            False,
            "Pacote DSPico em falta (_pico/). Instale primeiro em «Preparar SD».",
            {},
        )

    if not isinstance(emulator_ids, (list, tuple)):
        return False, "Lista de emuladores inválida.", {}

    raw_ids = []
    for x in emulator_ids:
        if isinstance(x, str) and x.strip():
            raw_ids.append(x.strip())
    if not raw_ids:
        return False, "Seleccione pelo menos um emulador.", {}

    # Dedup preserving order
    seen = set()
    ids = []
    for i in raw_ids:
        if i in seen:
            continue
        seen.add(i)
        ids.append(i)

    selected = []
    for eid in ids:
        entry = catalog_by_id(eid)
        if entry is None:
            return False, f"Emulador desconhecido: {eid!r}", {}
        if not _pin_ready(entry["cache_key"]):
            return False, f"Pin em falta para {entry['label']}.", {}
        for ck, dest in entry.get("extra_cache_files") or []:
            if not _pin_ready(ck):
                return False, f"Pin em falta para ficheiro extra ({ck}).", {}
            if not _safe_rel(dest):
                return False, f"Destino extra inválido: {dest!r}", {}
        if not _safe_rel(entry["nds_dest"]):
            return False, f"Destino NDS inválido: {entry['nds_dest']!r}", {}
        selected.append(entry)

    # SNEmulDS 0.6a e 0.6d partilham o mesmo ficheiro — o último seleccionado ganha
    snemul = [e for e in selected if e["id"].startswith("snemulds_")]
    if len(snemul) > 1:
        keep = snemul[-1]["id"]
        selected = [
            e
            for e in selected
            if not e["id"].startswith("snemulds_") or e["id"] == keep
        ]
        log(
            f"SNEmulDS: várias versões pedidas — a instalar só {keep}."
        )

    gba_winners = _resolve_gba_association_winners(selected)
    undo = UndoStack()
    installed: list[str] = []
    associations_updated: dict[str, str] = {}
    bios_hints: list[str] = []
    rom_dirs_created: list[str] = []
    tmp_dirs: list[str] = []

    try:
        settings_path = _ensure_settings_stub(mount_path, log)
        settings = _read_settings(settings_path)
        assoc = settings.get("fileAssociations")
        if not isinstance(assoc, dict):
            assoc = {}
            settings["fileAssociations"] = assoc

        for entry in selected:
            label = entry["label"]
            log(f"=== Instalar {label} ===")
            cache_path = ensure_cached(entry["cache_key"], log_callback=log_callback)
            extract_root = None
            src_nds = None

            if entry["archive"]:
                extract_root = _extract_zip_to_tmp(cache_path, log_callback)
                tmp_dirs.append(extract_root)
                member = entry.get("nds_member") or ""
                src_nds = _find_member(extract_root, member)
                if not src_nds:
                    raise RuntimeError(
                        f"{label}: {member!r} não encontrado no arquivo."
                    )
            else:
                src_nds = cache_path

            dest_nds = os.path.join(mount_path, entry["nds_dest"].replace("/", os.sep))
            _copy_with_undo(src_nds, dest_nds, undo, log_callback=log_callback)
            log(f"✅ {entry['nds_dest']}")

            # Árvores extra do zip (ex. _gba/)
            for src_rel, dst_rel in entry.get("copy_trees") or []:
                if not extract_root:
                    continue
                if not _safe_rel(src_rel) or not _safe_rel(dst_rel):
                    raise RuntimeError("copy_trees inválido.")
                src_tree = os.path.join(extract_root, src_rel.replace("/", os.sep))
                if not os.path.isdir(src_tree):
                    # tentar find
                    found = None
                    for walk_root, dirs, _files in os.walk(extract_root):
                        for d in dirs:
                            if d.lower() == src_rel.lower().rstrip("/"):
                                found = os.path.join(walk_root, d)
                                break
                        if found:
                            break
                    src_tree = found or src_tree
                if not os.path.isdir(src_tree):
                    log(f"⚠️ Pasta {src_rel}/ em falta no arquivo — a ignorar.")
                    continue
                dst_tree = os.path.join(mount_path, dst_rel.replace("/", os.sep))
                os.makedirs(dst_tree, exist_ok=True)
                for walk_root, dirs, files in os.walk(src_tree):
                    dirs[:] = [d for d in dirs if not d.startswith(".")]
                    rel = os.path.relpath(walk_root, src_tree)
                    out_dir = (
                        dst_tree
                        if rel in (".", "")
                        else os.path.join(dst_tree, rel)
                    )
                    os.makedirs(out_dir, exist_ok=True)
                    for fname in files:
                        if fname.startswith(".") or fname == ".DS_Store":
                            continue
                        s = os.path.join(walk_root, fname)
                        d = os.path.join(out_dir, fname)
                        _copy_with_undo(s, d, undo, log_callback=None)
                log(f"✅ {dst_rel}/ (conteúdo do arquivo)")

            # snemul.cfg
            if entry.get("patch_snemul_cfg") and extract_root:
                cfg_src = _find_member(extract_root, "snemul.cfg")
                if cfg_src:
                    with open(cfg_src, "r", encoding="utf-8", errors="replace") as f:
                        patched = _patch_snemul_cfg_text(f.read())
                    dest_cfg = os.path.join(mount_path, "snemul.cfg")
                    tmp_cfg = dest_cfg + f".partial_{os.getpid()}"
                    with open(tmp_cfg, "w", encoding="utf-8") as f:
                        f.write(patched)
                        f.flush()
                        os.fsync(f.fileno())
                    bak = None
                    if os.path.isfile(dest_cfg):
                        bak = dest_cfg + f".bak_{os.getpid()}"
                        shutil.copy2(dest_cfg, bak)
                        undo.push_restore_file(bak, dest_cfg)
                    os.replace(tmp_cfg, dest_cfg)
                    if bak is None:
                        undo.push_remove(dest_cfg)
                    elif bak and os.path.isfile(bak):
                        try:
                            os.remove(bak)
                        except OSError:
                            pass
                    log("✅ snemul.cfg (ROMPath = /ROMs/SNES)")
            elif entry["id"] == "snemulds_06d" and extract_root:
                cfg_src = _find_member(extract_root, "snemul.cfg")
                if cfg_src:
                    dest_cfg = os.path.join(mount_path, "snemul.cfg")
                    _copy_with_undo(cfg_src, dest_cfg, undo, log_callback=log_callback)

            # Ficheiros extra pinados (settings.cfg, _NeoDS.ini)
            for ck, dest_rel in entry.get("extra_cache_files") or []:
                src = ensure_cached(ck, log_callback=log_callback)
                dest = os.path.join(mount_path, dest_rel.replace("/", os.sep))
                _copy_with_undo(src, dest, undo, log_callback=log_callback)
                log(f"✅ {dest_rel}")

            # Pastas
            for rel in list(entry.get("rom_dirs") or []) + list(
                entry.get("extra_dirs") or []
            ):
                if not _safe_rel(rel):
                    continue
                path = os.path.join(mount_path, rel.replace("/", os.sep))
                if not os.path.isdir(path):
                    os.makedirs(path, exist_ok=True)
                    undo.push_remove(path)
                    rom_dirs_created.append(rel)
                    log(f"📁 {rel}/")

            # Associações argv
            if entry["install_mode"] == "argv":
                skip_assoc = False
                cg = entry.get("conflict_group")
                if cg and entry["id"] not in gba_winners:
                    skip_assoc = True
                    log(
                        f"Associação .{cg}: mantida para outro emulador "
                        f"(este fica só para lançamento manual)."
                    )
                if not skip_assoc:
                    for ext, payload in (entry.get("associations") or {}).items():
                        if not isinstance(ext, str) or not ext:
                            continue
                        if not isinstance(payload, dict):
                            continue
                        app = payload.get("appPath")
                        if not isinstance(app, str) or not app.startswith("/"):
                            continue
                        assoc[ext] = {"appPath": app}
                        associations_updated[ext] = app
                        log(f"🔗 .{ext} → {app}")

            note = (entry.get("bios_notes") or "").strip()
            if note:
                bios_hints.append(f"{label}: {note}")

            installed.append(entry["id"])

        settings["fileAssociations"] = assoc
        _write_settings(settings_path, settings, undo)
        sync_volume(mount_path)

        msg = f"{len(installed)} emulador(es) instalado(s)."
        if associations_updated:
            msg += f" Associações: {', '.join('.' + e for e in sorted(associations_updated))}."
        log(f"🎉 {msg}")
        return (
            True,
            msg,
            {
                "installed": installed,
                "associations_updated": associations_updated,
                "bios_hints": bios_hints,
                "rom_dirs_created": rom_dirs_created,
            },
        )
    except Exception as e:
        undo.rollback(log_callback, mount_path=mount_path)
        return False, str(e), {"installed": installed}
    finally:
        for d in tmp_dirs:
            shutil.rmtree(d, ignore_errors=True)


def count_installed_emulators(mount_path: str) -> dict[str, Any]:
    """Contagem leve para inspect_dspico."""
    emu_dir = os.path.join(mount_path, "_pico", "emulators")
    man_dir = os.path.join(mount_path, "Emulators")
    argv_n = 0
    manual_n = 0
    if os.path.isdir(emu_dir):
        argv_n = sum(
            1
            for f in os.listdir(emu_dir)
            if f.lower().endswith(".nds") and not f.startswith(".")
        )
    if os.path.isdir(man_dir):
        manual_n = sum(
            1
            for f in os.listdir(man_dir)
            if f.lower().endswith(".nds") and not f.startswith(".")
        )
    assoc_n = 0
    settings_path = os.path.join(mount_path, "_pico", "settings.json")
    if os.path.isfile(settings_path):
        data = _read_settings(settings_path)
        fa = data.get("fileAssociations")
        if isinstance(fa, dict):
            assoc_n = len(fa)
    return {
        "argv_nds": argv_n,
        "manual_nds": manual_n,
        "associations": assoc_n,
        "ok": argv_n > 0 or manual_n > 0,
    }
