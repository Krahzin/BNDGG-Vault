# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['password_manager.py'],
    pathex=[],
    binaries=[],
    datas=[('bndgg.ico', '.')],
    hiddenimports=[
        'argon2',
        'argon2.low_level',
        '_argon2_cffi_bindings',
        'cryptography',
        'cryptography.fernet',
        'cryptography.hazmat.backends.openssl',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'PIL', 'pandas'],
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
    icon=['bndgg.ico'],
)
