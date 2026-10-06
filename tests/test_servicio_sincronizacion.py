from threading import Event
from unittest.mock import Mock, patch
import unittest
from fraseya.aplicacion.formato_catalogo import serializar, leer_version
from fraseya.aplicacion.servicio_sincronizacion import ServicioSincronizacion
from fraseya.infraestructura import RepositorioSQLite


class SincronizacionTests(unittest.TestCase):
    def setUp(self):
        self.repo = RepositorioSQLite(':memory:')
        self.addCleanup(self.repo.cerrar)
        self.lector = Mock(identificador='supabase:https://ejemplo.supabase.co')
        self.lector.leer_version.return_value = None
        self.actualizar = Mock()
        self.servicio = ServicioSincronizacion(self.repo, lambda: self.lector, al_actualizar=self.actualizar)

    def publicar(self, numero, abreviatura='saludo'):
        categorias = [{'nombre': 'General', 'color': '#123456', 'frases': [
            {'titulo': 'Saludo', 'abreviatura': abreviatura, 'contenido': 'Hola'}]}]
        _, meta = serializar(categorias, numero, 'admin@example.test', '2026-10-05T12:00:00Z')
        version = leer_version(meta)
        self.lector.leer_version.return_value = version
        self.lector.leer.return_value = version, categorias

    def test_versiones_y_propias_intactas(self):
        categoria = self.repo.crear_categoria(self.repo.crear_catalogo('Propias'), 'Personal')
        ident = self.repo.crear_frase(categoria, 'Personal', 'mia', 'Mi frase')
        antes = self.repo.obtener_frase(ident)
        self.publicar(1)
        self.assertEqual(self.servicio.sincronizar().estado, 'actualizada')
        self.publicar(2, 'nueva')
        self.assertEqual(self.servicio.sincronizar().version, 2)
        self.assertEqual(self.repo.obtener_frase(ident), antes)
        self.publicar(1)
        self.assertEqual(self.servicio.sincronizar().estado, 'sin_cambios')
        self.assertEqual(self.actualizar.call_count, 2)

    def test_atomicidad_fallo_a_mitad(self):
        self.publicar(1)
        self.servicio.sincronizar()
        antes = self.repo.listar_frases()
        self.publicar(2, 'nueva')
        with patch.object(self.repo, '_crear_frase', side_effect=ValueError('Fallo simulado')):
            self.assertEqual(self.servicio.sincronizar().estado, 'error')
        self.assertEqual(self.repo.listar_frases(), antes)
        self.assertEqual(self.repo.listar_catalogos('compartida')[0]['version'], 1)

    def test_sin_publicar_y_error_de_red(self):
        self.assertEqual(self.servicio.sincronizar().estado, 'sin_cambios')
        self.lector.leer_version.side_effect = ValueError('Sin conexión')
        self.assertEqual(self.servicio.sincronizar().estado, 'error')

    def test_cambio_intervalo_durante_lectura_descarta(self):
        self.publicar(1)
        original = self.lector.leer.return_value
        def leer():
            self.servicio.configurar(2)
            return original
        self.lector.leer.side_effect = leer
        self.assertEqual(self.servicio.sincronizar().estado, 'sin_cambios')
        self.assertEqual(self.repo.listar_catalogos('compartida'), [])

    def test_simultaneas_se_omiten(self):
        self.servicio._candado.acquire()
        try:
            self.assertIn('en curso', self.servicio.sincronizar().detalle)
        finally:
            self.servicio._candado.release()

    def test_cierre_descarta_resultado_remoto(self):
        self.publicar(1)
        original = self.lector.leer.return_value
        def leer():
            self.servicio.detener()
            return original
        self.lector.leer.side_effect = leer
        self.assertEqual(self.servicio.sincronizar().estado, 'sin_cambios')
        self.assertEqual(self.repo.listar_catalogos('compartida'), [])

    def test_tres_equipos_reciben_publicacion(self):
        self.publicar(1)
        for numero in range(3):
            with RepositorioSQLite(':memory:') as repo:
                cat = repo.crear_categoria(repo.crear_catalogo('Propias'), 'Personal')
                ident = repo.crear_frase(cat, 'Personal', f'mia{numero}', 'Texto personal')
                antes = repo.obtener_frase(ident)
                servicio = ServicioSincronizacion(repo, lambda: self.lector)
                self.assertEqual(servicio.sincronizar().estado, 'actualizada')
                self.assertEqual(repo.obtener_frase(ident), antes)
