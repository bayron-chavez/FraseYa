"""Punto de entrada de FraseYa. Abre la ventana y la expansión por abreviatura. --sin-teclado la desactiva; --consola solo verifica el arranque."""
import sys
from pathlib import Path

PROYECTO = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
sys.path.insert(0, str(PROYECTO / 'src'))

from fraseya.presentacion.consola import ejecutar

RUTA_BD = PROYECTO / 'datos' / 'fraseya.db'

if __name__ == '__main__':
    if '--diagnostico' in sys.argv:
        from fraseya.infraestructura import RepositorioSQLite
        from fraseya.presentacion.bandeja import Bandeja
        from fraseya.aplicacion.importacion_excel import importar_excel
        with RepositorioSQLite(':memory:') as repo:
            assert repo.db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        raise SystemExit(0)
    if '--consola' in sys.argv:
        sys.argv.remove('--consola')
        raise SystemExit(ejecutar(ruta_predeterminada=RUTA_BD))
    from fraseya.presentacion.ventana_principal import abrir
    from fraseya.infraestructura.supabase import ErrorSupabase
    try:
        if not (PROYECTO / 'datos' / 'supabase.json').exists() or '--configurar' in sys.argv:
            from fraseya.presentacion.configuracion_supabase import configurar_supabase
            if not configurar_supabase(PROYECTO / 'datos' / 'supabase.json'):
                raise SystemExit(0)
        abrir(RUTA_BD, con_teclado='--sin-teclado' not in sys.argv)
    except ErrorSupabase as error:
        import tkinter as tk
        from tkinter import messagebox
        raiz = tk.Tk()
        raiz.withdraw()
        messagebox.showerror('FraseYa', str(error), parent=raiz)
        raiz.destroy()
        raise SystemExit(1) from None
