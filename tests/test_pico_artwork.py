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


def test_twilight_boxart_and_icon_normalize():
    big = _solid_png(600, 900, (200, 40, 80, 255))
    box = pico_bmp.image_bytes_to_twilight_png(big, "boxart")
    assert box.startswith(b"\x89PNG")
    bw, bh, _ = pico_bmp.decode_png_rgba(box)
    assert (bw, bh) == (128, 115)

    icon = pico_bmp.image_bytes_to_twilight_png(big, "icon")
    assert icon.startswith(b"\x89PNG")
    iw, ih, irgba = pico_bmp.decode_png_rgba(icon)
    assert (iw, ih) == (32, 32)
    # padding transparente nas margens (retrato → letterbox horizontal)
    assert irgba[3] == 0


def test_image_bytes_to_pico_bmp_accepts_oversized():
    png = _solid_png(400, 300, (12, 34, 56, 255))
    cover = pico_bmp.image_bytes_to_pico_bmp(png, "cover")
    assert cover[:2] == b"BM"
    cw, ch, _ = pico_bmp.decode_bmp_rgba(cover)
    assert (cw, ch) == (128, 96)
    icon = pico_bmp.image_bytes_to_pico_bmp(png, "icon")
    iw, ih, _ = pico_bmp.decode_bmp_rgba(icon)
    assert (iw, ih) == (32, 32)


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
    assert (fake_sd / "_pico" / "covers" / "user" / "Kart.nds.bmp").is_file()

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
    assert (fake_sd / "_pico" / "icons" / "user" / "Kart.nds.bmp").is_file()


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
    # Pesquisa sonda existência (HEAD) mas não descarrega o PNG.
    assert called["get"] == 0
    assert called["exists"] > 0
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

    data = dspico.browse_dspico_games(str(fake_sd), "Games")
    assert data["success"] is True
    files = data["files"]
    assert files
    assert files[0]["has_cover"] is True
    # Browse rápido: sem data-URL síncrono (UI pede previews à parte).
    assert not files[0].get("cover")


def test_get_dspico_game_previews_lazy(fake_sd):
    from core import dspico

    games = fake_sd / "Games"
    games.mkdir()
    make_nds(str(games / "Kart.nds"), title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")
    cover_dir = fake_sd / "_pico" / "covers" / "nds"
    cover_dir.mkdir(parents=True)
    png = _solid_png(64, 48)
    w, h, rgba = pico_bmp.decode_png_rgba(png)
    (cover_dir / "AMCE.bmp").write_bytes(pico_bmp.rgba_to_cover_bmp(w, h, rgba))

    prev = pico_artwork.get_dspico_game_previews(str(fake_sd), ["Kart.nds"])
    assert prev["success"] is True
    entry = prev["previews"]["Kart.nds"]
    assert entry["has_cover"] is True
    assert isinstance(entry.get("cover"), str) and entry["cover"].startswith(
        "data:image/png;base64,"
    )


def test_enrich_reuses_game_code(fake_sd, monkeypatch):
    games = fake_sd / "Games"
    games.mkdir()
    make_nds(str(games / "Kart.nds"), title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")
    cover_dir = fake_sd / "_pico" / "covers" / "nds"
    cover_dir.mkdir(parents=True)
    png = _solid_png(64, 48)
    w, h, rgba = pico_bmp.decode_png_rgba(png)
    (cover_dir / "AMCE.bmp").write_bytes(pico_bmp.rgba_to_cover_bmp(w, h, rgba))

    calls = {"n": 0}
    real = pico_artwork.get_nds_header_info

    def _count(*a, **k):
        calls["n"] += 1
        return real(*a, **k)

    monkeypatch.setattr(pico_artwork, "get_nds_header_info", _count)
    entry = {"rel_path": "Kart.nds", "area": "games", "game_code": "AMCE"}
    pico_artwork.enrich_dspico_game_entry(str(fake_sd), entry, with_preview=False)
    assert entry["has_cover"] is True
    assert calls["n"] == 0


def test_retro_artwork_user_bucket(fake_sd, monkeypatch, tmp_path):
    from core import dspico

    gb = fake_sd / "ROMs" / "GB"
    gb.mkdir(parents=True)
    (gb / "Tetris.gb").write_bytes(b"GBROM")

    monkeypatch.setattr(pico_artwork, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(pico_artwork, "sync_volume", lambda *a, **k: None)

    meta = pico_artwork.get_dspico_game_artwork(str(fake_sd), "ROMs/GB/Tetris.gb")
    assert meta["success"] is True
    assert meta["area"] == "roms"
    assert meta["platform"] == "gb"
    assert meta["has_cover"] is False

    src = tmp_path / "cover.png"
    src.write_bytes(_solid_png(80, 60))
    ok, msg, stats = pico_artwork.set_dspico_artwork_file(
        str(fake_sd), "ROMs/GB/Tetris.gb", "cover", str(src)
    )
    assert ok is True, msg
    dest = fake_sd / "_pico" / "covers" / "user" / "Tetris.gb.bmp"
    assert dest.is_file(), stats

    browse = dspico.browse_dspico_games(str(fake_sd), "ROMs/GB")
    assert browse["success"]
    entry = next(f for f in browse["files"] if f["name"] == "Tetris.gb")
    assert entry["has_cover"] is True


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


def test_collect_candidates_genesis_not_nds():
    items = pico_artwork._collect_candidate_urls(
        kind="cover",
        platform="genesis",
        basename="Sonic (USA).md",
        tid=None,
        title="Sonic",
        query="",
    )
    assert items
    assert all("Nintendo%20DS" not in u["url"] and "Nintendo DS" not in u["url"] for u in items)
    assert any("Mega%20Drive" in u["url"] or "Genesis" in u["url"] for u in items)


def test_collect_candidates_gba_skips_gametdb_ds():
    items = pico_artwork._collect_candidate_urls(
        kind="cover",
        platform="gba",
        basename="Metroid.gba",
        tid="AXVE",
        title="Metroid",
        query="",
    )
    assert items
    assert not any(i["source"] == "gametdb" for i in items)
    assert any("Game%20Boy%20Advance" in i["url"] for i in items)


def test_search_filters_dead_urls(fake_sd, monkeypatch):
    games = fake_sd / "Games"
    games.mkdir()
    make_nds(str(games / "Kart.nds"), title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")

    def fake_exists(url):
        return "AMCE" in url

    monkeypatch.setattr(pico_artwork, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(pico_artwork, "_http_exists", fake_exists)
    data = pico_artwork.search_dspico_artwork(
        str(fake_sd), "Kart.nds", kind="cover", query=""
    )
    assert data["success"]
    assert data["candidates"]
    assert all("AMCE" in c["url"] for c in data["candidates"])


def test_generate_dspico_artwork_batch_cover_icon_and_missing(fake_sd, monkeypatch):
    games = fake_sd / "Games"
    games.mkdir()
    make_nds(str(games / "Kart.nds"), title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")
    make_nds(str(games / "Miss.nds"), title=b"MISSINGGAME", code=b"ZZZZ", maker=b"01")

    png = _solid_png(64, 48)
    gets = {"n": 0}

    def fake_fetch(urls, **kwargs):
        gets["n"] += 1
        joined = " ".join(urls or [])
        if "AMCE" in joined or "Kart" in joined or "Mario" in joined:
            return png
        return None

    syncs = {"n": 0}

    monkeypatch.setattr(pico_artwork, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(
        pico_artwork, "sync_volume", lambda *a, **k: syncs.__setitem__("n", syncs["n"] + 1)
    )
    monkeypatch.setattr(pico_artwork, "_fetch_first_ok", fake_fetch)

    res = pico_artwork.generate_dspico_artwork_batch(str(fake_sd), max_games=50)
    assert res["success"] is True
    assert res["written"] >= 1
    assert (fake_sd / "_pico" / "covers" / "nds" / "AMCE.bmp").is_file()
    # Lote optimizado: sync uma vez no fim; sem HEAD
    assert syncs["n"] == 1
    assert gets["n"] >= 1
    missing = res.get("missing") or []
    assert any(
        (m.get("rel_path") or "").endswith("Miss.nds")
        and (m.get("missing_cover") or m.get("missing_icon"))
        for m in missing
    )


def test_generate_dspico_artwork_batch_scans_retro_inside_games(fake_sd, monkeypatch):
    games = fake_sd / "Games"
    games.mkdir()
    (games / "Tetris.gb").write_bytes(b"GBROM")

    png = _solid_png(64, 48)
    calls = {"n": 0}

    def fake_fetch(urls, **kwargs):
        calls["n"] += 1
        return png

    monkeypatch.setattr(pico_artwork, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(pico_artwork, "sync_volume", lambda *a, **k: None)
    monkeypatch.setattr(pico_artwork, "_fetch_first_ok", fake_fetch)

    res = pico_artwork.generate_dspico_artwork_batch(str(fake_sd), max_games=10)
    assert res["success"] is True
    assert calls["n"] >= 1
    assert res["written"] >= 1
    assert (fake_sd / "_pico" / "covers" / "user" / "Tetris.gb.bmp").is_file()


def test_batch_candidate_urls_capped():
    urls = pico_artwork._batch_candidate_urls(
        kind="cover",
        platform="nds",
        basename="Super Long Game Name (USA) (Rev 1).nds",
        tid="AMCE",
        title="Super Long Game Name",
    )
    assert len(urls) <= pico_artwork._BATCH_MAX_CANDIDATES
    assert any("gametdb.com" in u for u in urls)
    # Sem explosão de sufixos região (usa libretro_name_candidates)
    assert len(urls) < 20


def test_dspico_batch_emits_progress(fake_sd, monkeypatch):
    games = fake_sd / "Games"
    games.mkdir()
    make_nds(str(games / "Kart.nds"), title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")

    events = []

    def fake_emit(payload):
        events.append(payload)

    monkeypatch.setattr(pico_artwork, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(pico_artwork, "sync_volume", lambda *a, **k: None)
    monkeypatch.setattr(pico_artwork, "_fetch_first_ok", lambda *a, **k: None)
    monkeypatch.setattr(pico_artwork, "_emit_batch_progress", fake_emit)

    res = pico_artwork.generate_dspico_artwork_batch(str(fake_sd), max_games=10)
    assert res["success"] is True
    assert events
    assert events[0]["op"] == "dspico_artwork_batch"
    assert events[-1].get("done") is True
    currents = [e["current"] for e in events if e.get("total")]
    assert max(currents) >= 1


def test_generate_dspico_covers_batch_alias(fake_sd, monkeypatch):
    games = fake_sd / "Games"
    games.mkdir()
    make_nds(str(games / "Kart.nds"), title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")
    monkeypatch.setattr(pico_artwork, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(pico_artwork, "sync_volume", lambda *a, **k: None)
    monkeypatch.setattr(pico_artwork, "_fetch_first_ok", lambda *a, **k: None)
    res = pico_artwork.generate_dspico_covers_batch(str(fake_sd), max_games=10)
    assert res["success"] is True
    assert "missing" in res


def test_dspico_batch_skips_complete_and_cancel(fake_sd, monkeypatch):
    from core import progress

    games = fake_sd / "Games"
    games.mkdir()
    make_nds(str(games / "Done.nds"), title=b"DONEGAME01", code=b"DONE", maker=b"01")
    make_nds(str(games / "Todo.nds"), title=b"TODOGAME01", code=b"TODO", maker=b"01")
    make_nds(str(games / "Next.nds"), title=b"NEXTGAME01", code=b"NEXT", maker=b"01")

    cover = fake_sd / "_pico" / "covers" / "nds"
    icon = fake_sd / "_pico" / "icons" / "nds"
    cover.mkdir(parents=True)
    icon.mkdir(parents=True)

    def fake_resolve(mount, basename, tid, kind):
        if (tid or "").upper() == "DONE" or basename == "Done":
            path = cover / "DONE.bmp" if kind == "cover" else icon / "DONE.bmp"
            return str(path)
        return None

    progress.begin_operation("dspico_artwork_batch")
    calls = {"n": 0}

    def fake_fetch(urls, **kwargs):
        calls["n"] += 1
        progress.request_cancel()
        return None

    monkeypatch.setattr(pico_artwork, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(pico_artwork, "sync_volume", lambda *a, **k: None)
    monkeypatch.setattr(pico_artwork, "resolve_existing_art", fake_resolve)
    monkeypatch.setattr(pico_artwork, "_fetch_first_ok", fake_fetch)

    try:
        res = pico_artwork.generate_dspico_artwork_batch(str(fake_sd), max_games=10)
    finally:
        progress.end_operation()

    assert res["success"] is False
    assert res.get("cancelled") is True
    assert res["skipped"] >= 2
    assert calls["n"] >= 1
