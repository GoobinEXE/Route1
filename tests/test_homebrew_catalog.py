"""Testes do catálogo homebrew e instalação pinada."""

from core import cache, homebrew_catalog, homebrew_install, sd_utils
from core.about import is_allowed_external_url


def test_catalog_ids_unique_and_pinned():
    apps = homebrew_catalog.list_apps()
    assert apps
    ids = [a["id"] for a in apps]
    assert len(ids) == len(set(ids))
    for app in apps:
        assert app["installable"] is True
        key = app["install_key"]
        assert key in cache.PINNED_SHA256
        assert key in cache.URLS
        assert key in cache.FILENAMES
        assert app["dest_filename"] == cache.FILENAMES[key]
        assert app["gamebrew_url"].startswith(homebrew_catalog.GAMEBREW_WIKI_PREFIX)
        assert is_allowed_external_url(app["gamebrew_url"])
        assert isinstance(app.get("setup_notes"), list)


def test_get_app_and_payload():
    assert homebrew_catalog.get_app("") is None
    assert homebrew_catalog.get_app("nope") is None
    gm9 = homebrew_catalog.get_app("godmode9i")
    assert gm9 and gm9["title"] == "GodMode9i"
    payload = homebrew_catalog.build_catalog_payload()
    assert payload["success"] is True
    assert len(payload["apps"]) == len(homebrew_catalog.list_apps())
    assert payload["categories"]


def test_gamebrew_url_allowlist():
    assert is_allowed_external_url(
        "https://www.gamebrew.org/wiki/List_of_DS_homebrew_applications"
    )
    assert is_allowed_external_url("https://www.gamebrew.org/wiki/GodMode9i")
    assert not is_allowed_external_url("https://evil.example/wiki/GodMode9i")
    assert not is_allowed_external_url("https://www.gamebrew.org/wiki/foo/bar")
    assert not is_allowed_external_url("https://www.gamebrew.org/wiki/../x")
    assert not is_allowed_external_url("javascript:alert(1)")


def test_install_homebrew(tmp_path, monkeypatch, fake_cache):
    sd = tmp_path / "SD"
    sd.mkdir()
    src = fake_cache / "ftpd.nds"
    payload = b"FTPD" + b"\x00" * 2048
    src.write_bytes(payload)
    digest = __import__("hashlib").sha256(payload).hexdigest()

    monkeypatch.setattr(sd_utils, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(
        sd_utils, "ensure_cached", lambda key, log_callback=None: str(src)
    )
    monkeypatch.setitem(sd_utils.PINNED_SHA256, "ftpd", digest)
    monkeypatch.setattr("core.sdio.sync_volume", lambda *a, **k: None)

    ok, msg = sd_utils.install_homebrew(str(sd), "ftpd")
    assert ok is True
    assert (sd / "roms" / "apps" / "ftpd.nds").is_file()

    bad = sd_utils.install_homebrew(str(sd), "does-not-exist")
    assert bad[0] is False


def test_setup_godmode9i_wrapper(tmp_path, monkeypatch, fake_cache):
    sd = tmp_path / "SD"
    sd.mkdir()
    src = fake_cache / "GodMode9i.dsi"
    payload = b"GM9I" + b"\x00" * 2048
    src.write_bytes(payload)
    digest = __import__("hashlib").sha256(payload).hexdigest()

    monkeypatch.setattr(sd_utils, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(
        sd_utils, "ensure_cached", lambda key, log_callback=None: str(src)
    )
    monkeypatch.setitem(sd_utils.PINNED_SHA256, "godmode9i", digest)
    monkeypatch.setattr("core.sdio.sync_volume", lambda *a, **k: None)

    ok, msg = sd_utils.setup_godmode9i(str(sd))
    assert ok is True
    assert (sd / "roms" / "apps" / "GodMode9i.dsi").is_file()


def test_kekatsu_recipe_creates_databases(tmp_path, monkeypatch, fake_cache):
    sd = tmp_path / "SD"
    sd.mkdir()
    src = fake_cache / "Kekatsu.nds"
    payload = b"KEKA" + b"\x00" * 2048
    src.write_bytes(payload)
    digest = __import__("hashlib").sha256(payload).hexdigest()

    monkeypatch.setattr(sd_utils, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(
        sd_utils, "ensure_cached", lambda key, log_callback=None: str(src)
    )
    monkeypatch.setitem(sd_utils.PINNED_SHA256, "kekatsu", digest)
    monkeypatch.setattr("core.sdio.sync_volume", lambda *a, **k: None)

    ok, msg = sd_utils.install_homebrew(str(sd), "kekatsu")
    assert ok is True
    db = sd / "Kekatsu" / "databases.txt"
    assert db.is_file()
    text = db.read_text(encoding="utf-8")
    assert "UDB-Kekatsu-DS=" in text
    assert (sd / "roms" / "apps" / "Kekatsu.nds").is_file()

    # Segunda instalação não sobrescreve config do utilizador
    db.write_text("custom=https://example.com/db\n", encoding="utf-8")
    ok2, _ = sd_utils.install_homebrew(str(sd), "kekatsu")
    assert ok2 is True
    assert db.read_text(encoding="utf-8").startswith("custom=")


def test_pkmn_chest_dual_copy(tmp_path, monkeypatch, fake_cache):
    sd = tmp_path / "SD"
    sd.mkdir()
    src = fake_cache / "pkmn-chest.nds"
    payload = b"PKMN" + b"\x00" * 2048
    src.write_bytes(payload)
    digest = __import__("hashlib").sha256(payload).hexdigest()

    monkeypatch.setattr(sd_utils, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(
        sd_utils, "ensure_cached", lambda key, log_callback=None: str(src)
    )
    monkeypatch.setitem(sd_utils.PINNED_SHA256, "pkmn_chest", digest)
    monkeypatch.setattr("core.sdio.sync_volume", lambda *a, **k: None)

    ok, msg = sd_utils.install_homebrew(str(sd), "pkmn_chest")
    assert ok is True
    assert (sd / "roms" / "apps" / "pkmn-chest.nds").is_file()
    assert (sd / "_nds" / "pkmn-chest" / "pkmn-chest.nds").is_file()


def test_ntm_creates_backup_dir(tmp_path, monkeypatch, fake_cache):
    sd = tmp_path / "SD"
    sd.mkdir()
    src = fake_cache / "NTM.dsi"
    payload = b"NTM0" + b"\x00" * 2048
    src.write_bytes(payload)
    digest = __import__("hashlib").sha256(payload).hexdigest()

    monkeypatch.setattr(sd_utils, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(
        sd_utils, "ensure_cached", lambda key, log_callback=None: str(src)
    )
    monkeypatch.setitem(sd_utils.PINNED_SHA256, "ntm", digest)
    monkeypatch.setattr("core.sdio.sync_volume", lambda *a, **k: None)

    ok, _ = sd_utils.install_homebrew(str(sd), "ntm")
    assert ok is True
    assert (sd / "_nds" / "ntm" / "backup").is_dir()
    assert homebrew_install.notes_for("ntm")
