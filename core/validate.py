"""Validação estrutural de artefatos NDS/DSi e Memory Pit."""

from __future__ import annotations

import os
import struct

# Tamanhos exatos conhecidos dos pit.bin oficiais (dsi.cfw.guide).
PIT_EXPECTED_SIZES = {
    "pit_facebook": 48032,
    "pit_no_facebook": 48032,
}


def crc16_nds(data: bytes) -> int:
    """CRC-16 usado no cabeçalho Nintendo DS (poly 0xA001, init 0xFFFF)."""
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def validate_nds_header(path: str, min_size: int = 1024) -> tuple[bool, str]:
    """
    Verifica cabeçalho NDS/DSi: CRC do header, tamanho mínimo e rom_size declarado.
    Retorna (ok, mensagem).
    """
    try:
        size = os.path.getsize(path)
    except OSError as e:
        return False, f"Não foi possível ler {path}: {e}"

    if size < min_size:
        return False, f"Arquivo muito pequeno ({size} bytes): {path}"

    try:
        with open(path, "rb") as f:
            header = f.read(0x200)
    except OSError as e:
        return False, f"Falha ao ler cabeçalho de {path}: {e}"

    if len(header) < 0x160:
        return False, f"Cabeçalho incompleto em {path}"

    title = header[0:12].rstrip(b"\x00")
    if not title:
        return False, f"Título do cabeçalho vazio em {path}"

    stored_crc = struct.unpack_from("<H", header, 0x15E)[0]
    calc_crc = crc16_nds(header[:0x15E])
    if stored_crc != calc_crc:
        return (
            False,
            f"CRC do cabeçalho inválido em {path} "
            f"(esperado 0x{calc_crc:04X}, lido 0x{stored_crc:04X})",
        )

    rom_size = struct.unpack_from("<I", header, 0x80)[0]
    if rom_size and size < rom_size:
        return (
            False,
            f"Arquivo truncado em {path}: {size} bytes < rom_size {rom_size}",
        )

    return True, "ok"


def validate_pit_file(path: str, key: str) -> tuple[bool, str]:
    """Confere tamanho exato do pit.bin pela variante."""
    expected = PIT_EXPECTED_SIZES.get(key)
    try:
        size = os.path.getsize(path)
    except OSError as e:
        return False, f"Não foi possível ler {path}: {e}"
    if expected is not None and size != expected:
        return False, f"pit.bin ({key}) com tamanho {size}, esperado {expected}"
    if size < 100:
        return False, f"pit.bin ({key}) suspeitamente pequeno ({size} bytes)"
    return True, "ok"


def twilight_tree_ok(src_dir: str) -> tuple[bool, str]:
    """Exige estrutura mínima do pacote TWiLight Menu++ (DSi)."""
    boot = os.path.join(src_dir, "BOOT.NDS")
    nds = os.path.join(src_dir, "_nds")
    if not os.path.isfile(boot):
        return False, "BOOT.NDS ausente no pacote TWiLight"
    if not os.path.isdir(nds):
        return False, "Pasta _nds ausente no pacote TWiLight"

    ok, msg = validate_nds_header(boot)
    if not ok:
        return False, msg

    twl_menu = os.path.join(nds, "TWiLightMenu")
    bootstrap = os.path.join(nds, "nds-bootstrap-release.nds")
    if not os.path.isdir(twl_menu):
        # Algumas builds usam nomes ligeiramente diferentes; exigir ao menos arquivos em _nds
        try:
            entries = os.listdir(nds)
        except OSError:
            entries = []
        if not entries:
            return False, "Pasta _nds vazia"
    if os.path.isfile(bootstrap):
        ok, msg = validate_nds_header(bootstrap)
        if not ok:
            return False, f"nds-bootstrap inválido: {msg}"

    return True, "ok"
