"""Compatibilidade por jogo com o Pico Loader (port de PicoDex ``loaderlists.ts`` + ``rom.ts``).

Lê as três listas que o Pico Loader consulta ao abrir um jogo NDS:

- ``/_pico/aplist.bin``: correção anti-pirataria (DS Protect) por (gameCode, revisão);
- ``/_pico/savelist.bin``: tipo e tamanho do save por gameCode;
- ``/_pico/patchlist.bin``: patches por (gameCode, revisão).

e responde, para um ROM do cartão, o que o loader vai fazer com ele no boot,
na mesma ordem do loader (``NdsLoader.cpp`` / ``CardSaveArranger.cpp``).
Fonte: PicoDex de rasalopa (MIT), que documenta cada campo a partir do código
do pico-loader. Os parsers nunca levantam exceção: são tolerantes como as
fábricas do loader (sobras no fim do arquivo são ignoradas), exceto o
``patchlist.bin`` estruturalmente quebrado, que vira ``None``.

"Não listado" é um fato sobre a lista, não uma garantia sobre o jogo: o loader
também tem tabelas fixas no código (ARM9) que estas listas não mostram.
"""

from __future__ import annotations

import os
import struct
from typing import Any, Optional

from core.privacy import redact_text

# --------------------------------------------------------------------- formatos

DEFAULT_SAVE_SIZE_BYTES = 512 * 1024  # DEFAULT_SAVE_SIZE (CardSaveArranger.cpp)
_NAND_RW_REGION_END = 0x07A00000
_NTR_NAND_BLOCK_SIZE = 0x20000
_TWL_NAND_BLOCK_SIZE = 0x80000

_AP_ENTRY = 16
_SAVE_ENTRY = 8
_PATCH_HEADER_ENTRY = 8

# Ordem exata de common/DSProtectVersion.h (não é ordenada).
_DS_PROTECT_VERSIONS = (
    "v1.06", "v1.05", "v1.08", "v1.10", "v1.20", "v1.22", "v1.23", "v1.23Z",
    "v1.25", "v1.26", "v1.27", "v1.28", "v2.00", "v2.01", "v2.03", "v2.05",
    "v2.00s", "v2.01s", "v2.03s", "v2.05s", "v1.00_2",
)
_SAVE_TYPES = ("none", "eeprom", "flash", "nand")

# Limites de leitura: as listas oficiais têm dezenas de KB.
_MAX_LIST_BYTES = 8 * 1024 * 1024

# Cabeçalho NDS (rom.ts)
_NDS_GAME_CODE = 0x0C
_NDS_MAKER_CODE = 0x10
_NDS_UNIT_CODE = 0x12
_NDS_UNIT_SUPPORTS_DSI = 1 << 1
_NDS_TWL_FLAGS = 0x1C
_NDS_SOFTWARE_VERSION = 0x1E
_NDS_ARM7_LOAD_ADDRESS = 0x38
_NDS_ARM9_AUTOLOAD_HOOK = 0x70
_NDS_ARM7_AUTOLOAD_HOOK = 0x74
_NDS_ARM7_HOMEBREW_MIN = 0x03000000
_NDS_NAND_BACKUP_START = 0x96
_NDS_TITLE_ID = 0x230
_NDS_TWL_PUBLIC_SAV = 0x238
_NDS_TWL_PRIVATE_SAV = 0x23C
NDS_HEADER_PARSE_BYTES = _NDS_TWL_PRIVATE_SAV + 4


def _game_code(b: bytes, off: int) -> str:
    # Byte a byte, mesmo não imprimível: a lista é a verdade do loader.
    return b[off : off + 4].decode("latin-1")


def parse_ap_list(data: bytes) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for off in range(0, len(data) - _AP_ENTRY + 1, _AP_ENTRY):
        info = struct.unpack_from("<H", data, off + 4)[0]
        idx = (info >> 5) & 0x1F
        out.append(
            {
                "game_code": _game_code(data, off),
                "game_version": info & 0x1F,
                "ds_protect_version": _DS_PROTECT_VERSIONS[idx] if idx < len(_DS_PROTECT_VERSIONS) else "unknown",
            }
        )
    return out


def parse_save_list(data: bytes) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for off in range(0, len(data) - _SAVE_ENTRY + 1, _SAVE_ENTRY):
        stype = data[off + 4]
        log2 = data[off + 5]
        out.append(
            {
                "game_code": _game_code(data, off),
                "save_type": _SAVE_TYPES[stype] if stype < len(_SAVE_TYPES) else "unknown",
                "save_size_bytes": 0 if log2 == 0 else 2**log2,
            }
        )
    return out


def parse_patch_list(data: bytes) -> Optional[list[dict[str, Any]]]:
    if len(data) < 4:
        return None
    count = struct.unpack_from("<I", data, 0)[0]
    if 4 + count * _PATCH_HEADER_ENTRY > len(data):
        return None
    out: list[dict[str, Any]] = []
    for i in range(count):
        off = 4 + i * _PATCH_HEADER_ENTRY
        packed = struct.unpack_from("<I", data, off + 4)[0]
        body = packed >> 8
        if body + 4 > len(data):
            return None
        out.append(
            {
                "game_code": _game_code(data, off),
                "game_version": packed & 0xFF,
                "patch_count": struct.unpack_from("<H", data, body + 2)[0],
            }
        )
    return out


def _read_capped(path: str) -> Optional[bytes]:
    try:
        if not os.path.isfile(path) or os.path.getsize(path) > _MAX_LIST_BYTES:
            return None
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None


def load_loader_lists(mount_path: str) -> dict[str, Any]:
    """As três listas do cartão. ``None`` = arquivo ausente (ou patchlist ilegível)."""
    pico = os.path.join(mount_path, "_pico")
    ap = _read_capped(os.path.join(pico, "aplist.bin"))
    save = _read_capped(os.path.join(pico, "savelist.bin"))
    patch = _read_capped(os.path.join(pico, "patchlist.bin"))
    return {
        "ap": None if ap is None else parse_ap_list(ap),
        "save": None if save is None else parse_save_list(save),
        "patch": None if patch is None else parse_patch_list(patch),
    }


# ---------------------------------------------------------------- cabeçalho NDS


def _u32(b: bytes, off: int) -> Optional[int]:
    return struct.unpack_from("<I", b, off)[0] if len(b) >= off + 4 else None


def parse_nds_header_fields(header: bytes) -> dict[str, Any]:
    """Campos do cabeçalho que decidem o caminho do loader (rom.ts)."""
    h = header or b""
    code = h[_NDS_GAME_CODE : _NDS_GAME_CODE + 4].decode("latin-1") if len(h) >= _NDS_GAME_CODE + 4 else ""
    usable = len(code) == 4 and all(0x21 <= ord(c) <= 0x7E for c in code)
    software_version = h[_NDS_SOFTWARE_VERSION] if len(h) > _NDS_SOFTWARE_VERSION else None
    supports_dsi = bool(h[_NDS_UNIT_CODE] & _NDS_UNIT_SUPPORTS_DSI) if len(h) > _NDS_UNIT_CODE else None
    nand_start = (
        h[_NDS_NAND_BACKUP_START] | (h[_NDS_NAND_BACKUP_START + 1] << 8)
        if len(h) >= _NDS_NAND_BACKUP_START + 2
        else None
    )
    arm7 = _u32(h, _NDS_ARM7_LOAD_ADDRESS)
    hook9 = _u32(h, _NDS_ARM9_AUTOLOAD_HOOK)
    hook7 = _u32(h, _NDS_ARM7_AUTOLOAD_HOOK)
    homebrew: Optional[bool] = None
    if len(h) >= _NDS_MAKER_CODE + 2 and None not in (arm7, hook9, hook7):
        homebrew = (
            (h[_NDS_MAKER_CODE] == 0 and h[_NDS_MAKER_CODE + 1] == 0)
            or (hook9 == 0 and hook7 == 0)
            or arm7 >= _NDS_ARM7_HOMEBREW_MIN
        )
    title_hi = _u32(h, _NDS_TITLE_ID + 4)
    dsiware: Optional[bool] = None
    if len(h) > _NDS_TWL_FLAGS and title_hi is not None:
        dsiware = bool(h[_NDS_TWL_FLAGS] & 1) and bool(title_hi & 4)
    pub = _u32(h, _NDS_TWL_PUBLIC_SAV)
    prv = _u32(h, _NDS_TWL_PRIVATE_SAV)
    return {
        "game_code": code if usable else None,
        "software_version": software_version,
        "supports_dsi_mode": supports_dsi,
        "nand_backup_region_start": nand_start,
        "is_homebrew": homebrew,
        "is_dsiware": dsiware,
        "dsiware_save_bytes": None if pub is None or prv is None else {"public": pub, "private": prv},
    }


# --------------------------------------------------------------- consulta por jogo


def _patch_for(patch_list: Optional[list[dict[str, Any]]], code: str, version: int) -> dict[str, Any]:
    if patch_list is None:
        return {"status": "list-unavailable", "patch_count": 0, "entry_versions": []}
    entries = [e for e in patch_list if e["game_code"] == code]
    match = next((e for e in entries if e["game_version"] == version), None)
    return {
        "status": "not-listed" if not entries else ("applies" if match else "version-mismatch"),
        "patch_count": match["patch_count"] if match else 0,
        "entry_versions": [e["game_version"] for e in entries],
    }


def compat_for_game(lists: dict[str, Any], header: dict[str, Any]) -> dict[str, Any]:
    """``compatForGame`` da PicoDex, com o cabeçalho já lido por :func:`parse_nds_header_fields`."""
    code = header.get("game_code") or ""
    rom_version = header.get("software_version")
    match_version = rom_version if isinstance(rom_version, int) else 0
    if header.get("is_homebrew"):
        kind = "homebrew"
    elif header.get("is_dsiware"):
        kind = "dsiware"
    else:
        kind = "retail"

    if kind != "retail":
        dsi = kind == "dsiware"
        sizes = header.get("dsiware_save_bytes") or {}
        save = (
            {"save_type": None, "size_bytes": sizes.get("public", 0), "private_size_bytes": sizes.get("private", 0), "source": "dsiware-header"}
            if dsi
            else {"save_type": None, "size_bytes": 0, "source": "homebrew-none"}
        )
        return {
            "kind": kind,
            "save": save,
            "ap": {"status": "not-applicable", "ds_protect_version": None, "entry_versions": [], "rom_version": rom_version},
            # DSiWare passa pelo passo de patches (bloco separado no NdsLoader.cpp).
            "patch": _patch_for(lists.get("patch"), code, match_version)
            if dsi
            else {"status": "not-applicable", "patch_count": 0, "entry_versions": []},
        }

    nand_start = header.get("nand_backup_region_start") or 0
    if nand_start > 0:
        block = _TWL_NAND_BLOCK_SIZE if header.get("supports_dsi_mode") else _NTR_NAND_BLOCK_SIZE
        save = {"save_type": "nand", "size_bytes": max(0, _NAND_RW_REGION_END - nand_start * block), "source": "nand-header"}
    else:
        entry = next((e for e in (lists.get("save") or []) if e["game_code"] == code), None)
        save = (
            {"save_type": entry["save_type"], "size_bytes": entry["save_size_bytes"], "source": "list"}
            if entry
            else {"save_type": None, "size_bytes": DEFAULT_SAVE_SIZE_BYTES, "source": "default"}
        )

    ap_list = lists.get("ap")
    if ap_list is None:
        ap = {"status": "list-unavailable", "ds_protect_version": None, "entry_versions": [], "rom_version": rom_version}
    else:
        entries = [e for e in ap_list if e["game_code"] == code]
        match = next((e for e in entries if e["game_version"] == match_version), None)
        ap = {
            "status": "not-listed" if not entries else ("applies" if match else "version-mismatch"),
            "ds_protect_version": match["ds_protect_version"] if match else None,
            "entry_versions": [e["game_version"] for e in entries],
            "rom_version": rom_version,
        }

    return {"kind": kind, "save": save, "ap": ap, "patch": _patch_for(lists.get("patch"), code, match_version)}


def game_compat(mount_path: str, rom_path: str) -> dict[str, Any]:
    """Ficha de compatibilidade de um ``.nds``/``.dsi`` do cartão (só leitura)."""
    try:
        with open(rom_path, "rb") as f:
            header = f.read(NDS_HEADER_PARSE_BYTES)
    except OSError as e:
        return {"success": False, "error": redact_text(f"Não foi possível ler o ROM: {e}")}
    fields = parse_nds_header_fields(header)
    if not fields["game_code"]:
        return {"success": False, "error": "O cabeçalho do ROM não tem um código de jogo legível."}
    lists = load_loader_lists(mount_path)
    return {
        "success": True,
        "game_code": fields["game_code"],
        "rom_version": fields["software_version"],
        "compat": compat_for_game(lists, fields),
        "lists": {k: (v is not None) for k, v in lists.items()},
    }
