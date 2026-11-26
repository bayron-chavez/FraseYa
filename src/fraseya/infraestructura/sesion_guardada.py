"""«Recordar sesión»: token de renovación cifrado con Windows DPAPI.

Solo la cuenta de Windows que lo guardó puede descifrarlo. Nunca se guarda la
contraseña ni el token de acceso.
"""
import ctypes
import json
from ctypes import wintypes
from pathlib import Path


class _Blob(ctypes.Structure):
    _fields_ = [('tam', wintypes.DWORD), ('datos', ctypes.POINTER(ctypes.c_char))]


def _dpapi(funcion, datos):
    if not hasattr(ctypes, 'WinDLL'):
        raise OSError('El cifrado de sesión requiere Windows.')
    crypt32 = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    buffer = ctypes.create_string_buffer(datos, len(datos))
    entrada = _Blob(len(datos), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    salida = _Blob()
    # 1 = CRYPTPROTECT_UI_FORBIDDEN
    if not getattr(crypt32, funcion)(ctypes.byref(entrada), None, None, None, None, 1,
                                     ctypes.byref(salida)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(salida.datos, salida.tam)
    finally:
        kernel32.LocalFree(salida.datos)


class SesionGuardada:
    def __init__(self, ruta):
        self.ruta = Path(ruta)

    def guardar(self, url, token):
        cifrado = _dpapi('CryptProtectData', json.dumps({'url': url, 'token': token}).encode('utf-8'))
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = self.ruta.with_suffix('.tmp')
        temporal.write_bytes(cifrado)
        temporal.replace(self.ruta)

    def leer(self, url):
        """Devuelve el token guardado para ese proyecto, o None."""
        if not self.ruta.is_file():
            return None
        try:
            datos = json.loads(_dpapi('CryptUnprotectData', self.ruta.read_bytes()))
            if datos['url'] != url or not isinstance(datos['token'], str):
                return None
            return datos['token'] or None
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def borrar(self):
        self.ruta.unlink(missing_ok=True)
