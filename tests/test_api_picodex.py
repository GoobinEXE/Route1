"""As funções da PicoDex pela API (a fronteira que a UI usa), não só pelo core.

Regressão: _as_bool devolve (valor, erro); usado como booleano, um par é
sempre verdadeiro e ligava "manter ícone" e "cada sistema na sua pasta".
"""

from __future__ import annotations

import base64

import pytest

import app as app_mod
from core import routedex
from tests.conftest import make_nds


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setattr(app_mod, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr("core.pico_artwork.is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(app_mod, "preflight", lambda *a, **k: (True, "ok", {}))
    monkeypatch.setattr("core.sdio.sync_volume", lambda *a, **k: None)
    monkeypatch.setattr("core.dspico.sync_volume", lambda *a, **k: None)
    return app_mod.Api()


def _icon_token(api):
    rgba = bytes([0, 120, 255, 255]) * (32 * 32)
    r = api.encode_art("icon", base64.b64encode(rgba).decode())
    assert r["success"], r
    return r["token"]


def test_banner_saves_the_chosen_icon_when_keep_is_false(api, fake_sd):
    (fake_sd / "Games" / "gb").mkdir(parents=True)
    res = api.save_folder_banner(str(fake_sd), "Games/gb", "Game Boy", _icon_token(api), False)
    assert res["success"], res
    info = routedex.parse_banner((fake_sd / "Games" / "gb" / "banner.bnr").read_bytes())
    assert info["title"] == "Game Boy" and info["crc_ok"]
    # E manter o ícone continua funcionando com true.
    res2 = api.save_folder_banner(str(fake_sd), "Games/gb", "Portáteis", None, True)
    assert res2["success"], res2
    assert api.save_folder_banner(str(fake_sd), "Games/gb", "X", None, "talvez")["success"] is False


def test_import_respects_the_by_system_checkbox(api, fake_sd, tmp_path):
    (fake_sd / "_pico").mkdir()
    (fake_sd / "Games" / "Aberta").mkdir(parents=True)
    src = tmp_path / "host"
    src.mkdir()
    make_nds(str(src / "Kart.nds"), title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")

    off = api.import_dspico_games(str(fake_sd), [str(src / "Kart.nds")], "Aberta", {}, False, False)
    assert off["success"], off
    assert (fake_sd / "Games" / "Aberta" / "Kart.nds").is_file()
    assert not (fake_sd / "Games" / "nds").exists()

    (src / "Tetris.gb").write_bytes(b"GB" * 64)
    on = api.import_dspico_games(str(fake_sd), [str(src / "Tetris.gb")], "Aberta", {}, True, False)
    assert on["success"], on
    assert (fake_sd / "Games" / "gb" / "Tetris.gb").is_file()
    assert api.import_dspico_games(str(fake_sd), [str(src / "Tetris.gb")], "", {}, "sim?", False)["success"] is False


def test_compat_and_library_through_the_api(api, fake_sd):
    (fake_sd / "_pico").mkdir()
    nds = fake_sd / "Games" / "nds"
    nds.mkdir(parents=True)
    make_nds(str(nds / "Kart.nds"), title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")
    lib = api.get_routedex_library(str(fake_sd))
    assert lib["success"] and lib["totals"]["games"] == 1
    c = api.get_routedex_compat(str(fake_sd), "Games/nds/Kart.nds")
    assert c["success"] and c["game_code"] == "AMCE"
    assert api.get_routedex_compat(str(fake_sd), "Games/nds/../../etc.nds")["success"] is False
    assert api.get_routedex_compat(str(fake_sd), "Games/gb/Tetris.gb")["success"] is False
