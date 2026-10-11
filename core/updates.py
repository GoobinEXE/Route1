"""Verificação e instalação de updates do ecossistema DSPico (LNH-team)."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
import urllib.parse
import urllib.request
import zipfile
from typing import Any, Callable, Optional

from core.cache import (
    CACHE_DIR,
    DSPICO_EMU_CACHE_KEYS,
    PINNED_SHA256,
    PIN_META,
    ensure_cache_dir,
    ensure_cached,
)
from core.disks import is_safe_mount_path
from core.dspico import (
    _extract_zip_safe,
    _find_file,
    _find_dir,
    flash_dspico_firmware,
    is_rp2_volume,
)
from core.logging_util import emit_log
from core.privacy import redact_text
from core.sdio import UndoStack, sync_volume
from core.twilight import _is_safe_archive_member, _stage_dir_copy, _stage_file_copy

LogFn = Callable[[str], None]

_ALLOWLIST_HOSTS = {"api.github.com", "github.com"}
_USER_AGENT = "Route1Kit"
_TIMEOUT = 15
_CACHE_TTL_SECONDS = 600
_MEM_CACHE: dict[str, tuple[float, bytes]] = {}

_COMPONENTS: dict[str, dict[str, Any]] = {
    "pico-launcher": {
        "repo": "LNH-team/pico-launcher",
        "cache_key": "pico_launcher",
        "asset_suffixes": ("Pico_Launcher.zip",),
    },
    "pico-loader": {
        "repo": "LNH-team/pico-loader",
        "cache_key": "pico_loader_dspico",
        "asset_suffixes": ("Pico_Loader_DSPICO.zip",),
    },
    "dspico-firmware": {
        "repo": "LNH-team/dspico-firmware",
        "cache_key": "dspico_firmware_uf2",
        "asset_suffixes": (".uf2",),
    },
    "dspico-usb-examples": {
        "repo": "LNH-team/dspico-usb-examples",
        "cache_key": None,
        "asset_suffixes": ("mass-storage.nds", ".zip"),
    },
}

_KNOWN_DIGESTS: dict[str, list[dict[str, str]]] = {
    "pico-launcher": [
        {
            "version": "v1.3.0",
            "kind": "asset",
            "sha256": "b4ed7f2cf2713e0c74985764536a0bfb7381566c67b0f85dc8b83375bcfc495d",
        }
    ],
    "dspico-usb-examples": [
        {
            "version": "v1.2.0",
            "kind": "installed_file",
            "path": "Games/mass-storage.nds",
            "sha256": "7bd09bd03d2e4e37634421984b22fc319936adb2e44a69b0a7fcd2e246cdeb6f",
        }
    ],
}


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_allowed_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return False
    if parsed.scheme != "https" or parsed.hostname not in _ALLOWLIST_HOSTS:
        return False
    host = parsed.hostname or ""
    if host == "api.github.com":
        return parsed.path.startswith("/repos/LNH-team/")
    if host == "github.com":
        return parsed.path.startswith("/LNH-team/")
    return False


def _cached_http_get(url: str, *, timeout: int = _TIMEOUT) -> bytes:
    if not _is_allowed_url(url):
        raise RuntimeError(f"URL não permitida: {url}")
    now = time.time()
    cached = _MEM_CACHE.get(url)
    if cached and cached[0] > now:
        return cached[1]

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
        data = resp.read()
    _MEM_CACHE[url] = (now + _CACHE_TTL_SECONDS, data)
    return data


def _github_latest_release(repo: str) -> dict[str, Any]:
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    raw = _cached_http_get(url, timeout=_TIMEOUT)
    obj = json.loads(raw.decode("utf-8", errors="replace"))
    if not isinstance(obj, dict):
        raise RuntimeError("Resposta inválida da API do GitHub.")
    return obj


def _extract_digest(digest_field: Any) -> Optional[str]:
    if not isinstance(digest_field, str):
        return None
    text = digest_field.strip().lower()
    if text.startswith("sha256:"):
        text = text.split(":", 1)[1].strip()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        return None
    return text


def _component_meta(component: str) -> dict[str, Any]:
    meta = _COMPONENTS.get((component or "").strip().lower())
    if not meta:
        raise ValueError("Componente desconhecido.")
    return meta


def _pinned_version(component: str) -> str:
    meta = _component_meta(component)
    cache_key = meta.get("cache_key")
    if isinstance(cache_key, str):
        pin = PIN_META.get(cache_key) or {}
        if isinstance(pin.get("tag"), str) and pin["tag"].strip():
            return pin["tag"].strip()
    for item in _KNOWN_DIGESTS.get(component, []):
        if isinstance(item.get("version"), str):
            return item["version"]
    return "unknown"


def _component_asset_from_release(component: str, release: dict[str, Any]) -> Optional[dict[str, Any]]:
    wanted = _component_meta(component).get("asset_suffixes") or ()
    assets = release.get("assets")
    if not isinstance(assets, list):
        return None
    lower_suffixes = tuple(str(s).lower() for s in wanted)
    for item in assets:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        if not name:
            continue
        low = name.lower()
        if any(low.endswith(suf) for suf in lower_suffixes):
            return item
    return None


def _detect_installed_version(mount_path: str, component: str) -> str:
    for known in _KNOWN_DIGESTS.get(component, []):
        if known.get("kind") != "installed_file":
            continue
        rel = known.get("path")
        digest = known.get("sha256")
        if not isinstance(rel, str) or not isinstance(digest, str):
            continue
        target = os.path.join(mount_path, rel.replace("/", os.sep))
        if not os.path.isfile(target):
            continue
        try:
            current = _sha256_file(target)
        except OSError:
            continue
        if current.lower() == digest.lower():
            return str(known.get("version") or "unknown")
    return "unknown"


def _download_asset_verified(asset: dict[str, Any], log: LogFn) -> str:
    url = str(asset.get("browser_download_url") or "")
    if not _is_allowed_url(url):
        raise RuntimeError("Asset fora da allowlist LNH-team.")
    digest = _extract_digest(asset.get("digest"))
    if not digest:
        raise RuntimeError("Asset latest sem digest SHA-256 na API do GitHub.")
    name = str(asset.get("name") or "asset.bin")

    ensure_cache_dir()
    out_dir = os.path.join(CACHE_DIR, "updates_latest")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, name)
    tmp_path = out_path + ".partial"
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    log(f"Baixando asset latest: {name}")
    # Teto defensivo: evita stream infinito / ficheiro anormal a encher o disco.
    max_bytes = 80 * 1024 * 1024
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp, open(tmp_path, "wb") as f:  # nosec B310
            headers = getattr(resp, "headers", None)
            cl = headers.get("Content-Length") if headers is not None else None
            if cl is not None:
                try:
                    if int(cl) > max_bytes:
                        raise RuntimeError("Asset latest excede o tamanho máximo permitido.")
                except ValueError:
                    pass
            written = 0
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise RuntimeError("Asset latest excede o tamanho máximo permitido.")
                f.write(chunk)
            f.flush()
            os.fsync(f.fileno())
        actual = _sha256_file(tmp_path)
        if actual.lower() != digest:
            raise RuntimeError("Digest do asset latest não confere com a API.")
        os.replace(tmp_path, out_path)
        return out_path
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise


def _validate_mount_for_sd_writes(mount_path: str) -> None:
    if not isinstance(mount_path, str) or not mount_path.strip():
        raise RuntimeError("Caminho do cartão inválido.")
    if not is_safe_mount_path(mount_path):
        raise RuntimeError("Unidade não reconhecida como volume removível/USB/SD.")


def _install_launcher_from_zip(mount_path: str, zip_path: str, log: LogFn) -> dict[str, Any]:
    _validate_mount_for_sd_writes(mount_path)
    extracted = _extract_zip_safe(
        zip_path,
        os.path.join(CACHE_DIR, "Update_Pico_Launcher"),
        log,
    )
    launcher_nds = _find_file(extracted, ("LAUNCHER.nds", "_picoboot.nds"))
    pico_src = _find_dir(extracted, "_pico")
    if not launcher_nds or not pico_src:
        raise RuntimeError("Pacote do Pico Launcher incompleto.")

    undo = UndoStack()
    baks: list[Optional[str]] = []
    try:
        bak = _stage_file_copy(
            undo,
            launcher_nds,
            os.path.join(mount_path, "_picoboot.nds"),
            log,
        )
        baks.append(bak)
        _stage_dir_copy(undo, pico_src, os.path.join(mount_path, "_pico"), log)
        sync_volume(mount_path)
        for b in baks:
            if b and os.path.isfile(b):
                try:
                    os.remove(b)
                except OSError:
                    pass
        return {"success": True, "message": "Pico Launcher atualizado no cartão."}
    except Exception:
        undo.rollback(log, mount_path=mount_path)
        raise


def _install_loader_from_zip(mount_path: str, zip_path: str, log: LogFn) -> dict[str, Any]:
    _validate_mount_for_sd_writes(mount_path)
    extracted = _extract_zip_safe(
        zip_path,
        os.path.join(CACHE_DIR, "Update_Pico_Loader"),
        log,
    )
    loader7 = _find_file(extracted, ("picoLoader7.bin",))
    loader9 = _find_file(extracted, ("picoLoader9.bin", "picoLoader9_DSPICO.bin"))
    aplist = _find_file(extracted, ("aplist.bin",))
    savelist = _find_file(extracted, ("savelist.bin",))
    if not loader7 or not loader9 or not aplist or not savelist:
        raise RuntimeError("Pacote do Pico Loader incompleto.")

    dst_pico = os.path.join(mount_path, "_pico")
    os.makedirs(dst_pico, exist_ok=True)
    undo = UndoStack()
    baks: list[Optional[str]] = []
    try:
        for src, name in (
            (loader7, "picoLoader7.bin"),
            (loader9, "picoLoader9.bin"),
            (aplist, "aplist.bin"),
            (savelist, "savelist.bin"),
        ):
            bak = _stage_file_copy(undo, src, os.path.join(dst_pico, name), log)
            baks.append(bak)
        sync_volume(mount_path)
        for b in baks:
            if b and os.path.isfile(b):
                try:
                    os.remove(b)
                except OSError:
                    pass
        return {"success": True, "message": "Pico Loader atualizado no cartão."}
    except Exception:
        undo.rollback(log, mount_path=mount_path)
        raise


def _extract_zip_member_to_cache(zip_path: str, member_name: str) -> str:
    ensure_cache_dir()
    out_dir = os.path.join(CACHE_DIR, "updates_usb_examples")
    os.makedirs(out_dir, exist_ok=True)
    target = os.path.join(out_dir, member_name)
    with zipfile.ZipFile(zip_path, "r") as zf:
        found = None
        for info in zf.infolist():
            if not _is_safe_archive_member(info.filename, out_dir):
                raise RuntimeError(f"Zip rejeitado (caminho inseguro): {info.filename!r}")
            if os.path.basename(info.filename).lower() == member_name.lower():
                found = info
                break
        if not found:
            raise RuntimeError(f"{member_name} não encontrado no arquivo.")
        data = zf.read(found)
    tmp = target + ".partial"
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, target)
    return target


def _install_usb_examples_asset(mount_path: str, asset_path: str, log: LogFn) -> dict[str, Any]:
    _validate_mount_for_sd_writes(mount_path)
    src_path = asset_path
    if asset_path.lower().endswith(".zip"):
        src_path = _extract_zip_member_to_cache(asset_path, "mass-storage.nds")
    if os.path.basename(src_path).lower() != "mass-storage.nds":
        raise RuntimeError("Asset USB examples incompatível (esperado mass-storage.nds).")

    dst_dir = os.path.join(mount_path, "Games")
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, "mass-storage.nds")
    undo = UndoStack()
    bak = None
    try:
        bak = _stage_file_copy(undo, src_path, dst, log)
        sync_volume(mount_path)
        if bak and os.path.isfile(bak):
            try:
                os.remove(bak)
            except OSError:
                pass
        return {
            "success": True,
            "message": "USB examples instalado (Games/mass-storage.nds).",
        }
    except Exception:
        undo.rollback(log, mount_path=mount_path)
        raise


def _install_firmware(mount_path: str, channel: str, log: LogFn) -> dict[str, Any]:
    if channel == "pinned":
        if is_rp2_volume(mount_path):
            ok, msg = flash_dspico_firmware(mount_path, log)
            return {"success": bool(ok), "message": msg, "flashed": bool(ok)}
        return {
            "success": True,
            "message": (
                "Firmware não é gravado automaticamente no cartão SD. "
                "Use o volume RPI-RP2 (BOOTSEL) para flash."
            ),
            "flashed": False,
        }

    release = _github_latest_release(_component_meta("dspico-firmware")["repo"])
    asset = _component_asset_from_release("dspico-firmware", release)
    if not asset:
        raise RuntimeError("Release latest sem asset UF2 para firmware.")
    uf2_path = _download_asset_verified(asset, log)
    if is_rp2_volume(mount_path):
        # Grava apenas quando o caller já apontou para RPI-RP2.
        ok, msg = _flash_uf2_path(mount_path, uf2_path)
        return {"success": bool(ok), "message": msg, "flashed": bool(ok), "path": uf2_path}
    return {
        "success": True,
        "message": (
            "Firmware latest descarregado; para gravar, monte o cartucho em modo "
            "BOOTSEL (RPI-RP2) e execute o flash."
        ),
        "flashed": False,
        "path": uf2_path,
        "releases_url": "https://github.com/LNH-team/dspico-firmware/releases",
    }


def _flash_uf2_path(rp2_mount_path: str, uf2_path: str) -> tuple[bool, str]:
    if not is_rp2_volume(rp2_mount_path):
        return False, "Volume não parece RPI-RP2 (BOOTSEL)."
    if not os.path.isfile(uf2_path):
        return False, "UF2 inexistente."
    dest = os.path.join(rp2_mount_path, os.path.basename(uf2_path))
    try:
        with open(uf2_path, "rb") as src, open(dest, "wb") as out:
            shutil.copyfileobj(src, out, length=1024 * 1024)
            out.flush()
            try:
                os.fsync(out.fileno())
            except OSError:
                pass
        return True, "Firmware UF2 enviado ao volume RPI-RP2."
    except OSError as e:
        msg = str(e).lower()
        if "no such" in msg or "eject" in msg or "input/output" in msg:
            return True, "Firmware enviado (volume RPI-RP2 ejectou)."
        return False, f"Falha ao gravar UF2: {e}"


def check_dspico_updates(mount_path: str, log_callback=None) -> dict[str, Any]:
    """Verifica versões instaladas/pinadas/latest dos componentes DSPico."""
    log = lambda msg: emit_log(log_callback, msg)
    components: dict[str, Any] = {}
    try:
        for name, meta in _COMPONENTS.items():
            pinned_version = _pinned_version(name)
            installed_version = _detect_installed_version(mount_path, name)
            latest_version = "unknown"
            latest_error = None
            try:
                release = _github_latest_release(meta["repo"])
                tag = release.get("tag_name")
                latest_version = str(tag).strip() if isinstance(tag, str) and tag.strip() else "unknown"
            except Exception as e:
                latest_error = redact_text(e)
                log(f"⚠️ {name}: falha ao consultar latest: {latest_error}")

            has_pin = bool(_component_meta(name).get("cache_key")) or name == "dspico-firmware"
            can_latest = (
                latest_version not in {"", "unknown", None}
                and (latest_error is None)
                and name != "dspico-firmware"
            )
            item = {
                "id": name,
                "label": name,
                "installed_version": installed_version,
                "pinned_version": pinned_version,
                "latest_version": latest_version,
                "can_install_pinned": has_pin and name != "dspico-firmware",
                "can_install_latest": bool(can_latest),
                "release_url": f"https://github.com/{meta['repo']}/releases",
            }
            if latest_error:
                item["latest_error"] = latest_error
            components[name] = item

        emu_summary = {
            "total_keys": len(DSPICO_EMU_CACHE_KEYS),
            "pinned_keys": sum(1 for k in DSPICO_EMU_CACHE_KEYS if PINNED_SHA256.get(k)),
        }
        # Lista ordenada para a UI + mapa por id.
        ordered = [components[k] for k in _COMPONENTS.keys() if k in components]
        return {
            "success": True,
            "components": ordered,
            "components_by_id": components,
            "emulator_pins": emu_summary,
        }
    except Exception as e:
        return {"success": False, "error": redact_text(e), "components": components}


def install_dspico_component(
    mount_path: str,
    component: str,
    channel: str,
    log_callback=None,
) -> dict[str, Any]:
    """Instala/atualiza um componente DSPico via canal pinado ou latest."""
    log = lambda msg: emit_log(log_callback, msg)
    try:
        comp = (component or "").strip().lower()
        ch = (channel or "").strip().lower()
        if ch not in {"pinned", "latest"}:
            raise ValueError("Canal inválido (use pinned ou latest).")
        _component_meta(comp)

        if comp == "dspico-firmware":
            return _install_firmware(mount_path, ch, log)

        if ch == "pinned":
            cache_key = _component_meta(comp).get("cache_key")
            if not isinstance(cache_key, str):
                raise RuntimeError("Componente sem pacote pinado no cache.")
            pkg = ensure_cached(cache_key, log_callback=log_callback)
        else:
            release = _github_latest_release(_component_meta(comp)["repo"])
            asset = _component_asset_from_release(comp, release)
            if not asset:
                raise RuntimeError("Release latest sem asset compatível.")
            pkg = _download_asset_verified(asset, log)

        if comp == "pico-launcher":
            return _install_launcher_from_zip(mount_path, pkg, log)
        if comp == "pico-loader":
            return _install_loader_from_zip(mount_path, pkg, log)
        if comp == "dspico-usb-examples":
            return _install_usb_examples_asset(mount_path, pkg, log)
        raise RuntimeError("Componente não suportado.")
    except Exception as e:
        return {"success": False, "error": redact_text(e)}
