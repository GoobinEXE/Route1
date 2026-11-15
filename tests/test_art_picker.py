"""Janela de capa/ícone e editor de banner (port de PicoDex CoverPicker / BannerEditor)."""

from __future__ import annotations

import base64
import os

import pytest

from core import art_picker, pico_bmp, picodex_rules, routedex
from tests.conftest import make_nds


@pytest.fixture(autouse=True)
def _safe_mount(monkeypatch):
    monkeypatch.setattr("core.pico_artwork.is_safe_mount_path", lambda p: True)
    monkeypatch.setattr("core.sdio.sync_volume", lambda *a, **k: None)


def _b64(rgba: bytes) -> str:
    return base64.b64encode(rgba).decode("ascii")


def _solid(w: int, h: int, rgba=(200, 40, 40, 255)) -> bytes:
    return bytes(rgba) * (w * h)


def _card(sd):
    (sd / "_pico").mkdir()
    games = sd / "Games" / "nds"
    games.mkdir(parents=True)
    for name, code in (("Alpha.nds", b"AAAE"), ("Kart.nds", b"AMCE"), ("Zelda.nds", b"AZEE")):
        make_nds(str(games / name), title=name.encode()[:12], code=code, maker=b"01")
    return games


def test_encode_cover_and_icon_pass_launcher_checks():
    c = art_picker.encode_art("cover", _b64(_solid(128, 96)))
    assert c["success"] and c["preview"].startswith("data:image/png;base64,")
    cover = art_picker._stage_get(c["token"], "cover")["bmp"]
    assert pico_bmp.validate_launcher_cover_bmp(cover) is None

    icon_rgba = bytearray(_solid(32, 32, (10, 200, 10, 255)))
    icon_rgba[0:4] = b"\0\0\0\0"  # canto transparente
    i = art_picker.encode_art("icon", _b64(bytes(icon_rgba)))
    entry = art_picker._stage_get(i["token"], "icon")
    assert pico_bmp.validate_launcher_icon_bmp(entry["bmp"]) is None
    assert entry["rgba"][3] == 0 and entry["rgba"][7] == 255  # índice 0 continua transparente

    with pytest.raises(art_picker.ArtPickerError):
        art_picker.encode_art("cover", _b64(_solid(10, 10)))
    with pytest.raises(art_picker.ArtPickerError):
        art_picker._stage_get(i["token"], "cover")


def test_picker_context_and_save_cover_and_icon_together(fake_sd):
    _card(fake_sd)
    ctx = art_picker.picker_context(str(fake_sd), "Games/nds/Kart.nds")
    assert ctx["system"]["repo"] == "Nintendo_-_Nintendo_DS"
    assert ctx["targets"] == {"cover": "_pico/covers/nds/AMCE.bmp", "icon": "_pico/icons/nds/AMCE.bmp"}
    assert ctx["neighbours"] == {"before": ["Alpha"], "after": ["Zelda"]}
    assert ctx["cover"] is None

    c = art_picker.encode_art("cover", _b64(_solid(128, 96)))
    i = art_picker.encode_art("icon", _b64(_solid(32, 32)))
    out = art_picker.save_art(str(fake_sd), "Games/nds/Kart.nds", c["token"], i["token"])
    assert out["written"] == ["_pico/covers/nds/AMCE.bmp", "_pico/icons/nds/AMCE.bmp"]
    assert not any(n.endswith(".partial") for _r, _d, fs in os.walk(fake_sd) for n in fs)

    ctx2 = art_picker.picker_context(str(fake_sd), "Games/nds/Kart.nds")
    assert ctx2["cover"]["preview"] and ctx2["cover"]["invalid"] is None
    assert ctx2["icon"]["kind"] == "custom"

    with pytest.raises(art_picker.ArtPickerError):
        art_picker.save_art(str(fake_sd), "Games/nds/Kart.nds")


def test_invalid_icon_on_card_is_reported(fake_sd):
    _card(fake_sd)
    bad = fake_sd / "_pico" / "icons" / "nds"
    bad.mkdir(parents=True)
    (bad / "AMCE.bmp").write_bytes(b"BM" + b"\0" * 200)
    ctx = art_picker.picker_context(str(fake_sd), "Games/nds/Kart.nds")
    assert ctx["icon"]["kind"] == "invalid" and ctx["icon"]["preview"] is None


def test_catalog_search_puts_the_suggestion_first(monkeypatch):
    names = ["Mario Kart DS (Japan).png", "Mario Kart DS (USA, Australia).png", "Kirby (USA).png"]
    monkeypatch.setattr(picodex_rules, "fetch_catalog", lambda repo, kind="boxarts", **k: names)
    r = art_picker.catalog_search("Nintendo_-_Nintendo_DS", "Mario Kart DS", "boxarts", title="Mario Kart DS")
    assert r["success"] and r["suggested"] == "Mario Kart DS (USA, Australia).png"
    assert r["results"][0]["name"] == r["suggested"]
    assert r["results"][0]["label"] == "Mario Kart DS (USA, Australia)"


def test_catalog_requests_are_validated():
    assert art_picker.catalog_thumbs("../evil", ["a.png"])["success"] is False
    assert art_picker.catalog_image("Nintendo_-_Nintendo_DS", "../x.png")["success"] is False
    assert art_picker.remote_image("https://example.com/a.png")["success"] is False


def test_parse_catalog_kinds_splits_boxarts_and_logos():
    tree = {"tree": [
        {"path": "Named_Boxarts/A (USA).png"},
        {"path": "Named_Logos/A (USA).png"},
        {"path": "Named_Snaps/A (USA).png"},
        {"path": "README.md"},
    ]}
    kinds = picodex_rules.parse_catalog_kinds(tree)
    assert kinds == {"boxarts": ["A (USA).png"], "logos": ["A (USA).png"]}
    assert "Named_Logos/" in picodex_rules.thumb_url("Nintendo_-_Game_Boy", "A (USA).png", "logos")


def test_banner_context_save_new_icon_and_keep(fake_sd):
    _card(fake_sd)
    (fake_sd / "Games" / "gb").mkdir()
    ctx = art_picker.banner_context(str(fake_sd), "Games/gb")
    assert ctx["shared_systems"] == ["Game Boy", "Game Boy Color"]
    assert ctx["default_title"] == "Game Boy / Game Boy Color" and ctx["default_query"] == "Game Boy"
    assert ctx["current"] is None

    i = art_picker.encode_art("icon", _b64(_solid(32, 32, (0, 0, 255, 255))))
    out = art_picker.save_banner(str(fake_sd), "Games/gb", "Game Boy", icon_token=i["token"])
    assert out["written"] == "Games/gb/banner.bnr"
    info = routedex.parse_banner((fake_sd / "Games" / "gb" / "banner.bnr").read_bytes())
    assert info["title"] == "Game Boy" and info["crc_ok"]

    art_picker.save_banner(str(fake_sd), "Games/gb", "Portáteis", keep_icon=True)
    info2 = routedex.parse_banner((fake_sd / "Games" / "gb" / "banner.bnr").read_bytes())
    assert info2["title"] == "Portáteis" and info2["bitmap"] == info["bitmap"]
    ctx2 = art_picker.banner_context(str(fake_sd), "Games/gb")
    assert ctx2["current"]["title"] == "Portáteis" and ctx2["current"]["icon"]

    with pytest.raises(art_picker.ArtPickerError):
        art_picker.banner_context(str(fake_sd), "")
    with pytest.raises(routedex.RouteDexError):
        art_picker.banner_context(str(fake_sd), "../outside")


def test_icon_bmp_rgba_keeps_transparency_roundtrip():
    rgba = bytearray(_solid(32, 32, (255, 255, 0, 255)))
    for p in range(0, 32):  # primeira linha transparente
        rgba[p * 4 + 3] = 0
    bmp = pico_bmp.rgba_to_icon_bmp(32, 32, bytes(rgba))
    back = art_picker.icon_bmp_rgba(bmp)
    assert back[3] == 0 and back[31 * 4 + 3] == 0
    assert back[32 * 4 : 32 * 4 + 4] == bytes((255, 255, 0, 255))
