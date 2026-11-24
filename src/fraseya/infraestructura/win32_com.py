"""Primitivas y estructuras Win32 compartidas por teclado, escritor y UIA (solo Windows)."""
import ctypes
from ctypes import wintypes
import sys

_CLASE_RENDER_CHROMIUM = 'Chrome_RenderWidgetHostHWND'
_GA_ROOT = 2

_KEYEVENTF_KEYUP = 0x0002
_KEYEVENTF_UNICODE = 0x0004
_INPUT_MOUSE = 0
_INPUT_KEYBOARD = 1


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ('dx', wintypes.LONG),
        ('dy', wintypes.LONG),
        ('mouseData', wintypes.DWORD),
        ('dwFlags', wintypes.DWORD),
        ('time', wintypes.DWORD),
        ('dwExtraInfo', ctypes.c_size_t),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ('wVk', wintypes.WORD),
        ('wScan', wintypes.WORD),
        ('dwFlags', wintypes.DWORD),
        ('time', wintypes.DWORD),
        ('dwExtraInfo', ctypes.c_size_t),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [('ki', KEYBDINPUT), ('mi', MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [('type', wintypes.DWORD), ('u', INPUT_UNION)]


class VARIANT(ctypes.Structure):
    """Estructura VARIANT compatible con Windows x64 (24B) y x86 (16B)."""
    _fields_ = (
        [
            ('vt', ctypes.c_ushort),
            ('wReserved1', ctypes.c_ushort),
            ('wReserved2', wintypes.WORD),
            ('wReserved3', ctypes.c_ushort),
            ('lVal', ctypes.c_longlong),
            ('extra', ctypes.c_longlong),
        ]
        if ctypes.sizeof(ctypes.c_void_p) == 8
        else [
            ('vt', ctypes.c_ushort),
            ('wReserved1', ctypes.c_ushort),
            ('wReserved2', ctypes.c_ushort),
            ('wReserved3', ctypes.c_ushort),
            ('lVal', ctypes.c_longlong),
        ]
    )


def user32(*, exigir_windows: bool = True):
    """Devuelve user32.dll con firmas configuradas."""
    if sys.platform != 'win32':
        if exigir_windows:
            raise OSError('Esta funcionalidad solo está disponible en Windows.')
        return None
    u = ctypes.WinDLL('user32', use_last_error=True)
    u.GetForegroundWindow.restype = wintypes.HWND
    u.SetForegroundWindow.argtypes = [wintypes.HWND]
    u.BringWindowToTop.argtypes = [wintypes.HWND]
    u.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    u.GetAsyncKeyState.argtypes = [ctypes.c_int]
    u.GetKeyState.argtypes = [ctypes.c_int]
    u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    u.GetWindowThreadProcessId.restype = wintypes.DWORD
    u.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    u.GetWindowTextLengthW.restype = ctypes.c_int
    u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    u.GetWindowTextW.restype = ctypes.c_int
    u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    u.GetWindowRect.restype = wintypes.BOOL
    u.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    u.GetClassNameW.restype = ctypes.c_int
    u.IsWindowVisible.argtypes = [wintypes.HWND]
    u.IsWindowVisible.restype = wintypes.BOOL
    u.WindowFromPoint.argtypes = [wintypes.POINT]
    u.WindowFromPoint.restype = wintypes.HWND
    u.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    u.GetAncestor.restype = wintypes.HWND
    u.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    u.SendInput.restype = wintypes.UINT
    u.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
    u.MapVirtualKeyW.restype = wintypes.UINT
    u.GetKeyboardLayout.argtypes = [wintypes.DWORD]
    u.GetKeyboardLayout.restype = wintypes.HKL
    u.ToUnicodeEx.argtypes = [
        wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_ubyte),
        wintypes.LPWSTR, ctypes.c_int, wintypes.UINT, wintypes.HKL,
    ]
    return u


def ventana_activa():
    """Identificador de la ventana que tiene el foco ahora mismo."""
    return user32().GetForegroundWindow()


def forzar_primer_plano(ventana):
    """Trae una ventana nuestra al frente aunque otra aplicación tenga el foco."""
    u = user32()
    k = ctypes.WinDLL('kernel32')
    activa = u.GetForegroundWindow()
    hilo_activo = u.GetWindowThreadProcessId(activa, None) if activa else 0
    hilo_propio = k.GetCurrentThreadId()
    unido = (
        bool(hilo_activo)
        and hilo_activo != hilo_propio
        and bool(u.AttachThreadInput(hilo_propio, hilo_activo, True))
    )
    try:
        u.BringWindowToTop(ventana)
        u.SetForegroundWindow(ventana)
    finally:
        if unido:
            u.AttachThreadInput(hilo_propio, hilo_activo, False)


def activar_ventana(ventana):
    """Devuelve el foco a una ventana (después de que un formulario lo quitó)."""
    if not ventana:
        return
    try:
        forzar_primer_plano(ventana)
    except OSError:
        user32().SetForegroundWindow(ventana)


def pid_ventana(hwnd: int) -> int:
    if sys.platform != 'win32' or not hwnd:
        return 0
    try:
        u = user32(exigir_windows=False)
        if u is None or not hasattr(u, 'GetWindowThreadProcessId'):
            return 0
        pid = wintypes.DWORD(0)
        u.GetWindowThreadProcessId(wintypes.HWND(int(hwnd)), ctypes.byref(pid))
        return int(pid.value)
    except (OSError, ctypes.ArgumentError, ValueError):
        return 0


def info_punto_win32(x: int, y: int) -> tuple[int, int]:
    """Devuelve (pid, hwnd_raiz) de la ventana en pantalla en (x, y)."""
    if sys.platform != 'win32':
        return (0, 0)
    try:
        u = user32(exigir_windows=False)
        if u is None or not hasattr(u, 'WindowFromPoint'):
            return (0, 0)
        h = u.WindowFromPoint(wintypes.POINT(int(x), int(y)))
        if not h:
            return (0, 0)
        pid = wintypes.DWORD(0)
        u.GetWindowThreadProcessId(h, ctypes.byref(pid))
        raiz = u.GetAncestor(h, _GA_ROOT) or h
        return (int(pid.value), int(raiz))
    except (OSError, ctypes.ArgumentError, ValueError):
        return (0, 0)


def rect_hwnd_win32(hwnd: int) -> tuple[int, int, int, int]:
    if sys.platform != 'win32' or not hwnd:
        return (0, 0, 0, 0)
    try:
        u = user32(exigir_windows=False)
        if u is None:
            return (0, 0, 0, 0)
        rc = wintypes.RECT()
        if not u.GetWindowRect(wintypes.HWND(int(hwnd)), ctypes.byref(rc)):
            return (0, 0, 0, 0)
        return (int(rc.left), int(rc.top), int(rc.right), int(rc.bottom))
    except (OSError, ctypes.ArgumentError, ValueError):
        return (0, 0, 0, 0)


def hwnd_render_chat(hwnd: int) -> int:
    """Busca el HWND hijo Chrome_RenderWidgetHostHWND (WebView2/Chromium) para evitar el shell."""
    if sys.platform != 'win32' or not hwnd:
        return int(hwnd or 0)
    hwnd_int = int(hwnd)
    try:
        u = user32(exigir_windows=False)
        if u is None or not hasattr(u, 'EnumChildWindows') or not hasattr(u, 'GetClassNameW'):
            return hwnd_int
        enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        u.EnumChildWindows.argtypes = [wintypes.HWND, enum_proc, wintypes.LPARAM]
        u.EnumChildWindows.restype = wintypes.BOOL

        candidatos: list[tuple[int, int, int]] = []
        buf = ctypes.create_unicode_buffer(128)

        def _callback(child_hwnd, _lparam):
            try:
                largo = u.GetClassNameW(child_hwnd, buf, 128)
                if largo > 0 and buf.value == _CLASE_RENDER_CHROMIUM:
                    vis = 1 if u.IsWindowVisible(child_hwnd) else 0
                    rc = wintypes.RECT()
                    area = 0
                    if u.GetWindowRect(child_hwnd, ctypes.byref(rc)):
                        area = max(0, int(rc.right - rc.left)) * max(0, int(rc.bottom - rc.top))
                    candidatos.append((vis, area, int(child_hwnd)))
            except (OSError, ctypes.ArgumentError, ValueError):
                pass
            return True

        cb = enum_proc(_callback)
        u.EnumChildWindows(wintypes.HWND(hwnd_int), cb, 0)
        if not candidatos:
            return hwnd_int
        candidatos.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return candidatos[0][2]
    except (OSError, ctypes.ArgumentError, ValueError):
        return hwnd_int
