"""Regras da PicoDex (rasalopa/picodex, MIT) usadas pelo Route Pico.

Onde o Route Pico e a PicoDex fazem a mesma coisa, o Route Pico segue a PicoDex.
Este módulo é o port em Python das partes partilhadas; a versão de origem está
fixada em ``core/data/upstreams.lock.json`` (entrada ``picodex``) e
``tools/sync_upstreams.py`` avisa quando a PicoDex publica uma versão nova.

* Sistemas e pastas de jogos (``src/lib/systems.ts``)
* Onde gravar capa/ícone para o launcher a encontrar (``src/lib/artPaths.ts``)
* Correspondência de títulos com o catálogo libretro-thumbnails
  (``src/lib/matching.ts`` + ``src/lib/thumbnails.ts``)
* Título do banner NDS quando o nome do ficheiro não diz nada
  (``src/views/CoversView.tsx``)

A identificação da versão do Pico Loader usa o manifesto da própria PicoDex
(``src/data/loaderReleases.json``); ver ``core.routedex.identify_loader``.
"""

from __future__ import annotations

import difflib
import json
import os
import re
import struct
import time
import unicodedata
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Optional

from core.cache import CACHE_DIR

PICODEX_REPO = "rasalopa/picodex"


# --------------------------------------------------------------------------- #
# Sistemas (systems.ts)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class System:
    id: str
    label: str
    games_dir: str
    extensions: tuple[str, ...]
    libretro_repo: str
    cover_keying: str  # "gamecode" | "filename"


SYSTEMS: tuple[System, ...] = (
    System("nds", "Nintendo DS", "nds", (".nds", ".dsi", ".srl"), "Nintendo_-_Nintendo_DS", "gamecode"),
    System("gba", "Game Boy Advance", "gba", (".gba", ".agb"), "Nintendo_-_Game_Boy_Advance", "gamecode"),
    System("gb", "Game Boy", "gb", (".gb",), "Nintendo_-_Game_Boy", "filename"),
    System("gbc", "Game Boy Color", "gb", (".gbc",), "Nintendo_-_Game_Boy_Color", "filename"),
    System("gen", "Mega Drive / Genesis", "gen", (".md", ".gen", ".smd"), "Sega_-_Mega_Drive_-_Genesis", "filename"),
    System("sms", "Master System", "sms", (".sms",), "Sega_-_Master_System_-_Mark_III", "filename"),
    System("gg", "Game Gear", "gg", (".gg",), "Sega_-_Game_Gear", "filename"),
    System("nes", "NES", "nes", (".nes",), "Nintendo_-_Nintendo_Entertainment_System", "filename"),
    System("snes", "Super Nintendo", "snes", (".sfc", ".smc"), "Nintendo_-_Super_Nintendo_Entertainment_System", "filename"),
    System("ws", "WonderSwan", "ws", (".ws",), "Bandai_-_WonderSwan", "filename"),
    System("wsc", "WonderSwan Color", "ws", (".wsc",), "Bandai_-_WonderSwan_Color", "filename"),
    System("ngp", "Neo Geo Pocket", "ngp", (".ngp",), "SNK_-_Neo_Geo_Pocket", "filename"),
    System("ngc", "Neo Geo Pocket Color", "ngp", (".ngc",), "SNK_-_Neo_Geo_Pocket_Color", "filename"),
)

_BY_EXT = {ext: s for s in SYSTEMS for ext in s.extensions}
_BY_ID = {s.id: s for s in SYSTEMS}


def system_for_extension(file_name: str) -> Optional[System]:
    dot = file_name.rfind(".")
    if dot <= 0:
        return None
    return _BY_EXT.get(file_name[dot:].lower())


def system_by_id(system_id: str) -> Optional[System]:
    return _BY_ID.get(system_id)


def games_dir_by_extension() -> dict[str, str]:
    """Extensão → pasta de jogos da PicoDex (``Games/<pasta>/``)."""
    return {ext: s.games_dir for s in SYSTEMS for ext in s.extensions}


def libretro_repo_for_name(libretro_system_name: str) -> str:
    """'Nintendo - Nintendo DS' → 'Nintendo_-_Nintendo_DS' (nome do repo libretro-thumbnails)."""
    return libretro_system_name.replace(" ", "_")


# --------------------------------------------------------------------------- #
# Onde gravar a arte (artPaths.ts)
# --------------------------------------------------------------------------- #


def is_usable_game_code(code: Optional[str]) -> bool:
    if not code:
        return False
    if any(ord(c) < 0x20 or ord(c) >= 0x7F for c in code):
        return False
    return any(c != "#" for c in code)


def resolve_art_target(
    mount_path: str, kind_folder: str, file_name: str, system: Optional[System], game_code: Optional[str]
) -> str:
    """Ficheiro onde uma capa/ícone NOVO tem de ser gravado (um só destino).

    Um ``user/<ficheiro>.bmp`` já no cartão tem prioridade no launcher e é
    substituído no sítio; senão sistemas por game code com código utilizável
    vão para ``<nds|gba>/<CODE>.bmp``; o resto vai para ``user/``.
    ``kind_folder``: "covers" | "icons" | "banners".
    """
    base = os.path.join(mount_path, "_pico", kind_folder)
    user = os.path.join(base, "user", f"{file_name}.bmp")
    if os.path.isfile(user):
        return user
    if system is not None and system.cover_keying == "gamecode" and is_usable_game_code(game_code):
        sub = "nds" if system.id == "nds" else "gba"
        return os.path.join(base, sub, f"{game_code.upper()}.bmp")
    return user


# --------------------------------------------------------------------------- #
# Correspondência de títulos (matching.ts)
# --------------------------------------------------------------------------- #

FUZZY_CUTOFF = 0.85
SEARCH_CUTOFF = 0.5
DEFAULT_REGION_PREFS: tuple[str, ...] = ("(Europe", "(USA", "(World")
REGION_PREFS_BY_GBA_CODE: dict[str, tuple[str, ...]] = {
    "E": ("(USA", "(World", "(Europe"),
    "P": ("(Europe", "(World", "(USA"),
    "S": ("(Spain", "(Europe", "(USA"),
    "F": ("(France", "(Europe", "(USA"),
    "D": ("(Germany", "(Europe", "(USA"),
    "I": ("(Italy", "(Europe", "(USA"),
    "J": ("(Japan", "(USA", "(Europe"),
}
_VARIANT_ENTRY = re.compile(r"\([^()]*\b(?:demo|kiosk|proto(?:type)?|beta|sample|promo|debug|trial)\b[^()]*\)", re.I)


def normalize_title(s: str) -> str:
    t = "".join(ch for ch in unicodedata.normalize("NFKD", s) if ord(ch) <= 0x7F)
    t = re.sub(r"\(.*?\)", "", t)
    t = re.sub(r"[^a-z0-9]+", " ", t.lower())
    t = re.sub(r"\b(?:the|a|an|el|la|los|las)\b", " ", t)
    return " ".join(t.split())


def similarity_ratio(a: str, b: str) -> float:
    """Igual a ``similarityRatio`` da PicoDex: difflib sem heurística de lixo."""
    if not a and not b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def is_degenerate_title(title: str) -> bool:
    return len(normalize_title(title)) <= 2


def region_prefs_for(system_id: str, game_code: Optional[str]) -> tuple[str, ...]:
    if system_id == "gba" and game_code and len(game_code) == 4:
        return REGION_PREFS_BY_GBA_CODE.get(game_code[3], DEFAULT_REGION_PREFS)
    return DEFAULT_REGION_PREFS


def _strip_png(entry: str) -> str:
    return entry[:-4] if entry.lower().endswith(".png") else entry


def pick_boxart(title: str, catalog: list[str], region_prefs: tuple[str, ...] = DEFAULT_REGION_PREFS) -> Optional[str]:
    by_norm: dict[str, list[str]] = {}
    for entry in catalog:
        by_norm.setdefault(normalize_title(_strip_png(entry)), []).append(entry)
    key = normalize_title(title)
    if not key:
        return None
    candidates = by_norm.get(key)
    if not candidates and len(key) <= 2:
        return None
    prefix_key: Optional[str] = None
    if not candidates:
        for k in by_norm:
            if key.startswith(k + " ") or k.startswith(key + " "):
                if prefix_key is None or len(k) > len(prefix_key):
                    prefix_key = k
        if prefix_key is not None and similarity_ratio(key, prefix_key) >= FUZZY_CUTOFF:
            candidates = by_norm.get(prefix_key)
    if not candidates:
        best_key, best_ratio = None, 0.0
        for k in by_norm:
            r = similarity_ratio(key, k)
            if r >= FUZZY_CUTOFF and r > best_ratio:
                best_key, best_ratio = k, r
        if best_key is not None:
            candidates = by_norm.get(best_key)
    if not candidates and prefix_key is not None:
        candidates = by_norm.get(prefix_key)
    if not candidates:
        return None
    for pref in region_prefs:
        in_region = [c for c in candidates if pref in c]
        if in_region:
            return next((c for c in in_region if not _VARIANT_ENTRY.search(c)), in_region[0])
    return next((c for c in candidates if not _VARIANT_ENTRY.search(c)), candidates[0])


def search_catalog(catalog: list[str], query: str, limit: int = 24) -> list[str]:
    entries = sorted(set(catalog), key=lambda e: (e.lower(), e))
    keys = [normalize_title(_strip_png(e)) for e in entries]
    key = normalize_title(query)
    if not key:
        return entries[:limit]
    substring = [e for e, k in zip(entries, keys) if key in k]
    substring.sort(key=len)
    if len(substring) >= limit:
        return substring[:limit]
    fuzzy = []
    for e, k in zip(entries, keys):
        if key in k:
            continue
        r = similarity_ratio(key, k)
        if r >= SEARCH_CUTOFF:
            fuzzy.append((r, e))
    fuzzy.sort(key=lambda t: (-t[0], len(t[1])))
    return (substring + [e for _r, e in fuzzy])[:limit]


# --------------------------------------------------------------------------- #
# Catálogo libretro-thumbnails (thumbnails.ts)
# --------------------------------------------------------------------------- #

_BOXARTS_PREFIX = "Named_Boxarts/"
_CATALOG_TTL_S = 7 * 24 * 3600
_REPO_RE = re.compile(r"^[A-Za-z0-9_\-]+$")
_mem_catalog: dict[str, list[str]] = {}


class CatalogError(RuntimeError):
    """Catálogo indisponível (rede, limite da API do GitHub, resposta inválida)."""


def catalog_url(repo: str) -> str:
    return f"https://api.github.com/repos/libretro-thumbnails/{repo}/git/trees/master?recursive=1"


def boxart_url(repo: str, name: str) -> str:
    return (
        f"https://raw.githubusercontent.com/libretro-thumbnails/{repo}/master/"
        f"{_BOXARTS_PREFIX}{urllib.parse.quote(name, safe='')}"
    )


def parse_catalog(trees_json: object) -> list[str]:
    if not isinstance(trees_json, dict) or not isinstance(trees_json.get("tree"), list):
        raise CatalogError("Resposta inesperada da API do GitHub (árvore de capas).")
    names = []
    for entry in trees_json["tree"]:
        path = entry.get("path") if isinstance(entry, dict) else None
        if isinstance(path, str) and path.startswith(_BOXARTS_PREFIX) and path.endswith(".png"):
            names.append(path[len(_BOXARTS_PREFIX):])
    return names


def _cache_path(repo: str) -> str:
    return os.path.join(CACHE_DIR, "libretro_catalog", f"{repo}.json")


def fetch_catalog(repo: str, *, timeout: int = 20, opener=urllib.request.urlopen) -> list[str]:
    """Nomes das capas de um repo libretro-thumbnails (cache em disco 7 dias).

    A API do GitHub permite 60 pedidos/hora sem conta; a cache evita gastar
    um pedido por jogo. Uma cache expirada continua a servir se a rede falhar.
    """
    if not _REPO_RE.match(repo or ""):
        raise CatalogError("Repositório de capas inválido.")
    if repo in _mem_catalog:
        return _mem_catalog[repo]
    path = _cache_path(repo)
    stale: Optional[list[str]] = None
    try:
        with open(path, encoding="utf-8") as f:
            cached = json.load(f)
        if isinstance(cached, dict) and isinstance(cached.get("names"), list):
            stale = [n for n in cached["names"] if isinstance(n, str)]
            if time.time() - float(cached.get("fetched_at", 0)) < _CATALOG_TTL_S:
                _mem_catalog[repo] = stale
                return stale
    except (OSError, ValueError, TypeError):
        pass
    req = urllib.request.Request(
        catalog_url(repo), headers={"User-Agent": "RoutePico", "Accept": "application/vnd.github+json"}
    )
    try:
        with opener(req, timeout=timeout) as resp:  # nosec B310 - URL fixa api.github.com
            names = parse_catalog(json.loads(resp.read().decode("utf-8")))
    except CatalogError:
        raise
    except Exception as e:
        if stale is not None:
            _mem_catalog[repo] = stale
            return stale
        msg = str(e)
        if "403" in msg or "429" in msg:
            raise CatalogError("Limite da API do GitHub atingido (60 pedidos/hora sem conta); tente mais tarde.") from e
        raise CatalogError(f"Catálogo de capas indisponível: {e}") from e
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".partial"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"fetched_at": time.time(), "names": names}, f)
    os.replace(tmp, path)
    _mem_catalog[repo] = names
    return names


# --------------------------------------------------------------------------- #
# Título do banner NDS (readNdsBannerTitle)
# --------------------------------------------------------------------------- #


def read_nds_banner_title(path: str) -> Optional[str]:
    """Primeira linha do título inglês do banner da ROM, ou None."""
    try:
        with open(path, "rb") as f:
            head = f.read(0x6C)
            if len(head) < 0x6C:
                return None
            off = struct.unpack_from("<I", head, 0x68)[0]
            if not off:
                return None
            f.seek(off + 0x340)
            raw = f.read(0x100)
    except OSError:
        return None
    end = 0
    while end + 1 < len(raw) and (raw[end] or raw[end + 1]):
        end += 2
    text = raw[:end].decode("utf-16-le", "replace").strip()
    first = text.split("\n", 1)[0].strip()
    return first or None
