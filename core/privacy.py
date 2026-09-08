"""Redação de caminhos com home do utilizador (PII em logs/UI)."""

from __future__ import annotations

import os
import re
import sys
from functools import lru_cache


@lru_cache(maxsize=1)
def _home_prefixes() -> tuple[str, ...]:
    """Prefixes absolutos do home (abspath + realpath), mais longos primeiro."""
    found: list[str] = []
    try:
        home = os.path.expanduser("~")
    except Exception:
        return ()
    if not home or home == "~":
        return ()
    for candidate in (home,):
        try:
            found.append(os.path.abspath(candidate))
        except OSError:
            pass
        try:
            found.append(os.path.realpath(candidate))
        except OSError:
            pass
    # Dedup case-sensitive; no Windows também variantes de barra.
    uniq: list[str] = []
    seen: set[str] = set()
    for p in found:
        key = p.rstrip("\\/")
        if sys.platform == "win32":
            key = key.lower()
        if key in seen or not p:
            continue
        seen.add(key)
        uniq.append(p.rstrip("\\/"))
    uniq.sort(key=len, reverse=True)
    return tuple(uniq)


def redact_path(path: str | None) -> str:
    """Substitui o prefixo do home por ~ (path único)."""
    if not path or not isinstance(path, str):
        return path or ""
    text = path
    for home in _home_prefixes():
        if sys.platform == "win32":
            if text.lower().startswith(home.lower()):
                rest = text[len(home) :]
                if not rest:
                    return "~"
                if rest[0] in "\\/":
                    return "~" + rest.replace("\\", "/")
                break
        else:
            if text == home or text.startswith(home + os.sep):
                rest = text[len(home) :]
                return "~" + rest if rest else "~"
            # Também /Users/x via realpath vs abspath já coberto por _home_prefixes
    return text


def redact_text(msg: object) -> str:
    """Redige ocorrências do home dentro de mensagens de log/erro."""
    text = str(msg)
    if not text:
        return text
    for home in _home_prefixes():
        if sys.platform == "win32":
            # Case-insensitive; normaliza barras no resultado
            pattern = re.compile(re.escape(home), re.IGNORECASE)
            text = pattern.sub("~", text)
            text = text.replace("~\\", "~/").replace("~/", "~/")
        else:
            text = text.replace(home, "~")
    return text


def expand_user_path(path: str) -> str:
    """Expande ~ só no início; paths absolutos ficam intactos."""
    if not isinstance(path, str):
        return ""
    cleaned = path.strip()
    if not cleaned:
        return ""
    if cleaned.startswith("~"):
        return os.path.expanduser(cleaned)
    return cleaned
