import os

from core import rom_cleaner
from tests.conftest import make_nds


def test_does_not_touch_bootloaders(fake_sd):
    make_nds(fake_sd / "boot.nds")
    (fake_sd / "unlaunch-installer.dsi").write_bytes(b"x" * 100)
    (fake_sd / "_nds").mkdir()
    (fake_sd / "_nds" / "keep.bin").write_bytes(b"k")

    # ROM solta
    make_nds(fake_sd / "My Game.nds", title=b"TESTGAME")

    ok, msg = rom_cleaner.organize_roms_directory(str(fake_sd))
    assert ok
    assert (fake_sd / "boot.nds").is_file()
    assert (fake_sd / "unlaunch-installer.dsi").is_file()
    assert (fake_sd / "_nds" / "keep.bin").is_file()


def test_junk_only_under_roms(fake_sd):
    (fake_sd / "readme.txt").write_text("keep me")
    roms = fake_sd / "roms" / "nds"
    roms.mkdir(parents=True)
    (roms / "notes.txt").write_text("delete me")
    make_nds(roms / "Game.nds")

    ok, _ = rom_cleaner.organize_roms_directory(str(fake_sd))
    assert ok
    assert (fake_sd / "readme.txt").is_file()
    assert not (roms / "notes.txt").exists()


def test_save_follows_rom(fake_sd):
    make_nds(fake_sd / "Cool Game.nds")
    (fake_sd / "Cool Game.sav").write_bytes(b"save")
    ok, _ = rom_cleaner.organize_roms_directory(str(fake_sd))
    assert ok
    # save deve estar em /roms/nds/
    found = list((fake_sd / "roms").rglob("*.sav"))
    assert found, "save não foi movido"
