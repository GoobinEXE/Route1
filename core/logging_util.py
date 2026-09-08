"""Helpers de log compartilhados pelos módulos core/."""


def emit_log(log_callback, msg):
    """Imprime e, se houver callback, encaminha a mensagem para a UI."""
    if log_callback:
        log_callback(msg)
    print(msg)
