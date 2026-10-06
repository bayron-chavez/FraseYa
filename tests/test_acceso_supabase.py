from unittest.mock import Mock
import tkinter as tk
from fraseya.aplicacion.sesion import Sesion
from fraseya.presentacion.acceso import VentanaAcceso


def test_acceso_nube_no_crea_administrador_local_y_ofrece_offline():
    auth = Mock(nube=True)
    auth.tiene_usuarios.return_value = True
    auth.sin_conexion.return_value = Sesion('Modo sin conexión', 'usuario', 'offline')
    ventana = VentanaAcceso(auth)
    try:
        ventana.update_idletasks()
        assert ventana.usuario.cget('placeholder_text') == 'Correo de Supabase'
        ventana.sin_conexion()
        assert ventana.sesion.token == 'offline'
    finally:
        try:
            if ventana.winfo_exists():
                ventana.destroy()
        except tk.TclError:
            pass
