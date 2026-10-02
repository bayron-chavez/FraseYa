import time
import tkinter as tk

import pytest

from fraseya.aplicacion.gestion_frases import GestionFrases
from fraseya.infraestructura import RepositorioSQLite

ctk = pytest.importorskip('customtkinter')
from fraseya.presentacion import ventana_principal as vp  # noqa: E402


@pytest.fixture
def ventana():
    with RepositorioSQLite(':memory:') as repo:
        # Crear muchos Tk en un mismo proceso falla a veces con "Can't find a usable
        # init.tcl" (problema del entorno de pruebas, no de la app): se reintenta.
        for intento in range(5):
            try:
                v = vp.VentanaPrincipal(GestionFrases(repo))
                break
            except tk.TclError as error:
                ultimo_error = error
                time.sleep(0.2)
        else:
            pytest.skip(f'No se pudo abrir la ventana: {ultimo_error}')
        v.withdraw()
        yield v
        v.destroy()


def llenar(v, titulo, abrev, contenido):
    v.titulo.delete(0, 'end'); v.titulo.insert(0, titulo)
    v.abreviatura.delete(0, 'end'); v.abreviatura.insert(0, abrev)
    v.contenido.delete('1.0', 'end'); v.contenido.insert('1.0', contenido)


def filas(v):
    return [v.tabla.item(i, 'values')[0] for i in v.tabla.get_children()]


def test_crear_en_tres_pasos_y_ver_variables(ventana):
    ventana.nueva()                                   # paso 1
    llenar(ventana, 'Saludo', 'hola', 'Hola {nombre}, tu {orden}')  # paso 2
    ventana._mostrar_variables()
    assert '{nombre}, {orden}' in ventana.variables.cget('text')
    ventana.guardar()                                 # paso 3
    assert filas(ventana) == ['hola']
    assert ventana.estado.cget('text') == 'Frase propia'


def test_abreviatura_repetida_muestra_error_y_no_guarda(ventana):
    llenar(ventana, 'A', 'hola', 'x'); ventana.guardar()
    ventana.nueva()
    llenar(ventana, 'B', 'HOLA', 'y'); ventana.guardar()
    assert 'ya está en uso' in ventana.mensaje.cget('text')
    assert filas(ventana) == ['hola']


def test_editar_duplicar_y_eliminar(ventana, monkeypatch):
    llenar(ventana, 'A', 'a', 'x'); ventana.guardar()
    llenar(ventana, 'A editada', 'a', 'z'); ventana.guardar()
    assert ventana.gestion.listar()[0]['titulo'] == 'A editada'
    ventana.duplicar()
    assert sorted(filas(ventana)) == ['a', 'a2']
    monkeypatch.setattr(vp.messagebox, 'askyesno', lambda *a, **k: True)
    ventana.eliminar()
    assert filas(ventana) == ['a']
    assert ventana.seleccion is None


def test_eliminar_cancelado_no_borra(ventana, monkeypatch):
    llenar(ventana, 'A', 'a', 'x'); ventana.guardar()
    monkeypatch.setattr(vp.messagebox, 'askyesno', lambda *a, **k: False)
    ventana.eliminar()
    assert filas(ventana) == ['a']


def test_compartida_es_solo_lectura_pero_se_puede_duplicar(ventana):
    ventana.gestion.repo.reemplazar_compartidas(1, 'admin', '2026-10-01', [
        {'nombre': 'Normativa', 'frases': [{'titulo': 'S', 'abreviatura': 'sal', 'contenido': 'Hola'}]}])
    ventana.refrescar()
    ident = ventana.gestion.listar()[0]['id']
    ventana.tabla.selection_set(str(ident))
    ventana.update()
    assert 'solo lectura' in ventana.estado.cget('text')
    assert ventana.btn_guardar.cget('state') == 'disabled'
    assert ventana.btn_eliminar.cget('state') == 'disabled'
    ventana.duplicar()
    assert ventana.estado.cget('text') == 'Frase propia'
    assert ventana.seleccion['abreviatura'] == 'sal2'
    ventana.nueva()
    assert ventana.btn_guardar.cget('state') == 'normal'
    assert ventana.categoria.cget('values') == ['General']


def test_filtro_de_busqueda(ventana):
    llenar(ventana, 'Saludo', 'hola', 'Buenos días'); ventana.guardar()
    ventana.nueva()
    llenar(ventana, 'Cierre', 'chao', 'Hasta luego'); ventana.guardar()
    ventana.busqueda.insert(0, 'luego')
    ventana.refrescar()
    assert filas(ventana) == ['chao']


def test_muestra_todos_los_errores_a_la_vez(ventana):
    llenar(ventana, '', 'dos palabras', '')
    ventana.guardar()
    texto = ventana.mensaje.cget('text')
    assert texto.count('•') == 3
    assert 'título' in texto and 'espacios' in texto and 'contenido' in texto
    assert filas(ventana) == []


def test_botones_bloqueados_se_ven_grises_y_recuperan_su_color(ventana):
    rojo = ventana._colores_boton[ventana.btn_eliminar][0]
    ventana.nueva()
    assert ventana.btn_eliminar.cget('fg_color') == vp.COLOR_BLOQUEADO
    assert ventana.btn_duplicar.cget('fg_color') == vp.COLOR_BLOQUEADO
    llenar(ventana, 'A', 'a', 'x'); ventana.guardar()
    assert ventana.btn_eliminar.cget('state') == 'normal'
    assert ventana.btn_eliminar.cget('fg_color') == rojo
    assert ventana.btn_guardar.cget('fg_color') != vp.COLOR_BLOQUEADO


def test_contador_de_frases(ventana):
    assert ventana.contador.cget('text') == '0 frases · 0 propias · 0 compartidas'
    llenar(ventana, 'Saludo', 'hola', 'Buenos días'); ventana.guardar()
    assert ventana.contador.cget('text') == '1 frase · 1 propias · 0 compartidas'
    ventana.nueva()
    llenar(ventana, 'Cierre', 'chao', 'Hasta luego'); ventana.guardar()
    ventana.busqueda.insert(0, 'luego')
    ventana.refrescar()
    assert ventana.contador.cget('text') == 'Mostrando 1 de 2 frases'
    ventana.busqueda.delete(0, 'end'); ventana.busqueda.insert(0, 'zzz')
    ventana.refrescar()
    assert ventana.contador.cget('text') == 'Mostrando 0 de 2 frases'
