import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture
def fake_cache(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr("core.cache.CACHE_DIR", str(cache))
    return cache


@pytest.fixture
def fake_sd(tmp_path):
    sd = tmp_path / "SD"
    sd.mkdir()
    return sd


def make_nds(path, title=b"HOMEBREW", code=b"####", rom_size=None, payload=b"\x00" * 2048):
    """Cria um arquivo .nds mínimo com CRC de cabeçalho válido."""
    from core.validate import crc16_nds

    header = bytearray(0x200)
    header[0:12] = title.ljust(12, b"\x00")[:12]
    header[12:16] = code.ljust(4, b"\x00")[:4]
    body = payload
    size = 0x200 + len(body)
    if rom_size is None:
        rom_size = size
    header[0x80:0x84] = int(rom_size).to_bytes(4, "little")
    crc = crc16_nds(bytes(header[:0x15E]))
    header[0x15E:0x160] = crc.to_bytes(2, "little")
    with open(path, "wb") as f:
        f.write(header)
        f.write(body)
    return path
