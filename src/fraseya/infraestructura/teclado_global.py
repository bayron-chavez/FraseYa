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
ATAJO_PREDETERMINADO = 'ctrl+alt+espacio'
_MODIFICADORES_ATAJO = {'ctrl': 0x11, 'alt': 0x12, 'shift': 0x10}   # win se consulta aparte

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
    u.GetParent.argtypes = [wintypes.HWND]
    u.GetParent.restype = wintypes.HWND
    u.BringWindowToTop.argtypes = [wintypes.HWND]
    u.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    u.GetKeyboardLayout.argtypes = [wintypes.DWORD]
    u.GetKeyboardLayout.restype = wintypes.HKL
    u.ToUnicodeEx.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_ubyte),
                              wintypes.LPWSTR, ctypes.c_int, wintypes.UINT, wintypes.HKL]
    return u


def interpretar_atajo(texto):
    """'ctrl+alt+espacio' -> (frozenset({'ctrl', 'alt'}), código de la tecla).

    Exige al menos un modificador (si no, se tragaría el teclado normal) y una
    tecla: espacio, una letra o dígito, o F1 a F12.
    """
    partes = [p.strip().lower() for p in (texto or '').split('+') if p.strip()]
    if len(partes) < 2:
        raise ValueError(f'Atajo no válido: "{texto}". Ejemplo: ctrl+alt+espacio.')
    *modificadores, tecla = partes
    if len(set(modificadores)) != len(modificadores) or \
            any(m not in (*_MODIFICADORES_ATAJO, 'win') for m in modificadores):
        raise ValueError(f'Modificadores no válidos en "{texto}". Usa ctrl, alt, shift o win.')
    if tecla == 'espacio':
        vk = 0x20
    elif len(tecla) == 1 and tecla.isascii() and tecla.isalnum():
        vk = ord(tecla.upper())
    elif tecla.startswith('f') and tecla[1:].isdigit() and 1 <= int(tecla[1:]) <= 12:
        vk = 0x70 + int(tecla[1:]) - 1
    else:
        raise ValueError(f'Tecla no válida en "{texto}". Usa espacio, una letra, un dígito o F1-F12.')
    return frozenset(modificadores), vk


def hwnd_de(ventana_tk):
    """Identificador real (de nivel superior) de una ventana de Tkinter."""
    return _user32().GetParent(ventana_tk.winfo_id()) or ventana_tk.winfo_id()


def forzar_primer_plano(ventana):
    """Trae una ventana nuestra al frente aunque otra aplicación tenga el foco.

    Windows no deja que un proceso en segundo plano robe el foco; se evita
    uniendo temporalmente la cola de entrada con la de la ventana activa.
    """
    u = _user32()
    k = ctypes.WinDLL('kernel32')
    activa = u.GetForegroundWindow()
    hilo_activo = u.GetWindowThreadProcessId(activa, None) if activa else 0
    hilo_propio = k.GetCurrentThreadId()
    unido = bool(hilo_activo) and hilo_activo != hilo_propio and \
        bool(u.AttachThreadInput(hilo_propio, hilo_activo, True))
    try:
        u.BringWindowToTop(ventana)
        u.SetForegroundWindow(ventana)
    finally:
        if unido:
            u.AttachThreadInput(hilo_propio, hilo_activo, False)


def ventana_activa():
    """Identificador de la ventana que tiene el foco ahora mismo."""
    return _user32().GetForegroundWindow()


def activar_ventana(ventana):
    """Devuelve el foco a una ventana (después de que el formulario se lo quitó)."""
    _user32().SetForegroundWindow(ventana)


class TecladoGlobal:
    def __init__(self, motor, tecla_confirmacion=TECLA_PREDETERMINADA, atajo=None, al_atajo=None):
        """atajo: p. ej. 'ctrl+alt+espacio'; al_atajo se llama (rápido, sin bloquear) al pulsarlo."""
        if tecla_confirmacion not in TECLAS_CONFIRMACION:
            raise ValueError(f'Tecla de confirmación no válida: {tecla_confirmacion}. '
                             f'Opciones: {", ".join(TECLAS_CONFIRMACION)}.')
        self.motor = motor
        self.tecla_confirmacion = tecla_confirmacion
        self._vk_confirmacion = TECLAS_CONFIRMACION[tecla_confirmacion]
        self._atajo = interpretar_atajo(atajo) if atajo else None
        self.al_atajo = al_atajo
        self.pausado = False             # con el buscador abierto no se vigila lo que se escribe
        self._soltar = set()             # teclas cuyo "soltar" también hay que tragarse
        self._teclado = None
        self._raton = None
        self._u = None

    def configurar(self, tecla_confirmacion=None, atajo=None):
        """Cambia la tecla de confirmación y/o el atajo sin reiniciar.

        Valida todo antes de aplicar nada, así un valor inválido no deja el teclado a medias.
        """
        if tecla_confirmacion is not None and tecla_confirmacion not in TECLAS_CONFIRMACION:
            raise ValueError(f'Tecla de confirmación no válida: {tecla_confirmacion}.')
        nuevo_atajo = interpretar_atajo(atajo) if atajo else None
        if tecla_confirmacion is not None:
            self.tecla_confirmacion = tecla_confirmacion
            self._vk_confirmacion = TECLAS_CONFIRMACION[tecla_confirmacion]
        if nuevo_atajo is not None:
            self._atajo = nuevo_atajo

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
            vk = datos.vkCode
            if mensaje in (_WM_KEYUP, _WM_SYSKEYUP):
                if vk in self._soltar:
                    self._soltar.discard(vk)
                    self._teclado.suppress_event()
                return False
            if mensaje not in (_WM_KEYDOWN, _WM_SYSKEYDOWN):
                return False
            if vk in self._soltar:                    # repetición automática de una tecla ya tragada
                self._teclado.suppress_event()
            if self._atajo and vk == self._atajo[1] and self._modificadores() == self._atajo[0]:
                self._soltar.add(vk)
                if not self.pausado:
                    self._disparar_atajo()
                self._teclado.suppress_event()
            if self.pausado:
                return False
            if vk == self._vk_confirmacion:
                if self.motor.confirmar():
                    self._soltar.add(vk)
                    self._teclado.suppress_event()
                return False
            self._procesar(vk, datos.scanCode)
        except Exception as error:
            if type(error).__name__ == 'SuppressException':
                raise
            self.motor.reiniciar()   # ante cualquier duda, olvidar lo escrito
        return False

    def _modificadores(self):
        """Modificadores pulsados ahora: subconjunto de {'ctrl', 'alt', 'shift', 'win'}."""
        u = self._u
        activos = {n for n, vk in _MODIFICADORES_ATAJO.items() if u.GetAsyncKeyState(vk) & 0x8000}
        if u.GetAsyncKeyState(_VK_LWIN) & 0x8000 or u.GetAsyncKeyState(_VK_RWIN) & 0x8000:
            activos.add('win')
        return frozenset(activos)

    def _disparar_atajo(self):
        self.motor.reiniciar()
        if self.al_atajo is not None:
            try:
                self.al_atajo()
            except Exception:
                pass                        # un fallo del buscador no debe romper el hook

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
