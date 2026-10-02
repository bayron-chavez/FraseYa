"""Prueba manual del formulario de campos variables (RF-03).

    python scripts/prueba_formulario.py                  # frase de ejemplo con 4 variables
    python scripts/prueba_formulario.py "Hola {nombre}"  # tu propia frase
    python scripts/prueba_formulario.py "Sin variables"  # no debe abrir el formulario
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from fraseya.aplicacion.resolver_variables import resolver
from fraseya.presentacion.formulario_variables import pedir_valores

EJEMPLO = 'Gracias {nombre}, su caso {orden} por {monto} fue registrado el {fecha}. Saludos, {nombre}.'


def main():
    contenido = sys.argv[1] if len(sys.argv) > 1 else EJEMPLO
    print(f'Frase: {contenido}')
    texto = resolver(contenido, lambda nombres, iniciales: pedir_valores(nombres, iniciales))
    print('Cancelado: no se inserta nada.' if texto is None else f'Resultado: {texto}')


if __name__ == '__main__':
    main()
