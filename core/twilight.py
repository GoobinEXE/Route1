import os
import shutil

from core.cache import CACHE_DIR, ensure_cached
from core.logging_util import emit_log


def find_twilight_source():
    """Procura se o TWiLightMenu-DSi já foi baixado ou extraído localmente."""
    candidates = [
        os.path.expanduser("~/Downloads/TWiLightMenu-DSi"),
        os.path.join(CACHE_DIR, "TWiLightMenu-DSi"),
    ]
    for c in candidates:
        if os.path.exists(os.path.join(c, "BOOT.NDS")) and os.path.exists(
            os.path.join(c, "_nds")
        ):
            return c
    return None


def find_gei_source():
    """Procura se o kernel do GEi v4.2 já existe nos Downloads."""
    candidates = [
        os.path.expanduser("~/Downloads/GEiv4.2_EN"),
        os.path.join(CACHE_DIR, "GEiv4.2_EN"),
    ]
    for c in candidates:
        if os.path.exists(os.path.join(c, "_DS_MENU.DAT")):
            return c
    return None


def _extract_twilight_7z(archive_path, extract_dir, log_callback=None):
    """Extrai TWiLightMenu-DSi.7z com py7zr (sem depender de 7z no PATH)."""
    try:
        import py7zr
    except ImportError as e:
        raise RuntimeError(
            "Pacote py7zr não instalado. Execute: pip install py7zr"
        ) from e

    emit_log(log_callback, "Extraindo TWiLightMenu-DSi.7z...")
    os.makedirs(extract_dir, exist_ok=True)
    with py7zr.SevenZipFile(archive_path, mode="r") as archive:
        archive.extractall(path=extract_dir)

    # Alguns releases extraem com subpasta; normalizar se BOOT.NDS estiver um nível abaixo
    boot = os.path.join(extract_dir, "BOOT.NDS")
    if not os.path.exists(boot):
        for name in os.listdir(extract_dir):
            candidate = os.path.join(extract_dir, name)
            if os.path.isdir(candidate) and os.path.exists(
                os.path.join(candidate, "BOOT.NDS")
            ):
                return candidate
    return extract_dir


def install_twilight_menu(mount_path, log_callback=None):
    """Copia e instala os arquivos do TWiLight Menu++ no cartão SD."""
    log = lambda msg: emit_log(log_callback, msg)

    log("=== Instalando TWiLight Menu++ ===")
    src = find_twilight_source()
    if not src:
        log("🔍 Baixando pacote mais recente do TWiLight Menu++...")
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            archive_path = ensure_cached("twilight_7z", log_callback)
            extract_dir = os.path.join(CACHE_DIR, "TWiLightMenu-DSi")
            src = _extract_twilight_7z(archive_path, extract_dir, log_callback)
        except Exception as e:
            log(f"⚠️ Erro ao baixar/extrair TWiLight automaticamente: {e}")
            return (
                False,
                "Não foi possível obter o TWiLight Menu++. "
                "Baixe TWiLightMenu-DSi.7z, extraia em Downloads/TWiLightMenu-DSi "
                f"e tente de novo. Detalhe: {e}",
            )

    if not src or not os.path.exists(os.path.join(src, "BOOT.NDS")):
        return (
            False,
            "Pasta TWiLightMenu-DSi não encontrada ou incompleta. "
            "Baixe o TWiLightMenu-DSi.7z e extraia na pasta Downloads.",
        )

    log(f"Origem dos arquivos: {src}")

    boot_src = os.path.join(src, "BOOT.NDS")
    if os.path.exists(boot_src):
        shutil.copy2(boot_src, os.path.join(mount_path, "BOOT.NDS"))
        log("✅ BOOT.NDS copiado.")

    nds_src = os.path.join(src, "_nds")
    if os.path.exists(nds_src):
        log("Copiando pasta _nds (motor do TWiLight)...")
        shutil.copytree(nds_src, os.path.join(mount_path, "_nds"), dirs_exist_ok=True)
        log("✅ Pasta _nds copiada.")

    title_src = os.path.join(src, "title")
    if os.path.exists(title_src):
        shutil.copytree(
            title_src, os.path.join(mount_path, "title"), dirs_exist_ok=True
        )
        log("✅ Pasta title copiada.")

    for console in ("nds", "gba", "dsi"):
        os.makedirs(os.path.join(mount_path, "roms", console), exist_ok=True)
    log("✅ Pastas /roms/ criadas.")

    log("🎉 TWiLight Menu++ instalado com sucesso no SD!")
    return True, "TWiLight Menu++ instalado."


def install_gei_kernel(mount_path, log_callback=None):
    """Instala o kernel GEi v4.2 oficial para uso em Flashcards Slot-1."""
    log = lambda msg: emit_log(log_callback, msg)

    log("=== Instalando Kernel do Flashcard GEi (v4.2 EN) ===")
    src = find_gei_source()
    if not src:
        return False, "Pasta GEiv4.2_EN não encontrada na pasta Downloads."

    log(f"Origem dos arquivos GEi: {src}")

    for f in ("_DS_MENU.DAT", "_DS_MSHL.NDS"):
        s = os.path.join(src, f)
        if os.path.exists(s):
            shutil.copy2(s, os.path.join(mount_path, f))
            log(f"✅ {f} copiado.")

    for d in ("_SYSTEM_", "MOONSHL"):
        s = os.path.join(src, d)
        if os.path.exists(s):
            shutil.copytree(s, os.path.join(mount_path, d), dirs_exist_ok=True)
            log(f"✅ Pasta {d} copiada.")

    log("🎉 Kernel do GEi instalado com sucesso!")
    return True, "Kernel GEi v4.2 instalado."
