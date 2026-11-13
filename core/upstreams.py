"""Fontes oficiais do Route Pico — registo único.

Cinco repositórios, e só estes, alimentam o ecossistema DSPico do app:

* ``rasalopa/picodex`` — regras e dados que o RouteDex segue (MIT)
* ``LNH-team/pico-launcher`` — Pico Launcher oficial (padrão)
* ``LNH-team/pico-loader`` — Pico Loader oficial (padrão; asset DSPICO)
* ``rasalopa/pico-launcher-enhanced`` — Pico Launcher Enhanced (opcional)
* ``rasalopa/pico-loader`` — Pico Loader Enhanced (opcional)

As versões e digests em uso estão em ``core/data/upstreams.lock.json``.
``tools/sync_upstreams.py --apply`` atualiza o lock a partir das releases mais
recentes (o workflow ``upstreams.yml`` corre-o toda a semana e abre um PR);
``--check`` falha se alguma fonte tiver release mais nova que o lock.
``core.cache_pins`` lê daqui os pins destes pacotes, ``core.updates`` a
allowlist de downloads e ``core.routedex`` o manifesto do loader da PicoDex.
"""

from __future__ import annotations

import json
import os
from typing import Any

_HERE = os.path.dirname(os.path.abspath(__file__))
LOCK_PATH = os.path.join(_HERE, "data", "upstreams.lock.json")
PICODEX_DATA_DIR = os.path.join(_HERE, "data", "picodex")

# id → definição. ``cache_key`` liga ao cache pinado (core.cache_pins);
# ``asset_re`` escolhe o asset da release; ``files`` (só PicoDex) são ficheiros
# do repositório copiados para core/data/picodex/ na tag fixada.
UPSTREAMS: dict[str, dict[str, Any]] = {
    "picodex": {
        "repo": "rasalopa/picodex",
        "label": "PicoDex",
        "license": "MIT",
        "role": "Regras e dados do RouteDex (manifesto do Pico Loader, capas, pastas, saúde do cartão)",
        "files": {"src/data/loaderReleases.json": "loaderReleases.json"},
    },
    "pico_launcher": {
        "repo": "LNH-team/pico-launcher",
        "label": "Pico Launcher",
        "license": "Zlib",
        "role": "Launcher oficial (padrão)",
        "cache_key": "pico_launcher",
        "asset_re": r"^Pico[._]Launcher\.zip$",
    },
    "pico_loader": {
        "repo": "LNH-team/pico-loader",
        "label": "Pico Loader",
        "license": "Zlib",
        "role": "Loader oficial (padrão, build DSPICO)",
        "cache_key": "pico_loader_dspico",
        "asset_re": r"^Pico_Loader_DSPICO\.zip$",
    },
    "pico_launcher_enhanced": {
        "repo": "rasalopa/pico-launcher-enhanced",
        "label": "Pico Launcher Enhanced",
        "license": "Zlib",
        "role": "Launcher Enhanced (opcional, não oficial)",
        "cache_key": "pico_launcher_enhanced",
        "asset_re": r"^Pico_Launcher_Enhanced\.zip$",
    },
    "pico_loader_enhanced": {
        "repo": "rasalopa/pico-loader",
        "label": "Pico Loader Enhanced",
        "license": "Zlib",
        "role": "Loader Enhanced (opcional, não oficial, só DSPico)",
        "cache_key": "pico_loader_enhanced_dspico",
        "asset_re": r"^Pico_Loader_Enhanced_v[0-9.]+\.zip$",
    },
}

OFFICIAL_REPOS = frozenset(u["repo"] for u in UPSTREAMS.values())


def load_lock() -> dict[str, Any]:
    with open(LOCK_PATH, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("upstreams.lock.json inválido.")
    return data


def lock_entry(upstream_id: str) -> dict[str, Any]:
    entry = load_lock().get(upstream_id)
    if not isinstance(entry, dict):
        raise KeyError(f"Fonte sem entrada no lock: {upstream_id}")
    return entry


def pinned_assets() -> dict[str, dict[str, Any]]:
    """cache_key → {repo, tag, asset, sha256, url} para os pacotes com asset."""
    lock = load_lock()
    out: dict[str, dict[str, Any]] = {}
    for uid, meta in UPSTREAMS.items():
        key = meta.get("cache_key")
        entry = lock.get(uid) or {}
        if not key or not entry.get("asset"):
            continue
        out[key] = {
            "repo": meta["repo"],
            "tag": entry["tag"],
            "asset": entry["asset"],
            "sha256": entry["sha256"],
            "url": f"https://github.com/{meta['repo']}/releases/download/{entry['tag']}/{entry['asset']}",
        }
    return out


def picodex_data_path(name: str) -> str:
    return os.path.join(PICODEX_DATA_DIR, name)
