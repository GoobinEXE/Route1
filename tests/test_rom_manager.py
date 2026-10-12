"""Testes do gestor de ROMs (listar / importar / remover)."""

import os

from core import rom_manager
from core.sdio import copy_fast
from tests.conftest import make_nds


def test_copy_fast_size_match(tmp_path):
    src = tmp_path / "a.bin"
    src.write_bytes(b"hello-rom-data" * 100)
    dst = tmp_path / "out" / "a.bin"
    n = copy_fast(str(src), str(dst))
    assert n == src.stat().st_size
    assert dst.read_bytes() == src.read_bytes()
    assert not (tmp_path / "out" / "a.bin.partial").exists()


def test_list_roms_and_sidecars(fake_sd):
    nds = fake_sd / "roms" / "nds"
    nds.mkdir(parents=True)
    make_nds(nds / "Kart.nds", title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")
    (nds / "Kart.sav").write_bytes(b"save")
    (nds / "Kart.sha1").write_text("abc")

    data = rom_manager.list_roms(str(fake_sd))
    assert data["success"]
    assert data["count"] == 1
    item = data["roms"][0]
    assert item["platform"] == "nds"
    assert item["has_save"] is True
    assert item["game_code"] == "AMCE"
    assert any(s["ext"] == ".sav" for s in item["sidecars"])


def test_import_roms_fast(fake_sd, tmp_path):
    src = tmp_path / "Pearl.nds"
    make_nds(src, title=b"POKEMON P", code=b"APAE", maker=b"01")
    (tmp_path / "Pearl.sav").write_bytes(b"pearl-save")

    ok, msg, stats = rom_manager.import_roms(
        str(fake_sd), [str(src)], layout="console"
    )
    assert ok, msg
    assert stats["imported"] == 1
    assert stats["saves"] == 1
    assert list((fake_sd / "roms" / "nds").glob("*.nds"))
    assert list((fake_sd / "roms" / "nds").glob("*.sav"))


def test_import_layout_both(fake_sd, tmp_path):
    src = tmp_path / "Pearl.nds"
    make_nds(src, title=b"POKEMON P", code=b"APAE", maker=b"01")
    ok, msg, _ = rom_manager.import_roms(str(fake_sd), [str(src)], layout="both")
    assert ok, msg
    assert list((fake_sd / "roms" / "nds" / "Pokemon").glob("*.nds"))


def test_delete_roms_with_save_delete(fake_sd):
    nds = fake_sd / "roms" / "nds"
    nds.mkdir(parents=True)
    make_nds(nds / "Kart.nds", title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")
    (nds / "Kart.sav").write_bytes(b"save")
    (nds / "Kart.nds.partial").write_bytes(b"ghost")

    ok, msg, stats = rom_manager.delete_roms(
        str(fake_sd), ["nds/Kart.nds"], save_mode="delete"
    )
    assert ok, msg
    assert stats["deleted"] == 1
    assert stats["saves_deleted"] == 1
    assert not (nds / "Kart.nds").exists()
    assert not (nds / "Kart.sav").exists()


def test_delete_roms_keep_saves(fake_sd):
    nds = fake_sd / "roms" / "nds"
    nds.mkdir(parents=True)
    make_nds(nds / "Kart.nds", title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")
    (nds / "Kart.sav").write_bytes(b"save")

    ok, msg, stats = rom_manager.delete_roms(
        str(fake_sd), ["nds/Kart.nds"], save_mode="keep"
    )
    assert ok, msg
    assert stats["saves_kept"] == 1
    assert not (nds / "Kart.nds").exists()
    assert list((fake_sd / "roms" / "saves").glob("*.sav"))


def test_delete_roms_backup_saves(fake_sd, tmp_path):
    nds = fake_sd / "roms" / "nds"
    nds.mkdir(parents=True)
    make_nds(nds / "Kart.nds", title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")
    (nds / "Kart.sav").write_bytes(b"save-data")
    backup = tmp_path / "bak"

    ok, msg, stats = rom_manager.delete_roms(
        str(fake_sd),
        ["nds/Kart.nds"],
        save_mode="backup",
        backup_dir=str(backup),
    )
    assert ok, msg
    assert stats["saves_backed"] == 1
    assert not (nds / "Kart.sav").exists()
    backed = list(backup.rglob("*.sav"))
    assert backed
    assert backed[0].read_bytes() == b"save-data"


def test_path_traversal_rejected(fake_sd):
    assert rom_manager._resolve_under_roms(str(fake_sd), "../boot.nds") is None
    assert rom_manager._resolve_under_roms(str(fake_sd), "nds/../../etc/passwd") is None


def test_normalize_save_mode():
    assert rom_manager.normalize_save_mode("keep_on_sd") == "keep"
    assert rom_manager.normalize_save_mode("nope") is None


def test_list_rom_dir_and_tree(fake_sd):
    nds = fake_sd / "roms" / "nds" / "Pokemon"
    nds.mkdir(parents=True)
    make_nds(nds / "Pearl.nds", title=b"POKEMON P", code=b"APAE", maker=b"01")

    root = rom_manager.list_rom_dir(str(fake_sd), "")
    assert root["success"]
    assert any(d["name"] == "nds" for d in root["dirs"])

    sub = rom_manager.list_rom_dir(str(fake_sd), "nds/Pokemon")
    assert sub["success"]
    assert len(sub["files"]) == 1
    assert sub["files"][0]["game_code"] == "APAE"

    tree = rom_manager.list_rom_tree(str(fake_sd))
    assert tree["success"]
    assert tree["tree"][0]["name"] == "roms"
    assert any(c["name"] == "nds" for c in tree["tree"][0]["children"])

    browse = rom_manager.browse_roms(str(fake_sd), "nds/Pokemon")
    assert browse["success"]
    assert len(browse["files"]) == 1
    assert browse["tree"][0]["name"] == "roms"


def test_mkdir_rom_dir(fake_sd):
    ok, msg, stats = rom_manager.mkdir_rom_dir(str(fake_sd), "", "Custom")
    assert ok, msg
    assert (fake_sd / "roms" / "Custom").is_dir()
    assert stats["rel_path"] == "Custom"


def test_move_roms_with_save(fake_sd):
    src = fake_sd / "roms" / "nds"
    src.mkdir(parents=True)
    make_nds(src / "Kart.nds", title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")
    (src / "Kart.sav").write_bytes(b"save")
    dest = fake_sd / "roms" / "Mario"
    dest.mkdir(parents=True)

    ok, msg, stats = rom_manager.move_roms(
        str(fake_sd), ["nds/Kart.nds"], dest_rel_dir="Mario"
    )
    assert ok, msg
    assert stats["moved"] == 1
    assert list(dest.glob("*.nds"))
    assert list(dest.glob("*.sav"))
    assert not (src / "Kart.nds").exists()


def test_move_roms_rejects_traversal(fake_sd):
    ok, msg, _ = rom_manager.move_roms(
        str(fake_sd), ["nds/x.nds"], dest_rel_dir="../etc"
    )
    assert not ok


def test_import_with_dest_rel_dir(fake_sd, tmp_path):
    (fake_sd / "roms" / "Inbox").mkdir(parents=True)
    src = tmp_path / "Game.nds"
    make_nds(src, title=b"TESTGAME", code=b"AMCE", maker=b"01")
    ok, msg, stats = rom_manager.import_roms(
        str(fake_sd), [str(src)], layout="console", dest_rel_dir="Inbox"
    )
    assert ok, msg
    assert stats["imported"] == 1
    assert list((fake_sd / "roms" / "Inbox").glob("*.nds"))
    assert not list((fake_sd / "roms" / "nds").glob("*.nds"))


def _tiny_png(path):
    """PNG 1×1 mínimo válido."""
    import struct
    import zlib

    def chunk(tag, data):
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    raw = b"\x00" + bytes((0, 128, 255, 255))
    data = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(data)


def test_rom_details_and_boxart_tid(fake_sd, tmp_path):
    nds = fake_sd / "roms" / "nds"
    nds.mkdir(parents=True)
    make_nds(nds / "Kart.nds", title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")
    box = fake_sd / "_nds" / "TWiLightMenu" / "boxart"
    box.mkdir(parents=True)
    _tiny_png(box / "AMCE.png")

    data = rom_manager.rom_details(str(fake_sd), "nds/Kart.nds")
    assert data["success"], data.get("error")
    assert data["rom"]["game_code"] == "AMCE"
    assert data["boxart"] and data["boxart"].startswith("data:image/png")
    assert data["run_info"]["title"]
    assert "nds-bootstrap" in " ".join(data["run_info"]["requirements"])


def test_rom_details_filename_boxart_gba(fake_sd):
    gba = fake_sd / "roms" / "gba"
    gba.mkdir(parents=True)
    (gba / "Minish.gba").write_bytes(b"GBA" * 20)
    box = fake_sd / "_nds" / "TWiLightMenu" / "boxart"
    box.mkdir(parents=True)
    _tiny_png(box / "Minish.gba.png")

    data = rom_manager.rom_details(str(fake_sd), "gba/Minish.gba")
    assert data["success"], data.get("error")
    assert data["rom"]["platform"] == "gba"
    assert data["boxart"]
    assert "GBARunner" in data["run_info"]["body"] or "GBARunner" in " ".join(
        data["run_info"]["requirements"]
    )


def test_set_rom_artwork_boxart_and_icon(fake_sd, tmp_path):
    nds = fake_sd / "roms" / "nds"
    nds.mkdir(parents=True)
    make_nds(nds / "Kart.nds", title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")
    png = tmp_path / "art.png"
    _tiny_png(png)

    ok, msg, stats = rom_manager.set_rom_artwork(
        str(fake_sd), "nds/Kart.nds", "boxart", str(png)
    )
    assert ok, msg
    dest = fake_sd / "_nds" / "TWiLightMenu" / "boxart" / "AMCE.png"
    assert dest.is_file()
    assert stats.get("preview")
    from core.pico_bmp import decode_png_rgba

    bw, bh, _ = decode_png_rgba(dest.read_bytes())
    assert (bw, bh) == (128, 115)

    ok, msg, stats = rom_manager.set_rom_artwork(
        str(fake_sd), "nds/Kart.nds", "icon", str(png)
    )
    assert ok, msg
    icon = fake_sd / "_nds" / "TWiLightMenu" / "icons" / "Kart.nds.png"
    assert icon.is_file()
    iw, ih, _ = decode_png_rgba(icon.read_bytes())
    assert (iw, ih) == (32, 32)

    details = rom_manager.rom_details(str(fake_sd), "nds/Kart.nds")
    assert details["custom_icon"]
    assert details["boxart"]


def test_set_rom_artwork_rejects_non_png(fake_sd, tmp_path):
    nds = fake_sd / "roms" / "nds"
    nds.mkdir(parents=True)
    make_nds(nds / "Kart.nds", title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")
    bad = tmp_path / "x.jpg"
    bad.write_bytes(b"not-a-png")
    ok, msg, _ = rom_manager.set_rom_artwork(
        str(fake_sd), "nds/Kart.nds", "boxart", str(bad)
    )
    assert not ok
    assert "PNG" in msg or "BMP" in msg


def test_set_rom_artwork_accepts_bmp(fake_sd, tmp_path):
    import struct

    nds = fake_sd / "roms" / "nds"
    nds.mkdir(parents=True)
    make_nds(nds / "Kart.nds", title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")
    bmp = tmp_path / "art.bmp"
    w, h = 2, 2
    row = b"\x00\x80\xff" * w + b"\x00\x00"  # BGR + pad
    pixels = row * h
    off = 54
    size = off + len(pixels)
    bmp.write_bytes(
        struct.pack("<2sIHHI", b"BM", size, 0, 0, off)
        + struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0, len(pixels), 0, 0, 0, 0)
        + pixels
    )
    ok, msg, _ = rom_manager.set_rom_artwork(
        str(fake_sd), "nds/Kart.nds", "boxart", str(bmp)
    )
    assert ok, msg
    dest = fake_sd / "_nds" / "TWiLightMenu" / "boxart" / "AMCE.png"
    assert dest.is_file()
    assert dest.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_set_rom_artwork_rejects_traversal(fake_sd, tmp_path):
    png = tmp_path / "art.png"
    _tiny_png(png)
    ok, msg, _ = rom_manager.set_rom_artwork(
        str(fake_sd), "../boot.nds", "boxart", str(png)
    )
    assert not ok


def test_find_duplicate_roms_by_game_code(fake_sd):
    nds = fake_sd / "roms" / "nds"
    nds.mkdir(parents=True)
    make_nds(nds / "Kart.nds", title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")
    make_nds(nds / "Kart (2).nds", title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")
    make_nds(nds / "Other.nds", title=b"OTHERGAME", code=b"BBBB", maker=b"01")

    data = rom_manager.find_duplicate_roms(str(fake_sd))
    assert data["success"]
    assert data["count"] == 1
    group = data["groups"][0]
    assert group["key"] == "tid:AMCE"
    assert len(group["items"]) == 2


def test_find_duplicate_roms_gba_by_name(fake_sd):
    gba = fake_sd / "roms" / "gba"
    gba.mkdir(parents=True)
    (gba / "Minish.gba").write_bytes(b"GBA-ROM-A" * 20)
    (gba / "Minish (2).gba").write_bytes(b"GBA-ROM-B" * 20)

    data = rom_manager.find_duplicate_roms(str(fake_sd))
    assert data["success"]
    assert data["count"] == 1
    assert data["groups"][0]["key"].startswith("name:gba:")
    assert len(data["groups"][0]["items"]) == 2


def test_check_and_import_conflict_resolutions(fake_sd, tmp_path):
    nds = fake_sd / "roms" / "nds"
    nds.mkdir(parents=True)
    make_nds(nds / "Kart.nds", title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")

    src = tmp_path / "NewKart.nds"
    make_nds(src, title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")

    check = rom_manager.check_rom_import_conflicts(
        str(fake_sd), [str(src)], layout="console"
    )
    assert check["success"]
    assert check["has_conflicts"]
    assert len(check["conflicts"]) == 1
    cid = check["conflicts"][0]["conflict_id"]
    assert cid.startswith("tid:AMCE|")

    ok, msg, stats = rom_manager.import_roms(
        str(fake_sd),
        [str(src)],
        layout="console",
        conflict_resolutions={cid: "skip"},
    )
    assert ok, msg
    assert stats["imported"] == 0
    assert stats["skipped"] >= 1
    assert len(list(nds.glob("*.nds"))) == 1

    ok, msg, stats = rom_manager.import_roms(
        str(fake_sd),
        [str(src)],
        layout="console",
        conflict_resolutions={cid: "keep_both"},
    )
    assert ok, msg
    assert stats["imported"] == 1
    assert len(list(nds.glob("*.nds"))) == 2

    for p in nds.glob("*.nds"):
        p.unlink()
    make_nds(
        nds / "Kart.nds",
        title=b"MARIOKARTDS",
        code=b"AMCE",
        maker=b"01",
        payload=b"\x00" * 100,
    )
    old_size = (nds / "Kart.nds").stat().st_size
    src2 = tmp_path / "Bigger.nds"
    make_nds(
        src2,
        title=b"MARIOKARTDS",
        code=b"AMCE",
        maker=b"01",
        payload=b"\x11" * 4096,
    )
    check2 = rom_manager.check_rom_import_conflicts(
        str(fake_sd), [str(src2)], layout="console"
    )
    cid2 = check2["conflicts"][0]["conflict_id"]
    ok, msg, stats = rom_manager.import_roms(
        str(fake_sd),
        [str(src2)],
        layout="console",
        conflict_resolutions={cid2: "replace"},
    )
    assert ok, msg
    assert stats["imported"] == 1
    assert stats.get("replaced", 0) >= 1
    files = list(nds.glob("*.nds"))
    assert len(files) == 1
    assert files[0].stat().st_size > old_size


def test_normalize_conflict_resolutions_rejects_bad():
    assert rom_manager.normalize_conflict_resolutions(None) == {}
    assert rom_manager.normalize_conflict_resolutions({"a": "skip"}) == {"a": "skip"}
    assert rom_manager.normalize_conflict_resolutions({"a": "nope"}) is None
    assert rom_manager.normalize_conflict_resolutions("x") is None
