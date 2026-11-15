"""Garantias das fontes oficiais (core/upstreams.py) e das regras portadas da PicoDex."""

from __future__ import annotations

import hashlib
import json
import os

import pytest

from core import cache_pins, picodex_rules, routedex, updates, upstreams

EXPECTED_REPOS = {
    "picodex": "rasalopa/picodex",
    "pico_launcher": "LNH-team/pico-launcher",
    "pico_loader": "LNH-team/pico-loader",
    "pico_launcher_enhanced": "rasalopa/pico-launcher-enhanced",
    "pico_loader_enhanced": "rasalopa/pico-loader",
}


# --- registro e lock -------------------------------------------------------


def test_registry_is_exactly_the_five_official_repos():
    assert {k: v["repo"] for k, v in upstreams.UPSTREAMS.items()} == EXPECTED_REPOS


def test_lock_covers_every_upstream_with_matching_repo():
    lock = upstreams.load_lock()
    for uid, repo in EXPECTED_REPOS.items():
        entry = lock[uid]
        assert entry["repo"] == repo
        assert entry["tag"]
        if "files" in upstreams.UPSTREAMS[uid]:
            assert entry["commit"] and len(entry["commit"]) == 40
        else:
            assert len(entry["sha256"]) == 64 and entry["asset"].endswith(".zip")


def test_dspico_package_pins_come_only_from_the_lock():
    assets = upstreams.pinned_assets()
    assert set(assets) == {"pico_launcher", "pico_loader_dspico", "pico_launcher_enhanced", "pico_loader_enhanced_dspico"}
    for key, pin in assets.items():
        assert cache_pins.PINNED_SHA256[key] == pin["sha256"]
        assert cache_pins.URLS[key] == pin["url"]
        assert cache_pins.URLS[key].startswith(f"https://github.com/{pin['repo']}/releases/download/")
        assert pin["repo"] in upstreams.OFFICIAL_REPOS


def test_vendored_picodex_files_match_lock():
    entry = upstreams.lock_entry("picodex")
    for name, meta in entry["files"].items():
        with open(upstreams.picodex_data_path(name), "rb") as f:
            assert hashlib.sha256(f.read()).hexdigest() == meta["sha256"], name


def test_updates_use_registry_repos_and_reject_others():
    assert updates._COMPONENTS["pico-launcher"]["repo"] == EXPECTED_REPOS["pico_launcher"]
    assert updates._COMPONENTS["pico-loader"]["repo"] == EXPECTED_REPOS["pico_loader"]
    assert updates._COMPONENTS["pico-launcher"]["variants"]["enhanced"]["repo"] == EXPECTED_REPOS["pico_launcher_enhanced"]
    assert updates._COMPONENTS["pico-loader"]["variants"]["enhanced"]["repo"] == EXPECTED_REPOS["pico_loader_enhanced"]
    assert updates._COMPONENTS["picodex"]["repo"] == EXPECTED_REPOS["picodex"]
    for repo in EXPECTED_REPOS.values():
        assert updates._is_allowed_url(f"https://github.com/{repo}/releases/download/t/a.zip")
        assert updates._is_allowed_url(f"https://api.github.com/repos/{repo}/releases/latest")
    assert not updates._is_allowed_url("https://github.com/rasalopa/pico-loader-fake/releases/download/t/a.zip")
    assert not updates._is_allowed_url("https://github.com/someone/pico-launcher/releases/download/t/a.zip")


# --- manifesto do loader da PicoDex --------------------------------------


def test_routedex_uses_picodex_loader_manifest():
    routedex.reset_picodex_cache()
    m = routedex.load_picodex_loader_manifest()
    assert m["_origin"] == "app" and m["_picodex_tag"] == upstreams.lock_entry("picodex")["tag"]
    assert "v1.7.1" in [r["tag"] for r in m["releases"]]


def test_user_picodex_copy_wins_only_if_not_smaller(tmp_path, monkeypatch):
    routedex.reset_picodex_cache()
    monkeypatch.setattr(routedex, "PICODEX_USER_DIR", str(tmp_path))
    with open(upstreams.picodex_data_path("loaderReleases.json"), encoding="utf-8") as f:
        bundled = json.load(f)
    smaller = dict(bundled, releases=bundled["releases"][:-1])
    (tmp_path / "loaderReleases.json").write_text(json.dumps(smaller))
    assert routedex.load_picodex_loader_manifest()["_origin"] == "app"
    routedex.reset_picodex_cache()
    bigger = dict(bundled, releases=bundled["releases"] + [{"tag": "v9.9.9", "published": "2027-01-01"}])
    (tmp_path / "loaderReleases.json").write_text(json.dumps(bigger))
    (tmp_path / "meta.json").write_text(json.dumps({"tag": "v0.99.0"}))
    m = routedex.load_picodex_loader_manifest()
    assert m["_origin"] == "atualizado" and m["_picodex_tag"] == "v0.99.0"
    routedex.reset_picodex_cache()


def test_invalid_picodex_manifest_is_rejected():
    with pytest.raises(ValueError):
        routedex.validate_picodex_loader_manifest({"releases": [], "files": {}})


# --- regras portadas ------------------------------------------------------


def test_similarity_matches_picodex_reference_values():
    # Valores de matching.test.ts (mesma semântica do difflib).
    assert picodex_rules.similarity_ratio("abcd", "bcde") == pytest.approx(0.75)
    assert picodex_rules.similarity_ratio("", "") == 1.0
    assert picodex_rules.normalize_title("The Legend of Zelda (USA) - Minish Cap") == "legend of zelda minish cap"


def test_pick_boxart_region_and_variant_rules():
    catalog = [
        "Pokemon - Platinum Version (USA).png",
        "Pokemon - Platinum Version (Europe) (Demo).png",
        "Pokemon - Platinum Version (Europe) (En,Fr,De,Es,It).png",
    ]
    assert picodex_rules.pick_boxart("Pokemon Platinum Version", catalog) == catalog[2]
    us = picodex_rules.region_prefs_for("gba", "BPEE")
    assert picodex_rules.pick_boxart("Pokemon - Platinum Version", catalog, us) == catalog[0]
    assert picodex_rules.pick_boxart("x", catalog) is None


def test_art_target_follows_picodex(tmp_path):
    nds = picodex_rules.system_for_extension("Game.nds")
    gb = picodex_rules.system_for_extension("Game.gb")
    assert picodex_rules.resolve_art_target(str(tmp_path), "covers", "Game.nds", nds, "AMCE").endswith(
        os.path.join("covers", "nds", "AMCE.bmp")
    )
    assert picodex_rules.resolve_art_target(str(tmp_path), "covers", "Hb.nds", nds, "####").endswith(
        os.path.join("covers", "user", "Hb.nds.bmp")
    )
    assert picodex_rules.resolve_art_target(str(tmp_path), "icons", "Game.gb", gb, None).endswith(
        os.path.join("icons", "user", "Game.gb.bmp")
    )
    user = tmp_path / "_pico" / "covers" / "user" / "Game.nds.bmp"
    user.parent.mkdir(parents=True)
    user.write_bytes(b"x")
    assert picodex_rules.resolve_art_target(str(tmp_path), "covers", "Game.nds", nds, "AMCE") == str(user)


def test_games_dirs_follow_picodex():
    dirs = picodex_rules.games_dir_by_extension()
    assert dirs[".gbc"] == "gb" and dirs[".md"] == "gen" and dirs[".dsi"] == "nds" and dirs[".wsc"] == "ws"


def test_catalog_parse_and_urls():
    names = picodex_rules.parse_catalog(
        {"tree": [{"path": "Named_Boxarts/A (USA).png"}, {"path": "Named_Snaps/B.png"}, {"path": "Named_Boxarts/x.txt"}]}
    )
    assert names == ["A (USA).png"]
    assert picodex_rules.boxart_url("Nintendo_-_Nintendo_DS", "A & B (USA).png") == (
        "https://raw.githubusercontent.com/libretro-thumbnails/Nintendo_-_Nintendo_DS/master/Named_Boxarts/A%20%26%20B%20%28USA%29.png"
    )


def test_region_prefs_use_nds_code_and_file_name_tags():
    assert picodex_rules.region_prefs_for("nds", "AMCE")[0] == "(USA"
    assert picodex_rules.region_prefs_for("nds", "AMCP")[0] == "(Europe"
    assert picodex_rules.region_prefs_for("gb", None, "Tetris (USA).gb")[0] == "(USA"
    assert picodex_rules.region_prefs_for("gb", None, "Zelda (Japan).gb")[0] == "(Japan"
    assert picodex_rules.region_prefs_for("gb", None, "Tetris.gb") == picodex_rules.DEFAULT_REGION_PREFS
    names = ["Mario Kart DS (Europe) (En,Fr,De,Es,It).png", "Mario Kart DS (USA, Australia) (En,Fr,De,Es,It).png"]
    assert picodex_rules.pick_boxart("Mario Kart DS", names, picodex_rules.region_prefs_for("nds", "AMCE")) == names[1]


def test_pick_boxart_never_takes_another_game():
    """Melhorias sobre a PicoDex: palavras diferentes não contam como parecidas."""
    names = [
        "Brain Age - Train Your Brain in Minutes a Day! (USA).png",
        "Brain Age 2 - More Training in Minutes a Day! (USA).png",
        "Brain Voyage (USA) (En,Fr,Es).png",
        "Mario vs. Donkey Kong 2 - MiniMini Daikoushin! (Japan).png",
        "Mario Kart DS (USA) (En,Fr,De,Es,It).png",
        "1942 (Japan).png",
    ]
    us = picodex_rules.region_prefs_for("nds", "ANDE")
    assert picodex_rules.pick_boxart("Brain Age", names, us) == names[0]
    assert picodex_rules.pick_boxart("Brain Voyage", names, us) == names[2]
    assert picodex_rules.pick_boxart("Mario", names, us) is None
    assert picodex_rules.pick_boxart("Mario Kart DS", names, us) == names[4]
    assert picodex_rules.pick_boxart("1942", names, us) == names[5]
