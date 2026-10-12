"""Preferências locais da app (prefs.json no directório de dados do utilizador)."""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Optional


def user_data_dir() -> str:
    """Pasta de dados do utilizador (prefs, etc.)."""
    if sys.platform == "darwin":
        root = os.path.expanduser("~/Library/Application Support/Route1Kit")
    elif sys.platform.startswith("win"):
        root = os.path.join(
            os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"),
            "Route1Kit",
        )
    else:
        root = os.path.join(
            os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"),
            "Route1Kit",
        )
    try:
        os.makedirs(root, exist_ok=True)
    except OSError:
        pass
    return root


def prefs_path() -> str:
    return os.path.join(user_data_dir(), "prefs.json")


def load_prefs() -> dict[str, Any]:
    path = prefs_path()
    try:
        if not os.path.isfile(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {}


def get_pref(key: str, default: Any = None) -> Any:
    if not isinstance(key, str) or not key:
        return default
    prefs = load_prefs()
    return prefs.get(key, default)


def sanitize_prefs(prefs: Any) -> dict[str, Any]:
    """Allowlist superficial — UI só grava chaves simples."""
    if not isinstance(prefs, dict):
        return {}
    clean: dict[str, Any] = {}
    for k, v in list(prefs.items())[:64]:
        if not isinstance(k, str) or len(k) > 64:
            continue
        if isinstance(v, (str, int, float, bool)) or v is None:
            if isinstance(v, str) and len(v) > 2048:
                continue
            clean[k] = v
    return clean


def save_prefs(prefs: Any) -> tuple[bool, Optional[str], dict[str, Any]]:
    """Grava prefs.json via .partial + os.replace. Devolve (ok, erro, clean)."""
    clean = sanitize_prefs(prefs)
    path = prefs_path()
    partial = path + ".partial"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(partial, "w", encoding="utf-8") as f:
            json.dump(clean, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(partial, path)
        return True, None, clean
    except OSError as e:
        try:
            if os.path.isfile(partial):
                os.remove(partial)
        except OSError:
            pass
        return False, str(e), clean
