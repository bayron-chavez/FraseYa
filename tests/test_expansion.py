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


def test_publicar_ejecuta_en_el_hilo_de_tkinter_sin_bloquear(raiz):
    puente = PuenteHiloPrincipal(raiz, intervalo_ms=10)
    recibido = []
    hilo = threading.Thread(target=lambda: puente.publicar(lambda: recibido.append(threading.get_ident())))
    hilo.start(); hilo.join()
    assert recibido == []                      # publicar no ejecuta nada por sí mismo
    limite = time.time() + 2
    while not recibido and time.time() < limite:
        raiz.update(); time.sleep(0.01)
    assert recibido == [threading.get_ident()]
    puente.detener()


def test_publicar_tras_detener_se_ignora(raiz):
    puente = PuenteHiloPrincipal(raiz, intervalo_ms=10)
    puente.detener()
    puente.publicar(lambda: 1)                 # no debe fallar ni acumular
    assert puente._cola.empty()


def test_expansion_aplica_los_ajustes_sin_reiniciar():
    from fraseya.aplicacion.configuracion import Ajustes
    from fraseya.presentacion.expansion import Expansion

    class Escritor:
        velocidad_ms = 20

    class Teclado:
        def __init__(self):
            self.cambios, self.pausado = [], False

        def configurar(self, tecla, atajo):
            self.cambios.append((tecla, atajo))

    escritor, teclado = Escritor(), Teclado()
    expansion = Expansion(escritor, teclado, puente=None)
    expansion.aplicar(Ajustes('enter', 'ctrl+shift+k', 45, '', 15))
    assert escritor.velocidad_ms == 45
    assert teclado.cambios == [('enter', 'ctrl+shift+k')]
    expansion.pausar(True)
    assert teclado.pausado is True
