"""Listas desplegables: la marca sigue al mouse; el valor solo cambia con un clic."""
from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QAbstractItemView, QApplication, QWidget


class _SeguirMouse(QObject):
    def eventFilter(self, objeto, evento):
        if evento.type() == QEvent.MouseMove and isinstance(objeto, QWidget):
            vista = objeto.parent()
            if (isinstance(vista, QAbstractItemView) and vista.parent() is not None
                    and vista.parent().metaObject().className() == 'QComboBoxPrivateContainer'):
                indice = vista.indexAt(evento.position().toPoint())
                if indice.isValid() and indice != vista.currentIndex():
                    vista.setCurrentIndex(indice)
        return False


def activar():
    """Se instala una sola vez y vale para todos los desplegables de la aplicación."""
    app = QApplication.instance()
    if app is not None and app.findChild(_SeguirMouse) is None:
        app.installEventFilter(_SeguirMouse(app))
