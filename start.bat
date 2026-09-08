@echo off
cd /d "%~dp0"
echo ================================================
echo   Iniciando DSi SD Studio (desktop)...
echo ================================================

set PYTHON=python
if exist ".venv\Scripts\python.exe" (
  set PYTHON=.venv\Scripts\python.exe
) else (
  python -c "import webview" 2>nul
  if errorlevel 1 (
    echo Criando ambiente virtual e instalando pywebview...
    python -m venv .venv
    .venv\Scripts\pip install -r requirements.txt
    set PYTHON=.venv\Scripts\python.exe
  )
)

"%PYTHON%" app.py
pause
