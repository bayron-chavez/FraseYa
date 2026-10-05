import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fraseya.aplicacion.publicacion import ServicioPublicacion, ErrorPublicacion
from fraseya.aplicacion.servicio_sincronizacion import ServicioSincronizacion
from fraseya.infraestructura import RepositorioSQLite
from fraseya.infraestructura.repositorio_compartido import RepositorioCompartido


class PublicacionTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix='Publicación ñ ')
        self.addCleanup(self.temp.cleanup)
        self.ruta = Path(self.temp.name)
        self.repo = RepositorioSQLite(':memory:')
        self.addCleanup(self.repo.cerrar)
        self.cat = self.repo.crear_categoria(self.repo.crear_catalogo('Propias'), 'Atención', '#123456')
        self.frase = self.repo.crear_frase(self.cat, 'Saludo', 'hola', 'Hola {nombre}, mañana 😊\nGracias')
        self.servicio = ServicioPublicacion(self.repo, self.ruta, 'Bayron')

    def test_primera_segunda_y_diferencias(self):
        vista = self.servicio.preparar()
        self.assertEqual((vista.version, vista.nuevas, vista.cantidad_frases), (1, 1, 1))
        self.assertEqual(list(self.ruta.iterdir()), [])
        self.servicio.publicar(vista)
        version, categorias = RepositorioCompartido(self.ruta).leer()
        self.assertEqual(version.autor, 'Bayron')
        self.assertEqual(categorias[0]['color'], '#123456')
        self.assertIn('😊', categorias[0]['frases'][0]['contenido'])
        self.repo.actualizar_frase(self.frase, self.cat, 'Nuevo', 'hola', 'Texto modificado')
        vista = self.servicio.preparar()
        self.assertEqual((vista.version, vista.modificadas), (2, 1))
        self.assertEqual(self.servicio.publicar(vista).version, 2)
        self.assertEqual({p.name for p in self.ruta.iterdir()}, {'catalogo.json', 'version.json'})

    def test_solo_propias_y_aporte_vacio_conserva_publicadas(self):
        compartida = self.repo.crear_categoria(self.repo.crear_catalogo('Compartido', 'compartida', 99), 'Equipo')
        self.repo.crear_frase(compartida, 'Ajena', 'ajena', 'Texto', 'compartida')
        self.assertEqual(self.servicio.publicar().cantidad_frases, 1)
        self.repo.eliminar_frase(self.frase)
        vista = self.servicio.preparar()
        self.assertEqual(vista.eliminadas, 0)
        self.servicio.publicar(vista)
        self.assertEqual(RepositorioCompartido(self.ruta).leer()[0].cantidad_frases, 1)

    def test_nueva_frase_conserva_anteriores_y_actualiza_sin_duplicar(self):
        self.servicio.publicar()
        self.repo.eliminar_frase(self.frase)
        self.frase = self.repo.crear_frase(self.cat, 'Nueva', 'nueva', 'Otra frase')
        vista = self.servicio.preparar()
        self.assertEqual((vista.nuevas, vista.eliminadas), (1, 0))
        self.servicio.publicar(vista)
        self.repo.actualizar_frase(self.frase, self.cat, 'Editada', 'NUEVA', 'Contenido actualizado')
        self.servicio.publicar()
        _, categorias = RepositorioCompartido(self.ruta).leer()
        frases = [f for c in categorias for f in c['frases']]
        self.assertEqual(len(frases), 2)
        self.assertEqual({f['abreviatura'].casefold() for f in frases}, {'hola', 'nueva'})
        self.assertEqual(next(f['contenido'] for f in frases if f['abreviatura'] == 'NUEVA'), 'Contenido actualizado')

    def test_vista_obsoleta(self):
        vista = self.servicio.preparar()
        self.servicio.publicar(vista)
        with self.assertRaisesRegex(ErrorPublicacion, 'cambió'):
            self.servicio.publicar(vista)
        self.assertFalse((self.ruta / 'publicando.lock').exists())

    def test_candado_vigente_y_caducado(self):
        candado = self.ruta / 'publicando.lock'
        candado.write_text(json.dumps({'autor': 'Diego', 'fecha': 100, 'token': 'otro'}))
        servicio = ServicioPublicacion(self.repo, self.ruta, 'Bayron', reloj=lambda: 110)
        with self.assertRaisesRegex(ErrorPublicacion, 'Diego'):
            servicio.publicar()
        servicio = ServicioPublicacion(self.repo, self.ruta, 'Bayron', reloj=lambda: 221)
        self.assertEqual(servicio.publicar().version, 1)
        self.assertFalse(candado.exists())

    def test_fallo_entre_reemplazos_restaura_anterior(self):
        self.servicio.publicar()
        antes = {p.name: p.read_bytes() for p in self.ruta.iterdir()}
        vista = self.servicio.preparar()
        original = os.replace
        llamadas = 0
        def reemplazar(origen, destino):
            nonlocal llamadas
            llamadas += 1
            if llamadas == 2:
                raise OSError('Fallo simulado')
            return original(origen, destino)
        with patch('fraseya.aplicacion.publicacion.os.replace', side_effect=reemplazar):
            with self.assertRaises(ErrorPublicacion):
                self.servicio.publicar(vista)
        self.assertEqual(antes, {p.name: p.read_bytes() for p in self.ruta.iterdir()})
        self.assertEqual(RepositorioCompartido(self.ruta).leer()[0].version, 1)

    def test_disco_lleno_y_rutas_invalidas(self):
        self.servicio.publicar()
        antes = {p.name: p.read_bytes() for p in self.ruta.iterdir()}
        vista = self.servicio.preparar()
        with patch('fraseya.aplicacion.publicacion.os.fsync', side_effect=OSError('Disco lleno')):
            with self.assertRaises(ErrorPublicacion):
                self.servicio.publicar(vista)
        self.assertEqual(antes, {p.name: p.read_bytes() for p in self.ruta.iterdir()})
        for carpeta in ('', self.ruta / 'ausente'):
            with self.assertRaises(ErrorPublicacion):
                ServicioPublicacion(self.repo, carpeta).publicar()

    def test_publicar_y_sincronizar_tres_equipos(self):
        from contextlib import ExitStack
        with ExitStack() as pila:
            equipos = [pila.enter_context(RepositorioSQLite(':memory:')) for _ in range(3)]
            servicios, propias = [], []
            for numero, repo in enumerate(equipos):
                categoria = repo.crear_categoria(repo.crear_catalogo('Propias'), 'Personal')
                ident = repo.crear_frase(categoria, 'Mía', f'mia{numero}', 'Conservar')
                propias.append(repo.obtener_frase(ident))
                servicio = ServicioSincronizacion(repo)
                servicio.configurar(str(self.ruta), 1)
                servicios.append(servicio)
            self.servicio.publicar()
            for servicio in servicios:
                self.assertEqual(servicio.sincronizar().estado, 'actualizada')
            self.repo.actualizar_frase(self.frase, self.cat, 'Actualizada', 'hola', 'Nueva respuesta')
            self.servicio.publicar()
            for repo, servicio, propia in zip(equipos, servicios, propias):
                self.assertEqual(servicio.sincronizar().version, 2)
                self.assertEqual(repo.obtener_frase(propia['id']), propia)
                self.assertEqual(repo.listar_frases('compartida')[0]['contenido'], 'Nueva respuesta')

    def test_validacion_acumula_errores_sin_escribir(self):
        categorias = [{'nombre': 'Equipo', 'color': 'rojo', 'frases': [
            {'titulo': '', 'abreviatura': 'hola', 'contenido': ''}]}]
        with self.assertRaises(ValueError) as error:
            self.servicio.preparar(categorias)
        self.assertIn('color', str(error.exception))
        self.assertIn('titulo', str(error.exception))
        self.assertEqual(list(self.ruta.iterdir()), [])

    def test_verificacion_posterior_y_permiso(self):
        vista = self.servicio.preparar()
        from dataclasses import replace
        from fraseya.aplicacion.formato_catalogo import leer_version
        incorrecta = replace(leer_version(vista.metadata), version=99)
        with patch.object(RepositorioCompartido, 'leer', return_value=(incorrecta, [])):
            with self.assertRaisesRegex(ErrorPublicacion, 'verificación'):
                self.servicio.publicar(vista)
        self.assertEqual(list(self.ruta.iterdir()), [])

    def test_solo_admin_elimina_explicitamente_y_usuario_conserva(self):
        from fraseya.aplicacion.autenticacion import Autenticacion
        auth = Autenticacion(self.ruta / 'usuarios.db')
        self.addCleanup(auth.cerrar)
        auth.crear_administrador_inicial('admin', 'contraseña-prueba')
        admin = auth.iniciar_sesion('admin', 'contraseña-prueba')
        auth.crear_usuario(admin, 'usuario', 'contraseña-prueba')
        usuario = auth.iniciar_sesion('usuario', 'contraseña-prueba')
        self.servicio.publicar()
        lector = ServicioPublicacion(self.repo, self.ruta,
            autorizar_eliminacion=lambda: auth.validar(usuario, administrador=True))
        with self.assertRaises(PermissionError):
            lector.preparar([], eliminar=['hola'])
        servicio_admin = ServicioPublicacion(self.repo, self.ruta,
            autorizar_eliminacion=lambda: auth.validar(admin, administrador=True))
        vista = servicio_admin.preparar([], eliminar=['hola'])
        self.assertEqual(vista.eliminadas, 1)
        with self.assertRaises(PermissionError):
            lector.publicar(vista, confirmar_vacio=True)
        servicio_admin.publicar(vista, confirmar_vacio=True)
        self.assertEqual(RepositorioCompartido(self.ruta).leer()[1], [])
        nueva_vista = self.servicio.preparar()
        with patch('fraseya.aplicacion.publicacion.os.open', side_effect=PermissionError()):
            with self.assertRaisesRegex(ErrorPublicacion, 'permisos'):
                self.servicio.publicar(nueva_vista)
