from __future__ import annotations

import json

from core import pico_themes


def _write_theme_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_create_material_theme(fake_sd):
    ok, msg, stats = pico_themes.create_pico_material_theme(
        str(fake_sd), "Roxo", 120, 80, 200, dark=True
    )
    assert ok, msg
    folder = fake_sd / "_pico" / "themes" / "Roxo"
    assert folder.is_dir()
    assert (folder / "theme.json").is_file()
    assert (folder / "icon.bmp").is_file()
    assert stats["theme_folder"] == "Roxo"


def test_list_and_set_theme(fake_sd):
    theme_root = fake_sd / "_pico" / "themes" / "Blue"
    theme_root.mkdir(parents=True)
    _write_theme_json(
        theme_root / "theme.json",
        {
            "type": "material",
            "name": "Blue",
            "primaryColor": {"r": 10, "g": 20, "b": 30},
            "darkTheme": False,
        },
    )

    listed = pico_themes.list_pico_themes(str(fake_sd))
    assert listed["success"] is True
    assert any(t["folder"] == "Blue" for t in listed["themes"])

    ok, msg, _stats = pico_themes.set_pico_theme(str(fake_sd), "Blue")
    assert ok, msg
    listed2 = pico_themes.list_pico_themes(str(fake_sd))
    assert listed2["active_theme"] == "Blue"
    active_items = [t for t in listed2["themes"] if t["folder"] == "Blue"]
    assert active_items and active_items[0]["active"] is True


def test_import_custom_theme_rejects_missing_bins(fake_sd, tmp_path):
    src = tmp_path / "theme_custom"
    src.mkdir()
    _write_theme_json(
        src / "theme.json",
        {
            "type": "custom",
            "name": "Custom",
            "primaryColor": {"r": 1, "g": 2, "b": 3},
            "darkTheme": True,
        },
    )
    ok, msg, _stats = pico_themes.import_pico_theme(str(fake_sd), str(src))
    assert ok is False
    assert "incompleto" in msg.lower()
