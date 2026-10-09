"""Recursos de marca compartidos por la aplicación y el portable."""
import sys
from pathlib import Path
import tkinter as tk


def recurso(nombre):
    raiz = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[3]))
    return raiz / 'assets' / nombre


def configurar_icono(ventana):
    # CustomTkinter aplica su icono con retraso; aplicar después el de FraseYa.
    def aplicar():
        if ventana.winfo_exists():
            try:
                ventana.iconbitmap(str(recurso('fraseya.ico')))
            except tk.TclError:
                pass
    ventana.after(300, aplicar)
