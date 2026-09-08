"""Testes de boxart, cheats path helpers e relatório."""

import os

from core import boxart, sd_utils
from tests.conftest import make_nds


def test_tid_region_and_urls():
    assert boxart.tid_region("AMCE") == "US"
    assert boxart.tid_region("AMCP") == "EN"
    urls = boxart.boxart_urls_for_tid("AMCE")
    assert urls
    assert "AMCE.png" in urls[0]
    assert urls[0].startswith("https://art.gametdb.com/")


def test_boxart_scan_roms(fake_sd):
    nds = fake_sd / "roms" / "nds"
    nds.mkdir(parents=True)
    make_nds(nds / "Mario.nds", title=b"MARIOKART", code=b"AMCE", maker=b"01")
    tids = boxart._scan_rom_tids(str(fake_sd))
    assert tids
    assert tids[0][0] == "AMCE"


def test_copy_nand_backup(tmp_path, monkeypatch):
    sd = tmp_path / "SD"
    sd.mkdir()
    dt = sd / "DTAABBCC"
    dt.mkdir()
    (dt / "nand.bin").write_bytes(b"\x00" * (120 * 1024 * 1024))
    (dt / "nand.bin.sha1").write_text("deadbeef")

    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(sd_utils, "is_safe_mount_path", lambda p: True)
    # expanduser("~") uses HOME
    ok, msg = sd_utils.copy_nand_backup(str(sd))
    assert ok is True
    found = list(desktop.glob("NAND_DTAABBCC_*/nand.bin"))
    assert found
    assert found[0].stat().st_size >= 120 * 1024 * 1024


def test_install_cheats_from_downloads(tmp_path, monkeypatch):
    sd = tmp_path / "SD"
    sd.mkdir()
    (sd / "_nds" / "TWiLightMenu").mkdir(parents=True)
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    cheat = downloads / "usrcheat.dat"
    cheat.write_bytes(b"C" * (200 * 1024))

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(sd_utils, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr("core.sdio.sync_volume", lambda *a, **k: None)

    ok, msg = sd_utils.install_cheats(str(sd))
    assert ok is True
    dest = sd / "_nds" / "TWiLightMenu" / "extras" / "usrcheat.dat"
    assert dest.is_file()
    assert dest.stat().st_size >= 200 * 1024


def test_setup_godmode9i(tmp_path, monkeypatch, fake_cache):
    sd = tmp_path / "SD"
    sd.mkdir()
    src = fake_cache / "GodMode9i.dsi"
    payload = b"GM9I" + b"\x00" * 2048
    src.write_bytes(payload)
    digest = __import__("hashlib").sha256(payload).hexdigest()

    monkeypatch.setattr(sd_utils, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(sd_utils, "ensure_cached", lambda key, log_callback=None: str(src))
    monkeypatch.setitem(sd_utils.PINNED_SHA256, "godmode9i", digest)
    monkeypatch.setattr("core.sdio.sync_volume", lambda *a, **k: None)

    ok, msg = sd_utils.setup_godmode9i(str(sd))
    assert ok is True
    assert (sd / "roms" / "apps" / "GodMode9i.dsi").is_file()


def test_sd_report_logs(tmp_path, monkeypatch):
    sd = tmp_path / "SD"
    sd.mkdir()
    logs = []
    monkeypatch.setattr(sd_utils, "inspect_sd_card", lambda p: {
        "success": True,
        "name": "SD",
        "fs_type": "FAT32",
        "is_fat32": True,
        "total_size_gb": 8,
        "free_size_gb": 4,
        "has_twilight": True,
        "has_boot_nds": True,
        "has_dumptool": False,
        "has_unlaunch_installer": False,
        "has_dcim": False,
        "nand_dumps": [],
        "has_nand_dump": False,
        "roms_count": 3,
    })
    monkeypatch.setattr(sd_utils, "get_cluster_size_bytes", lambda p: 32768)
    ok, msg = sd_utils.format_sd_report(str(sd), log_callback=logs.append)
    assert ok is True
    assert any("32 KB" in m or "cluster" in m.lower() for m in logs)
