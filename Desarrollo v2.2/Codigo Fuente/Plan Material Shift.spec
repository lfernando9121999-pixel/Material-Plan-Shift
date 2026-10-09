# -*- mode: python ; coding: utf-8 -*-
# Compilación: pyinstaller --noconfirm --clean "Plan Material Shift.spec"
a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=[("pms/assets", "pms/assets")],
    hiddenimports=[],
    excludes=["matplotlib", "pandas", "PIL", "IPython", "pytest", "setuptools", "pydoc_data",
              "tkinter.test", "lib2to3"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Plan Material Shift",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon="pms/assets/icono.ico",
    version="version_info.txt",
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Plan Material Shift")
