import time
import tkinter as tk

import pytest

ctk = pytest.importorskip('customtkinter')
from fraseya.presentacion.formulario_variables import FormularioVariables  # noqa: E402


@pytest.fixture
def raiz():
    # Crear muchos Tk en un mismo proceso falla a veces con "Can't find a usable
    # init.tcl" (problema del entorno de pruebas, no de la app): se reintenta.
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


def abrir(raiz, nombres, iniciales=None):
    f = FormularioVariables(raiz, nombres, iniciales)
    f.withdraw()
    return f


def test_un_campo_por_variable_en_el_orden_definido(raiz):
    f = abrir(raiz, ['nombre', 'orden', 'monto'])
    assert list(f.entradas) == ['nombre', 'orden', 'monto']
    f.destroy()


def test_aceptar_devuelve_los_valores(raiz):
    f = abrir(raiz, ['nombre', 'orden'])
    f.entradas['nombre'].insert(0, '  Ana ')
    f.entradas['orden'].insert(0, '1234')
    f.aceptar()
    assert f.resultado == {'nombre': 'Ana', 'orden': '1234'}


def test_no_cierra_y_muestra_todos_los_campos_vacios(raiz):
    f = abrir(raiz, ['nombre', 'orden', 'monto'])
    f.entradas['orden'].insert(0, '5')
    f.aceptar()
    texto = f.mensaje.cget('text')
    assert f.winfo_exists() and f.resultado is None
    assert 'nombre' in texto and 'monto' in texto and 'orden' not in texto
    f.destroy()


def test_cancelar_devuelve_none(raiz):
    f = abrir(raiz, ['nombre'])
    f.entradas['nombre'].insert(0, 'Ana')
    f.cancelar()
    assert f.resultado is None


def test_valores_iniciales_prellenan_el_campo(raiz):
    f = abrir(raiz, ['nombre', 'fecha'], {'fecha': '02/10/2026'})
    assert f.entradas['fecha'].get() == '02/10/2026'
    assert f.entradas['nombre'].get() == ''
    f.destroy()


def test_vista_previa_actualiza_y_resalta_todas_las_apariciones(raiz):
    f = FormularioVariables(raiz, ['nombre', 'nombre_2'], contenido=
                           'Hola {nombre}, te atiende {nombre_2}. Gracias {nombre}.')
    f.withdraw()
    assert '[Nombre 2]' in f.vista_previa.get('1.0', 'end-1c')
    f.entradas['nombre'].insert(0, 'Ana')
    f.entradas['nombre_2'].insert(0, 'Luis')
    assert f.vista_previa.get('1.0', 'end-1c') == 'Hola Ana, te atiende Luis. Gracias Ana.'
    assert len(f.vista_previa.tag_ranges('activo')) == 4
    f._resaltar_variable('nombre_2')
    rangos = f.vista_previa.tag_ranges('activo')
    assert len(rangos) == 2
    assert f.vista_previa.get(*rangos) == 'Luis'
    f.destroy()


def test_vista_previa_no_reinterpreta_llaves_del_valor(raiz):
    f = FormularioVariables(raiz, ['nombre', 'monto'], contenido='{nombre}\n{monto}')
    f.withdraw()
    f.entradas['nombre'].insert(0, '{monto}')
    f.entradas['monto'].insert(0, '10')
    assert f.vista_previa.get('1.0', 'end-1c') == '{monto}\n10'
    f.cancelar()
    assert f.resultado is None
