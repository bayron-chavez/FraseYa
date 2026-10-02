"""EscritorTexto: escritura simulada en el campo de texto que tiene el foco.

El teclado real se aísla en un backend para poder probar la lógica sin
escribir en ventanas. Los saltos de línea se envían como Shift+Enter: un Enter
simple enviaría el mensaje en las aplicaciones de chat, y la pulsación de
envío debe quedar siempre en manos de la persona (RNF-10).
"""
import ctypes
import sys
import time
from ctypes import wintypes

VELOCIDAD_MIN_MS = 10
VELOCIDAD_MAX_MS = 60
VELOCIDAD_PREDETERMINADA_MS = 20
ESPACIOS_POR_TABULADOR = 4


class TecladoWindows:
    """Backend que usa SendInput con eventos Unicode (sin pynput)."""

    _KEYEVENTF_KEYUP = 0x0002
    _KEYEVENTF_UNICODE = 0x0004
    _INPUT_KEYBOARD = 1
    _VK_BACK, _VK_RETURN, _VK_SHIFT = 0x08, 0x0D, 0x10

    class _KEYBDINPUT(ctypes.Structure):
        _fields_ = [('wVk', wintypes.WORD), ('wScan', wintypes.WORD),
                    ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD),
                    ('dwExtraInfo', ctypes.c_size_t)]

    class _MOUSEINPUT(ctypes.Structure):  # fija el tamaño de la unión en 64 bits
        _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG),
                    ('mouseData', wintypes.DWORD), ('dwFlags', wintypes.DWORD),
                    ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_size_t)]

    class _UNION(ctypes.Union):
        pass

    def __init__(self):
        if sys.platform != 'win32':
            raise OSError('TecladoWindows solo funciona en Windows.')
        self._UNION._fields_ = [('ki', self._KEYBDINPUT), ('mi', self._MOUSEINPUT)]

        class _INPUT(ctypes.Structure):
            _fields_ = [('type', wintypes.DWORD), ('u', self._UNION)]

        self._INPUT = _INPUT
        self._user32 = ctypes.WinDLL('user32', use_last_error=True)
        self._user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int]
        self._user32.SendInput.restype = wintypes.UINT

    def _evento(self, vk=0, scan=0, flags=0):
        entrada = self._INPUT(type=self._INPUT_KEYBOARD)
        entrada.u.ki = self._KEYBDINPUT(vk, scan, flags, 0, 0)
        return entrada

    def _enviar(self, *eventos):
        arreglo = (self._INPUT * len(eventos))(*eventos)
        if self._user32.SendInput(len(eventos), arreglo, ctypes.sizeof(self._INPUT)) != len(eventos):
            raise OSError(f'SendInput falló (error {ctypes.get_last_error()}).')

    def _tecla(self, vk):
        self._enviar(self._evento(vk), self._evento(vk, flags=self._KEYEVENTF_KEYUP))

    def caracter(self, c):
        # Un carácter fuera del plano básico viaja como dos unidades UTF-16.
        datos = c.encode('utf-16-le')
        for i in range(0, len(datos), 2):
            unidad = int.from_bytes(datos[i:i + 2], 'little')
            self._enviar(self._evento(scan=unidad, flags=self._KEYEVENTF_UNICODE),
                         self._evento(scan=unidad, flags=self._KEYEVENTF_UNICODE | self._KEYEVENTF_KEYUP))

    def retroceso(self):
        self._tecla(self._VK_BACK)

    def salto_linea(self):
        self._enviar(self._evento(self._VK_SHIFT), self._evento(self._VK_RETURN),
                     self._evento(self._VK_RETURN, flags=self._KEYEVENTF_KEYUP),
                     self._evento(self._VK_SHIFT, flags=self._KEYEVENTF_KEYUP))


class EscritorTexto:
    def __init__(self, velocidad_ms=VELOCIDAD_PREDETERMINADA_MS, teclado=None, pausa=time.sleep):
        self.teclado = teclado if teclado is not None else TecladoWindows()
        self._pausa = pausa
        self.velocidad_ms = velocidad_ms

    @property
    def velocidad_ms(self):
        return self._velocidad_ms

    @velocidad_ms.setter
    def velocidad_ms(self, valor):
        if type(valor) is not int or not VELOCIDAD_MIN_MS <= valor <= VELOCIDAD_MAX_MS:
            raise ValueError(f'La velocidad debe ser un entero entre {VELOCIDAD_MIN_MS} y '
                             f'{VELOCIDAD_MAX_MS} ms por carácter.')
        self._velocidad_ms = valor

    def borrar(self, cantidad):
        """Borra hacia atrás tantos caracteres como tenía la abreviatura."""
        if type(cantidad) is not int or cantidad < 0:
            raise ValueError('La cantidad a borrar debe ser un entero no negativo.')
        for _ in range(cantidad):
            self.teclado.retroceso()
            self._pausa(self._velocidad_ms / 1000)

    def escribir(self, texto):
        # La tecla Tab mueve el foco en navegadores y chats (el resto del texto se
        # perdería fuera del campo), así que un tabulador se escribe como espacios.
        texto = texto.replace('\r\n', '\n').replace('\r', '\n').replace('\t', ' ' * ESPACIOS_POR_TABULADOR)
        for c in texto:
            if c == '\n':
                self.teclado.salto_linea()
            else:
                self.teclado.caracter(c)
            self._pausa(self._velocidad_ms / 1000)

    def reemplazar(self, caracteres_a_borrar, texto):
        """Borra la abreviatura (y la tecla de confirmación, si se escribió) y escribe la frase."""
        self.borrar(caracteres_a_borrar)
        self.escribir(texto)
