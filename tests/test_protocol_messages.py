"""Conformidade de protocol/messages.json (R1USB, partilhado entre o app do console e o desktop)."""

from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = json.loads((ROOT / "protocol" / "messages.json").read_text(encoding="utf-8"))


def test_identity_and_version():
    assert SPEC["protocol"] == "R1USB"
    assert re.fullmatch(r"\d+\.\d+\.\d+", SPEC["version"])


def test_message_and_error_codes_are_stable_and_unique():
    names = list(SPEC["msg_types"].values())
    assert len(names) == len(set(names))
    assert "PUT_BEGIN" in names and "PUT_COMMIT" in names and "CANCEL" in names
    codes = list(SPEC["errors"].values())
    assert len(codes) == len(set(codes))
    assert SPEC["errors"]["E_OK"] == 0 and SPEC["errors"]["E_HASH"] == 4


def test_limits_match_integrity_contract():
    limits = SPEC["limits"]
    assert limits["partial_suffix"] == ".r1partial"
    assert limits["hash"] == "SHA-256"
    assert limits["chunk_prefer"] <= limits["max_payload"]


def test_console_headers_agree_with_spec():
    version_h = (ROOT / "nds" / "include" / "route1" / "version.h").read_text(encoding="utf-8")
    m = re.search(r'#define R1_PROTOCOL_VERSION "([^"]+)"', version_h)
    assert m and m.group(1) == SPEC["version"]


def test_console_error_enum_agrees_with_spec():
    err_h = (ROOT / "nds" / "include" / "route1" / "err.h").read_text(encoding="utf-8")
    local = {f"E_{m.group(1)}": int(m.group(2)) for m in re.finditer(r"R1_E_([A-Z_]+)\s*=\s*(\d+)", err_h)}
    spec = SPEC["errors"]
    for name, value in local.items():
        if name in spec:
            assert value == spec[name], name
        else:
            # Código só do console (ex.: E_NOTFOUND): não pode reutilizar um número do protocolo.
            assert value not in spec.values(), name
