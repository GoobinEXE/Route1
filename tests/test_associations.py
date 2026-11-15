"""Editor de associações e proteção do settings.json (PicoDex AssociationsView / settings.ts)."""

from __future__ import annotations

import json

import pytest

from core import dspico


@pytest.fixture
def card(fake_sd, monkeypatch):
    monkeypatch.setattr("core.dspico.sync_volume", lambda *a, **k: None)
    (fake_sd / "_pico" / "emulators").mkdir(parents=True)
    (fake_sd / "_pico" / "emulators" / "GBARunner3.nds").write_bytes(b"x")
    return fake_sd


def _settings(sd, payload):
    p = sd / "_pico" / "settings.json"
    p.write_bytes(payload if isinstance(payload, bytes) else json.dumps(payload).encode())
    return p


def test_read_edit_and_preserve_other_keys(card):
    p = _settings(card, {"theme": "Win95", "fileAssociations": {"gba": {"appPath": "/_pico/emulators/GBARunner3.nds", "extra": 1}}, "zLast": True})
    got = dspico.get_file_associations(str(card))
    assert got["associations"] == [{"ext": "gba", "app_path": "/_pico/emulators/GBARunner3.nds"}]
    assert got["examples"][0] == "/_pico/emulators/GBARunner3.nds"

    ok, msg = dspico.set_file_associations(
        str(card),
        [{"ext": ".GBA", "app_path": "/_pico/emulators/GBARunner3.nds"}, {"ext": "nes", "app_path": " /_pico/emulators/nesDS.nds "}],
    )
    assert ok, msg
    data = json.loads(p.read_text())
    assert list(data.keys()) == ["theme", "fileAssociations", "zLast"]
    assert data["fileAssociations"] == {
        "gba": {"appPath": "/_pico/emulators/GBARunner3.nds", "extra": 1},
        "nes": {"appPath": "/_pico/emulators/nesDS.nds"},
    }


@pytest.mark.parametrize(
    "items,needle",
    [
        ([{"ext": "", "app_path": "/a.nds"}], "extensão"),
        ([{"ext": "nes", "app_path": "  "}], "vazio"),
        ([{"ext": "nes", "app_path": "relative.nds"}], "Caminho inválido"),
        ([{"ext": "nes", "app_path": "/../x.nds"}], "Caminho inválido"),
        ([{"ext": "nes", "app_path": "/a.nds"}, {"ext": ".NES", "app_path": "/b.nds"}], "duas vezes"),
    ],
)
def test_invalid_associations_are_refused(card, items, needle):
    p = _settings(card, {"fileAssociations": {}})
    before = p.read_bytes()
    ok, msg = dspico.set_file_associations(str(card), items)
    assert not ok and needle in msg
    assert p.read_bytes() == before


@pytest.mark.parametrize(
    "payload,kind",
    [
        (b"\xef\xbb\xbf{}", "bom"),
        (b"{not json", "invalid"),
        (b"[1, 2]", "not-object"),
    ],
)
def test_broken_settings_are_never_overwritten(card, payload, kind):
    p = _settings(card, payload)
    problem = dspico.settings_file_problem(str(card))
    assert problem["kind"] == kind
    ok, msg = dspico.set_dspico_settings(str(card), {"theme": "Win95"})
    assert not ok and msg.startswith("Nada foi salvo.")
    ok2, _ = dspico.set_file_associations(str(card), [{"ext": "nes", "app_path": "/a.nds"}])
    assert not ok2
    assert p.read_bytes() == payload
    assert dspico.get_file_associations(str(card))["problem"]["kind"] == kind


def test_missing_settings_asks_to_run_the_launcher(card):
    ok, msg = dspico.set_file_associations(str(card), [])
    assert not ok and "Pico Launcher" in msg
    assert dspico.settings_file_problem(str(card)) is None
