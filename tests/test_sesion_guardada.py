"""«Recordar sesión»: cifrado local, rotación del token y restauración."""
import json
import sys
from unittest.mock import Mock

import pytest

from fraseya.infraestructura.sesion_guardada import SesionGuardada
from fraseya.infraestructura.supabase import AutenticacionSupabase, ClienteSupabase, ErrorSupabase
from fraseya.presentacion.qt_aplicacion import _restaurar_sesion

URL = 'https://proyecto.supabase.co'
PERFIL = [{'id': '1', 'correo': 'a@example.test', 'rol': 'usuario'}]
solo_windows = pytest.mark.skipif(sys.platform != 'win32', reason='DPAPI es de Windows')


def cliente_con(transporte):
    return ClienteSupabase(URL, 'sb_publishable_prueba', transporte)


def transporte_correcto(metodo, ruta, cuerpo, headers):
    if 'grant_type' in ruta:
        return {'access_token': 'acceso', 'refresh_token': 'nuevo', 'expires_in': 3600}
    return PERFIL


@solo_windows
def test_token_cifrado_ligado_al_proyecto_y_borrable(tmp_path):
    almacen = SesionGuardada(tmp_path / 'sesion.dat')
    almacen.guardar(URL, 'secreto-de-prueba')
    assert b'secreto-de-prueba' not in almacen.ruta.read_bytes()
    assert almacen.leer(URL) == 'secreto-de-prueba'
    assert almacen.leer('https://otro.supabase.co') is None
    almacen.borrar()
    assert almacen.leer(URL) is None


@solo_windows
def test_archivo_corrupto_se_ignora(tmp_path):
    (tmp_path / 'sesion.dat').write_bytes(b'basura')
    assert SesionGuardada(tmp_path / 'sesion.dat').leer(URL) is None


@solo_windows
def test_restaurar_guarda_el_token_rotado(tmp_path):
    almacen = SesionGuardada(tmp_path / 'sesion.dat')
    almacen.guardar(URL, 'viejo')
    auth = AutenticacionSupabase(cliente_con(transporte_correcto))
    sesion, aviso = _restaurar_sesion(auth, almacen)
    assert sesion.usuario == 'a@example.test' and aviso == ''
    assert almacen.leer(URL) == 'nuevo'


@solo_windows
@pytest.mark.parametrize('estado, se_conserva', [(400, False), (401, False), (None, True)])
def test_token_rechazado_se_borra_y_fallo_de_red_lo_conserva(tmp_path, estado, se_conserva):
    almacen = SesionGuardada(tmp_path / 'sesion.dat')
    almacen.guardar(URL, 'viejo')
    auth = AutenticacionSupabase(cliente_con(Mock(side_effect=ErrorSupabase('fallo', estado))))
    sesion, aviso = _restaurar_sesion(auth, almacen)
    assert sesion is None and aviso
    assert (almacen.leer(URL) == 'viejo') is se_conserva


def test_sin_marcar_recordar_no_se_entrega_el_token():
    guardados = []
    cliente = cliente_con(transporte_correcto)
    cliente.entrar('a@example.test', 'clave-de-prueba')
    assert guardados == []
    cliente.recordar(guardados.append)
    assert guardados == ['nuevo']
    cliente.limpiar()
    assert cliente.al_renovar is None


@solo_windows
@pytest.mark.parametrize('cierra_sesion', [False, True])
def test_cerrar_ventana_conserva_la_sesion_y_cerrar_sesion_la_revoca(tmp_path, cierra_sesion):
    from unittest.mock import patch
    from PySide6.QtWidgets import QApplication, QDialog
    from fraseya.presentacion import qt_aplicacion

    app = QApplication.instance() or QApplication([])
    (tmp_path / 'supabase.json').write_text(json.dumps({}), encoding='utf-8')
    almacen = SesionGuardada(tmp_path / 'sesion.dat')
    almacen.guardar(URL, 'viejo')
    llamadas = []

    def transporte(metodo, ruta, cuerpo, headers):
        llamadas.append(ruta)
        return transporte_correcto(metodo, ruta, cuerpo, headers)

    acceso = Mock()
    acceso.exec.return_value = QDialog.Rejected
    with patch.object(qt_aplicacion, 'cargar_cliente', return_value=cliente_con(transporte)), \
         patch.object(qt_aplicacion, 'AccesoQt', return_value=acceso) as dialogo, \
         patch.object(qt_aplicacion, '_ejecutar_sesion', return_value=cierra_sesion):
        qt_aplicacion.abrir(tmp_path / 'fraseya.db', con_teclado=False)
    app.processEvents()

    assert ('/auth/v1/logout' in llamadas) is cierra_sesion
    assert dialogo.called is cierra_sesion  # sesión recordada: no se pide contraseña
    assert almacen.leer(URL) == (None if cierra_sesion else 'nuevo')


@solo_windows
@pytest.mark.parametrize('recordar', [True, False])
def test_credenciales_se_guardan_cifradas_y_rellenan_el_acceso(tmp_path, recordar):
    from unittest.mock import patch
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from fraseya.presentacion import qt_aplicacion

    app = QApplication.instance() or QApplication([])
    (tmp_path / 'supabase.json').write_text('{}', encoding='utf-8')
    vistos, dialogos = [], []
    real = qt_aplicacion.AccesoQt

    def crear(auth):
        dialogo = real(auth)
        dialogos.append(dialogo)

        def actuar():
            vistos.append((dialogo.usuario.text(), dialogo.clave.text()))
            if len(dialogos) > 1:
                return dialogo.reject()
            dialogo.usuario.setText('a@example.test')
            dialogo.clave.setText('clave-de-prueba')
            dialogo.casilla_recordar.setChecked(recordar)
            dialogo.iniciar()

        QTimer.singleShot(50, actuar)
        return dialogo

    with patch.object(qt_aplicacion, 'cargar_cliente', return_value=cliente_con(transporte_correcto)), \
         patch.object(qt_aplicacion, 'AccesoQt', side_effect=crear), \
         patch.object(qt_aplicacion, '_ejecutar_sesion', return_value=True):  # «Cerrar sesión»
        qt_aplicacion.abrir(tmp_path / 'fraseya.db', con_teclado=False)
    app.processEvents()

    esperado = ('a@example.test', 'clave-de-prueba') if recordar else ('', '')
    assert vistos == [('', ''), esperado]
    archivo = tmp_path / 'acceso.dat'
    assert archivo.exists() is recordar
    if recordar:
        assert b'clave-de-prueba' not in archivo.read_bytes()
