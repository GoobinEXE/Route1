"""Passos do assistente nativo (paridade com wizard.js)."""

from services.wizard_flow import build_steps, initial_step


def test_sd_new_has_stage_steps():
    steps = build_steps("sd-new")
    ids = [s["id"] for s in steps]
    assert "model" in ids
    assert "stage1" in ids
    assert "stage2" in ids
    assert "hiya-install" in ids
    assert ids[-1] == "done-sd"


def test_flash_new_requires_brand_for_full_path():
    stub = build_steps("flash-new", brand="")
    assert stub[0]["id"] == "brand"
    assert len(stub) == 1
    full = build_steps("flash-new", brand="gei")
    ids = [s["id"] for s in full]
    assert "format-warn" in ids
    assert "kernel-install" in ids
    assert ids[-1] == "done-flash"


def test_dspico_fw_steps():
    steps = build_steps("dspico-fw")
    assert steps[0]["id"] == "bootsel"
    assert any(s["bodyKind"] == "flash_uf2" for s in steps)


def test_initial_step():
    s = initial_step("sd-update")
    assert s["id"] == "select-lateral"
