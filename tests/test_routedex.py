"""RouteDex: gamedata sem perdas, saúde do cartão, capturas, banners, noturno, cheats."""

from __future__ import annotations

import io
import json
import os
import struct
import zipfile

import pytest

from core import routedex, updates
from tests.conftest import make_nds


@pytest.fixture(autouse=True)
def _host_backup(tmp_path, monkeypatch):
    monkeypatch.setattr(routedex, "CACHE_DIR", str(tmp_path / "host_cache"))


def _card(sd):
    (sd / "_pico").mkdir(exist_ok=True)
    (sd / "Games").mkdir(exist_ok=True)
    return sd


def _write(path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


# --- gamedata.json ---------------------------------------------------------


def test_gamedata_roundtrip_is_lossless_and_launcher_formatted(fake_sd):
    sd = _card(fake_sd)
    original = {
        "games": {
            "Mario Kart DS.nds": {"gameCode": "AMCE", "favorite": True, "launchCount": 3, "futureField": [1, 2]},
            "Empty.nds": {},
        },
        "sessionGame": "Mario Kart DS.nds",
        "sessionStart": "2026-11-12T20:00:00",
        "launcherOnly": {"x": 1},
    }
    (sd / "_pico" / "gamedata.json").write_text(json.dumps(original, indent=2).replace("\n", "\r\n"))
    data, exists = routedex.load_gamedata(str(sd))
    assert exists
    routedex.save_gamedata(str(sd), data)
    raw = (sd / "_pico" / "gamedata.json").read_bytes()
    assert b"\r\n" in raw and not raw.endswith(b"\n")
    out = json.loads(raw)
    # Campos desconhecidos e chaves de raiz sobrevivem; entrada vazia é podada.
    assert out["games"]["Mario Kart DS.nds"]["futureField"] == [1, 2]
    assert out["launcherOnly"] == {"x": 1}
    assert out["sessionStart"] == "2026-11-12T20:00:00"
    assert "Empty.nds" not in out["games"]


def test_invalid_gamedata_is_never_overwritten(fake_sd):
    sd = _card(fake_sd)
    make_nds(str(sd / "Games" / "Game.nds"), code=b"ABCE")
    bad = b'{"games": {broken'
    (sd / "_pico" / "gamedata.json").write_bytes(bad)
    with pytest.raises(routedex.RouteDexError):
        routedex.toggle_flag(str(sd), "Games/Game.nds", "favorite")
    assert (sd / "_pico" / "gamedata.json").read_bytes() == bad
    assert routedex.gamedata_overview(str(sd))["parse_error"]


def test_toggle_and_stats_match_case_insensitively_and_record_gamecode(fake_sd):
    sd = _card(fake_sd)
    make_nds(str(sd / "Games" / "Zelda.nds"), code=b"AZEE")
    (sd / "_pico" / "gamedata.json").write_text('{"games": {"ZELDA.NDS": {"launchCount": 1}}}')
    out = routedex.toggle_flag(str(sd), "Games/Zelda.nds", "favorite")
    assert out["entry"]["favorite"] is True
    routedex.set_stats(str(sd), "Games/Zelda.nds", "12", 90)
    games = json.loads((sd / "_pico" / "gamedata.json").read_bytes())["games"]
    assert list(games) == ["ZELDA.NDS"]
    assert games["ZELDA.NDS"] == {"gameCode": "AZEE", "favorite": True, "launchCount": 12, "playMinutes": 90}
    with pytest.raises(routedex.RouteDexError):
        routedex.set_stats(str(sd), "Games/Zelda.nds", -1, 0)


def test_homebrew_placeholder_code_is_not_recorded(fake_sd):
    sd = _card(fake_sd)
    make_nds(str(sd / "Games" / "hb.nds"), code=b"####")
    routedex.toggle_flag(str(sd), "Games/hb.nds", "completed")
    games = json.loads((sd / "_pico" / "gamedata.json").read_bytes())["games"]
    assert games == {"hb.nds": {"completed": True}}


def test_overview_joins_library_and_reports_stale(fake_sd):
    sd = _card(fake_sd)
    make_nds(str(sd / "Games" / "A.nds"), code=b"AAAE")
    (sd / "_pico" / "gamedata.json").write_text(
        '{"games": {"A.nds": {"launchCount": 2, "playMinutes": 30, "lastPlayed": "2026-11-10T10:00:00"},'
        ' "Gone.nds": {"favorite": true}}}'
    )
    ov = routedex.gamedata_overview(str(sd))
    assert [g["name"] for g in ov["library"]] == ["A.nds"]
    assert ov["library"][0]["launchCount"] == 2
    assert [e["fileName"] for e in ov["stale"]] == ["Gone.nds"]
    assert ov["totals"] == {"played": 1, "favorites": 1, "completed": 0, "launches": 2, "minutes": 30}
    assert routedex.prune_stale_entries(str(sd), ["Gone.nds", "A.nds"])["removed"] == 1


def test_path_traversal_is_rejected(fake_sd):
    sd = _card(fake_sd)
    with pytest.raises(routedex.RouteDexError):
        routedex.resolve_card_path(str(sd), "../outside.nds")


# --- versões ---------------------------------------------------------------


def _manifest(monkeypatch, data):
    monkeypatch.setattr(routedex, "_manifest_cache", data)


def test_identify_loader_official_mixed_and_enhanced(fake_sd, monkeypatch):
    sd = _card(fake_sd)
    files = {n: n.encode() * 4 for n in routedex.LOADER_HASHED_FILES}
    for n, b in files.items():
        _write(sd / "_pico" / n, b)
    h = {n: routedex._sha256_file(str(sd / "_pico" / n)) for n in files}
    manifest = {
        "loader": {
            "releases": [{"tag": "v1.0.0"}, {"tag": "v1.1.0"}, {"tag": "v1.2.0"}],
            "files": {n: {h[n]: ["v1.1.0"]} for n in files},
            "builds": {n: {h[n]: ["DSPICO"]} for n in files},
        },
        "loader_enhanced": {"files": {}},
    }
    _manifest(monkeypatch, manifest)
    res = routedex.identify_loader(str(sd))
    assert res["status"] == "identified" and res["candidates"] == ["v1.1.0"]
    assert res["releases_behind"] == 1 and res["variant"] == "official" and res["builds"] == ["DSPICO"]

    manifest["loader"]["files"]["aplist.bin"] = {h["aplist.bin"]: ["v1.2.0"]}
    res = routedex.identify_loader(str(sd))
    assert res["status"] == "mixed" and res["mismatch"]["odd_ones_out"] == ["aplist.bin"]

    manifest["loader"]["files"]["aplist.bin"] = {h["aplist.bin"]: ["v1.1.0"]}
    _write(sd / "_pico" / "picoLoader9.bin", b"\x00Pico Loader Enhanced v1.0.1 - unofficial build\x00")
    _write(sd / "_pico" / "picoLoader7.bin", b"enhanced arm7")
    res = routedex.identify_loader(str(sd))
    assert res["variant"] == "enhanced" and res["enhanced_version"] == "v1.0.1"
    assert res["enhanced_files"] == ["picoLoader7.bin", "picoLoader9.bin"]
    assert res["status"] == "identified" and res["candidates"] == ["v1.1.0"]


def test_identify_launcher_by_hash_and_marker(fake_sd, monkeypatch):
    sd = _card(fake_sd)
    _write(sd / "_picoboot.nds", b"stock launcher")
    digest = routedex._sha256_file(str(sd / "_picoboot.nds"))
    _manifest(monkeypatch, {"launcher": {"official": {digest: "v1.3.0"}, "enhanced": {}}})
    assert routedex.identify_launcher(str(sd)) == {"present": True, "variant": "official", "version": "v1.3.0", "known": True}
    _write(sd / "_picoboot.nds", b"...rasalopa/pico-launcher-enhanced...")
    assert routedex.identify_launcher(str(sd))["variant"] == "enhanced"


def test_shipped_manifest_knows_pinned_releases():
    m = routedex.load_manifest()
    assert "v1.3.0" in m["launcher"]["official"].values()
    assert "enhanced-v1.11.0" in m["launcher"]["enhanced"].values()
    assert "v1.6.0" in [r["tag"] for r in m["loader"]["releases"]]


# --- saúde -----------------------------------------------------------------


def test_health_finds_junk_orphans_and_duplicates_and_removes_with_backup(fake_sd):
    sd = _card(fake_sd)
    make_nds(str(sd / "Games" / "Kept.nds"), code=b"KEPE")
    _write(sd / "Games" / "Kept.sav", b"s")
    _write(sd / "Games" / "saves" / "Kept.sav", b"s2")
    _write(sd / "Games" / "Lost.sav", b"orphan")
    _write(sd / "Games" / "._Kept.nds", b"junk")
    _write(sd / ".fseventsd" / "no_log", b"")
    _write(sd / ".Spotlight-V100" / "x", b"")
    _write(sd / "_pico" / "covers" / "user" / "Gone.nds.bmp", b"BM")
    rep = routedex.check_health(str(sd))
    assert rep["orphan_saves"] == ["Games/Lost.sav"]
    assert rep["duplicate_saves"][0]["in_folder"] == "Games/saves/Kept.sav"
    assert "Games/._Kept.nds" in rep["junk"] and ".Spotlight-V100" in rep["junk"]
    assert ".fseventsd" not in rep["junk"]
    assert rep["orphan_art"] == ["_pico/covers/user/Gone.nds.bmp"]
    assert "picoLoader7.bin" in rep["missing_required"]

    with pytest.raises(routedex.RouteDexError):
        routedex.remove_card_items(str(sd), ["Games/Kept.sav"])
    out = routedex.remove_card_items(str(sd), ["Games/Lost.sav"])
    assert out["removed"] == ["Games/Lost.sav"] and not (sd / "Games" / "Lost.sav").exists()
    backups = [os.path.join(r, f) for r, _d, fs in os.walk(routedex.CACHE_DIR) for f in fs]
    assert any(p.endswith(os.path.join("Games", "Lost.sav")) for p in backups)


# --- capturas --------------------------------------------------------------


def _bmp24(w, h, rgb):
    row = (bytes((rgb[2], rgb[1], rgb[0])) * w).ljust(((w * 3 + 3) // 4) * 4, b"\x00")
    img = row * h
    hdr = b"BM" + struct.pack("<IHHI", 54 + len(img), 0, 0, 54)
    info = struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0, len(img), 0, 0, 0, 0)
    return hdr + info + img


def test_screenshots_pair_preview_and_delete(fake_sd):
    sd = _card(fake_sd)
    shots = sd / "_pico" / "screenshots"
    _write(shots / "shot001_top.bmp", _bmp24(4, 2, (255, 0, 0)))
    _write(shots / "shot001_bot.bmp", _bmp24(4, 2, (0, 0, 255)))
    _write(shots / "loose.bmp", _bmp24(2, 2, (0, 255, 0)))
    listed = routedex.list_screenshots(str(sd))["shots"]
    assert [s["id"] for s in listed] == ["001", "loose.bmp"]
    from core.pico_bmp import decode_png_rgba

    w, h, px = decode_png_rgba(routedex.screenshot_png(str(sd), "001"))
    assert (w, h) == (4, 4)
    assert px[:4] == bytes((255, 0, 0, 255)) and px[-4:] == bytes((0, 0, 255, 255))
    routedex.delete_screenshot(str(sd), "001")
    assert not (shots / "shot001_top.bmp").exists() and not (shots / "shot001_bot.bmp").exists()


# --- banners de pasta ------------------------------------------------------


def test_folder_banner_from_rom_has_valid_crc_and_title(fake_sd):
    sd = _card(fake_sd)
    folder = sd / "Games" / "Racing"
    rom = folder / "Kart.nds"
    folder.mkdir(parents=True)
    make_nds(str(rom), code=b"AMCE", payload=b"\x00" * 0x400)
    raw = bytearray(rom.read_bytes())
    struct.pack_into("<I", raw, 0x68, 0x200)
    raw[0x220:0x420] = bytes(range(256)) * 2
    raw[0x420:0x440] = bytes(range(32))
    rom.write_bytes(bytes(raw))

    routedex.write_folder_banner(str(sd), "Games/Racing", "Corridas", rom_name="Kart.nds")
    bnr = (folder / "banner.bnr").read_bytes()
    assert len(bnr) == 0x840
    info = routedex.parse_banner(bnr)
    assert info["title"] == "Corridas" and info["crc_ok"]
    assert info["bitmap"] == bytes(range(256)) * 2
    assert routedex.folder_art_status(str(sd), "Games/Racing")["banner"]["title"] == "Corridas"
    with pytest.raises(routedex.RouteDexError):
        routedex.write_folder_banner(str(sd), "", "Raiz", rom_name="Kart.nds")


def test_icon_encode_decode_roundtrip():
    rgba = bytearray(32 * 32 * 4)
    for y in range(32):
        for x in range(32):
            if (x + y) % 3:
                o = (y * 32 + x) * 4
                rgba[o : o + 4] = bytes((248, 0, 0, 255)) if x < 16 else bytes((0, 248, 0, 255))
    bitmap, palette = routedex.encode_icon_rgba(bytes(rgba))
    assert struct.unpack_from("<H", palette, 0)[0] == 0x7C1F
    back = routedex.decode_icon_rgba(bitmap, palette)
    assert back[3] == 0  # (0,0) transparente
    assert back[(0 * 32 + 1) * 4 : (0 * 32 + 1) * 4 + 4] == bytes((255, 0, 0, 255))


# --- fundos noturnos -------------------------------------------------------


def test_night_backgrounds_match_enhanced_formula(fake_sd):
    sd = _card(fake_sd)
    theme = sd / "_pico" / "themes" / "Mine"
    color = 0x8000 | 31 | (31 << 5) | (31 << 10)
    _write(theme / "topbg.bin", struct.pack("<H", color) * (256 * 192))
    routedex.generate_night_backgrounds(str(sd), "Mine")
    night = struct.unpack_from("<H", (theme / "topbg_night.bin").read_bytes(), 0)[0]
    assert night == 0x8000 | 12 | (14 << 5) | (22 << 10)
    assert not (theme / "bottombg_night.bin").exists()
    assert routedex.list_night_themes(str(sd))["themes"][0]["night"]["topbg"] is True
    with pytest.raises(routedex.RouteDexError):
        routedex.generate_night_backgrounds(str(sd), "../Mine")


# --- cheats ----------------------------------------------------------------


def _usrcheat(codes):
    head = bytearray(0x100)
    head[:16] = b"R4 CheatCode\x00\x01\x00\x00"
    head[0x10:0x10 + 9] = b"Test base"
    table = b""
    data_off = 0x100 + 16 * (len(codes) + 1)
    for c in codes:
        table += struct.pack("<4sIII", c, 0, data_off, 0)
    table += b"\x00" * 16
    return bytes(head) + table + b"\x00" * 32


def test_cheats_import_validates_and_counts_card_games(fake_sd, tmp_path):
    sd = _card(fake_sd)
    make_nds(str(sd / "Games" / "Kart.nds"), code=b"AMCE")
    make_nds(str(sd / "Games" / "Other.nds"), code=b"ZZZE")
    good = _write(tmp_path / "usrcheat.dat", _usrcheat([b"AMCE", b"ASME"]))
    bad = _write(tmp_path / "bad.dat", b"not a cheat db" * 30)
    with pytest.raises(routedex.RouteDexError):
        routedex.import_usrcheat(str(sd), str(bad))
    assert routedex.import_usrcheat(str(sd), str(good))["games"] == 2
    st = routedex.cheats_status(str(sd))
    assert st["valid"] and st["name"] == "Test base"
    assert st["card_games_with_cheats"] == 1 and st["card_nds_games"] == 2


# --- Enhanced como variante opcional (core.updates) ------------------------


def _zip(members):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_enhanced_loader_installs_only_binaries_and_needs_official_lists(fake_sd, tmp_path, monkeypatch):
    sd = _card(fake_sd)
    monkeypatch.setattr(updates, "CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(updates, "is_safe_mount_path", lambda _p: True)
    monkeypatch.setattr(updates, "sync_volume", lambda *_a, **_k: None)
    pkg = _write(tmp_path / "enh.zip", _zip({"_pico/picoLoader7.bin": b"E7", "_pico/picoLoader9.bin": b"E9"}))

    with pytest.raises(RuntimeError, match="oficial"):
        updates._install_loader_from_zip(str(sd), str(pkg), lambda _m: None, binaries_only=True)

    _write(sd / "_pico" / "aplist.bin", b"AP")
    _write(sd / "_pico" / "savelist.bin", b"SL")
    out = updates._install_loader_from_zip(str(sd), str(pkg), lambda _m: None, binaries_only=True)
    assert out["success"]
    assert (sd / "_pico" / "picoLoader9.bin").read_bytes() == b"E9"
    assert (sd / "_pico" / "aplist.bin").read_bytes() == b"AP"


def test_variant_version_label():
    assert updates._variant_version_label("Pico_Loader_Enhanced_v1.0.1.zip", "enhanced-v1.11.0") == "v1.0.1"
    assert updates._variant_version_label("Pico_Launcher_Enhanced.zip", "enhanced-v1.11.0") == "v1.11.0"


def test_enhanced_variant_is_opt_in_and_allowlisted():
    with pytest.raises(ValueError):
        updates._variant_meta("dspico-firmware", "enhanced")
    assert updates._variant_meta("pico-launcher", "official")["repo"] == "LNH-team/pico-launcher"
    assert updates._variant_meta("pico-loader", "enhanced")["cache_key"] == "pico_loader_enhanced_dspico"
    assert updates._is_allowed_url("https://github.com/rasalopa/pico-launcher-enhanced/releases/download/x/a.zip")
    assert not updates._is_allowed_url("https://github.com/rasalopa/other/releases/download/x/a.zip")
    res = updates.install_dspico_component("/nonexistent", "pico-launcher", "pinned", variant="bogus")
    assert res["success"] is False
