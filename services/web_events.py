"""Push de eventos UI (best-effort) para pywebview."""

from __future__ import annotations

import json
import threading
import time
from collections import deque
from typing import Deque, Dict, Optional, Tuple

try:  # pragma: no cover - pywebview pode não estar disponível em testes
    import webview
except Exception:  # pragma: no cover
    webview = None

_SUPPORTED_TYPES = frozenset({"log", "busy", "progress", "updates"})
_MAX_DISPATCH_HZ = 10.0
_MIN_INTERVAL_SEC = 1.0 / _MAX_DISPATCH_HZ


class _WebEventsService:
    """Fila thread-safe com dispatcher único e rate-limit global."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending_by_type: Dict[str, dict] = {}
        self._order: Deque[str] = deque()
        self._wake_event = threading.Event()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._next_dispatch_at = 0.0

    def start(self) -> None:
        with self._lock:
            running = self._thread is not None and self._thread.is_alive()
            if running:
                return
            self._stop_event.clear()
            self._wake_event.clear()
            self._next_dispatch_at = 0.0
            self._thread = threading.Thread(
                target=self._dispatch_loop,
                name="R1KWebEventsDispatcher",
                daemon=True,
            )
            self._thread.start()

    def stop(self, timeout: float = 1.0) -> None:
        with self._lock:
            thread = self._thread
            self._thread = None
        if thread is None:
            return
        self._stop_event.set()
        self._wake_event.set()
        thread.join(timeout=timeout)
        with self._lock:
            self._pending_by_type.clear()
            self._order.clear()

    def emit(self, event_type: str, payload: dict) -> None:
        if event_type not in _SUPPORTED_TYPES:
            return
        if not isinstance(payload, dict):
            return
        with self._lock:
            if event_type not in self._pending_by_type:
                self._order.append(event_type)
            self._pending_by_type[event_type] = payload
        self._wake_event.set()

    def _pop_next(self) -> Optional[Tuple[str, dict]]:
        with self._lock:
            while self._order:
                event_type = self._order.popleft()
                payload = self._pending_by_type.pop(event_type, None)
                if payload is not None:
                    return event_type, payload
        return None

    def _dispatch_loop(self) -> None:
        while not self._stop_event.is_set():
            item = self._pop_next()
            if item is None:
                self._wake_event.wait(timeout=0.5)
                self._wake_event.clear()
                continue
            now = time.monotonic()
            wait_sec = self._next_dispatch_at - now
            if wait_sec > 0 and self._stop_event.wait(timeout=wait_sec):
                break
            event_type, payload = item
            self._dispatch_event(event_type, payload)
            self._next_dispatch_at = max(self._next_dispatch_at, time.monotonic()) + _MIN_INTERVAL_SEC

    @staticmethod
    def _dispatch_event(event_type: str, payload: dict) -> None:
        # Best-effort: erros de janela/JS não devem propagar para chamadores.
        try:
            windows = getattr(webview, "windows", None) if webview is not None else None
            if not windows:
                return
            win = windows[0]
            data = {"type": event_type, "payload": payload}
            js_payload = json.dumps(data, ensure_ascii=False)
            win.evaluate_js(f"R1K.events.dispatch({js_payload})")
        except Exception:
            return


_SERVICE = _WebEventsService()


def start() -> None:
    _SERVICE.start()


def stop(timeout: float = 1.0) -> None:
    _SERVICE.stop(timeout=timeout)


def emit(event_type: str, payload: dict) -> None:
    _SERVICE.emit(event_type, payload)
