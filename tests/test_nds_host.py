"""Corre os testes C do app do console (nds/) no host, se houver compilador."""

from __future__ import annotations

import os
import shutil
import subprocess

import pytest

NDS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nds")


@pytest.mark.skipif(not (shutil.which("make") and shutil.which("cc")), reason="make/cc indisponíveis")
def test_nds_host_suite():
    res = subprocess.run(
        ["make", "-C", NDS, "host-test"],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    assert "test_path: ok" in res.stdout and "test_fs: ok" in res.stdout
