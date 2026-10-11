"""Testes do pacote DSPico (markers, Games/, settings, emunand, UF2)."""

from __future__ import annotations

import json
import os
import zipfile

import pytest

from core import dspico
from core.cache import DSPICO_CACHE_KEYS, dspico_firmware_uf2_ready


def test_dspico_markers_ok(tmp_path):
    assert dspico.dspico_markers_ok(str(tmp_path)) is False
    (tmp_path / "_picoboot.nds").write_bytes(b"NDS")
    pico = tmp_path / "_pico"
    pico.mkdir()
    (pico / "picoLoader7.bin").write_bytes(b"7")
    (pico / "picoLoader9.bin").write_bytes(b"9")
    assert dspico.dspico_markers_ok(str(tmp_path)) is True


def test_assemble_dspico_staging(tmp_path):
    launcher = tmp_path / "launcher"
    loader = tmp_path / "loader"
    launcher.mkdir()
    loader.mkdir()
    (launcher / "LAUNCHER.nds").write_bytes(b"LAUNCH")
    pico = launcher / "_pico"
    pico.mkdir()
    (pico / "themes").mkdir()
    (pico / "themes" / "x.txt").write_text("t")
    (loader / "picoLoader7.bin").write_bytes(b"7")
    (loader / "picoLoader9_DSPICO.bin").write_bytes(b"9")
    (loader / "aplist.bin").write_bytes(b"a")
    (loader / "savelist.bin").write_bytes(b"s")

    staging = tmp_path / "out"
    dspico._assemble_dspico_staging(str(launcher), str(loader), str(staging))
    assert dspico.dspico_markers_ok(str(staging))
    assert (staging / "Games").is_dir()
    assert (staging / "_pico" / "picoLoader9.bin").read_bytes() == b"9"


def test_extract_zip_rejects_slip(tmp_path, monkeypatch):
    monkeypatch.setattr(dspico, "CACHE_DIR", str(tmp_path / "cache"))
    os.makedirs(dspico.CACHE_DIR, exist_ok=True)
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("../escape.txt", "nope")
    with pytest.raises(RuntimeError, match="inseguro"):
        dspico._extract_zip_safe(str(evil), str(tmp_path / "out"))


def test_official_links_only_lnh():
    links = dspico.official_links()
    assert links
    assert links.get("dspico_user_manual") == dspico.DSPICO_USER_MANUAL_URL
    for key, url in links.items():
        if key == "dspico_user_manual":
            assert url == (
                "https://www.chiscart.com/manuals/"
                "DS_Pico_user_manual_87a632eec6.pdf"
            )
            continue
        assert url.startswith("https://github.com/LNH-team/")


def test_cache_keys_allowlist():
    assert "pico_launcher" in DSPICO_CACHE_KEYS
    assert "pico_loader_dspico" in DSPICO_CACHE_KEYS
    assert "dspico_firmware_uf2" in DSPICO_CACHE_KEYS
    # Sem pin actual → UF2 não ready
    assert dspico_firmware_uf2_ready() is False


def test_assert_dspico_cache_key():
    dspico.assert_dspico_cache_key("pico_launcher")
    with pytest.raises(ValueError, match="allowlisted"):
        dspico.assert_dspico_cache_key("twilight_7z")


def _minimal_dspico_sd(root):
    (root / "_picoboot.nds").write_bytes(b"NDS")
    pico = root / "_pico"
    pico.mkdir()
    (pico / "picoLoader7.bin").write_bytes(b"7")
    (pico / "picoLoader9.bin").write_bytes(b"9")
    (pico / "aplist.bin").write_bytes(b"a")
    (pico / "savelist.bin").write_bytes(b"s")
    (root / "Games").mkdir()


def test_inspect_dspico(tmp_path):
    _minimal_dspico_sd(tmp_path)
    res = dspico.inspect_dspico(str(tmp_path))
    assert res["success"] is True
    assert res["markers_ok"] is True
    assert res["games_count"] == 0
    assert res["firmware_uf2_ready"] is False
    assert "pico_launcher" in (res.get("official_links") or {})


def test_resolve_under_games_rejects_traversal(tmp_path):
    _minimal_dspico_sd(tmp_path)
    assert dspico._resolve_under_games(str(tmp_path), "../_picoboot.nds") is None
    assert dspico._resolve_under_games(str(tmp_path), "a/../../etc/passwd") is None
    ok = dspico._resolve_under_games(str(tmp_path), "")
    assert ok is not None
    assert os.path.basename(ok) == "Games"


def test_browse_import_delete_games(tmp_path):
    _minimal_dspico_sd(tmp_path)
    src = tmp_path / "host"
    src.mkdir()
    rom = src / "Kart.nds"
    rom.write_bytes(b"ROMDATA")

    ok, msg, stats = dspico.import_dspico_games(
        str(tmp_path), [str(rom)], dest_rel_dir=""
    )
    assert ok, msg
    assert stats.get("copied") == 1
    root = dspico.browse_dspico_games(str(tmp_path), "")
    assert root["success"]
    assert root.get("area") == "root"
    assert {d.get("name") for d in root.get("dirs") or []} >= {"Games", "ROMs"}

    browse = dspico.browse_dspico_games(str(tmp_path), "Games")
    assert browse["success"]
    assert browse.get("area") == "games"
    assert any(f.get("name") == "Kart.nds" for f in browse.get("files") or [])

    ok, msg, stats = dspico.delete_dspico_games(
        str(tmp_path), ["Kart.nds"]
    )
    assert ok, msg
    assert stats.get("removed") == 1


def test_browse_lists_retro_roms(tmp_path):
    _minimal_dspico_sd(tmp_path)
    gb = tmp_path / "ROMs" / "GB"
    gb.mkdir(parents=True)
    (gb / "Tetris.gb").write_bytes(b"GBROM")
    (tmp_path / "ROMs" / "GBA").mkdir(parents=True)
    (tmp_path / "ROMs" / "GBA" / "Zelda.gba").write_bytes(b"GBAROM")

    roms = dspico.browse_dspico_games(str(tmp_path), "ROMs")
    assert roms["success"]
    assert roms.get("area") == "roms"
    dir_names = {d.get("name") for d in roms.get("dirs") or []}
    assert "GB" in dir_names
    assert "GBA" in dir_names

    gb_list = dspico.browse_dspico_games(str(tmp_path), "ROMs/GB")
    assert gb_list["success"]
    files = gb_list.get("files") or []
    assert any(f.get("name") == "Tetris.gb" for f in files)
    tetris = next(f for f in files if f.get("name") == "Tetris.gb")
    assert tetris.get("area") == "roms"
    assert tetris.get("rel_path") == "ROMs/GB/Tetris.gb"
    assert tetris.get("platform") == "gb"


def test_mkdir_and_move_games(tmp_path):
    _minimal_dspico_sd(tmp_path)
    ok, msg, stats = dspico.mkdir_dspico_games(str(tmp_path), "", "NDS")
    assert ok, msg
    rom = tmp_path / "Games" / "A.nds"
    rom.write_bytes(b"x")
    ok, msg, stats = dspico.move_dspico_games(
        str(tmp_path), ["A.nds"], dest_rel_dir="NDS"
    )
    assert ok, msg
    assert (tmp_path / "Games" / "NDS" / "A.nds").is_file()


def test_emunand_skeleton(tmp_path):
    _minimal_dspico_sd(tmp_path)
    ok, msg, stats = dspico.ensure_emunand_skeleton(str(tmp_path))
    assert ok, msg
    assert (tmp_path / "photo").is_dir()
    assert (tmp_path / "shared2" / "0000").is_dir()
    assert (tmp_path / "sys").is_dir()


def test_import_bios_and_font(tmp_path):
    _minimal_dspico_sd(tmp_path)
    bios = tmp_path / "biosnds7.rom"
    bios.write_bytes(b"B" * 64)
    ok, msg = dspico.import_biosnds7(str(tmp_path), str(bios))
    assert ok, msg
    assert (tmp_path / "_pico" / "biosnds7.rom").read_bytes() == b"B" * 64

    font = tmp_path / "TWLFontTable.dat"
    font.write_bytes(b"F" * 32)
    ok, msg = dspico.import_twl_font(str(tmp_path), str(font))
    assert ok, msg
    assert (tmp_path / "sys" / "TWLFontTable.dat").is_file()


def test_settings_allowlist(tmp_path):
    _minimal_dspico_sd(tmp_path)
    ok, msg = dspico.set_dspico_settings(
        str(tmp_path),
        {
            "theme": "raspberry",
            "romBrowserLayout": "Coverflow",
            "romBrowserSortMode": "NameAscending",
            "language": "english",
        },
    )
    assert ok, msg
    got = dspico.get_dspico_settings(str(tmp_path))
    assert got["success"]
    assert got["settings"]["theme"] == "raspberry"
    assert got["settings"]["romBrowserLayout"] == "Coverflow"

    ok, msg = dspico.set_dspico_settings(
        str(tmp_path), {"evilKey": "nope"}
    )
    assert ok is False
    assert "não permitida" in msg


def test_flash_refuses_without_pin(tmp_path):
    fake_rp2 = tmp_path / "RPI-RP2"
    fake_rp2.mkdir()
    (fake_rp2 / "INFO_UF2.TXT").write_text("UF2 Bootloader v1\n")
    ok, msg = dspico.flash_dspico_firmware(str(fake_rp2))
    assert ok is False
    assert "oficial" in msg.lower() or "LNH" in msg


def test_looks_like_rp2(tmp_path):
    vol = tmp_path / "RPI-RP2"
    vol.mkdir()
    (vol / "INFO_UF2.TXT").write_text("x")
    assert dspico.is_rp2_volume(str(vol)) is True
    other = tmp_path / "NOPE"
    other.mkdir()
    assert dspico.is_rp2_volume(str(other)) is False


def test_normalize_dspico_layout():
    assert dspico.normalize_dspico_layout(None) == dspico.LAYOUT_GAMES
    assert dspico.normalize_dspico_layout("franchise") == dspico.LAYOUT_FRANCHISE
    assert dspico.normalize_dspico_layout("console") == dspico.LAYOUT_PLATFORM
    assert dspico.normalize_dspico_layout("raiz") == dspico.LAYOUT_ROOT
    assert dspico.normalize_dspico_layout("nope") is None


def test_organize_dspico_removes_foreign_and_layouts(tmp_path):
    from tests.conftest import make_nds

    _minimal_dspico_sd(tmp_path)
    # Conteúdo de outros sistemas
    (tmp_path / "_nds").mkdir()
    (tmp_path / "_nds" / "TWiLightMenu").mkdir()
    (tmp_path / "roms").mkdir()
    (tmp_path / "MOONSHL").mkdir()
    (tmp_path / "boot.nds").write_bytes(b"BOOT")

    pearl = tmp_path / "roms" / "Pearl.nds"
    make_nds(str(pearl), title=b"POKEMON PEAR", code=b"APAE", maker=b"01")
    (tmp_path / "roms" / "Pearl.sav").write_bytes(b"SAVE")
    kart = tmp_path / "Games" / "Kart.nds"
    make_nds(str(kart), title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")

    ok, msg, stats = dspico.organize_dspico_sd(
        str(tmp_path), layout="franchise"
    )
    assert ok, msg
    assert not (tmp_path / "_nds").exists()
    # /roms/ é preservado (emuladores Pico usam /ROMs/); jogos NDS são resgatados
    assert not (tmp_path / "MOONSHL").exists()
    assert not (tmp_path / "boot.nds").exists()
    assert (tmp_path / "_picoboot.nds").is_file()
    assert (tmp_path / "_pico").is_dir()
    assert (tmp_path / "Games" / "Pokemon" / "Pokemon Pearl.nds").is_file() or (
        tmp_path / "Games" / "Pokemon"
    ).is_dir()
    # Save segue o jogo
    pokemon_dir = tmp_path / "Games" / "Pokemon"
    assert pokemon_dir.is_dir()
    savs = list(pokemon_dir.glob("*.sav"))
    assert savs, "save deveria acompanhar o jogo"
    assert stats.get("removed_foreign", 0) >= 2

    # Reorganizar soltos em Games/
    ok, msg, stats = dspico.organize_dspico_sd(str(tmp_path), layout="games")
    assert ok, msg
    flat = list((tmp_path / "Games").glob("*.nds"))
    assert len(flat) >= 2

    # Layout raiz
    ok, msg, stats = dspico.organize_dspico_sd(str(tmp_path), layout="root")
    assert ok, msg
    root_nds = [
        p
        for p in tmp_path.glob("*.nds")
        if p.name.lower() != "_picoboot.nds"
    ]
    assert len(root_nds) >= 2
    assert (tmp_path / "_picoboot.nds").is_file()


def test_organize_dspico_platform_layout(tmp_path):
    from tests.conftest import make_nds

    _minimal_dspico_sd(tmp_path)
    make_nds(
        str(tmp_path / "Games" / "Kart.nds"),
        title=b"MARIOKARTDS",
        code=b"AMCE",
        maker=b"01",
    )
    make_nds(
        str(tmp_path / "Games" / "Ware.dsi"),
        title=b"DSIWARE",
        code=b"KXXE",
        maker=b"01",
        unitcode=2,
    )
    ok, msg, stats = dspico.organize_dspico_sd(
        str(tmp_path), layout="platform"
    )
    assert ok, msg
    assert (tmp_path / "Games" / "nds").is_dir()
    assert any((tmp_path / "Games" / "nds").glob("*.nds"))
    assert (tmp_path / "Games" / "dsi").is_dir()
    assert any((tmp_path / "Games" / "dsi").glob("*.dsi"))


def test_organize_dspico_collects_retro_from_anywhere(tmp_path):
    _minimal_dspico_sd(tmp_path)
    # Retro fora de ROMs/ (e um já no sítio certo)
    (tmp_path / "Downloads").mkdir()
    (tmp_path / "Downloads" / "Tetris.gb").write_bytes(b"GBROM")
    (tmp_path / "Downloads" / "Tetris.sav").write_bytes(b"SAVE")
    (tmp_path / "Games" / "Zelda.gba").write_bytes(b"GBAROM")
    (tmp_path / "misc").mkdir()
    (tmp_path / "misc" / "Mario.sfc").write_bytes(b"SNESROM")
    already = tmp_path / "ROMs" / "GB"
    already.mkdir(parents=True)
    (already / "Kirby.gb").write_bytes(b"KIRBY")

    ok, msg, stats = dspico.organize_dspico_sd(str(tmp_path), layout="games")
    assert ok, msg
    assert (tmp_path / "ROMs" / "GB" / "Tetris.gb").is_file()
    assert (tmp_path / "ROMs" / "GB" / "Tetris.sav").is_file()
    assert (tmp_path / "ROMs" / "GBA" / "Zelda.gba").is_file()
    assert (tmp_path / "ROMs" / "SNES" / "Mario.sfc").is_file()
    assert (tmp_path / "ROMs" / "GB" / "Kirby.gb").is_file()
    assert not (tmp_path / "Games" / "Zelda.gba").exists()
    assert stats.get("retro", 0) >= 3


def test_find_duplicate_dspico_games(tmp_path):
    from tests.conftest import make_nds

    _minimal_dspico_sd(tmp_path)
    games = tmp_path / "Games"
    make_nds(str(games / "Kart.nds"), title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")
    make_nds(str(games / "Kart_2.nds"), title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")
    make_nds(str(games / "Other.nds"), title=b"OTHERGAME", code=b"ZZZZ", maker=b"01")

    data = dspico.find_duplicate_dspico_games(str(tmp_path))
    assert data["success"]
    assert data["count"] == 1
    assert data["groups"][0]["key"] == "tid:AMCE"
    assert len(data["groups"][0]["items"]) == 2


def test_dspico_import_conflict_skip_and_replace(tmp_path):
    from tests.conftest import make_nds

    _minimal_dspico_sd(tmp_path)
    games = tmp_path / "Games"
    make_nds(
        str(games / "Kart.nds"),
        title=b"MARIOKARTDS",
        code=b"AMCE",
        maker=b"01",
        payload=b"\x00" * 100,
    )
    src = tmp_path / "host" / "New.nds"
    src.parent.mkdir()
    make_nds(
        str(src),
        title=b"MARIOKARTDS",
        code=b"AMCE",
        maker=b"01",
        payload=b"\x22" * 2048,
    )

    check = dspico.check_dspico_import_conflicts(str(tmp_path), [str(src)])
    assert check["success"]
    assert check["has_conflicts"]
    cid = check["conflicts"][0]["conflict_id"]

    ok, msg, stats = dspico.import_dspico_games(
        str(tmp_path), [str(src)], conflict_resolutions={cid: "skip"}
    )
    assert ok, msg
    assert stats["copied"] == 0
    assert len(list(games.glob("*.nds"))) == 1

    ok, msg, stats = dspico.import_dspico_games(
        str(tmp_path), [str(src)], conflict_resolutions={cid: "replace"}
    )
    assert ok, msg
    assert stats["copied"] == 1
    assert stats.get("replaced", 0) >= 1
    files = list(games.glob("*.nds"))
    assert len(files) == 1
    assert files[0].stat().st_size > 0x200 + 100
