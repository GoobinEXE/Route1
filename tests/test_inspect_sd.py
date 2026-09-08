"""Testes de inspeção somente-leitura do cartão."""

import os

import app as app_mod
from core import inspect_sd


def test_inspect_finds_dt_nand(tmp_path, monkeypatch):
    sd = tmp_path / "SD"
    sd.mkdir()
    dt = sd / "DT010203040A0B0C0D"
    dt.mkdir()
    nand = dt / "nand.bin"
    nand.write_bytes(b"\x00" * (120 * 1024 * 1024))
    (dt / "nand.bin.sha1").write_text("abc")

    monkeypatch.setattr(inspect_sd, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(
        inspect_sd,
        "get_mounted_drives",
        lambda: [
            {
                "mount_path": str(sd),
                "name": "SD",
                "fs_type": "FAT32",
                "total_size_gb": 8,
                "free_size_gb": 4,
                "is_removable": True,
            }
        ],
    )
    monkeypatch.setattr(inspect_sd, "_twilight_present", lambda p: False)

    res = inspect_sd.inspect_sd_card(str(sd))
    assert res["success"] is True
    assert res["is_fat32"] is True
    assert res["has_nand_dump"] is True
    assert res["nand_dumps"][0]["folder"].startswith("DT")
    assert res["nand_dumps"][0]["rel_path"].endswith("/nand.bin")
    assert "path" not in res["nand_dumps"][0]
    assert res["nand_dumps"][0]["has_sha1"] is True
    assert res["has_dcim"] is False


def test_inspect_rejects_unsafe(monkeypatch):
    monkeypatch.setattr(inspect_sd, "is_safe_mount_path", lambda p: False)
    res = inspect_sd.inspect_sd_card("/tmp/not-a-drive")
    assert res["success"] is False


def test_quarantine_dcim(tmp_path, monkeypatch):
    sd = tmp_path / "SD"
    sd.mkdir()
    dcim = sd / "DCIM"
    dcim.mkdir()
    (dcim / "photo.jpg").write_bytes(b"x")

    monkeypatch.setattr("core.sdio.sync_volume", lambda *a, **k: None)
    ok, msg = inspect_sd.quarantine_dcim(str(sd))
    assert ok is True
    assert not (sd / "DCIM").exists()
    assert (sd / "DCIM_backup_1" / "photo.jpg").is_file()


def test_api_inspect_sd(monkeypatch, tmp_path):
    api = app_mod.Api()
    fake = tmp_path / "SD"
    fake.mkdir()
    monkeypatch.setattr(app_mod, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(
        app_mod,
        "inspect_sd_card",
        lambda p: {"success": True, "has_nand_dump": False, "mount_path": p},
    )
    res = api.inspect_sd(str(fake))
    assert res["success"] is True


def test_api_probe_kernels(monkeypatch):
    api = app_mod.Api()
    monkeypatch.setattr(
        app_mod,
        "probe_kernels",
        lambda: {"success": True, "gei": None, "r4": []},
    )
    res = api.probe_kernels()
    assert res["success"] is True
    assert res["r4"] == []
