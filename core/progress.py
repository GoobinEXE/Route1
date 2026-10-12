"""Tracker de progresso para a UI (bytes/itens, velocidade, ETA).

Emit throttled via web_events — não abranda I/O no hot path.

Cancelamento cooperativo: o utilizador pede via Api.cancel_op; as ops
param em fronteiras seguras (entre ficheiros / chunks .partial) sem
deixar destinos a meio.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Optional

# Alinhado ao coalesce ~10 Hz de services/web_events.py
_MIN_EMIT_INTERVAL_SEC = 0.12
_MIN_SPEED_SAMPLES_SEC = 0.5
_EMA_ALPHA = 0.35

EmitFn = Callable[[dict[str, Any]], None]

# Cancelamento da operação sob OP_LOCK (pedido da UI → check nos hot paths).
_CANCEL_EVENT = threading.Event()
_CANCEL_OP: str = ""
_CANCEL_LOCK = threading.Lock()


class OperationCancelled(Exception):
    """Pedido de cancelamento honrado num ponto seguro (sem corrupção)."""

    def __init__(self, message: str = "Operação cancelada pelo utilizador.") -> None:
        super().__init__(message)


def begin_operation(op: str = "") -> None:
    """Limpa o pedido de cancelamento ao iniciar uma op sob OP_LOCK."""
    global _CANCEL_OP
    with _CANCEL_LOCK:
        _CANCEL_OP = str(op or "")
        _CANCEL_EVENT.clear()


def end_operation() -> None:
    """Limpa estado de cancelamento ao libertar OP_LOCK."""
    global _CANCEL_OP
    with _CANCEL_LOCK:
        _CANCEL_OP = ""
        _CANCEL_EVENT.clear()


def request_cancel() -> bool:
    """
    Pede cancelamento da op em curso.
    Retorna True se o flag foi activado (a op pára no próximo checkpoint).
    """
    with _CANCEL_LOCK:
        op = _CANCEL_OP
        _CANCEL_EVENT.set()
    try:
        emit_progress(
            {
                "op": op,
                "label": "A cancelar… (ponto seguro)",
                "cancelling": True,
                "done": False,
            }
        )
    except Exception:
        pass
    return True


def is_cancelled() -> bool:
    return _CANCEL_EVENT.is_set()


def check_cancelled() -> None:
    """Levanta OperationCancelled se o utilizador pediu cancelar."""
    if _CANCEL_EVENT.is_set():
        raise OperationCancelled()


# Último snapshot — fallback se evaluate_js falhar durante a chamada API.
_LAST_LOCK = threading.Lock()
_LAST_PROGRESS: Optional[dict[str, Any]] = None


def remember_progress(payload: dict[str, Any]) -> None:
    """Guarda cópia do último progresso (thread-safe)."""
    global _LAST_PROGRESS
    if not isinstance(payload, dict):
        return
    with _LAST_LOCK:
        _LAST_PROGRESS = dict(payload)


def get_last_progress() -> Optional[dict[str, Any]]:
    """Cópia do último progresso emitido, ou None."""
    with _LAST_LOCK:
        if _LAST_PROGRESS is None:
            return None
        return dict(_LAST_PROGRESS)


def clear_last_progress() -> None:
    global _LAST_PROGRESS
    with _LAST_LOCK:
        _LAST_PROGRESS = None


def emit_progress(payload: dict[str, Any]) -> None:
    """Push best-effort do payload progress para a UI (+ snapshot para poll)."""
    if not isinstance(payload, dict):
        return
    remember_progress(payload)
    try:
        from services import web_events

        web_events.emit("progress", payload)
    except Exception:
        pass


class ProgressTracker:
    """Acumula progresso e emite payloads densos com throttle."""

    def __init__(
        self,
        op: str,
        *,
        label: str = "",
        total_items: int = 0,
        total_bytes: int = 0,
        emit_fn: Optional[EmitFn] = None,
    ) -> None:
        self.op = str(op or "")
        self.label = str(label or "")
        self.phase: Optional[str] = None
        self.current = 0
        self.total_items = max(0, int(total_items or 0))
        self.bytes_done = 0
        self.total_bytes = max(0, int(total_bytes or 0))
        self.written = 0
        self.skipped = 0
        self.failed = 0
        self._emit: EmitFn = emit_fn or emit_progress
        self._t0 = time.monotonic()
        self._last_emit = 0.0
        self._last_sample_t = self._t0
        self._last_sample_bytes = 0
        self._last_sample_items = 0
        self._speed_bps: Optional[float] = None
        self._speed_ips: Optional[float] = None
        self._done = False
        # False só em fases destrutivas irrecuperáveis (ex. format a meio).
        self.cancellable: bool = True

    def set_totals(
        self,
        *,
        items: Optional[int] = None,
        bytes: Optional[int] = None,
    ) -> None:
        if items is not None:
            try:
                self.total_items = max(0, int(items))
            except (TypeError, ValueError):
                pass
        if bytes is not None:
            try:
                self.total_bytes = max(0, int(bytes))
            except (TypeError, ValueError):
                pass

    def set_label(self, label: str) -> None:
        self.label = str(label or "")

    def set_phase(
        self,
        phase: str,
        *,
        label: Optional[str] = None,
        cancellable: Optional[bool] = None,
    ) -> None:
        self.phase = str(phase or "") or None
        if label is not None:
            self.label = str(label or "")
        if cancellable is not None:
            self.cancellable = bool(cancellable)
        self.tick(force=True)

    def add_bytes(self, n: int) -> None:
        """Hot path: acumula bytes sem emitir."""
        try:
            delta = int(n)
        except (TypeError, ValueError):
            return
        if delta <= 0:
            return
        self.bytes_done += delta
        self._update_rates()

    def advance_item(
        self,
        *,
        bytes_delta: int = 0,
        label: Optional[str] = None,
        written: bool = False,
        skipped: bool = False,
        failed: bool = False,
    ) -> None:
        self.current += 1
        if bytes_delta:
            self.add_bytes(bytes_delta)
        else:
            self._update_rates()
        if written:
            self.written += 1
        if skipped:
            self.skipped += 1
        if failed:
            self.failed += 1
        if label is not None:
            self.label = str(label or "")
        self.tick(force=True)

    def _update_rates(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_sample_t
        if elapsed < 0.05:
            return
        wall = now - self._t0
        if wall < _MIN_SPEED_SAMPLES_SEC:
            return

        db = self.bytes_done - self._last_sample_bytes
        di = self.current - self._last_sample_items
        self._last_sample_t = now
        self._last_sample_bytes = self.bytes_done
        self._last_sample_items = self.current

        if db > 0:
            inst = db / elapsed
            if self._speed_bps is None:
                self._speed_bps = inst
            else:
                self._speed_bps = (
                    _EMA_ALPHA * inst + (1.0 - _EMA_ALPHA) * self._speed_bps
                )
        if di > 0:
            inst_i = di / elapsed
            if self._speed_ips is None:
                self._speed_ips = inst_i
            else:
                self._speed_ips = (
                    _EMA_ALPHA * inst_i + (1.0 - _EMA_ALPHA) * self._speed_ips
                )

    def _pct(self) -> Optional[int]:
        if self.total_bytes > 0:
            return min(
                100, int(round(100.0 * self.bytes_done / float(self.total_bytes)))
            )
        if self.total_items > 0:
            return min(100, int(round(100.0 * self.current / float(self.total_items))))
        return None

    def _eta_s(self) -> Optional[int]:
        if self.total_bytes > 0 and self._speed_bps and self._speed_bps > 1.0:
            remaining = self.total_bytes - self.bytes_done
            if remaining <= 0:
                return 0
            return max(0, int(round(remaining / self._speed_bps)))
        if self.total_items > 0 and self._speed_ips and self._speed_ips > 0.01:
            remaining = self.total_items - self.current
            if remaining <= 0:
                return 0
            return max(0, int(round(remaining / self._speed_ips)))
        return None

    def build_payload(self, *, done: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "op": self.op,
            "label": self.label or ("Concluído" if done else "A processar…"),
            "done": bool(done),
        }
        if self.phase:
            payload["phase"] = self.phase
        if self.total_items > 0 or self.current > 0:
            payload["current"] = int(self.current)
            if self.total_items > 0:
                payload["total"] = int(self.total_items)
        if self.bytes_done > 0 or self.total_bytes > 0:
            payload["bytes_done"] = int(self.bytes_done)
            if self.total_bytes > 0:
                payload["bytes_total"] = int(self.total_bytes)
        pct = 100 if done and (self.total_bytes > 0 or self.total_items > 0) else self._pct()
        if pct is not None:
            payload["pct"] = int(pct)
        if self.written:
            payload["written"] = int(self.written)
        if self.skipped:
            payload["skipped"] = int(self.skipped)
        if self.failed:
            payload["failed"] = int(self.failed)
        if not done:
            payload["cancellable"] = bool(self.cancellable)
            if self._speed_bps is not None and self._speed_bps > 0:
                payload["speed_bps"] = float(self._speed_bps)
            elif self._speed_ips is not None and self._speed_ips > 0:
                payload["speed_ips"] = float(self._speed_ips)
            eta = self._eta_s()
            if eta is not None:
                payload["eta_s"] = int(eta)
        return payload

    def tick(self, force: bool = False) -> None:
        if self._done:
            return
        now = time.monotonic()
        if not force and (now - self._last_emit) < _MIN_EMIT_INTERVAL_SEC:
            return
        self._update_rates()
        self._last_emit = now
        payload = self.build_payload(done=False)
        remember_progress(payload)
        try:
            self._emit(payload)
        except Exception:
            pass

    def finish(self, label: str = "Concluído") -> None:
        self._done = True
        if label:
            self.label = str(label)
        if self.total_items > 0:
            self.current = max(self.current, self.total_items)
        if self.total_bytes > 0:
            self.bytes_done = max(self.bytes_done, self.total_bytes)
        payload = self.build_payload(done=True)
        remember_progress(payload)
        try:
            self._emit(payload)
        except Exception:
            pass


# Labels PT curtos para ops conhecidas (bridge / UI).
OP_LABELS_PT: dict[str, str] = {
    "dspico_import_games": "Importar jogos",
    "dspico_artwork_batch": "Capas DSPico",
    "twilight_artwork_batch": "Capas TWiLight",
    "generate_dspico_artwork_batch": "Capas DSPico",
    "generate_dspico_covers_batch": "Capas DSPico",
    "generate_twilight_artwork_batch": "Capas TWiLight",
    "dspico_organize": "Organizar DSPico",
    "organize_dspico": "Organizar DSPico",
    "import_roms": "Importar ROMs",
    "organize_roms": "Organizar ROMs",
    "setup_dspico": "Preparar DSPico",
    "setup_gei": "Kernel GEi",
    "setup_r4": "Kernel R4",
    "setup_nand_dump": "Passo 1 (dump)",
    "setup_unlaunch": "Passo 2 (Unlaunch)",
    "setup_hiya": "hiyaCFW",
    "setup_godmode9i": "GodMode9i",
    "format_sd": "Formatar cartão",
    "backup_sd": "Backup do cartão",
    "backup_drive": "Backup do cartão",
    "backup": "Backup do cartão",
    "download": "Descarregar",
    "cache_download": "Descarregar",
}


def op_label_pt(op: str) -> str:
    key = str(op or "").strip()
    return OP_LABELS_PT.get(key, key.replace("_", " ") if key else "Operação")
