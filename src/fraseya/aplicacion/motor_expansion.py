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
                 activar_ventana=lambda _ventana: None, lanzar=None):
        self.escritor = escritor
        self._pedir_valores = pedir_valores
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
        self._lanzar(lambda: self._expandir(abreviatura, contenido, ventana))
        return True

    # ---- expansión ------------------------------------------------------
    def _expandir(self, abreviatura, contenido, ventana):
        try:
            tiene_campos = bool(resolver_variables.detectar(contenido))
            texto = resolver_variables.resolver(contenido, self._pedir_valores)
            if texto is None:        # canceló el formulario: la abreviatura queda como estaba
                return
            if tiene_campos and ventana:
                self._activar_ventana(ventana)       # el formulario le quitó el foco
                time.sleep(PAUSA_TRAS_FORMULARIO_S)
            self.escritor.reemplazar(len(abreviatura), texto)
        finally:
            self._ocupado = False

    @staticmethod
    def _lanzar_en_hilo(trabajo):
        threading.Thread(target=trabajo, daemon=True, name='expansion').start()
