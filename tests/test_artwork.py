"""Testes do pipeline de capas/ícones (SteamGridDB + GameTDB + Libretro)."""

from __future__ import annotations

import io
import struct
import zlib
from unittest.mock import MagicMock, patch

from core import artwork, boxart
from tests.conftest import make_nds


def test_tid_region_and_urls():
    assert boxart.tid_region("AMCE") == "US"
    assert boxart.tid_region("AMCP") == "EN"
    urls = boxart.boxart_urls_for_tid("AMCE")
    assert urls
    assert "AMCE.png" in urls[0]
    assert urls[0].startswith("https://art.gametdb.com/")


def test_libretro_sanitize_and_candidates():
    assert artwork.libretro_sanitize_name("Foo & Bar*/Baz") == "Foo _ Bar__Baz"
    names = artwork.libretro_name_candidates(
        "Super Mario Bros. (USA) [!].nes"
    )
    assert names[0] == "Super Mario Bros. (USA) [!]"
    assert "Super Mario Bros." in names
    assert artwork.libretro_name_candidates("") == []


def test_libretro_urls_encoding():
    urls = artwork.libretro_urls(
        "gba", "Pokemon Emerald (USA, Europe)", kind="boxart"
    )
    assert len(urls) == 1
    assert urls[0].startswith("https://thumbnails.libretro.com/")
    assert "Named_Boxarts" in urls[0]
    assert "Game%20Boy%20Advance" in urls[0]
    assert "Pokemon%20Emerald" in urls[0]

    title = artwork.libretro_urls("nes", "Metroid (USA)", kind="icon")
    assert "Named_Titles" in title[0]


def test_libretro_platform_key_aliases():
    assert artwork.libretro_platform_key("genesis") == "gen"
    assert artwork.libretro_platform_key("2600") == "a26"
    assert artwork.libretro_platform_key("coleco") == "col"
    assert artwork.libretro_platform_key("gba") == "gba"
    assert artwork.libretro_platform_key("neogeo") is None
    assert artwork.is_nds_family_platform("nds")
    assert artwork.is_nds_family_platform("dsi")
    assert not artwork.is_nds_family_platform("gba")

    urls = artwork.libretro_urls("genesis", "Sonic (USA)", kind="boxart")
    assert urls
    assert "Mega%20Drive" in urls[0] or "Genesis" in urls[0]
    assert "Nintendo%20DS" not in urls[0]


def test_jsdelivr_libretro_urls():
    urls = artwork.jsdelivr_libretro_urls(
        "nds", "Mario Kart DS (USA)", kind="boxart"
    )
    assert urls
    assert urls[0].startswith("https://cdn.jsdelivr.net/gh/libretro-thumbnails/")
    assert "@master/Named_Boxarts/" in urls[0]
    assert "Mario%20Kart%20DS" in urls[0]
    icons = artwork.jsdelivr_libretro_urls("gba", "Metroid", kind="icon")
    assert "Named_Titles" in icons[0]


def test_boxart_scan_roms(fake_sd):
    nds = fake_sd / "roms" / "nds"
    nds.mkdir(parents=True)
    make_nds(nds / "Mario.nds", title=b"MARIOKART", code=b"AMCE", maker=b"01")
    tids = boxart._scan_rom_tids(str(fake_sd))
    assert tids
    assert tids[0][0] == "AMCE"


def test_scan_roms_multi_platform(fake_sd):
    gba = fake_sd / "roms" / "gba"
    gba.mkdir(parents=True)
    (gba / "Advance Wars (USA).gba").write_bytes(b"GBA" + b"\x00" * 200)
    nds = fake_sd / "roms" / "nds"
    nds.mkdir(parents=True)
    make_nds(nds / "Mario.nds", title=b"MARIOKART", code=b"AMCE", maker=b"01")

    items = artwork._scan_roms_for_artwork(str(fake_sd))
    plats = {i["platform"] for i in items}
    assert "gba" in plats
    assert "nds" in plats


def _png_bytes(w: int = 32, h: int = 32) -> bytes:
    """PNG RGBA válido (decodificável) para testes de normalização TWiLight."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    rgba = bytes((40, 120, 200, 255)) * (w * h)
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


def test_fetch_rom_artwork_gba_libretro(fake_sd, monkeypatch):
    gba = fake_sd / "roms" / "gba"
    gba.mkdir(parents=True)
    rom = gba / "Advance Wars (USA).gba"
    rom.write_bytes(b"GBA" + b"\x00" * 200)

    png = _png_bytes(64, 64)

    def fake_urlopen(req, timeout=30):
        cm = MagicMock()
        cm.__enter__ = lambda s: s
        cm.__exit__ = lambda *a: None
        bio = io.BytesIO(png)
        cm.read = bio.read
        return cm

    monkeypatch.setattr(artwork, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(artwork, "sync_volume", lambda *a, **k: None)
    monkeypatch.setattr(artwork.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr("core.steamgriddb.has_api_key", lambda: False)

    ok, msg, stats = artwork.fetch_rom_artwork(
        str(fake_sd), "gba/Advance Wars (USA).gba"
    )
    assert ok is True
    assert stats.get("boxart") is True
    dest = (
        fake_sd
        / "_nds"
        / "TWiLightMenu"
        / "boxart"
        / "Advance Wars (USA).gba.png"
    )
    assert dest.is_file()


def test_install_artwork_skips_existing(fake_sd, monkeypatch):
    nds = fake_sd / "roms" / "nds"
    nds.mkdir(parents=True)
    make_nds(nds / "Mario.nds", title=b"MARIOKART", code=b"AMCE", maker=b"01")
    box = fake_sd / "_nds" / "TWiLightMenu" / "boxart"
    icons = fake_sd / "_nds" / "TWiLightMenu" / "icons"
    box.mkdir(parents=True)
    icons.mkdir(parents=True)
    png = _png_bytes(64, 64)
    (box / "AMCE.png").write_bytes(png)
    (icons / "Mario.nds.png").write_bytes(png)

    monkeypatch.setattr(artwork, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(artwork, "sync_volume", lambda *a, **k: None)
    monkeypatch.setattr("core.steamgriddb.has_api_key", lambda: False)
    monkeypatch.setattr(
        artwork,
        "_fetch_first_ok",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no net")),
    )

    ok, msg = artwork.install_artwork(str(fake_sd))
    assert ok is True
    assert "já existiam" in msg or "1" in msg


def test_generate_twilight_artwork_batch_writes_and_missing(fake_sd, monkeypatch, tmp_path):
    nds = fake_sd / "roms" / "nds"
    nds.mkdir(parents=True)
    make_nds(nds / "Mario.nds", title=b"MARIOKART", code=b"AMCE", maker=b"01")
    make_nds(nds / "Ghost.nds", title=b"GHOSTGAME", code=b"XXXX", maker=b"01")

    png = _png_bytes(64, 64)
    hits = {"n": 0}

    def fake_bytes(url, timeout=None):
        # Só URLs AMCE devolvem PNG; Ghost falha → missing
        if "AMCE" in url:
            hits["n"] += 1
            return png
        return None

    monkeypatch.setattr(artwork, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(artwork, "sync_volume", lambda *a, **k: None)
    monkeypatch.setattr(artwork, "_download_png_bytes", fake_bytes)
    monkeypatch.setattr("core.steamgriddb.has_api_key", lambda: False)

    # Escrita só no mount — nunca em tmp_path do host
    host_before = set(tmp_path.iterdir()) if tmp_path.exists() else set()

    res = artwork.generate_twilight_artwork_batch(str(fake_sd), max_games=50)
    assert res["success"] is True
    assert res["written"] >= 1
    box = fake_sd / "_nds" / "TWiLightMenu" / "boxart" / "AMCE.png"
    assert box.is_file()
    # Sem pasta DSPico tocada
    assert not (fake_sd / "_pico").exists()
    missing = res.get("missing") or []
    assert any(m.get("rel_path", "").endswith("Ghost.nds") for m in missing)
    assert host_before == (set(tmp_path.iterdir()) if tmp_path.exists() else set())
    # Teto de URLs no lote: poucos downloads tentados por jogo em falta
    assert hits["n"] >= 1


def test_twilight_candidates_include_jsdelivr():
    urls = artwork._twilight_candidate_urls(
        "nds", "Mario Kart DS (USA).nds", "AMCE", "boxart"
    )
    assert any("art.gametdb.com" in u for u in urls)
    assert any("thumbnails.libretro.com" in u for u in urls)
    assert any("cdn.jsdelivr.net" in u for u in urls)
    # CDN estáticos: GameTDB → Libretro → jsDelivr
    # (SteamGridDB entra via API, fora desta lista)
    i_gt = next(i for i, u in enumerate(urls) if "gametdb" in u)
    i_lr = next(i for i, u in enumerate(urls) if "thumbnails.libretro.com" in u)
    i_jd = next(i for i, u in enumerate(urls) if "cdn.jsdelivr.net" in u)
    assert i_gt < i_lr < i_jd


def test_fetch_rom_artwork_prefers_steamgriddb(fake_sd, monkeypatch):
    gba = fake_sd / "roms" / "gba"
    gba.mkdir(parents=True)
    rom = gba / "Advance Wars (USA).gba"
    rom.write_bytes(b"GBA" + b"\x00" * 200)
    png = _png_bytes(128, 128)

    monkeypatch.setattr(artwork, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(artwork, "sync_volume", lambda *a, **k: None)
    monkeypatch.setattr("core.steamgriddb.has_api_key", lambda: True)
    monkeypatch.setattr(
        "core.steamgriddb.search_term_from_rom",
        lambda *a, **k: "Advance Wars",
    )
    monkeypatch.setattr(
        "core.steamgriddb.fetch_asset_png_bytes",
        lambda term, kind: png,
    )
    # Libretro não deve ser chamado se SteamGridDB resolver capa e ícone
    monkeypatch.setattr(
        artwork,
        "_fetch_libretro_asset",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no libretro")),
    )

    ok, msg, stats = artwork.fetch_rom_artwork(
        str(fake_sd), "gba/Advance Wars (USA).gba"
    )
    assert ok is True
    assert stats.get("source_boxart") == "steamgriddb"
    assert stats.get("source_icon") == "steamgriddb"
    dest = (
        fake_sd
        / "_nds"
        / "TWiLightMenu"
        / "boxart"
        / "Advance Wars (USA).gba.png"
    )
    assert dest.is_file()
    from core.pico_bmp import decode_png_rgba

    bw, bh, _ = decode_png_rgba(dest.read_bytes())
    assert (bw, bh) == (128, 115)
    icon = (
        fake_sd
        / "_nds"
        / "TWiLightMenu"
        / "icons"
        / "Advance Wars (USA).gba.png"
    )
    assert icon.is_file()
    iw, ih, _ = decode_png_rgba(icon.read_bytes())
    assert (iw, ih) == (32, 32)


def test_twilight_batch_emits_progress_and_caps_urls(fake_sd, monkeypatch):
    nds = fake_sd / "roms" / "nds"
    nds.mkdir(parents=True)
    make_nds(nds / "Mario.nds", title=b"MARIOKART", code=b"AMCE", maker=b"01")

    events = []
    attempts = {"n": 0}

    def fake_bytes(url, timeout=None):
        attempts["n"] += 1
        return None

    monkeypatch.setattr(artwork, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(artwork, "sync_volume", lambda *a, **k: None)
    monkeypatch.setattr(artwork, "_download_png_bytes", fake_bytes)
    monkeypatch.setattr(artwork, "_emit_batch_progress", lambda p: events.append(p))
    monkeypatch.setattr("core.steamgriddb.has_api_key", lambda: False)

    res = artwork.generate_twilight_artwork_batch(str(fake_sd), max_games=10)
    assert res["success"] is True
    assert events
    assert events[-1].get("done") is True
    assert events[-1]["op"] == "twilight_artwork_batch"
    # Capa + ícone, cada um ≤ _BATCH_MAX_URLS
    assert attempts["n"] <= artwork._BATCH_MAX_URLS * 2


def test_fetch_first_ok_returns_fast_winner(monkeypatch):
    import threading
    import time

    png = _png_bytes(16, 16)
    slow_started = threading.Event()
    slow_finished = {"n": 0}

    def fake_bytes(url, timeout=None):
        if "slow" in url:
            slow_started.set()
            time.sleep(0.4)
            slow_finished["n"] += 1
            return None
        # Espera o lento arrancar para garantir corrida real
        slow_started.wait(timeout=1.0)
        return png

    monkeypatch.setattr(artwork, "_download_png_bytes", fake_bytes)
    t0 = time.monotonic()
    data = artwork._fetch_first_ok(
        [
            "https://art.gametdb.com/slow.png",
            "https://art.gametdb.com/fast.png",
        ],
        max_urls=2,
        timeout=2,
        workers=2,
    )
    elapsed = time.monotonic() - t0
    assert data == png
    assert elapsed < 0.35


def test_twilight_batch_skips_complete_games(fake_sd, monkeypatch):
    nds = fake_sd / "roms" / "nds"
    nds.mkdir(parents=True)
    make_nds(nds / "Mario.nds", title=b"MARIOKART", code=b"AMCE", maker=b"01")
    png = _png_bytes(64, 64)
    box = fake_sd / "_nds" / "TWiLightMenu" / "boxart"
    icons = fake_sd / "_nds" / "TWiLightMenu" / "icons"
    box.mkdir(parents=True)
    icons.mkdir(parents=True)
    (box / "AMCE.png").write_bytes(png)
    (icons / "Mario.nds.png").write_bytes(png)

    calls = {"n": 0}

    def boom(*a, **k):
        calls["n"] += 1
        raise AssertionError("não deve descarregar")

    monkeypatch.setattr(artwork, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(artwork, "sync_volume", lambda *a, **k: None)
    monkeypatch.setattr("core.steamgriddb.has_api_key", lambda: False)
    monkeypatch.setattr(artwork, "_fetch_first_ok", boom)

    res = artwork.generate_twilight_artwork_batch(str(fake_sd), max_games=10)
    assert res["success"] is True
    assert res["written"] == 0
    assert res["skipped"] >= 2
    assert calls["n"] == 0


def test_twilight_batch_cancel_midway(fake_sd, monkeypatch):
    from core import progress

    nds = fake_sd / "roms" / "nds"
    nds.mkdir(parents=True)
    make_nds(nds / "A.nds", title=b"GAMEAAAA", code=b"AAAA", maker=b"01")
    make_nds(nds / "B.nds", title=b"GAMEBBBB", code=b"BBBB", maker=b"01")

    progress.begin_operation("twilight_artwork_batch")
    seen = {"n": 0}

    def fake_fetch(urls, **kwargs):
        seen["n"] += 1
        if seen["n"] == 1:
            progress.request_cancel()
        return None

    monkeypatch.setattr(artwork, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(artwork, "sync_volume", lambda *a, **k: None)
    monkeypatch.setattr(artwork, "_fetch_first_ok", fake_fetch)

    try:
        res = artwork.generate_twilight_artwork_batch(str(fake_sd), max_games=10)
    finally:
        progress.end_operation()

    assert res["success"] is False
    assert res.get("cancelled") is True
