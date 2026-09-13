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


def test_macos_newfs_argv_32k():
    cmd = disks._macos_newfs_argv("/sbin/newfs_msdos", "DSI_SD", "/dev/rdisk4s1")
    assert cmd[cmd.index("-b") + 1] == "32768"
    assert cmd[cmd.index("-F") + 1] == "32"
    assert "-v" in cmd
    assert "DSI_SD" in cmd


def test_macos_newfs_needs_privilege():
    assert disks._macos_newfs_needs_privilege(
        1, "newfs_msdos: /dev/rdisk4s1: Permission denied", ""
    )
    assert disks._macos_newfs_needs_privilege(1, "Resource busy", "")
    assert disks._macos_newfs_needs_privilege(1, "Operation not permitted", "")
    assert not disks._macos_newfs_needs_privilege(1, "too few clusters for FAT32", "")
    assert not disks._macos_newfs_needs_privilege(0, "Permission denied", "")


def test_macos_admin_newfs_shell_allowlisted():
    sh = disks._macos_admin_newfs_shell("/sbin/newfs_msdos", "DSI_SD", "disk4", "disk4s1")
    assert "unmountDisk force /dev/disk4" in sh
    assert "-b 32768" in sh
    assert "/dev/rdisk4s1" in sh
    assert "&&" in sh
    assert ";" not in sh


def test_macos_force_cluster_rejects_bad_ids():
    ok, msg = disks._macos_force_cluster32("disk4;rm", "disk4s1", "DSI_SD")
    assert ok is False
    ok, msg = disks._macos_force_cluster32("disk4", "disk4s1", "DSI;SD")
    assert ok is False
    ok, msg = disks._macos_force_cluster32("disk4", "disk5s1", "DSI_SD")
    assert ok is False
    ok, msg = disks._macos_force_cluster32("disk4s1", "disk4s1", "DSI_SD")
    assert ok is False


class _Proc:
    def __init__(self, code=0, err="", out=""):
        self.returncode = code
        self.stderr = err
        self.stdout = out


def test_macos_force_cluster_retries_admin_on_permission(monkeypatch):
    auth_devs = []
    copy_calls = []

    def fake_run(cmd, **kwargs):
        if cmd and "newfs_msdos" in cmd[0]:
            return _Proc(1, "Permission denied")
        return _Proc(0)

    monkeypatch.setattr(disks.subprocess, "run", fake_run)
    monkeypatch.setattr(disks, "_macos_newfs_bin", lambda: "/sbin/newfs_msdos")
    monkeypatch.setattr(disks, "_macos_partition_total_size", lambda _p: 8 * 1024**3)
    monkeypatch.setattr(
        disks,
        "_macos_build_fat32_sparse_image",
        lambda *_a, **_k: ("/tmp/fake.img", ""),
    )
    monkeypatch.setattr(disks, "_macos_image_payload_bytes", lambda *_a, **_k: 1024)
    monkeypatch.setattr(disks, "_macos_fat32_prefix_from_bpb", lambda *_a, **_k: 1024)

    def fake_auth(dev):
        auth_devs.append(dev)
        return 99, ""

    monkeypatch.setattr(disks, "_macos_authopen_rdwr", fake_auth)

    def fake_copy(path, fd, nbytes):
        copy_calls.append((path, fd, nbytes))
        return True, nbytes

    monkeypatch.setattr(disks, "_macos_copy_to_fd", fake_copy)
    monkeypatch.setattr(disks.os, "remove", lambda _p: None)
    monkeypatch.setattr(disks.os, "close", lambda _fd: None)

    ok, err = disks._macos_force_cluster32("disk4", "disk4s1", "DSI_SD")
    assert ok is True
    assert err == ""
    assert auth_devs == ["/dev/rdisk4s1"]
    assert copy_calls


def test_macos_force_cluster_skips_admin_on_geometry(monkeypatch):
    def fake_run(cmd, **kwargs):
        if cmd and "newfs_msdos" in cmd[0]:
            return _Proc(1, "too few clusters for FAT32")
        return _Proc(0)

    monkeypatch.setattr(disks.subprocess, "run", fake_run)
    monkeypatch.setattr(disks, "_macos_newfs_bin", lambda: "/sbin/newfs_msdos")

    def _no_build(*_a, **_k):
        raise AssertionError("não deve criar imagem em erro de geometria")

    monkeypatch.setattr(disks, "_macos_build_fat32_sparse_image", _no_build)
    ok, err = disks._macos_force_cluster32("disk4", "disk4s1", "DSI_SD")
    assert ok is False
    assert "too few clusters" in err


def test_macos_force_cluster_admin_cancelled(monkeypatch):
    def fake_run(cmd, **kwargs):
        if cmd and "newfs_msdos" in cmd[0]:
            return _Proc(1, "Permission denied")
        return _Proc(0)

    monkeypatch.setattr(disks.subprocess, "run", fake_run)
    monkeypatch.setattr(disks, "_macos_newfs_bin", lambda: "/sbin/newfs_msdos")
    monkeypatch.setattr(disks, "_macos_partition_total_size", lambda _p: 8 * 1024**3)
    monkeypatch.setattr(
        disks,
        "_macos_build_fat32_sparse_image",
        lambda *_a, **_k: ("/tmp/fake.img", ""),
    )
    monkeypatch.setattr(disks, "_macos_image_payload_bytes", lambda *_a, **_k: 1024)
    monkeypatch.setattr(disks, "_macos_fat32_prefix_from_bpb", lambda *_a, **_k: 1024)
    monkeypatch.setattr(
        disks,
        "_macos_authopen_rdwr",
        lambda _dev: (None, "User canceled. (-128)"),
    )
    monkeypatch.setattr(disks.os, "remove", lambda _p: None)

    ok, err = disks._macos_force_cluster32("disk4", "disk4s1", "DSI_SD")
    assert ok is False
    assert "cancelada" in err.lower() or "autoriz" in err.lower()


def test_macos_authopen_rejects_bad_dev():
    ok, err = disks._macos_newfs_with_authopen(
        "/sbin/newfs_msdos", "DSI_SD", "/dev/disk4"
    )
    assert ok is False
    assert "allowlist" in err.lower() or "inválido" in err.lower() or "fora" in err.lower()


def test_macos_parse_hdiutil_attach_dev():
    out = "/dev/disk9          \t\n"
    assert disks._macos_parse_hdiutil_attach_dev(out) == "/dev/disk9"
    assert disks._macos_parse_hdiutil_attach_dev("") == ""


def test_macos_build_rejects_tiny_partition():
    path, err = disks._macos_build_fat32_sparse_image(
        "/sbin/newfs_msdos", "DSI_SD", 64 * 1024 * 1024
    )
    assert path is None
    assert "pequena" in err.lower() or "mínimo" in err.lower() or "minimo" in err.lower()


def test_macos_first_fat_slice(monkeypatch):
    plist = {
        "AllDisksAndPartitions": [
            {
                "DeviceIdentifier": "disk4",
                "Partitions": [
                    {"DeviceIdentifier": "disk4s1", "Content": "DOS_FAT_32"},
                ],
            }
        ]
    }

    monkeypatch.setattr(
        disks.subprocess,
        "check_output",
        lambda *a, **k: disks.plistlib.dumps(plist),
    )
    assert disks._macos_first_fat_slice("disk4") == "disk4s1"


def test_macos_first_fat_slice_fallback(monkeypatch):
    def boom(*a, **k):
        raise OSError("fail")

    monkeypatch.setattr(disks.subprocess, "check_output", boom)
    assert disks._macos_first_fat_slice("disk7") == "disk7s1"


def test_macos_format_remounts_when_cluster_fails(monkeypatch):
    mounts = []

    def fake_co(cmd, **kwargs):
        return disks.plistlib.dumps(
            {
                "Removable": True,
                "BusProtocol": "USB",
                "DeviceIdentifier": "disk4s1",
                "ParentWholeDisk": "disk4",
                "TotalSize": 8 * 1024**3,
            }
        )

    def fake_run(cmd, **kwargs):
        if cmd and cmd[:2] == ["diskutil", "mount"]:
            mounts.append(cmd)
        return _Proc(0)

    monkeypatch.setattr(disks.subprocess, "check_output", fake_co)
    monkeypatch.setattr(disks.subprocess, "run", fake_run)
    monkeypatch.setattr(
        disks, "_macos_first_fat_slice", lambda p: "disk4s1"
    )
    monkeypatch.setattr(
        disks, "_macos_force_cluster32", lambda *a, **k: (False, "Permission denied")
    )
    ok, msg = disks._format_sd_macos("/Volumes/SD", "DSI_SD", expected_device_id="disk4s1")
    assert ok is False
    assert "cluster" in msg.lower()
    assert mounts
    assert mounts[0][2] == "/dev/disk4s1"


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
