"""Cache local de downloads com verificação SHA-256."""

from __future__ import annotations

import hashlib
import os
import shutil
import urllib.request
from typing import Optional

from core.logging_util import emit_log

CACHE_DIR = os.path.expanduser("~/.dsi_sd_studio_cache")
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) DSi-SD-Studio/1.0"

# Hashes conhecidos para artefatos com URL estável (dsi.cfw.guide).
# Se o upstream mudar o arquivo, o cache será invalidado e o download falhará
# até o pin ser atualizado — preferível a usar um binário corrompido.
PINNED_SHA256 = {
    "pit_facebook": "ca4c197ef81283ad0c802fdc39bcb6c880e2e182cb7ac5c456a68368e50bbe14",
    "pit_no_facebook": "9f2b97bfb9569723ed5c0c48f314ab8c94e56e855acb468db727b8ecf059342b",
    "dumptool": "313b255a754bda4d06d6f761a7490b4f1675c957c41676119330520cb09a47ea",
}

URLS = {
    "pit_facebook": "https://dsi.cfw.guide/assets/files/memory_pit/768_1024/pit.bin",
    "pit_no_facebook": "https://dsi.cfw.guide/assets/files/memory_pit/256/pit.bin",
    "dumptool": "https://dsi.cfw.guide/assets/files/dumptool/boot.nds",
    "unlaunch": (
        "https://github.com/edo9300/unlaunch-installer/releases/latest/download/"
        "unlaunch-installer.dsi"
    ),
    "twilight_7z": (
        "https://github.com/DS-Homebrew/TWiLightMenu/releases/latest/download/"
        "TWiLightMenu-DSi.7z"
    ),
}

FILENAMES = {
    "pit_facebook": "pit_facebook.bin",
    "pit_no_facebook": "pit_no_facebook.bin",
    "dumptool": "dumptool.nds",
    "unlaunch": "unlaunch.dsi",
    "twilight_7z": "TWiLightMenu-DSi.7z",
}

MIN_SIZES = {
    "pit_facebook": 100,
    "pit_no_facebook": 100,
    "dumptool": 1024,
    "unlaunch": 1024,
    "twilight_7z": 1024 * 100,
}


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
            return f.read().strip().split()[0].lower()
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
    if size < MIN_SIZES.get(key, 1):
        return False
    if _looks_like_html(path):
        return False

    digest = _sha256_file(path)
    pinned = PINNED_SHA256.get(key)
    if pinned:
        return digest == pinned.lower()

    side = _read_sidecar(path)
    if side:
        return digest == side
    # Sem pin nem sidecar: aceita se tamanho ok e não for HTML;
    # grava sidecar para as próximas leituras.
    _write_sidecar(path, digest)
    return True


def download_url(url: str, target_path: str, log_callback=None) -> None:
    """Baixa URL para target_path com User-Agent consistente."""
    emit_log(log_callback, f"Baixando de {url}...")
    headers = {"User-Agent": USER_AGENT}
    req = urllib.request.Request(url, headers=headers)
    tmp_path = f"{target_path}.partial"
    try:
        with urllib.request.urlopen(req, timeout=120) as resp, open(tmp_path, "wb") as out:
            shutil.copyfileobj(resp, out)
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
    Garante que o artefato `key` esteja no cache local e íntegro.
    Invalida e rebaixa se o arquivo estiver vazio, for HTML ou falhar no SHA-256.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    filename = FILENAMES.get(key)
    if not filename:
        raise ValueError(f"Arquivo de cache desconhecido para a chave: {key}")
    target_path = os.path.join(CACHE_DIR, filename)

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
    pinned = PINNED_SHA256.get(key)
    if pinned and digest != pinned.lower():
        try:
            os.remove(target_path)
        except OSError:
            pass
        raise RuntimeError(
            f"Integridade de {key} falhou (SHA-256 diferente do esperado). "
            "O arquivo upstream pode ter mudado."
        )

    _write_sidecar(target_path, digest)
    emit_log(
        log_callback,
        f"✅ {key} baixado com sucesso ({os.path.getsize(target_path)} bytes).",
    )
    return target_path
