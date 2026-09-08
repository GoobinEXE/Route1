#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "================================================"
echo "  Iniciando DSi SD Studio (desktop)..."
echo "================================================"

PYTHON="python3"
if [ -x "$DIR/.venv/bin/python" ]; then
  PYTHON="$DIR/.venv/bin/python"
elif ! python3 -c "import webview" 2>/dev/null; then
  echo "Criando ambiente virtual e instalando pywebview..."
  python3 -m venv "$DIR/.venv"
  "$DIR/.venv/bin/pip" install -r "$DIR/requirements.txt"
  PYTHON="$DIR/.venv/bin/python"
fi

"$PYTHON" app.py
