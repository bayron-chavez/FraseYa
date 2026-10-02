import time
import tkinter as tk

import pytest

ctk = pytest.importorskip('customtkinter')
from fraseya.presentacion.buscador_rapido import VentanaBuscador  # noqa: E402

FRASES = [
    {'abreviatura': 'hola', 'titulo': 'Saludo inicial', 'categoria': 'General', 'origen': 'propia',
     'contenido': 'Buenos días, ¿en qué puedo ayudarle?'},
    {'abreviatura': 'cierre', 'titulo': 'Despedida', 'categoria': 'General', 'origen': 'propia',
     'contenido': 'Gracias {nombre}, su caso {orden} quedó registrado.'},
    {'abreviatura': 'plazo', 'titulo': 'Plazo de reclamo', 'categoria': 'Normativa', 'origen': 'compartida',
     'contenido': 'El plazo es de {dias} días.'},
]


@pytest.fixture
def raiz():
    for _ in range(5):
        try:
            r = ctk.CTk()
            break
        except tk.TclError as error:
            ultimo = error
            time.sleep(0.2)
    else:
        pytest.skip(f'No se pudo abrir la ventana: {ultimo}')
    r.withdraw()
    yield r
    r.destroy()


@pytest.fixture
def buscador(raiz):
    eventos = {'elegidas': [], 'canceladas': [], 'mostrado': 0, 'oculto': 0}
    b = VentanaBuscador(raiz,
                        al_elegir=lambda f, o: eventos['elegidas'].append((f['abreviatura'], o)),
                        al_cancelar=lambda o: eventos['canceladas'].append(o),
                        al_mostrar=lambda: eventos.__setitem__('mostrado', eventos['mostrado'] + 1),
                        al_ocultar=lambda: eventos.__setitem__('oculto', eventos['oculto'] + 1))
    b.eventos = eventos
    return b


def abrevs(b):
    return [f['abreviatura'] for f in b.resultados]


def test_nace_oculto_y_se_muestra_con_todas_las_frases(buscador):
    assert buscador.state() == 'withdrawn'
    buscador.mostrar(FRASES, origen=77)
    assert buscador.visible and buscador.state() == 'normal'
    assert abrevs(buscador) == ['cierre', 'plazo', 'hola']      # por título
    assert buscador.eventos['mostrado'] == 1


def test_filtra_mientras_se_escribe(buscador):
    buscador.mostrar(FRASES, 77)
    buscador.entrada.insert(0, 'reclamo')
    assert abrevs(buscador) == ['plazo']
    buscador.entrada.delete(0, 'end')
    assert len(buscador.resultados) == 3


def test_busca_sin_acentos_en_el_contenido(buscador):
    buscador.mostrar(FRASES, 77)
    buscador.entrada.insert(0, 'dias')
    assert set(abrevs(buscador)) == {'hola', 'plazo'}


def test_las_flechas_mueven_la_seleccion_sin_salirse_de_la_lista(buscador):
    buscador.mostrar(FRASES, 77)
    assert buscador.seleccionada()['abreviatura'] == 'cierre'
    buscador._mover(1)
    assert buscador.seleccionada()['abreviatura'] == 'plazo'
    buscador._mover(1); buscador._mover(1); buscador._mover(1)
    assert buscador.seleccionada()['abreviatura'] == 'hola'      # tope inferior
    buscador._mover(-5)
    assert buscador.seleccionada()['abreviatura'] == 'cierre'    # tope superior


def test_enter_elige_la_seleccionada_y_entrega_la_ventana_de_origen(buscador):
    buscador.mostrar(FRASES, 77)
    buscador._mover(1)
    buscador.elegir()
    assert buscador.eventos['elegidas'] == [('plazo', 77)]
    assert not buscador.visible and buscador.state() == 'withdrawn'
    assert buscador.eventos['oculto'] == 1


def test_esc_cierra_y_devuelve_el_foco_al_origen_sin_elegir(buscador):
    buscador.mostrar(FRASES, 77)
    buscador.cancelar()
    assert buscador.eventos['canceladas'] == [77] and buscador.eventos['elegidas'] == []
    assert not buscador.visible


def test_sin_resultados_enter_no_hace_nada(buscador):
    buscador.mostrar(FRASES, 77)
    buscador.entrada.insert(0, 'zzzz')
    assert buscador.resultados == [] and buscador.seleccionada() is None
    assert 'Sin resultados' in buscador.vista_previa.cget('text')
    buscador.elegir()
    assert buscador.eventos['elegidas'] == [] and buscador.visible


def test_vista_previa_muestra_el_contenido_de_la_seleccionada(buscador):
    buscador.mostrar(FRASES, 77)
    assert 'Gracias {nombre}' in buscador.vista_previa.cget('text')


def test_cada_apertura_empieza_limpia(buscador):
    buscador.mostrar(FRASES, 77)
    buscador.entrada.insert(0, 'hola')
    buscador.ocultar()
    buscador.mostrar(FRASES, 88)
    assert buscador.entrada.get() == '' and len(buscador.resultados) == 3 and buscador.origen == 88


def test_ocultar_dos_veces_no_avisa_dos_veces(buscador):
    buscador.mostrar(FRASES, 77)
    buscador.ocultar(); buscador.ocultar()
    assert buscador.eventos['oculto'] == 1
