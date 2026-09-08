"""Redação de paths com home do utilizador."""

import os

from core import privacy
from core.logging_util import emit_log


def test_redact_path_replaces_home(monkeypatch, tmp_path):
    home = str(tmp_path / "homeuser")
    os.makedirs(home, exist_ok=True)
    monkeypatch.setattr(privacy, "_home_prefixes", lambda: (home,))

    target = os.path.join(home, "Desktop", "Backup_SD")
    assert privacy.redact_path(target) == "~/Desktop/Backup_SD"
    assert privacy.redact_path(home) == "~"
    assert privacy.redact_path("/Volumes/SDCARD") == "/Volumes/SDCARD"


def test_redact_text_in_messages(monkeypatch, tmp_path):
    home = str(tmp_path / "alice")
    os.makedirs(home, exist_ok=True)
    monkeypatch.setattr(privacy, "_home_prefixes", lambda: (home,))

    msg = f"Backup concluído em: {home}/Desktop/Backup_X (3 itens)"
    out = privacy.redact_text(msg)
    assert home not in out
    assert "~/Desktop/Backup_X" in out


def test_emit_log_redacts(monkeypatch, tmp_path, capsys):
    home = str(tmp_path / "bob")
    os.makedirs(home, exist_ok=True)
    monkeypatch.setattr(privacy, "_home_prefixes", lambda: (home,))
    seen = []
    emit_log(seen.append, f"Origem: {home}/Downloads/R4")
    assert seen[0].startswith("Origem: ~/Downloads")
    assert home not in seen[0]
    assert home not in capsys.readouterr().out


def test_expand_user_path_roundtrip(monkeypatch, tmp_path):
    home = str(tmp_path / "carol")
    os.makedirs(home, exist_ok=True)

    def _expand(p):
        if isinstance(p, str) and p.startswith("~"):
            return home + p[1:]
        return p

    monkeypatch.setattr(os.path, "expanduser", _expand)
    assert privacy.expand_user_path("~/Downloads/R4") == os.path.join(
        home, "Downloads", "R4"
    )


def test_api_backup_message_redacts_home(monkeypatch, tmp_path):
    import app as app_mod

    home = str(tmp_path / "dave")
    os.makedirs(home, exist_ok=True)
    monkeypatch.setattr(app_mod, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(app_mod, "preflight", lambda *a, **k: (True, "ok", {}))
    backup_dir = os.path.join(home, "Desktop", "Backup_SD_1")
    monkeypatch.setattr(
        app_mod, "backup_drive", lambda *a, **k: (True, backup_dir)
    )
    monkeypatch.setattr(app_mod, "redact_path", lambda p: privacy.redact_path(p))
    monkeypatch.setattr(privacy, "_home_prefixes", lambda: (home,))

    # app.redact_path is imported by name — patch module function used by app
    monkeypatch.setattr(
        "core.privacy._home_prefixes",
        lambda: (home,),
    )
    # Re-bind app's redact_path to use updated prefixes via privacy module
    from core.privacy import redact_path as rp

    monkeypatch.setattr(app_mod, "redact_path", rp)

    api = app_mod.Api()
    fake = tmp_path / "SD"
    fake.mkdir()
    res = api.backup(str(fake))
    assert res["success"] is True
    assert home not in res["message"]
    assert "~/Desktop/Backup_SD_1" in res["message"]
