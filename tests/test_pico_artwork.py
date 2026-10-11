"""Testes de capas/ícones Pico Launcher (DSPico)."""

from __future__ import annotations

import struct
import zlib

from core import pico_artwork, pico_bmp
from tests.conftest import make_nds


def _png_rgba(w: int, h: int, rgba: bytes) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw.extend(rgba[y * w * 4 : (y + 1) * w * 4])
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def _solid_png(w=32, h=32, color=(40, 120, 200, 255)) -> bytes:
    rgba = bytes(color) * (w * h)
    return _png_rgba(w, h, rgba)


def test_png_roundtrip_and_cover_bmp():
    png = _solid_png(64, 48, (255, 0, 0, 255))
    w, h, rgba = pico_bmp.decode_png_rgba(png)
    assert (w, h) == (64, 48)
    bmp = pico_bmp.rgba_to_cover_bmp(w, h, rgba)
    assert bmp[:2] == b"BM"
    assert len(bmp) > 128
    pw, ph, _ = pico_bmp.decode_bmp_rgba(bmp)
    assert (pw, ph) == (128, 96)


def test_icon_bmp_4bpp():
    png = _solid_png(48, 48, (10, 200, 80, 255))
    w, h, rgba = pico_bmp.decode_png_rgba(png)
    bmp = pico_bmp.rgba_to_icon_bmp(w, h, rgba)
    assert bmp[:2] == b"BM"
    # bpp @ offset 28
    bpp = struct.unpack_from("<H", bmp, 28)[0]
    assert bpp == 4
    pw, ph, _ = pico_bmp.decode_bmp_rgba(bmp)
    assert (pw, ph) == (32, 32)


def test_search_name_variants_include_regions():
    names = pico_artwork._search_name_variants("Mario Kart DS", "Mario Kart DS.nds")
    assert any("Mario Kart DS" in n for n in names)
    assert any("(USA)" in n for n in names)


def test_get_and_set_dspico_artwork(fake_sd, monkeypatch, tmp_path):
    games = fake_sd / "Games"
    games.mkdir()
    rom = games / "Kart.nds"
    make_nds(str(rom), title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")

    monkeypatch.setattr(pico_artwork, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(pico_artwork, "sync_volume", lambda *a, **k: None)

    meta = pico_artwork.get_dspico_game_artwork(str(fake_sd), "Kart.nds")
    assert meta["success"] is True
    assert meta["game_code"] == "AMCE"
    assert meta["has_cover"] is False

    src = tmp_path / "cover.png"
    src.write_bytes(_solid_png(80, 60))
    ok, msg, stats = pico_artwork.set_dspico_artwork_file(
        str(fake_sd), "Kart.nds", "cover", str(src)
    )
    assert ok is True, msg
    dest = fake_sd / "_pico" / "covers" / "nds" / "AMCE.bmp"
    assert dest.is_file()

    meta2 = pico_artwork.get_dspico_game_artwork(str(fake_sd), "Kart.nds")
    assert meta2["has_cover"] is True
    assert meta2["cover"] and meta2["cover"].startswith("data:image/png")

    src_i = tmp_path / "icon.png"
    src_i.write_bytes(_solid_png(32, 32, (0, 0, 255, 255)))
    ok, msg, _ = pico_artwork.set_dspico_artwork_file(
        str(fake_sd), "Kart.nds", "icon", str(src_i)
    )
    assert ok is True, msg
    assert (fake_sd / "_pico" / "icons" / "nds" / "AMCE.bmp").is_file()


def test_search_dspico_artwork_candidates(fake_sd, monkeypatch):
    games = fake_sd / "Games"
    games.mkdir()
    rom = games / "Kart.nds"
    make_nds(str(rom), title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")

    called = {"get": 0, "exists": 0}

    def fake_exists(url):
        called["exists"] += 1
        return True

    def fake_get(url):
        called["get"] += 1
        return b"should-not-download-on-search"

    monkeypatch.setattr(pico_artwork, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(pico_artwork, "_http_exists", fake_exists)
    monkeypatch.setattr(pico_artwork, "_http_get", fake_get)

    data = pico_artwork.search_dspico_artwork(
        str(fake_sd), "Kart.nds", kind="cover", query=""
    )
    assert data["success"] is True
    assert data["candidates"]
    # Pesquisa não descarrega — preview é a URL remota allowlisted.
    assert called["get"] == 0
    assert called["exists"] == 0
    preview = data["candidates"][0]["preview"]
    assert preview.startswith("https://")
    assert data["candidates"][0]["url"] == preview


def test_apply_rejects_bad_url(fake_sd, monkeypatch):
    games = fake_sd / "Games"
    games.mkdir()
    make_nds(str(games / "Kart.nds"), title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")
    monkeypatch.setattr(pico_artwork, "is_safe_mount_path", lambda p: True)
    ok, msg, _ = pico_artwork.apply_dspico_artwork_url(
        str(fake_sd),
        "Kart.nds",
        "cover",
        "https://evil.example/x.png",
    )
    assert ok is False
    assert "permitida" in msg.lower() or "URL" in msg


def test_browse_marks_cover(fake_sd):
    from core import dspico

    games = fake_sd / "Games"
    games.mkdir()
    make_nds(str(games / "Kart.nds"), title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")
    cover_dir = fake_sd / "_pico" / "covers" / "nds"
    cover_dir.mkdir(parents=True)
    png = _solid_png(64, 48)
    w, h, rgba = pico_bmp.decode_png_rgba(png)
    (cover_dir / "AMCE.bmp").write_bytes(pico_bmp.rgba_to_cover_bmp(w, h, rgba))

    data = dspico.browse_dspico_games(str(fake_sd), "")
    assert data["success"] is True
    files = data["files"]
    assert files
    assert files[0]["has_cover"] is True


def test_collect_candidates_include_jsdelivr(fake_sd, monkeypatch):
    games = fake_sd / "Games"
    games.mkdir()
    make_nds(str(games / "Kart.nds"), title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")
    items = pico_artwork._collect_candidate_urls(
        kind="cover",
        platform="nds",
        basename="Kart.nds",
        tid="AMCE",
        title="Mario Kart DS",
        query="",
    )
    sources = {i["source"] for i in items}
    assert "gametdb" in sources
    assert "libretro" in sources
    assert "jsdelivr" in sources
    assert any("cdn.jsdelivr.net" in i["url"] for i in items)


def test_generate_dspico_artwork_batch_cover_icon_and_missing(fake_sd, monkeypatch):
    games = fake_sd / "Games"
    games.mkdir()
    make_nds(str(games / "Kart.nds"), title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")
    make_nds(str(games / "Miss.nds"), title=b"MISSINGGAME", code=b"ZZZZ", maker=b"01")

    png = _solid_png(64, 48)

    def fake_exists(url):
        return "AMCE" in url or "Mario" in url or "Kart" in url

    def fake_get(url):
        if "AMCE" in url or "Kart" in url or "Mario" in url:
            return png
        raise OSError("not found")

    monkeypatch.setattr(pico_artwork, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(pico_artwork, "sync_volume", lambda *a, **k: None)
    monkeypatch.setattr(pico_artwork, "_http_exists", fake_exists)
    monkeypatch.setattr(pico_artwork, "_http_get", fake_get)

    res = pico_artwork.generate_dspico_artwork_batch(str(fake_sd), max_games=50)
    assert res["success"] is True
    assert res["written"] >= 1
    assert (fake_sd / "_pico" / "covers" / "nds" / "AMCE.bmp").is_file()
    missing = res.get("missing") or []
    assert any(
        (m.get("rel_path") or "").endswith("Miss.nds")
        and (m.get("missing_cover") or m.get("missing_icon"))
        for m in missing
    )


def test_generate_dspico_covers_batch_alias(fake_sd, monkeypatch):
    games = fake_sd / "Games"
    games.mkdir()
    make_nds(str(games / "Kart.nds"), title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")
    monkeypatch.setattr(pico_artwork, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(pico_artwork, "sync_volume", lambda *a, **k: None)
    monkeypatch.setattr(pico_artwork, "_http_exists", lambda u: False)
    res = pico_artwork.generate_dspico_covers_batch(str(fake_sd), max_games=10)
    assert res["success"] is True
    assert "missing" in res
