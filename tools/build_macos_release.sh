#!/usr/bin/env bash
# Empacota Route Pico no macOS: ZIP portátil (.app) + DMG instalável.
#
# Assinatura e notarização (docs/MACOS_SIGNING.md):
#   - Identidade: ROUTE_PICO_CODESIGN_IDENTITY, ou a primeira
#     "Developer ID Application" encontrada no Keychain.
#   - Notarização: ROUTE_PICO_NOTARY_PROFILE (perfil do `xcrun notarytool
#     store-credentials`, padrão "RoutePico"), ou a chave de API do App Store
#     Connect em ROUTE_PICO_NOTARY_KEY / _KEY_ID / _ISSUER (usado no CI).
#   - ROUTE_PICO_REQUIRE_SIGNING=1 faz o build falhar se não puder assinar e
#     notarizar (use para uma release pública).
#   - ROUTE_PICO_ALLOW_DEV_IDENTITY=1 aceita uma identidade "Apple Development"
#     só para testar o hardened runtime localmente (não notariza).
# Sem identidade, o app sai com assinatura ad-hoc, como antes.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VERSION="$(python -c "from core import __version__; print(__version__)")"
ARCH="$(uname -m)"
OUT="${ROOT}/release_artifacts"
DIST="${ROOT}/dist"
BUILD="${ROOT}/build"
APP="${DIST}/Route Pico.app"
STAGE="${OUT}/dmg_stage"
ENTITLEMENTS="${ROOT}/packaging/macos/entitlements.plist"
REQUIRE_SIGNING="${ROUTE_PICO_REQUIRE_SIGNING:-0}"
NOTARY_PROFILE="${ROUTE_PICO_NOTARY_PROFILE:-RoutePico}"

fail() {
  echo "Erro: $*" >&2
  exit 1
}

# --------------------------------------------------------------- identidade
IDENTITY="${ROUTE_PICO_CODESIGN_IDENTITY:-}"
if [[ -z "$IDENTITY" ]]; then
  # Nome completo da identidade (o hash não é necessário para o codesign).
  IDENTITY="$(security find-identity -v -p codesigning 2>/dev/null \
    | sed -n 's/.*"\(Developer ID Application: [^"]*\)".*/\1/p' | head -n 1 || true)"
fi

SIGN_MODE="adhoc"
if [[ -n "$IDENTITY" ]]; then
  case "$IDENTITY" in
    "Developer ID Application:"*) SIGN_MODE="developer-id" ;;
    "Apple Development:"*)
      [[ "${ROUTE_PICO_ALLOW_DEV_IDENTITY:-0}" == "1" ]] \
        || fail "\"Apple Development\" não serve para distribuir fora da App Store. Crie um certificado Developer ID Application (docs/MACOS_SIGNING.md)."
      SIGN_MODE="development"
      ;;
    *) fail "Identidade não suportada para distribuição: ${IDENTITY}. Use uma \"Developer ID Application\"." ;;
  esac
fi

if [[ "$REQUIRE_SIGNING" == "1" && "$SIGN_MODE" != "developer-id" ]]; then
  fail "ROUTE_PICO_REQUIRE_SIGNING=1, mas não há certificado Developer ID Application no Keychain."
fi

# ------------------------------------------------------------- notarização
NOTARY_ARGS=()
if [[ "$SIGN_MODE" == "developer-id" ]]; then
  if [[ -n "${ROUTE_PICO_NOTARY_KEY:-}" && -n "${ROUTE_PICO_NOTARY_KEY_ID:-}" && -n "${ROUTE_PICO_NOTARY_ISSUER:-}" ]]; then
    NOTARY_ARGS=(--key "$ROUTE_PICO_NOTARY_KEY" --key-id "$ROUTE_PICO_NOTARY_KEY_ID" --issuer "$ROUTE_PICO_NOTARY_ISSUER")
  elif xcrun notarytool history --keychain-profile "$NOTARY_PROFILE" >/dev/null 2>&1; then
    NOTARY_ARGS=(--keychain-profile "$NOTARY_PROFILE")
  fi
fi
if [[ "$REQUIRE_SIGNING" == "1" && ${#NOTARY_ARGS[@]} -eq 0 ]]; then
  fail "Sem credenciais de notarização (perfil \"${NOTARY_PROFILE}\" ou chave de API). Veja docs/MACOS_SIGNING.md."
fi

notarize() {
  # $1 = arquivo (.zip ou .dmg) a enviar à Apple; espera o veredito.
  local file="$1" out status sub_id
  echo "==> Notarização: $(basename "$file") (pode levar alguns minutos)"
  out="$(xcrun notarytool submit "$file" "${NOTARY_ARGS[@]}" --wait --output-format json)" \
    || fail "notarytool falhou ao enviar $(basename "$file")."
  status="$(python -c 'import json,sys; print(json.loads(sys.argv[1]).get("status",""))' "$out")"
  sub_id="$(python -c 'import json,sys; print(json.loads(sys.argv[1]).get("id",""))' "$out")"
  if [[ "$status" != "Accepted" ]]; then
    echo "Notarização recusada (${status}). Relatório da Apple:" >&2
    xcrun notarytool log "$sub_id" "${NOTARY_ARGS[@]}" >&2 || true
    exit 1
  fi
  echo "    aceita (${sub_id})"
}

# ------------------------------------------------------------------- build
rm -rf "$OUT" "$DIST" "$BUILD"
mkdir -p "$OUT"

case "$SIGN_MODE" in
  developer-id) echo "==> Assinatura: ${IDENTITY}" ;;
  development) echo "==> Assinatura de TESTE (Apple Development; não notarizável): ${IDENTITY}" ;;
  *) echo "==> Sem certificado Developer ID: assinatura ad-hoc (o macOS vai pedir confirmação ao abrir)" ;;
esac

echo "==> Avisos de terceiros (licenças do que vai no app)"
python tools/gen_third_party_notices.py
echo "==> PyInstaller (Route Pico ${VERSION}, ${ARCH})"
if [[ "$SIGN_MODE" == "adhoc" ]]; then
  ROUTE_PICO_CODESIGN_IDENTITY="" python -m PyInstaller --noconfirm --clean \
    --distpath "$DIST" --workpath "$BUILD" packaging/RoutePico.spec
else
  ROUTE_PICO_CODESIGN_IDENTITY="$IDENTITY" python -m PyInstaller --noconfirm --clean \
    --distpath "$DIST" --workpath "$BUILD" packaging/RoutePico.spec
fi

[[ -d "$APP" ]] || fail "${APP} não foi gerado."

if [[ "$SIGN_MODE" != "adhoc" ]]; then
  echo "==> Verificando a assinatura"
  codesign --verify --deep --strict --verbose=2 "$APP"
  # Saída capturada antes do grep: com pipefail, `grep -q` fecha o pipe cedo e o
  # codesign morre com SIGPIPE, o que parecia uma falha de assinatura.
  ents="$(codesign -d --entitlements - "$APP" 2>/dev/null || true)"
  [[ "$ents" == *allow-unsigned-executable-memory* ]] \
    || fail "entitlements ausentes no executável principal (${ENTITLEMENTS})."
  info="$(codesign -dv "$APP" 2>&1 || true)"
  [[ "$info" =~ flags=0x[0-9a-f]*\(runtime\) ]] || fail "hardened runtime ausente."
fi

if [[ ${#NOTARY_ARGS[@]} -gt 0 ]]; then
  NOTARY_ZIP="${OUT}/notary-app.zip"
  ditto -c -k --sequesterRsrc --keepParent "$APP" "$NOTARY_ZIP"
  notarize "$NOTARY_ZIP"
  rm -f "$NOTARY_ZIP"
  xcrun stapler staple "$APP"
  xcrun stapler validate "$APP"
elif [[ "$SIGN_MODE" == "developer-id" ]]; then
  echo "Aviso: assinado, mas sem credenciais de notarização; o Gatekeeper ainda vai avisar." >&2
fi

# --------------------------------------------------------------- pacotes
PORTABLE_ZIP="${OUT}/Route-Pico-${VERSION}-macOS-${ARCH}-portable.zip"
echo "==> Portátil: ${PORTABLE_ZIP}"
ditto -c -k --sequesterRsrc --keepParent "$APP" "$PORTABLE_ZIP"

DMG="${OUT}/Route-Pico-${VERSION}-macOS-${ARCH}-installer.dmg"
echo "==> Instalável (DMG): ${DMG}"
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
rm -f "$DMG"
hdiutil create \
  -volname "Route Pico ${VERSION}" \
  -srcfolder "$STAGE" \
  -ov \
  -format UDZO \
  "$DMG"
rm -rf "$STAGE"

if [[ "$SIGN_MODE" != "adhoc" ]]; then
  codesign --force --sign "$IDENTITY" --timestamp "$DMG"
fi
if [[ ${#NOTARY_ARGS[@]} -gt 0 ]]; then
  notarize "$DMG"
  xcrun stapler staple "$DMG"
  echo "==> Gatekeeper"
  spctl -a -vvv -t exec "$APP"
  spctl -a -vvv -t open --context context:primary-signature "$DMG"
fi

echo
echo "Artefatos em ${OUT} (assinatura: ${SIGN_MODE}; notarizado: $([[ ${#NOTARY_ARGS[@]} -gt 0 ]] && echo sim || echo não)):"
ls -lh "$OUT"
