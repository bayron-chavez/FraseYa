"""Identidad de sesión en memoria; no contiene la contraseña ni el JWT."""
from dataclasses import dataclass
import hashlib
from pathlib import Path


@dataclass(frozen=True)
class Sesion:
    usuario: str
    rol: str
    token: str


def ruta_bd_sesion(ruta_base, sesion):
    """Devuelve una ruta SQLite aislada por correo para sesiones autenticadas online.

    Las rutas `:memory:` y el modo sin conexión conservan `ruta_base`.
    El nombre de archivo usa un hash SHA-256 del correo normalizado para evitar
    path traversal y no exponer direcciones de correo en disco.
    """
    if ruta_base is None or str(ruta_base) == ':memory:':
        return ruta_base
    base = Path(ruta_base)
    if sesion is None or getattr(sesion, 'token', None) == 'offline':
        return base
    usuario = getattr(sesion, 'usuario', '')
    if not isinstance(usuario, str) or not usuario.strip():
        return base
    huella = hashlib.sha256(usuario.strip().casefold().encode('utf-8')).hexdigest()[:24]
    return base.parent / 'usuarios' / f'{huella}.db'
