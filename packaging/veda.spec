# -*- mode: python ; coding: utf-8 -*-
# VEDA: Visualization, Exploration, and Data Analysis
# Cross-platform PyInstaller spec.  Build with:  python scripts/build_exe.py
#   Windows : dist/VEDA.exe        (single file)
#   Linux   : dist/VEDA            (single file)
#   macOS   : dist/VEDA.app        (application bundle)
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

HERE = Path(SPECPATH)
ROOT = HERE.parent
PKG = ROOT / "src" / "veda"
ICON = str(HERE / "veda.ico")

a = Analysis(
    [str(HERE / "veda_entry.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=[
        (str(PKG / "frontend"), "veda/frontend"),
        (str(PKG / "sampledata"), "veda/sampledata"),
    ],
    hiddenimports=(
        collect_submodules("veda")
        + collect_submodules("uvicorn")
        + [
            "scipy.signal", "scipy.ndimage", "scipy.interpolate",
            "matplotlib.backends.backend_agg",
            "astropy.io.fits", "astropy.visualization",
            "anyio._backends._asyncio",
            # imported lazily by veda.desktop; the pywebview hook adds the
            # platform backend (EdgeChromium/WinForms, Cocoa, GTK/Qt)
            "webview",
        ]
        + (["webview.platforms.edgechromium", "webview.platforms.winforms", "clr"]
           if sys.platform == "win32" else [])
    ),
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

if sys.platform == "darwin":
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name="VEDA",
        console=False,
        upx=False,
        icon=ICON,
    )
    coll = COLLECT(exe, a.binaries, a.datas, name="VEDA", upx=False)
    app = BUNDLE(
        coll,
        name="VEDA.app",
        icon=ICON,
        bundle_identifier="io.github.jovian-explorer.veda",
        info_plist={"NSHighResolutionCapable": True},
    )
else:
    # A folder build (VEDA/VEDA.exe + VEDA/_internal), not --onefile: a onefile
    # exe unpacks ~200 MB to a temp folder on every launch (and antivirus scans
    # it each time), which made start-up take a minute or more.
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name="VEDA",
        console=False,
        upx=False,
        icon=ICON if sys.platform == "win32" else None,
    )
    coll = COLLECT(exe, a.binaries, a.datas, name="VEDA", upx=False)
