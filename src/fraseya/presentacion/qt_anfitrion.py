"""Ventana única de FraseYa: el acceso y la aplicación son páginas de la misma ventana."""
from PySide6.QtCore import Qt, QEventLoop
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QStackedWidget, QWidget

from .identidad import recurso


class VentanaUnica(QStackedWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('FraseYa')
        self.setWindowIcon(QIcon(str(recurso('fraseya.ico'))))

    def mostrar(self, pagina):
        """Coloca la página (diálogo o ventana) en la ventana única y retira la anterior."""
        anterior = self.currentWidget()
        pagina.setWindowFlags(Qt.Widget)
        pagina.setWindowState(Qt.WindowNoState)
        self.addWidget(pagina)
        self.setCurrentWidget(pagina)
        pagina.show()
        if anterior is not None and anterior is not pagina:
            self.quitar(anterior)
        if not self.isVisible():
            self.showMaximized()

    def quitar(self, pagina):
        if isinstance(pagina, QWidget):
            self.removeWidget(pagina)
            pagina.deleteLater()

    def pedir_acceso(self, acceso):
        """Equivale a acceso.exec(), sin abrir una ventana aparte."""
        if not isinstance(acceso, QWidget):  # dobles de prueba
            return acceso.exec()
        bucle = QEventLoop()
        acceso.finished.connect(bucle.quit)
        self.mostrar(acceso)
        acceso.usuario.setFocus()
        bucle.exec()
        return acceso.result()

    def closeEvent(self, event):
        pagina = self.currentWidget()
        if isinstance(pagina, QDialog):
            if getattr(pagina, 'ocupada', False):
                event.ignore()
                return
            pagina.reject()
        elif pagina is not None and not pagina.close():
            event.ignore()
            return
        event.accept()
