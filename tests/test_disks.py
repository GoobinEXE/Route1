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


def test_macos_newfs_needs_privilege():
    assert disks._macos_newfs_needs_privilege(
        1, "newfs_msdos: /dev/rdisk4s1: Permission denied", ""
    )
    assert disks._macos_newfs_needs_privilege(1, "Resource busy", "")
    assert not disks._macos_newfs_needs_privilege(1, "too few clusters for FAT32", "")
    assert not disks._macos_newfs_needs_privilege(0, "Permission denied", "")


class _Proc:
    def __init__(self, code=0, err="", out=""):
        self.returncode = code
        self.stderr = err
        self.stdout = out


def test_macos_force_cluster_retries_admin_on_permission(monkeypatch):
    term_calls = []

    monkeypatch.setattr(disks.subprocess, "run", lambda *a, **k: _Proc(0))
    monkeypatch.setattr(disks, "_macos_newfs_bin", lambda: "/sbin/newfs_msdos")
    monkeypatch.setattr(disks.os, "geteuid", lambda: 501)
    monkeypatch.setattr(
        disks,
        "_macos_terminal_newfs",
        lambda *a, **k: term_calls.append(a) or (True, ""),
    )
    monkeypatch.setattr(
        disks,
        "_macos_run_admin_shell",
        lambda sh: (_ for _ in ()).throw(AssertionError("não deve usar osascript")),
    )
    ok, err = disks._macos_force_cluster32("disk4", "disk4s1", "DSI_SD")
    assert ok is True
    assert err == ""
    assert term_calls


def test_macos_force_cluster_terminal_fallback_on_eperm(monkeypatch):
    """Mantido: euid!=0 usa Terminal directamente (sem osascript)."""
    term_calls = []

    monkeypatch.setattr(disks.subprocess, "run", lambda *a, **k: _Proc(0))
    monkeypatch.setattr(disks, "_macos_newfs_bin", lambda: "/sbin/newfs_msdos")
    monkeypatch.setattr(disks.os, "geteuid", lambda: 501)
    monkeypatch.setattr(
        disks,
        "_macos_terminal_newfs",
        lambda *a, **k: term_calls.append(a) or (True, ""),
    )
    ok, err = disks._macos_force_cluster32("disk4", "disk4s1", "DSI_SD")
    assert ok is True
    assert term_calls


def test_macos_admin_shell_uses_disk_c64():
    sh = disks._macos_admin_newfs_shell(
        "/sbin/newfs_msdos", "DSI_SD", "disk4", "disk4s1"
    )
    assert "-c 64" in sh
    assert "/dev/disk4s1" in sh
    assert "unmountDisk force /dev/disk4" in sh
    ok, _ = disks._macos_force_cluster32("disk4;rm", "disk4s1", "DSI_SD")
    assert ok is False
    ok, _ = disks._macos_force_cluster32("disk4", "disk5s1", "DSI_SD")
    assert ok is False


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
