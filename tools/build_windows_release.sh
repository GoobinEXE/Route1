#!/usr/bin/env bash
# Empacota Route 1 Kit no Windows (Git Bash / CI): ZIP portátil + Setup (Inno).
#
# Fases (ROUTE1KIT_WIN_PHASE):
#   all     — PyInstaller + assinatura opcional + ZIP + Inno (predefinição)
#   build   — só PyInstaller → dist/Route1Kit/
#   package — ZIP + Inno a partir de dist/Route1Kit/ já existente
#
# Assinatura local (opcional, fase all/package):
#   WINDOWS_PFX_PATH / WINDOWS_PFX_PASSWORD — SignTool com certificado .pfx
#   Ou WINDOWS_SIGNTOOL_CMD — comando completo; "$1" / {} = ficheiro a assinar
# Ver docs/WINDOWS_SIGNING.md (Azure Artifact Signing no CI).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PHASE="${ROUTE1KIT_WIN_PHASE:-all}"
VERSION="$(python -c "from core import __version__; print(__version__)")"
OUT="${ROOT}/release_artifacts"
DIST="${ROOT}/dist"
BUILD="${ROOT}/build"
APP_DIR="${DIST}/Route1Kit"
TIMESTAMP_URL="${WINDOWS_TIMESTAMP_URL:-http://timestamp.digicert.com}"

find_iscc() {
  local candidate
  for candidate in \
    "/c/Program Files (x86)/Inno Setup 6/ISCC.exe" \
    "/c/Program Files/Inno Setup 6/ISCC.exe"
  do
    if [[ -f "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  if command -v iscc >/dev/null 2>&1; then
    command -v iscc
    return 0
  fi
  return 1
}

find_signtool() {
  local candidate
  # Preferir o Windows SDK mais recente se existir.
  shopt -s nullglob
  local kits=(/c/Program\ Files\ \(x86\)/Windows\ Kits/10/bin/*/x64/signtool.exe)
  shopt -u nullglob
  if ((${#kits[@]})); then
    # Ordenação lexicográfica ≈ versão do kit.
    printf '%s\n' "${kits[@]}" | sort -V | tail -n1
    return 0
  fi
  if command -v signtool.exe >/dev/null 2>&1; then
    command -v signtool.exe
    return 0
  fi
  if command -v signtool >/dev/null 2>&1; then
    command -v signtool
    return 0
  fi
  return 1
}

sign_one() {
  local target="$1"
  if [[ -n "${WINDOWS_SIGNTOOL_CMD:-}" ]]; then
    # shellcheck disable=SC2086
    eval "${WINDOWS_SIGNTOOL_CMD}" "\"${target}\""
    return
  fi
  local signtool
  signtool="$(find_signtool)" || {
    echo "SignTool não encontrado (instale o Windows SDK)." >&2
    return 1
  }
  if [[ -z "${WINDOWS_PFX_PATH:-}" ]]; then
    echo "WINDOWS_PFX_PATH (ou WINDOWS_SIGNTOOL_CMD) em falta." >&2
    return 1
  fi
  local args=(
    sign
    /fd SHA256
    /td SHA256
    /tr "${TIMESTAMP_URL}"
    /f "${WINDOWS_PFX_PATH}"
  )
  if [[ -n "${WINDOWS_PFX_PASSWORD:-}" ]]; then
    args+=(/p "${WINDOWS_PFX_PASSWORD}")
  fi
  args+=("${target}")
  "$signtool" "${args[@]}"
}

sign_tree() {
  local dir="$1"
  local f count=0
  echo "==> Assinatura Authenticode em ${dir}"
  while IFS= read -r -d '' f; do
    sign_one "$f"
    count=$((count + 1))
  done < <(find "$dir" -type f \( -iname '*.exe' -o -iname '*.dll' \) -print0)
  echo "    ${count} ficheiro(s) assinados."
}

want_local_sign() {
  [[ -n "${WINDOWS_PFX_PATH:-}" || -n "${WINDOWS_SIGNTOOL_CMD:-}" ]]
}

run_build() {
  rm -rf "$DIST" "$BUILD"
  mkdir -p "$DIST"
  echo "==> PyInstaller (Route 1 Kit ${VERSION})"
  python -m PyInstaller \
    --noconfirm \
    --clean \
    --distpath "$DIST" \
    --workpath "$BUILD" \
    packaging/Route1Kit.spec

  if [[ ! -d "$APP_DIR" ]]; then
    echo "Falha: ${APP_DIR} não foi gerado." >&2
    exit 1
  fi
}

run_package() {
  if [[ ! -d "$APP_DIR" ]]; then
    echo "Falha: ${APP_DIR} não existe — corra a fase build primeiro." >&2
    exit 1
  fi

  mkdir -p "$OUT"

  if want_local_sign; then
    sign_tree "$APP_DIR"
  fi

  local portable_zip="${OUT}/Route-1-Kit-${VERSION}-windows-x64-portable.zip"
  echo "==> Portátil: ${portable_zip}"
  rm -f "$portable_zip"
  if command -v powershell.exe >/dev/null 2>&1; then
    local dist_win out_win
    dist_win="$(cygpath -w "${APP_DIR}" 2>/dev/null || echo "${APP_DIR}")"
    out_win="$(cygpath -w "${portable_zip}" 2>/dev/null || echo "${portable_zip}")"
    powershell.exe -NoProfile -Command \
      "Compress-Archive -Path '${dist_win}' -DestinationPath '${out_win}' -Force"
  elif command -v zip >/dev/null 2>&1; then
    (cd "$DIST" && zip -r "$portable_zip" Route1Kit)
  else
    echo "Sem powershell nem zip para criar o arquivo portátil." >&2
    exit 1
  fi

  local iscc=""
  if iscc="$(find_iscc)"; then
    echo "==> Instalável (Inno Setup): ${iscc}"
    local iscc_args=("//DMyAppVersion=${VERSION}")
    if want_local_sign; then
      local signtool_path
      signtool_path="$(find_signtool)" || exit 1
      # Inno: $f = caminho do ficheiro; /Snome=comando
      local sign_def
      if [[ -n "${WINDOWS_SIGNTOOL_CMD:-}" ]]; then
        sign_def="${WINDOWS_SIGNTOOL_CMD} \$f"
      else
        sign_def="\"${signtool_path}\" sign /fd SHA256 /td SHA256 /tr ${TIMESTAMP_URL} /f \"${WINDOWS_PFX_PATH}\""
        if [[ -n "${WINDOWS_PFX_PASSWORD:-}" ]]; then
          sign_def+=" /p \"${WINDOWS_PFX_PASSWORD}\""
        fi
        sign_def+=" \$f"
      fi
      iscc_args+=("//DROUTE1_SIGN=1" "//Sroute1sign=${sign_def}")
    fi
    "$iscc" "${iscc_args[@]}" "packaging/windows/Route1Kit.iss"

    if want_local_sign; then
      local setup
      setup="${OUT}/Route-1-Kit-${VERSION}-windows-x64-setup.exe"
      if [[ -f "$setup" ]]; then
        # Reforço: assinar o setup mesmo se o SignTool do Inno falhar em silêncio.
        sign_one "$setup" || true
      fi
    fi
  else
    echo "Aviso: Inno Setup (ISCC) não encontrado — só o ZIP portátil foi gerado." >&2
  fi
}

case "$PHASE" in
  build)
    run_build
    ;;
  package)
    # Em CI o dist já vem da fase build; não apagar OUT se já existir artefactos parciais.
    run_package
    ;;
  all)
    rm -rf "$OUT"
    mkdir -p "$OUT"
    run_build
    run_package
    ;;
  *)
    echo "ROUTE1KIT_WIN_PHASE inválida: ${PHASE} (use all|build|package)" >&2
    exit 1
    ;;
esac

echo
echo "Artefactos em ${OUT}:"
if [[ -d "$OUT" ]]; then
  ls -lh "$OUT" || true
fi
