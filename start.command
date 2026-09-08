#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "================================================"
echo "  Iniciando Route 1 Kit (desktop)..."
echo "================================================"

if [ ! -x "$DIR/.venv/bin/python" ]; then
  echo "Criando ambiente virtual e instalando dependências..."
  python3 -m venv "$DIR/.venv"
fi

PYTHON="$DIR/.venv/bin/python"
"$PYTHON" -m pip install --upgrade "pip>=26.2"
if [ -f "$DIR/requirements.lock.txt" ]; then
  "$PYTHON" -m pip install --require-hashes -r "$DIR/requirements.lock.txt"
else
  "$PYTHON" -m pip install -r "$DIR/requirements.txt"
fi

"$PYTHON" app.py
