"""Instalação headless de hiyaCFW (SDNAND) com tools do TWLMagician pinado."""

from __future__ import annotations

import os
import platform
import shutil
import struct
import subprocess
import tempfile
from typing import Optional
from binascii import hexlify

from core.cache import CACHE_DIR, ensure_cached, ensure_cache_dir
from core.logging_util import emit_log
from core.privacy import expand_user_path, redact_path
from core.sdio import UndoStack, sync_volume
from core.twilight import (
    _cleanup_baks,
    _is_safe_archive_member,
    _safe_under,
    _stage_dir_copy,
    _stage_file_copy,
    install_twilight_menu,
)

_NAND_MIN_BYTES = 100 * 1024 * 1024
_NOCASH_MAGIC = b"DSi eMMC CID/CPU"
_REGION_CODES = {
    "484e4143": "CHN",
    "484e4145": "USA",
    "484e414a": "JPN",
    "484e414b": "KOR",
    "484e4150": "EUR",
    "484e4155": "AUS",
}
_LAUNCHER_PIN_KEYS = {
    "USA": "hiya_launcher_usa",
    "EUR": "hiya_launcher_eur",
    "JPN": "hiya_launcher_jpn",
    "AUS": "hiya_launcher_aus",
    "CHN": "hiya_launcher_chn",
    "KOR": "hiya_launcher_kor",
}
_TWL_TIMEOUT = 600
_EXTRACT_TIMEOUT = 600
# Offset da 1.ª partição FAT (TWLN) na NAND DSi — igual ao TWLMagician/fatcat
_TWLN_FAT_OFFSET = "1109504"


def hiya_markers_ok(mount_path: str) -> bool:
    """True se hiyaCFW parece instalado (hiya.dsi + pasta hiya)."""
    return os.path.isfile(os.path.join(mount_path, "hiya.dsi")) and os.path.isdir(
        os.path.join(mount_path, "hiya")
    )


def _run(cmd: list[str], *, cwd: str, timeout: int, log_callback=None) -> None:
    emit_log(log_callback, f"Exec: {os.path.basename(cmd[0])} …")
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"Timeout ({timeout}s) em {os.path.basename(cmd[0])}") from e
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(
            f"{os.path.basename(cmd[0])} falhou (código {proc.returncode})"
            + (f": {err[:200]}" if err else "")
        )


def ensure_twlmagician_tools(log_callback=None) -> dict[str, str]:
    """
    Garante tools pinados do TWLMagician (twltool / 7za|7z / fatcat / ndsblc).

    O release macOS é só o GUI PyInstaller — as tools vêm de Darwin/ no
    repositório (pins SHA-256). A extracção da NAND usa fatcat (o 7za
    standalone no Darwin não abre .img de NAND como arquivo).
    """
    system = platform.system()
    if system == "Darwin":
        specs = {
            "twltool": "twlm_twltool_darwin",
            "za": "twlm_7za_darwin",
            "fatcat": "twlm_fatcat_darwin",
            "ndsblc": "twlm_ndsblc_darwin",
        }
    elif system == "Windows":
        specs = {
            "twltool": "twlm_twltool_win",
            "za": "twlm_7z_win",
            "fatcat": "twlm_fatcat_win",
            "ndsblc": None,
            "dll": "twlm_7z_dll_win",
        }
    else:
        specs = {
            "twltool": "twlm_twltool_linux",
            "za": "twlm_7za_linux",
            "fatcat": "twlm_fatcat_linux",
            "ndsblc": "twlm_ndsblc_linux",
        }

    emit_log(log_callback, "A preparar tools TWLMagician (pinados)…")
    twltool = ensure_cached(specs["twltool"], log_callback)
    za = ensure_cached(specs["za"], log_callback)
    fatcat = ensure_cached(specs["fatcat"], log_callback)

    # Windows: 7z.dll tem de estar ao lado de 7z.exe
    if specs.get("dll"):
        dll_src = ensure_cached(specs["dll"], log_callback)
        dll_dst = os.path.join(os.path.dirname(za), "7z.dll")
        if os.path.realpath(dll_src) != os.path.realpath(dll_dst):
            try:
                shutil.copy2(dll_src, dll_dst)
            except OSError as e:
                raise RuntimeError(f"Não foi possível colocar 7z.dll junto de 7z.exe: {e}") from e

    ndsblc = ""
    if specs.get("ndsblc"):
        ndsblc = ensure_cached(specs["ndsblc"], log_callback)

    missing = []
    if not os.path.isfile(twltool):
        missing.append("twltool")
    if not os.path.isfile(za):
        missing.append("7za")
    if not os.path.isfile(fatcat):
        missing.append("fatcat")
    if missing:
        raise RuntimeError(
            "Tools TWLMagician incompletos após download: " + ", ".join(missing)
        )

    if platform.system() != "Windows":
        for p in (twltool, za, fatcat, ndsblc):
            if p and os.path.isfile(p):
                try:
                    os.chmod(p, 0o755)
                except OSError:
                    pass

    tool_dir = os.path.dirname(twltool)
    return {
        "root": tool_dir,
        "twltool": twltool,
        "za": za,
        "fatcat": fatcat,
        "ndsblc": ndsblc,
        "tool_dir": tool_dir,
    }


def _extract_hiyacfw_7z(archive: str, dest: str, log_callback=None) -> str:
    try:
        import py7zr
    except ImportError as e:
        raise RuntimeError("py7zr não instalado.") from e

    emit_log(log_callback, "Extraindo hiyaCFW.7z…")
    with tempfile.TemporaryDirectory(dir=CACHE_DIR, prefix="hiya_7z_") as tmp:
        with py7zr.SevenZipFile(archive, mode="r") as z:
            for name in z.getnames():
                if not _is_safe_archive_member(name, tmp):
                    raise RuntimeError(f"7z rejeitado: {name!r}")
            z.extractall(path=tmp)

        staging = dest + f".staging_{os.getpid()}"
        if os.path.isdir(staging):
            shutil.rmtree(staging, ignore_errors=True)
        shutil.copytree(tmp, staging)
        if os.path.isdir(dest):
            shutil.rmtree(dest, ignore_errors=True)
        os.rename(staging, dest)

    sdnand = os.path.join(dest, "for SDNAND SD card")
    if not os.path.isdir(sdnand):
        # pode estar um nível abaixo
        for name in os.listdir(dest):
            cand = os.path.join(dest, name, "for SDNAND SD card")
            if os.path.isdir(cand):
                return os.path.dirname(cand)
        raise RuntimeError("Pacote hiyaCFW sem pasta 'for SDNAND SD card'.")
    return dest


def read_nocash_footer(nand_path: str) -> tuple[str, str]:
    """
    Lê CID e Console ID do footer No$GBA.
    Devolve (cid_hex_upper, console_id_hex_upper).
    """
    size = os.path.getsize(nand_path)
    if size < _NAND_MIN_BYTES:
        raise RuntimeError(
            f"nand.bin demasiado pequeno ({size // (1024 * 1024)} MiB). "
            "É necessário um dump completo do dumpTool."
        )
    with open(nand_path, "rb") as f:
        f.seek(-64, 2)
        magic = f.read(0x10)
        if magic != _NOCASH_MAGIC:
            raise RuntimeError(
                "Footer No$GBA em falta no nand.bin. "
                "Use o dump do dumpTool (com footer) — não um dump raw sem footer."
            )
        cid = hexlify(f.read(0x10)).upper().decode("ascii")
        console_raw = f.read(8)
        console_id = hexlify(bytearray(reversed(console_raw))).upper().decode("ascii")
    return cid, console_id


def resolve_nand_path(mount_path: str, nand_path: str = "") -> str:
    """
    Resolve path do nand.bin: argumento tipado, dump no cartão, ou allowlist
    Desktop/Downloads/cache.
    """
    if nand_path:
        cleaned = expand_user_path(nand_path) if nand_path.startswith("~") else nand_path
        cleaned = cleaned.strip()
        if not cleaned:
            raise RuntimeError("Caminho do nand.bin vazio.")
        # relativo ao mount?
        if not os.path.isabs(cleaned):
            cand = os.path.join(mount_path, cleaned.replace("\\", "/"))
            if os.path.isfile(cand):
                return os.path.realpath(cand)
        real = os.path.realpath(cleaned)
        if not os.path.isfile(real):
            raise RuntimeError(f"nand.bin não encontrado: {redact_path(cleaned)}")
        # allowlist: sob o mount, Desktop, Downloads ou cache
        allowed_roots = [
            mount_path,
            os.path.expanduser("~/Desktop"),
            os.path.expanduser("~/Downloads"),
            CACHE_DIR,
        ]
        if not any(_safe_under(root, real) for root in allowed_roots):
            raise RuntimeError(
                "nand.bin fora da allowlist (cartão, Desktop, Downloads ou cache)."
            )
        return real

    dumps = _find_nand_dumps(mount_path)
    plausible = [d for d in dumps if d.get("plausible")]
    if not plausible:
        raise RuntimeError(
            "Nenhum DT*/nand.bin válido no cartão. "
            "Faça o dump com dumpTool ou indique o caminho do nand.bin."
        )
    rel = plausible[0]["rel_path"]
    return os.path.realpath(os.path.join(mount_path, rel))


def _find_nand_dumps(mount_path: str) -> list:
    """Delega a inspect_sd (import local evita ciclo hiya↔inspect_sd)."""
    from core.inspect_sd import _find_nand_dumps as _find

    return _find(mount_path)


def _apply_ips(patch_path: str, target_path: str) -> None:
    """Aplica patch IPS (formato usado pelo TWLMagician / hiyaCFW)."""
    patch_size = os.path.getsize(patch_path)
    with open(patch_path, "rb") as patchfile, open(target_path, "r+b") as target:
        if patchfile.read(5) != b"PATCH":
            raise RuntimeError(f"IPS inválido: {os.path.basename(patch_path)}")

        def unpack_int(bstr: bytes) -> int:
            (ret_val,) = struct.unpack_from(
                ">I", b"\x00" * (4 - len(bstr)) + bstr
            )
            return ret_val

        r = patchfile.read(3)
        while patchfile.tell() not in (patch_size, patch_size - 3):
            offset = unpack_int(r)
            r = patchfile.read(2)
            size = unpack_int(r)
            if size == 0:
                r = patchfile.read(2)
                rle_size = unpack_int(r)
                data = patchfile.read(1) * rle_size
            else:
                data = patchfile.read(size)
            target.seek(offset)
            target.write(data)
            r = patchfile.read(3)
        if patch_size - 3 == patchfile.tell():
            trim_size = unpack_int(patchfile.read(3))
            target.truncate(trim_size)


def _detect_region(sdnand_root: str) -> tuple[str, str]:
    """Devolve (app_id_hex, region_name) a partir de title/00030017."""
    base = os.path.join(sdnand_root, "title", "00030017")
    if not os.path.isdir(base):
        raise RuntimeError("SDNAND sem title/00030017 — extract incompleto.")
    for app in os.listdir(base):
        content = os.path.join(base, app, "content")
        if not os.path.isdir(content):
            continue
        for f in os.listdir(content):
            if f.lower().endswith(".app") and f.lower().startswith("0000000"):
                region = _REGION_CODES.get(app.lower())
                if not region:
                    raise RuntimeError(f"Launcher/região não suportada: {app}")
                return app, region
    raise RuntimeError("Não foi possível detectar a região do NAND.")


def _build_bootloader(
    work: str,
    hiya_root: str,
    tools: dict[str, str],
    nand_copy: str,
    log_callback=None,
) -> str:
    """Extrai BIOS, patcha e gera bootloader.nds. Devolve path do bootloader."""
    twltool = tools["twltool"]
    _run([twltool, "boot2", "--in", nand_copy], cwd=work, timeout=_TWL_TIMEOUT, log_callback=log_callback)

    for name in ("arm7.bin", "arm9.bin"):
        if not os.path.isfile(os.path.join(work, name)):
            raise RuntimeError(f"twltool boot2 não gerou {name}")

    pc = os.path.join(hiya_root, "for PC", "bootloader files")
    if not os.path.isdir(pc):
        # procurar
        for walk_root, dirs, _ in os.walk(hiya_root):
            if "bootloader files" in dirs:
                pc = os.path.join(walk_root, "bootloader files")
                break
    if not os.path.isdir(pc):
        raise RuntimeError("Pasta 'for PC/bootloader files' em falta no hiyaCFW.")

    _apply_ips(os.path.join(pc, "bootloader arm7 patch.ips"), os.path.join(work, "arm7.bin"))
    _apply_ips(os.path.join(pc, "bootloader arm9 patch.ips"), os.path.join(work, "arm9.bin"))

    prepend = os.path.join(pc, "bootloader arm9 append to start.bin")
    arm9 = os.path.join(work, "arm9.bin")
    with open(arm9, "rb") as f:
        data = f.read()
    with open(arm9, "wb") as f, open(prepend, "rb") as pre:
        f.write(pre.read())
        f.write(data)

    bootloader = os.path.join(work, "bootloader.nds")
    ndsblc = tools.get("ndsblc") or ""
    if ndsblc and os.path.isfile(ndsblc):
        exe = ndsblc
    else:
        # Windows: ndstool do pacote hiya
        exe = os.path.join(pc, "ndstool.exe")
        if not os.path.isfile(exe):
            raise RuntimeError("ndsblc/ndstool não encontrado para gerar bootloader.")

    _run(
        [
            exe,
            "-c",
            "bootloader.nds",
            "-9",
            "arm9.bin",
            "-7",
            "arm7.bin",
            "-t",
            os.path.join(pc, "banner.bin"),
            "-h",
            os.path.join(pc, "header.bin"),
        ],
        cwd=work,
        timeout=_TWL_TIMEOUT,
        log_callback=log_callback,
    )
    if not os.path.isfile(bootloader):
        raise RuntimeError("Falha ao gerar bootloader.nds")
    return bootloader


def _decrypt_and_extract_sdnand(
    work: str,
    tools: dict[str, str],
    nand_copy: str,
    console_id: str,
    log_callback=None,
) -> str:
    """
    nandcrypt + extracção da partição TWLN via fatcat (offset 1109504).

    No Darwin o 7za pinado não abre .img de NAND como arquivo; o TWLMagician
    oficial usa fatcat neste passo.
    """
    img = os.path.join(work, f"{console_id}.img")
    twltool = tools["twltool"]
    fatcat = tools.get("fatcat") or ""
    if not fatcat or not os.path.isfile(fatcat):
        raise RuntimeError("fatcat em falta — necessário para extrair a SDNAND.")

    _run(
        [twltool, "nandcrypt", "--in", nand_copy, "--out", img],
        cwd=work,
        timeout=_TWL_TIMEOUT,
        log_callback=log_callback,
    )
    if not os.path.isfile(img):
        raise RuntimeError("nandcrypt não gerou a imagem desencriptada.")
    try:
        img_size = os.path.getsize(img)
    except OSError:
        img_size = 0
    if img_size < _NAND_MIN_BYTES:
        raise RuntimeError(
            f"Imagem desencriptada demasiado pequena ({img_size} bytes)."
        )

    sdnand = os.path.join(work, "sdnand_out")
    os.makedirs(sdnand, exist_ok=True)
    emit_log(log_callback, "A extrair partição TWLN com fatcat…")
    # fatcat -O <offset> -x <outdir> <image>
    _run(
        [fatcat, "-O", _TWLN_FAT_OFFSET, "-x", sdnand, img],
        cwd=work,
        timeout=_EXTRACT_TIMEOUT,
        log_callback=log_callback,
    )
    # Sanidade mínima: sys/ ou title/ devem existir após extract
    if not (
        os.path.isdir(os.path.join(sdnand, "title"))
        or os.path.isdir(os.path.join(sdnand, "sys"))
    ):
        raise RuntimeError(
            "fatcat correu mas a SDNAND extraiu vazia/incompleta "
            "(sem title/ nem sys/). Verifique o nand.bin."
        )
    return sdnand


def _install_launcher_app(
    work: str,
    tools: dict[str, str],
    region: str,
    app_id: str,
    launcher_folder: str,
    log_callback=None,
) -> str:
    """Descarrega launcher pinado, extrai .app, copia para launcher_folder. Devolve nome do .app."""
    pin_key = _LAUNCHER_PIN_KEYS.get(region)
    if not pin_key:
        raise RuntimeError(f"Sem pin de launcher para região {region}.")
    launcher_arc = ensure_cached(pin_key, log_callback)
    # copiar para work com nome da região (7za espera esse nome)
    local_arc = os.path.join(work, region)
    shutil.copy2(launcher_arc, local_arc)

    if region in ("CHN", "KOR"):
        launcher_app = "00000000.app"
    else:
        launcher_app = "00000002.app"

    password = app_id.lower()
    za = tools["za"]
    _run(
        [za, "x", "-bso0", "-y", f"-p{password}", local_arc, launcher_app],
        cwd=work,
        timeout=120,
        log_callback=log_callback,
    )
    app_path = os.path.join(work, launcher_app)
    if not os.path.isfile(app_path):
        raise RuntimeError(f"Falha ao extrair {launcher_app} do launcher {region}.")

    os.makedirs(launcher_folder, exist_ok=True)
    # limpar apps antigos (exceto title.tmd se update)
    for name in os.listdir(launcher_folder):
        if name.lower() == "title.tmd":
            continue
        fp = os.path.join(launcher_folder, name)
        try:
            if os.path.isfile(fp):
                os.chmod(fp, 0o666)
                os.remove(fp)
        except OSError:
            pass
    shutil.copy2(app_path, os.path.join(launcher_folder, launcher_app))
    return launcher_app


def update_hiya_only(mount_path: str, log_callback=None) -> tuple[bool, str]:
    """Substitui só hiya.dsi a partir do 7z pinado (update leve)."""
    log = lambda msg: emit_log(log_callback, msg)
    if not hiya_markers_ok(mount_path):
        return False, "hiyaCFW não detectado no cartão — use a instalação completa."

    try:
        archive = ensure_cached("hiyacfw_7z", log_callback)
        hiya_root = _extract_hiyacfw_7z(
            archive, os.path.join(CACHE_DIR, "hiyaCFW_extract"), log_callback
        )
    except Exception as e:
        return False, f"Não foi possível obter hiyaCFW: {e}"

    src = os.path.join(hiya_root, "for SDNAND SD card", "hiya.dsi")
    if not os.path.isfile(src):
        # procurar
        found = None
        for walk_root, _d, files in os.walk(hiya_root):
            if "hiya.dsi" in files:
                found = os.path.join(walk_root, "hiya.dsi")
                break
        if not found:
            return False, "hiya.dsi em falta no pacote."
        src = found

    undo = UndoStack()
    baks: list[Optional[str]] = []
    try:
        bak = _stage_file_copy(
            undo, src, os.path.join(mount_path, "hiya.dsi"), log_callback
        )
        baks.append(bak)
        sync_volume(mount_path)
        _cleanup_baks(baks)
        log("✅ hiya.dsi atualizado.")
        return True, "hiyaCFW atualizado (hiya.dsi)."
    except Exception as e:
        undo.rollback(log_callback, mount_path=mount_path)
        return False, str(e)


def install_hiya_cfw(
    mount_path: str,
    nand_path: str = "",
    *,
    update_only: bool = False,
    log_callback=None,
) -> tuple[bool, str]:
    """
    Instala hiyaCFW + SDNAND no cartão a partir do nand.bin do utilizador.
    Nunca escreve na SysNAND da consola.
    """
    log = lambda msg: emit_log(log_callback, msg)

    if update_only and hiya_markers_ok(mount_path):
        return update_hiya_only(mount_path, log_callback)

    log("=== Instalando hiyaCFW (SDNAND) ===")
    log("O app não grava na NAND da consola — só no cartão SD.")

    try:
        nand = resolve_nand_path(mount_path, nand_path)
        cid, console_id = read_nocash_footer(nand)
        log(f"NAND OK (footer No$GBA). Console ID: {console_id[:4]}…")
        # cid não é logado na íntegra por privacidade — só prefixo curto
        _ = cid
    except Exception as e:
        return False, str(e)

    try:
        tools = ensure_twlmagician_tools(log_callback)
        archive = ensure_cached("hiyacfw_7z", log_callback)
        hiya_root = _extract_hiyacfw_7z(
            archive, os.path.join(CACHE_DIR, "hiyaCFW_extract"), log_callback
        )
    except Exception as e:
        return False, f"Falha a preparar tools/pacote: {e}"

    # Trabalho em staging — nunca decrypt in-place no nand do utilizador
    with tempfile.TemporaryDirectory(dir=CACHE_DIR, prefix="hiya_work_") as work:
        try:
            nand_copy = os.path.join(work, "nand.bin")
            log("A copiar nand.bin para staging…")
            shutil.copy2(nand, nand_copy)

            log("A gerar bootloader…")
            bootloader = _build_bootloader(
                work, hiya_root, tools, nand_copy, log_callback
            )

            log("A desencriptar NAND e extrair SDNAND (pode demorar)…")
            sdnand = _decrypt_and_extract_sdnand(
                work, tools, nand_copy, console_id, log_callback
            )

            app_id, region = _detect_region(sdnand)
            log(f"Região detectada: {region}")

            # Mesclar ficheiros hiyaCFW no sdnand staging
            sdnand_pkg = os.path.join(hiya_root, "for SDNAND SD card")
            if not os.path.isdir(sdnand_pkg):
                for walk_root, dirs, _ in os.walk(hiya_root):
                    if "for SDNAND SD card" in dirs:
                        sdnand_pkg = os.path.join(walk_root, "for SDNAND SD card")
                        break

            # Copiar hiya/ photo/ hiya.dsi para sdnand staging
            for name in ("hiya", "photo"):
                src = os.path.join(sdnand_pkg, name)
                if os.path.isdir(src):
                    dst = os.path.join(sdnand, name)
                    if os.path.isdir(dst):
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
            hiya_dsi = os.path.join(sdnand_pkg, "hiya.dsi")
            if os.path.isfile(hiya_dsi):
                shutil.copy2(hiya_dsi, os.path.join(sdnand, "hiya.dsi"))

            # bootloader
            hiya_dir = os.path.join(sdnand, "hiya")
            os.makedirs(hiya_dir, exist_ok=True)
            shutil.copy2(bootloader, os.path.join(hiya_dir, "bootloader.nds"))

            launcher_folder = os.path.join(
                sdnand, "title", "00030017", app_id, "content"
            )
            launcher_app = _install_launcher_app(
                work, tools, region, app_id, launcher_folder, log_callback
            )

            # title.tmd do pacote
            tmd_src = os.path.join(
                sdnand_pkg, "title", "00030017", app_id, "content", "title.tmd"
            )
            if not os.path.isfile(tmd_src):
                # fallback: qualquer title.tmd da região no pacote
                for walk_root, _d, files in os.walk(
                    os.path.join(sdnand_pkg, "title", "00030017")
                ):
                    if "title.tmd" in files:
                        tmd_src = os.path.join(walk_root, "title.tmd")
                        break
            if os.path.isfile(tmd_src):
                shutil.copy2(tmd_src, os.path.join(launcher_folder, "title.tmd"))

            log(f"Launcher {region} ({launcher_app}) instalado no staging.")

            # Promote SDNAND para o cartão (pastas críticas)
            undo = UndoStack()
            baks: list[Optional[str]] = []
            critical_dirs = (
                "title",
                "ticket",
                "sys",
                "shared1",
                "shared2",
                "hiya",
                "photo",
            )
            try:
                for dname in critical_dirs:
                    src = os.path.join(sdnand, dname)
                    if not os.path.isdir(src):
                        continue
                    dst = os.path.join(mount_path, dname)
                    log(f"A copiar {dname}/…")
                    n = _stage_dir_copy(undo, src, dst, log_callback)
                    log(f"✅ {dname}/ ({n} ficheiros).")

                # ficheiros na raiz do SDNAND relevantes
                for fname in ("hiya.dsi",):
                    src = os.path.join(sdnand, fname)
                    if os.path.isfile(src):
                        bak = _stage_file_copy(
                            undo,
                            src,
                            os.path.join(mount_path, fname),
                            log_callback,
                        )
                        baks.append(bak)
                        log(f"✅ {fname} copiado.")

                # TWiLight se faltar
                from core.exploits import _twilight_present

                if not _twilight_present(mount_path):
                    log("TWiLight em falta — a instalar versão pinada…")
                    ok, msg = install_twilight_menu(mount_path, log_callback=log_callback)
                    if not ok:
                        raise RuntimeError(f"hiya OK parcial, mas TWiLight falhou: {msg}")

                sync_volume(mount_path)
                _cleanup_baks(baks)

                if not hiya_markers_ok(mount_path):
                    raise RuntimeError("Validação pós-install: hiya.dsi/hiya em falta.")

                log("🎉 hiyaCFW + SDNAND instalados no SD.")
                log(
                    "No DSi (Unlaunch): A+B → OPTIONS → NO BUTTON → hiyaCFW. "
                    "Não faça system update."
                )
                return True, (
                    "hiyaCFW instalado. Configure Unlaunch: NO BUTTON → hiyaCFW. "
                    "Não atualize o sistema."
                )
            except Exception as e:
                log(f"⚠️ Falha ao promover para o SD — revertendo: {e}")
                undo.rollback(log_callback, mount_path=mount_path)
                return False, str(e)

        except Exception as e:
            log(f"⚠️ Falha no pipeline hiyaCFW: {e}")
            return False, str(e)
