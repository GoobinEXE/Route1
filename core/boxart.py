"""Compat: reexporta o pipeline de capas/ícones de core.artwork."""

from core.artwork import (  # noqa: F401
    boxart_urls_for_tid,
    fetch_rom_artwork,
    install_artwork,
    install_boxarts,
    libretro_name_candidates,
    libretro_sanitize_name,
    libretro_urls,
    tid_region,
)
from core.artwork import _scan_rom_tids  # noqa: F401  # usado em testes
