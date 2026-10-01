"""Punto de entrada de FraseYa. Ejecutar desde cualquier carpeta."""
import sys
from pathlib import Path

PROYECTO = Path(__file__).resolve().parent
sys.path.insert(0, str(PROYECTO / 'src'))

from fraseya.presentacion.consola import ejecutar

if __name__ == '__main__':
    raise SystemExit(ejecutar(ruta_predeterminada=PROYECTO / 'datos' / 'fraseya.db'))
