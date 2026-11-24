"""RF-03: completar los campos variables ({nombre}, {orden}, {monto}, {fecha}…) de una frase.

Si la frase no tiene marcadores, el formulario no se pide y la inserción es
inmediata. Quien pide los valores (la ventana) se inyecta como función, para
poder probar esta lógica sin interfaz.
"""
from datetime import date

from fraseya.dominio.reglas import MARCADOR_VARIABLE, extraer_marcadores

_MARCADOR = MARCADOR_VARIABLE
detectar = extraer_marcadores


def valores_iniciales(nombres, hoy=None):
    """Sugerencias para el formulario: {fecha} viene con la fecha de hoy."""
    hoy = hoy or date.today()
    return {n: hoy.strftime('%d/%m/%Y') for n in nombres if n.lower() == 'fecha'}


def sustituir(contenido, valores):
    """Reemplaza cada marcador por su valor en una sola pasada.

    Un valor que contenga llaves no se vuelve a sustituir, y un marcador sin
    valor se deja tal cual.
    """
    return _MARCADOR.sub(lambda m: valores.get(m.group(1), m.group(0)), contenido)


def faltantes(nombres, valores):
    """Marcadores sin valor o con el valor vacío."""
    return [n for n in nombres if not (valores.get(n) or '').strip()]


def resolver(contenido, pedir_valores):
    """Devuelve el texto final, o None si la persona cancela el formulario.

    pedir_valores(nombres, iniciales) abre el formulario y devuelve un dict
    {nombre: valor} o None. No se llama si la frase no tiene marcadores.
    """
    nombres = detectar(contenido)
    if not nombres:
        return contenido
    valores = pedir_valores(nombres, valores_iniciales(nombres))
    if valores is None:
        return None
    pendientes = faltantes(nombres, valores)
    if pendientes:
        raise ValueError('Faltan valores para: ' + ', '.join(pendientes))
    return sustituir(contenido, {n: valores[n].strip() for n in nombres})
