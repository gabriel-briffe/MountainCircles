# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# Manually list the files from src and utils directories
datas_files = [
    ('app_settings.py', '.'),
    ('launch.py', '.'),
    ('src/airfields.py', 'src'),
    ('src/convert_coordinates.py', 'src'),
    ('src/logging.py', 'src'),
    ('src/postprocess.py', 'src'),
    ('src/raster.py', 'src'),
    ('src/use_case_settings.py', 'src'),
    ('utils/cupConvert.py', 'utils'),
    ('utils/process_passes.py', 'utils'),
    ('utils/process_sectors.py', 'utils'),
    ('map.html', '.')
]

a = Analysis(
    ['gui.py'],  # Entry point is gui.py.
    pathex=['.'],  # Start looking for modules in the main folder.
    binaries=[('compute.exe', '.')],  # Include compute.exe from the main folder.
    datas=datas_files,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='MountainCirclesApp',  # Name of your application
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Set to False to avoid a console for a GUI app.
    icon = 'ressources/icon.icns'
)
