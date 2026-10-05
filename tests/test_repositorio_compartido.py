import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
import time
import subprocess
import sys
import unittest
from unittest.mock import patch

from fraseya.aplicacion.formato_catalogo import serializar
from fraseya.infraestructura.repositorio_compartido import (
    RepositorioCompartido, CarpetaNoDisponible, CatalogoNoPublicado,
    FormatoInvalido, FormatoNoSoportado, CatalogoEnTransicion)


class CompartidoTests(unittest.TestCase):
    def setUp(self):
        self.temporal = TemporaryDirectory(prefix='Frases ñ ')
        self.addCleanup(self.temporal.cleanup)
        self.ruta = Path(self.temporal.name)
        self.repo = RepositorioCompartido(self.ruta, pausa=lambda _: None)

    def publicar(self, version=1, bom=False):
        datos, metadata = serializar([], version, 'Bayron', '2026-10-05T12:00:00-03:00')
        if bom:
            datos = b'\xef\xbb\xbf' + datos
            objeto = json.loads(metadata)
            objeto['sha256'] = hashlib.sha256(datos).hexdigest()
            metadata = b'\xef\xbb\xbf' + json.dumps(objeto).encode()
        (self.ruta / 'catalogo.json').write_bytes(datos)
        (self.ruta / 'version.json').write_bytes(metadata)

    def test_estados_y_sin_publicacion(self):
        self.assertEqual(RepositorioCompartido('').comprobar().estado, 'sin_configurar')
        self.assertEqual(RepositorioCompartido(self.ruta / 'ausente').comprobar().estado, 'inaccesible')
        archivo = self.ruta / 'archivo'
        archivo.touch()
        self.assertEqual(RepositorioCompartido(archivo).comprobar().estado, 'inaccesible')
        self.assertEqual(self.repo.comprobar().estado, 'disponible')
        self.assertIsNone(self.repo.leer_version())
        with self.assertRaises(CatalogoNoPublicado):
            self.repo.leer()

    def test_ejemplos_solo_lectura(self):
        origen = Path(__file__).resolve().parents[1] / 'docs' / 'ejemplos'
        for nombre in ('version.json', 'catalogo.json'):
            (self.ruta / nombre).write_bytes((origen / nombre).read_bytes())
        antes = {p.name: p.read_bytes() for p in self.ruta.iterdir()}
        version, categorias = self.repo.leer()
        self.assertEqual(version.cantidad_frases, sum(len(c['frases']) for c in categorias))
        self.assertEqual(antes, {p.name: p.read_bytes() for p in self.ruta.iterdir()})

    def test_bom_y_cambio_origen(self):
        self.publicar(3, bom=True)
        self.assertEqual(self.repo.leer()[0].version, 3)
        with TemporaryDirectory() as otra:
            datos, meta = serializar([], 8, '', '2026-10-05T12:00:00Z')
            Path(otra, 'catalogo.json').write_bytes(datos)
            Path(otra, 'version.json').write_bytes(meta)
            self.assertEqual(RepositorioCompartido(otra).leer()[0].version, 8)
        self.assertEqual(self.repo.leer()[0].version, 3)

    def test_hash_y_recuperacion(self):
        self.publicar()
        archivo = self.ruta / 'catalogo.json'
        archivo.write_bytes(archivo.read_bytes() + b' ')
        with self.assertRaises(CatalogoEnTransicion):
            self.repo.leer()
        self.repo._pausa = lambda _: self.publicar()
        self.assertEqual(self.repo.leer()[0].version, 1)

    def test_version_concurrente(self):
        self.publicar()
        original = self.repo._archivo
        llamadas = 0
        def leer(nombre, opcional=False):
            nonlocal llamadas
            if nombre == 'version.json':
                llamadas += 1
                if llamadas == 2:
                    self.publicar(2)
            return original(nombre, opcional)
        with patch.object(self.repo, '_archivo', side_effect=leer):
            self.assertEqual(self.repo.leer()[0].version, 2)

    def test_json_formato_y_ausente(self):
        for nombre in ('version.json', 'catalogo.json'):
            self.publicar()
            (self.ruta / nombre).write_bytes(b'{')
            with self.assertRaises(FormatoInvalido):
                self.repo.leer()
        self.publicar()
        objeto = json.loads((self.ruta / 'version.json').read_bytes())
        objeto['formato'] = 99
        (self.ruta / 'version.json').write_text(json.dumps(objeto))
        with self.assertRaisesRegex(FormatoNoSoportado, 'actualiza FraseYa'):
            self.repo.leer_version()
        self.publicar()
        (self.ruta / 'catalogo.json').unlink()
        with self.assertRaisesRegex(CatalogoNoPublicado, 'catalogo.json'):
            self.repo.leer()

    def test_cantidad_incorrecta(self):
        self.publicar()
        objeto = json.loads((self.ruta / 'version.json').read_bytes())
        objeto['cantidad_frases'] = 1
        (self.ruta / 'version.json').write_text(json.dumps(objeto))
        with self.assertRaisesRegex(FormatoInvalido, 'cantidad'):
            self.repo.leer()

    def test_timeout_no_acumula_hilos(self):
        liberar = Event()
        terminado = Event()
        repo = RepositorioCompartido(self.ruta, tiempo_maximo_s=0.05)
        def bloqueada(*args, **kwargs):
            try:
                liberar.wait()
            finally:
                terminado.set()
        with patch.object(repo, '_archivo', side_effect=bloqueada):
            inicio = time.monotonic()
            try:
                with self.assertRaisesRegex(CarpetaNoDisponible, 'no responde'):
                    repo.leer_version()
                self.assertLess(time.monotonic() - inicio, 0.5)
                with self.assertRaisesRegex(CarpetaNoDisponible, 'pendiente'):
                    repo.leer_version()
            finally:
                liberar.set()
                terminado.wait(1)

    def test_permiso_denegado(self):
        with patch.object(Path, 'open', side_effect=PermissionError()):
            self.assertEqual(self.repo.comprobar().estado, 'inaccesible')
            with self.assertRaisesRegex(CarpetaNoDisponible, 'permisos'):
                self.repo.leer_version()

    def test_limite_y_ruta_unc(self):
        from fraseya.aplicacion.formato_catalogo import MAX_BYTES
        self.publicar()
        (self.ruta / 'catalogo.json').write_bytes(b' ' * (MAX_BYTES + 1))
        with self.assertRaisesRegex(FormatoInvalido, '5 MiB'):
            self.repo.leer()
        repo = RepositorioCompartido(r'\\servidor\carpeta')
        with patch.object(Path, 'is_dir', side_effect=OSError()):
            self.assertEqual(repo.comprobar().estado, 'inaccesible')

    def test_script_valida_vacia_y_danada(self):
        script = Path(__file__).resolve().parents[1] / 'scripts' / 'prueba_compartido.py'
        def ejecutar():
            return subprocess.run([sys.executable, str(script), str(self.ruta)],
                                  capture_output=True, timeout=5)
        self.assertEqual(ejecutar().returncode, 1)
        self.publicar()
        self.assertEqual(ejecutar().returncode, 0)
        archivo = self.ruta / 'catalogo.json'
        archivo.write_bytes(archivo.read_bytes() + b' ')
        resultado = ejecutar()
        self.assertEqual(resultado.returncode, 1)
        self.assertNotIn(b'Traceback', resultado.stderr)
