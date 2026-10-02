import unittest
from fraseya import RepositorioSQLite
from fraseya.aplicacion.gestor_frases import GestorFrases


class GestorFrasesTests(unittest.TestCase):
    def setUp(self):
        self.repo = RepositorioSQLite(':memory:')
        self.addCleanup(self.repo.cerrar)
        self.gestor = GestorFrases(self.repo)

    def test_crea_catalogo_propio_una_sola_vez(self):
        GestorFrases(self.repo)
        self.assertEqual(self.repo.db.execute('SELECT COUNT(*) FROM CATALOGO').fetchone()[0], 1)

    def test_crear_editar_y_eliminar(self):
        ident = self.gestor.crear('Saludo', ' hola ', 'Hola {nombre}')
        self.assertEqual(self.repo.obtener_frase(ident)['abreviatura'], 'hola')
        self.gestor.editar(ident, 'Saludo 2', 'hola', 'Buen día')
        self.assertEqual(self.repo.obtener_frase(ident)['titulo'], 'Saludo 2')
        self.gestor.eliminar(ident)
        self.assertEqual(self.gestor.listar(), [])

    def test_abreviatura_unica_sin_distinguir_mayusculas(self):
        ident = self.gestor.crear('A', 'hola', 'x')
        with self.assertRaises(ValueError):
            self.gestor.crear('B', 'HOLA', 'y')
        otra = self.gestor.crear('B', 'chao', 'y')
        with self.assertRaises(ValueError):
            self.gestor.editar(otra, 'B', 'Hola', 'y')
        self.gestor.editar(ident, 'A', 'hola', 'z')  # conservar la propia es válido

    def test_duplicar_genera_abreviatura_libre(self):
        ident = self.gestor.crear('A', 'hola', 'x')
        self.gestor.crear('B', 'hola2', 'y')
        copia = self.repo.obtener_frase(self.gestor.duplicar(ident))
        self.assertEqual((copia['abreviatura'], copia['origen']), ('hola3', 'propia'))

    def test_compartidas_son_de_solo_lectura_pero_duplicables(self):
        self.repo.reemplazar_compartidas(1, 'a', None, [{'nombre': 'Eq', 'color': '#123ABC', 'frases': [
            {'titulo': 'T', 'abreviatura': 'eq', 'contenido': 'c'}]}])
        ident = next(f['id'] for f in self.gestor.listar() if f['origen'] == 'compartida')
        with self.assertRaises(ValueError):
            self.gestor.editar(ident, 'T', 'eq', 'c')
        with self.assertRaises(ValueError):
            self.gestor.eliminar(ident)
        self.assertEqual(self.repo.obtener_frase(self.gestor.duplicar(ident))['origen'], 'propia')
