"""Crea automáticamente el esquema al arrancar, sin interfaz gráfica."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))
from fraseya import RepositorioSQLite

if __name__ == '__main__':
    ruta = sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent / 'datos' / 'fraseya.db'
    with RepositorioSQLite(ruta) as repo:
        print('Base SQLite preparada. Esquema versión 1, seis tablas.')
