from PyInstaller.utils.hooks import collect_data_files

datos = [('docs/LICENCIAS_QT.md', 'licencias'), ('licenses/LGPL-3.0.txt', 'licencias'), ('licenses/GPL-3.0.txt', 'licencias')]
datos += [('src/fraseya/infraestructura/schema.sql', 'fraseya/infraestructura')]
datos += [('assets/logo.png', 'assets'), ('assets/fraseya.ico', 'assets')]
a = Analysis(['main.py'], pathex=['src'], binaries=[], datas=datos,
    hiddenimports=['defusedxml'],
    excludes=['pytest', 'coverage', 'pip', 'lxml', 'matplotlib', 'numpy', 'pandas', 'tkinter', 'customtkinter', 'pystray',
              'PySide6.QtWebEngineCore','PySide6.QtWebEngineWidgets','PySide6.QtWebEngineQuick',
              'PySide6.QtPdf','PySide6.QtPdfWidgets','PySide6.QtQml','PySide6.QtQuick',
              'PySide6.QtQuickWidgets'], noarchive=False)
# Qt utiliza el ICU de Windows. Un ICU de Poppler encontrado en PATH tiene
# símbolos distintos y rompe el arranque; no incorporar DLL de otras herramientas.
a.binaries = [b for b in a.binaries if b[0].lower() not in ('icuuc.dll', 'icudt78.dll')]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='FraseYa', debug=False,
    bootloader_ignore_signals=False, strip=False, upx=False, console=False, icon='assets/fraseya.ico')
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='FraseYa')
