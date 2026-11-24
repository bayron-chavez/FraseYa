"""Recursos de marca compartidos por la aplicación."""
import sys
from pathlib import Path


def recurso(nombre):
    raiz = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[3]))
    return raiz / 'assets' / nombre
