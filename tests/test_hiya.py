"""Testes de hiyaCFW (footer, markers, resolve nand, tools)."""

from __future__ import annotations

import os

import pytest

from core import hiya


def _write_fake_nand(path, *, with_footer=True, size_mb=120):
    """Cria nand.bin mínimo com ou sem footer No$GBA."""
    body = b"\x00" * (size_mb * 1024 * 1024 - 64)
    if with_footer:
        footer = (
            b"DSi eMMC CID/CPU"
            + bytes.fromhex("00112233445566778899aabbccddeeff")
            + bytes(reversed(bytes.fromhex("0123456789abcdef")))
            + b"\x00" * (64 - 16 - 16 - 8)
        )
        data = body + footer
    else:
        data = body + b"\x00" * 64
    path.write_bytes(data)


def test_hiya_markers_ok(tmp_path):
    assert hiya.hiya_markers_ok(str(tmp_path)) is False
    (tmp_path / "hiya.dsi").write_bytes(b"x")
    (tmp_path / "hiya").mkdir()
    assert hiya.hiya_markers_ok(str(tmp_path)) is True


def test_read_nocash_footer_ok(tmp_path):
    nand = tmp_path / "nand.bin"
    _write_fake_nand(nand, with_footer=True)
    cid, console_id = hiya.read_nocash_footer(str(nand))
    assert cid == "00112233445566778899AABBCCDDEEFF"
    assert console_id == "0123456789ABCDEF"


def test_read_nocash_footer_missing(tmp_path):
    nand = tmp_path / "nand.bin"
    _write_fake_nand(nand, with_footer=False)
    with pytest.raises(RuntimeError, match="No\\$GBA"):
        hiya.read_nocash_footer(str(nand))


def test_read_nocash_footer_too_small(tmp_path):
    nand = tmp_path / "nand.bin"
    nand.write_bytes(b"\x00" * 1024)
    with pytest.raises(RuntimeError, match="pequeno"):
        hiya.read_nocash_footer(str(nand))


def test_resolve_nand_from_dt(tmp_path):
    sd = tmp_path / "SD"
    sd.mkdir()
    dt = sd / "DTAABBCCDDEEFF0011"
    dt.mkdir()
    nand = dt / "nand.bin"
    _write_fake_nand(nand, with_footer=True)
    resolved = hiya.resolve_nand_path(str(sd), "")
    assert os.path.realpath(resolved) == os.path.realpath(str(nand))


def test_resolve_nand_allowlist_reject(tmp_path, monkeypatch):
    sd = tmp_path / "SD"
    sd.mkdir()
    outside = tmp_path / "outside" / "nand.bin"
    outside.parent.mkdir()
    _write_fake_nand(outside, with_footer=True)
    monkeypatch.setattr(hiya, "CACHE_DIR", str(tmp_path / "cache"))
    with pytest.raises(RuntimeError, match="allowlist"):
        hiya.resolve_nand_path(str(sd), str(outside))


def test_ensure_twlmagician_tools_darwin(tmp_path, monkeypatch):
    monkeypatch.setattr(hiya.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(hiya, "CACHE_DIR", str(tmp_path))

    paths = {}
    for name in ("twltool", "7za", "ndsblc", "fatcat"):
        p = tmp_path / name
        p.write_bytes(b"#!/bin/sh\n")
        paths[name] = str(p)

    def fake_cached(key, log_callback=None):
        mapping = {
            "twlm_twltool_darwin": paths["twltool"],
            "twlm_7za_darwin": paths["7za"],
            "twlm_ndsblc_darwin": paths["ndsblc"],
            "twlm_fatcat_darwin": paths["fatcat"],
        }
        return mapping[key]

    monkeypatch.setattr(hiya, "ensure_cached", fake_cached)
    tools = hiya.ensure_twlmagician_tools()
    assert tools["twltool"] == paths["twltool"]
    assert tools["za"] == paths["7za"]
    assert tools["fatcat"] == paths["fatcat"]
    assert tools["ndsblc"] == paths["ndsblc"]
    assert os.access(tools["twltool"], os.X_OK)


def test_decrypt_extract_uses_fatcat(tmp_path, monkeypatch):
    """Garante que a extracção SDNAND chama fatcat com o offset TWLN."""
    work = tmp_path / "work"
    work.mkdir()
    nand = work / "nand.bin"
    nand.write_bytes(b"\x00" * (120 * 1024 * 1024))
    img = work / "ABC.img"
    fake_fatcat = tmp_path / "fatcat"
    fake_twl = tmp_path / "twltool"
    fake_fatcat.write_bytes(b"x")
    fake_twl.write_bytes(b"x")
    calls = []

    def fake_run(cmd, *, cwd, timeout, log_callback=None):
        calls.append(list(cmd))
        if "nandcrypt" in cmd:
            img.write_bytes(b"\x00" * (120 * 1024 * 1024))
        elif str(cmd[0]).endswith("fatcat"):
            out = cmd[cmd.index("-x") + 1]
            os.makedirs(os.path.join(out, "title"), exist_ok=True)
            os.makedirs(os.path.join(out, "sys"), exist_ok=True)

    monkeypatch.setattr(hiya, "_run", fake_run)
    tools = {
        "twltool": str(fake_twl),
        "fatcat": str(fake_fatcat),
        "za": str(tmp_path / "7za"),
    }
    out = hiya._decrypt_and_extract_sdnand(
        str(work), tools, str(nand), "ABC", log_callback=None
    )
    assert os.path.isdir(os.path.join(out, "title"))
    fat_cmds = [c for c in calls if c and str(c[0]).endswith("fatcat")]
    assert fat_cmds, calls
    assert hiya._TWLN_FAT_OFFSET in fat_cmds[0]


def test_apply_ips_rle(tmp_path):
    target = tmp_path / "t.bin"
    target.write_bytes(b"\x00" * 16)
    # IPS: PATCH + offset 0x000002 size 0 RLE size 3 byte 0xAB + EOF
    patch = tmp_path / "p.ips"
    patch.write_bytes(
        b"PATCH"
        + b"\x00\x00\x02"  # offset 2
        + b"\x00\x00"  # size 0 = RLE
        + b"\x00\x03"  # rle length 3
        + b"\xab"
        + b"EOF"
    )
    hiya._apply_ips(str(patch), str(target))
    data = target.read_bytes()
    assert data[2:5] == b"\xab\xab\xab"
