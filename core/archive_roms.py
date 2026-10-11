"""Extracção segura de ROMs a partir de .zip / .7z / .rar para importação."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import zipfile
from typing import Any, Iterable, Optional

from core.cache import CACHE_DIR, ensure_cache_dir
from core.privacy import redact_path
from core.twilight import _audit_extracted_tree, _extract_7z_safe, _is_safe_archive_member

ARCHIVE_EXTS = frozenset({".zip", ".7z", ".7zip", ".rar"})
_MAX_ROMS_PER_ARCHIVE = 200
_MAX_ARCHIVE_BYTES = 4 * 1024 * 1024 * 1024  # 4 GiB
_RAR_TIMEOUT = 120


def is_archive_path(path: str) -> bool:
    low = (path or "").lower()
    if low.endswith(".7zip"):
        return True
    return os.path.splitext(low)[1] in ARCHIVE_EXTS


def _archive_kind(path: str) -> Optional[str]:
    low = (path or "").lower()
    if low.endswith(".7zip") or low.endswith(".7z"):
        return "7z"
    if low.endswith(".zip"):
        return "zip"
    if low.endswith(".rar"):
        return "rar"
    return None


def _collect_roms_under(
    root: str, allowed_exts: frozenset[str], *, limit: int
) -> list[str]:
    out: list[str] = []
    root_real = os.path.realpath(root)
    for walk_root, dirs, files in os.walk(root):
        # Evitar lixo de SO / macOS
        dirs[:] = [
            d
            for d in dirs
            if d not in (".", "..", "__MACOSX", ".DS_Store") and not d.startswith(".")
        ]
        for name in files:
            if name.startswith(".") or name.startswith("._"):
                continue
            full = os.path.join(walk_root, name)
            try:
                if os.path.islink(full) or not os.path.isfile(full):
                    continue
                real = os.path.realpath(full)
                if os.path.commonpath([root_real, real]) != root_real:
                    continue
            except (OSError, ValueError):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext not in allowed_exts:
                continue
            out.append(real)
            if len(out) >= limit:
                return out
    return out


def _extract_zip_safe(archive_path: str, tmp: str) -> None:
    with zipfile.ZipFile(archive_path, "r") as zf:
        for info in zf.infolist():
            name = info.filename
            if not _is_safe_archive_member(name, tmp):
                raise RuntimeError(
                    f"Arquivo zip rejeitado (caminho inseguro): {name!r}"
                )
            if info.is_dir():
                continue
            # Symlinks / atributos Unix
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise RuntimeError(f"Symlink rejeitado na extração: {name!r}")
        zf.extractall(path=tmp)
    _audit_extracted_tree(tmp)


def _resolve_7za() -> Optional[str]:
    """Binário 7za/7z pinado (TWLMagician), sem exigir toda a toolchain hiya."""
    import platform

    from core.cache import ensure_cached

    system = platform.system()
    if system == "Darwin":
        key = "twlm_7za_darwin"
    elif system == "Windows":
        key = "twlm_7z_win"
    else:
        key = "twlm_7za_linux"
    try:
        path = ensure_cached(key)
    except Exception:
        return None
    if not path or not os.path.isfile(path):
        return None
    if system != "Windows":
        try:
            os.chmod(path, 0o755)
        except OSError:
            pass
    return path


def _extract_rar_safe(archive_path: str, tmp: str) -> None:
    za = _resolve_7za()
    if not za:
        raise RuntimeError(
            "Não foi possível obter o 7za pinado para extrair .rar. "
            "Verifique a ligação à Internet ou extraia o arquivo manualmente."
        )
    # 7za: -y assume Yes; -o sem espaço antes do path
    out_switch = f"-o{tmp}"
    cmd = [za, "x", "-y", "-bd", out_switch, "--", archive_path]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_RAR_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError("Tempo esgotado ao extrair .rar.") from e
    except OSError as e:
        raise RuntimeError(f"Falha ao executar 7za: {e}") from e
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(
            "Falha ao extrair .rar"
            + (f": {err[:200]}" if err else ".")
        )
    _audit_extracted_tree(tmp)


def _extract_archive(archive_path: str, tmp: str, kind: str) -> None:
    if kind == "zip":
        _extract_zip_safe(archive_path, tmp)
    elif kind == "7z":
        _extract_7z_safe(archive_path, tmp)
    elif kind == "rar":
        _extract_rar_safe(archive_path, tmp)
    else:
        raise RuntimeError(f"Formato de arquivo não suportado: {kind}")


def expand_rom_sources(
    paths: Iterable[str],
    allowed_exts: Iterable[str],
    *,
    max_roms_per_archive: int = _MAX_ROMS_PER_ARCHIVE,
) -> tuple[list[str], list[str], dict[str, Any]]:
    """
    Expande ROMs soltas e arquivos (.zip/.7z/.rar) para paths absolutos de ROM.

    Retorna (rom_paths, errors, stats). Staging temporário é limpo no fim;
    os paths devolvidos são cópias sob um staging partilhado que o caller
    deve usar imediatamente (ainda válido até cleanup do contexto).

    Nota: o staging vive até ``cleanup_expand_staging(stats)`` ou GC do
    TemporaryDirectory guardado em stats[\"_staging_dirs\"].
    """
    allowed = frozenset(
        e.lower() if e.startswith(".") else f".{e.lower()}" for e in allowed_exts
    )
    rom_paths: list[str] = []
    errors: list[str] = []
    stats: dict[str, Any] = {
        "archives": 0,
        "direct": 0,
        "extracted_roms": 0,
        "_staging_dirs": [],
    }
    try:
        max_n = int(max_roms_per_archive)
    except (TypeError, ValueError):
        max_n = _MAX_ROMS_PER_ARCHIVE
    if max_n < 1:
        max_n = 1

    staging_parent = None
    try:
        ensure_cache_dir()
        staging_parent = CACHE_DIR
    except OSError:
        staging_parent = None
    try:
        staging_root = tempfile.mkdtemp(
            prefix="rom_import_", dir=staging_parent
        )
    except OSError:
        staging_root = tempfile.mkdtemp(prefix="rom_import_")
    stats["_staging_dirs"].append(staging_root)

    seen: set[str] = set()

    def _add_rom(path: str) -> None:
        real = os.path.realpath(path)
        if real in seen:
            return
        seen.add(real)
        rom_paths.append(real)

    for raw in paths:
        if not isinstance(raw, str) or not raw.strip() or "\x00" in raw:
            continue
        src = os.path.realpath(os.path.expanduser(raw.strip()))
        if not os.path.isfile(src):
            errors.append(f"Inexistente: {redact_path(src)}")
            continue
        try:
            size = os.path.getsize(src)
        except OSError:
            errors.append(f"Inacessível: {redact_path(src)}")
            continue

        kind = _archive_kind(src)
        if kind is None:
            ext = os.path.splitext(src)[1].lower()
            if ext not in allowed:
                errors.append(f"Extensão não suportada: {os.path.basename(src)}")
                continue
            _add_rom(src)
            stats["direct"] += 1
            continue

        if size > _MAX_ARCHIVE_BYTES:
            errors.append(
                f"Arquivo demasiado grande: {os.path.basename(src)}"
            )
            continue

        stats["archives"] += 1
        tmp = tempfile.mkdtemp(prefix=f"arc_{kind}_", dir=staging_root)
        try:
            _extract_archive(src, tmp, kind)
        except Exception as e:
            errors.append(
                f"{os.path.basename(src)}: {e}"
            )
            continue
        found = _collect_roms_under(tmp, allowed, limit=max_n)
        if not found:
            errors.append(
                f"Sem ROMs válidas em {os.path.basename(src)}"
            )
            continue
        for rom in found:
            _add_rom(rom)
            stats["extracted_roms"] += 1
        if len(found) >= max_n:
            errors.append(
                f"{os.path.basename(src)}: limite de {max_n} ROMs por arquivo."
            )

    stats["roms"] = len(rom_paths)
    return rom_paths, errors, stats


def cleanup_expand_staging(stats: Optional[dict[str, Any]]) -> None:
    """Remove staging criado por expand_rom_sources."""
    if not isinstance(stats, dict):
        return
    dirs = stats.pop("_staging_dirs", None) or []
    allow_roots = []
    try:
        allow_roots.append(os.path.realpath(CACHE_DIR))
    except OSError:
        pass
    try:
        allow_roots.append(os.path.realpath(tempfile.gettempdir()))
    except OSError:
        pass
    for d in dirs:
        if not isinstance(d, str) or not d or not os.path.isdir(d):
            continue
        try:
            real = os.path.realpath(d)
            if not any(
                os.path.commonpath([root, real]) == root for root in allow_roots
            ):
                continue
            if "rom_import_" not in os.path.basename(real):
                continue
            shutil.rmtree(real, ignore_errors=True)
        except (OSError, ValueError):
            pass
