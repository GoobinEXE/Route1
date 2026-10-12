"""Testes do ProgressTracker (pct, speed, ETA, throttle, campos opcionais)."""

from __future__ import annotations

import time

from core.progress import ProgressTracker, emit_progress, op_label_pt


def test_op_label_pt_known_and_fallback():
    assert op_label_pt("dspico_import_games") == "Importar jogos"
    assert op_label_pt("format_sd") == "Formatar cartão"
    assert "foo" in op_label_pt("foo_bar")


def test_build_payload_omits_unknown_totals():
    events = []
    t = ProgressTracker("cache_download", label="A descarregar…", emit_fn=events.append)
    t.add_bytes(1024)
    t.tick(force=True)
    assert events
    p = events[-1]
    assert p["op"] == "cache_download"
    assert p["bytes_done"] == 1024
    assert "bytes_total" not in p
    assert "pct" not in p
    assert "eta_s" not in p


def test_pct_prefers_bytes_over_items():
    t = ProgressTracker(
        "import_roms",
        total_items=10,
        total_bytes=1000,
        emit_fn=lambda _p: None,
    )
    t.current = 1
    t.bytes_done = 250
    assert t._pct() == 25


def test_pct_falls_back_to_items():
    t = ProgressTracker(
        "twilight_artwork_batch",
        total_items=4,
        emit_fn=lambda _p: None,
    )
    t.current = 2
    assert t._pct() == 50


def test_advance_item_emits_and_counts(monkeypatch):
    events = []
    monkeypatch.setattr(
        "core.progress._MIN_SPEED_SAMPLES_SEC", 0.0
    )
    t = ProgressTracker(
        "dspico_import_games",
        total_items=2,
        total_bytes=200,
        emit_fn=events.append,
    )
    t.advance_item(bytes_delta=100, label="a.nds", written=True)
    t.advance_item(bytes_delta=100, label="b.nds", written=True)
    assert t.current == 2
    assert t.bytes_done == 200
    assert t.written == 2
    assert any(e.get("label") == "b.nds" for e in events)


def test_finish_sets_done_and_full_pct():
    events = []
    t = ProgressTracker(
        "organize_roms",
        total_items=3,
        total_bytes=300,
        emit_fn=events.append,
    )
    t.current = 2
    t.bytes_done = 200
    t.finish("Concluído")
    assert events
    p = events[-1]
    assert p["done"] is True
    assert p["pct"] == 100
    assert p["current"] == 3
    assert p["bytes_done"] == 300


def test_throttle_skips_rapid_ticks():
    events = []
    t = ProgressTracker("cache_download", emit_fn=events.append)
    t.add_bytes(10)
    t.tick(force=True)
    n = len(events)
    t.add_bytes(10)
    t.tick(force=False)
    # Segundo tick imediato deve ser ignorado (intervalo mínimo)
    assert len(events) == n


def test_eta_and_speed_after_samples(monkeypatch):
    events = []
    monkeypatch.setattr("core.progress._MIN_SPEED_SAMPLES_SEC", 0.0)
    t = ProgressTracker(
        "cache_download",
        total_bytes=1000,
        emit_fn=events.append,
    )
    t._t0 = time.monotonic() - 1.0
    t._last_sample_t = time.monotonic() - 0.5
    t.add_bytes(500)
    t._update_rates()
    assert t._speed_bps is not None and t._speed_bps > 0
    eta = t._eta_s()
    assert eta is not None
    assert eta >= 0


def test_emit_progress_swallows_errors(monkeypatch):
    def boom(_type, _payload):
        raise RuntimeError("no window")

    monkeypatch.setattr(
        "services.web_events.emit",
        boom,
        raising=False,
    )
    # Não deve propagar
    emit_progress({"op": "x", "label": "y"})


def test_last_progress_snapshot_for_poll():
    from core.progress import clear_last_progress, get_last_progress

    clear_last_progress()
    assert get_last_progress() is None
    events = []
    t = ProgressTracker(
        "dspico_artwork_batch",
        total_items=10,
        emit_fn=events.append,
    )
    t.cancellable = True
    t.current = 3
    t.tick(force=True)
    snap = get_last_progress()
    assert snap is not None
    assert snap["op"] == "dspico_artwork_batch"
    assert snap["current"] == 3
    assert snap["total"] == 10
    assert snap.get("cancellable") is True
    clear_last_progress()
    assert get_last_progress() is None


def test_cancel_request_raises_at_checkpoint():
    from core.progress import (
        OperationCancelled,
        begin_operation,
        check_cancelled,
        end_operation,
        request_cancel,
    )

    begin_operation("twilight_artwork_batch")
    try:
        check_cancelled()  # no-op
        request_cancel()
        try:
            check_cancelled()
            assert False, "deveria cancelar"
        except OperationCancelled:
            pass
    finally:
        end_operation()
