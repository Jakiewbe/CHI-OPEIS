# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = []
hiddenimports += collect_submodules('chi_generator')


a = Analysis(
    ['src\\chi_generator\\main.py'],
    pathex=['src'],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pytest',
        'tests',
        'test',
        'opeis_master',
        'opeis_master.app',
        'opeis_master.core',
        'opeis_master.domain',
        'opeis_master.gui',
        'opeis_master.main',
        'opeis_master.models',
        'opeis_master.renderers',
        'opeis_master.ui',
        'setuptools',
        'pip',
        'distutils',
        'wheel',
    ],
    noarchive=False,
    optimize=0,
)

# Prune non-essential PySide6 translation files.
# Keep only zh_CN, zh_TW, and en translations (~12 files instead of ~96).
_keep_translations = frozenset({
    'qt_zh_CN.qm', 'qt_zh_TW.qm', 'qt_en.qm',
    'qtbase_zh_CN.qm', 'qtbase_zh_TW.qm', 'qtbase_en.qm',
    'qt_help_zh_CN.qm', 'qt_help_zh_TW.qm', 'qt_help_en.qm',
})

from PyInstaller.building.datastruct import TOC
import os

_filtered_datas = TOC()
for item in a.datas:
    name = os.path.basename(item[0])
    if name.endswith('.qm') and 'PySide6' in item[0] and 'translations' in item[0]:
        if name not in _keep_translations:
            continue
    _filtered_datas.append(item)
a.datas = _filtered_datas

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CHI-OPEIS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CHI-OPEIS',
)
