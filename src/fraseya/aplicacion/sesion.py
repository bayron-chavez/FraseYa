"""Identidad de sesión en memoria; no contiene la contraseña ni el JWT."""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

_HUELLA_RE = re.compile(r'^[0-9a-f]{24}$')


@dataclass(frozen=True)
class Sesion:
    usuario: str
    rol: str
    token: str


def _huella_usuario(usuario: str) -> str:
    return hashlib.sha256(usuario.strip().casefold().encode('utf-8')).hexdigest()[:24]


def _ruta_ultimo_perfil(base: Path) -> Path:
    return base.parent / 'usuarios' / 'ultimo_perfil'


def registrar_ultimo_perfil(ruta_base, sesion) -> None:
    """Guarda solo la huella SHA-256 del último usuario autenticado para uso offline."""
    if ruta_base is None or str(ruta_base) == ':memory:':
        return
    if sesion is None or getattr(sesion, 'token', None) == 'offline':
        return
    usuario = getattr(sesion, 'usuario', '')
    if not isinstance(usuario, str) or not usuario.strip():
        return
    puntero = _ruta_ultimo_perfil(Path(ruta_base))
    puntero.parent.mkdir(parents=True, exist_ok=True)
    puntero.write_text(_huella_usuario(usuario), encoding='utf-8')


def ruta_bd_sesion(ruta_base, sesion):
    """Devuelve la ruta SQLite aislada por correo (online) o la copia local vigente (offline).

    - Las rutas `:memory:` conservan `ruta_base`.
    - Las sesiones online usan `usuarios/<sha256[:24]>.db` para aislar por correo
      sin exponer direcciones en disco ni permitir path traversal.
    - El modo sin conexión abre la copia del último perfil autenticado si existe;
      si nunca hubo sesión online previa, usa `ruta_base`.
    """
    if ruta_base is None or str(ruta_base) == ':memory:':
        return ruta_base
    base = Path(ruta_base)
    if sesion is None or getattr(sesion, 'token', None) == 'offline':
        puntero = _ruta_ultimo_perfil(base)
        if puntero.is_file():
            huella = puntero.read_text(encoding='utf-8').strip()
            if _HUELLA_RE.fullmatch(huella):
                candidata = base.parent / 'usuarios' / f'{huella}.db'
                if candidata.is_file():
                    return candidata
        return base
    usuario = getattr(sesion, 'usuario', '')
    if not isinstance(usuario, str) or not usuario.strip():
        return base
    return base.parent / 'usuarios' / f'{_huella_usuario(usuario)}.db'
