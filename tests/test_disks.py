import os

import pytest

from core import disks


def test_format_rejects_bad_volume_name(monkeypatch):
    monkeypatch.setattr(disks, "resolve_safe_drive", lambda p: {"device_id": "disk2", "is_removable": True})
    ok, msg = disks.format_sd_card("/Volumes/SD", volume_name="bad name!")
    assert ok is False
    assert "inválido" in msg.lower() or "invalid" in msg.lower() or "Nome" in msg


def test_format_rejects_unsafe_path(monkeypatch):
    monkeypatch.setattr(disks, "resolve_safe_drive", lambda p: None)
    ok, msg = disks.format_sd_card("/")
    assert ok is False


def test_windows_letter_validation(monkeypatch):
    ok, msg = disks._format_sd_windows("C:\\", "DSI_SD", expected_device_id="C:")
    assert ok is False
    assert "recusada" in msg.lower() or "inválida" in msg.lower() or "C" in msg


def test_is_safe_requires_removable(monkeypatch):
    monkeypatch.setattr(
        disks,
        "get_mounted_drives",
        lambda: [
            {
                "mount_path": "/Volumes/Data",
                "is_removable": False,
                "device_id": "disk9",
            }
        ],
    )
    assert disks.is_safe_mount_path("/Volumes/Data") is False


def test_resolve_safe_drive_match(monkeypatch, tmp_path):
    sd = tmp_path / "SD"
    sd.mkdir()
    monkeypatch.setattr(
        disks,
        "get_mounted_drives",
        lambda: [
            {
                "mount_path": str(sd),
                "is_removable": True,
                "device_id": "disk3s1",
                "fs_type": "FAT32",
            }
        ],
    )
    d = disks.resolve_safe_drive(str(sd))
    assert d is not None
    assert d["device_id"] == "disk3s1"
