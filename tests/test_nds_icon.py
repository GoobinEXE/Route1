"""Testes de extracção do ícone do banner NDS."""

import struct

from core import nds_icon


def _make_banner_with_solid_color(palette_index=1, color_bgr555=0x7C00):
    """Banner mínimo: um pixel no canto com cor da palette[index]."""
    banner = bytearray(0x240)
    # version
    struct.pack_into("<H", banner, 0, 0x0001)
    # bitmap: primeiro nibble baixo = index no tile 0
    banner[0x20] = palette_index & 0xF
    # palette
    struct.pack_into("<H", banner, 0x220 + palette_index * 2, color_bgr555)
    return bytes(banner)


def test_decode_nds_banner_icon_png():
    banner = _make_banner_with_solid_color(1, 0x001F)  # red-ish in BGR555
    png = nds_icon.decode_nds_banner_icon(banner)
    assert png is not None
    assert png.startswith(b"\x89PNG")
    assert len(png) > 50


def test_extract_from_file(tmp_path):
    rom = tmp_path / "game.nds"
    header = bytearray(0x200)
    banner_off = 0x200
    struct.pack_into("<I", header, 0x68, banner_off)
    banner = _make_banner_with_solid_color(2, 0x03E0)
    rom.write_bytes(bytes(header) + banner)

    png = nds_icon.extract_nds_icon_png(str(rom))
    assert png is not None
    url = nds_icon.nds_icon_data_url(str(rom))
    assert url and url.startswith("data:image/png;base64,")
    # cache hit
    assert nds_icon.nds_icon_data_url(str(rom)) == url


def test_extract_missing_banner(tmp_path):
    rom = tmp_path / "nobanner.nds"
    rom.write_bytes(b"\x00" * 0x200)
    assert nds_icon.extract_nds_icon_png(str(rom)) is None
