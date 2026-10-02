"""Captura global del teclado (Windows) para el motor de expansión.

Todo el procesamiento ocurre dentro del filtro del hook, que se ejecuta de forma
sincrónica antes de que la tecla llegue a la aplicación. Eso permite tragarse la
tecla de confirmación solo cuando realmente se va a expandir (si no hay
coincidencia, la tecla pasa normal). Los eventos de pynput llegan después, en
otro hilo, y no sirven para decidir eso sin condiciones de carrera.

Las teclas inyectadas (las que escribe EscritorTexto) se ignoran, para que el
motor no se dispare con su propio texto.
"""
import ctypes
import sys
from ctypes import wintypes

TECLAS_CONFIRMACION = {'tab': 0x09, 'enter': 0x0D, 'espacio': 0x20}
TECLA_PREDETERMINADA = 'tab'

_WM_KEYDOWN, _WM_KEYUP, _WM_SYSKEYDOWN, _WM_SYSKEYUP = 0x100, 0x101, 0x104, 0x105
_LLKHF_INJECTED, _LLKHF_LOWER_IL_INJECTED = 0x10, 0x02
_VK_BACK = 0x08
_VK_SHIFT, _VK_CONTROL, _VK_MENU, _VK_CAPITAL = 0x10, 0x11, 0x12, 0x14
_VK_LWIN, _VK_RWIN = 0x5B, 0x5C
_MODIFICADORES = {_VK_SHIFT, 0xA0, 0xA1, _VK_CONTROL, 0xA2, 0xA3, _VK_MENU, 0xA4, 0xA5,
                  _VK_CAPITAL, _VK_LWIN, _VK_RWIN}
_NO_CAMBIAR_ESTADO = 0x4   # ToUnicodeEx: no altera el estado de las teclas muertas


def _user32():
    if sys.platform != 'win32':
        raise OSError('La captura global del teclado solo funciona en Windows.')
    u = ctypes.WinDLL('user32', use_last_error=True)
    u.GetForegroundWindow.restype = wintypes.HWND
    u.SetForegroundWindow.argtypes = [wintypes.HWND]
    u.GetAsyncKeyState.argtypes = [ctypes.c_int]
    u.GetKeyState.argtypes = [ctypes.c_int]
    u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    u.GetKeyboardLayout.argtypes = [wintypes.DWORD]
    u.GetKeyboardLayout.restype = wintypes.HKL
    u.ToUnicodeEx.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_ubyte),
                              wintypes.LPWSTR, ctypes.c_int, wintypes.UINT, wintypes.HKL]
    return u


def ventana_activa():
    """Identificador de la ventana que tiene el foco ahora mismo."""
    return _user32().GetForegroundWindow()


def activar_ventana(ventana):
    """Devuelve el foco a una ventana (después de que el formulario se lo quitó)."""
    _user32().SetForegroundWindow(ventana)


class TecladoGlobal:
    def __init__(self, motor, tecla_confirmacion=TECLA_PREDETERMINADA):
        if tecla_confirmacion not in TECLAS_CONFIRMACION:
            raise ValueError(f'Tecla de confirmación no válida: {tecla_confirmacion}. '
                             f'Opciones: {", ".join(TECLAS_CONFIRMACION)}.')
        self.motor = motor
        self.tecla_confirmacion = tecla_confirmacion
        self._vk_confirmacion = TECLAS_CONFIRMACION[tecla_confirmacion]
        self._soltar_pendiente = False   # hay que tragarse también el "soltar" de la tecla
        self._teclado = None
        self._raton = None
        self._u = None

    # ---- ciclo de vida --------------------------------------------------
    def iniciar(self):
        from pynput import keyboard, mouse   # import tardío: solo hace falta al capturar
        self._u = _user32()
        self._teclado = keyboard.Listener(win32_event_filter=self._filtro)
        self._raton = mouse.Listener(on_click=lambda *_: self.motor.reiniciar())
        self._teclado.start()
        self._raton.start()

    def detener(self):
        for oyente in (self._teclado, self._raton):
            if oyente is not None:
                oyente.stop()
        self._teclado = self._raton = None

    # ---- filtro del hook ------------------------------------------------
    def _filtro(self, mensaje, datos):
        """Procesa la tecla. Devuelve siempre False: pynput no necesita reenviarla."""
        try:
            if datos.flags & (_LLKHF_INJECTED | _LLKHF_LOWER_IL_INJECTED):
                return False
            if mensaje in (_WM_KEYUP, _WM_SYSKEYUP):
                if self._soltar_pendiente and datos.vkCode == self._vk_confirmacion:
                    self._soltar_pendiente = False
                    self._teclado.suppress_event()
                return False
            if mensaje not in (_WM_KEYDOWN, _WM_SYSKEYDOWN):
                return False
            if datos.vkCode == self._vk_confirmacion:
                if self.motor.confirmar():
                    self._soltar_pendiente = True
                    self._teclado.suppress_event()
                return False
            self._procesar(datos.vkCode, datos.scanCode)
        except Exception as error:
            if type(error).__name__ == 'SuppressException':
                raise
            self.motor.reiniciar()   # ante cualquier duda, olvidar lo escrito
        return False

    def _procesar(self, vk, scan):
        if vk in _MODIFICADORES and vk not in (_VK_LWIN, _VK_RWIN):
            return
        if vk in (_VK_LWIN, _VK_RWIN):
            self.motor.reiniciar()
        elif vk == _VK_BACK:
            self.motor.retroceso()
        else:
            letra = self._a_caracter(vk, scan)
            if letra is None:
                return                      # tecla muerta: la letra llegará en la siguiente
            if letra.isprintable() and not letra.isspace():
                self.motor.caracter(letra)
            else:
                self.motor.reiniciar()      # espacio, Enter, Esc, flechas, atajos…

    def _a_caracter(self, vk, scan):
        """Carácter que produce la tecla con el teclado y los modificadores actuales."""
        u = self._u
        estado = (ctypes.c_ubyte * 256)()
        ctrl = bool(u.GetAsyncKeyState(_VK_CONTROL) & 0x8000)
        alt = bool(u.GetAsyncKeyState(_VK_MENU) & 0x8000)
        if ctrl and not alt:
            return '\x00'                   # Ctrl+tecla es un atajo, no texto
        for modificador in (_VK_SHIFT, _VK_CONTROL, _VK_MENU):
            if u.GetAsyncKeyState(modificador) & 0x8000:
                estado[modificador] = 0x80
        if u.GetKeyState(_VK_CAPITAL) & 1:
            estado[_VK_CAPITAL] = 1
        ventana = u.GetForegroundWindow()
        distribucion = u.GetKeyboardLayout(u.GetWindowThreadProcessId(ventana, None))
        salida = ctypes.create_unicode_buffer(8)
        n = u.ToUnicodeEx(vk, scan, estado, salida, len(salida), _NO_CAMBIAR_ESTADO, distribucion)
        if n < 0:
            return None                     # tecla muerta (acento pendiente)
        return salida.value[:n] if n else '\x00'
