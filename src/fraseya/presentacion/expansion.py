"""Une el motor de expansión (RF-01) con la ventana: teclado global, formulario y catálogo."""
import queue
import threading

from fraseya.aplicacion.motor_expansion import MotorExpansion
from fraseya.infraestructura.escritor_texto import (VELOCIDAD_PREDETERMINADA_MS, EscritorTexto)
from fraseya.infraestructura.teclado_global import (TECLA_PREDETERMINADA, TecladoGlobal,
                                                    activar_ventana, ventana_activa)
from .formulario_variables import pedir_valores

CLAVE_TECLA = 'tecla_confirmacion'
CLAVE_VELOCIDAD = 'velocidad_ms'


class PuenteHiloPrincipal:
    """Ejecuta funciones en el hilo de Tkinter desde otros hilos y espera su resultado.

    Tkinter solo es seguro en su hilo; el motor trabaja en otro (para no frenar el
    teclado) y necesita abrir el formulario, así que le pasa el trabajo por una cola.
    """

    def __init__(self, raiz, intervalo_ms=40):
        self._raiz = raiz
        self._intervalo = intervalo_ms
        self._cola = queue.Queue()
        self._activo = True
        raiz.after(intervalo_ms, self._atender)

    def llamar(self, funcion):
        pedido = {'funcion': funcion, 'listo': threading.Event(), 'resultado': None, 'error': None}
        if not self._activo:
            raise RuntimeError('La ventana ya se cerró.')
        self._cola.put(pedido)
        pedido['listo'].wait()
        if pedido['error'] is not None:
            raise pedido['error']
        return pedido['resultado']

    def _atender(self):
        try:
            while True:
                pedido = self._cola.get_nowait()
                try:
                    pedido['resultado'] = pedido['funcion']()
                except Exception as error:
                    pedido['error'] = error
                finally:
                    pedido['listo'].set()
        except queue.Empty:
            pass
        if self._activo:
            self._raiz.after(self._intervalo, self._atender)

    def detener(self):
        """Libera a quien esté esperando (por ejemplo, si se cierra la ventana con el formulario abierto)."""
        self._activo = False
        while True:
            try:
                pedido = self._cola.get_nowait()
            except queue.Empty:
                return
            pedido['error'] = RuntimeError('La ventana se cerró.')
            pedido['listo'].set()


def _leer_configuracion(repo):
    tecla = repo.leer_configuracion(CLAVE_TECLA, TECLA_PREDETERMINADA)
    try:
        velocidad = int(repo.leer_configuracion(CLAVE_VELOCIDAD, str(VELOCIDAD_PREDETERMINADA_MS)))
    except ValueError:
        velocidad = VELOCIDAD_PREDETERMINADA_MS
    return tecla, velocidad


def iniciar_expansion(ventana, repo):
    """Arranca la captura del teclado. Devuelve una función para detenerla."""
    tecla, velocidad = _leer_configuracion(repo)
    try:
        escritor = EscritorTexto(velocidad)
    except ValueError:
        escritor = EscritorTexto()
    puente = PuenteHiloPrincipal(ventana)

    def pedir(nombres, iniciales):
        return puente.llamar(lambda: pedir_valores(nombres, iniciales, parent=ventana))

    motor = MotorExpansion(escritor, pedir, ventana_activa, activar_ventana)
    motor.actualizar_frases(repo.listar_frases())
    try:
        teclado = TecladoGlobal(motor, tecla)
    except ValueError:
        teclado = TecladoGlobal(motor)        # configuración inválida: se usa la tecla por defecto
    teclado.iniciar()
    ventana.al_cambiar = lambda: motor.actualizar_frases(repo.listar_frases())

    def detener():
        teclado.detener()
        puente.detener()

    return detener
