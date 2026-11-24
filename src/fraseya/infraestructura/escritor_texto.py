"""EscritorTexto: escritura simulada en el campo de texto que tiene el foco.

Los saltos de línea se envían como Shift+Enter: un Enter simple enviaría el mensaje
en las aplicaciones de chat, y el envío queda siempre bajo control del usuario.
"""
import ctypes
from ctypes import wintypes
import sys
import time

from .win32_com import (
    _INPUT_KEYBOARD,
    _KEYEVENTF_KEYUP,
    _KEYEVENTF_UNICODE,
    INPUT,
    KEYBDINPUT,
    user32,
)

VELOCIDAD_MIN_MS = 10
VELOCIDAD_MAX_MS = 60
VELOCIDAD_PREDETERMINADA_MS = 20
ESPACIOS_POR_TABULADOR = 4


class TecladoWindows:
    """Backend que usa SendInput con eventos Unicode y portapapeles con restauración."""

    _INPUT = INPUT
    _KEYBDINPUT = KEYBDINPUT
    _KEYEVENTF_KEYUP = _KEYEVENTF_KEYUP
    _KEYEVENTF_UNICODE = _KEYEVENTF_UNICODE
    _INPUT_KEYBOARD = _INPUT_KEYBOARD
    _VK_BACK, _VK_RETURN, _VK_SHIFT = 0x08, 0x0D, 0x10
    _VK_CONTROL, _VK_V = 0x11, 0x56
    _CF_UNICODETEXT = 13
    _GMEM_MOVEABLE = 0x0002

    def __init__(self):
        if sys.platform != 'win32':
            raise OSError('TecladoWindows solo funciona en Windows.')
        self._user32 = user32()

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
        datos = c.encode('utf-16-le')
        for i in range(0, len(datos), 2):
            unidad = int.from_bytes(datos[i:i + 2], 'little')
            self._enviar(
                self._evento(scan=unidad, flags=self._KEYEVENTF_UNICODE),
                self._evento(scan=unidad, flags=self._KEYEVENTF_UNICODE | self._KEYEVENTF_KEYUP),
            )

    def retroceso(self):
        self._tecla(self._VK_BACK)

    def salto_linea(self):
        self._enviar(
            self._evento(self._VK_SHIFT),
            self._evento(self._VK_RETURN),
            self._evento(self._VK_RETURN, flags=self._KEYEVENTF_KEYUP),
            self._evento(self._VK_SHIFT, flags=self._KEYEVENTF_KEYUP),
        )

    def _apis_portapapeles(self):
        u = self._user32
        k = ctypes.WinDLL('kernel32', use_last_error=True)
        u.OpenClipboard.argtypes = [wintypes.HWND]
        u.OpenClipboard.restype = wintypes.BOOL
        u.CloseClipboard.argtypes = []
        u.CloseClipboard.restype = wintypes.BOOL
        u.EmptyClipboard.argtypes = []
        u.EmptyClipboard.restype = wintypes.BOOL
        u.GetClipboardData.argtypes = [wintypes.UINT]
        u.GetClipboardData.restype = wintypes.HANDLE
        u.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        u.SetClipboardData.restype = wintypes.HANDLE
        k.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        k.GlobalAlloc.restype = wintypes.HGLOBAL
        k.GlobalLock.argtypes = [wintypes.HGLOBAL]
        k.GlobalLock.restype = ctypes.c_void_p
        k.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        k.GlobalUnlock.restype = wintypes.BOOL
        k.GlobalFree.argtypes = [wintypes.HGLOBAL]
        k.GlobalFree.restype = wintypes.HGLOBAL
        return u, k

    def _abrir_portapapeles(self, u) -> bool:
        for _ in range(10):
            if u.OpenClipboard(None):
                return True
            time.sleep(0.025)
        return False

    def _leer_portapapeles(self, u, k) -> str | None:
        hmem = u.GetClipboardData(self._CF_UNICODETEXT)
        if not hmem:
            return None
        ptr = k.GlobalLock(hmem)
        if not ptr:
            return None
        try:
            return ctypes.wstring_at(ptr)
        finally:
            k.GlobalUnlock(hmem)

    def _escribir_portapapeles(self, u, k, texto: str) -> bool:
        datos = (texto + '\0').encode('utf-16-le')
        hmem = k.GlobalAlloc(self._GMEM_MOVEABLE, len(datos))
        if not hmem:
            return False
        ptr = k.GlobalLock(hmem)
        if not ptr:
            k.GlobalFree(hmem)
            return False
        try:
            ctypes.memmove(ptr, datos, len(datos))
        finally:
            k.GlobalUnlock(hmem)
        u.EmptyClipboard()
        if not u.SetClipboardData(self._CF_UNICODETEXT, hmem):
            k.GlobalFree(hmem)
            return False
        return True

    def pegar_texto(self, texto: str) -> bool:
        """Copia el texto al portapapeles, envía Ctrl+V y restaura el texto previo."""
        if not texto:
            return True
        try:
            u, k = self._apis_portapapeles()
        except OSError:
            return False

        if not self._abrir_portapapeles(u):
            return False

        respaldo: str | None = None
        try:
            respaldo = self._leer_portapapeles(u, k)
            escrito = self._escribir_portapapeles(u, k, texto.replace('\n', '\r\n'))
        finally:
            u.CloseClipboard()

        if not escrito:
            return False

        try:
            scan_ctrl = u.MapVirtualKeyW(self._VK_CONTROL, 0)
            scan_v = u.MapVirtualKeyW(self._VK_V, 0)
            self._enviar(self._evento(self._VK_CONTROL, scan=scan_ctrl))
            time.sleep(0.025)
            self._enviar(self._evento(self._VK_V, scan=scan_v))
            time.sleep(0.025)
            self._enviar(self._evento(self._VK_V, scan=scan_v, flags=self._KEYEVENTF_KEYUP))
            time.sleep(0.025)
            self._enviar(self._evento(self._VK_CONTROL, scan=scan_ctrl, flags=self._KEYEVENTF_KEYUP))
            time.sleep(0.08)
        finally:
            if respaldo is not None and self._abrir_portapapeles(u):
                try:
                    self._escribir_portapapeles(u, k, respaldo)
                finally:
                    u.CloseClipboard()
        return True


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
            raise ValueError(
                f'La velocidad debe ser un entero entre {VELOCIDAD_MIN_MS} y '
                f'{VELOCIDAD_MAX_MS} ms por carácter.'
            )
        self._velocidad_ms = valor

    def borrar(self, cantidad):
        """Borra hacia atrás tantos caracteres como tenía la abreviatura."""
        if type(cantidad) is not int or cantidad < 0:
            raise ValueError('La cantidad a borrar debe ser un entero no negativo.')
        for _ in range(cantidad):
            self.teclado.retroceso()
            self._pausa(self._velocidad_ms / 1000)

    def escribir(self, texto):
        # Tab mueve el foco fuera del campo en navegadores y chats; se escribe como espacios.
        texto = texto.replace('\r\n', '\n').replace('\r', '\n').replace('\t', ' ' * ESPACIOS_POR_TABULADOR)
        if len(texto) >= 12 and hasattr(self.teclado, 'pegar_texto'):
            try:
                if self.teclado.pegar_texto(texto):
                    return
            except OSError:
                pass
        for c in texto:
            if c == '\n':
                self.teclado.salto_linea()
            else:
                self.teclado.caracter(c)
            self._pausa(self._velocidad_ms / 1000)

    def reemplazar(self, caracteres_a_borrar, texto):
        """Borra la abreviatura y escribe la frase."""
        self.borrar(caracteres_a_borrar)
        self.escribir(texto)
