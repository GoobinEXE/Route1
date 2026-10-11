"""Conversão de imagens para o formato BMP do Pico Launcher (stdlib only).

Capas: 128×96, 8 bpp (área útil 106×96 à esquerda).
Ícones: 32×32, 4 bpp (cor 0 = transparente).
"""

from __future__ import annotations

import struct
import zlib
from typing import Optional


COVER_W = 128
COVER_H = 96
COVER_VISIBLE_W = 106
ICON_SIZE = 32


def decode_png_rgba(data: bytes) -> tuple[int, int, bytes]:
    """
    Decodifica PNG RGB/RGBA/paleta/cinza (8-bit) → (w, h, rgba_bytes).
    Suficiente para GameTDB / Libretro / PNG escolhido pelo utilizador.
    """
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Não é PNG.")
    pos = 8
    width = height = None
    bit_depth = color_type = None
    idat = bytearray()
    plte: Optional[bytes] = None
    trns: Optional[bytes] = None

    while pos + 8 <= len(data):
        length = struct.unpack_from(">I", data, pos)[0]
        pos += 4
        if pos + 4 + length + 4 > len(data):
            break
        tag = data[pos : pos + 4]
        pos += 4
        chunk = data[pos : pos + length]
        pos += length
        pos += 4  # CRC
        if tag == b"IHDR":
            if length < 13:
                raise ValueError("IHDR inválido.")
            width, height, bit_depth, color_type, comp, filt, inter = struct.unpack(
                ">IIBBBBB", chunk[:13]
            )
            if comp != 0 or filt != 0 or inter != 0:
                raise ValueError("PNG com compressão/filtro/interlace não suportado.")
            if bit_depth != 8:
                raise ValueError("Só PNG 8-bit é suportado.")
            if color_type not in (0, 2, 3, 4, 6):
                raise ValueError("Tipo de cor PNG não suportado.")
        elif tag == b"PLTE":
            plte = chunk
        elif tag == b"tRNS":
            trns = chunk
        elif tag == b"IDAT":
            idat.extend(chunk)
        elif tag == b"IEND":
            break

    if width is None or height is None or not idat:
        raise ValueError("PNG incompleto.")
    if width < 1 or height < 1 or width > 4096 or height > 4096:
        raise ValueError("Dimensões PNG inválidas.")

    raw = zlib.decompress(bytes(idat))
    if color_type == 2:
        bpp = 3
    elif color_type == 6:
        bpp = 4
    elif color_type == 0:
        bpp = 1
    elif color_type == 4:
        bpp = 2
    else:  # paleta
        bpp = 1

    stride = width * bpp
    expected = (stride + 1) * height
    if len(raw) < expected:
        raise ValueError("Dados PNG truncados.")

    rows: list[bytearray] = []
    prev = bytearray(stride)
    offset = 0
    for _ in range(height):
        ftype = raw[offset]
        offset += 1
        cur = bytearray(raw[offset : offset + stride])
        offset += stride
        if ftype == 1:  # Sub
            for i in range(bpp, stride):
                cur[i] = (cur[i] + cur[i - bpp]) & 0xFF
        elif ftype == 2:  # Up
            for i in range(stride):
                cur[i] = (cur[i] + prev[i]) & 0xFF
        elif ftype == 3:  # Average
            for i in range(stride):
                left = cur[i - bpp] if i >= bpp else 0
                cur[i] = (cur[i] + ((left + prev[i]) // 2)) & 0xFF
        elif ftype == 4:  # Paeth
            for i in range(stride):
                a = cur[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                cur[i] = (cur[i] + pr) & 0xFF
        elif ftype != 0:
            raise ValueError("Filtro PNG desconhecido.")
        rows.append(cur)
        prev = cur

    out = bytearray(width * height * 4)
    oi = 0
    for row in rows:
        if color_type == 2:
            for x in range(width):
                i = x * 3
                out[oi : oi + 4] = bytes((row[i], row[i + 1], row[i + 2], 255))
                oi += 4
        elif color_type == 6:
            for x in range(width):
                i = x * 4
                out[oi : oi + 4] = bytes(row[i : i + 4])
                oi += 4
        elif color_type == 0:
            for x in range(width):
                g = row[x]
                out[oi : oi + 4] = bytes((g, g, g, 255))
                oi += 4
        elif color_type == 4:
            for x in range(width):
                i = x * 2
                g, a = row[i], row[i + 1]
                out[oi : oi + 4] = bytes((g, g, g, a))
                oi += 4
        else:
            if not plte or len(plte) < 3:
                raise ValueError("PNG paleta sem PLTE.")
            for x in range(width):
                idx = row[x]
                pi = idx * 3
                if pi + 2 >= len(plte):
                    r = g = b = 0
                else:
                    r, g, b = plte[pi], plte[pi + 1], plte[pi + 2]
                a = 255
                if trns is not None and idx < len(trns):
                    a = trns[idx]
                out[oi : oi + 4] = bytes((r, g, b, a))
                oi += 4
    return width, height, bytes(out)


def decode_bmp_rgba(data: bytes) -> tuple[int, int, bytes]:
    """Decodifica BMP não comprimido 8/24/32 bpp → RGBA."""
    if len(data) < 54 or data[:2] != b"BM":
        raise ValueError("Não é BMP.")
    pixel_off = struct.unpack_from("<I", data, 10)[0]
    hdr_size = struct.unpack_from("<I", data, 14)[0]
    if hdr_size < 40:
        raise ValueError("BMP antigo não suportado.")
    width = struct.unpack_from("<i", data, 18)[0]
    height_raw = struct.unpack_from("<i", data, 22)[0]
    planes, bpp = struct.unpack_from("<HH", data, 26)
    compression = struct.unpack_from("<I", data, 30)[0]
    if planes != 1 or compression != 0:
        raise ValueError("BMP comprimido/planos não suportado.")
    if width < 1 or abs(height_raw) < 1 or width > 4096 or abs(height_raw) > 4096:
        raise ValueError("Dimensões BMP inválidas.")
    top_down = height_raw < 0
    height = abs(height_raw)
    palette = []
    if bpp <= 8:
        colors = struct.unpack_from("<I", data, 46)[0] or (1 << bpp)
        pal_off = 14 + hdr_size
        for i in range(colors):
            o = pal_off + i * 4
            if o + 3 >= len(data):
                break
            b, g, r = data[o], data[o + 1], data[o + 2]
            palette.append((r, g, b, 255 if i > 0 or bpp != 4 else 0))

    row_bytes = ((width * bpp + 31) // 32) * 4
    out = bytearray(width * height * 4)
    for y in range(height):
        src_y = y if top_down else (height - 1 - y)
        row_off = pixel_off + src_y * row_bytes
        for x in range(width):
            di = (y * width + x) * 4
            if bpp == 24:
                o = row_off + x * 3
                if o + 2 >= len(data):
                    break
                out[di : di + 4] = bytes((data[o + 2], data[o + 1], data[o], 255))
            elif bpp == 32:
                o = row_off + x * 4
                if o + 3 >= len(data):
                    break
                out[di : di + 4] = bytes((data[o + 2], data[o + 1], data[o], data[o + 3]))
            elif bpp == 8:
                o = row_off + x
                if o >= len(data):
                    break
                idx = data[o]
                r, g, b, a = palette[idx] if idx < len(palette) else (0, 0, 0, 255)
                out[di : di + 4] = bytes((r, g, b, a))
            elif bpp == 4:
                o = row_off + (x // 2)
                if o >= len(data):
                    break
                byte = data[o]
                idx = (byte >> 4) if (x % 2) == 0 else (byte & 0xF)
                r, g, b, a = palette[idx] if idx < len(palette) else (0, 0, 0, 255)
                out[di : di + 4] = bytes((r, g, b, a))
            else:
                raise ValueError(f"BMP {bpp} bpp não suportado.")
    return width, height, bytes(out)


def decode_image_rgba(data: bytes) -> tuple[int, int, bytes]:
    if data.startswith(b"\x89PNG"):
        return decode_png_rgba(data)
    if data[:2] == b"BM":
        return decode_bmp_rgba(data)
    raise ValueError("Formato de imagem não suportado (use PNG ou BMP).")


def _resize_rgba(
    src_w: int, src_h: int, src: bytes, dst_w: int, dst_h: int
) -> bytes:
    """Nearest-neighbor resize."""
    out = bytearray(dst_w * dst_h * 4)
    if src_w < 1 or src_h < 1:
        return bytes(out)
    for y in range(dst_h):
        sy = min(src_h - 1, (y * src_h) // dst_h)
        for x in range(dst_w):
            sx = min(src_w - 1, (x * src_w) // dst_w)
            si = (sy * src_w + sx) * 4
            di = (y * dst_w + x) * 4
            out[di : di + 4] = src[si : si + 4]
    return bytes(out)


def _fit_contain(
    src_w: int, src_h: int, src: bytes, box_w: int, box_h: int, pad_rgb=(0, 0, 0)
) -> bytes:
    """Encaixa mantendo aspecto; padding com pad_rgb, alpha 255."""
    if src_w < 1 or src_h < 1:
        canvas = bytearray(box_w * box_h * 4)
        pr, pg, pb = pad_rgb
        for i in range(0, len(canvas), 4):
            canvas[i : i + 4] = bytes((pr, pg, pb, 255))
        return bytes(canvas)
    scale = min(box_w / src_w, box_h / src_h)
    tw = max(1, int(round(src_w * scale)))
    th = max(1, int(round(src_h * scale)))
    scaled = _resize_rgba(src_w, src_h, src, tw, th)
    canvas = bytearray(box_w * box_h * 4)
    pr, pg, pb = pad_rgb
    for i in range(0, len(canvas), 4):
        canvas[i : i + 4] = bytes((pr, pg, pb, 255))
    ox = (box_w - tw) // 2
    oy = (box_h - th) // 2
    for y in range(th):
        for x in range(tw):
            si = (y * tw + x) * 4
            di = ((oy + y) * box_w + (ox + x)) * 4
            r, g, b, a = scaled[si : si + 4]
            if a < 128:
                continue
            canvas[di : di + 4] = bytes((r, g, b, 255))
    return bytes(canvas)


def _median_cut_palette(pixels: list[tuple[int, int, int]], max_colors: int) -> list[tuple[int, int, int]]:
    if not pixels:
        return [(0, 0, 0)]
    buckets: list[list[tuple[int, int, int]]] = [list(pixels)]
    while len(buckets) < max_colors:
        buckets.sort(
            key=lambda b: (
                0
                if not b
                else max(
                    max(p[c] for p in b) - min(p[c] for p in b) for c in range(3)
                )
            ),
            reverse=True,
        )
        bucket = buckets[0]
        if len(bucket) < 2:
            break
        channel = max(
            range(3),
            key=lambda c: max(p[c] for p in bucket) - min(p[c] for p in bucket),
        )
        bucket.sort(key=lambda p: p[channel])
        mid = len(bucket) // 2
        buckets[0] = bucket[:mid]
        buckets.append(bucket[mid:])
    palette = []
    for b in buckets:
        if not b:
            continue
        n = len(b)
        palette.append(
            (
                sum(p[0] for p in b) // n,
                sum(p[1] for p in b) // n,
                sum(p[2] for p in b) // n,
            )
        )
    while len(palette) < max_colors:
        palette.append((0, 0, 0))
    return palette[:max_colors]


def _nearest_index(r: int, g: int, b: int, palette: list[tuple[int, int, int]], start: int = 0) -> int:
    best_i = start
    best_d = 1 << 30
    for i in range(start, len(palette)):
        pr, pg, pb = palette[i]
        d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if d < best_d:
            best_d = d
            best_i = i
            if d == 0:
                break
    return best_i


def _pack_bmp(
    width: int,
    height: int,
    bpp: int,
    palette: list[tuple[int, int, int, int]],
    indices: bytes,
) -> bytes:
    """Escreve BMP bottom-up não comprimido."""
    colors = len(palette)
    row_bytes = ((width * bpp + 31) // 32) * 4
    pixel_size = row_bytes * height
    pal_size = colors * 4
    pixel_off = 14 + 40 + pal_size
    file_size = pixel_off + pixel_size

    header = struct.pack(
        "<2sIHHI",
        b"BM",
        file_size,
        0,
        0,
        pixel_off,
    )
    info = struct.pack(
        "<IiiHHIIiiII",
        40,
        width,
        height,  # bottom-up
        1,
        bpp,
        0,
        pixel_size,
        2835,
        2835,
        colors,
        0,
    )
    pal = bytearray()
    for r, g, b, _a in palette:
        pal.extend(bytes((b, g, r, 0)))

    pixels = bytearray()
    for y in range(height - 1, -1, -1):
        row = bytearray(row_bytes)
        if bpp == 8:
            for x in range(width):
                row[x] = indices[y * width + x]
        elif bpp == 4:
            for x in range(width):
                idx = indices[y * width + x] & 0xF
                if x % 2 == 0:
                    row[x // 2] = (idx << 4) & 0xF0
                else:
                    row[x // 2] = (row[x // 2] & 0xF0) | idx
        else:
            raise ValueError("bpp inválido")
        pixels.extend(row)
    return header + info + bytes(pal) + bytes(pixels)


def rgba_to_cover_bmp(src_w: int, src_h: int, rgba: bytes) -> bytes:
    """Converte imagem → capa Pico 128×96 8 bpp (conteúdo em 106×96)."""
    fitted = _fit_contain(src_w, src_h, rgba, COVER_VISIBLE_W, COVER_H)
    canvas = bytearray(COVER_W * COVER_H * 4)
    for y in range(COVER_H):
        for x in range(COVER_VISIBLE_W):
            si = (y * COVER_VISIBLE_W + x) * 4
            di = (y * COVER_W + x) * 4
            canvas[di : di + 4] = fitted[si : si + 4]
    # amostragem para paleta (saltar padding preto)
    samples = []
    step = max(1, (COVER_VISIBLE_W * COVER_H) // 4000)
    for i in range(0, COVER_VISIBLE_W * COVER_H, step):
        o = ((i // COVER_VISIBLE_W) * COVER_W + (i % COVER_VISIBLE_W)) * 4
        samples.append((canvas[o], canvas[o + 1], canvas[o + 2]))
    palette_rgb = _median_cut_palette(samples, 256)
    palette = [(r, g, b, 255) for r, g, b in palette_rgb]
    indices = bytearray(COVER_W * COVER_H)
    for y in range(COVER_H):
        for x in range(COVER_W):
            o = (y * COVER_W + x) * 4
            r, g, b = canvas[o], canvas[o + 1], canvas[o + 2]
            indices[y * COVER_W + x] = _nearest_index(r, g, b, palette_rgb, 0)
    return _pack_bmp(COVER_W, COVER_H, 8, palette, bytes(indices))


def rgba_to_icon_bmp(src_w: int, src_h: int, rgba: bytes) -> bytes:
    """Converte imagem → ícone Pico 32×32 4 bpp (cor 0 transparente)."""
    fitted = _fit_contain(src_w, src_h, rgba, ICON_SIZE, ICON_SIZE)
    samples = []
    for i in range(ICON_SIZE * ICON_SIZE):
        o = i * 4
        if fitted[o + 3] < 128:
            continue
        samples.append((fitted[o], fitted[o + 1], fitted[o + 2]))
    palette_rgb = [(0, 0, 0)] + _median_cut_palette(samples, 15)
    while len(palette_rgb) < 16:
        palette_rgb.append((0, 0, 0))
    palette = [(r, g, b, 0 if i == 0 else 255) for i, (r, g, b) in enumerate(palette_rgb)]
    indices = bytearray(ICON_SIZE * ICON_SIZE)
    for i in range(ICON_SIZE * ICON_SIZE):
        o = i * 4
        if fitted[o + 3] < 128:
            indices[i] = 0
        else:
            indices[i] = _nearest_index(
                fitted[o], fitted[o + 1], fitted[o + 2], palette_rgb, 1
            )
    return _pack_bmp(ICON_SIZE, ICON_SIZE, 4, palette, bytes(indices))


def image_bytes_to_pico_bmp(data: bytes, kind: str) -> bytes:
    """kind: 'cover' | 'icon'."""
    w, h, rgba = decode_image_rgba(data)
    if kind == "icon":
        return rgba_to_icon_bmp(w, h, rgba)
    return rgba_to_cover_bmp(w, h, rgba)


def rgba_to_png(width: int, height: int, rgba: bytes) -> bytes:
    """PNG RGBA mínimo (para previews data-URL)."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    raw = bytearray()
    stride = width * 4
    for y in range(height):
        raw.append(0)
        raw.extend(rgba[y * stride : (y + 1) * stride])
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
        + chunk(b"IEND", b"")
    )


def bmp_to_preview_png(data: bytes) -> bytes:
    w, h, rgba = decode_bmp_rgba(data)
    return rgba_to_png(w, h, rgba)


def image_bytes_to_preview_png(data: bytes, max_side: int = 128) -> bytes:
    w, h, rgba = decode_image_rgba(data)
    if max(w, h) > max_side:
        if w >= h:
            nw, nh = max_side, max(1, int(round(h * max_side / w)))
        else:
            nh, nw = max_side, max(1, int(round(w * max_side / h)))
        rgba = _resize_rgba(w, h, rgba, nw, nh)
        w, h = nw, nh
    return rgba_to_png(w, h, rgba)
