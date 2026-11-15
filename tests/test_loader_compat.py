"""Compatibilidade por jogo com o Pico Loader (casos portados de PicoDex loaderlists.test.ts)."""

from __future__ import annotations

import struct

from core import loader_compat as lc


def ap_entry(code: str, version: int, protect_idx: int) -> bytes:
    info = (version & 0x1F) | ((protect_idx & 0x1F) << 5)
    return code.encode("latin-1") + struct.pack("<H", info) + b"\0" * 10


def save_entry(code: str, stype: int, log2: int) -> bytes:
    return code.encode("latin-1") + bytes([stype, log2]) + b"\0\0"


def patch_file(entries: list[tuple[str, int, int]]) -> bytes:
    header = struct.pack("<I", len(entries))
    bodies = b""
    body_start = 4 + 8 * len(entries)
    for code, version, count in entries:
        offset = body_start + len(bodies)
        header += code.encode("latin-1") + struct.pack("<I", (offset << 8) | version)
        bodies += struct.pack("<HH", 4, count)
    return header + bodies


def header(code="AMCE", version=0, *, nand_start=0, dsi=False, homebrew=False, dsiware=False, pub=0, prv=0) -> dict:
    return {
        "game_code": code,
        "software_version": version,
        "supports_dsi_mode": dsi,
        "nand_backup_region_start": nand_start,
        "is_homebrew": homebrew,
        "is_dsiware": dsiware,
        "dsiware_save_bytes": {"public": pub, "private": prv},
    }


def test_parse_ap_list_decodes_bitfield_and_floors_trailing_bytes():
    data = ap_entry("AMCE", 1, 9) + ap_entry("ABCD", 0, 31) + b"\x01\x02\x03"
    out = lc.parse_ap_list(data)
    assert out == [
        {"game_code": "AMCE", "game_version": 1, "ds_protect_version": "v1.26"},
        {"game_code": "ABCD", "game_version": 0, "ds_protect_version": "unknown"},
    ]
    assert lc.parse_ap_list(b"") == []
    assert lc.parse_ap_list(b"\0" * 15) == []


def test_parse_save_list_types_sizes_and_unknown():
    data = save_entry("AAAA", 0, 0) + save_entry("BBBB", 1, 9) + save_entry("CCCC", 2, 18) + save_entry("DDDD", 3, 23) + save_entry("EEEE", 7, 10)
    out = lc.parse_save_list(data + b"\xff")
    assert [(e["save_type"], e["save_size_bytes"]) for e in out] == [
        ("none", 0), ("eeprom", 512), ("flash", 256 * 1024), ("nand", 8 * 1024 * 1024), ("unknown", 1024)
    ]


def test_parse_patch_list_follows_offsets_and_rejects_broken_files():
    out = lc.parse_patch_list(patch_file([("AMCE", 0, 3), ("AMCE", 1, 5)]))
    assert out == [
        {"game_code": "AMCE", "game_version": 0, "patch_count": 3},
        {"game_code": "AMCE", "game_version": 1, "patch_count": 5},
    ]
    assert lc.parse_patch_list(struct.pack("<I", 0)) == []
    assert lc.parse_patch_list(b"\0\0") is None
    assert lc.parse_patch_list(struct.pack("<I", 3)) is None  # contagem não cabe
    bad = struct.pack("<I", 1) + b"AMCE" + struct.pack("<I", (0xFFFF << 8))
    assert lc.parse_patch_list(bad) is None


def test_compat_unavailable_lists_and_default_save():
    c = lc.compat_for_game({"ap": None, "save": None, "patch": None}, header())
    assert c["kind"] == "retail"
    assert c["ap"]["status"] == "list-unavailable"
    assert c["patch"]["status"] == "list-unavailable"
    assert c["save"] == {"save_type": None, "size_bytes": lc.DEFAULT_SAVE_SIZE_BYTES, "source": "default"}


def test_compat_exact_version_match_without_fallback():
    lists = {
        "ap": lc.parse_ap_list(ap_entry("AMCE", 1, 9)),
        "save": lc.parse_save_list(save_entry("AMCE", 2, 18)),
        "patch": lc.parse_patch_list(patch_file([("AMCE", 1, 4)])),
    }
    hit = lc.compat_for_game(lists, header(version=1))
    assert hit["ap"] == {"status": "applies", "ds_protect_version": "v1.26", "entry_versions": [1], "rom_version": 1}
    assert hit["patch"]["status"] == "applies" and hit["patch"]["patch_count"] == 4
    assert hit["save"] == {"save_type": "flash", "size_bytes": 256 * 1024, "source": "list"}
    miss = lc.compat_for_game(lists, header(version=0))
    assert miss["ap"]["status"] == "version-mismatch"
    assert miss["patch"]["status"] == "version-mismatch"
    assert miss["save"]["source"] == "list"  # savelist só olha o gameCode
    other = lc.compat_for_game(lists, header(code="ZZZZ"))
    assert other["ap"]["status"] == "not-listed" and other["patch"]["status"] == "not-listed"


def test_unreadable_version_falls_back_to_zero():
    lists = {"ap": lc.parse_ap_list(ap_entry("AMCE", 0, 1)), "save": [], "patch": []}
    c = lc.compat_for_game(lists, header(version=None))
    assert c["ap"]["status"] == "applies" and c["ap"]["rom_version"] is None


def test_nand_header_wins_over_savelist_with_mode_dependent_block():
    lists = {"ap": [], "save": lc.parse_save_list(save_entry("AMCE", 1, 9)), "patch": []}
    ntr = lc.compat_for_game(lists, header(nand_start=0x100))
    assert ntr["save"] == {"save_type": "nand", "size_bytes": 0x07A00000 - 0x100 * 0x20000, "source": "nand-header"}
    twl = lc.compat_for_game(lists, header(nand_start=0x10, dsi=True))
    assert twl["save"]["size_bytes"] == 0x07A00000 - 0x10 * 0x80000
    huge = lc.compat_for_game(lists, header(nand_start=0xFFFF))
    assert huge["save"]["size_bytes"] == 0


def test_homebrew_and_dsiware_paths():
    lists = {
        "ap": lc.parse_ap_list(ap_entry("AMCE", 0, 1)),
        "save": lc.parse_save_list(save_entry("AMCE", 1, 9)),
        "patch": lc.parse_patch_list(patch_file([("AMCE", 0, 2)])),
    }
    hb = lc.compat_for_game(lists, header(homebrew=True))
    assert hb["kind"] == "homebrew"
    assert hb["save"]["source"] == "homebrew-none"
    assert hb["ap"]["status"] == "not-applicable" and hb["patch"]["status"] == "not-applicable"
    dw = lc.compat_for_game(lists, header(dsiware=True, pub=0x4000, prv=0x1000))
    assert dw["kind"] == "dsiware"
    assert dw["save"] == {"save_type": None, "size_bytes": 0x4000, "private_size_bytes": 0x1000, "source": "dsiware-header"}
    assert dw["ap"]["status"] == "not-applicable"
    assert dw["patch"]["status"] == "applies" and dw["patch"]["patch_count"] == 2


def test_parse_nds_header_fields():
    h = bytearray(lc.NDS_HEADER_PARSE_BYTES)
    h[0x0C:0x10] = b"AMCE"
    h[0x10:0x12] = b"01"
    h[0x12] = 0x02
    h[0x1E] = 3
    h[0x96:0x98] = struct.pack("<H", 0x20)
    struct.pack_into("<I", h, 0x38, 0x02380000)
    struct.pack_into("<I", h, 0x70, 0x02000800)
    struct.pack_into("<I", h, 0x74, 0x02380800)
    f = lc.parse_nds_header_fields(bytes(h))
    assert f["game_code"] == "AMCE" and f["software_version"] == 3
    assert f["supports_dsi_mode"] is True and f["nand_backup_region_start"] == 0x20
    assert f["is_homebrew"] is False and f["is_dsiware"] is False
    h[0x10:0x12] = b"\0\0"
    assert lc.parse_nds_header_fields(bytes(h))["is_homebrew"] is True
    h[0x0C:0x10] = b"####"[:3] + b"\x01"
    assert lc.parse_nds_header_fields(bytes(h))["game_code"] is None


def test_game_compat_reads_card_files(fake_sd):
    pico = fake_sd / "_pico"
    pico.mkdir()
    (pico / "aplist.bin").write_bytes(ap_entry("AMCE", 0, 9))
    (pico / "savelist.bin").write_bytes(save_entry("AMCE", 2, 19))
    rom = fake_sd / "Games" / "k.nds"
    rom.parent.mkdir()
    h = bytearray(lc.NDS_HEADER_PARSE_BYTES)
    h[0x0C:0x10] = b"AMCE"
    h[0x10:0x12] = b"01"
    struct.pack_into("<I", h, 0x38, 0x02380000)
    struct.pack_into("<I", h, 0x70, 1)
    rom.write_bytes(bytes(h))
    r = lc.game_compat(str(fake_sd), str(rom))
    assert r["success"] is True
    assert r["lists"] == {"ap": True, "save": True, "patch": False}
    assert r["compat"]["ap"]["status"] == "applies"
    assert r["compat"]["patch"]["status"] == "list-unavailable"
    assert r["compat"]["save"]["size_bytes"] == 512 * 1024
