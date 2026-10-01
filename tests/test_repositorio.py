import sqlite3
import tempfile
import unittest
from pathlib import Path
from fraseya import RepositorioSQLite


def catalogo(shortcut='equipo', content='Hola {nombre}'):
    return [{'nombre': 'Equipo', 'color': '#123ABC', 'frases': [
        {'titulo': 'Saludo', 'abreviatura': shortcut, 'contenido': content}]}]


class RepositorioTests(unittest.TestCase):
    def setUp(self):
        self.repo = RepositorioSQLite(':memory:')
        self.addCleanup(self.repo.cerrar)
        self.cat = self.repo.crear_catalogo('Personal')
        self.category = self.repo.crear_categoria(self.cat, 'General')

    def frase(self, shortcut='local', content='Hola {nombre} {nombre} {fecha}'):
        return self.repo.crear_frase(self.category, 'Título', shortcut, content)

    def test_seis_tablas_y_foreign_keys(self):
        names = {r[0] for r in self.repo.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertEqual(names, {'CATALOGO', 'CATEGORIA', 'FRASE', 'VARIABLE', 'SINCRONIZACION', 'CONFIGURACION'})
        self.assertEqual(self.repo.db.execute('PRAGMA foreign_keys').fetchone()[0], 1)
        self.assertEqual(self.repo.db.execute('PRAGMA user_version').fetchone()[0], 1)

    def test_crud_frases_y_variables(self):
        ident = self.frase()
        self.assertEqual([r['nombre'] for r in self.repo.obtener_frase(ident)['variables']], ['nombre', 'fecha'])
        self.repo.actualizar_frase(ident, self.category, 'Nuevo', 'nuevo', 'Orden {orden}')
        self.assertEqual(self.repo.obtener_frase(ident)['titulo'], 'Nuevo')
        self.assertEqual([r['nombre'] for r in self.repo.listar_variables(ident)], ['orden'])
        self.repo.eliminar_frase(ident)
        self.assertEqual(self.repo.listar_variables(ident), [])
        with self.assertRaises(LookupError):
            self.repo.obtener_frase(ident)

    def test_abreviatura_unica_y_rollback_edicion(self):
        first = self.frase('local')
        second = self.frase('segunda')
        with self.assertRaises(sqlite3.IntegrityError):
            self.frase('LOCAL')
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.actualizar_frase(second, self.category, 'Cambió', 'LOCAL', 'Nuevo {x}')
        self.assertEqual(self.repo.obtener_frase(second)['abreviatura'], 'segunda')
        self.assertEqual(len(self.repo.listar_frases()), 2)
        self.assertEqual(self.repo.obtener_frase(first)['titulo'], 'Título')

    def test_crud_categorias_y_colores(self):
        ident = self.repo.crear_categoria(self.cat, 'Otra', '#aabbCC')
        self.repo.actualizar_categoria(ident, 'Renombrada', '#AABBCC')
        self.assertEqual(self.repo.obtener_categoria(ident)['nombre'], 'Renombrada')
        self.assertEqual(len(self.repo.listar_categorias(self.cat)), 2)
        self.assertEqual(len(self.repo.listar_categorias()), 2)
        self.repo.eliminar_categoria(ident)
        with self.assertRaises(LookupError):
            self.repo.obtener_categoria(ident)
        for color in ('rojo', '#GG0000', '#000', '0000000'):
            with self.assertRaises(sqlite3.IntegrityError):
                self.repo.crear_categoria(self.cat, 'Mala', color)

    def test_categoria_ocupada_no_elimina_frases(self):
        ident = self.frase()
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.eliminar_categoria(self.category)
        self.assertEqual(self.repo.obtener_frase(ident)['categoria_id'], self.category)

    def test_claves_foraneas_y_origen(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.crear_categoria(999, 'Sin catálogo')
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.crear_frase(999, 'Sin categoría', 'sincat', 'Texto')
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.crear_frase(self.category, 'Ajena', 'ajena', 'Texto', 'compartida')
        ident = self.frase()
        shared = self.repo.crear_catalogo('Compartido', 'compartida')
        shared_category = self.repo.crear_categoria(shared, 'Equipo')
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.actualizar_frase(ident, shared_category, 'Ajena', 'local', 'Texto')
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.db.execute('UPDATE CATEGORIA SET catalogo_id=? WHERE id=?', (shared, self.category))
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.db.execute("UPDATE CATALOGO SET origen='compartida' WHERE id=?", (self.cat,))
        self.repo.db.rollback()

    def test_crud_variables(self):
        frase_id = self.frase(content='Texto')
        ident = self.repo.crear_variable(frase_id, 'extra', 0)
        self.repo.actualizar_variable(ident, 'otra', 2)
        self.assertEqual(self.repo.listar_variables(frase_id)[0]['nombre'], 'otra')
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.crear_variable(frase_id, 'otra', 3)
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.crear_variable(frase_id, 'nuevo', 2)
        self.repo.eliminar_variable(ident)
        self.assertEqual(self.repo.listar_variables(frase_id), [])

    def test_configuracion_upsert(self):
        self.assertIsNone(self.repo.leer_configuracion('atajo'))
        self.assertEqual(self.repo.leer_configuracion('atajo', 'Ctrl+Space'), 'Ctrl+Space')
        self.repo.guardar_configuracion('atajo', 'Ctrl+Space')
        self.repo.guardar_configuracion('atajo', 'Alt+Space')
        self.assertEqual(self.repo.leer_configuracion('atajo'), 'Alt+Space')
        with self.assertRaises(ValueError):
            self.repo.guardar_configuracion('atajo', 1)

    def test_registro_sincronizaciones(self):
        self.repo.registrar_sincronizacion('sin_cambios', 0)
        self.repo.registrar_sincronizacion('error', detalle='Carpeta inaccesible')
        rows = self.repo.listar_sincronizaciones()
        self.assertEqual(rows[0]['estado'], 'error')
        self.assertTrue(rows[0]['fecha'])
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.registrar_sincronizacion('estado inválido')

    def test_reemplazo_preserva_propias(self):
        local = self.frase()
        before = self.repo.obtener_frase(local)
        self.repo.reemplazar_compartidas(1, 'Bayron', '2026-10-01T12:00:00Z', catalogo())
        ident = self.repo.reemplazar_compartidas(2, 'Bayron', '2026-10-01T13:00:00Z', catalogo('otra'))
        self.assertEqual(self.repo.obtener_catalogo(ident)['version'], 2)
        self.assertEqual(self.repo.obtener_frase(local), before)
        self.assertEqual(len(self.repo.listar_frases('compartida')), 1)
        self.assertEqual(len(self.repo.listar_frases(categoria_id=self.category)), 1)
        self.assertEqual(self.repo.listar_frases('compartida')[0]['abreviatura'], 'otra')
        self.assertEqual(self.repo.listar_sincronizaciones()[0]['version_aplicada'], 2)

    def test_conflicto_compartida_revierte_toda_transaccion(self):
        self.frase('local')
        self.repo.reemplazar_compartidas(1, 'Bayron', None, catalogo())
        before = self.repo.listar_frases()
        incoming = catalogo('nueva')
        incoming[0]['frases'].append({'titulo': 'Colisión', 'abreviatura': 'LOCAL', 'contenido': 'Texto'})
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.reemplazar_compartidas(2, 'Bayron', None, incoming)
        self.assertEqual(self.repo.listar_frases(), before)
        self.assertEqual(len(self.repo.listar_sincronizaciones()), 1)
        shared = self.repo.listar_categorias()[1]
        self.assertTrue(shared)

    def test_datos_incompletos_revierten_reemplazo(self):
        self.repo.reemplazar_compartidas(1, '', None, catalogo())
        before = self.repo.listar_frases()
        with self.assertRaises(KeyError):
            self.repo.reemplazar_compartidas(2, '', None, [{'nombre': 'Falta frases'}])
        self.assertEqual(self.repo.listar_frases(), before)
        self.repo.reemplazar_compartidas(2, '', None, [])
        self.assertEqual(self.repo.listar_frases('compartida'), [])

    def test_validacion(self):
        for version in (-1, True, '1'):
            with self.assertRaises(ValueError):
                self.repo.crear_catalogo('Inválido', version=version)
        with self.assertRaises(ValueError):
            self.repo.crear_catalogo('Nombre', 'invalido')
        with self.assertRaises(ValueError):
            self.frase(content='  ')
        with self.assertRaises(ValueError):
            self.repo.guardar_configuracion('', '')
        with self.assertRaises(LookupError):
            self.repo.actualizar_variable(999, 'x', 0)
        with self.assertRaises(LookupError):
            self.repo.eliminar_variable(999)


class ArranqueTests(unittest.TestCase):
    def test_creacion_automatica_persistencia_y_reapertura(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'datos' / 'fraseya.db'
            with RepositorioSQLite(path) as repo:
                cat = repo.crear_catalogo('Personal')
                category = repo.crear_categoria(cat, 'General')
                repo.crear_frase(category, 'Saludo', 'sal', 'Hola')
            self.assertTrue(path.is_file())
            with RepositorioSQLite(path) as repo:
                self.assertEqual(len(repo.listar_frases()), 1)
                self.assertEqual(repo.db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_version_no_soportada(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'test.db'
            with sqlite3.connect(path) as db:
                db.execute('PRAGMA user_version=42')
            db.close()
            with self.assertRaises(ValueError):
                RepositorioSQLite(path)

    def test_no_sobrescribe_prototipo(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'test.db'
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE frase(id INTEGER PRIMARY KEY)')
            db.close()
            with self.assertRaises(ValueError):
                RepositorioSQLite(path)
