"""Prueba de carga de la ventana principal con muchas frases.

Usa una base temporal (no toca datos/fraseya.db). Mide cuánto tarda en cargar
la lista y en filtrar con el buscador. Con --ventana la deja abierta para
probarla a mano.

    python scripts/prueba_carga.py            # solo mide
    python scripts/prueba_carga.py --ventana  # mide y abre la ventana
"""
import argparse
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from fraseya.aplicacion.gestion_frases import GestionFrases
from fraseya.infraestructura import RepositorioSQLite
from fraseya.presentacion.ventana_principal import VentanaPrincipal

TEMAS = ['Saludo', 'Despedida', 'Solicitud', 'Confirmación', 'Aviso', 'Reclamo', 'Plazo', 'Pago']


def poblar(gestion, propias, compartidas):
    categoria = gestion.categorias_propias()[0]['id']
    for i in range(propias):
        tema = TEMAS[i % len(TEMAS)]
        gestion.crear(f'{tema} {i}', f'p{i}', f'{tema} número {i} para {{nombre}}, caso {{orden}}.', categoria)
    gestion.repo.reemplazar_compartidas(1, 'admin', '2026-10-01', [
        {'nombre': 'Normativa', 'frases': [
            {'titulo': f'Norma {i}', 'abreviatura': f'n{i}', 'contenido': f'Texto regulado {i}, plazo {{dias}}.'}
            for i in range(compartidas)]}])


def medir(etiqueta, funcion):
    inicio = time.perf_counter()
    funcion()
    print(f'{etiqueta}: {(time.perf_counter() - inicio) * 1000:.0f} ms')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ventana', action='store_true')
    parser.add_argument('--frases', type=int, default=200)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as carpeta:
        with RepositorioSQLite(Path(carpeta) / 'prueba.db') as repo:
            gestion = GestionFrases(repo)
            mitad = args.frases // 2
            medir(f'Crear {args.frases} frases', lambda: poblar(gestion, mitad, args.frases - mitad))
            inicio = time.perf_counter()
            ventana = VentanaPrincipal(gestion)
            print(f'Abrir ventana con {args.frases} frases: {(time.perf_counter() - inicio) * 1000:.0f} ms')
            medir('Recargar la lista', ventana.refrescar)
            for texto in ('p1', 'norma', 'caso 150', 'zzz'):
                ventana.busqueda.delete(0, 'end')
                ventana.busqueda.insert(0, texto)
                medir(f'Buscar "{texto}"', ventana.refrescar)
            ventana.busqueda.delete(0, 'end')
            ventana.refrescar()
            if args.ventana:
                print('Ventana abierta con datos de prueba. Ciérrala para terminar.')
                ventana.mainloop()
            else:
                ventana.destroy()


if __name__ == '__main__':
    main()
