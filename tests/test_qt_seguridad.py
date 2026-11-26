import os
import time
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
pytest.importorskip('PySide6')
from unittest.mock import Mock
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton
from fraseya.aplicacion.sesion import Sesion
from fraseya.aplicacion.gestion_frases import GestionFrases
from fraseya.infraestructura import RepositorioSQLite
from fraseya.presentacion.qt_dialogos import AccesoQt
from fraseya.presentacion.qt_paneles import PanelIA
from fraseya.presentacion.qt_vista import VentanaQt, EtiquetaSegura


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def esperar(app, predicado):
    limite = time.monotonic() + 3
    while not predicado() and time.monotonic() < limite:
        app.processEvents()
        time.sleep(.01)
    assert predicado()


def test_login_sin_doble_peticion_y_clave_limpiada(app):
    auth = Mock()
    auth.iniciar_sesion.return_value = Sesion('uno@example.test', 'usuario', 'sesion')
    d = AccesoQt(auth)
    d.usuario.setText('uno@example.test')
    d.clave.setText('clave-sintetica')
    d.iniciar()
    d.iniciar()
    assert d.clave.text() == ''
    esperar(app, lambda: not d.ocupada)
    auth.iniciar_sesion.assert_called_once_with('uno@example.test', 'clave-sintetica')
    assert d.sesion.rol == 'usuario'
    d.deleteLater()


def test_login_fallido_no_crea_sesion(app):
    auth = Mock()
    auth.iniciar_sesion.side_effect = ValueError('Correo o contraseña incorrectos.')
    d = AccesoQt(auth)
    d.clave.setText('clave-sintetica')
    d.iniciar()
    d.sin_conexion()
    auth.sin_conexion.assert_not_called()
    esperar(app, lambda: not d.ocupada)
    assert d.sesion is None and d.clave.text() == ''
    assert 'incorrectos' in d.aviso.text()
    d.reject()
    d.deleteLater()


def test_offline_no_expone_acciones_centrales_ni_html(app):
    with RepositorioSQLite(':memory:') as repo:
        g = GestionFrases(repo)
        cat = g.categorias_propias()[0]['id']
        g.crear('<img src="https://example.test/a">', '!html', 'Texto', cat)
        v = VentanaQt(g, autenticacion=Mock(), sesion=Sesion('Offline', 'usuario', 'offline'))
        assert not v.nav_ia.isEnabled()
        assert 'Catálogo compartido' not in [b.text().strip() for b in v.findChildren(QPushButton)]
        etiqueta = EtiquetaSegura('<b>Texto de usuario</b>')
        assert etiqueta.textFormat() == Qt.PlainText
        v.close()


def test_panel_ia_guarda_en_hilo_qt_y_no_publica(app):
    with RepositorioSQLite(':memory:') as repo:
        g = GestionFrases(repo)
        g.crear('Base', '!base', 'Texto', g.categorias_propias()[0]['id'])
        cliente = Mock()
        cliente.solicitar.side_effect = [
            {'sugerencias': []},
            {'titulo': 'Soporte', 'categoria': 'General', 'contenido': 'Estimado/a {nombre}, ¿en qué podemos ayudarle?'},
        ]
        panel = PanelIA(g, cliente)
        panel.mensaje.setPlainText('Necesito ayuda')
        panel.sugerir()
        panel.sugerir()
        esperar(app, lambda: not panel.ocupada)
        assert len(g.listar()) == 2 and all(f['origen'] == 'propia' for f in g.listar())
        assert cliente.solicitar.call_count == 2
        assert all(c.args[1] == '/functions/v1/fraseya-ia' for c in cliente.solicitar.call_args_list)
        panel.detener()
        panel.deleteLater()


def test_ia_integrada_en_ventana_guarda_y_protege_cierre(app):
    from PySide6.QtWidgets import QLabel as QtLabel
    with RepositorioSQLite(':memory:') as repo:
        g = GestionFrases(repo)
        g.crear('Base', '!base', 'Texto', g.categorias_propias()[0]['id'])
        auth = Mock()
        auth.cliente.solicitar.side_effect = [
            {'sugerencias': []},
            {'titulo': 'Soporte', 'categoria': 'General', 'contenido': 'Estimado/a {nombre}, ¿en qué podemos ayudarle?'},
        ]
        sesion = Sesion('admin@example.test', 'administrador', 'token')
        v = VentanaQt(g, demostracion=False, autenticacion=auth, sesion=sesion)
        assert all(lbl.textFormat() == Qt.PlainText for lbl in v.findChildren(QtLabel))

        v.abrir_ia()
        assert v.paginas.currentWidget() is v.panel_ia
        v.panel_ia.mensaje.setPlainText('Necesito ayuda urgente')
        v.panel_ia.sugerir()
        v.panel_ia.sugerir()
        assert v.tiene_operacion_en_curso()
        v.close()
        assert not v.banner.isHidden()

        esperar(app, lambda: not v.panel_ia.ocupada)
        assert len(g.listar()) == 2 and all(f['origen'] == 'propia' for f in g.listar())
        nueva = next(f for f in g.listar() if f['titulo'] == 'Soporte')
        v.panel_ia.elegir(nueva)
        assert v.paginas.currentWidget() is v._paginas['frases']
        assert v.seleccion['id'] == nueva['id']
        v.close()
