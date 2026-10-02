"""Escritura simulada de teclado en la aplicación con foco (RNF-03)."""
import time

VELOCIDAD_MIN_MS = 10
VELOCIDAD_MAX_MS = 60


class TecladoPynput:
    """Teclado real. pynput se importa al usarlo para no exigir pantalla al importar."""

    def __init__(self):
        from pynput.keyboard import Controller, Key
        self._teclado = Controller()
        self._key = Key

    def escribir_caracter(self, caracter):
        self._teclado.type(caracter)

    def enter(self):
        self._teclado.tap(self._key.enter)

    def retroceso(self):
        self._teclado.tap(self._key.backspace)


class EscritorTexto:
    def __init__(self, teclado=None, velocidad_ms=20, dormir=time.sleep):
        self._teclado = teclado
        self._dormir = dormir
        self.velocidad_ms = velocidad_ms

    @property
    def velocidad_ms(self):
        return self._velocidad_ms

    @velocidad_ms.setter
    def velocidad_ms(self, valor):
        if type(valor) is not int or not VELOCIDAD_MIN_MS <= valor <= VELOCIDAD_MAX_MS:
            raise ValueError(
                f'La velocidad debe estar entre {VELOCIDAD_MIN_MS} y {VELOCIDAD_MAX_MS} ms por carácter.')
        self._velocidad_ms = valor

    @property
    def teclado(self):
        if self._teclado is None:
            self._teclado = TecladoPynput()
        return self._teclado

    def _pausa(self):
        self._dormir(self._velocidad_ms / 1000)

    def borrar(self, cantidad):
        for _ in range(cantidad):
            self.teclado.retroceso()
            self._pausa()

    def escribir(self, texto):
        """Escribe el texto carácter a carácter; los saltos de línea pulsan Enter."""
        for caracter in texto.replace('\r\n', '\n').replace('\r', '\n'):
            if caracter == '\n':
                self.teclado.enter()
            else:
                self.teclado.escribir_caracter(caracter)
            self._pausa()

    def reemplazar_abreviatura(self, abreviatura, texto):
        """Borra la abreviatura tecleada y escribe en su lugar el texto expandido."""
        self.borrar(len(abreviatura))
        self.escribir(texto)
