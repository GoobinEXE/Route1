#!/usr/bin/env bash
# Empacota Route 1 Kit no Linux: tar.gz portátil (onedir).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VERSION="$(python -c "from core import __version__; print(__version__)")"
ARCH="$(uname -m)"
OUT="${ROOT}/release_artifacts"
DIST="${ROOT}/dist"
BUILD="${ROOT}/build"

rm -rf "$OUT" "$DIST" "$BUILD"
mkdir -p "$OUT"

echo "==> PyInstaller (Route 1 Kit ${VERSION}, ${ARCH})"
python -m PyInstaller \
  --noconfirm \
  --clean \
  --distpath "$DIST" \
  --workpath "$BUILD" \
  packaging/Route1Kit.spec

PORTABLE="${OUT}/Route-1-Kit-${VERSION}-linux-${ARCH}-portable.tar.gz"
echo "==> Portátil: ${PORTABLE}"
tar -C "$DIST" -czf "$PORTABLE" Route1Kit

# “Instalável” Linux v1: o mesmo onedir com script de atalho simples empacotado.
INSTALL_DIR="${OUT}/Route1Kit-install"
rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cp -a "${DIST}/Route1Kit/." "$INSTALL_DIR/"
cat > "$INSTALL_DIR/install-desktop-entry.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$DESKTOP"
cat > "${DESKTOP}/route1kit.desktop" <<INNER
[Desktop Entry]
Type=Application
Name=Route 1 Kit
Comment=Preparar cartões SD para Nintendo DSi
Exec=${APP_DIR}/Route1Kit
Icon=${APP_DIR}/_internal/static/assets/app-icon-256.png
Terminal=false
Categories=Utility;
INNER
echo "Atalho criado em ${DESKTOP}/route1kit.desktop"
EOF
chmod +x "$INSTALL_DIR/install-desktop-entry.sh" "$INSTALL_DIR/Route1Kit" || true

INSTALL_TGZ="${OUT}/Route-1-Kit-${VERSION}-linux-${ARCH}-installer.tar.gz"
tar -C "$OUT" -czf "$INSTALL_TGZ" Route1Kit-install
rm -rf "$INSTALL_DIR"

echo
echo "Artefactos em ${OUT}:"
ls -lh "$OUT"
