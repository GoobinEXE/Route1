import os

from core import sdio


def test_copy_verified_roundtrip(tmp_path):
    src = tmp_path / "src.bin"
    dst = tmp_path / "dst.bin"
    src.write_bytes(b"hello-sd-card" * 100)
    digest = sdio.copy_verified(str(src), str(dst))
    assert dst.read_bytes() == src.read_bytes()
    assert len(digest) == 64


def test_copy_verified_detects_mismatch(tmp_path):
    src = tmp_path / "src.bin"
    dst = tmp_path / "dst.bin"
    src.write_bytes(b"A" * 1024)
    import pytest

    with pytest.raises(RuntimeError, match="Integridade"):
        sdio.copy_verified(str(src), str(dst), expected_sha256="0" * 64)
    assert not dst.exists()
    assert not (tmp_path / "dst.bin.partial").exists()


def test_copy_verified_preserves_existing_on_mismatch(tmp_path):
    """Mismatch deve falhar sem destruir o destino já existente (verify-before-replace)."""
    src = tmp_path / "src.bin"
    dst = tmp_path / "dst.bin"
    src.write_bytes(b"NEW" * 256)
    dst.write_bytes(b"OLD-CONTENT-PRESERVE")
    import pytest

    with pytest.raises(RuntimeError, match="Integridade"):
        sdio.copy_verified(str(src), str(dst), expected_sha256="0" * 64)
    assert dst.read_bytes() == b"OLD-CONTENT-PRESERVE"
    assert not (tmp_path / "dst.bin.partial").exists()


def test_undo_stack_restores_and_syncs(tmp_path, monkeypatch):
    dst = tmp_path / "file.bin"
    bak = tmp_path / "file.bin.bak"
    dst.write_bytes(b"new")
    bak.write_bytes(b"old")
    synced = {"n": 0}
    monkeypatch.setattr(sdio, "sync_volume", lambda p: synced.__setitem__("n", synced["n"] + 1))

    undo = sdio.UndoStack()
    undo.push_restore_file(str(bak), str(dst))
    undo.rollback(mount_path=str(tmp_path))
    assert dst.read_bytes() == b"old"
    assert synced["n"] == 1


def test_preflight_rejects_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(sdio, "get_mounted_drives", lambda: [])
    ok, msg, _ = sdio.preflight(str(tmp_path / "nope"))
    assert ok is False
