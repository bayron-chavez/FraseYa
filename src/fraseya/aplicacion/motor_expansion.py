"""RF-01: expansión de texto por abreviatura.

El motor lleva la cuenta de lo que la persona va escribiendo y, cuando pulsa la
tecla de confirmación sobre una abreviatura existente, reemplaza la abreviatura
por la frase. Sin la tecla de confirmación nunca se expande.

No depende del teclado real ni de la interfaz: quien captura las teclas
(TecladoGlobal) llama a caracter / retroceso / reiniciar / confirmar, y la
ventana entrega la función que pide los valores de los campos variables.
"""
import threading
import time

from . import resolver_variables

LARGO_MAXIMO = 64          # una abreviatura más larga que esto no existe
PAUSA_TRAS_FORMULARIO_S = 0.15


class MotorExpansion:
    def __init__(self, escritor, pedir_valores, ventana_activa=lambda: None,
                 activar_ventana=lambda _ventana: None, lanzar=None, pedir_con_contexto=None):
        self.escritor = escritor
        self._pedir_valores = pedir_valores
        self._pedir_con_contexto = pedir_con_contexto
        self._ventana_activa = ventana_activa
        self._activar_ventana = activar_ventana
        self._lanzar = lanzar or self._lanzar_en_hilo
        self._frases = {}        # abreviatura en minúsculas -> contenido
        self._buffer = ''
        self._ventana = None     # ventana donde se empezó a escribir la abreviatura
        self._ocupado = False

    # ---- catálogo -------------------------------------------------------
    def actualizar_frases(self, frases):
        """Recibe las frases como lista de dicts (abreviatura, contenido).

        Se reemplaza el diccionario completo de una vez, así el hilo del teclado
        nunca ve un estado a medias ni toca la base de datos.
        """
        self._frases = {f['abreviatura'].lower(): f['contenido'] for f in frases}

    # ---- teclas ---------------------------------------------------------
    def caracter(self, c):
        if self._ocupado:
            return
        if not self._buffer:
            self._ventana = self._ventana_activa()
        self._buffer += c
        if len(self._buffer) > LARGO_MAXIMO:
            self.reiniciar()

    def retroceso(self):
        self._buffer = self._buffer[:-1]

    def reiniciar(self):
        self._buffer = ''
        self._ventana = None

    @property
    def escrito(self):
        return self._buffer

    def hay_coincidencia(self):
        return (not self._ocupado and self._buffer.lower() in self._frases
                and self._ventana_activa() == self._ventana)

    def confirmar(self):
        """Se pulsó la tecla de confirmación. True si expandirá (hay que tragarse la tecla)."""
        if not self.hay_coincidencia():
            self.reiniciar()
            return False
        abreviatura, ventana = self._buffer, self._ventana
        contenido = self._frases[abreviatura.lower()]
        self.reiniciar()
        self._ocupado = True
        self._lanzar(lambda: self._insertar(contenido, ventana, len(abreviatura)))
        return True

    def insertar(self, contenido, ventana):
        """Escribe una frase elegida a mano (buscador rápido) en `ventana`, sin borrar nada.

        Devuelve False si ya hay una inserción en curso.
        """
        if self._ocupado:
            return False
        self.reiniciar()
        self._ocupado = True
        self._lanzar(lambda: self._insertar(contenido, ventana, 0, devolver_foco=True))
        return True

    # ---- escritura ------------------------------------------------------
    def _insertar(self, contenido, ventana, borrar, devolver_foco=False):
        """Resuelve los campos variables y escribe el texto en `ventana`.

        borrar: caracteres a borrar antes (la abreviatura). devolver_foco: hay que
        reactivar la ventana aunque no haya formulario (el buscador le quitó el foco).
        """
        try:
            tiene_campos = bool(resolver_variables.detectar(contenido))
            pedir = self._pedir_valores
            if self._pedir_con_contexto is not None:
                pedir = lambda nombres, iniciales: self._pedir_con_contexto(nombres, iniciales, contenido)
            texto = resolver_variables.resolver(contenido, pedir)
            if texto is None:        # canceló el formulario: no se escribe ni borra nada
                if devolver_foco and ventana:
                    self._activar_ventana(ventana)
                return
            if (tiene_campos or devolver_foco) and ventana:
                self._activar_ventana(ventana)       # el formulario o el buscador le quitaron el foco
                time.sleep(PAUSA_TRAS_FORMULARIO_S)
            self.escritor.reemplazar(borrar, texto)
        finally:
            self._ocupado = False

    @staticmethod
    def _lanzar_en_hilo(trabajo):
        threading.Thread(target=trabajo, daemon=True, name='expansion').start()
