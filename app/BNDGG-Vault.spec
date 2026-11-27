# -*- mode: python ; coding: utf-8 -*-

import os

block_cipher = None

# Python 3.15 ships ABI3 extension modules that import python3t.dll; the
# forwarder lives in abi3t-compat and PyInstaller does not find it automatically.
compat_dll = r'C:\Python315\abi3t-compat\python3t.dll'
binaries = [(compat_dll, '.')] if os.path.isfile(compat_dll) else []

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=[('../project/bndgg.ico', '.')],
    hiddenimports=[
        'argon2',
        'argon2.low_level',
        '_argon2_cffi_bindings',
        'cryptography',
        'cryptography.hazmat.primitives.ciphers.aead',
        'PySide6.QtSvg',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'PIL',
        'pandas',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets',
        'PySide6.Qt3DCore',
        'PySide6.QtCharts',
        'PySide6.QtDataVisualization',
        'PySide6.QtMultimedia',
        'PySide6.QtQuick',
        'PySide6.QtQml',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='BNDGG-Vault',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['../project/bndgg.ico'],
)
