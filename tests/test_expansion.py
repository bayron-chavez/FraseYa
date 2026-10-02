import threading
import time
import tkinter as tk

import pytest

ctk = pytest.importorskip('customtkinter')
from fraseya.presentacion.expansion import PuenteHiloPrincipal  # noqa: E402


@pytest.fixture
def raiz():
    for _ in range(5):
        try:
            r = ctk.CTk()
            break
        except tk.TclError as error:
            ultimo = error
            time.sleep(0.2)
    else:
        pytest.skip(f'No se pudo abrir la ventana: {ultimo}')
    r.withdraw()
    yield r
    r.destroy()


def desde_otro_hilo(raiz, trabajo):
    """Ejecuta `trabajo` en un hilo y bombea Tk (como el mainloop) hasta que termine."""
    salida = {}

    def correr():
        try:
            salida['ok'] = trabajo()
        except Exception as error:
            salida['error'] = error

    hilo = threading.Thread(target=correr)
    hilo.start()
    limite = time.time() + 5
    while hilo.is_alive() and time.time() < limite:
        raiz.update()
        time.sleep(0.01)
    hilo.join(1)
    return salida


def test_la_funcion_corre_en_el_hilo_de_tkinter_y_devuelve_su_resultado(raiz):
    puente = PuenteHiloPrincipal(raiz, intervalo_ms=10)
    principal = threading.get_ident()
    salida = desde_otro_hilo(raiz, lambda: puente.llamar(lambda: (threading.get_ident(), 42)))
    hilo_de_la_funcion, resultado = salida['ok']
    assert resultado == 42 and hilo_de_la_funcion == principal
    puente.detener()


def test_un_error_en_la_funcion_se_propaga_a_quien_espera(raiz):
    puente = PuenteHiloPrincipal(raiz, intervalo_ms=10)

    def falla():
        raise ValueError('boom')

    salida = desde_otro_hilo(raiz, lambda: puente.llamar(falla))
    assert isinstance(salida['error'], ValueError)
    puente.detener()


def test_detener_libera_a_quien_espera_y_rechaza_llamadas_nuevas(raiz):
    puente = PuenteHiloPrincipal(raiz, intervalo_ms=10_000)   # no atiende solo
    salida = {}

    def esperar():
        try:
            puente.llamar(lambda: 1)
        except RuntimeError as error:
            salida['error'] = error

    hilo = threading.Thread(target=esperar)
    hilo.start()
    time.sleep(0.2)
    puente.detener()
    hilo.join(2)
    assert not hilo.is_alive() and 'cerró' in str(salida['error'])
    with pytest.raises(RuntimeError):
        puente.llamar(lambda: 1)
