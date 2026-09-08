import pytest

import app as app_mod


def test_api_inspect_blocks_during_op(monkeypatch, tmp_path):
    api = app_mod.Api()
    fake = tmp_path / "SD"
    fake.mkdir()
    monkeypatch.setattr(app_mod, "is_safe_mount_path", lambda p: True)
    assert app_mod.OP_LOCK.acquire(blocking=False)
    try:
        res = api.inspect_sd(str(fake))
        assert res["success"] is False
        assert "andamento" in res["error"].lower()
    finally:
        app_mod.OP_LOCK.release()


def test_api_blocks_concurrent_ops(monkeypatch, tmp_path):
    api = app_mod.Api()
    fake = tmp_path / "SD"
    fake.mkdir()
    monkeypatch.setattr(app_mod, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(
        app_mod,
        "preflight",
        lambda *a, **k: (True, "ok", {"is_removable": True}),
    )
    monkeypatch.setattr(app_mod, "setup_nand_backup_stage", lambda *a, **k: True)

    assert app_mod.OP_LOCK.acquire(blocking=False)
    try:
        res = api.setup_nand_dump(str(fake), True)
        assert res["success"] is False
        assert "andamento" in res["error"].lower()
    finally:
        app_mod.OP_LOCK.release()

    # Após liberar o lock, a operação deve seguir
    res2 = api.setup_nand_dump(str(fake), True)
    assert res2["success"] is True


def test_api_maps_exception_to_failure(monkeypatch, tmp_path):
    api = app_mod.Api()
    fake = tmp_path / "SD"
    fake.mkdir()
    monkeypatch.setattr(app_mod, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(
        app_mod, "preflight", lambda *a, **k: (True, "ok", {})
    )

    def boom(*a, **k):
        raise RuntimeError("falha controlada")

    monkeypatch.setattr(app_mod, "setup_nand_backup_stage", boom)
    res = api.setup_nand_dump(str(fake), True)
    assert res["success"] is False
    assert "falha controlada" in res["error"]


def test_backup_false_success_propagates(monkeypatch, tmp_path):
    api = app_mod.Api()
    fake = tmp_path / "SD"
    fake.mkdir()
    monkeypatch.setattr(app_mod, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(app_mod, "preflight", lambda *a, **k: (True, "ok", {}))
    monkeypatch.setattr(app_mod, "backup_drive", lambda *a, **k: (False, "/tmp/x"))
    res = api.backup(str(fake))
    assert res["success"] is False


def test_api_rejects_non_string_mount_path():
    api = app_mod.Api()
    for bad in (None, 123, ["Volumes"], {"p": "/tmp"}, b"/Volumes/SD"):
        res = api.backup(bad)
        assert res["success"] is False
        assert "inválido" in res["error"].lower() or "não especificado" in res["error"].lower()


def test_api_rejects_nul_in_mount_path(monkeypatch):
    api = app_mod.Api()
    monkeypatch.setattr(app_mod, "is_safe_mount_path", lambda p: True)
    res = api.backup("/Volumes/SD\x00/../etc")
    assert res["success"] is False
    assert "inválido" in res["error"].lower()


def test_api_rejects_unsafe_mount(monkeypatch, tmp_path):
    api = app_mod.Api()
    monkeypatch.setattr(app_mod, "is_safe_mount_path", lambda p: False)
    res = api.backup(str(tmp_path))
    assert res["success"] is False
    assert "removível" in res["error"].lower() or "reconhecida" in res["error"].lower()


def test_as_bool_rejects_python_truthy_strings():
    # bool("false") seria True em Python — tipagem estrita deve rejeitar ambíguos.
    ok, err = app_mod._as_bool("false")
    assert ok is False and err is None
    ok, err = app_mod._as_bool("true")
    assert ok is True and err is None
    ok, err = app_mod._as_bool(["x"])
    assert ok is None and err


def test_setup_nand_dump_bool_coercion(monkeypatch, tmp_path):
    api = app_mod.Api()
    fake = tmp_path / "SD"
    fake.mkdir()
    monkeypatch.setattr(app_mod, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(app_mod, "preflight", lambda *a, **k: (True, "ok", {}))
    seen = {}

    def capture(mount, has_facebook=True, log_callback=None):
        seen["has_facebook"] = has_facebook

    monkeypatch.setattr(app_mod, "setup_nand_backup_stage", capture)
    assert api.setup_nand_dump(str(fake), "false")["success"] is True
    assert seen["has_facebook"] is False
    assert api.setup_nand_dump(str(fake), "not-a-bool")["success"] is False


def test_setup_r4_rejects_non_string_source(monkeypatch, tmp_path):
    api = app_mod.Api()
    fake = tmp_path / "SD"
    fake.mkdir()
    monkeypatch.setattr(app_mod, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(app_mod, "preflight", lambda *a, **k: (True, "ok", {}))
    res = api.setup_r4(str(fake), ["/evil"])
    assert res["success"] is False
    assert "origem" in res["error"].lower() or "inválido" in res["error"].lower()
