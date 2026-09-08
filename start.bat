@echo off
cd /d "%~dp0"
echo ================================================
echo   Iniciando Route 1 Kit (desktop)...
echo ================================================

if not exist ".venv\Scripts\python.exe" (
  echo Criando ambiente virtual e instalando dependencias...
  python -m venv .venv
)

set PYTHON=.venv\Scripts\python.exe
"%PYTHON%" -m pip install --upgrade "pip>=26.2"
if exist "requirements.lock.txt" (
  "%PYTHON%" -m pip install --require-hashes -r requirements.lock.txt
) else (
  "%PYTHON%" -m pip install -r requirements.txt
)

"%PYTHON%" app.py
pause
