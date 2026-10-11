"""Instalação do TWiLight Menu++, kernel GEi e kernel R4."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from typing import Any, Optional

from core.cache import CACHE_DIR, ensure_cached, ensure_cache_dir
from core.logging_util import emit_log
from core.privacy import expand_user_path, redact_path
from core.rom_cleaner import TWILIGHT_ROM_FOLDERS, ensure_twilight_rom_folders
from core.sdio import UndoStack, copy_verified, copytree_verified, sync_volume
from core.validate import twilight_tree_ok, validate_nds_header

# Pacote base GEi incluído no repositório / build (vendor/GEiv4.2_EN).
_GEI_VENDOR_REL = os.path.join("vendor", "GEiv4.2_EN")

# Extensões / nomes típicos de kernel Slot-1 (não jogos).
_R4_KERNEL_FILES = {
    "_ds_menu.dat",
    "_dsmenu.dat",
    "r4.dat",
    "r4tf.dat",
    "r4i.dat",
    "akmenu4.nds",
    "r4.nds",
    "ttmenu.dat",
    "ttmenu.nds",
    "usp.dat",
    "ysmenu.ini",
    "system.ini",
    "moonshl2.ini",
}
_R4_KERNEL_DIRS = {
    "_system_",
    "moonshl",
    "moonshl2",
    "ttmenu",
    "system",
    "skin",
    "skins",
    "r4i",
    "r4",
}
_R4_SKIP_DIRS = {"roms", "games", "games", "nds", "gba", "dsi", "saves", "save"}
_R4_LAUNCHER_NDS = {"akmenu4.nds", "r4.nds", "ttmenu.nds", "_ds_mshl.nds"}


def _stage_file_copy(undo: UndoStack, src: str, dst: str, log_callback=None, expected_sha256=None):
    """Copia verificada com rollback: restaura backup ou remove ficheiro novo."""
    bak = None
    if os.path.exists(dst):
        bak = dst + ".bak_install"
        shutil.copy2(dst, bak)
        undo.push_restore_file(bak, dst)
    else:
        undo.push_remove(dst)
    copy_verified(src, dst, expected_sha256=expected_sha256, log_callback=log_callback)
    return bak


def _stage_dir_copy(undo: UndoStack, src: str, dst: str, log_callback=None) -> int:
    """
    Copia árvore verificada. Se dst não existia, rollback remove a pasta inteira.
    Se já existia, cada ficheiro fica protegido pelo verify-before-replace
    (parcial: ficheiros já promovidos permanecem; o caller de etapa pode
    remover a pasta se ela era nova).
    """
    if not os.path.isdir(dst):
        undo.push_remove(dst)
    return copytree_verified(src, dst, log_callback=log_callback)

def _cleanup_baks(paths) -> None:
    for bak in paths:
        if bak and os.path.exists(bak):
            try:
                os.remove(bak)
            except OSError:
                pass


def find_twilight_source():
    """Procura TWiLight pinado no cache primeiro; Downloads só como fallback."""
    candidates = [
        os.path.join(CACHE_DIR, "TWiLightMenu-DSi"),
        os.path.expanduser("~/Downloads/TWiLightMenu-DSi"),
    ]
    for c in candidates:
        ok, _ = twilight_tree_ok(c) if os.path.isdir(c) else (False, "")
        if ok:
            # Preferir cache que tenha manifesto gerado pela extração pinada
            if c.startswith(CACHE_DIR) or os.path.isfile(
                os.path.join(c, ".route_1_kit_manifest")
            ):
                return c
    # Se só Downloads existir e for estruturalmente ok, ainda aceita (com aviso no caller)
    for c in candidates:
        ok, _ = twilight_tree_ok(c) if os.path.isdir(c) else (False, "")
        if ok:
            return c
    return None


def _app_root() -> str:
    """Raiz do app (fonte ou _MEIPASS quando frozen)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS  # type: ignore[attr-defined]
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bundled_gei_dir() -> Optional[str]:
    """Pasta vendor/GEiv4.2_EN incluída no projeto, se completa."""
    cand = os.path.normpath(os.path.join(_app_root(), _GEI_VENDOR_REL))
    if is_gei_kernel_dir(cand):
        return cand
    return None


def find_gei_source():
    """Procura o kernel GEi: Downloads/cache (override), depois vendor bundled."""
    candidates = [
        os.path.expanduser("~/Downloads/GEiv4.2_EN"),
        os.path.join(CACHE_DIR, "GEiv4.2_EN"),
        bundled_gei_dir(),
    ]
    for c in candidates:
        if c and is_gei_kernel_dir(c):
            return c
    return None


def is_gei_kernel_dir(path: str) -> bool:
    """GEi distingue-se pelo par _DS_MENU.DAT + _DS_MSHL.NDS."""
    return os.path.isfile(os.path.join(path, "_DS_MENU.DAT")) and os.path.isfile(
        os.path.join(path, "_DS_MSHL.NDS")
    )


def is_bundled_gei_path(path: str | None) -> bool:
    """True se o path for o pacote vendor incluído no app."""
    if not path:
        return False
    bundled = bundled_gei_dir()
    if not bundled:
        return False
    try:
        return os.path.realpath(path) == os.path.realpath(bundled)
    except OSError:
        return False


def _has_r4_marker(path: str) -> bool:
    if not os.path.isdir(path):
        return False
    if is_gei_kernel_dir(path):
        return False
    markers = (
        "_DS_MENU.DAT",
        "_DSMENU.DAT",
        "R4.dat",
        "R4.DAT",
        "R4TF.DAT",
        "R4i.dat",
        "TTMenu.dat",
        "AKMENU4.NDS",
    )
    try:
        names = {n.lower() for n in os.listdir(path)}
    except OSError:
        return False
    return any(m.lower() in names for m in markers)


def _safe_under(root: str, path: str) -> bool:
    try:
        real_root = os.path.realpath(root)
        real_path = os.path.realpath(path)
        return os.path.commonpath([real_root, real_path]) == real_root
    except (ValueError, OSError):
        return False


def find_r4_candidates(search_roots: Optional[list[str]] = None) -> list[dict[str, Any]]:
    """
    Lista pastas candidatas a kernel R4 em Downloads/cache.
    Não inclui pastas GEi. Profundidade limitada a 2 níveis.
    """
    if search_roots is None:
        search_roots = [
            os.path.expanduser("~/Downloads"),
            CACHE_DIR,
        ]

    found: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _consider(folder: str) -> None:
        real = os.path.realpath(folder)
        if real in seen or not os.path.isdir(real):
            return
        if is_gei_kernel_dir(real):
            return
        if not _has_r4_marker(real):
            return
        seen.add(real)
        files = list_r4_kernel_files(real)
        if not files["files"] and not files["dirs"]:
            return
        found.append(
            {
                "path": redact_path(real),
                "name": os.path.basename(real),
                "files": files["files"],
                "dirs": files["dirs"],
            }
        )

    for root in search_roots:
        if not root or not os.path.isdir(root):
            continue
        # Pasta raiz em si (raro)
        _consider(root)
        try:
            level1 = [
                os.path.join(root, n)
                for n in os.listdir(root)
                if os.path.isdir(os.path.join(root, n)) and not n.startswith(".")
            ]
        except OSError:
            continue
        for d1 in level1:
            _consider(d1)
            # Um nível abaixo (ex.: Downloads/R4i/kernel)
            try:
                for n2 in os.listdir(d1):
                    d2 = os.path.join(d1, n2)
                    if os.path.isdir(d2) and not n2.startswith("."):
                        _consider(d2)
            except OSError:
                continue

    found.sort(key=lambda x: x["name"].lower())
    return found


def list_r4_kernel_files(source_dir: str) -> dict[str, list[str]]:
    """Lista apenas artefatos de kernel (arquivos + pastas) a copiar."""
    files: list[str] = []
    dirs: list[str] = []
    if not os.path.isdir(source_dir):
        return {"files": files, "dirs": dirs}

    try:
        entries = os.listdir(source_dir)
    except OSError:
        return {"files": files, "dirs": dirs}

    for name in entries:
        if name.startswith("."):
            continue
        full = os.path.join(source_dir, name)
        low = name.lower()
        if os.path.isdir(full):
            if low in _R4_SKIP_DIRS:
                continue
            if low in _R4_KERNEL_DIRS or low.startswith("_system"):
                dirs.append(name)
            continue
        if not os.path.isfile(full):
            continue
        if low in _R4_KERNEL_FILES:
            files.append(name)
            continue
        # DAT/INI na raiz = tipicamente kernel
        if low.endswith((".dat", ".ini")):
            files.append(name)
            continue
        # Só .nds lançadores conhecidos — nunca jogos genéricos
        if low.endswith(".nds") and low in _R4_LAUNCHER_NDS:
            files.append(name)

    files.sort(key=str.lower)
    dirs.sort(key=str.lower)
    return {"files": files, "dirs": dirs}


def probe_kernels() -> dict[str, Any]:
    """Estado das pastas GEi/R4 (sem gravar). Paths redigidos (~)."""
    gei = find_gei_source()
    r4_list = find_r4_candidates()
    gei_payload = None
    if gei:
        bundled = is_bundled_gei_path(gei)
        gei_payload = {
            "path": "vendor/GEiv4.2_EN" if bundled else redact_path(gei),
            "name": os.path.basename(gei),
            "ready": True,
            "bundled": bundled,
        }
    return {
        "success": True,
        "gei": gei_payload,
        "r4": r4_list,
    }


def install_r4_kernel(mount_path: str, source_dir: str, log_callback=None):
    """
    Copia kernel R4 de source_dir para o MicroSD do cartucho.
    Recusa pastas GEi; ignora roms/; valida path e headers NDS.
    """
    log = lambda msg: emit_log(log_callback, msg)

    log("=== Instalando Kernel do Flashcard R4 ===")
    if not source_dir:
        return False, "Pasta de origem do kernel R4 inválida."
    source_dir = expand_user_path(source_dir)
    if not os.path.isdir(source_dir):
        return False, "Pasta de origem do kernel R4 inválida."

    source_dir = os.path.realpath(source_dir)
    downloads = os.path.realpath(os.path.expanduser("~/Downloads"))
    cache = os.path.realpath(CACHE_DIR)
    if not (_safe_under(downloads, source_dir) or _safe_under(cache, source_dir)):
        return (
            False,
            "A pasta do kernel deve estar em Downloads ou no cache do app.",
        )

    if is_gei_kernel_dir(source_dir):
        return (
            False,
            "Esta pasta parece ser GEi (_DS_MSHL.NDS). Use «Instalar kernel GEi».",
        )

    if not _has_r4_marker(source_dir):
        return False, "Pasta sem marcadores típicos de kernel R4."

    planned = list_r4_kernel_files(source_dir)
    if not planned["files"] and not planned["dirs"]:
        return False, "Nenhum arquivo de kernel R4 encontrado na pasta."

    log(f"Origem dos arquivos R4: {source_dir}")
    log(
        f"A copiar: {len(planned['files'])} arquivo(s), "
        f"{len(planned['dirs'])} pasta(s)."
    )

    undo = UndoStack()
    baks: list[Optional[str]] = []
    try:
        for f in planned["files"]:
            s = os.path.join(source_dir, f)
            if not _safe_under(source_dir, s):
                raise RuntimeError(f"Caminho inseguro rejeitado: {f}")
            if f.lower().endswith(".nds"):
                ok, msg = validate_nds_header(s)
                if not ok:
                    raise RuntimeError(f"Arquivo R4 inválido ({f}): {msg}")
            bak = _stage_file_copy(undo, s, os.path.join(mount_path, f), log_callback)
            baks.append(bak)
            log(f"✅ {f} copiado e verificado.")

        for d in planned["dirs"]:
            s = os.path.join(source_dir, d)
            if not _safe_under(source_dir, s):
                raise RuntimeError(f"Caminho inseguro rejeitado: {d}")
            n = _stage_dir_copy(undo, s, os.path.join(mount_path, d), log_callback)
            log(f"✅ Pasta {d} copiada ({n} arquivos).")

        sync_volume(mount_path)
        _cleanup_baks(baks)
        log("🎉 Kernel R4 instalado com sucesso!")
        return True, "Kernel R4 instalado."
    except Exception as e:
        log(f"⚠️ Falha na instalação R4 — revertendo: {e}")
        undo.rollback(log_callback, mount_path=mount_path)
        return False, str(e)


def _is_safe_archive_member(name: str, extract_root: str) -> bool:
    """Rejeita zip-slip: absolutos, .. e caminhos que saem de extract_root."""
    if not name or name.endswith("/"):
        # diretórios são ok se o caminho resolvido ficar dentro
        pass
    # Normalizar separadores
    norm = name.replace("\\", "/")
    if norm.startswith("/") or (len(norm) > 1 and norm[1] == ":"):
        return False
    parts = [p for p in norm.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        return False
    dest = os.path.realpath(os.path.join(extract_root, *parts))
    root = os.path.realpath(extract_root)
    try:
        common = os.path.commonpath([root, dest])
    except ValueError:
        return False
    return common == root


_VC_GAMEYOB_REL = os.path.join(
    "_nds", "TWiLightMenu", "emulators", "gameyob.nds"
)


def _audit_extracted_tree(tmp: str) -> None:
    """Recusa symlinks e caminhos que saem de ``tmp`` após extractall."""
    root_real = os.path.realpath(tmp)
    for walk_root, dirs, files in os.walk(tmp):
        for name in dirs + files:
            full = os.path.join(walk_root, name)
            real = os.path.realpath(full)
            try:
                common = os.path.commonpath([root_real, real])
            except ValueError:
                raise RuntimeError(f"Extração 7z escapou do diretório: {full}")
            if common != root_real:
                raise RuntimeError(f"Extração 7z escapou do diretório: {full}")
            if os.path.islink(full):
                raise RuntimeError(f"Symlink rejeitado na extração: {full}")


def _promote_extracted_dir(src: str, extract_dir: str, staging_prefix: str) -> str:
    """
    Copia ``src`` para staging com manifesto e promove com rename.
    Em falha, restaura a árvore anterior se existir.
    """
    from core.cache import _sha256_file

    parent = os.path.dirname(os.path.abspath(extract_dir)) or CACHE_DIR
    staging = os.path.join(parent, f".{staging_prefix}_{os.getpid()}")
    old_backup = extract_dir.rstrip("/\\") + ".bak_promote"
    try:
        if os.path.isdir(staging):
            shutil.rmtree(staging, ignore_errors=True)
        if os.path.isdir(old_backup):
            shutil.rmtree(old_backup, ignore_errors=True)

        shutil.copytree(src, staging)

        manifest_path = os.path.join(staging, ".route_1_kit_manifest")
        lines = []
        for root, _dirs, files in os.walk(staging):
            for f in files:
                if f.startswith("."):
                    continue
                full = os.path.join(root, f)
                rel = os.path.relpath(full, staging).replace("\\", "/")
                lines.append(f"{_sha256_file(full)}  {rel}")
        with open(manifest_path, "w", encoding="utf-8") as mf:
            mf.write("\n".join(sorted(lines)) + "\n")

        if os.path.isdir(extract_dir):
            os.rename(extract_dir, old_backup)
        os.rename(staging, extract_dir)
        if os.path.isdir(old_backup):
            shutil.rmtree(old_backup, ignore_errors=True)
    except Exception:
        if os.path.isdir(staging):
            shutil.rmtree(staging, ignore_errors=True)
        if not os.path.isdir(extract_dir) and os.path.isdir(old_backup):
            try:
                os.rename(old_backup, extract_dir)
            except OSError:
                try:
                    shutil.copytree(old_backup, extract_dir)
                    shutil.rmtree(old_backup, ignore_errors=True)
                except OSError:
                    pass
        raise
    return extract_dir


def _extract_7z_safe(archive_path: str, tmp: str) -> None:
    try:
        import py7zr
    except ImportError as e:
        raise RuntimeError(
            "Pacote py7zr não instalado. Execute: pip install -r requirements.txt"
        ) from e

    with py7zr.SevenZipFile(archive_path, mode="r") as archive:
        names = archive.getnames()
        for name in names:
            if not _is_safe_archive_member(name, tmp):
                raise RuntimeError(
                    f"Arquivo 7z rejeitado (caminho inseguro): {name!r}"
                )
        archive.extractall(path=tmp)
    _audit_extracted_tree(tmp)


def _extract_twilight_7z(archive_path, extract_dir, log_callback=None):
    """
    Extrai TWiLightMenu-DSi.7z com py7zr, validando membros contra zip-slip.
    Extrai em diretório temporário e só promove se a árvore for válida.
    """
    emit_log(log_callback, "Extraindo TWiLightMenu-DSi.7z...")
    ensure_cache_dir()

    with tempfile.TemporaryDirectory(dir=CACHE_DIR, prefix="twl_extract_") as tmp:
        _extract_7z_safe(archive_path, tmp)

        # Normalizar se BOOT.NDS estiver um nível abaixo
        src = tmp
        boot = os.path.join(tmp, "BOOT.NDS")
        if not os.path.exists(boot):
            for name in os.listdir(tmp):
                candidate = os.path.join(tmp, name)
                if os.path.isdir(candidate) and os.path.exists(
                    os.path.join(candidate, "BOOT.NDS")
                ):
                    src = candidate
                    break

        ok, msg = twilight_tree_ok(src)
        if not ok:
            raise RuntimeError(f"Pacote TWiLight inválido após extração: {msg}")

        return _promote_extracted_dir(src, extract_dir, "twl_staging")


def twilight_vc_tree_ok(path: str):
    """Valida o add-on Virtual Console (GameYob presente)."""
    if not path or not os.path.isdir(path):
        return False, "Pasta do add-on Virtual Console inexistente"
    gameyob = os.path.join(path, _VC_GAMEYOB_REL)
    if not os.path.isfile(gameyob):
        return False, "gameyob.nds em falta no add-on Virtual Console"
    ok, msg = validate_nds_header(gameyob)
    if not ok:
        return False, f"gameyob.nds inválido: {msg}"
    return True, "ok"


def find_twilight_vc_source():
    """Procura add-on Virtual Console pinado no cache."""
    candidate = os.path.join(CACHE_DIR, "TWiLightMenu-VC")
    ok, _ = twilight_vc_tree_ok(candidate) if os.path.isdir(candidate) else (False, "")
    if ok and os.path.isfile(os.path.join(candidate, ".route_1_kit_manifest")):
        return candidate
    return None


def _extract_twilight_vc_7z(archive_path, extract_dir, log_callback=None):
    """Extrai AddOn-VirtualConsole-DSi-Flashcard.7z (GameYob + outros)."""
    emit_log(log_callback, "Extraindo add-on Virtual Console (GameYob)...")
    ensure_cache_dir()

    with tempfile.TemporaryDirectory(dir=CACHE_DIR, prefix="twl_vc_extract_") as tmp:
        _extract_7z_safe(archive_path, tmp)

        src = tmp
        marker = os.path.join(tmp, _VC_GAMEYOB_REL)
        if not os.path.isfile(marker):
            for name in os.listdir(tmp):
                candidate = os.path.join(tmp, name)
                if os.path.isdir(candidate) and os.path.isfile(
                    os.path.join(candidate, _VC_GAMEYOB_REL)
                ):
                    src = candidate
                    break

        ok, msg = twilight_vc_tree_ok(src)
        if not ok:
            raise RuntimeError(f"Add-on Virtual Console inválido: {msg}")

        return _promote_extracted_dir(src, extract_dir, "twl_vc_staging")


def ensure_twilight_vc_source(log_callback=None) -> str:
    """Garante árvore do add-on Virtual Console no cache (download + extract)."""
    src = find_twilight_vc_source()
    if src:
        return src
    emit_log(log_callback, "🔍 Baixando add-on Virtual Console (GameYob)...")
    archive_path = ensure_cached("twilight_vc_7z", log_callback)
    extract_dir = os.path.join(CACHE_DIR, "TWiLightMenu-VC")
    return _extract_twilight_vc_7z(archive_path, extract_dir, log_callback)


def install_twilight_menu(mount_path, log_callback=None):
    """Copia e instala os arquivos do TWiLight Menu++ no cartão SD (com verificação)."""
    log = lambda msg: emit_log(log_callback, msg)

    log("=== Instalando TWiLight Menu++ ===")
    src = find_twilight_source()
    # Se a origem for só Downloads (sem manifesto), forçar re-extração do archive pinado
    if src and not src.startswith(CACHE_DIR) and not os.path.isfile(
        os.path.join(src, ".route_1_kit_manifest")
    ):
        log(
            "⚠️ TWiLight em Downloads sem manifesto pinado — "
            "baixando/extraindo release oficial pinada em vez disso."
        )
        src = None

    if not src:
        log("🔍 Baixando pacote pinado do TWiLight Menu++...")
        try:
            archive_path = ensure_cached("twilight_7z", log_callback)
            extract_dir = os.path.join(CACHE_DIR, "TWiLightMenu-DSi")
            src = _extract_twilight_7z(archive_path, extract_dir, log_callback)
        except Exception as e:
            log(f"⚠️ Erro ao baixar/extrair TWiLight automaticamente: {e}")
            return (
                False,
                "Não foi possível obter o TWiLight Menu++. "
                "Baixe TWiLightMenu-DSi.7z (v27.24.1), extraia em Downloads/TWiLightMenu-DSi "
                f"e tente de novo. Detalhe: {e}",
            )

    ok, msg = twilight_tree_ok(src)
    if not ok:
        return False, f"Pacote TWiLight incompleto/inválido: {msg}"

    try:
        vc_src = ensure_twilight_vc_source(log_callback)
    except Exception as e:
        log(f"⚠️ Erro ao obter add-on Virtual Console (GameYob): {e}")
        return (
            False,
            "Não foi possível obter o add-on Virtual Console (GameYob). "
            f"Detalhe: {e}",
        )

    log(f"Origem dos arquivos: {src}")

    undo = UndoStack()
    baks: list[Optional[str]] = []
    try:
        boot_src = os.path.join(src, "BOOT.NDS")
        bak = _stage_file_copy(
            undo, boot_src, os.path.join(mount_path, "BOOT.NDS"), log_callback
        )
        baks.append(bak)
        log("✅ BOOT.NDS copiado e verificado.")

        nds_src = os.path.join(src, "_nds")
        if os.path.exists(nds_src):
            log("Copiando pasta _nds (motor do TWiLight)...")
            n = _stage_dir_copy(
                undo, nds_src, os.path.join(mount_path, "_nds"), log_callback
            )
            log(f"✅ Pasta _nds copiada ({n} arquivos verificados).")

        title_src = os.path.join(src, "title")
        if os.path.exists(title_src):
            n = _stage_dir_copy(
                undo, title_src, os.path.join(mount_path, "title"), log_callback
            )
            log(f"✅ Pasta title copiada ({n} arquivos verificados).")

        # Add-on Virtual Console (GameYob GB/GBC + emuladores retro)
        log("Instalando add-on Virtual Console (GameYob)...")
        vc_nds = os.path.join(vc_src, "_nds")
        if os.path.isdir(vc_nds):
            n = _stage_dir_copy(
                undo, vc_nds, os.path.join(mount_path, "_nds"), log_callback
            )
            log(f"✅ Emuladores VC copiados ({n} arquivos; inclui gameyob.nds).")

        snemul_src = os.path.join(vc_src, "snemul.cfg")
        if os.path.isfile(snemul_src):
            bak = _stage_file_copy(
                undo,
                snemul_src,
                os.path.join(mount_path, "snemul.cfg"),
                log_callback,
            )
            baks.append(bak)
            log("✅ snemul.cfg copiado.")

        # Todas as pastas /roms/ do kit (base + Virtual Console + extras)
        for name in TWILIGHT_ROM_FOLDERS:
            dst_sub = os.path.join(mount_path, "roms", name)
            if not os.path.isdir(dst_sub):
                undo.push_remove(dst_sub)
        ensure_twilight_rom_folders(mount_path)

        # Placeholders oficiais do add-on (ficheiros de texto) — best-effort
        vc_roms = os.path.join(vc_src, "roms")
        if os.path.isdir(vc_roms):
            for name in os.listdir(vc_roms):
                if name.startswith("."):
                    continue
                src_sub = os.path.join(vc_roms, name)
                if not os.path.isdir(src_sub):
                    continue
                dst_sub = os.path.join(mount_path, "roms", name)
                os.makedirs(dst_sub, exist_ok=True)
                for placeholder in os.listdir(src_sub):
                    if placeholder.startswith("."):
                        continue
                    p_src = os.path.join(src_sub, placeholder)
                    p_dst = os.path.join(dst_sub, placeholder)
                    if os.path.isfile(p_src) and not os.path.exists(p_dst):
                        bak = _stage_file_copy(undo, p_src, p_dst, log_callback)
                        baks.append(bak)

        log(
            f"✅ Pastas /roms/ criadas "
            f"({len(TWILIGHT_ROM_FOLDERS)} plataformas: gb/gbc/nes/snes/…)."
        )

        sync_volume(mount_path)
        _cleanup_baks(baks)
        log("🎉 TWiLight Menu++ + GameYob (Virtual Console) instalados no SD!")
        return True, "TWiLight Menu++ e Virtual Console (GameYob) instalados."
    except Exception as e:
        log(f"⚠️ Falha ao instalar TWiLight — revertendo: {e}")
        undo.rollback(log_callback, mount_path=mount_path)
        return False, str(e)


def install_twilight_virtual_console(mount_path, log_callback=None):
    """
    Instala só o add-on Virtual Console (GameYob) num SD que já tem TWiLight.
    """
    log = lambda msg: emit_log(log_callback, msg)
    log("=== Instalando Virtual Console (GameYob) ===")
    try:
        vc_src = ensure_twilight_vc_source(log_callback)
    except Exception as e:
        return False, f"Não foi possível obter o add-on Virtual Console: {e}"

    undo = UndoStack()
    baks: list[Optional[str]] = []
    try:
        vc_nds = os.path.join(vc_src, "_nds")
        if not os.path.isdir(vc_nds):
            return False, "Add-on Virtual Console sem pasta _nds."
        n = _stage_dir_copy(
            undo, vc_nds, os.path.join(mount_path, "_nds"), log_callback
        )
        log(f"✅ Emuladores VC copiados ({n} arquivos; inclui gameyob.nds).")

        snemul_src = os.path.join(vc_src, "snemul.cfg")
        if os.path.isfile(snemul_src):
            bak = _stage_file_copy(
                undo,
                snemul_src,
                os.path.join(mount_path, "snemul.cfg"),
                log_callback,
            )
            baks.append(bak)

        for name in TWILIGHT_ROM_FOLDERS:
            dst_sub = os.path.join(mount_path, "roms", name)
            if not os.path.isdir(dst_sub):
                undo.push_remove(dst_sub)
        ensure_twilight_rom_folders(mount_path)

        vc_roms = os.path.join(vc_src, "roms")
        if os.path.isdir(vc_roms):
            for name in os.listdir(vc_roms):
                if name.startswith("."):
                    continue
                src_sub = os.path.join(vc_roms, name)
                if not os.path.isdir(src_sub):
                    continue
                dst_sub = os.path.join(mount_path, "roms", name)
                os.makedirs(dst_sub, exist_ok=True)
                for placeholder in os.listdir(src_sub):
                    if placeholder.startswith("."):
                        continue
                    p_src = os.path.join(src_sub, placeholder)
                    p_dst = os.path.join(dst_sub, placeholder)
                    if os.path.isfile(p_src) and not os.path.exists(p_dst):
                        bak = _stage_file_copy(undo, p_src, p_dst, log_callback)
                        baks.append(bak)

        log(
            f"✅ Pastas /roms/ do Virtual Console "
            f"({len(TWILIGHT_ROM_FOLDERS)} plataformas)."
        )
        sync_volume(mount_path)
        _cleanup_baks(baks)
        log("🎉 Virtual Console (GameYob) instalado no SD!")
        return True, "Virtual Console (GameYob) instalado."
    except Exception as e:
        log(f"⚠️ Falha ao instalar Virtual Console — revertendo: {e}")
        undo.rollback(log_callback, mount_path=mount_path)
        return False, str(e)


def install_gei_kernel(mount_path, log_callback=None):
    """Instala o kernel GEi v4.2 para uso em Flashcards Slot-1."""
    log = lambda msg: emit_log(log_callback, msg)

    log("=== Instalando Kernel do Flashcard GEi (v4.2 EN) ===")
    src = find_gei_source()
    if not src:
        return (
            False,
            "Pacote GEi não encontrado (vendor/GEiv4.2_EN nem Downloads/GEiv4.2_EN).",
        )

    required = ["_DS_MENU.DAT", "_DS_MSHL.NDS"]
    missing = [f for f in required if not os.path.exists(os.path.join(src, f))]
    if missing:
        return False, f"Pacote GEi incompleto — faltando: {', '.join(missing)}"

    origin = (
        "vendor/GEiv4.2_EN (incluído)"
        if is_bundled_gei_path(src)
        else redact_path(src)
    )
    log(f"Origem dos arquivos GEi: {origin}")

    undo = UndoStack()
    baks: list[Optional[str]] = []
    try:
        for f in required:
            s = os.path.join(src, f)
            if f.lower().endswith(".nds"):
                ok, msg = validate_nds_header(s)
                if not ok:
                    raise RuntimeError(f"Arquivo GEi inválido ({f}): {msg}")
            bak = _stage_file_copy(
                undo, s, os.path.join(mount_path, f), log_callback
            )
            baks.append(bak)
            log(f"✅ {f} copiado e verificado.")

        optional_files = ("_DS_MENU.INI",)
        for f in optional_files:
            s = os.path.join(src, f)
            if os.path.isfile(s):
                bak = _stage_file_copy(
                    undo, s, os.path.join(mount_path, f), log_callback
                )
                baks.append(bak)
                log(f"✅ {f} copiado e verificado.")

        for d in ("_SYSTEM_", "MOONSHL"):
            s = os.path.join(src, d)
            if os.path.isdir(s):
                n = _stage_dir_copy(
                    undo, s, os.path.join(mount_path, d), log_callback
                )
                log(f"✅ Pasta {d} copiada ({n} arquivos).")

        sync_volume(mount_path)
        _cleanup_baks(baks)
        log("🎉 Kernel do GEi instalado com sucesso!")
        return True, "Kernel GEi v4.2 instalado."
    except Exception as e:
        log(f"⚠️ Falha na instalação GEi — revertendo: {e}")
        undo.rollback(log_callback, mount_path=mount_path)
        return False, str(e)
