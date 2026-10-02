"""Prueba manual de EscritorTexto en una ventana real.

Ejecútalo, y durante la cuenta regresiva haz clic en el campo donde quieras
que escriba (Bloc de notas, navegador, chat). No muevas el mouse después.

    python scripts/prueba_escritor.py                 # una frase con tildes, ñ, saltos y emoji
    python scripts/prueba_escritor.py --reemplazo     # escribe "hola" y lo reemplaza por la frase
    python scripts/prueba_escritor.py --cien          # 100 inserciones numeradas
    python scripts/prueba_escritor.py --velocidad 10  # entre 10 y 60 ms por carácter
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from fraseya.infraestructura.escritor_texto import EscritorTexto

FRASE = ('Buenos días, ¿cómo está? Soy Diego y le atiendo hoy.\n'
         'Año nuevo, ñandú, café, pingüino ✓ 😀\n'
         'Teléfono: 600 123 4567\tHorario: lunes a viernes')


def cuenta_regresiva(segundos):
    for s in range(segundos, 0, -1):
        print(f'Escribe en {s}… (haz clic en el campo de destino)', end='\r', flush=True)
        time.sleep(1)
    print(' ' * 60, end='\r')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reemplazo', action='store_true')
    parser.add_argument('--cien', action='store_true')
    parser.add_argument('--velocidad', type=int, default=20)
    parser.add_argument('--espera', type=int, default=5)
    args = parser.parse_args()

    escritor = EscritorTexto(args.velocidad)
    cuenta_regresiva(args.espera)
    inicio = time.perf_counter()
    if args.cien:
        for i in range(1, 101):
            escritor.escribir(f'Inserción {i:03d}: Año ñandú café ✓')
            escritor.escribir('\n')
        total = 100
    elif args.reemplazo:
        escritor.escribir('hola')
        time.sleep(1)
        escritor.reemplazar(len('hola'), FRASE)
        total = 1
    else:
        escritor.escribir(FRASE)
        total = 1
    print(f'Listo: {total} inserción(es) en {time.perf_counter() - inicio:.1f} s '
          f'a {args.velocidad} ms por carácter.')


if __name__ == '__main__':
    main()
