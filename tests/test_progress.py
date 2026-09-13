"""Testes do helper de progresso e snapshot na API de logs."""

import app as app_mod
from core.progress import clamp_fraction, emit_progress, map_fraction


def test_clamp_and_map_fraction():
    assert clamp_fraction(-1) == 0.0
    assert clamp_fraction(2) == 1.0
    assert clamp_fraction("x") == 0.0
    assert abs(map_fraction(0.5, (0.2, 0.6)) - 0.4) < 1e-9
    assert map_fraction(1, (0.1, 0.3)) == 0.3


def test_emit_progress_calls_sink():
    seen = []

    class Sink:
        def progress(self, fraction, detail=None):
            seen.append((fraction, detail))

    emit_progress(Sink(), 0.5, "meio", span=(0.0, 1.0))
    assert seen == [(0.5, "meio")]
    emit_progress(None, 0.5, "ignorado")
    assert len(seen) == 1


def test_op_progress_monotonic_and_get_logs():
    app_mod.end_op_progress()
    app_mod.begin_op_progress("inicio")
    app_mod.set_op_progress(0.2, "a")
    app_mod.set_op_progress(0.1, "nao regride")
    snap = app_mod.get_op_progress_snapshot()
    assert snap is not None
    assert snap["fraction"] == 0.2
    # Fração não regride; o detalhe pode atualizar (última mensagem útil).
    assert snap["detail"] == "nao regride"

    api = app_mod.Api()
    data = api.get_logs(0)
    assert data["progress"] is not None
    assert data["progress"]["fraction"] == 0.2

    app_mod.set_op_progress(1.0, "fim")
    app_mod.end_op_progress()
    assert app_mod.get_op_progress_snapshot() is None
    assert api.get_logs(0)["progress"] is None


def test_op_sink_logs_and_progress():
    app_mod.end_op_progress()
    app_mod.begin_op_progress()
    before = app_mod._LOG_SEQ
    app_mod.op_sink("mensagem de teste")
    app_mod.op_sink.progress(0.4, "40%")
    assert app_mod._LOG_SEQ > before
    snap = app_mod.get_op_progress_snapshot()
    assert snap["fraction"] == 0.4
    assert "40%" in snap["detail"]
    app_mod.end_op_progress()
