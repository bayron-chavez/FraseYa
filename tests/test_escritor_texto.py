import sys

import pytest

from fraseya.infraestructura.escritor_texto import EscritorTexto


class TecladoFalso:
    def __init__(self):
        self.eventos = []

    def caracter(self, c):
        self.eventos.append(('c', c))

    def retroceso(self):
        self.eventos.append(('bs',))

    def salto_linea(self):
        self.eventos.append(('nl',))


def escritor(velocidad=20):
    pausas = []
    teclado = TecladoFalso()
    return EscritorTexto(velocidad, teclado, pausas.append), teclado, pausas


def test_escribe_unicode_y_emojis_caracter_a_caracter():
    e, teclado, _ = escritor()
    e.escribir('Año ñandú ✓ 😀')
    assert ''.join(x[1] for x in teclado.eventos if x[0] == 'c') == 'Año ñandú ✓ 😀'


def test_saltos_de_linea_son_shift_enter_y_se_normalizan():
    e, teclado, _ = escritor()
    e.escribir('a\r\nb\rc\nd')
    assert [x[0] for x in teclado.eventos] == ['c', 'nl', 'c', 'nl', 'c', 'nl', 'c']


def test_tabulador_se_escribe_como_espacios_y_no_como_tecla_tab():
    # La tecla Tab sacaría el foco del campo en navegadores y chats.
    e, teclado, _ = escritor()
    e.escribir('a\tb')
    assert teclado.eventos == [('c', 'a')] + [('c', ' ')] * 4 + [('c', 'b')]


def test_borra_la_abreviatura_antes_de_escribir():
    e, teclado, _ = escritor()
    e.reemplazar(3, 'Hola')
    assert [x[0] for x in teclado.eventos[:3]] == ['bs', 'bs', 'bs']
    assert teclado.eventos[3] == ('c', 'H')


def test_pausa_por_caracter_segun_velocidad():
    e, _, pausas = escritor(40)
    e.escribir('abc')
    assert pausas == [0.04] * 3


@pytest.mark.parametrize('valor', [9, 61, 0, -5, 20.5, '20', None])
def test_velocidad_fuera_de_rango_se_rechaza(valor):
    with pytest.raises(ValueError):
        escritor()[0].velocidad_ms = valor


@pytest.mark.parametrize('valor', [10, 60])
def test_velocidad_en_los_limites_es_valida(valor):
    assert escritor(valor)[0].velocidad_ms == valor


@pytest.mark.parametrize('cantidad', [-1, 1.5, '2'])
def test_cantidad_a_borrar_invalida(cantidad):
    with pytest.raises(ValueError):
        escritor()[0].borrar(cantidad)


def test_texto_vacio_no_envia_nada():
    e, teclado, _ = escritor()
    e.escribir('')
    assert teclado.eventos == []


@pytest.mark.skipif(sys.platform != 'win32', reason='Solo Windows')
def test_backend_windows_se_construye_y_tiene_tamano_de_input_correcto():
    import ctypes
    from fraseya.infraestructura.escritor_texto import TecladoWindows
    t = TecladoWindows()
    assert ctypes.sizeof(t._INPUT) == (40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)
