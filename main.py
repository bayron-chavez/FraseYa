"""Punto de entrada de FraseYa. Abre la ventana y la expansión por abreviatura. --sin-teclado la desactiva; --consola solo verifica el arranque."""
import sys
from pathlib import Path

PROYECTO = Path(__file__).resolve().parent
sys.path.insert(0, str(PROYECTO / 'src'))

from fraseya.presentacion.consola import ejecutar

RUTA_BD = PROYECTO / 'datos' / 'fraseya.db'

if __name__ == '__main__':
    if '--consola' in sys.argv:
        sys.argv.remove('--consola')
        raise SystemExit(ejecutar(ruta_predeterminada=RUTA_BD))
    from fraseya.presentacion.ventana_principal import abrir
    from fraseya.infraestructura.supabase import ErrorSupabase
    try:
        abrir(RUTA_BD, con_teclado='--sin-teclado' not in sys.argv)
    except ErrorSupabase as error:
        print(str(error))
        raise SystemExit(1) from None
