from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from dataclasses import replace

from fraseya.aplicacion.autenticacion import Autenticacion


class AccesoTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.auth = Autenticacion(Path(self.temp.name) / 'usuarios.db')
        self.addCleanup(self.auth.cerrar)
        self.auth.crear_administrador_inicial('Bayron', 'contraseña-segura')
        self.admin = self.auth.iniciar_sesion('bayron', 'contraseña-segura')

    def test_login_y_clave_no_guardada_en_texto(self):
        self.assertEqual(self.admin.rol, 'administrador')
        fila = self.auth.db.execute('SELECT sal,clave FROM usuario').fetchone()
        self.assertNotEqual(fila[1], b'contrase\xc3\xb1a-segura')
        with self.assertRaises(PermissionError):
            self.auth.iniciar_sesion('Bayron', 'incorrecta')
        with self.assertRaises(PermissionError):
            self.auth.crear_administrador_inicial('Otra', 'contraseña-segura')

    def test_usuario_no_puede_crear_cuentas_ni_elevar_rol(self):
        self.auth.crear_usuario(self.admin, 'Diego', 'otra-contraseña')
        usuario = self.auth.iniciar_sesion('Diego', 'otra-contraseña')
        with self.assertRaises(PermissionError):
            self.auth.validar(usuario, administrador=True)
        with self.assertRaises(PermissionError):
            self.auth.validar(replace(usuario, rol='administrador'), administrador=True)
        with self.assertRaises(PermissionError):
            self.auth.crear_usuario(usuario, 'Otra', 'contraseña-segura')
        self.auth.salir(self.admin)
        with self.assertRaises(PermissionError):
            self.auth.validar(self.admin, administrador=True)

    def test_crud_cuenta_y_revocacion(self):
        self.auth.crear_usuario(self.admin, 'Diego', 'otra-contraseña')
        sesion = self.auth.iniciar_sesion('Diego', 'otra-contraseña')
        self.assertEqual(self.auth.listar_usuarios(self.admin)[1], {'nombre': 'Diego', 'rol': 'usuario'})
        self.auth.actualizar_usuario(self.admin, 'Diego', 'DiegoAdmin', 'administrador', 'nueva-contraseña')
        with self.assertRaises(PermissionError):
            self.auth.validar(sesion)
        with self.assertRaises(PermissionError):
            self.auth.iniciar_sesion('DiegoAdmin', 'otra-contraseña')
        nueva = self.auth.iniciar_sesion('DiegoAdmin', 'nueva-contraseña')
        self.assertEqual(nueva.rol, 'administrador')
        self.auth.actualizar_usuario(self.admin, 'DiegoAdmin', 'DiegoAdmin', 'usuario')
        self.assertEqual(self.auth.iniciar_sesion('DiegoAdmin', 'nueva-contraseña').rol, 'usuario')
        self.auth.eliminar_usuario(self.admin, 'DiegoAdmin')
        with self.assertRaises(PermissionError):
            self.auth.iniciar_sesion('DiegoAdmin', 'nueva-contraseña')

    def test_proteger_cuenta_actual_y_validacion_atomica(self):
        with self.assertRaises(ValueError):
            self.auth.eliminar_usuario(self.admin, 'Bayron')
        with self.assertRaises(ValueError):
            self.auth.actualizar_usuario(self.admin, 'Bayron', 'Bayron', 'usuario')
        self.auth.crear_usuario(self.admin, 'Diego', 'otra-contraseña')
        with self.assertRaises(ValueError):
            self.auth.actualizar_usuario(self.admin, 'Diego', 'bayron', 'administrador')
        self.assertEqual(self.auth.iniciar_sesion('Diego', 'otra-contraseña').rol, 'usuario')
        with self.assertRaises(ValueError):
            self.auth.actualizar_usuario(self.admin, 'Diego', 'Diego', 'administrador', 'corta')

    def test_usuario_no_puede_usar_crud(self):
        self.auth.crear_usuario(self.admin, 'Diego', 'otra-contraseña')
        usuario = self.auth.iniciar_sesion('Diego', 'otra-contraseña')
        for accion in (lambda: self.auth.listar_usuarios(usuario),
                       lambda: self.auth.actualizar_usuario(usuario, 'Bayron', 'Bayron', 'usuario'),
                       lambda: self.auth.eliminar_usuario(usuario, 'Bayron')):
            with self.assertRaises(PermissionError):
                accion()
