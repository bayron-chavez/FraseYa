"""Arranque en consola para verificar la estructura antes de integrar ventanas."""
import argparse
from pathlib import Path
import sqlite3
from fraseya.aplicacion.arranque import preparar_aplicacion


def ejecutar(argv=None, ruta_predeterminada=None):
    parser = argparse.ArgumentParser(description='FraseYa: preparación del proyecto local')
    parser.add_argument('--bd', type=Path, default=ruta_predeterminada,
                        help='Ruta de la base de datos local')
    parser.add_argument('--ventana', action='store_true',
                        help='Abre la ventana principal de gestión de frases')
    args = parser.parse_args(argv)
    try:
        resultado = preparar_aplicacion(args.bd)
    except (OSError, sqlite3.Error, ValueError) as error:
        print(f'No se pudo iniciar FraseYa: {error}')
        return 1
    if args.ventana:
        from fraseya.presentacion.ventana_principal import abrir
        abrir(args.bd)
        return 0
    print('FraseYa inició correctamente.')
    print(f'Esquema SQLite: versión {resultado["version_esquema"]}.')
    print(f'Frases guardadas: {resultado["cantidad_frases"]}.')
    print('Estructura preparada. La interfaz de escritorio se integrará después.')
    return 0
