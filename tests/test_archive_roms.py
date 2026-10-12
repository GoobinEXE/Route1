"""Testes de extracção segura de ROMs a partir de arquivos."""

from __future__ import annotations

import zipfile
from pathlib import Path

from core import archive_roms, dspico
from tests.conftest import make_nds


def test_expand_zip_with_rom(tmp_path):
    rom = tmp_path / "Kart.nds"
    make_nds(str(rom), title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")
    zpath = tmp_path / "pack.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.write(rom, arcname="Kart.nds")
        zf.writestr("readme.txt", "ignore me")

    paths, errors, stats = archive_roms.expand_rom_sources(
        [str(zpath)], {".nds", ".dsi", ".ids"}
    )
    try:
        assert stats["archives"] == 1
        assert stats["extracted_roms"] >= 1
        assert len(paths) == 1
        assert paths[0].endswith("Kart.nds")
        assert Path(paths[0]).is_file()
    finally:
        archive_roms.cleanup_expand_staging(stats)


def test_expand_rejects_zip_slip(tmp_path):
    zpath = tmp_path / "evil.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("../escape.nds", b"x" * 100)

    paths, errors, stats = archive_roms.expand_rom_sources(
        [str(zpath)], {".nds"}
    )
    try:
        assert paths == []
        assert errors
        assert any("inseguro" in e.lower() or "rejeitado" in e.lower() for e in errors)
    finally:
        archive_roms.cleanup_expand_staging(stats)


def test_expand_direct_rom_and_multi(tmp_path):
    a = tmp_path / "A.nds"
    b = tmp_path / "B.nds"
    make_nds(str(a), title=b"GAMEAAAAAA", code=b"AAAA", maker=b"01")
    make_nds(str(b), title=b"GAMEBBBBBB", code=b"BBBB", maker=b"01")
    paths, errors, stats = archive_roms.expand_rom_sources(
        [str(a), str(b)], {".nds"}
    )
    try:
        assert stats["direct"] == 2
        assert len(paths) == 2
        assert not errors
    finally:
        archive_roms.cleanup_expand_staging(stats)


def test_import_dspico_from_zip(fake_sd, tmp_path, monkeypatch):
    games = fake_sd / "Games"
    games.mkdir(exist_ok=True)
    (fake_sd / "_picoboot.nds").write_bytes(b"x")

    rom = tmp_path / "Kart.nds"
    make_nds(str(rom), title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")
    zpath = tmp_path / "games.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.write(rom, arcname="subdir/Kart.nds")

    monkeypatch.setattr(dspico, "sync_volume", lambda *a, **k: None)
    # is_safe_mount_path may reject tmp fake_sd — force OK for import path checks
    monkeypatch.setattr(
        "core.disks.is_safe_mount_path", lambda p: True, raising=False
    )

    ok, msg, stats = dspico.import_dspico_games(
        str(fake_sd), [str(zpath)], dest_rel_dir=""
    )
    assert ok, msg
    assert stats.get("copied") == 1
    assert stats.get("archives") == 1
    assert (fake_sd / "Games" / "Kart.nds").is_file()


def test_expand_unsupported_inside_zip(tmp_path):
    zpath = tmp_path / "empty.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("notes.txt", "no roms")

    paths, errors, stats = archive_roms.expand_rom_sources(
        [str(zpath)], {".nds"}
    )
    try:
        assert paths == []
        assert any("Sem ROMs" in e for e in errors)
    finally:
        archive_roms.cleanup_expand_staging(stats)


def test_import_dspico_gba_to_games_and_progress(fake_sd, tmp_path, monkeypatch):
    games = fake_sd / "Games"
    games.mkdir(exist_ok=True)
    (fake_sd / "_picoboot.nds").write_bytes(b"x")

    gba = tmp_path / "Zelda.gba"
    gba.write_bytes(b"GBA" + b"\x00" * 200)
    nds = tmp_path / "Kart.nds"
    make_nds(str(nds), title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")

    events = []
    monkeypatch.setattr(dspico, "sync_volume", lambda *a, **k: None)
    monkeypatch.setattr(
        dspico, "_emit_import_progress", lambda p: events.append(p)
    )

    ok, msg, stats = dspico.import_dspico_games(
        str(fake_sd), [str(gba), str(nds)], dest_rel_dir=""
    )
    assert ok, msg
    assert stats.get("copied") == 2
    assert stats.get("games") == 1
    assert stats.get("retro") == 1
    assert (fake_sd / "Games" / "Kart.nds").is_file()
    assert (fake_sd / "Games" / "Zelda.gba").is_file()
    assert not (fake_sd / "ROMs" / "GBA" / "Zelda.gba").exists()
    assert events
    assert events[-1].get("done") is True
    assert events[-1].get("op") == "dspico_import_games"
