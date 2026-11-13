#!/usr/bin/env bash
# Empacota Route Pico no Linux: tar.gz portátil (onedir).
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

echo "==> PyInstaller (Route Pico ${VERSION}, ${ARCH})"
python -m PyInstaller \
  --noconfirm \
  --clean \
  --distpath "$DIST" \
  --workpath "$BUILD" \
  packaging/RoutePico.spec

PORTABLE="${OUT}/Route-Pico-${VERSION}-linux-${ARCH}-portable.tar.gz"
echo "==> Portátil: ${PORTABLE}"
tar -C "$DIST" -czf "$PORTABLE" RoutePico

# “Instalável” Linux v1: o mesmo onedir com script de atalho simples empacotado.
INSTALL_DIR="${OUT}/RoutePico-install"
rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cp -a "${DIST}/RoutePico/." "$INSTALL_DIR/"
cat > "$INSTALL_DIR/install-desktop-entry.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$DESKTOP"
cat > "${DESKTOP}/route1kit.desktop" <<INNER
[Desktop Entry]
Type=Application
Name=Route Pico
Comment=Preparar cartões SD para Nintendo DSi
Exec=${APP_DIR}/RoutePico
Icon=${APP_DIR}/_internal/static/assets/app-icon-256.png
Terminal=false
Categories=Utility;
INNER
echo "Atalho criado em ${DESKTOP}/route1kit.desktop"
EOF
chmod +x "$INSTALL_DIR/install-desktop-entry.sh" "$INSTALL_DIR/RoutePico" || true

INSTALL_TGZ="${OUT}/Route-Pico-${VERSION}-linux-${ARCH}-installer.tar.gz"
tar -C "$OUT" -czf "$INSTALL_TGZ" RoutePico-install
rm -rf "$INSTALL_DIR"

echo
echo "Artefactos em ${OUT}:"
ls -lh "$OUT"
