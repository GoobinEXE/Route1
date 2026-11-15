"""Vistas de biblioteca da PicoDex: visão por sistema, galeria, capas que faltam, estatísticas."""

from __future__ import annotations

import json
import struct
import zlib

import pytest

from core import library_views as lv
from core import pico_bmp, picodex_rules
from tests.conftest import make_nds


def _png(w=40, h=60, rgb=(200, 30, 30)) -> bytes:
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


@pytest.fixture
def card(fake_sd, monkeypatch):
    monkeypatch.setattr("core.sdio.sync_volume", lambda *a, **k: None)
    (fake_sd / "_pico").mkdir()
    nds = fake_sd / "Games" / "nds"
    nds.mkdir(parents=True)
    make_nds(str(nds / "Mario Kart DS.nds"), title=b"MARIOKARTDS", code=b"AMCE", maker=b"01")
    make_nds(str(nds / "Unknown Thing.nds"), title=b"UNKNOWN", code=b"ZZZZ", maker=b"01")
    gb = fake_sd / "Games" / "gb"
    gb.mkdir()
    (gb / "Tetris.gb").write_bytes(b"GB")
    (gb / "Pokemon Yellow.gbc").write_bytes(b"GBC")
    covers = fake_sd / "_pico" / "covers" / "user"
    covers.mkdir(parents=True)
    (covers / "Tetris.gb.bmp").write_bytes(pico_bmp.rgba_to_cover_bmp(2, 2, bytes([1, 2, 3, 255] * 4)))
    (fake_sd / "_pico" / "gamedata.json").write_text(
        json.dumps({"games": {
            "Mario Kart DS.nds": {"favorite": True, "launchCount": 5, "playMinutes": 90, "lastPlayed": "2026-11-01 10:00"},
            "Tetris.gb": {"launchCount": 2, "playMinutes": 10, "lastPlayed": "2026-11-02 10:00"},
        }}),
        encoding="utf-8",
    )
    return fake_sd


def test_library_overview_counts_systems_covers_and_shared_folders(card):
    ov = lv.library_overview(str(card))
    assert ov["totals"] == {"games": 4, "systems": 3, "favorites": 1, "minutes": 100, "covered": 1}
    by_id = {s["id"]: s for s in ov["systems"]}
    assert by_id["nds"]["count"] == 2 and by_id["nds"]["covered"] == 0
    assert by_id["gb"]["covered"] == 1 and by_id["gb"]["folder"] == "Games/gb"
    assert by_id["gb"]["shares_folder_with"] == ["Game Boy Color"]
    assert "api_version" in ov["loader"]


def test_system_gallery_and_covers(card):
    g = lv.system_gallery(str(card), "nds")
    assert [x["title"] for x in g["games"]] == ["Mario Kart DS", "Unknown Thing"]
    mk = g["games"][0]
    assert mk["favorite"] and mk["launchCount"] == 5 and mk["game_code"] == "AMCE"
    covers = lv.gallery_covers(str(card), ["Games/gb/Tetris.gb", "Games/nds/Mario Kart DS.nds", "../x"])
    assert covers["covers"]["Games/gb/Tetris.gb"].startswith("data:image/png")
    assert covers["covers"]["Games/nds/Mario Kart DS.nds"] is None
    assert lv.system_gallery(str(card), "psx")["success"] is False


def test_missing_covers_and_fetch_writes_only_exact_matches(card, monkeypatch):
    miss = lv.missing_covers(str(card))
    assert {m["rel"] for m in miss["missing"]} == {
        "Games/nds/Mario Kart DS.nds", "Games/nds/Unknown Thing.nds", "Games/gb/Pokemon Yellow.gbc"
    }
    catalogs = {
        "Nintendo_-_Nintendo_DS": ["Mario Kart DS (USA, Australia).png", "Mario Party DS (USA).png"],
        "Nintendo_-_Game_Boy_Color": ["Pokemon - Yellow Version (USA, Europe).png"],
    }
    monkeypatch.setattr(picodex_rules, "fetch_catalog", lambda repo, kind="boxarts", **k: catalogs.get(repo, []))
    monkeypatch.setattr("core.pico_artwork._http_get", lambda url, timeout=0: _png())
    out = lv.fetch_missing_covers(str(card), [m["rel"] for m in miss["missing"]])
    status = {r["rel"]: r["status"] for r in out["results"]}
    assert status["Games/nds/Mario Kart DS.nds"] == "written"
    # Sem par exato no catálogo: fica sem capa em vez de ganhar a de outro jogo.
    assert status["Games/nds/Unknown Thing.nds"] == "no-match"
    assert (card / "_pico" / "covers" / "nds" / "AMCE.bmp").is_file()
    assert not (card / "_pico" / "icons").exists()  # nunca grava ícones
    written = (card / "_pico" / "covers" / "nds" / "AMCE.bmp").read_bytes()
    assert pico_bmp.validate_launcher_cover_bmp(written) is None
    # Segunda passada não sobrescreve.
    again = lv.fetch_missing_covers(str(card), ["Games/nds/Mario Kart DS.nds"])
    assert again["results"] == []


def test_play_stats_has_favorites_and_rels(card):
    st = lv.play_stats(str(card))
    assert st["totals"]["launches"] == 7
    assert st["top"][0]["fileName"] == "Mario Kart DS.nds" and st["top"][0]["rel"] == "Games/nds/Mario Kart DS.nds"
    assert [f["fileName"] for f in st["favorites"]] == ["Mario Kart DS.nds"]
    by_name = lv.gallery_covers_by_name(str(card), ["Tetris.gb"])
    assert by_name["covers"]["Tetris.gb"].startswith("data:image/png")
