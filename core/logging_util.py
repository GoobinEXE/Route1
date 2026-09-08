"""Helpers de log compartilhados pelos módulos core/."""

from core.privacy import redact_text


def emit_log(log_callback, msg):
    """Imprime e, se houver callback, encaminha a mensagem para a UI (paths redigidos)."""
    safe = redact_text(msg)
    if log_callback:
        log_callback(safe)
    print(safe)
