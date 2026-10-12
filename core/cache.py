"""Cache local de downloads com verificação SHA-256."""

from __future__ import annotations

import hashlib
import os
import urllib.request
from typing import List, Optional

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
#   twilight_vc: add-on Virtual Console (GameYob GB/GBC + outros) v27.24.1
#   godmode9i + apps do catálogo: releases GitHub (digest verificado no download)
#   hiyacfw / twlmagician_*: SDNAND via pipeline TWLMagician (tools pinados)
#   pico_*: LNH-team Pico Launcher + Loader DSPICO (só github.com/LNH-team/)
#   dspico_firmware_uf2: reservado — releases LNH ainda sem asset .uf2 (ver DSPICO_*)
#   hiya_launcher_*: launchers regionais do repo TWLMagician (pinados)

# Chaves de cache exclusivas do fluxo DSPico (allowlist — nunca mirrors de terceiros).
DSPICO_CACHE_KEYS = frozenset(
    {
        "pico_launcher",
        "pico_loader_dspico",
        "dspico_firmware_uf2",
    }
)
# dspico_firmware_uf2: não entra em PINNED_SHA256/URLS até o LNH publicar o .uf2
# oficial em https://github.com/LNH-team/dspico-firmware/releases — ver
# dspico_firmware_uf2_ready() abaixo.

# Emuladores Pico-Launcher (guia Sanrax) — fora do allowlist LNH-only.
# Digests verificados no download oficial (2026-10-08).
DSPICO_EMU_CACHE_KEYS = frozenset(
    {
        "emu_gbarunner3",
        "emu_gbarunner2",
        "emu_gameyob",
        "emu_nesds",
        "emu_stellads",
        "emu_a5200ds",
        "emu_a7800ds",
        "emu_a8ds",
        "emu_picodrive_twl",
        "emu_s8ds",
        "emu_ngpds",
        "emu_ngpds_settings",
        "emu_nitrografx",
        "emu_colecods",
        "emu_nintv_ds",
        "emu_snemulds_06a",
        "emu_snemulds_06d",
        "emu_jenesisds",
        "emu_neods",
        "emu_neods_ini",
    }
)

# Tabelas pesadas em core.cache_pins — acesso via __getattr__ / _pins().
_PIN_ATTRS = frozenset(
    {"PINNED_SHA256", "PIN_META", "URLS", "FILENAMES", "MIN_SIZES", "UrlEntry"}
)
_pins_mod = None


def _pins():
    """Import lazy de cache_pins (uma vez)."""
    global _pins_mod
    if _pins_mod is None:
        from core import cache_pins as mod

        _pins_mod = mod
    return _pins_mod


def __getattr__(name: str):
    if name in _PIN_ATTRS:
        return getattr(_pins(), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | set(_PIN_ATTRS))



def urls_for(key: str) -> List[str]:
    """Lista ordenada de URLs HTTPS para ``key`` (sempre lista, mesmo com 1 fonte)."""
    raw = _pins().URLS.get(key)
    if raw is None:
        return []
    if isinstance(raw, str):
        u = raw.strip()
        return [u] if u else []
    out: List[str] = []
    seen = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        u = item.strip()
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out

def dspico_firmware_uf2_ready() -> bool:
    """
    True só quando existir pin + URL HTTPS em github.com/LNH-team/ para o UF2.
    Releases actuais do firmware não publicam asset .uf2 (compilar via GUIDE).
    """
    pins = _pins()
    pin = pins.PINNED_SHA256.get("dspico_firmware_uf2")
    urls = pins.URLS.get("dspico_firmware_uf2")
    name = pins.FILENAMES.get("dspico_firmware_uf2")
    if not pin or not name:
        return False
    if isinstance(urls, str):
        return urls.startswith("https://github.com/LNH-team/")
    if isinstance(urls, (list, tuple)) and urls:
        return all(
            isinstance(u, str) and u.startswith("https://github.com/LNH-team/")
            for u in urls
        )
    return False


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


def _read_sidecar_record(target_path: str) -> Optional[tuple[str, Optional[int], Optional[int]]]:
    """Lê sidecar: (digest, size|None, mtime_ns|None). Formato antigo = só digest."""
    side = _sidecar_path(target_path)
    if not os.path.isfile(side):
        return None
    try:
        with open(side, "r", encoding="utf-8") as f:
            parts = f.read().strip().split()
        if not parts:
            return None
        digest = parts[0].lower()
        size: Optional[int] = None
        mtime_ns: Optional[int] = None
        if len(parts) >= 3:
            try:
                size = int(parts[1])
                mtime_ns = int(parts[2])
            except (TypeError, ValueError):
                size = None
                mtime_ns = None
        return digest, size, mtime_ns
    except OSError:
        return None


def _read_sidecar(target_path: str) -> Optional[str]:
    """Compat: só o digest do sidecar, ou None."""
    rec = _read_sidecar_record(target_path)
    return rec[0] if rec else None


def _write_sidecar(target_path: str, digest: str) -> None:
    """Grava digest + size + mtime_ns (fast-path na próxima validação)."""
    try:
        st = os.stat(target_path)
        payload = f"{digest} {st.st_size} {st.st_mtime_ns}\n"
    except OSError:
        payload = f"{digest}\n"
    with open(_sidecar_path(target_path), "w", encoding="utf-8") as f:
        f.write(payload)


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
    try:
        st = os.stat(path)
    except OSError:
        return False
    size = st.st_size
    pins = _pins()
    min_size = pins.MIN_SIZES.get(key, 1)
    # Para pits, exigir tamanho exato
    if key in ("pit_facebook", "pit_no_facebook") and size != min_size:
        return False
    if size < min_size:
        return False
    if _looks_like_html(path):
        return False

    pinned = pins.PINNED_SHA256.get(key)
    if not pinned:
        # Todos os artefatos oficiais devem ter pin; recusar aceitar sem pin.
        return False
    pinned_l = pinned.lower()

    # Fast-path: sidecar completo com digest==pin e size/mtime intactos.
    rec = _read_sidecar_record(path)
    if (
        rec
        and rec[1] is not None
        and rec[2] is not None
        and rec[0] == pinned_l
        and rec[1] == size
        and rec[2] == st.st_mtime_ns
    ):
        return True

    digest = _sha256_file(path)
    if digest != pinned_l:
        return False

    # Sidecar antigo/stale: reescrever; se digest diverge do ficheiro, inválido.
    if rec and rec[0] != digest:
        return False
    _write_sidecar(path, digest)
    return True


_DOWNLOAD_CHUNK = 1024 * 1024  # 1 MiB — progresso sem abrandar I/O


def download_url(url: str, target_path: str, log_callback=None) -> None:
    """Baixa URL HTTPS para target_path com User-Agent consistente."""
    if not url.startswith("https://"):
        raise ValueError(f"Apenas HTTPS é permitido: {url}")
    emit_log(log_callback, f"Baixando de {url}...")
    headers = {"User-Agent": USER_AGENT}
    req = urllib.request.Request(url, headers=headers)
    tmp_path = f"{target_path}.partial"
    from core.progress import ProgressTracker

    tracker = ProgressTracker("cache_download", label="A descarregar…")
    try:
        # URLs vêm exclusivamente de URLS (constantes); não há input do usuário.
        with urllib.request.urlopen(req, timeout=120) as resp, open(tmp_path, "wb") as out:  # nosec B310  # nosemgrep: dynamic-urllib-use-detected
            total_hdr = resp.headers.get("Content-Length")
            if total_hdr:
                try:
                    tracker.set_totals(bytes=max(0, int(total_hdr)))
                except (TypeError, ValueError):
                    pass
            tracker.tick(force=True)
            while True:
                chunk = resp.read(_DOWNLOAD_CHUNK)
                if not chunk:
                    break
                out.write(chunk)
                tracker.add_bytes(len(chunk))
                tracker.tick()
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp_path, target_path)
        tracker.finish("Descarregamento concluído")
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
    pins = _pins()
    filename = pins.FILENAMES.get(key)
    if not filename:
        raise ValueError(f"Arquivo de cache desconhecido para a chave: {key}")
    target_path = os.path.join(CACHE_DIR, filename)

    pinned = pins.PINNED_SHA256.get(key)
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

    urls = urls_for(key)
    if not urls:
        raise ValueError(f"URL desconhecida para a chave: {key}")

    emit_log(
        log_callback,
        f"Baixando componente {key} ({len(urls)} fonte(s) disponível(is))...",
    )
    last_error: Optional[Exception] = None
    for idx, url in enumerate(urls):
        if len(urls) > 1:
            emit_log(log_callback, f"Tentativa {idx + 1}/{len(urls)}…")
        try:
            download_url(url, target_path, log_callback)
        except Exception as e:
            last_error = e
            emit_log(log_callback, f"Falha na fonte {idx + 1}: {e}")
            continue

        if not os.path.isfile(target_path) or os.path.getsize(target_path) < pins.MIN_SIZES.get(
            key, 1
        ):
            last_error = RuntimeError(
                f"Download de {key} falhou: arquivo vazio ou muito pequeno."
            )
            try:
                os.remove(target_path)
            except OSError:
                pass
            continue
        if _looks_like_html(target_path):
            try:
                os.remove(target_path)
            except OSError:
                pass
            last_error = RuntimeError(
                f"Download de {key} retornou HTML (possível erro 404/rate-limit)."
            )
            continue

        digest = _sha256_file(target_path)
        if digest != pinned.lower():
            try:
                os.remove(target_path)
            except OSError:
                pass
            last_error = RuntimeError(
                f"Integridade de {key} falhou (SHA-256 diferente do esperado)."
            )
            emit_log(log_callback, str(last_error))
            continue

        _write_sidecar(target_path, digest)
        emit_log(
            log_callback,
            f"✅ {key} baixado com sucesso ({os.path.getsize(target_path)} bytes).",
        )
        return target_path

    if last_error is not None:
        raise RuntimeError(
            f"Todas as fontes de download de {key} falharam. "
            "O arquivo upstream pode ter mudado — rode tools/update_pins.py."
        ) from last_error
    raise RuntimeError(f"Download de {key} falhou sem fontes válidas.")
