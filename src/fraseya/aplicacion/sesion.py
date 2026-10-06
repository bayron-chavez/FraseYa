"""Identidad de sesión en memoria; no contiene la contraseña ni el JWT."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Sesion:
    usuario: str
    rol: str
    token: str
