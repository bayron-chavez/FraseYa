"""Los desplegables marcan la opción bajo el mouse y confirman solo con clic."""
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox

from fraseya.presentacion import qt_desplegables
from fraseya.presentacion.qt_temas import hoja_estilo


def test_marca_sigue_al_mouse_y_solo_el_clic_confirma():
    app = QApplication.instance() or QApplication([])
    qt_desplegables.activar()
    combo = QComboBox()
    combo.setStyleSheet(hoja_estilo())
    combo.addItems(['General', 'Promociones', 'Ventas'])
    combo.show()
    combo.showPopup()
    QTest.qWait(500)
    vista = combo.view()
    punto = vista.visualRect(combo.model().index(2, 0)).center()
    QTest.mouseMove(vista.viewport(), vista.visualRect(combo.model().index(1, 0)).center())
    QTest.mouseMove(vista.viewport(), punto)
    app.processEvents()
    assert vista.currentIndex().row() == 2
    assert combo.currentIndex() == 0
    QTest.mouseClick(vista.viewport(), Qt.LeftButton, pos=punto)
    app.processEvents()
    assert combo.currentIndex() == 2
    combo.close()
