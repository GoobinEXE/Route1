import os
from unittest.mock import MagicMock

import py7zr
import pytest

from core import twilight


def test_reject_unsafe_member_names(tmp_path):
    assert twilight._is_safe_archive_member("/etc/passwd", str(tmp_path)) is False
    assert twilight._is_safe_archive_member("..\\x", str(tmp_path)) is False
    assert twilight._is_safe_archive_member("../evil.txt", str(tmp_path)) is False
    assert twilight._is_safe_archive_member("_nds/TWiLightMenu/x", str(tmp_path)) is True


def test_reject_zip_slip_via_getnames(tmp_path, fake_cache, monkeypatch):
    monkeypatch.setattr("core.twilight.CACHE_DIR", str(fake_cache))
    archive = tmp_path / "evil.7z"
    # Arquivo 7z válido com nomes seguros; forçamos getnames() a reportar zip-slip
    with py7zr.SevenZipFile(archive, "w") as z:
        z.writestr(b"pwned", "ok.txt")

    real_cls = py7zr.SevenZipFile

    class EvilArchive(real_cls):
        def getnames(self):
            return ["../evil.txt", "ok.txt"]

    monkeypatch.setattr(py7zr, "SevenZipFile", EvilArchive)
    with pytest.raises(RuntimeError, match="inseguro|rejeitado"):
        twilight._extract_twilight_7z(str(archive), str(fake_cache / "out"))


def test_valid_extract_generates_manifest(tmp_path, fake_cache, monkeypatch):
    from tests.conftest import make_nds

    monkeypatch.setattr("core.twilight.CACHE_DIR", str(fake_cache))
    staging = tmp_path / "pkg"
    (staging / "_nds" / "TWiLightMenu").mkdir(parents=True)
    make_nds(staging / "BOOT.NDS")
    (staging / "_nds" / "TWiLightMenu" / "main.srldr").write_bytes(b"ok")

    archive = tmp_path / "good.7z"
    with py7zr.SevenZipFile(archive, "w") as z:
        for root, _dirs, files in os.walk(staging):
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, staging)
                z.write(full, rel)

    out = fake_cache / "TWiLightMenu-DSi"
    result = twilight._extract_twilight_7z(str(archive), str(out))
    assert os.path.isfile(os.path.join(result, "BOOT.NDS"))
    assert os.path.isfile(os.path.join(result, ".route_1_kit_manifest"))


def test_extract_vc_addon_requires_gameyob(tmp_path, fake_cache, monkeypatch):
    from tests.conftest import make_nds

    monkeypatch.setattr("core.twilight.CACHE_DIR", str(fake_cache))
    staging = tmp_path / "vc"
    emu = staging / "_nds" / "TWiLightMenu" / "emulators"
    emu.mkdir(parents=True)
    make_nds(emu / "gameyob.nds")
    (staging / "roms" / "gb").mkdir(parents=True)
    (staging / "roms" / "gb" / "Place GB here").write_text("x")

    archive = tmp_path / "vc.7z"
    with py7zr.SevenZipFile(archive, "w") as z:
        for root, _dirs, files in os.walk(staging):
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, staging)
                z.write(full, rel)

    out = fake_cache / "TWiLightMenu-VC"
    result = twilight._extract_twilight_vc_7z(str(archive), str(out))
    assert os.path.isfile(
        os.path.join(result, "_nds", "TWiLightMenu", "emulators", "gameyob.nds")
    )
    assert os.path.isfile(os.path.join(result, ".route_1_kit_manifest"))


def test_install_twilight_virtual_console(tmp_path, fake_cache, monkeypatch):
    from tests.conftest import make_nds

    monkeypatch.setattr("core.twilight.CACHE_DIR", str(fake_cache))
    monkeypatch.setattr("core.twilight.sync_volume", lambda *a, **k: None)

    vc = fake_cache / "TWiLightMenu-VC"
    emu = vc / "_nds" / "TWiLightMenu" / "emulators"
    emu.mkdir(parents=True)
    make_nds(emu / "gameyob.nds")
    (vc / "roms" / "gb").mkdir(parents=True)
    (vc / "roms" / "gb" / "Place ROMs").write_text("ok")
    (vc / ".route_1_kit_manifest").write_text("dummy\n")
    (vc / "snemul.cfg").write_text("cfg\n")

    mount = tmp_path / "SD"
    (mount / "_nds" / "TWiLightMenu").mkdir(parents=True)

    ok, msg = twilight.install_twilight_virtual_console(str(mount))
    assert ok is True, msg
    assert (mount / "_nds" / "TWiLightMenu" / "emulators" / "gameyob.nds").is_file()
    assert (mount / "roms" / "gb").is_dir()
    assert (mount / "roms" / "gbc").is_dir()
    assert (mount / "roms" / "nes").is_dir()
    assert (mount / "roms" / "snes").is_dir()
    assert (mount / "roms" / "tg16").is_dir()
    assert (mount / "roms" / "cpc").is_dir()
    assert (mount / "snemul.cfg").is_file()


def test_is_gei_kernel_dir(tmp_path):
    gei = tmp_path / "GEiv4.2_EN"
    gei.mkdir()
    (gei / "_DS_MENU.DAT").write_bytes(b"x")
    (gei / "_DS_MSHL.NDS").write_bytes(b"y")
    assert twilight.is_gei_kernel_dir(str(gei)) is True

    r4 = tmp_path / "R4i"
    r4.mkdir()
    (r4 / "_DS_MENU.DAT").write_bytes(b"x")
    assert twilight.is_gei_kernel_dir(str(r4)) is False


def test_find_gei_source_prefers_complete_downloads(tmp_path, monkeypatch):
    """Downloads completa sobrescreve o vendor; incompleta cai no bundled."""
    root = tmp_path / "app"
    vendor = root / "vendor" / "GEiv4.2_EN"
    vendor.mkdir(parents=True)
    (vendor / "_DS_MENU.DAT").write_bytes(b"bundled-menu")
    (vendor / "_DS_MSHL.NDS").write_bytes(b"bundled-mshl")

    downloads = tmp_path / "Downloads"
    complete = downloads / "GEiv4.2_EN"
    complete.mkdir(parents=True)
    (complete / "_DS_MENU.DAT").write_bytes(b"dl-menu")
    (complete / "_DS_MSHL.NDS").write_bytes(b"dl-mshl")

    monkeypatch.setattr(twilight, "_app_root", lambda: str(root))
    monkeypatch.setattr(
        twilight.os.path,
        "expanduser",
        lambda p: str(complete) if "GEiv4.2_EN" in p else os.path.expanduser(p),
    )
    monkeypatch.setattr(twilight, "CACHE_DIR", str(tmp_path / "cache"))

    found = twilight.find_gei_source()
    assert found == str(complete)
    assert twilight.is_bundled_gei_path(found) is False

    # Sem _DS_MSHL.NDS em Downloads → usa vendor
    (complete / "_DS_MSHL.NDS").unlink()
    found = twilight.find_gei_source()
    assert found == str(vendor)
    assert twilight.is_bundled_gei_path(found) is True


def test_find_gei_source_skips_incomplete_downloads(tmp_path, monkeypatch):
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    incomplete = downloads / "GEiv4.2_EN"
    incomplete.mkdir()
    (incomplete / "_DS_MENU.DAT").write_bytes(b"only-menu")

    monkeypatch.setattr(twilight, "bundled_gei_dir", lambda: None)
    monkeypatch.setattr(
        twilight.os.path,
        "expanduser",
        lambda p: str(incomplete) if "GEiv4.2_EN" in p else os.path.expanduser(p),
    )
    monkeypatch.setattr(twilight, "CACHE_DIR", str(tmp_path / "cache"))

    assert twilight.find_gei_source() is None


def test_probe_kernels_marks_bundled(tmp_path, monkeypatch):
    root = tmp_path / "app"
    vendor = root / "vendor" / "GEiv4.2_EN"
    vendor.mkdir(parents=True)
    (vendor / "_DS_MENU.DAT").write_bytes(b"m")
    (vendor / "_DS_MSHL.NDS").write_bytes(b"n")

    monkeypatch.setattr(twilight, "_app_root", lambda: str(root))
    monkeypatch.setattr(twilight, "find_r4_candidates", lambda: [])
    monkeypatch.setattr(twilight, "CACHE_DIR", str(tmp_path / "cache"))

    res = twilight.probe_kernels()
    assert res["success"] is True
    assert res["gei"]["bundled"] is True
    assert res["gei"]["path"] == "vendor/GEiv4.2_EN"


def test_find_r4_candidates_skips_gei_and_roms(tmp_path, monkeypatch):
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    monkeypatch.setattr(
        twilight,
        "find_r4_candidates",
        twilight.find_r4_candidates,
    )

    gei = downloads / "GEiv4.2_EN"
    gei.mkdir()
    (gei / "_DS_MENU.DAT").write_bytes(b"g")
    (gei / "_DS_MSHL.NDS").write_bytes(b"g")

    r4 = downloads / "R4_kernel"
    r4.mkdir()
    (r4 / "_DS_MENU.DAT").write_bytes(b"r")
    (r4 / "system.ini").write_bytes(b"ini")
    (r4 / "roms").mkdir()
    (r4 / "roms" / "game.nds").write_bytes(b"game")
    (r4 / "SomeGame.nds").write_bytes(b"game")  # deve ser ignorado
    (r4 / "_SYSTEM_").mkdir()
    (r4 / "_SYSTEM_" / "x.bin").write_bytes(b"1")

    found = twilight.find_r4_candidates([str(downloads)])
    paths = [f["path"] for f in found]
    assert any(os.path.basename(p) == "R4_kernel" for p in paths)
    assert not any("GEiv4.2_EN" in p for p in paths)

    planned = twilight.list_r4_kernel_files(str(r4))
    assert "_DS_MENU.DAT" in planned["files"]
    assert "system.ini" in planned["files"]
    assert "SomeGame.nds" not in planned["files"]
    assert "_SYSTEM_" in planned["dirs"]
    assert "roms" not in planned["dirs"]


def test_install_r4_rejects_gei(tmp_path, monkeypatch):
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    gei = downloads / "oops"
    gei.mkdir()
    (gei / "_DS_MENU.DAT").write_bytes(b"g")
    (gei / "_DS_MSHL.NDS").write_bytes(b"g")
    mount = tmp_path / "SD"
    mount.mkdir()

    monkeypatch.setattr(
        "core.twilight.os.path.expanduser",
        lambda p: str(downloads) if "Downloads" in str(p) else os.path.expanduser(p),
    )

    ok, msg = twilight.install_r4_kernel(str(mount), str(gei))
    assert ok is False
    assert "GEi" in msg


def test_install_r4_copies_kernel_only(tmp_path, monkeypatch):
    from tests.conftest import make_nds

    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    src = downloads / "MyR4"
    src.mkdir()
    (src / "_DS_MENU.DAT").write_bytes(b"menu")
    (src / "system.ini").write_bytes(b"ini")
    make_nds(src / "AKMENU4.NDS")
    (src / "roms").mkdir()
    (src / "roms" / "game.nds").write_bytes(b"should-not-copy")
    (src / "Zelda.nds").write_bytes(b"game")

    mount = tmp_path / "SD"
    mount.mkdir()

    monkeypatch.setattr(
        "core.twilight.os.path.expanduser",
        lambda p: str(downloads) if "Downloads" in str(p) else os.path.expanduser(p),
    )
    monkeypatch.setattr("core.twilight.sync_volume", lambda *a, **k: None)

    def _copy(s, d, **k):
        os.makedirs(os.path.dirname(d) or ".", exist_ok=True)
        with open(s, "rb") as rf, open(d, "wb") as wf:
            wf.write(rf.read())

    monkeypatch.setattr("core.twilight.copy_verified", _copy)
    monkeypatch.setattr("core.twilight.copytree_verified", lambda s, d, **k: 0)

    ok, msg = twilight.install_r4_kernel(str(mount), str(src))
    assert ok is True
    assert (mount / "_DS_MENU.DAT").is_file()
    assert (mount / "system.ini").is_file()
    assert (mount / "AKMENU4.NDS").is_file()
    assert not (mount / "Zelda.nds").exists()
    assert not (mount / "roms").exists()


def test_install_r4_rollback_on_mid_failure(tmp_path, monkeypatch):
    """Falha a meio deve reverter ficheiros novos e restaurar os que existiam."""
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    src = downloads / "MyR4"
    src.mkdir()
    (src / "_DS_MENU.DAT").write_bytes(b"new-menu")
    (src / "system.ini").write_bytes(b"new-ini")

    mount = tmp_path / "SD"
    mount.mkdir()
    (mount / "_DS_MENU.DAT").write_bytes(b"old-menu")

    monkeypatch.setattr(
        "core.twilight.os.path.expanduser",
        lambda p: str(downloads) if "Downloads" in str(p) else os.path.expanduser(p),
    )
    monkeypatch.setattr("core.twilight.sync_volume", lambda *a, **k: None)

    calls = {"n": 0}
    real = twilight.copy_verified

    def flaky(s, d, **k):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise OSError("disk full")
        return real(s, d, **k)

    monkeypatch.setattr("core.twilight.copy_verified", flaky)

    ok, msg = twilight.install_r4_kernel(str(mount), str(src))
    assert ok is False
    assert "disk full" in msg.lower() or "disk full" in str(msg)
    # Destino antigo restaurado; system.ini novo removido
    assert (mount / "_DS_MENU.DAT").read_bytes() == b"old-menu"
    assert not (mount / "system.ini").exists()
    assert not list(mount.glob("*.bak_install"))


def test_extract_preserves_old_on_promote_failure(tmp_path, fake_cache, monkeypatch):
    """Se a promoção falhar a meio, a árvore antiga no cache deve voltar."""
    from tests.conftest import make_nds

    monkeypatch.setattr("core.twilight.CACHE_DIR", str(fake_cache))
    out = fake_cache / "TWiLightMenu-DSi"
    out.mkdir()
    (out / "OLD.txt").write_text("keep-me")
    make_nds(out / "BOOT.NDS")
    (out / "_nds" / "TWiLightMenu").mkdir(parents=True)
    (out / "_nds" / "TWiLightMenu" / "main.srldr").write_bytes(b"old")

    staging_pkg = tmp_path / "pkg"
    (staging_pkg / "_nds" / "TWiLightMenu").mkdir(parents=True)
    make_nds(staging_pkg / "BOOT.NDS")
    (staging_pkg / "_nds" / "TWiLightMenu" / "main.srldr").write_bytes(b"new")

    archive = tmp_path / "good.7z"
    with py7zr.SevenZipFile(archive, "w") as z:
        for root, _dirs, files in os.walk(staging_pkg):
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, staging_pkg)
                z.write(full, rel)

    real_rename = os.rename
    state = {"n": 0}

    def flaky_rename(src, dst):
        state["n"] += 1
        # Deixa o rename extract→backup passar; falha no staging→extract
        if state["n"] >= 2:
            raise OSError("rename failed")
        return real_rename(src, dst)

    monkeypatch.setattr(os, "rename", flaky_rename)
    with pytest.raises(OSError, match="rename failed"):
        twilight._extract_twilight_7z(str(archive), str(out))
    assert (out / "OLD.txt").read_text() == "keep-me"


def test_api_setup_r4(monkeypatch, tmp_path):
    import app as app_mod

    api = app_mod.Api()
    fake = tmp_path / "SD"
    fake.mkdir()
    monkeypatch.setattr(app_mod, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(app_mod, "preflight", lambda *a, **k: (True, "ok", {}))
    monkeypatch.setattr(
        app_mod,
        "install_r4_kernel",
        lambda mount, src, log_callback=None: (True, "Kernel R4 instalado."),
    )
    res = api.setup_r4(str(fake), "/tmp/r4")
    assert res["success"] is True
