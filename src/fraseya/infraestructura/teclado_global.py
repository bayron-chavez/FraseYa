"""Captura global del teclado (Windows) para el motor de expansión.

Todo el procesamiento ocurre dentro del filtro del hook de forma sincrónica antes
de que la tecla llegue a la aplicación. Las teclas inyectadas se ignoran.
"""
import ctypes
import threading
import time

from .win32_com import activar_ventana, forzar_primer_plano, user32, ventana_activa

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

_user32 = user32


def interpretar_atajo(texto):
    """'ctrl+alt+espacio' -> (frozenset({'ctrl', 'alt'}), código de la tecla)."""
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


class TecladoGlobal:
    def __init__(self, motor, tecla_confirmacion=TECLA_PREDETERMINADA, atajo=None, al_atajo=None):
        """atajo: p. ej. 'ctrl+alt+espacio'; al_atajo se llama (rápido, sin bloquear) al pulsarlo."""
        if tecla_confirmacion not in TECLAS_CONFIRMACION:
            raise ValueError(
                f'Tecla de confirmación no válida: {tecla_confirmacion}. '
                f'Opciones: {", ".join(TECLAS_CONFIRMACION)}.'
            )
        self.motor = motor
        self.tecla_confirmacion = tecla_confirmacion
        self._vk_confirmacion = TECLAS_CONFIRMACION[tecla_confirmacion]
        self._atajo = interpretar_atajo(atajo) if atajo else None
        self.al_atajo = al_atajo
        self.pausado = False
        self._soltar = set()
        self._teclado = None
        self._raton = None
        self._u = None
        self._candado_clic = threading.Lock()
        self._pegado_pendiente = None

    def armar_pegado_al_clic(self, callback, timeout_seg: float = 10.0):
        """Arma una única ejecución de `callback()` tras el próximo clic izquierdo."""
        if not callable(callback):
            return
        expira = time.monotonic() + max(1.0, float(timeout_seg))
        with self._candado_clic:
            self._pegado_pendiente = (callback, expira)

    def desarmar_pegado_al_clic(self):
        with self._candado_clic:
            self._pegado_pendiente = None

    def _al_clic_raton(self, x, y, button, pressed):
        self.motor.reiniciar()
        if pressed:
            return
        nombre_btn = getattr(button, 'name', str(button)).lower()
        if 'left' not in nombre_btn:
            return
        pendiente = None
        with self._candado_clic:
            if self._pegado_pendiente is not None:
                cb, expira = self._pegado_pendiente
                self._pegado_pendiente = None
                if time.monotonic() <= expira:
                    pendiente = cb
        if pendiente is not None:
            threading.Thread(target=pendiente, daemon=True, name='fraseya-pegar-clic').start()

    def configurar(self, tecla_confirmacion=None, atajo=None):
        """Cambia la tecla de confirmación y/o el atajo sin reiniciar."""
        if tecla_confirmacion is not None and tecla_confirmacion not in TECLAS_CONFIRMACION:
            raise ValueError(f'Tecla de confirmación no válida: {tecla_confirmacion}.')
        nuevo_atajo = interpretar_atajo(atajo) if atajo else None
        if tecla_confirmacion is not None:
            self.tecla_confirmacion = tecla_confirmacion
            self._vk_confirmacion = TECLAS_CONFIRMACION[tecla_confirmacion]
        if nuevo_atajo is not None:
            self._atajo = nuevo_atajo

    def iniciar(self):
        from pynput import keyboard, mouse
        self._u = _user32()
        self._teclado = keyboard.Listener(win32_event_filter=self._filtro)
        self._raton = mouse.Listener(on_click=self._al_clic_raton)
        self._teclado.start()
        self._raton.start()

    def detener(self):
        self.desarmar_pegado_al_clic()
        for oyente in (self._teclado, self._raton):
            if oyente is not None:
                oyente.stop()
        self._teclado = self._raton = None

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
            if vk in self._soltar:
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
            self.motor.reiniciar()
        return False

    def _modificadores(self):
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
                pass

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
                return
            if letra.isprintable() and not letra.isspace():
                self.motor.caracter(letra)
            else:
                self.motor.reiniciar()

    def _a_caracter(self, vk, scan):
        u = self._u
        estado = (ctypes.c_ubyte * 256)()
        ctrl = bool(u.GetAsyncKeyState(_VK_CONTROL) & 0x8000)
        alt = bool(u.GetAsyncKeyState(_VK_MENU) & 0x8000)
        if ctrl and not alt:
            return '\x00'
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
            return None
        return salida.value[:n] if n else '\x00'


__all__ = [
    'ATAJO_PREDETERMINADO',
    'TECLAS_CONFIRMACION',
    'TECLA_PREDETERMINADA',
    'TecladoGlobal',
    'activar_ventana',
    'forzar_primer_plano',
    'interpretar_atajo',
    'ventana_activa',
]
