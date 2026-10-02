import unittest
from fraseya.infraestructura.escritor_texto import EscritorTexto


class TecladoFalso:
    def __init__(self):
        self.eventos = []

    def escribir_caracter(self, caracter):
        self.eventos.append(('c', caracter))

    def enter(self):
        self.eventos.append(('enter',))

    def retroceso(self):
        self.eventos.append(('borrar',))


class EscritorTextoTests(unittest.TestCase):
    def setUp(self):
        self.teclado = TecladoFalso()
        self.pausas = []
        self.escritor = EscritorTexto(self.teclado, 25, self.pausas.append)

    def test_escribe_unicode_y_saltos_de_linea(self):
        self.escritor.escribir('Año ✓\r\nfin\n')
        self.assertEqual(self.teclado.eventos, [
            ('c', 'A'), ('c', 'ñ'), ('c', 'o'), ('c', ' '), ('c', '✓'), ('enter',),
            ('c', 'f'), ('c', 'i'), ('c', 'n'), ('enter',)])

    def test_respeta_la_velocidad_configurada(self):
        self.escritor.escribir('ab')
        self.assertEqual(self.pausas, [0.025, 0.025])
        self.escritor.velocidad_ms = 60
        self.escritor.escribir('c')
        self.assertEqual(self.pausas[-1], 0.06)

    def test_rechaza_velocidades_fuera_de_rango(self):
        for valor in (9, 61, 0, -5, 20.5, '20', True):
            with self.assertRaises(ValueError, msg=repr(valor)):
                self.escritor.velocidad_ms = valor
        for valor in (10, 60):
            self.escritor.velocidad_ms = valor
        with self.assertRaises(ValueError):
            EscritorTexto(self.teclado, 5)

    def test_reemplaza_la_abreviatura_antes_de_escribir(self):
        self.escritor.reemplazar_abreviatura('hola', 'Hi')
        self.assertEqual(self.teclado.eventos,
                         [('borrar',)] * 4 + [('c', 'H'), ('c', 'i')])

    def test_cien_inserciones_no_pierden_caracteres(self):
        texto = 'Línea 1 ñ✓\nLínea 2'
        for _ in range(100):
            self.escritor.reemplazar_abreviatura('x', texto)
        escritos = sum(1 for e in self.teclado.eventos if e[0] in ('c', 'enter'))
        self.assertEqual(escritos, 100 * len(texto))
        self.assertEqual(sum(1 for e in self.teclado.eventos if e[0] == 'borrar'), 100)
