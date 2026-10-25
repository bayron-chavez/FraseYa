import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from unittest.mock import Mock,patch
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QDialog
from fraseya.aplicacion.sesion import Sesion
from fraseya.presentacion.qt_aplicacion import abrir
from fraseya.presentacion.qt_expansion import ExpansionQt
from fraseya.presentacion.qt_vista import VentanaQt
from fraseya.aplicacion.gestion_frases import GestionFrases
from fraseya.infraestructura import RepositorioSQLite


def test_arranque_qt_offline_conserva_datos_y_cierra(tmp_path):
    app=QApplication.instance() or QApplication([])
    ruta=tmp_path/'fraseya.db'; (tmp_path/'supabase.json').write_text('{}')
    with RepositorioSQLite(ruta) as repo:
        g=GestionFrases(repo); g.crear('Persistente','!p','Hola {nombre}',g.categorias_propias()[0]['id'])
    auth=Mock(); auth._sesion=None; auth.cliente.url='https://example.supabase.co'
    acceso=Mock(); acceso.exec.return_value=QDialog.Accepted; acceso.sesion=Sesion('Offline','usuario','offline')
    def cerrar():
        for w in app.topLevelWidgets():
            if isinstance(w,VentanaQt): w.close()
    QTimer.singleShot(100,cerrar)
    with patch('fraseya.presentacion.qt_aplicacion.cargar_cliente'),patch('fraseya.presentacion.qt_aplicacion.AutenticacionSupabase',return_value=auth),patch('fraseya.presentacion.qt_aplicacion.AccesoQt',return_value=acceso):
        abrir(ruta,con_teclado=False)
    auth.cerrar.assert_called_once()
    with RepositorioSQLite(ruta) as repo: assert repo.listar_frases()[0]['titulo']=='Persistente'


def test_teclado_se_pausa_en_ventanas_propias():
    app=QApplication.instance() or QApplication([])
    with RepositorioSQLite(':memory:') as repo:
        ventana=VentanaQt(GestionFrases(repo),demostracion=True)
        with patch('fraseya.presentacion.qt_expansion.TecladoGlobal') as teclado:
            expansion=ExpansionQt(ventana,repo)
            with patch.object(QApplication,'activeWindow',return_value=ventana):
                expansion.actualizar_pausa(); assert teclado.return_value.pausado
            with patch.object(QApplication,'activeWindow',return_value=None):
                expansion.actualizar_pausa(); assert not teclado.return_value.pausado
            expansion.detener()
        ventana.close()
