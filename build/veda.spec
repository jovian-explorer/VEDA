# -*- mode: python ; coding: utf-8 -*-
# VEDA: Visualization, Exploration, and Data Analysis
# PyInstaller packaging specification for standalone .exe software package
from pathlib import Path

block_cipher = None

a = Analysis(
    ['../backend/app.py'],
    pathex=['../backend'],
    binaries=[],
    datas=[
        ('../frontend', 'frontend'),
        ('../sampledata', 'sampledata'),
    ],
    hiddenimports=[
        # Scientific stack
        'numpy', 'scipy', 'scipy.signal', 'scipy.ndimage', 'scipy.interpolate',
        'matplotlib', 'matplotlib.backends.backend_agg', 'astropy', 'astropy.io.fits',
        'astropy.visualization', 'PIL', 'PIL.Image',
        # FastAPI / ASGI
        'fastapi', 'uvicorn', 'uvicorn.lifespan.on',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.logging',
        'starlette', 'starlette.routing', 'starlette.staticfiles',
        'anyio', 'anyio._backends._asyncio',
        # pywebview + pythonnet
        'webview',
        'webview.platforms.edgechromium',
        'webview.platforms.winforms',
        'webview.util',
        'webview.guilib',
        'clr',
        'clr_loader',
        'pythonnet',
        # VEDA modules
        'veda',
        'veda.config',
        'veda.core',
        'veda.core.models',
        'veda.core.registry',
        'veda.core.base_adapter',
        'veda.analysis',
        'veda.analysis.atmospheric',
        'veda.analysis.advanced_science',
        'veda.analysis.wave_and_stability',
        'veda.readers',
        'veda.readers.pds3_reader',
        'veda.readers.fits_reader',
        'veda.missions',
        'veda.missions.manager',
        'veda.missions.akatsuki_adapter',
        'veda.missions.new_horizons_adapter',
        'veda.missions.juno_adapter',
        'veda.missions.cassini_adapter',
        'veda.missions.vex_adapter',
        'veda.missions.maven_adapter',
        'veda.missions.bepicolombo_adapter',
        'veda.missions.galileo_adapter',
        'veda.missions.extended_adapters',
        'veda.missions.isro_adapters',
        'veda.pipeline',
        'veda.pipeline.archive_downloader',
        'veda.api',
        'veda.api.app',
        'veda.api.routes',
        # stdlib helpers
        'email.mime.multipart', 'email.mime.base', 'email.mime.text',
        'multipart',
    ],
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='VEDA',
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
    icon='veda.ico',
)
