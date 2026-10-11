"""Extracção do ícone 32×32 do banner NDS/DSi (stdlib only → PNG)."""

from __future__ import annotations

import base64
import os
import struct
import zlib
from typing import Optional

# Cache em memória: (realpath, mtime_ns, size) → data URL ou None
_ICON_CACHE: dict[tuple, Optional[str]] = {}
_ICON_CACHE_MAX = 256


def _png_rgba(width: int, height: int, rgba: bytes) -> bytes:
    """Codifica imagem RGBA crua num PNG mínimo."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    raw = bytearray()
    stride = width * 4
    for y in range(height):
        raw.append(0)  # filter None
        raw.extend(rgba[y * stride : (y + 1) * stride])
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def _bgr555_to_rgba(color: int, transparent: bool) -> tuple[int, int, int, int]:
    if transparent:
        return (0, 0, 0, 0)
    r = round((color & 0x1F) * 255 / 31)
    g = round(((color >> 5) & 0x1F) * 255 / 31)
    b = round(((color >> 10) & 0x1F) * 255 / 31)
    return (r, g, b, 255)


def decode_nds_banner_icon(banner: bytes) -> Optional[bytes]:
    """
    Decodifica ícone estático DS a partir do bloco de banner.
    Requer pelo menos 0x240 bytes (bitmap @0x20 + palette @0x220).
    Retorna PNG bytes ou None.
    """
    if len(banner) < 0x240:
        return None
    bitmap = banner[0x20 : 0x20 + 512]
    palette_raw = banner[0x220 : 0x220 + 32]
    palette = []
    for i in range(16):
        color = struct.unpack_from("<H", palette_raw, i * 2)[0]
        palette.append(_bgr555_to_rgba(color, transparent=(i == 0)))

    # 4×4 tiles de 8×8, 4 bpp
    pixels = bytearray(32 * 32 * 4)
    bi = 0
    for ty in range(4):
        for tx in range(4):
            for y in range(8):
                for x in range(4):
                    if bi >= len(bitmap):
                        break
                    byte = bitmap[bi]
                    bi += 1
                    for n, idx in enumerate((byte & 0xF, byte >> 4)):
                        px = tx * 8 + x * 2 + n
                        py = ty * 8 + y
                        r, g, b, a = palette[idx & 0xF]
                        o = (py * 32 + px) * 4
                        pixels[o : o + 4] = bytes((r, g, b, a))
    return _png_rgba(32, 32, bytes(pixels))


def extract_nds_icon_png(file_path: str) -> Optional[bytes]:
    """Lê o banner da ROM e devolve PNG do ícone, ou None."""
    try:
        with open(file_path, "rb") as f:
            header = f.read(0x70)
            if len(header) < 0x6C:
                return None
            banner_off = struct.unpack_from("<I", header, 0x68)[0]
            if banner_off == 0 or banner_off > 0x2000000:
                return None
            f.seek(banner_off)
            # Ícone estático DS: até palette inclusive (~0x240)
            banner = f.read(0x240)
    except OSError:
        return None
    return decode_nds_banner_icon(banner)


def nds_icon_data_url(file_path: str) -> Optional[str]:
    """Data URL do ícone (com cache por mtime/tamanho)."""
    try:
        st = os.stat(file_path)
        key = (os.path.realpath(file_path), getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)), st.st_size)
    except OSError:
        return None

    if key in _ICON_CACHE:
        return _ICON_CACHE[key]

    png = extract_nds_icon_png(file_path)
    url = None
    if png:
        url = "data:image/png;base64," + base64.b64encode(png).decode("ascii")

    if len(_ICON_CACHE) >= _ICON_CACHE_MAX:
        # Evitar crescimento ilimitado
        _ICON_CACHE.clear()
    _ICON_CACHE[key] = url
    return url


def clear_icon_cache() -> None:
    _ICON_CACHE.clear()
