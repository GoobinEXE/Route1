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

if [[ ! -d "${DIST}/Route1Kit" ]]; then
  echo "Falha: ${DIST}/Route1Kit não foi gerado." >&2
  exit 1
fi

PORTABLE_ZIP="${OUT}/Route-1-Kit-${VERSION}-windows-x64-portable.zip"
echo "==> Portátil: ${PORTABLE_ZIP}"
# Preferir PowerShell Compress-Archive no CI Windows (caminhos nativos).
if command -v powershell.exe >/dev/null 2>&1; then
  DIST_WIN="$(cygpath -w "${DIST}/Route1Kit" 2>/dev/null || echo "${DIST}/Route1Kit")"
  OUT_WIN="$(cygpath -w "${PORTABLE_ZIP}" 2>/dev/null || echo "${PORTABLE_ZIP}")"
  powershell.exe -NoProfile -Command \
    "Compress-Archive -Path '${DIST_WIN}' -DestinationPath '${OUT_WIN}' -Force"
elif command -v zip >/dev/null 2>&1; then
  (cd "$DIST" && zip -r "$PORTABLE_ZIP" Route1Kit)
else
  echo "Sem powershell nem zip para criar o arquivo portátil." >&2
  exit 1
fi

ISCC=""
for candidate in \
  "/c/Program Files (x86)/Inno Setup 6/ISCC.exe" \
  "/c/Program Files/Inno Setup 6/ISCC.exe"
do
  if [[ -f "$candidate" ]]; then
    ISCC="$candidate"
    break
  fi
done

if [[ -z "$ISCC" ]] && command -v iscc >/dev/null 2>&1; then
  ISCC="$(command -v iscc)"
fi

if [[ -n "$ISCC" ]]; then
  echo "==> Instalável (Inno Setup): ${ISCC}"
  # Git Bash: passar flags Windows com //
  "$ISCC" "//DMyAppVersion=${VERSION}" "packaging/windows/Route1Kit.iss"
else
  echo "Aviso: Inno Setup (ISCC) não encontrado — só o ZIP portátil foi gerado." >&2
fi

echo
echo "Artefactos em ${OUT}:"
ls -lh "$OUT"
