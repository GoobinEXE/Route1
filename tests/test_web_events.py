import json
import time
from types import SimpleNamespace

from services import web_events


class _FakeWindow:
    def __init__(self):
        self.calls = []

    def evaluate_js(self, script):
        self.calls.append(script)


def _extract_dispatch_payload(script):
    prefix = "R1K.events.dispatch("
    assert script.startswith(prefix)
    assert script.endswith(")")
    return json.loads(script[len(prefix) : -1])


def test_emit_coalesces_same_event_type(monkeypatch):
    win = _FakeWindow()
    monkeypatch.setattr(web_events, "webview", SimpleNamespace(windows=[win]))
    web_events.stop()
    # Isolar fila: só logs neste teste (o serviço é singleton partilhado).
    for i in range(25):
        web_events.emit("log", {"message": f"log-{i}"})
    web_events.start()
    time.sleep(0.25)
    web_events.stop()
    log_calls = [
        c for c in win.calls if '"type": "log"' in c or "\"type\": \"log\"" in c
    ]
    assert len(log_calls) == 1
    payload = _extract_dispatch_payload(log_calls[0])
    assert payload["type"] == "log"
    assert payload["payload"]["message"] == "log-24"


def test_emit_without_window_never_crashes(monkeypatch):
    monkeypatch.setattr(web_events, "webview", SimpleNamespace(windows=[]))
    web_events.stop()
    web_events.start()
    web_events.emit("updates", {"available": True})
    time.sleep(0.12)
    web_events.stop()
