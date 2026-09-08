#!/usr/bin/env bash
# Empacota Route 1 Kit no Windows (Git Bash / CI): ZIP portátil + Setup (Inno).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VERSION="$(python -c "from core import __version__; print(__version__)")"
OUT="${ROOT}/release_artifacts"
DIST="${ROOT}/dist"
BUILD="${ROOT}/build"

rm -rf "$OUT" "$DIST" "$BUILD"
mkdir -p "$OUT"

echo "==> PyInstaller (Route 1 Kit ${VERSION})"
python -m PyInstaller \
  --noconfirm \
  --clean \
  --distpath "$DIST" \
  --workpath "$BUILD" \
  packaging/Route1Kit.spec

PORTABLE_ZIP="${OUT}/Route-1-Kit-${VERSION}-windows-x64-portable.zip"
echo "==> Portátil: ${PORTABLE_ZIP}"
# Preferir PowerShell Compress-Archive no CI Windows.
if command -v powershell.exe >/dev/null 2>&1; then
  powershell.exe -NoProfile -Command \
    "Compress-Archive -Path '${DIST}/Route1Kit' -DestinationPath '${PORTABLE_ZIP}' -Force"
else
  (cd "$DIST" && zip -r "$PORTABLE_ZIP" Route1Kit)
fi

ISCC=""
for candidate in \
  "/c/Program Files (x86)/Inno Setup 6/ISCC.exe" \
  "/c/Program Files/Inno Setup 6/ISCC.exe" \
  "C:/Program Files (x86)/Inno Setup 6/ISCC.exe" \
  "C:/Program Files/Inno Setup 6/ISCC.exe"
do
  if [[ -x "$candidate" ]] || [[ -f "$candidate" ]]; then
    ISCC="$candidate"
    break
  fi
done

if [[ -n "$ISCC" ]]; then
  echo "==> Instalável (Inno Setup): ${ISCC}"
  "$ISCC" "//DMyAppVersion=${VERSION}" packaging/windows/Route1Kit.iss
  mv -f "${OUT}/Route-1-Kit-${VERSION}-windows-x64-setup.exe" "$OUT/" 2>/dev/null || true
else
  echo "Aviso: Inno Setup (ISCC) não encontrado — só o ZIP portátil foi gerado." >&2
fi

echo
echo "Artefactos em ${OUT}:"
ls -lh "$OUT"
