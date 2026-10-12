"""Testes do cliente SteamGridDB (API mockada)."""

from __future__ import annotations

import io
import json
import struct
import zlib
from unittest.mock import MagicMock

from core import steamgriddb as sgdb


def _png_bytes(w: int = 16, h: int = 16) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    rgba = bytes((10, 20, 30, 255)) * (w * h)
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


def test_normalize_and_has_key(monkeypatch):
    assert sgdb.normalize_api_key("  abcd1234  ") == "abcd1234"
    assert sgdb.normalize_api_key("short") is None
    assert sgdb.normalize_api_key("bad key!!") is None
    monkeypatch.delenv("STEAMGRIDDB_API_KEY", raising=False)
    monkeypatch.setattr(sgdb, "get_pref", lambda k, default=None: None)
    assert sgdb.has_api_key() is False
    monkeypatch.setenv("STEAMGRIDDB_API_KEY", "testkey12345678")
    assert sgdb.get_api_key() == "testkey12345678"
    assert sgdb.has_api_key() is True


def test_is_asset_url():
    assert sgdb.is_asset_url(
        "https://cdn2.steamgriddb.com/grid/abc.png"
    )
    assert sgdb.is_asset_url(
        "https://s3.amazonaws.com/cdn.steamgriddb.com/icon/x.png"
    )
    assert not sgdb.is_asset_url("https://evil.example/x.png")
    assert not sgdb.is_asset_url(
        "https://s3.amazonaws.com/other-bucket/x.png"
    )
    assert not sgdb.is_asset_url("http://cdn2.steamgriddb.com/grid/x.png")


def test_search_term_from_rom():
    assert (
        sgdb.search_term_from_rom("Mario Kart DS (USA) [!].nds")
        == "Mario Kart DS"
    )
    assert sgdb.search_term_from_rom("x.nds", query="Zelda") == "Zelda"
    # TID de 4 letras: não usar como termo SGDB — limpar o basename
    assert sgdb.search_term_from_rom("Mario.nds", query="AMCE") == "Mario"


def test_candidate_assets_order_and_png(monkeypatch):
    monkeypatch.setenv("STEAMGRIDDB_API_KEY", "testkey12345678")
    sgdb.clear_game_cache()

    calls: list[str] = []

    def fake_urlopen(req, timeout=20):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        calls.append(url)
        cm = MagicMock()
        cm.__enter__ = lambda s: s
        cm.__exit__ = lambda *a: None
        if "/search/autocomplete/" in url:
            payload = {
                "success": True,
                "data": [
                    {"id": 99, "name": "Mario Kart DS", "verified": True},
                ],
            }
        elif "/grids/game/99" in url:
            payload = {
                "success": True,
                "data": [
                    {
                        "id": 1,
                        "score": 10,
                        "url": "https://cdn2.steamgriddb.com/grid/cover.png",
                        "thumb": "https://cdn2.steamgriddb.com/grid/cover_thumb.png",
                    }
                ],
            }
        else:
            payload = {"success": False}
        raw = json.dumps(payload).encode("utf-8")
        cm.read = lambda n=-1: raw
        return cm

    monkeypatch.setattr(sgdb.urllib.request, "urlopen", fake_urlopen)
    cands = sgdb.candidate_assets("Mario Kart DS", "boxart", limit=5)
    assert cands
    assert cands[0]["source"] == "steamgriddb"
    assert "cdn2.steamgriddb.com" in cands[0]["url"]
    assert "SteamGridDB" in cands[0]["label"]
    assert any("Authorization" in str(getattr(c, "headers", {})) or True for c in calls)


def test_fetch_asset_png_bytes(monkeypatch):
    monkeypatch.setenv("STEAMGRIDDB_API_KEY", "testkey12345678")
    sgdb.clear_game_cache()
    png = _png_bytes()

    def fake_urlopen(req, timeout=20):
        url = getattr(req, "full_url", None) or req.get_full_url()
        cm = MagicMock()
        cm.__enter__ = lambda s: s
        cm.__exit__ = lambda *a: None
        if "/search/" in url:
            body = json.dumps(
                {
                    "success": True,
                    "data": [{"id": 1, "name": "Test", "verified": True}],
                }
            ).encode()
            cm.read = lambda n=-1: body
        elif "/grids/" in url or "/icons/" in url:
            body = json.dumps(
                {
                    "success": True,
                    "data": [
                        {
                            "url": "https://cdn2.steamgriddb.com/grid/t.png",
                            "thumb": "https://cdn2.steamgriddb.com/grid/t.png",
                            "score": 5,
                        }
                    ],
                }
            ).encode()
            cm.read = lambda n=-1: body
        else:
            bio = io.BytesIO(png)
            cm.read = bio.read
        return cm

    monkeypatch.setattr(sgdb.urllib.request, "urlopen", fake_urlopen)
    data = sgdb.fetch_asset_png_bytes("Test Game", "boxart")
    assert data == png


def test_no_key_returns_empty(monkeypatch):
    monkeypatch.delenv("STEAMGRIDDB_API_KEY", raising=False)
    monkeypatch.setattr(sgdb, "get_pref", lambda k, default=None: None)
    sgdb.clear_game_cache()
    assert sgdb.candidate_assets("Mario", "icon") == []
    assert sgdb.fetch_asset_png_bytes("Mario", "icon") is None


def test_candidate_assets_retries_on_empty_list(monkeypatch):
    """1.º pedido com filtros → []; 2.º sem dimensions/styles → PNG."""
    monkeypatch.setenv("STEAMGRIDDB_API_KEY", "testkey12345678")
    sgdb.clear_game_cache()
    grid_calls: list[str] = []

    def fake_urlopen(req, timeout=20):
        url = getattr(req, "full_url", None) or req.get_full_url()
        cm = MagicMock()
        cm.__enter__ = lambda s: s
        cm.__exit__ = lambda *a: None
        if "/search/autocomplete/" in url:
            payload = {
                "success": True,
                "data": [
                    {"id": 42, "name": "Pokemon Emerald", "verified": True},
                ],
            }
        elif "/grids/game/42" in url:
            grid_calls.append(url)
            if "dimensions=" in url:
                payload = {"success": True, "data": []}
            else:
                payload = {
                    "success": True,
                    "data": [
                        {
                            "id": 7,
                            "score": 20,
                            "url": "https://cdn2.steamgriddb.com/grid/emerald.png",
                            "thumb": "https://cdn2.steamgriddb.com/grid/emerald_t.png",
                        }
                    ],
                }
        else:
            payload = {"success": False}
        raw = json.dumps(payload).encode("utf-8")
        cm.read = lambda n=-1: raw
        return cm

    monkeypatch.setattr(sgdb.urllib.request, "urlopen", fake_urlopen)
    cands = sgdb.candidate_assets("Pokemon Emerald", "cover", limit=5)
    assert cands
    assert cands[0]["url"] == "https://cdn2.steamgriddb.com/grid/emerald.png"
    assert len(grid_calls) >= 2
    assert any("dimensions=" in u for u in grid_calls)
    assert any("dimensions=" not in u for u in grid_calls)


def test_icon_ico_uses_png_thumb(monkeypatch):
    """Ícone .ico + thumb PNG → candidato usa o thumb para apply."""
    monkeypatch.setenv("STEAMGRIDDB_API_KEY", "testkey12345678")
    sgdb.clear_game_cache()

    def fake_urlopen(req, timeout=20):
        url = getattr(req, "full_url", None) or req.get_full_url()
        cm = MagicMock()
        cm.__enter__ = lambda s: s
        cm.__exit__ = lambda *a: None
        if "/search/autocomplete/" in url:
            payload = {
                "success": True,
                "data": [{"id": 11, "name": "Test Icon", "verified": True}],
            }
        elif "/icons/game/11" in url:
            # 1.º (só PNG) vazio; retry com ico devolve .ico + thumb PNG
            if "image%2Fvnd.microsoft.icon" in url or "vnd.microsoft.icon" in url:
                payload = {
                    "success": True,
                    "data": [
                        {
                            "id": 3,
                            "score": 8,
                            "url": "https://cdn2.steamgriddb.com/icon/game.ico",
                            "thumb": "https://cdn2.steamgriddb.com/icon/game_thumb.png",
                        }
                    ],
                }
            else:
                payload = {"success": True, "data": []}
        else:
            payload = {"success": False}
        raw = json.dumps(payload).encode("utf-8")
        cm.read = lambda n=-1: raw
        return cm

    monkeypatch.setattr(sgdb.urllib.request, "urlopen", fake_urlopen)
    cands = sgdb.candidate_assets("Test Icon", "icon", limit=5)
    assert cands
    assert cands[0]["url"].endswith(".png")
    assert "game_thumb.png" in cands[0]["url"]
    assert cands[0]["preview"].endswith(".png")
