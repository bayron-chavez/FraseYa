import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from fraseya.aplicacion.arranque import preparar_aplicacion
from fraseya.presentacion.consola import ejecutar


class ArranqueAplicacionTests(unittest.TestCase):
    def test_arranque_repetido_conserva_base(self):
        with tempfile.TemporaryDirectory() as folder:
            ruta = Path(folder) / 'datos' / 'catalogo.db'
            esperado = {'version_esquema': 1, 'cantidad_frases': 0}
            self.assertEqual(preparar_aplicacion(ruta), esperado)
            self.assertEqual(preparar_aplicacion(ruta), esperado)
            self.assertTrue(ruta.exists())

    def test_entrada_consola(self):
        with tempfile.TemporaryDirectory() as folder:
            salida = io.StringIO()
            with contextlib.redirect_stdout(salida):
                codigo = ejecutar(['--bd', str(Path(folder) / 'catalogo.db')])
            self.assertEqual(codigo, 0)
            self.assertIn('FraseYa inició correctamente', salida.getvalue())

    def test_error_arranque_informa_sin_ocultar_fallo(self):
        with tempfile.TemporaryDirectory() as folder:
            salida = io.StringIO()
            with contextlib.redirect_stdout(salida):
                codigo = ejecutar(['--bd', folder])
            self.assertEqual(codigo, 1)
            self.assertIn('No se pudo iniciar', salida.getvalue())
