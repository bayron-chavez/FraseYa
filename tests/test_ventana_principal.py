import time
import tkinter as tk
import threading

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


def test_menu_variable_inserta_en_cursor_y_guarda(ventana, monkeypatch):
    monkeypatch.setattr(ventana, '_elegir_variable_repetida', lambda _: 'misma')
    llenar(ventana, 'Cobro', '!cobro', 'Hola , total ')
    ventana.contenido.mark_set('insert', '1.5')
    ventana._insertar_variable('Nombre')
    assert ventana.contenido.get('1.0', 'end-1c') == 'Hola {nombre}, total '
    ventana.contenido.mark_set('insert', 'end-1c')
    ventana._insertar_variable('Monto')
    ventana._insertar_variable('Monto')
    assert ventana.menu_variables.get() == 'Insertar variable…'
    assert '{nombre}, {monto}' in ventana.variables.cget('text')
    ventana.guardar()
    assert ventana.gestion.listar()[0]['contenido'] == 'Hola {nombre}, total {monto}{monto}'


def test_menu_variable_respeta_solo_lectura(ventana):
    ventana.contenido.insert('1.0', 'Compartida {fecha}')
    ventana._modo_edicion(False)
    assert ventana.menu_variables.cget('state') == 'disabled'
    ventana._insertar_variable('Nombre')
    assert ventana.contenido.get('1.0', 'end-1c') == 'Compartida {fecha}'
    ventana.nueva()
    assert ventana.menu_variables.cget('state') == 'normal'


def test_variable_distinta_no_colisiona_y_resuelve_separada(ventana, monkeypatch):
    from fraseya.aplicacion.resolver_variables import resolver
    monkeypatch.setattr(ventana, '_elegir_variable_repetida', lambda _: 'otra')
    llenar(ventana, 'Saludo', '!saludo', '{nombre} saluda a {nombre_2}: ')
    ventana.contenido.mark_set('insert', 'end-1c')
    ventana._insertar_variable('Nombre')
    texto = ventana.contenido.get('1.0', 'end-1c')
    assert texto == '{nombre} saluda a {nombre_2}: {nombre_3}'
    assert resolver(texto, lambda *_: {
        'nombre': 'Ana', 'nombre_2': 'Luis', 'nombre_3': 'Eva',
    }) == 'Ana saluda a Luis: Eva'


def test_cancelar_variable_repetida_conserva_contenido(ventana, monkeypatch):
    monkeypatch.setattr(ventana, '_elegir_variable_repetida', lambda _: None)
    ventana.contenido.insert('1.0', 'Hola {nombre}')
    ventana._insertar_variable('Nombre')
    assert ventana.contenido.get('1.0', 'end-1c') == 'Hola {nombre}'


def test_dialogo_repetida_tiene_eleccion_clara(ventana):
    ventana.deiconify()
    ventana.update()

    def elegir():
        for dialogo in ventana.winfo_children():
            if isinstance(dialogo, ctk.CTkToplevel):
                for boton in dialogo.winfo_children():
                    if isinstance(boton, ctk.CTkButton) and boton.cget('text') == 'Agregar otro valor':
                        boton.invoke()
                        return
        ventana.after(50, elegir)

    ventana.after(200, elegir)
    assert ventana._elegir_variable_repetida('Nombre') == 'otra'


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


def test_favoritas_filtro_y_deshacer_en_interfaz(ventana, monkeypatch):
    llenar(ventana, 'A', '!a', 'Hola {nombre}')
    ventana.guardar()
    ventana.alternar_favorita()
    assert ventana.btn_favorita.cget('text') == '★ Quitar de favoritas'
    ventana.solo_favoritas.select()
    ventana.refrescar()
    assert filas(ventana) == ['!a']
    monkeypatch.setattr(vp.messagebox, 'askyesno', lambda *a, **k: True)
    ventana.eliminar()
    assert filas(ventana) == []
    assert ventana.btn_deshacer.cget('state') == 'normal'
    ventana.deshacer_eliminacion()
    assert filas(ventana) == ['!a']
    assert ventana.contenido.get('1.0', 'end-1c') == 'Hola {nombre}'
    assert ventana.btn_deshacer.cget('state') == 'disabled'


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
    assert ventana.categoria.cget('values') == ['General', 'Normativa']


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


def test_avisa_al_motor_cuando_las_frases_cambian(ventana):
    avisos = []
    ventana.al_cambiar = lambda: avisos.append(1)
    llenar(ventana, 'A', 'a', 'x'); ventana.guardar()
    ventana.duplicar()
    assert len(avisos) == 2
    ventana.nueva(); llenar(ventana, '', '', ''); ventana.guardar()   # con errores no avisa
    assert len(avisos) == 2
