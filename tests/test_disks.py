import os

import pytest

from core import disks


def test_macos_whole_disk_id():
    assert disks._macos_whole_disk_id("disk4") == "disk4"
    assert disks._macos_whole_disk_id("disk4s1") == "disk4"
    assert disks._macos_whole_disk_id("disk12s3") == "disk12"
    assert disks._macos_whole_disk_id("di") == ""
    assert disks._macos_whole_disk_id("disk4".split("s")[0]) == ""
    assert disks._macos_whole_disk_id("") == ""
    assert disks._macos_whole_disk_id(None) == ""


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


def test_target_cluster_constant():
    assert disks.TARGET_CLUSTER_BYTES == 32768


def test_get_cluster_size_missing_path():
    assert disks.get_cluster_size_bytes("") is None
    assert disks.get_cluster_size_bytes("/nonexistent/path/xyz") is None


def test_format_linux_cmd_includes_sectors(monkeypatch, tmp_path):
    """Garante que mkfs.vfat recebe -s 64 (32 KB)."""
    sd = tmp_path / "mnt"
    sd.mkdir()
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        class R:
            returncode = 0
            stderr = ""
            stdout = ""
        return R()

    monkeypatch.setattr(disks, "_resolve_linux_source", lambda p: "/dev/sdb1")
    monkeypatch.setattr(disks, "_unmount_linux", lambda m, d: (True, "ok"))
    monkeypatch.setattr(disks, "_linux_still_mounted", lambda p: False)
    monkeypatch.setattr(disks.shutil, "which", lambda n: "/usr/bin/mkfs.vfat" if "mkfs" in n else None)
    monkeypatch.setattr(disks.subprocess, "run", fake_run)
    monkeypatch.setattr(disks.sys, "platform", "linux")

    ok, msg = disks._format_sd_linux(str(sd), "DSI_SD", expected_device_id="/dev/sdb1")
    assert ok is True
    assert "-s" in captured["cmd"]
    assert "64" in captured["cmd"]
    assert "32 KB" in msg or "32768" in msg or "cluster" in msg.lower()


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
