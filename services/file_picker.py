"""Diálogos nativos de ficheiro/pasta via pywebview (FileDialog)."""

from __future__ import annotations

import re
from typing import List, Optional, Sequence, Tuple

import webview

from core.privacy import redact_path

# "ROMs (*.nds *.dsi)" / "ROMs (*.nds;*.dsi)" → "ROMs (*.nds;*.dsi)"
_FILTER_RE = re.compile(r"^(.+?)\s*\((.+)\)\s*$")


def qt_filters_to_webview(filters: Sequence[str]) -> Tuple[str, ...]:
    """Converte filtros estilo Qt para o formato pywebview (extensões com ';')."""
    out: List[str] = []
    for raw in filters:
        if not isinstance(raw, str) or not raw.strip():
            continue
        m = _FILTER_RE.match(raw.strip())
        if not m:
            out.append(raw.strip())
            continue
        label, body = m.group(1).strip(), m.group(2).strip()
        parts = [p.strip() for p in re.split(r"[;\s]+", body) if p.strip()]
        if not parts:
            out.append(raw.strip())
            continue
        out.append(f"{label} ({';'.join(parts)})")
    if not out:
        return ("Todos os ficheiros (*.*)",)
    return tuple(out)


class FilePickerPort:
    """Porta injectável na Api para escolha de ficheiros no host (pywebview)."""

    def __init__(self, window: Optional[object] = None):
        self._window = window

    def set_window(self, window: Optional[object]) -> None:
        self._window = window

    def set_parent(self, _parent: Optional[object] = None) -> None:
        """Compatibilidade com o contrato antigo (Qt); no-op em pywebview."""
        return None

    def _resolve_window(self):
        if self._window is not None:
            return self._window
        windows = getattr(webview, "windows", None) or []
        if windows:
            return windows[0]
        return None

    def open_files(
        self,
        *,
        caption: str = "Abrir",
        filters: Sequence[str] = (),
        multiple: bool = False,
    ) -> Tuple[bool, List[str]]:
        """
        Retorna (cancelled, paths_absolutos).
        filters: lista de padrões Qt ou pywebview, ex. \"ROMs (*.nds *.dsi)\".
        """
        win = self._resolve_window()
        if win is None:
            return True, []
        file_types = qt_filters_to_webview(filters)
        # caption não é suportado pela API pywebview; file_types carrega a descrição.
        _ = caption
        try:
            result = win.create_file_dialog(
                webview.FileDialog.OPEN,
                allow_multiple=bool(multiple),
                file_types=file_types,
            )
        except Exception:
            return True, []
        if not result:
            return True, []
        cleaned = [str(p) for p in result if isinstance(p, str) and p.strip()]
        if not cleaned:
            return True, []
        return False, cleaned

    def open_folder(self, *, caption: str = "Escolher pasta") -> Tuple[bool, str]:
        win = self._resolve_window()
        if win is None:
            return True, ""
        _ = caption
        try:
            result = win.create_file_dialog(webview.FileDialog.FOLDER)
        except Exception:
            return True, ""
        if not result:
            return True, ""
        # pywebview pode devolver str ou sequência
        if isinstance(result, str):
            path = result.strip()
        else:
            path = ""
            for item in result:
                if isinstance(item, str) and item.strip():
                    path = item.strip()
                    break
        if not path:
            return True, ""
        return False, path

    @staticmethod
    def redact_paths(paths: Sequence[str]) -> List[str]:
        return [redact_path(p) for p in paths if isinstance(p, str) and p.strip()]

    @staticmethod
    def redact_one(path: str) -> str:
        return redact_path(path) if path else ""
