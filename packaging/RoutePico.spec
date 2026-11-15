# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — Route Pico (onedir + .app no macOS)."""

import os
import sys

from PyInstaller.building.api import COLLECT, EXE, PYZ
from PyInstaller.building.build_main import Analysis
from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
STATIC = os.path.join(ROOT, "static")
ICON_ICNS = os.path.join(STATIC, "assets", "app-icon.icns")
ICON_ICO = os.path.join(STATIC, "assets", "app-icon.ico")

# Versão única: core/__init__.py (o Info.plist e o instalador Windows leem daqui).
sys.path.insert(0, ROOT)
from core import __version__ as APP_VERSION  # noqa: E402

# Assinatura macOS (tools/build_macos_release.sh). Vazio = assinatura ad-hoc local.
# Com identidade "Developer ID Application", o PyInstaller assina cada binário de
# dentro para fora com hardened runtime + timestamp, como a notarização exige.
MAC_SIGN_IDENTITY = os.environ.get("ROUTE_PICO_CODESIGN_IDENTITY") or None
MAC_ENTITLEMENTS = (
    os.path.join(ROOT, "packaging", "macos", "entitlements.plist") if MAC_SIGN_IDENTITY else None
)

datas = [
    (STATIC, "static"),
    (os.path.join(ROOT, "CHANGELOG.md"), "."),
    # Manifesto de hashes Pico Loader/Launcher usado pelo RouteDex (offline).
    (os.path.join(ROOT, "core", "data"), os.path.join("core", "data")),
    # Licença do Route Pico e avisos de terceiros vão junto com o binário.
    (os.path.join(ROOT, "LICENSE"), "."),
    (os.path.join(ROOT, "docs", "licenses"), os.path.join("docs", "licenses")),
    # O pacote GEi (kernel/MoonShell) é software de terceiros sem licença de
    # redistribuição: NÃO entra no app; o usuário baixa o oficial (Downloads).
]
binaries = []
hiddenimports = list(collect_submodules("core")) + list(collect_submodules("services"))

for pkg in ("webview", "py7zr"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

block_cipher = None

a = Analysis(
    [os.path.join(ROOT, "app.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PySide6", "shiboken6", "PySide6.QtWebEngine", "PySide6.QtWebEngineCore"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RoutePico",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=MAC_SIGN_IDENTITY if sys.platform == "darwin" else None,
    entitlements_file=MAC_ENTITLEMENTS if sys.platform == "darwin" else None,
    icon=ICON_ICO if sys.platform.startswith("win") else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="RoutePico",
)

if sys.platform == "darwin":
    from PyInstaller.building.osx import BUNDLE

    app = BUNDLE(
        coll,
        name="Route Pico.app",
        icon=ICON_ICNS,
        # Identificador mantido de Route 1 Kit: macOS trata como a mesma app (permissões, Dock).
        bundle_identifier="com.route1kit.app",
        info_plist={
            "CFBundleName": "Route Pico",
            "CFBundleDisplayName": "Route Pico",
            "CFBundleShortVersionString": APP_VERSION,
            "CFBundleVersion": APP_VERSION,
            "NSHumanReadableCopyright": "GPL-3.0 · Route Pico",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
        },
    )
