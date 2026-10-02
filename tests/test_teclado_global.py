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
    assert t._soltar == {0x09}
    with pytest.raises(SuppressException):
        t._filtro(tg._WM_KEYUP, evento(0x09))
    assert t._soltar == set()
    assert t._filtro(tg._WM_KEYUP, evento(0x09)) is False   # un segundo "soltar" ya pasa normal


def test_soltar_otra_tecla_nunca_se_traga():
    t = teclado(coincide=True)
    t._soltar = {0x09}
    assert t._filtro(tg._WM_KEYUP, evento(0x48)) is False
    assert t._soltar == {0x09}


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


# ---- atajo global del buscador (RF-02) -----------------------------------

@pytest.mark.parametrize('texto,esperado', [
    ('ctrl+alt+espacio', (frozenset({'ctrl', 'alt'}), 0x20)),
    ('Ctrl + Shift + K', (frozenset({'ctrl', 'shift'}), ord('K'))),
    ('win+7', (frozenset({'win'}), ord('7'))),
    ('alt+f9', (frozenset({'alt'}), 0x78)),
])
def test_interpretar_atajo(texto, esperado):
    assert tg.interpretar_atajo(texto) == esperado


@pytest.mark.parametrize('texto', ['', 'espacio', 'k', 'ctrl+', 'ctrl+ctrl+k', 'super+k',
                                   'ctrl+f13', 'ctrl+ñ', 'ctrl+dos'])
def test_atajos_no_validos(texto):
    with pytest.raises(ValueError):
        tg.interpretar_atajo(texto)


def teclado_con_atajo(mods=frozenset({'ctrl', 'alt'}), atajo='ctrl+alt+espacio', coincide=False):
    llamadas = []
    t = tg.TecladoGlobal(MotorFalso(coincide), atajo=atajo, al_atajo=lambda: llamadas.append(1))
    t._teclado, t._u = OyenteFalso(), tg._user32()
    t._modificadores = lambda: mods
    return t, llamadas


def test_el_atajo_se_dispara_y_se_traga_la_tecla():
    t, llamadas = teclado_con_atajo()
    with pytest.raises(SuppressException):
        abajo(t, 0x20)
    assert llamadas == [1] and t._soltar == {0x20}
    assert ('reset',) in t.motor.eventos     # se olvida lo que se venía escribiendo


def test_el_soltar_del_atajo_tambien_se_traga():
    t, _ = teclado_con_atajo()
    with pytest.raises(SuppressException):
        abajo(t, 0x20)
    with pytest.raises(SuppressException):
        t._filtro(tg._WM_KEYUP, evento(0x20))
    assert t._soltar == set()


def test_mantener_pulsado_el_atajo_no_lo_dispara_varias_veces():
    t, llamadas = teclado_con_atajo()
    for _ in range(4):
        with pytest.raises(SuppressException):
            abajo(t, 0x20)
    assert llamadas == [1]


def test_con_otros_modificadores_no_es_el_atajo():
    for mods in (frozenset({'ctrl'}), frozenset({'ctrl', 'alt', 'shift'}), frozenset()):
        t, llamadas = teclado_con_atajo(mods=mods)
        abajo(t, 0x20)                       # no debe tragarse la tecla
        assert llamadas == []


def test_otra_tecla_con_los_mismos_modificadores_no_es_el_atajo():
    t, llamadas = teclado_con_atajo()
    abajo(t, 0x41)
    assert llamadas == []


def test_en_pausa_el_atajo_se_traga_pero_no_vuelve_a_abrir_y_no_se_vigila_el_teclado():
    t, llamadas = teclado_con_atajo()
    t.pausado = True
    with pytest.raises(SuppressException):
        abajo(t, 0x20)
    assert llamadas == []
    t.motor.eventos.clear()
    abajo(t, 0x48)                           # escribir en el buscador no debe llegar al motor
    assert t.motor.eventos == []


def test_un_error_en_el_buscador_no_rompe_el_hook():
    t, _ = teclado_con_atajo()
    t.al_atajo = lambda: (_ for _ in ()).throw(RuntimeError('falla'))
    with pytest.raises(SuppressException):
        abajo(t, 0x20)


def test_sin_atajo_configurado_nada_cambia():
    t = teclado()
    abajo(t, 0x20)
    assert t.motor.eventos == [('reset',)]


# ---- cambio de configuración en caliente (RF-11) --------------------------

def test_configurar_cambia_la_tecla_de_confirmacion_y_el_atajo_sin_reiniciar():
    t = teclado(coincide=True, tecla='tab')
    t.configurar('enter', 'ctrl+shift+k')
    assert t.tecla_confirmacion == 'enter' and t._vk_confirmacion == 0x0D
    assert t._atajo == (frozenset({'ctrl', 'shift'}), ord('K'))
    with pytest.raises(SuppressException):
        abajo(t, 0x0D)                                   # ahora Enter confirma
    t._soltar.clear()
    t.motor.eventos.clear()
    abajo(t, 0x09)                                       # y Tab ya no
    assert t.motor.eventos == [('reset',)]


def test_configurar_con_un_valor_invalido_no_deja_nada_a_medias():
    t = teclado(tecla='tab')
    original = (t.tecla_confirmacion, t._atajo)
    with pytest.raises(ValueError):
        t.configurar('enter', 'k')                       # atajo inválido
    with pytest.raises(ValueError):
        t.configurar('f13')
    assert (t.tecla_confirmacion, t._atajo) == original


def test_configurar_solo_una_cosa_conserva_la_otra():
    t = teclado_con_atajo()[0]
    t.configurar(atajo='alt+f9')
    assert t.tecla_confirmacion == 'tab'
    t.configurar(tecla_confirmacion='espacio')
    assert t._atajo == (frozenset({'alt'}), 0x78)
