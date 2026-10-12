"""Testes do catálogo e instalação de emuladores DSPico / Pico-Launcher."""

from __future__ import annotations

import json
import os
import zipfile

import pytest

from core import dspico, dspico_emulators
from core.cache import DSPICO_EMU_CACHE_KEYS, PINNED_SHA256


def _minimal_dspico_sd(root):
    (root / "_picoboot.nds").write_bytes(b"NDS")
    pico = root / "_pico"
    pico.mkdir()
    (pico / "picoLoader7.bin").write_bytes(b"7")
    (pico / "picoLoader9.bin").write_bytes(b"9")
    (pico / "aplist.bin").write_bytes(b"a")
    (pico / "savelist.bin").write_bytes(b"s")
    (root / "Games").mkdir()


def test_list_emulators_all_available():
    data = dspico_emulators.list_emulators()
    assert data["success"] is True
    emus = data["emulators"]
    assert len(emus) >= 18
    assert all(e["available"] for e in emus)
    assert all(e.get("installed") is False for e in emus)
    ids = {e["id"] for e in emus}
    assert "gbarunner3" in ids
    assert "gameyob" in ids
    assert "snemulds_06a" in ids
    assert "neods" in ids


def test_list_emulators_marks_installed(tmp_path):
    _minimal_dspico_sd(tmp_path)
    emu_dir = tmp_path / "_pico" / "emulators"
    emu_dir.mkdir(parents=True)
    (emu_dir / "gameyob.nds").write_bytes(b"GY")

    data = dspico_emulators.list_emulators(str(tmp_path))
    assert data["success"] is True
    by_id = {e["id"]: e for e in data["emulators"]}
    assert by_id["gameyob"]["installed"] is True
    assert by_id["gbarunner3"]["installed"] is False


def test_emu_cache_keys_pinned():
    assert "emu_gbarunner3" in DSPICO_EMU_CACHE_KEYS
    for key in DSPICO_EMU_CACHE_KEYS:
        assert key in PINNED_SHA256
        assert len(PINNED_SHA256[key]) == 64


def test_install_requires_pico(tmp_path):
    ok, msg, _ = dspico_emulators.install_dspico_emulators(
        str(tmp_path), ["nesds"]
    )
    assert ok is False
    assert "_pico" in msg


def test_install_unknown_id(tmp_path):
    _minimal_dspico_sd(tmp_path)
    ok, msg, _ = dspico_emulators.install_dspico_emulators(
        str(tmp_path), ["not_a_real_emu"]
    )
    assert ok is False
    assert "desconhecido" in msg.lower()


def test_install_nesds_with_fake_cache(tmp_path, monkeypatch):
    _minimal_dspico_sd(tmp_path)
    fake = tmp_path / "nesDS.nds"
    fake.write_bytes(b"NESDSROM")

    def fake_cached(key, log_callback=None):
        assert key == "emu_nesds"
        return str(fake)

    monkeypatch.setattr(dspico_emulators, "ensure_cached", fake_cached)
    monkeypatch.setattr(dspico_emulators, "sync_volume", lambda *_a, **_k: None)

    ok, msg, details = dspico_emulators.install_dspico_emulators(
        str(tmp_path), ["nesds"]
    )
    assert ok, msg
    dest = tmp_path / "_pico" / "emulators" / "nesDS.nds"
    assert dest.read_bytes() == b"NESDSROM"
    assert (tmp_path / "ROMs" / "NES").is_dir()
    settings = json.loads((tmp_path / "_pico" / "settings.json").read_text())
    assert settings["fileAssociations"]["nes"]["appPath"] == (
        "/_pico/emulators/nesDS.nds"
    )
    assert "nesds" in details.get("installed", [])


def test_gba_conflict_prefers_gbarunner3(tmp_path, monkeypatch):
    _minimal_dspico_sd(tmp_path)
    g3 = tmp_path / "g3.zip"
    with zipfile.ZipFile(g3, "w") as zf:
        zf.writestr("GBARunner3.nds", b"GBA3")
        zf.writestr("_gba/configs/x.json", "{}")
    g2 = tmp_path / "g2.nds"
    g2.write_bytes(b"GBA2")

    def fake_cached(key, log_callback=None):
        if key == "emu_gbarunner3":
            return str(g3)
        if key == "emu_gbarunner2":
            return str(g2)
        raise AssertionError(key)

    monkeypatch.setattr(dspico_emulators, "ensure_cached", fake_cached)
    monkeypatch.setattr(dspico_emulators, "sync_volume", lambda *_a, **_k: None)

    ok, msg, details = dspico_emulators.install_dspico_emulators(
        str(tmp_path), ["gbarunner2", "gbarunner3"]
    )
    assert ok, msg
    assert (tmp_path / "_pico" / "emulators" / "GBARunner3.nds").is_file()
    assert (
        tmp_path / "_pico" / "emulators" / "GBARunner2_arm9dldi_ds.nds"
    ).is_file()
    settings = json.loads((tmp_path / "_pico" / "settings.json").read_text())
    assert settings["fileAssociations"]["gba"]["appPath"].endswith(
        "GBARunner3.nds"
    )
    assert (tmp_path / "_gba" / "configs" / "x.json").is_file()
    assert (tmp_path / "ROMs" / "GBA").is_dir()


def test_install_gameyob_zip(tmp_path, monkeypatch):
    _minimal_dspico_sd(tmp_path)
    zpath = tmp_path / "gameyob.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("gameyob.nds", b"GY")
        zf.writestr("README.txt", "x")

    monkeypatch.setattr(
        dspico_emulators,
        "ensure_cached",
        lambda key, log_callback=None: str(zpath),
    )
    monkeypatch.setattr(dspico_emulators, "sync_volume", lambda *_a, **_k: None)

    ok, msg, details = dspico_emulators.install_dspico_emulators(
        str(tmp_path), ["gameyob"]
    )
    assert ok, msg
    assert (tmp_path / "_pico" / "emulators" / "gameyob.nds").read_bytes() == b"GY"
    settings = json.loads((tmp_path / "_pico" / "settings.json").read_text())
    assert "gb" in settings["fileAssociations"]
    assert "gbc" in settings["fileAssociations"]


def test_snemulds_patches_rompath(tmp_path, monkeypatch):
    _minimal_dspico_sd(tmp_path)
    zpath = tmp_path / "snem.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("SNEmulDS.nds", b"SNES")
        zf.writestr("snemul.cfg", "ROMPath = /SNES\nSomething = 1\n")

    monkeypatch.setattr(
        dspico_emulators,
        "ensure_cached",
        lambda key, log_callback=None: str(zpath),
    )
    monkeypatch.setattr(dspico_emulators, "sync_volume", lambda *_a, **_k: None)

    ok, msg, _ = dspico_emulators.install_dspico_emulators(
        str(tmp_path), ["snemulds_06a"]
    )
    assert ok, msg
    assert (tmp_path / "Emulators" / "SNEmulDS.nds").is_file()
    cfg = (tmp_path / "snemul.cfg").read_text()
    assert "ROMPath = /ROMs/SNES" in cfg
    settings = json.loads((tmp_path / "_pico" / "settings.json").read_text())
    # manual — sem associações sfc/smc
    assert "sfc" not in (settings.get("fileAssociations") or {})


def test_organize_preserves_emulators_migrates_retro(tmp_path):
    _minimal_dspico_sd(tmp_path)
    (tmp_path / "ROMs" / "GBA").mkdir(parents=True)
    (tmp_path / "ROMs" / "GBA" / "game.gba").write_bytes(b"GBA")
    (tmp_path / "ROMs" / "BIOS").mkdir(parents=True)
    (tmp_path / "ROMs" / "BIOS" / "optional.rom").write_bytes(b"BIOSROM")
    (tmp_path / "_gba").mkdir()
    (tmp_path / "_gba" / "bios.bin").write_bytes(b"BIOS")
    (tmp_path / "Emulators").mkdir()
    (tmp_path / "Emulators" / "SNEmulDS.nds").write_bytes(b"EMU")
    (tmp_path / "_pico" / "emulators").mkdir()
    (tmp_path / "_pico" / "emulators" / "nesDS.nds").write_bytes(b"NES")
    (tmp_path / "snemul.cfg").write_text("ROMPath = /ROMs/SNES\n")
    (tmp_path / "foreign_twl").mkdir()
    (tmp_path / "foreign_twl" / "x.txt").write_text("x")

    ok, msg, stats = dspico.organize_dspico_sd(str(tmp_path), layout="games")
    assert ok, msg
    # Retro migra para Games/; BIOS em ROMs/ preservado
    assert (tmp_path / "Games" / "game.gba").is_file()
    assert (tmp_path / "ROMs" / "BIOS" / "optional.rom").is_file()
    assert (tmp_path / "_gba" / "bios.bin").is_file()
    assert (tmp_path / "Emulators" / "SNEmulDS.nds").is_file()
    assert (tmp_path / "_pico" / "emulators" / "nesDS.nds").is_file()
    assert (tmp_path / "snemul.cfg").is_file()
    assert not (tmp_path / "foreign_twl").exists()


def test_inspect_includes_emulators(tmp_path):
    _minimal_dspico_sd(tmp_path)
    (tmp_path / "_pico" / "emulators").mkdir()
    (tmp_path / "_pico" / "emulators" / "nesDS.nds").write_bytes(b"N")
    res = dspico.inspect_dspico(str(tmp_path))
    assert res["success"]
    assert res["emulators"]["argv_nds"] == 1
    ids = {c["id"] for c in res["checklist"]}
    assert "emulators" in ids


def test_patch_snemul_cfg_helper():
    out = dspico_emulators._patch_snemul_cfg_text("ROMPath = /SNES\nFoo=1\n")
    assert "ROMPath = /ROMs/SNES" in out
    assert "Foo=1" in out


def test_retro_platform_map_covers_all_catalog_associations():
    plat = dspico_emulators.retro_platform_map()
    missing = []
    for entry in dspico_emulators.EMULATOR_CATALOG:
        for assoc in (entry.get("associations") or {}):
            key = f".{(assoc or '').strip().lower().lstrip('.')}"
            if key not in plat:
                missing.append(f"{entry['id']}:{key}")
    assert not missing, f"Associações sem pasta Games/: {missing}"
    assert plat[".sfc"] == "snes"
    assert plat[".neo"] == "neogeo"
    assert plat[".a26"] == "2600"
    assert plat[".int"] == "int"
    assert plat[".car"] == "800"


def test_dspico_rom_picker_includes_emulator_exts():
    labels = dspico_emulators.dspico_rom_picker_filter_labels()
    blob = " ".join(labels)
    for ext in ("gba", "nes", "gen", "a26", "int", "col", "neo", "sfc", "zip"):
        assert f"*.{ext}" in blob


def test_organize_all_emulator_roms_by_platform(tmp_path):
    _minimal_dspico_sd(tmp_path)
    samples = {
        "ROMs/GBA/Zelda.gba": "gba",
        "ROMs/NES/Mega.nes": "nes",
        "ROMs/Genesis/Sonic.gen": "genesis",
        "ROMs/2600/Pitfall.a26": "2600",
        "ROMs/800/Basic.car": "800",
        "ROMs/INTV/Astrosmash.int": "int",
        "ROMs/Coleco/Donkey.col": "coleco",
        "ROMs/SNES/Mario.sfc": "snes",
        "ROMs/NeoGeo/Metal.neo": "neogeo",
        "ROMs/SMS/Alex.sms": "sms",
        "ROMs/GG/Sonic.gg": "gg",
        "ROMs/NGPocket/Puzzle.ngp": "ngp",
        "ROMs/TurboGrafx/Bonk.pce": "pce",
    }
    bios = tmp_path / "ROMs" / "BIOS"
    bios.mkdir(parents=True)
    (bios / "ngp-color-bios.ngp").write_bytes(b"BIOSNGP")
    (bios / "coleco.rom").write_bytes(b"BIOSCOL")

    for rel, _plat in samples.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"ROM" + rel.encode()[:20])

    ok, msg, stats = dspico.organize_dspico_sd(str(tmp_path), layout="platform")
    assert ok, msg
    assert stats.get("retro", 0) >= len(samples)
    for rel, plat in samples.items():
        name = os.path.basename(rel)
        assert (tmp_path / "Games" / plat / name).is_file(), name
        assert not (tmp_path / rel).exists(), rel
    # BIOS com extensão de jogo não migra
    assert (bios / "ngp-color-bios.ngp").is_file()
    assert (bios / "coleco.rom").is_file()
