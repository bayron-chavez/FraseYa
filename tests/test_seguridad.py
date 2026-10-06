import json
import unittest
from unittest.mock import Mock
from urllib.request import Request
from pathlib import Path
from tempfile import TemporaryDirectory

from fraseya.aplicacion.sesion import Sesion
from fraseya.infraestructura.supabase import (
    validar_conexion, ClienteSupabase, AutenticacionSupabase, SinRedirecciones,
    ErrorSupabase, cargar_cliente)
from fraseya.infraestructura import RepositorioSQLite


class SeguridadTests(unittest.TestCase):
    def test_url_no_envia_credenciales_a_servidor_ajeno(self):
        for url in ['https://atacante.test', 'https://ejemplo.supabase.co.atacante.test',
                    'https://ejemplo.supabase.co:443', 'https://127.0.0.1',
                    'https://ejemplo.supabase.co/ruta', 'https://ejemplo.supabase.co@atacante.test']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                validar_conexion(url, 'sb_publishable_prueba')

    def test_redireccion_no_reenvia_jwt(self):
        peticion = Request('https://ejemplo.supabase.co/auth/v1/token',
            headers={'Authorization': 'Bearer secreto-de-prueba'})
        with self.assertRaises(ErrorSupabase):
            SinRedirecciones().redirect_request(peticion, None, 302, '', {}, 'https://atacante.test')

    def test_sesion_anterior_no_revive_con_misma_cuenta(self):
        cliente = Mock()
        cliente.entrar.return_value = {'correo':'admin@example.test', 'rol':'administrador', 'id':'mismo-uuid'}
        auth = AutenticacionSupabase(cliente)
        anterior = auth.iniciar_sesion('admin@example.test', 'ficticia')
        auth.salir(anterior)
        actual = auth.iniciar_sesion('admin@example.test', 'ficticia')
        self.assertNotEqual(anterior.token, actual.token)
        with self.assertRaises(PermissionError):
            auth.validar(anterior)
        auth.validar(actual)

    def test_rol_manipulado_local_no_da_privilegios(self):
        cliente = Mock()
        cliente.entrar.return_value = {'correo':'u@example.test', 'rol':'usuario', 'id':'uuid'}
        auth = AutenticacionSupabase(cliente)
        sesion = auth.iniciar_sesion('u@example.test', 'ficticia')
        falsificada = Sesion(sesion.usuario, 'administrador', sesion.token)
        with self.assertRaises(PermissionError):
            auth.validar(falsificada, administrador=True)

    def test_admin_revocado_no_publica(self):
        cliente = Mock()
        cliente.entrar.return_value = {'correo':'a@example.test', 'rol':'administrador', 'id':'uuid'}
        cliente.perfil.return_value = {'rol':'usuario'}
        auth = AutenticacionSupabase(cliente)
        sesion = auth.iniciar_sesion('a@example.test', 'ficticia')
        with self.assertRaises(PermissionError):
            auth.validar(sesion, administrador=True)

    def test_falta_configuracion_no_crea_login_local(self):
        with TemporaryDirectory() as temp:
            with self.assertRaises(ErrorSupabase):
                cargar_cliente(Path(temp)/'supabase.json')

    def test_token_invalido_elimina_sesion(self):
        cliente = ClienteSupabase('https://ejemplo.supabase.co', 'sb_publishable_prueba')
        for respuesta in [{'access_token':'x\r\nHeader: z','refresh_token':'r','expires_in':3600},
                          {'access_token':'a','refresh_token':'r','expires_in':-1}, {}]:
            with self.assertRaises(ErrorSupabase):
                cliente._guardar_tokens(respuesta)
            self.assertIsNone(cliente._access)

    def test_inyeccion_sql_es_texto_no_comando(self):
        ataque = "'; DROP TABLE FRASE; --"
        with RepositorioSQLite(':memory:') as repo:
            cat = repo.crear_categoria(repo.crear_catalogo('Propias'), ataque)
            ident = repo.crear_frase(cat, ataque, 'ataque', ataque)
            self.assertEqual(repo.obtener_frase(ident)['contenido'], ataque)
            self.assertEqual(len(repo.listar_frases()), 1)
            repo.guardar_configuracion(ataque, ataque)
            self.assertEqual(repo.leer_configuracion(ataque), ataque)
            self.assertEqual(repo.db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_respuesta_http_401_descarta_tokens(self):
        cliente = ClienteSupabase('https://ejemplo.supabase.co', 'sb_publishable_prueba',
            transporte=Mock(side_effect=ErrorSupabase('No autorizado', 401)))
        cliente._guardar_tokens({'access_token':'a','refresh_token':'r','expires_in':3600})
        with self.assertRaises(ErrorSupabase):
            cliente.solicitar('GET', '/rest/v1/fraseya_catalogo')
        self.assertIsNone(cliente._access)
