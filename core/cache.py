"""Cache local de downloads com verificação SHA-256."""

from __future__ import annotations

import hashlib
import os
import shutil
import urllib.request
from typing import Optional

from core import __version__ as _APP_VERSION
from core.logging_util import emit_log

CACHE_DIR = os.path.expanduser("~/.route_1_kit_cache")
USER_AGENT = (
    f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Route-1-Kit/{_APP_VERSION}"
)

# Pins oficiais — atualizar com tools/update_pins.py após verificar digest no GitHub.
# Origem documentada:
#   pit_*:     dsi.cfw.guide Memory Pit (estável)
#   dumptool:  dsi.cfw.guide dumpTool boot.nds
#   unlaunch:  edo9300/unlaunch-installer v2.6 (digest GitHub Release)
#   twilight:  DS-Homebrew/TWiLightMenu v27.24.1 (digest GitHub Release)
#   godmode9i + apps do catálogo: releases GitHub (digest verificado no download)
PINNED_SHA256 = {
    "pit_facebook": "ca4c197ef81283ad0c802fdc39bcb6c880e2e182cb7ac5c456a68368e50bbe14",
    "pit_no_facebook": "9f2b97bfb9569723ed5c0c48f314ab8c94e56e855acb468db727b8ecf059342b",
    "dumptool": "313b255a754bda4d06d6f761a7490b4f1675c957c41676119330520cb09a47ea",
    "unlaunch": "14ba0b4af84e801206e20cffdf55002e3b4b5dd8be18abf3c0977011b23f1aeb",
    "twilight_7z": "c04fc66305ce8dc80e69aa4070d3ce966f04868881663f57b91f68d687a2bb90",
    "godmode9i": "7fcf94f3b840ed240175a386c0a28c246bd40bcc791e8505c100ca78ba49b6e1",
    "ftpd": "63cf06c4e13772544630f60c91921c9fd616ad507b55174cb057fc3125fa8423",
    "pkmn_chest": "7e06166b565e89492a8489bfbf4d4c30e7e537de1517faa1ab2da5ec5f6ebf13",
    "ndsi_savedumper": "528df32883ca0380c37d81368eed8c40bb1346cae24e441c2fc28c2c9a9e9690",
    "ntm": "2563f8c0481c92ad361eccf7849f4bfeb1d6e6af3c88337f08d14ba2353b8797",
    "rocket_video": "f085152c1dde9d2b372fb0137b224c73d516cae4ba833f2f9fdda994e4bdf6e8",
    "ds_micpassthrough": "fba5e4725d73ee96117fddca4d67d029659b6a76b15db25eddb3d6dd936c6d3e",
    "dsfetch": "13b2022c0603ac7b60e8903526bb8487d22a37a72a61f7c8d56e62227c5fbac4",
    "cart_flasher": "03145f84957afdee5c27ba1cada7fcd1e9b887fd39da8c5967ae60d6b787b59a",
    "fastvideo_ds": "09e480591acd63073319e9dd191d32d8a3d85543c82037f7d1c966941b039f61",
    "dsidl": "23f56f0c6b9d0780f6b8306b25879c0ae2c1cc87fbb020d0fa4a1cd1897db30b",
    "kekatsu": "7e298996478fe22ffd1209a82aa153b859d104c0afae12aef77e716b0992aa87",
}

PIN_META = {
    "unlaunch": {
        "repo": "edo9300/unlaunch-installer",
        "tag": "v2.6",
        "asset": "unlaunch-installer.dsi",
    },
    "twilight_7z": {
        "repo": "DS-Homebrew/TWiLightMenu",
        "tag": "v27.24.1",
        "asset": "TWiLightMenu-DSi.7z",
    },
    "godmode9i": {
        "repo": "DS-Homebrew/GodMode9i",
        "tag": "v3.9.0",
        "asset": "GodMode9i.dsi",
    },
    "ftpd": {"repo": "mtheall/ftpd", "tag": "v3.2.1", "asset": "ftpd.nds"},
    "pkmn_chest": {
        "repo": "Universal-Team/pkmn-chest",
        "tag": "v2.2",
        "asset": "pkmn-chest.nds",
    },
    "ndsi_savedumper": {
        "repo": "edo9300/ndsi-savedumper",
        "tag": "1.2",
        "asset": "savedumper.nds",
    },
    "ntm": {"repo": "Epicpkmn11/NTM", "tag": "v0.5.1", "asset": "NTM.dsi"},
    "rocket_video": {
        "repo": "RocketRobz/RocketVideoPlayer",
        "tag": "v2.3.0",
        "asset": "RocketVideoPlayer.dsi",
    },
    "ds_micpassthrough": {
        "repo": "korbosoft/ds-micpassthrough",
        "tag": "v3.0.0",
        "asset": "ds-micpassthrough.nds",
    },
    "dsfetch": {
        "repo": "xPsycho999/DSFetch",
        "tag": "v1.0.0",
        "asset": "DSFetch.nds",
    },
    "cart_flasher": {
        "repo": "tasken/cart-flasher",
        "tag": "v0.8-tinkatuff",
        "asset": "cart_flasher.nds",
    },
    "fastvideo_ds": {
        "repo": "Mathos42/FastVideoDSPlayer-2",
        "tag": "v1.7",
        "asset": "FastVideoDS.nds",
    },
    "dsidl": {"repo": "Epicpkmn11/dsidl", "tag": "v0.1.1", "asset": "dsidl.dsi"},
    "kekatsu": {
        "repo": "cavv-dev/Kekatsu-DS",
        "tag": "v1.2.0",
        "asset": "Kekatsu.nds",
    },
}

URLS = {
    "pit_facebook": "https://dsi.cfw.guide/assets/files/memory_pit/768_1024/pit.bin",
    "pit_no_facebook": "https://dsi.cfw.guide/assets/files/memory_pit/256/pit.bin",
    "dumptool": "https://dsi.cfw.guide/assets/files/dumptool/boot.nds",
    "unlaunch": (
        "https://github.com/edo9300/unlaunch-installer/releases/download/v2.6/"
        "unlaunch-installer.dsi"
    ),
    "twilight_7z": (
        "https://github.com/DS-Homebrew/TWiLightMenu/releases/download/v27.24.1/"
        "TWiLightMenu-DSi.7z"
    ),
    "godmode9i": (
        "https://github.com/DS-Homebrew/GodMode9i/releases/download/v3.9.0/"
        "GodMode9i.dsi"
    ),
    "ftpd": "https://github.com/mtheall/ftpd/releases/download/v3.2.1/ftpd.nds",
    "pkmn_chest": (
        "https://github.com/Universal-Team/pkmn-chest/releases/download/v2.2/"
        "pkmn-chest.nds"
    ),
    "ndsi_savedumper": (
        "https://github.com/edo9300/ndsi-savedumper/releases/download/1.2/"
        "savedumper.nds"
    ),
    "ntm": "https://github.com/Epicpkmn11/NTM/releases/download/v0.5.1/NTM.dsi",
    "rocket_video": (
        "https://github.com/RocketRobz/RocketVideoPlayer/releases/download/v2.3.0/"
        "RocketVideoPlayer.dsi"
    ),
    "ds_micpassthrough": (
        "https://github.com/korbosoft/ds-micpassthrough/releases/download/v3.0.0/"
        "ds-micpassthrough.nds"
    ),
    "dsfetch": (
        "https://github.com/xPsycho999/DSFetch/releases/download/v1.0.0/DSFetch.nds"
    ),
    "cart_flasher": (
        "https://github.com/tasken/cart-flasher/releases/download/v0.8-tinkatuff/"
        "cart_flasher.nds"
    ),
    "fastvideo_ds": (
        "https://github.com/Mathos42/FastVideoDSPlayer-2/releases/download/v1.7/"
        "FastVideoDS.nds"
    ),
    "dsidl": (
        "https://github.com/Epicpkmn11/dsidl/releases/download/v0.1.1/dsidl.dsi"
    ),
    "kekatsu": (
        "https://github.com/cavv-dev/Kekatsu-DS/releases/download/v1.2.0/Kekatsu.nds"
    ),
}

FILENAMES = {
    "pit_facebook": "pit_facebook.bin",
    "pit_no_facebook": "pit_no_facebook.bin",
    "dumptool": "dumptool.nds",
    "unlaunch": "unlaunch.dsi",
    "twilight_7z": "TWiLightMenu-DSi.7z",
    "godmode9i": "GodMode9i.dsi",
    "ftpd": "ftpd.nds",
    "pkmn_chest": "pkmn-chest.nds",
    "ndsi_savedumper": "savedumper.nds",
    "ntm": "NTM.dsi",
    "rocket_video": "RocketVideoPlayer.dsi",
    "ds_micpassthrough": "ds-micpassthrough.nds",
    "dsfetch": "DSFetch.nds",
    "cart_flasher": "cart_flasher.nds",
    "fastvideo_ds": "FastVideoDS.nds",
    "dsidl": "dsidl.dsi",
    "kekatsu": "Kekatsu.nds",
}

MIN_SIZES = {
    "pit_facebook": 48032,
    "pit_no_facebook": 48032,
    "dumptool": 1024,
    "unlaunch": 1024,
    "twilight_7z": 1024 * 100,
    "godmode9i": 1024,
    "ftpd": 1024,
    "pkmn_chest": 1024 * 100,
    "ndsi_savedumper": 1024,
    "ntm": 1024,
    "rocket_video": 1024,
    "ds_micpassthrough": 1024,
    "dsfetch": 1024,
    "cart_flasher": 1024,
    "fastvideo_ds": 1024,
    "dsidl": 1024,
    "kekatsu": 1024,
}


def ensure_cache_dir() -> str:
    """Cria o diretório de cache com permissões restritas (0o700)."""
    os.makedirs(CACHE_DIR, mode=0o700, exist_ok=True)
    try:
        os.chmod(CACHE_DIR, 0o700)  # nosemgrep: insecure-file-permissions — 0o700 é mais restritivo (só o dono)
    except OSError:
        pass
    return CACHE_DIR


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sidecar_path(target_path: str) -> str:
    return f"{target_path}.sha256"


def _read_sidecar(target_path: str) -> Optional[str]:
    side = _sidecar_path(target_path)
    if not os.path.isfile(side):
        return None
    try:
        with open(side, "r", encoding="utf-8") as f:
            parts = f.read().strip().split()
        if not parts:
            return None
        return parts[0].lower()
    except OSError:
        return None


def _write_sidecar(target_path: str, digest: str) -> None:
    with open(_sidecar_path(target_path), "w", encoding="utf-8") as f:
        f.write(f"{digest}\n")


def _looks_like_html(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            head = f.read(256).lstrip().lower()
        return head.startswith(b"<!doctype") or head.startswith(b"<html")
    except OSError:
        return False


def _is_valid_cached(key: str, path: str) -> bool:
    if not os.path.isfile(path):
        return False
    size = os.path.getsize(path)
    min_size = MIN_SIZES.get(key, 1)
    # Para pits, exigir tamanho exato
    if key in ("pit_facebook", "pit_no_facebook") and size != min_size:
        return False
    if size < min_size:
        return False
    if _looks_like_html(path):
        return False

    digest = _sha256_file(path)
    pinned = PINNED_SHA256.get(key)
    if not pinned:
        # Todos os artefatos oficiais devem ter pin; recusar aceitar sem pin.
        return False
    if digest != pinned.lower():
        return False

    # Sidecar é apenas detecção de corrupção local (opcional)
    side = _read_sidecar(path)
    if side and side != digest:
        return False
    return True


def download_url(url: str, target_path: str, log_callback=None) -> None:
    """Baixa URL HTTPS para target_path com User-Agent consistente."""
    if not url.startswith("https://"):
        raise ValueError(f"Apenas HTTPS é permitido: {url}")
    emit_log(log_callback, f"Baixando de {url}...")
    headers = {"User-Agent": USER_AGENT}
    req = urllib.request.Request(url, headers=headers)
    tmp_path = f"{target_path}.partial"
    try:
        # URLs vêm exclusivamente de URLS (constantes); não há input do usuário.
        with urllib.request.urlopen(req, timeout=120) as resp, open(tmp_path, "wb") as out:  # nosec B310  # nosemgrep: dynamic-urllib-use-detected
            shutil.copyfileobj(resp, out)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp_path, target_path)
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise


def ensure_cached(key: str, log_callback=None) -> str:
    """
    Garante que o artefato `key` esteja no cache local e íntegro (SHA-256 pinado).
    Invalida e rebaixa se o arquivo estiver vazio, for HTML ou falhar no pin.
    """
    ensure_cache_dir()
    filename = FILENAMES.get(key)
    if not filename:
        raise ValueError(f"Arquivo de cache desconhecido para a chave: {key}")
    target_path = os.path.join(CACHE_DIR, filename)

    pinned = PINNED_SHA256.get(key)
    if not pinned:
        raise ValueError(
            f"Sem pin SHA-256 para '{key}'. Atualize PINNED_SHA256 via tools/update_pins.py."
        )

    if _is_valid_cached(key, target_path):
        return target_path

    # Cache inválido → remover e baixar de novo
    for p in (target_path, _sidecar_path(target_path)):
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass

    url = URLS.get(key)
    if not url:
        raise ValueError(f"URL desconhecida para a chave: {key}")

    emit_log(log_callback, f"Baixando componente {key}...")
    download_url(url, target_path, log_callback)

    if not os.path.isfile(target_path) or os.path.getsize(target_path) < MIN_SIZES.get(key, 1):
        raise RuntimeError(f"Download de {key} falhou: arquivo vazio ou muito pequeno.")
    if _looks_like_html(target_path):
        try:
            os.remove(target_path)
        except OSError:
            pass
        raise RuntimeError(f"Download de {key} retornou HTML (possível erro 404/rate-limit).")

    digest = _sha256_file(target_path)
    if digest != pinned.lower():
        try:
            os.remove(target_path)
        except OSError:
            pass
        raise RuntimeError(
            f"Integridade de {key} falhou (SHA-256 diferente do esperado). "
            "O arquivo upstream pode ter mudado — rode tools/update_pins.py."
        )

    _write_sidecar(target_path, digest)
    emit_log(
        log_callback,
        f"✅ {key} baixado com sucesso ({os.path.getsize(target_path)} bytes).",
    )
    return target_path
