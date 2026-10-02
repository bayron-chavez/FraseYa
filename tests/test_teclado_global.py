import sys
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='Solo Windows')

from fraseya.infraestructura import teclado_global as tg  # noqa: E402


class SuppressException(Exception):
    """Mismo nombre que la de pynput: así el filtro la deja pasar."""


class OyenteFalso:
    def suppress_event(self):
        raise SuppressException()


class MotorFalso:
    def __init__(self, coincide=False):
        self.eventos, self.coincide = [], coincide

    def caracter(self, c):
        self.eventos.append(('c', c))

    def retroceso(self):
        self.eventos.append(('bs',))

    def reiniciar(self):
        self.eventos.append(('reset',))

    def confirmar(self):
        self.eventos.append(('confirmar',))
        return self.coincide


def teclado(coincide=False, tecla='tab'):
    t = tg.TecladoGlobal(MotorFalso(coincide), tecla)
    t._teclado = OyenteFalso()
    t._u = tg._user32()
    return t


def evento(vk, flags=0, scan=0):
    return SimpleNamespace(vkCode=vk, scanCode=scan, flags=flags)


def abajo(t, vk, flags=0):
    return t._filtro(tg._WM_KEYDOWN, evento(vk, flags, scan=0))


def test_una_tecla_inyectada_se_ignora():
    t = teclado()
    abajo(t, 0x48, flags=tg._LLKHF_INJECTED)       # la escribió EscritorTexto
    abajo(t, 0x48, flags=tg._LLKHF_LOWER_IL_INJECTED)
    assert t.motor.eventos == []


def test_una_letra_normal_llega_al_motor():
    t = teclado()
    abajo(t, 0x48)                                  # H
    assert t.motor.eventos == [('c', 'h')]


def test_retroceso_se_informa():
    t = teclado()
    abajo(t, tg._VK_BACK)
    assert t.motor.eventos == [('bs',)]


@pytest.mark.parametrize('vk', [0x10, 0xA0, 0x11, 0x12, 0x14])
def test_los_modificadores_solos_no_reinician_ni_escriben(vk):
    t = teclado()
    abajo(t, vk)
    assert t.motor.eventos == []


@pytest.mark.parametrize('vk', [0x0D, 0x1B, 0x25, 0x26, 0x70, 0x20])   # Enter, Esc, flechas, F1, espacio
def test_enter_esc_flechas_y_espacio_reinician(vk):
    t = teclado(tecla='tab')                        # ninguna de estas es la tecla de confirmación
    abajo(t, vk)
    assert t.motor.eventos == [('reset',)]


def test_tab_sin_coincidencia_pasa_de_largo():
    t = teclado(coincide=False)
    abajo(t, 0x09)                                  # no debe lanzar SuppressException
    assert t.motor.eventos == [('confirmar',)]


def test_tab_con_coincidencia_se_traga_la_tecla_y_tambien_el_soltado():
    t = teclado(coincide=True)
    with pytest.raises(SuppressException):
        abajo(t, 0x09)
    assert t._soltar_pendiente is True
    with pytest.raises(SuppressException):
        t._filtro(tg._WM_KEYUP, evento(0x09))
    assert t._soltar_pendiente is False
    assert t._filtro(tg._WM_KEYUP, evento(0x09)) is False   # un segundo "soltar" ya pasa normal


def test_soltar_otra_tecla_nunca_se_traga():
    t = teclado(coincide=True)
    t._soltar_pendiente = True
    assert t._filtro(tg._WM_KEYUP, evento(0x48)) is False
    assert t._soltar_pendiente is True


def test_la_tecla_de_confirmacion_inyectada_no_cuenta():
    t = teclado(coincide=True)
    abajo(t, 0x09, flags=tg._LLKHF_INJECTED)
    assert t.motor.eventos == []


def test_un_error_interno_olvida_lo_escrito_y_no_rompe_el_hook():
    t = teclado()
    t._u = None                                     # fuerza una excepción dentro del filtro
    abajo(t, 0x48)
    assert t.motor.eventos == [('reset',)]


def test_la_tecla_de_confirmacion_debe_ser_una_de_las_permitidas():
    with pytest.raises(ValueError, match='no válida'):
        tg.TecladoGlobal(MotorFalso(), 'f13')


def test_ventana_activa_devuelve_un_identificador():
    assert tg.ventana_activa() is not None
