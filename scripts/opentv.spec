# -*- mode: python ; coding: utf-8 -*-
# OpenTV PyInstaller Build Specification
# Milestone 5: Standalone Single-File Executables Distribution

import sys
from pathlib import Path

block_cipher = None
project_root = Path(r'/home/prem/Projects/OpenTV')
companion_dir = Path(r'/home/prem/Projects/OpenTV/companion')

a = Analysis(
    [r'/home/prem/Projects/OpenTV/companion/opentv/__main__.py'],
    pathex=[str(companion_dir)],
    binaries=[],
    datas=[],
    hiddenimports=[
        'opentv',
        'opentv.cli',
        'opentv.core',
        'opentv.core.adb',
        'opentv.core.app_names',
        'opentv.core.config',
        'opentv.core.deployer',
        'opentv.core.device',
        'opentv.core.discovery',
        'opentv.debloat',
        'opentv.debloat.audit',
        'opentv.debloat.database',
        'opentv.debloat.guardrails',
        'opentv.debloat.rollback',
        'opentv.profiles',
        'opentv.profiles.detector',
        'opentv.tui',
        'opentv.tui.app',
        'opentv.tui.fallback',
        'opentv.tui.terminal',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas', 'pytest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
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
    name='opentv',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
