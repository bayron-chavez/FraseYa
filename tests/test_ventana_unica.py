"""El acceso y la aplicación comparten una sola ventana."""
from unittest.mock import Mock

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog, QMainWindow

from fraseya.presentacion.qt_anfitrion import VentanaUnica
from fraseya.presentacion.qt_dialogos import AccesoQt


def test_acceso_y_aplicacion_usan_la_misma_ventana():
    app = QApplication.instance() or QApplication([])
    anfitrion = VentanaUnica()
    acceso = AccesoQt(Mock())
    visto = {}

    def entrar():
        visto['dentro'] = acceso.window() is anfitrion and anfitrion.isVisible()
        acceso.sin_conexion()

    QTimer.singleShot(50, entrar)
    assert anfitrion.pedir_acceso(acceso) == QDialog.Accepted
    principal = QMainWindow()
    anfitrion.mostrar(principal)
    assert anfitrion.count() == 1
    assert visto['dentro']
    assert principal.window() is anfitrion and anfitrion.currentWidget() is principal
    assert anfitrion.isVisible()
    assert anfitrion.close()
    app.processEvents()


def test_cerrar_la_ventana_en_el_acceso_cancela():
    QApplication.instance() or QApplication([])
    anfitrion = VentanaUnica()
    QTimer.singleShot(50, anfitrion.close)
    assert anfitrion.pedir_acceso(AccesoQt(Mock())) == QDialog.Rejected
