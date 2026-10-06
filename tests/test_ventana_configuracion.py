import time
import tkinter as tk

import pytest

ctk = pytest.importorskip('customtkinter')
from fraseya.aplicacion.configuracion import Ajustes, Configuracion  # noqa: E402
from fraseya.aplicacion.gestion_frases import GestionFrases  # noqa: E402
from fraseya.infraestructura import RepositorioSQLite  # noqa: E402
from fraseya.presentacion import ventana_principal as vp  # noqa: E402
from fraseya.presentacion.ventana_configuracion import VentanaConfiguracion  # noqa: E402


def _crear_raiz(clase):
    # Crear muchos Tk en un mismo proceso falla a veces con "Can't find a usable
    # init.tcl" (problema del entorno de pruebas, no de la app): se reintenta.
    for _ in range(5):
        try:
            return clase()
        except tk.TclError as error:
            ultimo = error
            time.sleep(0.2)
    pytest.skip(f'No se pudo abrir la ventana: {ultimo}')


@pytest.fixture
def repo():
    with RepositorioSQLite(':memory:') as r:
        yield r


@pytest.fixture
def raiz():
    r = _crear_raiz(ctk.CTk)
    r.withdraw()
    yield r
    r.destroy()


@pytest.fixture
def dialogo(raiz, repo):
    eventos = {'guardados': [], 'cerrado': 0}
    d = VentanaConfiguracion(raiz, Configuracion(repo),
                             al_guardar=eventos['guardados'].append,
                             al_cerrar=lambda: eventos.__setitem__('cerrado', eventos['cerrado'] + 1))
    d.withdraw()
    d.eventos = eventos
    return d


def poner(entrada, texto):
    entrada.delete(0, 'end')
    entrada.insert(0, texto)


def existe(ventana):
    try:
        return bool(ventana.winfo_exists())
    except tk.TclError:
        return False


def test_muestra_los_valores_actuales(dialogo):
    assert dialogo.atajo.get() == 'ctrl+alt+espacio'
    assert dialogo.tecla.get() == 'Tab'
    assert round(dialogo.velocidad.get()) == 20
    assert dialogo.intervalo.get() == '15'
    assert '20 ms' in dialogo.etiqueta_velocidad.cget('text')
    dialogo.destroy()


def test_guardar_persiste_aplica_y_cierra(dialogo, repo):
    poner(dialogo.atajo, 'Ctrl+Shift+K')
    dialogo.tecla.set('Enter')
    dialogo.velocidad.set(35)
    dialogo._mostrar_velocidad()
    poner(dialogo.intervalo, '10')
    dialogo.guardar()
    esperado = Ajustes('enter', 'ctrl+shift+k', 35, 10)
    assert dialogo.guardado == esperado
    assert Configuracion(repo).leer() == esperado                  # persistido
    assert dialogo.eventos['guardados'] == [esperado]               # aplicado
    assert dialogo.eventos['cerrado'] == 1 and not existe(dialogo)


def test_con_errores_los_muestra_todos_juntos_y_no_cierra_ni_guarda(dialogo, repo):
    poner(dialogo.atajo, 'k')
    poner(dialogo.intervalo, '0')
    dialogo.guardar()
    texto = dialogo.mensaje.cget('text')
    assert texto.count('•') == 2
    assert existe(dialogo) and dialogo.guardado is None and dialogo.eventos['guardados'] == []
    assert Configuracion(repo).leer() == Ajustes()
    dialogo.destroy()


def test_restablecer_carga_los_predeterminados_pero_no_guarda_hasta_pulsar_guardar(dialogo, repo):
    Configuracion(repo).guardar({'velocidad_ms': '50', 'intervalo_sincronizacion_min': '5'})
    dialogo.cargar(Configuracion(repo).leer())
    assert dialogo.intervalo.get() == '5'
    dialogo.restablecer()
    assert dialogo.intervalo.get() == '15' and round(dialogo.velocidad.get()) == 20
    assert Configuracion(repo).leer().intervalo_sincronizacion_min == 5     # aún sin guardar
    dialogo.guardar()
    assert Configuracion(repo).leer() == Ajustes()



def test_cancelar_no_guarda_nada(dialogo, repo):
    poner(dialogo.intervalo, '99')
    dialogo.cancelar()
    assert dialogo.guardado is None and dialogo.eventos['guardados'] == []
    assert Configuracion(repo).leer().intervalo_sincronizacion_min == 15
    assert dialogo.eventos['cerrado'] == 1 and not existe(dialogo)


def test_el_deslizador_actualiza_la_etiqueta(dialogo):
    dialogo.velocidad.set(60)
    dialogo._mostrar_velocidad()
    assert '60 ms' in dialogo.etiqueta_velocidad.cget('text')
    dialogo.destroy()


# ---- integración con la ventana principal -----------------------------------

@pytest.fixture
def principal(repo):
    v = _crear_raiz(lambda: vp.VentanaPrincipal(GestionFrases(repo)))
    v.withdraw()
    yield v
    v.destroy()


def test_la_ventana_principal_abre_la_configuracion_una_sola_vez(principal):
    principal.abrir_configuracion()
    primera = principal._configuracion
    principal.abrir_configuracion()
    assert principal._configuracion is primera
    primera.cancelar()
    assert principal._configuracion is None


def test_guardar_aplica_los_ajustes_al_motor_y_pausa_el_teclado_mientras_esta_abierta(principal):
    aplicados, pausas = [], []
    principal.al_configurar = aplicados.append
    principal.al_pausar = pausas.append
    principal.abrir_configuracion()
    d = principal._configuracion
    poner(d.intervalo, '7')
    d.guardar()
    assert [a.intervalo_sincronizacion_min for a in aplicados] == [7]
    assert pausas == [True, False]
    assert 'guardada y aplicada' in principal.mensaje.cget('text')



def test_cancelar_tambien_reanuda_el_teclado(principal):
    pausas = []
    principal.al_pausar = pausas.append
    principal.abrir_configuracion()
    principal._configuracion.cancelar()
    assert pausas == [True, False]


# ---- botones de atajos recomendados -----------------------------------------

def test_hay_un_boton_por_cada_atajo_recomendado(dialogo):
    from fraseya.aplicacion.configuracion import ATAJOS_RECOMENDADOS
    assert list(dialogo.botones_atajo) == [a for a, _ in ATAJOS_RECOMENDADOS]
    dialogo.destroy()


def test_al_abrir_se_resalta_el_atajo_actual_y_se_explica(dialogo):
    azul = '#1F6AA5'
    assert dialogo.botones_atajo['ctrl+alt+espacio'].cget('fg_color') == azul
    assert dialogo.botones_atajo['ctrl+alt+f9'].cget('fg_color') != azul
    assert 'Recomendado' in dialogo.ayuda_atajo.cget('text')
    dialogo.destroy()


def test_pulsar_un_boton_rellena_la_entrada_y_cambia_el_resaltado(dialogo):
    dialogo.botones_atajo['ctrl+alt+f9'].invoke()
    assert dialogo.atajo.get() == 'ctrl+alt+f9'
    assert dialogo.botones_atajo['ctrl+alt+f9'].cget('fg_color') == '#1F6AA5'
    assert dialogo.botones_atajo['ctrl+alt+espacio'].cget('fg_color') != '#1F6AA5'
    assert 'teclas F' in dialogo.ayuda_atajo.cget('text')
    dialogo.destroy()


def test_un_atajo_escrito_a_mano_no_resalta_ninguno(dialogo):
    poner(dialogo.atajo, 'ctrl+shift+k')
    dialogo._marcar_atajo()
    assert all(b.cget('fg_color') != '#1F6AA5' for b in dialogo.botones_atajo.values())
    assert 'Escribe otro' in dialogo.ayuda_atajo.cget('text')
    dialogo.destroy()


def test_un_atajo_escrito_con_otro_formato_igual_resalta_su_boton(dialogo):
    poner(dialogo.atajo, ' Shift + Ctrl + Espacio ')
    dialogo._marcar_atajo()
    assert dialogo.botones_atajo['ctrl+shift+espacio'].cget('fg_color') == '#1F6AA5'
    dialogo.destroy()


def test_elegir_un_recomendado_y_guardar_lo_persiste_y_lo_aplica(dialogo, repo):
    dialogo.botones_atajo['ctrl+shift+f9'].invoke()
    dialogo.guardar()
    assert Configuracion(repo).leer().atajo_buscador == 'ctrl+shift+f9'
    assert dialogo.eventos['guardados'][0].atajo_buscador == 'ctrl+shift+f9'


def test_pulsar_un_boton_no_guarda_hasta_pulsar_guardar(dialogo, repo):
    dialogo.botones_atajo['ctrl+alt+f9'].invoke()
    assert Configuracion(repo).leer().atajo_buscador == 'ctrl+alt+espacio'
    dialogo.destroy()


def test_restablecer_vuelve_a_resaltar_el_predeterminado(dialogo):
    dialogo.botones_atajo['ctrl+alt+f9'].invoke()
    dialogo.restablecer()
    assert dialogo.atajo.get() == 'ctrl+alt+espacio'
    assert dialogo.botones_atajo['ctrl+alt+espacio'].cget('fg_color') == '#1F6AA5'
    dialogo.destroy()
