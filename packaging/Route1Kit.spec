# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — Route 1 Kit (onedir + .app no macOS)."""

import os
import sys

from PyInstaller.building.api import COLLECT, EXE, PYZ
from PyInstaller.building.osx import BUNDLE
from PyInstaller.building.build_main import Analysis
from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
STATIC = os.path.join(ROOT, "static")
ICON_ICNS = os.path.join(STATIC, "assets", "app-icon.icns")
ICON_ICO = os.path.join(STATIC, "assets", "app-icon.ico")

datas = [(STATIC, "static")]
binaries = []
hiddenimports = list(collect_submodules("core"))

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
    excludes=[],
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
    name="Route1Kit",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
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
    name="Route1Kit",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Route 1 Kit.app",
        icon=ICON_ICNS,
        bundle_identifier="com.route1kit.app",
        info_plist={
            "CFBundleName": "Route 1 Kit",
            "CFBundleDisplayName": "Route 1 Kit",
            "CFBundleShortVersionString": "1.0.0",
            "CFBundleVersion": "1.0.0",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
        },
    )
