from PyInstaller.utils.hooks import collect_data_files

datos = collect_data_files('customtkinter')
datos += [('src/fraseya/infraestructura/schema.sql', 'fraseya/infraestructura')]
datos += [('assets/logo.png', 'assets'), ('assets/fraseya.ico', 'assets')]
a = Analysis(['main.py'], pathex=['src'], binaries=[], datas=datos,
    hiddenimports=['pystray._win32', 'PIL._tkinter_finder', 'defusedxml'],
    excludes=['pytest', 'coverage', 'pip', 'lxml', 'matplotlib', 'numpy', 'pandas'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='FraseYa', debug=False,
    bootloader_ignore_signals=False, strip=False, upx=False, console=False, icon='assets/fraseya.ico')
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='FraseYa')
