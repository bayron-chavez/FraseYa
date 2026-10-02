import unittest
from fraseya import RepositorioSQLite
from fraseya.aplicacion.gestor_frases import GestorFrases

try:
    import tkinter as tk
    from fraseya.presentacion.ventana_principal import VentanaPrincipal
    tk.Tk().destroy()
    HAY_PANTALLA = True
except Exception:
    HAY_PANTALLA = False


@unittest.skipUnless(HAY_PANTALLA, 'requiere Tkinter y pantalla')
class VentanaPrincipalTests(unittest.TestCase):
    def setUp(self):
        self.repo = RepositorioSQLite(':memory:')
        self.addCleanup(self.repo.cerrar)
        self.errores = []
        self.gestor = GestorFrases(self.repo)
        self.ventana = VentanaPrincipal(
            self.gestor, avisar=lambda _t, msg, **_k: self.errores.append(msg),
            confirmar=lambda *a, **k: True)
        self.addCleanup(self.ventana.destroy)

    def crear_por_formulario(self, titulo, abreviatura, contenido):
        form = self.ventana.nueva()
        form.titulo.set(titulo)
        form.abreviatura.set(abreviatura)
        form.contenido.insert('1.0', contenido)
        return form.guardar()

    def test_crear_frase_sin_reiniciar_y_listarla(self):
        self.assertTrue(self.crear_por_formulario('Saludo', 'hola', 'Hola {nombre}'))
        filas = [self.ventana.tabla.item(i, 'values') for i in self.ventana.tabla.get_children()]
        self.assertEqual(filas, [('Saludo', 'hola', 'Propia')])

    def test_abreviatura_repetida_muestra_error_y_no_guarda(self):
        self.crear_por_formulario('A', 'hola', 'x')
        self.assertFalse(self.crear_por_formulario('B', 'hola', 'y'))
        self.assertEqual(len(self.errores), 1)
        self.assertEqual(len(self.gestor.listar()), 1)

    def test_editar_duplicar_y_eliminar(self):
        self.crear_por_formulario('A', 'hola', 'x')
        ident = self.ventana.tabla.get_children()[0]
        self.ventana.tabla.selection_set(ident)
        form = self.ventana.editar()
        form.titulo.set('Nuevo')
        self.assertTrue(form.guardar())
        self.assertEqual(self.repo.obtener_frase(int(ident))['titulo'], 'Nuevo')
        self.ventana.duplicar()
        self.assertEqual(len(self.ventana.tabla.get_children()), 2)
        self.ventana.eliminar()
        self.assertEqual(len(self.ventana.tabla.get_children()), 1)

    def test_compartidas_bloquean_editar_y_eliminar(self):
        self.repo.reemplazar_compartidas(1, 'a', None, [{'nombre': 'Eq', 'color': '#123ABC', 'frases': [
            {'titulo': 'T', 'abreviatura': 'eq', 'contenido': 'c'}]}])
        self.ventana.refrescar()
        self.ventana.tabla.selection_set(self.ventana.tabla.get_children()[0])
        self.ventana.update()
        self.assertEqual(str(self.ventana.botones['Editar']['state']), 'disabled')
        self.assertEqual(str(self.ventana.botones['Eliminar']['state']), 'disabled')
        self.assertEqual(str(self.ventana.botones['Duplicar']['state']), 'normal')
        self.assertIsNone(self.ventana.editar())
