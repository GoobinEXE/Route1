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
    assert "nenhuma imagem" in msg.lower()


def _custom_theme(root, name, files):
    folder = root / "_pico" / "themes" / name
    folder.mkdir(parents=True)
    _write_theme_json(
        folder / "theme.json",
        {"type": "custom", "name": name, "primaryColor": {"r": 255, "g": 255, "b": 255}, "darkTheme": False},
    )
    for f in files:
        (folder / f).write_bytes(b"\0" * 64)
    return folder


def test_custom_themes_with_launcher_file_names_are_listed_and_selectable(fake_sd):
    """Nomes reais do Pico Launcher (tema raspberry incluído): gridcellSelectedPltt.bin."""
    full = [
        "bannerListCell.bin", "bannerListCellPltt.bin", "bannerListCellSelected.bin",
        "bannerListCellSelectedPltt.bin", "bottombg.bin", "gridcell.bin", "gridcellPltt.bin",
        "gridcellSelected.bin", "gridcellSelectedPltt.bin", "scrim.bin", "scrimPltt.bin", "topbg.bin",
    ]
    _custom_theme(fake_sd, "Win95", full)
    # Tema só para a lista de banners: sem arquivos de grade, o launcher usa o resto.
    _custom_theme(fake_sd, "PiCardboard", [f for f in full if not f.startswith("gridcell")])

    listed = pico_themes.list_pico_themes(str(fake_sd))
    folders = {t["folder"] for t in listed["themes"]}
    assert {"Win95", "PiCardboard"} <= folders

    ok, msg, _stats = pico_themes.set_pico_theme(str(fake_sd), "PiCardboard")
    assert ok, msg
