import os,time
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
pytest.importorskip('PySide6')
from unittest.mock import Mock
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication,QPushButton
from fraseya.aplicacion.sesion import Sesion
from fraseya.aplicacion.gestion_frases import GestionFrases
from fraseya.infraestructura import RepositorioSQLite
from fraseya.presentacion.qt_dialogos import AccesoQt,IAQt
from fraseya.presentacion.qt_vista import VentanaQt,EtiquetaSegura


@pytest.fixture(scope='module')
def app(): return QApplication.instance() or QApplication([])


def esperar(app,predicado):
    limite=time.monotonic()+3
    while not predicado() and time.monotonic()<limite: app.processEvents(); time.sleep(.01)
    assert predicado()


def test_login_sin_doble_peticion_y_clave_limpiada(app):
    auth=Mock(); auth.iniciar_sesion.return_value=Sesion('uno@example.test','usuario','sesion')
    d=AccesoQt(auth); d.usuario.setText('uno@example.test'); d.clave.setText('clave-sintetica')
    d.iniciar(); d.iniciar()
    assert d.clave.text()==''
    esperar(app,lambda:not d.ocupada)
    auth.iniciar_sesion.assert_called_once_with('uno@example.test','clave-sintetica')
    assert d.sesion.rol=='usuario'; d.deleteLater()


def test_login_fallido_no_crea_sesion(app):
    auth=Mock(); auth.iniciar_sesion.side_effect=ValueError('Correo o contraseña incorrectos.')
    d=AccesoQt(auth); d.clave.setText('clave-sintetica'); d.iniciar()
    d.sin_conexion(); auth.sin_conexion.assert_not_called()
    esperar(app,lambda:not d.ocupada)
    assert d.sesion is None and d.clave.text()==''
    assert 'incorrectos' in d.aviso.text(); d.reject(); d.deleteLater()


def test_offline_no_expone_acciones_centrales_ni_html(app):
    with RepositorioSQLite(':memory:') as repo:
        g=GestionFrases(repo); cat=g.categorias_propias()[0]['id']
        g.crear('<img src="https://example.test/a">','!html','Texto',cat)
        v=VentanaQt(g,autenticacion=Mock(),sesion=Sesion('Offline','usuario','offline'))
        assert not v.nav_ia.isEnabled()
        assert 'Publicar catálogo' not in [b.text() for b in v.findChildren(QPushButton)]
        etiqueta=EtiquetaSegura('<b>Texto de usuario</b>')
        assert etiqueta.textFormat()==Qt.PlainText
        v.close()


def test_ia_guarda_en_hilo_qt_y_no_publica(app):
    with RepositorioSQLite(':memory:') as repo:
        g=GestionFrases(repo); g.crear('Base','!base','Texto',g.categorias_propias()[0]['id'])
        cliente=Mock(); cliente.solicitar.side_effect=[{'sugerencias':[]},
            {'titulo':'Soporte','categoria':'General','contenido':'Estimado/a {nombre}, ¿en qué podemos ayudarle?'}]
        v=VentanaQt(g,True); d=IAQt(v,cliente,g)
        d.mensaje.setPlainText('Necesito ayuda'); d.sugerir(); d.sugerir()
        esperar(app,lambda:not d.ocupada)
        assert len(g.listar())==2 and all(f['origen']=='propia' for f in g.listar())
        assert cliente.solicitar.call_count==2
        assert all(c.args[1]=='/functions/v1/fraseya-ia' for c in cliente.solicitar.call_args_list)
        d.reject(); d.deleteLater(); v.close()
