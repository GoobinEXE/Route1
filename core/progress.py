"""Progresso de operações longas (fração 0–1) para a UI."""

from __future__ import annotations

from typing import Optional, Tuple

from core.privacy import redact_text


def clamp_fraction(value) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 0.0
    if f < 0.0:
        return 0.0
    if f > 1.0:
        return 1.0
    return f


def map_fraction(local: float, span: Optional[Tuple[float, float]]) -> float:
    """Mapeia fração local 0–1 para um intervalo absoluto (start, end)."""
    local = clamp_fraction(local)
    if not span:
        return local
    try:
        start = float(span[0])
        end = float(span[1])
    except (TypeError, ValueError, IndexError):
        return local
    if end < start:
        start, end = end, start
    return clamp_fraction(start + (end - start) * local)


def emit_progress(log_callback, fraction, detail=None, span=None) -> None:
    """
    Atualiza o progresso se o callback tiver `.progress(fraction, detail=)`.
    `span=(start, end)` mapeia a fração local para o intervalo absoluto.
    """
    if log_callback is None or not hasattr(log_callback, "progress"):
        return
    abs_frac = map_fraction(fraction, span)
    safe_detail = redact_text(detail) if detail else None
    try:
        log_callback.progress(abs_frac, safe_detail)
    except Exception:
        pass  # progresso é best-effort; não derrubar a operação
