# -*- mode: python ; coding: utf-8 -*-

# No encryption - removed due to compatibility issues
block_cipher = None

# Get paddleocr dependencies 
from PyInstaller.utils.hooks import collect_all
paddleocr_datas, paddleocr_binaries, paddleocr_hiddenimports = collect_all('paddleocr')

a = Analysis(
    ['EDAPGui.py'],
    pathex=[],
    binaries=paddleocr_binaries,
    datas=[
        ('screen/edap.ico', 'screen'),
        ('screen/*.png', 'screen'),
        ('*.py', '.'),
    ] + paddleocr_datas,
    hiddenimports=['paddleocr', 'paddleocr.tools'] + paddleocr_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='EDAPGui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,  # Strip symbols to reduce false positives
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='screen/edap.ico',
    version='version.txt',  # Add version information
    uac_admin=False,  # Don't request admin privileges
    manifest='EDAPGui.manifest',  # Include manifest file
) 