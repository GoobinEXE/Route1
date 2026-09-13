"""Utilitários extras do cartão: GodMode9i, cheats, cópia NAND."""

from __future__ import annotations

import os
import shutil
import zipfile
from datetime import datetime
from typing import Optional

from core.cache import PINNED_SHA256, ensure_cached
from core.disks import TARGET_CLUSTER_BYTES, get_cluster_size_bytes, is_safe_mount_path
from core.inspect_sd import _find_nand_dumps, inspect_sd_card
from core.logging_util import emit_log
from core.privacy import redact_path
from core.sdio import copy_verified, sync_volume

_USRCHEAT_MIN = 1024 * 100  # DB real é dezenas de MB; mínimo defensivo
_ALLOWED_CHEAT_NAMES = frozenset({"usrcheat.dat"})


def _safe_under(root: str, path: str) -> bool:
    try:
        root_r = os.path.realpath(root)
        path_r = os.path.realpath(path)
        return os.path.commonpath([root_r, path_r]) == root_r
    except (ValueError, OSError):
        return False


def install_homebrew(
    mount_path: str, app_id: str, log_callback=None
) -> tuple[bool, str]:
    """Instala um app do catálogo com receita GameBrew/README (cache pinado)."""
    from core.homebrew_catalog import get_app
    from core.homebrew_install import apply_install_recipe

    log = lambda msg: emit_log(log_callback, msg)
    if not is_safe_mount_path(mount_path):
        return False, "Unidade não reconhecida como volume removível/USB/SD."
    if not isinstance(app_id, str) or not app_id.strip():
        return False, "Aplicação inválida."

    app = get_app(app_id.strip())
    if not app:
        return False, "Aplicação não encontrada no catálogo."
    if not app.get("installable"):
        return False, f"{app['title']} não tem download pinado neste app."

    key = app["install_key"]
    if not PINNED_SHA256.get(key):
        return False, f"Sem pin SHA-256 para {app['title']}."

    log(f"=== Instalar {app['title']} (guia GameBrew) ===")
    try:
        src = ensure_cached(key, log_callback=log_callback)
    except Exception as e:
        return False, f"Falha ao obter {app['title']}: {e}"

    ok, msg, notes = apply_install_recipe(
        mount_path, app, src, log_callback=log_callback
    )
    if not ok:
        return False, msg

    try:
        sync_volume(mount_path)
    except Exception as e:
        return False, f"{msg} (sync falhou: {e})"

    for note in notes:
        log(f"ℹ️ {note}")
    log(f"✅ {msg}")
    if notes:
        extra = " ".join(notes[:2])
        return True, f"{msg}. {extra}"
    return True, msg


def setup_godmode9i(mount_path: str, log_callback=None) -> tuple[bool, str]:
    """Compat: instala GodMode9i via catálogo."""
    return install_homebrew(mount_path, "godmode9i", log_callback=log_callback)


def _find_usrcheat_candidates() -> list[str]:
    """Procura usrcheat.dat (ou zip) em Desktop/Downloads."""
    home = os.path.expanduser("~")
    roots = [
        os.path.join(home, "Downloads"),
        os.path.join(home, "Desktop"),
        os.path.join(home, "Transferências"),  # macOS PT
        os.path.join(home, "Ambiente de Trabalho"),
    ]
    found: list[str] = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        try:
            for name in os.listdir(root):
                low = name.lower()
                path = os.path.join(root, name)
                if not _safe_under(root, path):
                    continue
                if low == "usrcheat.dat" and os.path.isfile(path):
                    found.append(path)
                elif low.endswith((".zip", ".7z")) and "cheat" in low and os.path.isfile(path):
                    found.append(path)
        except OSError:
            continue
    return found


def _extract_usrcheat_from_zip(zip_path: str, dest_dir: str) -> Optional[str]:
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for info in zf.infolist():
                base = os.path.basename(info.filename).lower()
                if base != "usrcheat.dat" or info.is_dir():
                    continue
                # Evitar path traversal no zip
                if ".." in info.filename.replace("\\", "/").split("/"):
                    continue
                zf.extract(info, dest_dir)
                extracted = os.path.join(dest_dir, info.filename)
                # Normalizar para dest_dir/usrcheat.dat
                final = os.path.join(dest_dir, "usrcheat.dat")
                if os.path.abspath(extracted) != os.path.abspath(final):
                    os.makedirs(dest_dir, exist_ok=True)
                    if os.path.exists(final):
                        os.remove(final)
                    shutil.move(extracted, final)
                return final
    except (OSError, zipfile.BadZipFile):
        return None
    return None


def install_cheats(mount_path: str, log_callback=None) -> tuple[bool, str]:
    """
    Instala usrcheat.dat em /_nds/TWiLightMenu/extras/.
    Fonte: ficheiro em Downloads/Desktop (sem URL estável pinável).
    """
    log = lambda msg: emit_log(log_callback, msg)
    if not is_safe_mount_path(mount_path):
        return False, "Unidade não reconhecida como volume removível/USB/SD."

    log("=== Instalar cheats (usrcheat.dat) ===")
    candidates = _find_usrcheat_candidates()
    if not candidates:
        return (
            False,
            "Coloque usrcheat.dat (DeadSkullzJr) em Downloads ou Desktop e tente de novo. "
            "Ver FAQ TWiLight Menu++ / GBAtemp thread 488711.",
        )

    src = candidates[0]
    log(f"Fonte: {redact_path(src)}")

    import tempfile

    tmp_dir = None
    try:
        if src.lower().endswith(".zip"):
            tmp_dir = tempfile.mkdtemp(prefix="route1_cheats_")
            extracted = _extract_usrcheat_from_zip(src, tmp_dir)
            if not extracted or not os.path.isfile(extracted):
                return False, "Zip sem usrcheat.dat válido."
            src = extracted
        elif src.lower().endswith(".7z"):
            return (
                False,
                "Arquivos .7z não são suportados aqui — extraia usrcheat.dat "
                "para Downloads e tente de novo.",
            )

        if os.path.basename(src).lower() not in _ALLOWED_CHEAT_NAMES:
            return False, "Ficheiro de cheats inválido (nome esperado: usrcheat.dat)."
        if os.path.getsize(src) < _USRCHEAT_MIN:
            return False, "usrcheat.dat demasiado pequeno — ficheiro incompleto?"

        extras = os.path.join(mount_path, "_nds", "TWiLightMenu", "extras")
        os.makedirs(extras, exist_ok=True)
        dst = os.path.join(extras, "usrcheat.dat")
        copy_verified(src, dst, log_callback=log_callback)
        sync_volume(mount_path)
        log("✅ Cheats instalados em /_nds/TWiLightMenu/extras/usrcheat.dat")
        return True, "Cheats instalados em /_nds/TWiLightMenu/extras/usrcheat.dat"
    except Exception as e:
        return False, f"Falha ao instalar cheats: {e}"
    finally:
        if tmp_dir and os.path.isdir(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)


def copy_nand_backup(mount_path: str, log_callback=None) -> tuple[bool, str]:
    """Copia DT*/nand.bin (+sha1) para o Desktop. Não apaga do cartão."""
    log = lambda msg: emit_log(log_callback, msg)
    if not is_safe_mount_path(mount_path):
        return False, "Unidade não reconhecida como volume removível/USB/SD."

    dumps = [d for d in _find_nand_dumps(mount_path) if d.get("plausible")]
    if not dumps:
        return False, "Nenhum dump NAND plausível (DT*/nand.bin ≥100 MiB) encontrado."

    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    if not os.path.isdir(desktop):
        # macOS PT
        alt = os.path.join(os.path.expanduser("~"), "Ambiente de Trabalho")
        desktop = alt if os.path.isdir(alt) else os.path.expanduser("~")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    copied = 0
    dests = []
    try:
        for d in dumps:
            folder = d["folder"]
            src = os.path.join(mount_path, folder, "nand.bin")
            if not os.path.isfile(src):
                continue
            out_dir = os.path.join(desktop, f"NAND_{folder}_{stamp}")
            os.makedirs(out_dir, exist_ok=True)
            dst = os.path.join(out_dir, "nand.bin")
            log(f"A copiar {folder}/nand.bin ({d.get('size_mb')} MiB)…")
            shutil.copy2(src, dst)
            sha_src = os.path.join(mount_path, folder, "nand.bin.sha1")
            if os.path.isfile(sha_src):
                shutil.copy2(sha_src, os.path.join(out_dir, "nand.bin.sha1"))
            copied += 1
            dests.append(redact_path(out_dir))
            log(f"✅ Copiado para {redact_path(out_dir)}")
    except OSError as e:
        return False, f"Falha ao copiar NAND: {e}"

    if copied == 0:
        return False, "Não foi possível copiar nenhum dump NAND."
    return True, f"{copied} dump(s) NAND copiado(s): {', '.join(dests)}"


def format_sd_report(mount_path: str, log_callback=None) -> tuple[bool, str]:
    """Gera relatório legível no log a partir de inspect_sd + cluster."""
    log = lambda msg: emit_log(log_callback, msg)
    info = inspect_sd_card(mount_path)
    if not info.get("success"):
        return False, info.get("error") or "Falha ao inspecionar o cartão."

    cluster = get_cluster_size_bytes(mount_path)
    cluster_ok = cluster == TARGET_CLUSTER_BYTES if cluster else None

    log("=== Relatório do cartão ===")
    log(f"Nome: {info.get('name')}")
    log(f"FS: {info.get('fs_type')} (FAT32: {'sim' if info.get('is_fat32') else 'não'})")
    if cluster:
        kb = cluster // 1024
        status = "OK" if cluster_ok else "AVISO — recomendado 32 KB (dsi.cfw.guide)"
        log(f"Cluster: {kb} KB ({cluster} bytes) — {status}")
        info["cluster_bytes"] = cluster
        info["cluster_ok"] = bool(cluster_ok)
    else:
        log("Cluster: não foi possível ler neste sistema.")
        info["cluster_bytes"] = None
        info["cluster_ok"] = None

    log(f"Capacidade: {info.get('total_size_gb')} GB · Livre: {info.get('free_size_gb')} GB")
    log(f"TWiLight: {'sim' if info.get('has_twilight') else 'não'}")
    log(f"boot.nds: {'sim' if info.get('has_boot_nds') else 'não'}")
    log(f"dumpTool: {'sim' if info.get('has_dumptool') else 'não'}")
    log(f"Unlaunch installer: {'sim' if info.get('has_unlaunch_installer') else 'não'}")
    log(f"DCIM na raiz: {'sim' if info.get('has_dcim') else 'não'}")
    nands = info.get("nand_dumps") or []
    if nands:
        for n in nands:
            flag = "OK" if n.get("plausible") else "pequeno?"
            log(f"NAND: {n.get('rel_path')} ({n.get('size_mb')} MiB) [{flag}]")
    else:
        log("NAND: nenhum DT*/nand.bin encontrado")
    log(f"ROMs sob /roms/: {info.get('roms_count', 0)}")
    if not info.get("is_fat32"):
        log("⚠️ Cartão não está em FAT32 — formate com cluster 32 KB.")
    elif cluster_ok is False:
        log("⚠️ Cluster ≠ 32 KB — Unlaunch pode mostrar 'Clusters too large'.")
    log("=== Fim do relatório ===")

    bits = [
        f"FS={info.get('fs_type')}",
        f"cluster={cluster // 1024 if cluster else '?'}KB",
        f"TWiLight={'sim' if info.get('has_twilight') else 'não'}",
        f"NAND={'sim' if info.get('has_nand_dump') else 'não'}",
        f"ROMs={info.get('roms_count', 0)}",
    ]
    return True, "Relatório: " + " · ".join(bits)
