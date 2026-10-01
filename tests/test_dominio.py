import unittest
from fraseya.dominio import (COMPARTIDA, CatalogoFrases, Categoria, Frase,
                             VersionCatalogo, Variable)


def compartida(abrev, contenido='Hola'):
    return Frase('T', abrev, contenido, COMPARTIDA)


def publicado(*abrevs):
    c = Categoria('Normativa', '#112233')
    for a in abrevs:
        c.agregar(compartida(a))
    return [c]


class VariableTests(unittest.TestCase):
    def test_validaciones(self):
        with self.assertRaises(ValueError):
            Variable(' ', 0)
        with self.assertRaises(ValueError):
            Variable('x', -1)


class FraseTests(unittest.TestCase):
    def test_variables_en_orden_sin_repetir(self):
        f = Frase('Saludo', 'hi', 'Hola {nombre}, orden {orden} {nombre} {monto}')
        self.assertEqual([(v.nombre, v.orden) for v in f.variables],
                         [('nombre', 0), ('orden', 1), ('monto', 2)])

    def test_sin_marcadores(self):
        self.assertEqual(Frase('A', 'a', 'Texto').variables, [])

    def test_validaciones(self):
        with self.assertRaises(ValueError):
            Frase('', 'a', 'x')
        with self.assertRaises(ValueError):
            Frase('A', 'a', 'x', origen='otra')

    def test_duplicar_es_propia(self):
        copia = compartida('a').duplicar('b')
        self.assertEqual((copia.abreviatura, copia.origen), ('b', 'propia'))


class CategoriaTests(unittest.TestCase):
    def test_color_y_abreviatura_unica(self):
        with self.assertRaises(ValueError):
            Categoria('X', 'rojo')
        c = Categoria('X')
        c.agregar(Frase('A', 'ab', 'x'))
        with self.assertRaises(ValueError):
            c.agregar(Frase('B', 'AB', 'y'))


class VersionTests(unittest.TestCase):
    def test_es_posterior_a(self):
        self.assertTrue(VersionCatalogo(2).es_posterior_a(VersionCatalogo(1)))
        self.assertFalse(VersionCatalogo(1).es_posterior_a(VersionCatalogo(1)))


class CatalogoTests(unittest.TestCase):
    def setUp(self):
        self.cat = CatalogoFrases()
        c = Categoria('Normativa')
        c.agregar(compartida('vieja'))
        c.agregar(Frase('Mía', 'mia', 'mi texto'))
        self.cat.agregar_categoria(c)

    def test_reemplaza_solo_compartidas(self):
        self.cat.reemplazar_compartidas(VersionCatalogo(1), publicado('nueva'))
        self.assertEqual({f.abreviatura for f in self.cat.frases()}, {'mia', 'nueva'})
        self.assertEqual(self.cat.version.numero, 1)

    def test_rechaza_version_no_posterior(self):
        with self.assertRaises(ValueError):
            self.cat.reemplazar_compartidas(VersionCatalogo(0), publicado('nueva'))

    def test_conflicto_con_propia_no_modifica(self):
        with self.assertRaises(ValueError):
            self.cat.reemplazar_compartidas(VersionCatalogo(1), publicado('MIA'))
        self.assertIsNotNone(self.cat.buscar('vieja'))
        self.assertEqual(self.cat.version.numero, 0)

    def test_buscar(self):
        self.assertEqual(self.cat.buscar('MIA').abreviatura, 'mia')
        self.assertIsNone(self.cat.buscar('zzz'))


if __name__ == '__main__':
    unittest.main()
