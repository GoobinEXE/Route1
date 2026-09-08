#!/usr/bin/env bash
# Empacota Route 1 Kit no macOS: ZIP portátil (.app) + DMG instalável.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VERSION="$(python -c "from core import __version__; print(__version__)")"
ARCH="$(uname -m)"
OUT="${ROOT}/release_artifacts"
DIST="${ROOT}/dist"
BUILD="${ROOT}/build"
APP="${DIST}/Route 1 Kit.app"
STAGE="${OUT}/dmg_stage"

rm -rf "$OUT" "$DIST" "$BUILD"
mkdir -p "$OUT"

echo "==> PyInstaller (Route 1 Kit ${VERSION}, ${ARCH})"
python -m PyInstaller \
  --noconfirm \
  --clean \
  --distpath "$DIST" \
  --workpath "$BUILD" \
  packaging/Route1Kit.spec

if [[ ! -d "$APP" ]]; then
  echo "Falha: ${APP} não foi gerado." >&2
  exit 1
fi

PORTABLE_ZIP="${OUT}/Route-1-Kit-${VERSION}-macOS-${ARCH}-portable.zip"
echo "==> Portátil: ${PORTABLE_ZIP}"
ditto -c -k --sequesterRsrc --keepParent "$APP" "$PORTABLE_ZIP"

DMG="${OUT}/Route-1-Kit-${VERSION}-macOS-${ARCH}-installer.dmg"
echo "==> Instalável (DMG): ${DMG}"
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
rm -f "$DMG"
hdiutil create \
  -volname "Route 1 Kit ${VERSION}" \
  -srcfolder "$STAGE" \
  -ov \
  -format UDZO \
  "$DMG"
rm -rf "$STAGE"

echo
echo "Artefactos em ${OUT}:"
ls -lh "$OUT"
