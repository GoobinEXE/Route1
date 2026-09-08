import os

from core import rom_cleaner
from tests.conftest import make_nds


def test_does_not_touch_bootloaders(fake_sd):
    make_nds(fake_sd / "boot.nds")
    (fake_sd / "unlaunch-installer.dsi").write_bytes(b"x" * 100)
    (fake_sd / "_nds").mkdir()
    (fake_sd / "_nds" / "keep.bin").write_bytes(b"k")

    # ROM comercial solta
    make_nds(
        fake_sd / "My Game.nds",
        title=b"MARIOKARTDS",
        code=b"AMCE",
        maker=b"01",
    )

    ok, msg = rom_cleaner.organize_roms_directory(str(fake_sd))
    assert ok
    assert (fake_sd / "boot.nds").is_file()
    assert (fake_sd / "unlaunch-installer.dsi").is_file()
    assert (fake_sd / "_nds" / "keep.bin").is_file()
    assert (fake_sd / "roms" / "nds").is_dir()
    assert list((fake_sd / "roms" / "nds").glob("*.nds"))


def test_junk_only_under_roms(fake_sd):
    (fake_sd / "readme.txt").write_text("keep me")
    roms = fake_sd / "roms" / "nds"
    roms.mkdir(parents=True)
    (roms / "notes.txt").write_text("delete me")
    make_nds(roms / "Game.nds", title=b"TESTGAME", code=b"AMCE", maker=b"01")

    ok, _ = rom_cleaner.organize_roms_directory(str(fake_sd))
    assert ok
    assert (fake_sd / "readme.txt").is_file()
    assert not (roms / "notes.txt").exists()


def test_save_follows_rom(fake_sd):
    make_nds(fake_sd / "Cool Game.nds", title=b"COOLGAME", code=b"AMCE", maker=b"01")
    (fake_sd / "Cool Game.sav").write_bytes(b"save")
    ok, _ = rom_cleaner.organize_roms_directory(str(fake_sd))
    assert ok
    found = list((fake_sd / "roms").rglob("*.sav"))
    assert found, "save não foi movido"
    assert "nds" in str(found[0])


def test_homebrew_goes_to_apps(fake_sd):
    make_nds(fake_sd / "MyTool.nds", title=b"HOMEBREW", code=b"####", maker=b"00")
    ok, _ = rom_cleaner.organize_roms_directory(str(fake_sd))
    assert ok
    apps = list((fake_sd / "roms" / "apps").glob("*.nds"))
    assert apps
    assert not list((fake_sd / "roms" / "nds").glob("*.nds"))


def test_dsiware_goes_to_nds_flat(fake_sd):
    """DSi exclusive (unitcode 2) deve ir para /roms/nds/, não /roms/dsi/."""
    make_nds(
        fake_sd / "DSiWare.nds",
        title=b"DSIWARE",
        code=b"KACE",
        maker=b"01",
        unitcode=2,
    )
    ok, _ = rom_cleaner.organize_roms_directory(str(fake_sd))
    assert ok
    assert list((fake_sd / "roms" / "nds").glob("*.nds"))
    assert not (fake_sd / "roms" / "dsi").exists() or not list(
        (fake_sd / "roms" / "dsi").glob("*.nds")
    )


def test_moves_from_roms_dsi_to_nds(fake_sd):
    dsi = fake_sd / "roms" / "dsi"
    dsi.mkdir(parents=True)
    make_nds(dsi / "OldDSi.nds", title=b"OLDGAME", code=b"AMCE", maker=b"01", unitcode=2)
    ok, _ = rom_cleaner.organize_roms_directory(str(fake_sd))
    assert ok
    assert list((fake_sd / "roms" / "nds").glob("*.nds"))


def test_classify_nds_kind_system_and_game():
    assert (
        rom_cleaner.classify_nds_kind("x", "####", "00", "boot.nds", at_sd_root=True)
        == "system"
    )
    assert rom_cleaner.classify_nds_kind("x", "AMCE", "01", "game.nds") == "game"
    assert rom_cleaner.classify_nds_kind("x", "####", "00", "tool.nds") == "app"
