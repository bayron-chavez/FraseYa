import json
import unittest
from unittest.mock import Mock

from fraseya.aplicacion.formato_catalogo import serializar
from fraseya.aplicacion.publicacion_supabase import PublicacionSupabase
from fraseya.aplicacion.servicio_sincronizacion import ServicioSincronizacion
from fraseya.infraestructura.repositorio_sqlite import RepositorioSQLite
from fraseya.infraestructura.supabase import (
    ClienteSupabase, AutenticacionSupabase, RepositorioSupabase, ErrorSupabase, validar_conexion)

URL = 'https://ejemplo.supabase.co'
KEY = 'sb_publishable_clave_de_prueba'
CATEGORIAS = [{'nombre': 'General', 'color': '#123456', 'frases': [
    {'titulo': 'Saludo', 'abreviatura': '!hola', 'contenido': 'Hola {nombre}'}]}]


def snapshot(version=1, categorias=CATEGORIAS):
    datos, meta = serializar(categorias, version, 'admin@example.test', '2026-10-05T12:00:00Z')
    return [{'contenido': datos.decode(), 'metadata': json.loads(meta)}]


class SupabaseTests(unittest.TestCase):
    def setUp(self):
        self.transporte = Mock()
        self.cliente = ClienteSupabase(URL, KEY, self.transporte, reloj=lambda: 100)
        self.cliente._guardar_tokens({'access_token': 'sesion-de-prueba',
            'refresh_token': 'refresh-de-prueba', 'expires_in': 3600})
        self.repo = RepositorioSQLite(':memory:')
        self.addCleanup(self.repo.cerrar)
        self.lector = RepositorioSupabase(self.cliente)
        self.sync = ServicioSincronizacion(self.repo, crear_lector=lambda: self.lector)

    def test_rechaza_claves_privilegiadas_y_url_insegura(self):
        for clave in ['sb_secret_privilegiada', 'password', '']:
            with self.assertRaises(ValueError):
                validar_conexion(URL, clave)
        with self.assertRaises(ValueError):
            validar_conexion('http://ejemplo.supabase.co', KEY)
        with self.assertRaises(ValueError):
            validar_conexion('https://usuario:clave@ejemplo.supabase.co', KEY)

    def test_lee_y_verifica_snapshot(self):
        self.transporte.return_value = snapshot()
        version, categorias = self.lector.leer()
        self.assertEqual(version.version, 1)
        self.assertEqual(categorias, CATEGORIAS)
        self.assertEqual(self.transporte.call_args.args[3]['Authorization'], 'Bearer sesion-de-prueba')

    def test_catalogo_inicial_sin_publicar(self):
        self.transporte.return_value = [{'contenido': None, 'metadata': None}]
        self.assertIsNone(self.lector.leer_version())

    def test_integridad_y_fallo_red_conservan_cache(self):
        self.transporte.return_value = snapshot()
        self.assertEqual(self.sync.sincronizar().estado, 'actualizada')
        antes = self.repo.listar_frases()
        alterado = snapshot(2)
        alterado[0]['contenido'] += ' '
        self.transporte.return_value = alterado
        self.assertEqual(self.sync.sincronizar().estado, 'error')
        self.transporte.side_effect = ErrorSupabase('Sin conexión')
        self.assertEqual(self.sync.sincronizar().estado, 'error')
        self.assertEqual(self.repo.listar_frases(), antes)

    def test_nuevo_origen_admite_version_menor_y_conserva_propias(self):
        self.repo.reemplazar_compartidas(23, 'local', None, CATEGORIAS)
        cat = self.repo.crear_catalogo('Mis frases')
        categoria = self.repo.crear_categoria(cat, 'Personal')
        ident = self.repo.crear_frase(categoria, 'Personal', '!personal', 'Mi texto')
        propia = self.repo.obtener_frase(ident)
        self.transporte.return_value = snapshot(1)
        self.assertEqual(self.sync.sincronizar().version, 1)
        self.assertEqual(self.repo.obtener_frase(ident), propia)
        self.assertEqual(self.repo.leer_configuracion('origen_sincronizado'), self.lector.identificador)
        self.assertEqual(self.sync.sincronizar().estado, 'sin_cambios')

    def test_conflicto_personal_rechaza_toda_actualizacion(self):
        cat = self.repo.crear_catalogo('Mis frases')
        categoria = self.repo.crear_categoria(cat, 'Personal')
        self.repo.crear_frase(categoria, 'Personal', '!HOLA', 'Hola {nombre}')
        self.transporte.return_value = snapshot()
        self.assertEqual(self.sync.sincronizar().estado, 'error')
        self.assertEqual(self.repo.listar_frases('compartida'), [])
        self.assertEqual(self.repo.leer_configuracion('origen_sincronizado', ''), '')

    def test_renueva_sesion_y_no_guarda_credenciales(self):
        self.cliente._vence = 110
        self.transporte.side_effect = [
            {'access_token': 'nueva', 'refresh_token': 'nuevo-refresh', 'expires_in': 3600}, snapshot()]
        self.assertEqual(self.lector.leer_version().version, 1)
        llamadas = self.transporte.call_args_list
        self.assertNotIn('Authorization', llamadas[0].args[3])
        self.assertEqual(llamadas[1].args[3]['Authorization'], 'Bearer nueva')

    def test_login_y_modo_offline_sin_privilegios(self):
        auth = AutenticacionSupabase(self.cliente)
        self.transporte.side_effect = [
            {'access_token': 'nuevo', 'refresh_token': 'nuevo-refresh', 'expires_in': 3600},
            [{'id': 'uuid', 'correo': 'admin@example.test', 'rol': 'administrador'}]]
        sesion = auth.iniciar_sesion('admin@example.test', 'clave-ficticia')
        self.assertEqual(sesion.rol, 'administrador')
        offline = auth.sin_conexion()
        auth.validar(offline)
        with self.assertRaises(PermissionError):
            auth.validar(offline, administrador=True)
        with self.assertRaises(ErrorSupabase):
            self.lector.leer()

    def test_publicacion_conserva_anteriores_y_envia_version_esperada(self):
        auth = Mock()
        auth.cliente = self.cliente
        sesion = Mock(usuario='admin@example.test')
        servicio = PublicacionSupabase(self.repo, auth, sesion)
        self.transporte.return_value = snapshot(3)
        aporte = [{'nombre': 'General', 'color': '#123456', 'frases': [
            {'titulo': 'Adiós', 'abreviatura': '!adios', 'contenido': 'Hasta luego'}]}]
        vista = servicio.preparar(aporte)
        self.assertEqual(vista.cantidad_frases, 2)
        self.transporte.return_value = json.loads(vista.metadata)
        self.assertEqual(servicio.publicar(vista).version, 4)
        enviado = json.loads(self.transporte.call_args.args[2])
        self.assertEqual(enviado['p_version_anterior'], 3)
        self.assertEqual(len(json.loads(enviado['p_contenido'])['categorias'][0]['frases']), 2)

    def test_publicacion_sin_rol_admin_no_envia_catalogo(self):
        auth = Mock()
        auth.cliente = self.cliente
        auth.validar.side_effect = PermissionError('Solo administrador')
        servicio = PublicacionSupabase(self.repo, auth, Mock(usuario='usuario@example.test'))
        with self.assertRaises(PermissionError):
            servicio.preparar(CATEGORIAS)
        self.transporte.assert_not_called()

    def test_eliminacion_explicita_y_catalogo_vacio_confirmado(self):
        auth = Mock()
        auth.cliente = self.cliente
        servicio = PublicacionSupabase(self.repo, auth, Mock(usuario='admin@example.test'))
        self.transporte.return_value = snapshot(1)
        vista = servicio.preparar([], eliminar=('!hola',))
        self.assertEqual(vista.eliminadas, 1)
        self.assertEqual(vista.cantidad_frases, 0)
        with self.assertRaises(ValueError):
            servicio.publicar(vista)
        self.transporte.return_value = json.loads(vista.metadata)
        self.assertEqual(servicio.publicar(vista, confirmar_vacio=True).version, 2)

    def test_respuesta_publicacion_alterada_no_confirma_exito(self):
        auth = Mock()
        auth.cliente = self.cliente
        servicio = PublicacionSupabase(self.repo, auth, Mock(usuario='admin@example.test'))
        self.transporte.return_value = snapshot(1)
        vista = servicio.preparar([])
        self.transporte.return_value = {**json.loads(vista.metadata), 'version': 99}
        with self.assertRaisesRegex(ValueError, 'no coincide'):
            servicio.publicar(vista)


if __name__ == '__main__':
    unittest.main()
