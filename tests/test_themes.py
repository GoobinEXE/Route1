"""Temas da app: ficheiros gerados em dia e contraste AA em todas as combinações."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tools", "build_themes.py")


def _load():
    spec = importlib.util.spec_from_file_location("build_themes", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_generated_theme_files_are_up_to_date():
    res = subprocess.run([sys.executable, TOOL, "--check"], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr or "rode python tools/build_themes.py"


def test_every_theme_and_mode_meets_wcag_aa():
    bt = _load()
    assert len(bt.FAMILIES) == 7
    for fam in bt.FAMILIES:
        for mode in ("original", "light", "dark"):
            t = bt.tokens(fam, mode)
            for ground in (t["surface"], t["surface-2"], t["bg"]):
                assert bt.contrast(t["fg"], ground) >= 7.0, (fam["id"], mode)
                for key in ("fg-soft", "fg-mute", "accent-fg", "ok", "warn", "danger"):
                    assert bt.contrast(t[key], ground) >= 4.5, (fam["id"], mode, key)
            assert bt.contrast(t["on-accent"], t["accent"]) >= 4.5, (fam["id"], mode)
            assert bt.contrast(t["on-select"], t["select-fill"]) >= 4.5, (fam["id"], mode)
            assert bt.contrast(t["line-strong"], t["surface"]) >= 3.0, (fam["id"], mode)


def test_theme_names_avoid_trademarks():
    bt = _load()
    banned = ("nintendo", "wii", "gamecube", "3ds", "switch", "ds lite", "dsi")
    for fam in bt.FAMILIES:
        text = (fam["label"] + " " + fam["hint"]).lower()
        assert not any(b in text for b in banned), fam["label"]
