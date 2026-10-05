import pytest

pytest.importorskip('customtkinter')
from fraseya.aplicacion.autenticacion import Autenticacion
from fraseya.infraestructura import RepositorioSQLite
from fraseya.aplicacion.gestion_frases import GestionFrases
from fraseya.presentacion.acceso import VentanaAcceso, VentanaUsuarios
from fraseya.presentacion.ventana_principal import VentanaPrincipal


def test_acceso_crear_admin_y_alta_usuario(tmp_path, monkeypatch):
    auth = Autenticacion(tmp_path / 'usuarios.db')
    try:
        acceso = VentanaAcceso(auth)
        acceso.withdraw()
        acceso.usuario.insert(0, 'Bayron')
        acceso.clave.insert(0, 'contraseña-prueba')
        acceso.repetida.insert(0, 'contraseña-prueba')
        acceso.entrar()
        assert acceso.sesion.rol == 'administrador'
        with RepositorioSQLite(':memory:') as repo:
            ventana = VentanaPrincipal(GestionFrases(repo), autenticacion=auth, sesion=acceso.sesion)
            ventana.withdraw()
            alta = VentanaUsuarios(ventana, auth, acceso.sesion)
            alta.withdraw()
            try:
                alta.usuario.insert(0, 'Diego')
                alta.clave.insert(0, 'contraseña-usuario')
                alta.repetida.insert(0, 'contraseña-usuario')
                alta.crear()
                assert alta.mensaje.cget('text') == 'Cuenta creada.'
                assert auth.iniciar_sesion('Diego', 'contraseña-usuario').rol == 'usuario'
                fila = next(i for i in alta.tabla.get_children() if alta.tabla.item(i, 'values')[0] == 'Diego')
                alta.tabla.selection_set(fila)
                alta.seleccionar()
                alta.rol.set('administrador')
                alta.guardar()
                assert auth.iniciar_sesion('Diego', 'contraseña-usuario').rol == 'administrador'
                fila = next(i for i in alta.tabla.get_children() if alta.tabla.item(i, 'values')[0] == 'Diego')
                alta.tabla.selection_set(fila)
                alta.seleccionar()
                from fraseya.presentacion import acceso as modulo
                monkeypatch.setattr(modulo.messagebox, 'askyesno', lambda *args, **kwargs: False)
                alta.eliminar()
                assert len(auth.listar_usuarios(acceso.sesion)) == 2
                monkeypatch.setattr(modulo.messagebox, 'askyesno', lambda *args, **kwargs: True)
                alta.eliminar()
                assert len(auth.listar_usuarios(acceso.sesion)) == 1
            finally:
                alta.destroy()
                ventana.destroy()
    finally:
        auth.cerrar()


def test_usuario_no_puede_borrar_desde_ventana(tmp_path):
    auth = Autenticacion(tmp_path / 'usuarios.db')
    try:
        auth.crear_administrador_inicial('admin', 'contraseña-admin')
        admin = auth.iniciar_sesion('admin', 'contraseña-admin')
        auth.crear_usuario(admin, 'usuario', 'contraseña-usuario')
        sesion = auth.iniciar_sesion('usuario', 'contraseña-usuario')
        with RepositorioSQLite(':memory:') as repo:
            ventana = VentanaPrincipal(GestionFrases(repo), autenticacion=auth, sesion=sesion)
            ventana.withdraw()
            try:
                ventana.eliminar_del_catalogo()
                assert 'Solo el administrador' in ventana.estado_publicacion.cget('text')
                with pytest.raises(PermissionError):
                    VentanaUsuarios(ventana, auth, sesion)
            finally:
                ventana.destroy()
    finally:
        auth.cerrar()
