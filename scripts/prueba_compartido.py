"""Comprueba RF-05 sin modificar SQLite ni la carpeta compartida."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from fraseya.infraestructura.repositorio_compartido import (
    RepositorioCompartido, CarpetaNoDisponible, CatalogoNoPublicado,
    FormatoInvalido, CatalogoEnTransicion)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('carpeta', nargs='?', help='Carpeta publicada; por defecto usa la configuración local.')
    parser.add_argument('--bd', default=str(Path(__file__).resolve().parents[1] / 'datos' / 'fraseya.db'))
    args = parser.parse_args()
    carpeta = args.carpeta
    if carpeta is None:
        # Solo consulta la preferencia; no crea ni inicializa la base.
        import sqlite3
        try:
            with sqlite3.connect(Path(args.bd).resolve().as_uri() + '?mode=ro', uri=True) as conexion:
                fila = conexion.execute("SELECT valor FROM CONFIGURACION WHERE clave = 'carpeta_compartida'").fetchone()
                carpeta = fila[0] if fila else ''
        except sqlite3.Error:
            print('No se pudo leer la configuración local; indica la carpeta como argumento.')
            return 1
    lector = RepositorioCompartido(carpeta)
    estado = lector.comprobar()
    print(f'{estado.estado}: {estado.mensaje}')
    if estado.estado != 'disponible':
        return 1
    try:
        version, _ = lector.leer()
    except (CarpetaNoDisponible, CatalogoNoPublicado, FormatoInvalido, CatalogoEnTransicion) as error:
        print(str(error))
        return 1
    print(f'Versión: {version.version} | Autor: {version.autor} | Frases: {version.cantidad_frases}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
