# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build for PS4 Theme Tools.

Build from the repository root:

    pyinstaller --noconfirm PS4ThemeTools.spec

The result is a self-contained folder in dist/PS4ThemeTools.  Downloaded
dependencies (FFmpeg, PkgTool, at9tool) are intentionally not bundled: the app
fetches and verifies them on demand into %LOCALAPPDATA%\\PS4ThemeTools\\tools.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

ROOT = Path(SPECPATH)

datas = collect_data_files("customtkinter")
datas += [
    (str(ROOT / "assets" / "app_icon.ico"), "assets"),
    (str(ROOT / "assets" / "app_icon.png"), "assets"),
    (str(ROOT / "assets" / "logo.png"), "assets"),
]

a = Analysis(
    ["app.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=["PIL._tkinter_finder"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "setuptools", "pip"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PS4ThemeTools",
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
    icon=str(ROOT / "assets" / "app_icon.ico"),
    version=str(ROOT / "packaging" / "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="PS4ThemeTools",
)
