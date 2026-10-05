from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
import unittest
from unittest.mock import Mock, patch

from fraseya.aplicacion.formato_catalogo import serializar
from fraseya.aplicacion.servicio_sincronizacion import ServicioSincronizacion
from fraseya.infraestructura import RepositorioSQLite
from fraseya.infraestructura.repositorio_compartido import RepositorioCompartido


class SincronizacionTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ruta = Path(self.temp.name)
        self.repo = RepositorioSQLite(':memory:')
        self.addCleanup(self.repo.cerrar)
        self.actualizar = Mock()
        self.servicio = ServicioSincronizacion(self.repo, al_actualizar=self.actualizar)
        self.servicio.configurar(str(self.ruta), 1)

    def publicar(self, version, abrev='saludo', contenido='Hola'):
        categorias = [{'nombre': 'General', 'color': '#112233', 'frases': [
            {'titulo': 'Prueba', 'abreviatura': abrev, 'contenido': contenido}]}]
        datos, meta = serializar(categorias, version, 'Bayron', '2026-10-05T12:00:00Z')
        (self.ruta / 'catalogo.json').write_bytes(datos)
        (self.ruta / 'version.json').write_bytes(meta)

    def propia(self, abrev='personal', contenido='Mi frase'):
        catalogo = self.repo.crear_catalogo('Propias')
        categoria = self.repo.crear_categoria(catalogo, 'Personal')
        return self.repo.crear_frase(categoria, 'Mía', abrev, contenido)

    def test_versiones_y_propias_intactas(self):
        ident = self.propia()
        antes = self.repo.obtener_frase(ident)
        self.publicar(1)
        self.assertEqual(self.servicio.sincronizar().estado, 'actualizada')
        self.publicar(2, 'nueva')
        self.assertEqual(self.servicio.sincronizar().version, 2)
        self.assertEqual([f['abreviatura'] for f in self.repo.listar_frases('compartida')], ['nueva'])
        self.assertEqual(antes, self.repo.obtener_frase(ident))
        self.assertEqual(self.servicio.sincronizar().estado, 'sin_cambios')
        self.publicar(1)
        self.assertEqual(self.servicio.sincronizar().estado, 'sin_cambios')
        self.assertEqual(self.actualizar.call_count, 2)
        self.assertEqual(len(self.repo.listar_sincronizaciones()), 4)

    def test_sin_publicar(self):
        resultado = self.servicio.sincronizar()
        self.assertEqual(resultado.estado, 'sin_cambios')
        self.assertIn('no se ha publicado', resultado.detalle)

    def test_fallos_conservan_catalogo(self):
        self.publicar(1)
        self.servicio.sincronizar()
        antes = self.repo.listar_frases()
        self.publicar(2)
        archivo = self.ruta / 'catalogo.json'
        archivo.write_bytes(archivo.read_bytes() + b' ')
        self.servicio._lector._pausa = lambda _: None
        self.assertEqual(self.servicio.sincronizar().estado, 'error')
        self.servicio.configurar(str(self.ruta / 'ausente'), 1)
        self.assertEqual(self.servicio.sincronizar().estado, 'error')
        self.assertEqual(antes, self.repo.listar_frases())
        self.assertEqual(self.actualizar.call_count, 1)

    def test_conflictos_incluso_identicos(self):
        ident = self.propia('SALUDO', 'Hola')
        antes = self.repo.obtener_frase(ident)
        self.publicar(1)
        resultado = self.servicio.sincronizar()
        self.assertEqual(resultado.estado, 'error')
        self.assertIn('saludo', resultado.detalle)
        self.assertEqual(antes, self.repo.obtener_frase(ident))
        self.assertEqual(self.repo.listar_catalogos('compartida'), [])
        self.actualizar.assert_not_called()

    def test_atomicidad_fallo_a_mitad(self):
        self.publicar(1)
        self.servicio.sincronizar()
        antes = self.repo.listar_frases()
        self.publicar(2, 'otra')
        with patch.object(self.repo, '_crear_frase', side_effect=ValueError('Fallo simulado')):
            self.assertEqual(self.servicio.sincronizar().estado, 'error')
        self.assertEqual(antes, self.repo.listar_frases())
        self.assertEqual(self.repo.listar_catalogos('compartida')[0]['version'], 1)

    def test_cambio_ruta_durante_lectura_descarta(self):
        self.publicar(1)
        original = self.servicio._lector.leer
        def leer():
            resultado = original()
            self.servicio.configurar(str(self.ruta / 'nueva'), 2)
            return resultado
        with patch.object(self.servicio._lector, 'leer', side_effect=leer):
            self.assertEqual(self.servicio.sincronizar().estado, 'sin_cambios')
        self.assertEqual(self.repo.listar_catalogos('compartida'), [])

    def test_simultaneas_se_omiten(self):
        self.servicio._candado.acquire()
        try:
            self.assertIn('en curso', self.servicio.sincronizar().detalle)
        finally:
            self.servicio._candado.release()

    def test_hilo_inicio_intervalo_y_cierre(self):
        ruta_bd = self.ruta / 'local.db'
        self.publicar(1)
        with RepositorioSQLite(ruta_bd) as repo:
            resultados, esperas = [], []
            listo = Event()
            def esperar(segundos):
                esperas.append(segundos)
                servicio.detener()
                listo.set()
            servicio = ServicioSincronizacion(repo, al_resultado=resultados.append, esperar=esperar)
            servicio.configurar(str(self.ruta), 2)
            servicio.iniciar()
            self.assertTrue(listo.wait(2))
            servicio._hilo.join(0.5)
            self.assertFalse(servicio._hilo.is_alive())
            self.assertEqual(esperas, [120])
            self.assertEqual(resultados[0].estado, 'actualizada')
            self.assertEqual(repo.listar_catalogos('compartida')[0]['version'], 1)

    def test_tres_equipos_reciben_publicacion(self):
        self.publicar(1)
        for numero in range(3):
            with RepositorioSQLite(':memory:') as repo:
                cat = repo.crear_categoria(repo.crear_catalogo('Propias'), 'Personal')
                ident = repo.crear_frase(cat, 'Personal', f'mia{numero}', 'Texto personal')
                antes = repo.obtener_frase(ident)
                servicio = ServicioSincronizacion(repo)
                servicio.configurar(str(self.ruta), 1)
                self.assertEqual(servicio.sincronizar().estado, 'actualizada')
                self.assertEqual(antes, repo.obtener_frase(ident))

    def test_recarga_motor_sin_reiniciar(self):
        from fraseya.aplicacion.motor_expansion import MotorExpansion
        escritor = Mock()
        motor = MotorExpansion(escritor, Mock(), lambda: 1, lanzar=lambda accion: accion())
        servicio = ServicioSincronizacion(self.repo,
            al_actualizar=lambda: motor.actualizar_frases(self.repo.listar_frases()))
        servicio.configurar(str(self.ruta), 1)
        self.publicar(1)
        self.assertEqual(servicio.sincronizar().estado, 'actualizada')
        for caracter in 'saludo':
            motor.caracter(caracter)
        self.assertTrue(motor.confirmar())
        escritor.reemplazar.assert_called_once_with(6, 'Hola')

    def test_cambio_en_caliente_y_detener_lectura_bloqueada(self):
        otra = self.ruta / 'otra'
        otra.mkdir()
        datos, meta = serializar([], 2, '', '2026-10-05T12:00:00Z')
        (otra / 'catalogo.json').write_bytes(datos)
        (otra / 'version.json').write_bytes(meta)
        bd = self.ruta / 'hilo.db'
        with RepositorioSQLite(bd) as repo:
            primero, segundo = Event(), Event()
            def recibido(resultado):
                if resultado.version == 2:
                    segundo.set()
                else:
                    primero.set()
            servicio = ServicioSincronizacion(repo, al_resultado=recibido)
            servicio.configurar(str(self.ruta), 1)
            servicio.iniciar()
            try:
                self.assertTrue(primero.wait(2))
                servicio.configurar(str(otra), 3)
                self.assertTrue(segundo.wait(2))
                self.assertEqual(repo.listar_catalogos('compartida')[0]['version'], 2)
            finally:
                servicio.detener()
                servicio._hilo.join(0.5)
            self.assertFalse(servicio._hilo.is_alive())
