"""Une el motor de expansión (RF-01) con la ventana: teclado global, formulario y catálogo."""
import queue
import threading

from fraseya.aplicacion.configuracion import Configuracion
from fraseya.aplicacion.motor_expansion import MotorExpansion
from fraseya.infraestructura.escritor_texto import EscritorTexto
from fraseya.infraestructura.teclado_global import (TecladoGlobal, activar_ventana, forzar_primer_plano,
                                                    hwnd_de, ventana_activa)
from .buscador_rapido import VentanaBuscador
from .formulario_variables import pedir_valores



class PuenteHiloPrincipal:
    """Ejecuta funciones en el hilo de Tkinter desde otros hilos y espera su resultado.

    Tkinter solo es seguro en su hilo; el motor trabaja en otro (para no frenar el
    teclado) y necesita abrir el formulario, así que le pasa el trabajo por una cola.
    """

    def __init__(self, raiz, intervalo_ms=25):
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

    def publicar(self, funcion):
        """Pide ejecutar `funcion` en el hilo de Tkinter sin esperar (para el hilo del teclado)."""
        if self._activo:
            self._cola.put({'funcion': funcion, 'listo': threading.Event(), 'resultado': None, 'error': None})

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


class Expansion:
    """La expansión por abreviatura y el buscador rápido, en marcha. Admite cambios de configuración."""

    def __init__(self, escritor, teclado, puente):
        self._escritor, self._teclado, self._puente = escritor, teclado, puente

    def aplicar(self, ajustes):
        """Aplica los ajustes al instante, sin reiniciar la aplicación."""
        self._escritor.velocidad_ms = ajustes.velocidad_ms
        self._teclado.configurar(ajustes.tecla_confirmacion, ajustes.atajo_buscador)

    def pausar(self, pausado):
        """Con la pantalla de configuración abierta no se vigila el teclado."""
        self._teclado.pausado = pausado

    def detener(self):
        self._teclado.detener()
        self._puente.detener()


def iniciar_expansion(ventana, repo):
    """Arranca la expansión por abreviatura y el buscador rápido; devuelve el objeto Expansion."""
    ajustes = Configuracion(repo).leer()
    escritor = EscritorTexto(ajustes.velocidad_ms)
    puente = PuenteHiloPrincipal(ventana)

    def pedir(nombres, iniciales):
        return puente.llamar(lambda: pedir_valores(nombres, iniciales, parent=ventana))

    motor = MotorExpansion(escritor, pedir, ventana_activa, activar_ventana)
    catalogo = []

    def recargar():
        catalogo[:] = ventana.gestion.listar()        # dicts con categoría, para el buscador
        motor.actualizar_frases(catalogo)

    recargar()
    teclado = TecladoGlobal(motor, ajustes.tecla_confirmacion, ajustes.atajo_buscador)

    buscador = VentanaBuscador(
        ventana,
        al_elegir=lambda frase, origen: motor.insertar(frase['contenido'], origen),
        al_cancelar=activar_ventana,
        al_mostrar=lambda: setattr(teclado, 'pausado', True),
        al_ocultar=lambda: setattr(teclado, 'pausado', False),
        forzar_primer_plano=forzar_primer_plano, hwnd_de=hwnd_de)

    def al_atajo():
        """Corre en el hilo del teclado: solo anota la ventana de origen y delega en Tkinter."""
        origen = ventana_activa()
        puente.publicar(lambda: buscador.mostrar(list(catalogo), origen))

    teclado.al_atajo = al_atajo
    teclado.iniciar()
    ventana.al_cambiar = recargar
    return Expansion(escritor, teclado, puente)
