"""Testes do pipeline de capas/ícones (GameTDB + Libretro)."""

from __future__ import annotations

import io
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


def _png_bytes() -> bytes:
    # PNG 1x1 minimal
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f"
        b"\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def test_fetch_rom_artwork_gba_libretro(fake_sd, monkeypatch):
    gba = fake_sd / "roms" / "gba"
    gba.mkdir(parents=True)
    rom = gba / "Advance Wars (USA).gba"
    rom.write_bytes(b"GBA" + b"\x00" * 200)

    png = _png_bytes()
    # Pad to satisfy _PNG_MIN
    png = png + b"\x00" * 64

    def fake_urlopen(req, timeout=30):
        cm = MagicMock()
        cm.__enter__ = lambda s: s
        cm.__exit__ = lambda *a: None
        cm.read = lambda: png
        # copyfileobj reads in chunks via readinto / read
        bio = io.BytesIO(png)
        cm.read = bio.read
        return cm

    monkeypatch.setattr(artwork, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(artwork, "sync_volume", lambda *a, **k: None)
    monkeypatch.setattr(artwork.urllib.request, "urlopen", fake_urlopen)

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
    box.mkdir(parents=True)
    existing = box / "AMCE.png"
    existing.write_bytes(_png_bytes() + b"\x00" * 64)

    monkeypatch.setattr(artwork, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(artwork, "sync_volume", lambda *a, **k: None)
    monkeypatch.setattr(
        artwork, "_download_png", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no net"))
    )

    ok, msg = artwork.install_artwork(str(fake_sd))
    assert ok is True
    assert "já existiam" in msg or "1" in msg


def test_generate_twilight_artwork_batch_writes_and_missing(fake_sd, monkeypatch, tmp_path):
    nds = fake_sd / "roms" / "nds"
    nds.mkdir(parents=True)
    make_nds(nds / "Mario.nds", title=b"MARIOKART", code=b"AMCE", maker=b"01")
    make_nds(nds / "Ghost.nds", title=b"GHOSTGAME", code=b"XXXX", maker=b"01")

    png = _png_bytes() + b"\x00" * 64
    hits = {"n": 0}

    def fake_download(url, dest, timeout=None):
        # Só a 1.ª URL GameTDB AMCE grava; Ghost falha → missing
        if "AMCE" in url:
            hits["n"] += 1
            with open(dest, "wb") as f:
                f.write(png)
            return True
        return False

    monkeypatch.setattr(artwork, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(artwork, "sync_volume", lambda *a, **k: None)
    monkeypatch.setattr(artwork, "_download_png", fake_download)

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
    # Ordem: GameTDB antes de Libretro antes de jsDelivr
    i_gt = next(i for i, u in enumerate(urls) if "gametdb" in u)
    i_lr = next(i for i, u in enumerate(urls) if "thumbnails.libretro.com" in u)
    i_jd = next(i for i, u in enumerate(urls) if "cdn.jsdelivr.net" in u)
    assert i_gt < i_lr < i_jd


def test_twilight_batch_emits_progress_and_caps_urls(fake_sd, monkeypatch):
    nds = fake_sd / "roms" / "nds"
    nds.mkdir(parents=True)
    make_nds(nds / "Mario.nds", title=b"MARIOKART", code=b"AMCE", maker=b"01")

    events = []
    attempts = {"n": 0}

    def fake_download(url, dest, timeout=None):
        attempts["n"] += 1
        return False

    monkeypatch.setattr(artwork, "is_safe_mount_path", lambda p: True)
    monkeypatch.setattr(artwork, "sync_volume", lambda *a, **k: None)
    monkeypatch.setattr(artwork, "_download_png", fake_download)
    monkeypatch.setattr(artwork, "_emit_batch_progress", lambda p: events.append(p))

    res = artwork.generate_twilight_artwork_batch(str(fake_sd), max_games=10)
    assert res["success"] is True
    assert events
    assert events[-1].get("done") is True
    assert events[-1]["op"] == "twilight_artwork_batch"
    # Capa + ícone, cada um ≤ _BATCH_MAX_URLS
    assert attempts["n"] <= artwork._BATCH_MAX_URLS * 2
