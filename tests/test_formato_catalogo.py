import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

from fraseya.aplicacion.formato_catalogo import (
    ErrorFormato, MAX_BYTES, leer_catalogo, leer_version, serializar, verificar_integridad)
from fraseya.infraestructura import RepositorioSQLite

FECHA = '2026-10-05T12:00:00-03:00'


def ejemplo():
    return [{'nombre': 'Atención', 'color': '#1F6AA5', 'frases': [
        {'titulo': 'Saludo', 'abreviatura': 'hola',
         'contenido': 'Hola {nombre}, mañana revisaremos tu solicitud. 😊\nLlaves: {}'}]}]


def encode(obj):
    return json.dumps(obj, ensure_ascii=False).encode('utf-8')


class FormatoTests(unittest.TestCase):
    def test_ida_vuelta_determinismo_y_hash(self):
        datos, metadata = serializar(ejemplo(), 7, 'Bayron', FECHA)
        self.assertEqual(leer_catalogo(datos), ejemplo())
        self.assertEqual(serializar(ejemplo(), 7, 'Bayron', FECHA), (datos, metadata))
        reordenado = copy.deepcopy(ejemplo())
        reordenado[0]['frases'][0] = dict(reversed(list(reordenado[0]['frases'][0].items())))
        self.assertEqual(serializar(reordenado, 7, 'Bayron', FECHA), (datos, metadata))
        version = leer_version(metadata)
        self.assertEqual(version.cantidad_frases, 1)
        self.assertTrue(verificar_integridad(datos, version))
        self.assertFalse(verificar_integridad(datos + b' ', version))
        self.assertEqual(version.sha256, hashlib.sha256(datos).hexdigest())

    def test_bom_lectura_sin_bom_escritura(self):
        datos, metadata = serializar(ejemplo(), 1, '', FECHA)
        bom = b'\xef\xbb\xbf'
        self.assertFalse(datos.startswith(bom))
        self.assertFalse(metadata.startswith(bom))
        self.assertEqual(leer_catalogo(bom + datos), ejemplo())
        self.assertEqual(leer_version(bom + metadata), leer_version(metadata))
        self.assertFalse(verificar_integridad(bom + datos, leer_version(metadata)))

    def test_catalogo_vacio(self):
        datos, metadata = serializar([], 1, 'Bayron', FECHA)
        self.assertEqual(leer_catalogo(datos), [])
        self.assertEqual(leer_version(metadata).cantidad_frases, 0)

    def test_json_roto_tipo_tamano_duplicadas(self):
        for datos in (b'{', b'[]', b'\xff', 'texto', b'x' * (MAX_BYTES + 1),
                      b'{"formato":1,"formato":1,"categorias":[]}',
                      b'{"formato":NaN,"categorias":[]}'):
            with self.subTest(datos=str(datos)[:30]), self.assertRaises(ErrorFormato):
                leer_catalogo(datos)

    def test_faltantes_tipos_y_formato_futuro(self):
        for objeto in ({}, {'formato': True, 'categorias': []},
                       {'formato': 1, 'categorias': {}}, {'formato': 1, 'categorias': [None]}):
            with self.subTest(objeto=objeto), self.assertRaises(ErrorFormato):
                leer_catalogo(encode(objeto))
        with self.assertRaisesRegex(ErrorFormato, 'actualiza FraseYa'):
            leer_catalogo(b'{"formato":2,"categorias":[]}')

    def test_version_fecha_y_metadata_invalidas(self):
        _, datos = serializar(ejemplo(), 1, 'Bayron', FECHA)
        metadata = json.loads(datos)
        for campo, valor in [('version', 0), ('version', -1), ('version', True),
                             ('version', '1'), ('fecha', 'ayer'), ('fecha', '2026-10-05'),
                             ('fecha', '2026-10-05T12:00:00'), ('autor', None),
                             ('sha256', 'no'), ('cantidad_frases', True), ('formato', 2)]:
            with self.subTest(campo=campo, valor=valor), self.assertRaises(ErrorFormato):
                leer_version(encode({**metadata, campo: valor}))
        with self.assertRaises(ErrorFormato):
            leer_version(b'{}')
        with self.assertRaises(ErrorFormato):
            serializar(ejemplo(), 0, 'Bayron', FECHA)

    def test_validaciones_de_catalogo(self):
        for campo, valor in [('abreviatura', 'con espacio'), ('abreviatura', 'tab\t'),
                             ('abreviatura', ''), ('titulo', ''), ('contenido', 9)]:
            categorias = ejemplo()
            categorias[0]['frases'][0][campo] = valor
            with self.subTest(campo=campo), self.assertRaises(ErrorFormato):
                serializar(categorias, 1, 'Bayron', FECHA)
        for color in ('red', '#12345', '#GGGGGG'):
            categorias = ejemplo()
            categorias[0]['color'] = color
            with self.assertRaises(ErrorFormato):
                serializar(categorias, 1, 'Bayron', FECHA)
        categorias = ejemplo()
        categorias[0]['frases'].append({**categorias[0]['frases'][0], 'abreviatura': 'HOLA'})
        with self.assertRaisesRegex(ErrorFormato, r'categorias\[0\].frases\[1\].abreviatura'):
            serializar(categorias, 1, '', FECHA)
        categorias = ejemplo() + ejemplo()
        with self.assertRaisesRegex(ErrorFormato, 'categoría repetida'):
            serializar(categorias, 1, '', FECHA)

    def test_errores_acumulados(self):
        categorias = [{'nombre': '', 'color': 'red', 'frases': [
            {'titulo': '', 'abreviatura': 'dos palabras', 'contenido': ''}]}]
        with self.assertRaises(ErrorFormato) as capturado:
            serializar(categorias, 0, None, 'ayer')
        self.assertGreaterEqual(len(capturado.exception.errores), 8)
        self.assertIn('categorias[0].frases[0].titulo', str(capturado.exception))
        self.assertIn('categorias[0].color', str(capturado.exception))

    def test_claves_desconocidas(self):
        categorias = ejemplo()
        categorias[0]['frases'][0]['variables'] = ['nombre']
        with self.assertRaisesRegex(ErrorFormato, 'variables'):
            serializar(categorias, 1, '', FECHA)

    def test_ejemplos_y_compatibilidad_sqlite(self):
        ejemplos = Path(__file__).resolve().parents[1] / 'docs' / 'ejemplos'
        datos = (ejemplos / 'catalogo.json').read_bytes()
        version = leer_version((ejemplos / 'version.json').read_bytes())
        self.assertTrue(verificar_integridad(datos, version))
        categorias = leer_catalogo(datos)
        with RepositorioSQLite(':memory:') as repo:
            ident = repo.reemplazar_compartidas(version.version, version.autor, version.fecha, categorias)
            self.assertEqual(repo.obtener_catalogo(ident)['version'], version.version)
            self.assertEqual(len(repo.listar_frases('compartida')), version.cantidad_frases)
