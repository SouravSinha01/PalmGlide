# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

mediapipe_data, mediapipe_binaries, mediapipe_hiddenimports = collect_all("mediapipe")

analysis = Analysis(
    ["palmglide.py"],
    pathex=[],
    binaries=mediapipe_binaries,
    datas=mediapipe_data + [("models/hand_landmarker.task", "models")],
    hiddenimports=mediapipe_hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="PalmGlide",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

bundle = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    name="PalmGlide",
)
