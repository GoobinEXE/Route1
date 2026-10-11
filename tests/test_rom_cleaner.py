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


def test_detect_franchise_by_code_and_name():
    assert rom_cleaner.detect_franchise("Anything", game_code="APAE") == "Pokemon"
    assert rom_cleaner.detect_franchise("New Super Mario Bros") == "Mario"
    assert rom_cleaner.detect_franchise("Random Puzzle Game") is None


def test_normalize_layout():
    assert rom_cleaner.normalize_layout(None) == "console"
    assert rom_cleaner.normalize_layout("both") == "both"
    assert rom_cleaner.normalize_layout("franquia") == "franchise"
    assert rom_cleaner.normalize_layout("nope") is None


def test_layout_franchise(fake_sd):
    make_nds(
        fake_sd / "Pearl.nds",
        title=b"POKEMON P",
        code=b"APAE",
        maker=b"01",
    )
    make_nds(
        fake_sd / "Kart.nds",
        title=b"MARIOKARTDS",
        code=b"AMCE",
        maker=b"01",
    )
    ok, _ = rom_cleaner.organize_roms_directory(str(fake_sd), layout="franchise")
    assert ok
    assert list((fake_sd / "roms" / "Pokemon").glob("*.nds"))
    assert list((fake_sd / "roms" / "Mario").glob("*.nds"))
    assert not (fake_sd / "roms" / "nds").exists() or not list(
        (fake_sd / "roms" / "nds").glob("*.nds")
    )


def test_layout_both_console_then_franchise(fake_sd):
    make_nds(
        fake_sd / "Pearl.nds",
        title=b"POKEMON P",
        code=b"APAE",
        maker=b"01",
    )
    (fake_sd / "Pearl.sav").write_bytes(b"save")
    (fake_sd / "Other.gba").write_bytes(b"GBA" + b"\x00" * 64)
    ok, _ = rom_cleaner.organize_roms_directory(str(fake_sd), layout="both")
    assert ok
    pearl = list((fake_sd / "roms" / "nds" / "Pokemon").glob("*.nds"))
    assert pearl
    assert list((fake_sd / "roms" / "nds" / "Pokemon").glob("*.sav"))
    # GBA sem franquia reconhecida → flat em /roms/gba/
    assert list((fake_sd / "roms" / "gba").glob("*.gba"))


def test_layout_franchise_unknown_goes_to_outros(fake_sd):
    make_nds(
        fake_sd / "Obscure.nds",
        title=b"OBSCURE",
        code=b"ZZZZ",
        maker=b"01",
    )
    ok, _ = rom_cleaner.organize_roms_directory(str(fake_sd), layout="franchise")
    assert ok
    assert list((fake_sd / "roms" / "Outros").glob("*.nds"))


def test_apps_ignore_franchise_layout(fake_sd):
    make_nds(fake_sd / "MyTool.nds", title=b"HOMEBREW", code=b"####", maker=b"00")
    ok, _ = rom_cleaner.organize_roms_directory(str(fake_sd), layout="both")
    assert ok
    assert list((fake_sd / "roms" / "apps").glob("*.nds"))


def test_invalid_layout_rejected(fake_sd):
    ok, msg = rom_cleaner.organize_roms_directory(str(fake_sd), layout="nope")
    assert not ok
    assert "inválido" in msg.lower() or "invalid" in msg.lower()


def test_gameyob_states_and_gb_roms_follow(fake_sd):
    """GameYob: .gb/.gbc + .sav/.yss/.ys0/.cht vão juntos para /roms/gb|gbc/."""
    (fake_sd / "Zelda DX.gbc").write_bytes(b"GBC" + b"\x00" * 64)
    (fake_sd / "Zelda DX.sav").write_bytes(b"sram")
    (fake_sd / "Zelda DX.yss").write_bytes(b"state")
    (fake_sd / "Zelda DX.ys0").write_bytes(b"slot0")
    (fake_sd / "Zelda DX.cht").write_bytes(b"cheats")
    (fake_sd / "Tetris.gb").write_bytes(b"GB" + b"\x00" * 32)

    ok, _ = rom_cleaner.organize_roms_directory(str(fake_sd))
    assert ok
    gbc = fake_sd / "roms" / "gbc"
    gb = fake_sd / "roms" / "gb"
    assert list(gbc.glob("*.gbc"))
    assert list(gbc.glob("*.sav"))
    assert list(gbc.glob("*.yss"))
    assert list(gbc.glob("*.ys0"))
    assert list(gbc.glob("*.cht"))
    assert list(gb.glob("*.gb"))


def test_s8ds_double_ext_save_follows(fake_sd):
    """S8DS: Sonic.gg.sav acompanha Sonic.gg."""
    (fake_sd / "Sonic.gg").write_bytes(b"GG" + b"\x00" * 32)
    (fake_sd / "Sonic.gg.sav").write_bytes(b"save")
    ok, _ = rom_cleaner.organize_roms_directory(str(fake_sd))
    assert ok
    gg = fake_sd / "roms" / "gg"
    assert list(gg.glob("*.gg"))
    assert any(p.name.endswith(".gg.sav") or p.suffix == ".sav" for p in gg.iterdir())


def test_pce_goes_to_tg16(fake_sd):
    (fake_sd / "Bonk.pce").write_bytes(b"PCE" + b"\x00" * 32)
    ok, _ = rom_cleaner.organize_roms_directory(str(fake_sd))
    assert ok
    assert list((fake_sd / "roms" / "tg16").glob("*.pce"))


def test_ensure_twilight_rom_folders_creates_vc_set(fake_sd):
    created = rom_cleaner.ensure_twilight_rom_folders(str(fake_sd))
    assert "gb" in created or (fake_sd / "roms" / "gb").is_dir()
    for name in ("nes", "snes", "tg16", "cpc", "col", "ws", "ngp", "a26"):
        assert (fake_sd / "roms" / name).is_dir(), name
    # Segunda chamada não falha
    rom_cleaner.ensure_twilight_rom_folders(str(fake_sd))


def test_companion_index_keys_s8ds():
    keys = dict(rom_cleaner.companion_index_keys("Sonic.gg.sav"))
    assert keys["sonic.gg"] == ".sav"
    assert keys["sonic"] == ".gg.sav"


def test_franchise_layout_prunes_empty_platform_folders(fake_sd):
    """Por franquia: cria /roms/Pokemon/ e remove pastas de consola vazias."""
    ensure = fake_sd / "roms"
    for name in ("nds", "gba", "a26", "nes"):
        (ensure / name).mkdir(parents=True, exist_ok=True)
    make_nds(
        fake_sd / "Pearl.nds",
        title=b"POKEMON P",
        code=b"APAE",
        maker=b"01",
    )
    ok, msg = rom_cleaner.organize_roms_directory(str(fake_sd), layout="franchise")
    assert ok
    assert list((fake_sd / "roms" / "Pokemon").glob("*.nds"))
    assert not (fake_sd / "roms" / "nds").exists()
    assert not (fake_sd / "roms" / "a26").exists()
    assert (fake_sd / "roms" / "apps").is_dir()
    assert "removida" in msg.lower() or "vazia" in msg.lower() or "organizados" in msg.lower()


def test_console_layout_keeps_canonical_empty_folders(fake_sd):
    """Por consola: pastas TWiLight vazias (sem jogos) mantêm-se."""
    make_nds(
        fake_sd / "Kart.nds",
        title=b"MARIOKARTDS",
        code=b"AMCE",
        maker=b"01",
    )
    ok, _ = rom_cleaner.organize_roms_directory(str(fake_sd), layout="console")
    assert ok
    assert list((fake_sd / "roms" / "nds").glob("*.nds"))
    assert (fake_sd / "roms" / "gba").is_dir()
    assert (fake_sd / "roms" / "nes").is_dir()


def test_both_layout_creates_nested_franchise_and_prunes_old(fake_sd):
    """Consola+franquia: /roms/nds/Pokemon/ e limpa pasta franquia solta vazia."""
    (fake_sd / "roms" / "Pokemon").mkdir(parents=True)
    make_nds(
        fake_sd / "roms" / "Pokemon" / "Pearl.nds",
        title=b"POKEMON P",
        code=b"APAE",
        maker=b"01",
    )
    # Pasta vazia residual
    (fake_sd / "roms" / "EmptyFranchise").mkdir(parents=True)
    ok, _ = rom_cleaner.organize_roms_directory(str(fake_sd), layout="both")
    assert ok
    assert list((fake_sd / "roms" / "nds" / "Pokemon").glob("*.nds"))
    assert not (fake_sd / "roms" / "Pokemon").exists()
    assert not (fake_sd / "roms" / "EmptyFranchise").exists()


def test_prune_empty_dirs_respects_skip(fake_sd):
    (fake_sd / "_nds" / "empty").mkdir(parents=True)
    (fake_sd / "roms" / "leftover").mkdir(parents=True)
    n = rom_cleaner.prune_empty_dirs(str(fake_sd), layout="franchise")
    assert n >= 1
    assert (fake_sd / "_nds" / "empty").is_dir()
    assert not (fake_sd / "roms" / "leftover").exists()
