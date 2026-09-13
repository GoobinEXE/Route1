"""Catálogo de homebrew DS/DSi instalável (releases oficiais pinadas).

Curadoria baseada na lista GameBrew de aplicações, limitada a artefactos
``.nds``/``.dsi`` com URL HTTPS estável e SHA-256 em ``core.cache``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.cache import FILENAMES, PINNED_SHA256
from core.homebrew_install import notes_for

GAMEBREW_WIKI_PREFIX = "https://www.gamebrew.org/wiki/"

# Categorias alinhadas à lista GameBrew (subset útil no DSi).
CATEGORIES: Dict[str, str] = {
    "media": "Reprodutores",
    "system": "Sistema",
    "files": "Ficheiros",
    "saves": "Saves",
    "utilities": "Utilitários",
}

# Cada entrada: install_key deve existir em PINNED_SHA256 / FILENAMES.
_APPS: List[Dict[str, Any]] = [
    {
        "id": "godmode9i",
        "title": "GodMode9i",
        "description": "Explorador de ficheiros com dump de cartuchos e acesso à NAND.",
        "category": "files",
        "author": "DS-Homebrew",
        "version": "3.9.0",
        "gamebrew_slug": "GodMode9i",
        "install_key": "godmode9i",
        "warn_nand": False,
    },
    {
        "id": "ntm",
        "title": "NAND Title Manager",
        "description": "Instala e gere títulos na SysNAND / SDNAND (hiyaCFW).",
        "category": "system",
        "author": "Epicpkmn11 (Pk11)",
        "version": "0.5.1",
        "gamebrew_slug": "NAND_Title_Manager",
        "install_key": "ntm",
        "warn_nand": True,
    },
    {
        "id": "cart_flasher",
        "title": "Cart-Flasher",
        "description": "Backup e restauro de imagens flash de flashcarts Slot-1.",
        "category": "system",
        "author": "Tasken (Nimbo)",
        "version": "0.8-tinkatuff",
        "gamebrew_slug": "Cart-Flasher_DS",
        "install_key": "cart_flasher",
        "warn_nand": False,
    },
    {
        "id": "dsfetch",
        "title": "DSFetch",
        "description": "Informação do sistema no estilo fastfetch.",
        "category": "system",
        "author": "xPsycho999",
        "version": "1.0.0",
        "gamebrew_slug": "DSFetch",
        "install_key": "dsfetch",
        "warn_nand": False,
    },
    {
        "id": "rocket_video",
        "title": "Rocket Video Player",
        "description": "Reprodutor de vídeo (.rvid) para DS e DSi.",
        "category": "media",
        "author": "RocketRobz",
        "version": "2.3.0",
        "gamebrew_slug": "Rocket_Video_Player",
        "install_key": "rocket_video",
        "warn_nand": False,
    },
    {
        "id": "fastvideo_ds",
        "title": "FastVideoDSPlayer 2",
        "description": "Fork actualizado do FastVideoDS Player (.fv).",
        "category": "media",
        "author": "Mathos42",
        "version": "1.7",
        "gamebrew_slug": "FastVideoDSPlayer_2",
        "install_key": "fastvideo_ds",
        "warn_nand": False,
    },
    {
        "id": "ftpd",
        "title": "ftpd",
        "description": "Servidor FTP Wi‑Fi para transferir ficheiros com o PC.",
        "category": "utilities",
        "author": "mtheall",
        "version": "3.2.1",
        "gamebrew_slug": "Ftpd_NDS",
        "install_key": "ftpd",
        "warn_nand": False,
    },
    {
        "id": "kekatsu",
        "title": "Kekatsu DS",
        "description": "Descarregador de conteúdo no próprio console.",
        "category": "utilities",
        "author": "cavv-dev",
        "version": "1.2.0",
        "gamebrew_slug": "Kekatsu_DS",
        "install_key": "kekatsu",
        "warn_nand": False,
    },
    {
        "id": "dsidl",
        "title": "Dsidl",
        "description": "Descarrega ficheiros para o DSi via código QR.",
        "category": "utilities",
        "author": "Epicpkmn11",
        "version": "0.1.1",
        "gamebrew_slug": "Dsidl",
        "install_key": "dsidl",
        "warn_nand": False,
    },
    {
        "id": "ds_micpassthrough",
        "title": "ds-micpassthrough",
        "description": "Encaminha o microfone do DS/DSi para o PC.",
        "category": "utilities",
        "author": "korbosoft",
        "version": "3.0.0",
        "gamebrew_slug": "Ds-micpassthrough",
        "install_key": "ds_micpassthrough",
        "warn_nand": False,
    },
    {
        "id": "ndsi_savedumper",
        "title": "NDSi SaveDumper",
        "description": "Extrai e injeta saves de cartuchos originais no DSi.",
        "category": "saves",
        "author": "edo9300",
        "version": "1.2",
        "gamebrew_slug": "NDSi_SaveDumper",
        "install_key": "ndsi_savedumper",
        "warn_nand": False,
    },
    {
        "id": "pkmn_chest",
        "title": "pkmn-chest",
        "description": "Banco Pokémon para jogos das gerações 3 a 5.",
        "category": "saves",
        "author": "Universal-Team / Pk11",
        "version": "2.2",
        "gamebrew_slug": "Pkmn-chest",
        "install_key": "pkmn_chest",
        "warn_nand": False,
    },
]


def _normalize(entry: Dict[str, Any]) -> Dict[str, Any]:
    key = entry["install_key"]
    dest = FILENAMES.get(key) or f"{entry['id']}.nds"
    slug = entry["gamebrew_slug"]
    return {
        "id": entry["id"],
        "title": entry["title"],
        "description": entry["description"],
        "category": entry["category"],
        "category_label": CATEGORIES.get(entry["category"], entry["category"]),
        "author": entry["author"],
        "version": entry["version"],
        "gamebrew_slug": slug,
        "gamebrew_url": f"{GAMEBREW_WIKI_PREFIX}{slug}",
        "install_key": key,
        "dest_filename": dest,
        "warn_nand": bool(entry.get("warn_nand")),
        "installable": key in PINNED_SHA256 and key in FILENAMES,
        "setup_notes": notes_for(entry["id"]),
    }


def list_apps() -> List[Dict[str, Any]]:
    """Lista completa do catálogo (só leitura)."""
    return [_normalize(e) for e in _APPS]


def get_app(app_id: str) -> Optional[Dict[str, Any]]:
    if not isinstance(app_id, str) or not app_id.strip():
        return None
    want = app_id.strip().lower()
    for entry in _APPS:
        if entry["id"] == want:
            return _normalize(entry)
    return None


def build_catalog_payload() -> Dict[str, Any]:
    apps = list_apps()
    cats = [
        {"id": cid, "label": label}
        for cid, label in CATEGORIES.items()
        if any(a["category"] == cid for a in apps)
    ]
    return {
        "success": True,
        "apps": apps,
        "categories": cats,
        "attribution": (
            "Seleção baseada na lista de aplicações da GameBrew; "
            "downloads oficiais com verificação SHA-256."
        ),
    }


def installable_stems() -> frozenset:
    """Stems de ficheiro (sem extensão) para classificação em rom_cleaner."""
    stems = set()
    for app in list_apps():
        name = app.get("dest_filename") or ""
        stem = name.rsplit(".", 1)[0].lower() if name else ""
        if stem:
            stems.add(stem)
        stems.add(str(app["id"]).lower().replace("_", "-"))
        stems.add(str(app["id"]).lower().replace("_", ""))
    return frozenset(stems)
