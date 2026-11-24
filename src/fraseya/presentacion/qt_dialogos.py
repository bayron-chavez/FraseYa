"""Diálogos Qt de arranque y expansión global."""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit,
    QTextEdit, QDialogButtonBox, QMessageBox, QScrollArea,
)
from .identidad import recurso
from .qt_paneles import (
    boton, EtiquetaSegura as QLabel, FormularioVariablesQt, Trabajos,
)
from .qt_temas import estilo_actual


class DialogoRed(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(estilo_actual())
        self.trabajos = Trabajos(self)
        self.ocupada = False
        self.setWindowIcon(QIcon(str(recurso('fraseya.ico'))))

    def reject(self):
        if self.ocupada:
            return
        self.trabajos.detener()
        super().reject()

    def closeEvent(self, event):
        if self.ocupada:
            event.ignore()
        else:
            self.trabajos.detener()
            event.accept()


class AccesoQt(DialogoRed):
    def __init__(self, autenticacion):
        super().__init__()
        self.auth = autenticacion
        self.sesion = None
        self.setWindowTitle('FraseYa · Iniciar sesión')
        self.resize(430, 460)
        l = QVBoxLayout(self)
        l.setContentsMargins(40, 25, 40, 25)
        l.setSpacing(14)
        logo = QLabel()
        logo.setAlignment(Qt.AlignCenter)
        logo.setPixmap(QPixmap(str(recurso('logo.png'))).scaled(78, 78, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        l.addWidget(logo)
        titulo = QLabel('Bienvenido a FraseYa')
        titulo.setObjectName('heading')
        l.addWidget(titulo)
        self.usuario = QLineEdit()
        self.usuario.setPlaceholderText('Correo electrónico')
        l.addWidget(self.usuario)
        self.clave = QLineEdit()
        self.clave.setPlaceholderText('Contraseña')
        self.clave.setEchoMode(QLineEdit.Password)
        l.addWidget(self.clave)
        self.aviso = QLabel('')
        self.aviso.setWordWrap(True)
        l.addWidget(self.aviso)
        self.entrar = boton('Iniciar sesión', self.iniciar, True)
        l.addWidget(self.entrar)
        self.offline = boton('Trabajar sin conexión', self.sin_conexion)
        l.addWidget(self.offline)
        self.clave.returnPressed.connect(self.iniciar)

    def iniciar(self):
        if self.ocupada:
            return
        correo, clave = self.usuario.text(), self.clave.text()
        self.clave.clear()
        self.ocupada = True
        self.entrar.setEnabled(False)
        self.offline.setEnabled(False)
        self.aviso.setText('Conectando…')
        self.trabajos.ejecutar(lambda: self.auth.iniciar_sesion(correo, clave), self.terminar)

    def terminar(self, sesion, error):
        self.ocupada = False
        self.entrar.setEnabled(True)
        self.offline.setEnabled(True)
        if error:
            self.aviso.setText(str(error) if isinstance(error, (ValueError, PermissionError)) else 'No se pudo iniciar sesión.')
            return
        self.sesion = sesion
        self.trabajos.detener()
        self.accept()

    def sin_conexion(self):
        if self.ocupada:
            return
        self.sesion = self.auth.sin_conexion()
        self.trabajos.detener()
        self.accept()


def configurar_conexion(ruta, parent=None):
    from fraseya.infraestructura.supabase import validar_conexion
    import json
    d = QDialog(parent)
    d.setStyleSheet(estilo_actual())
    d.setWindowTitle('Conexión de FraseYa')
    d.resize(570, 280)
    l = QVBoxLayout(d)
    l.addWidget(QLabel('URL de Supabase y clave pública publishable o anon.'))
    url, clave = QLineEdit(), QLineEdit()
    url.setPlaceholderText('https://proyecto.supabase.co')
    clave.setPlaceholderText('Clave pública')
    l.addWidget(url)
    l.addWidget(clave)
    aviso = QLabel()
    aviso.setWordWrap(True)
    l.addWidget(aviso)
    botones = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
    l.addWidget(botones)

    def guardar():
        try:
            direccion, publica = validar_conexion(url.text(), clave.text())
            Path(ruta).parent.mkdir(parents=True, exist_ok=True)
            Path(ruta).write_text(json.dumps({'url': direccion, 'clave_publica': publica}), encoding='utf8')
        except (ValueError, OSError) as e:
            aviso.setText(str(e))
            return
        d.accept()

    botones.accepted.connect(guardar)
    botones.rejected.connect(d.reject)
    return d.exec() == QDialog.Accepted


def completar_variables(parent, contenido, nombres=None, iniciales=None, flotante=False):
    """Usado por la expansión global desde aplicaciones externas."""
    usar_flotante = bool(flotante or parent is None)
    d = QDialog(None if usar_flotante else parent)
    if usar_flotante:
        d.setWindowFlags(d.windowFlags() | Qt.WindowStaysOnTopHint)
    d.setWindowTitle('Completar campos')
    d.setStyleSheet(estilo_actual())
    d.resize(570, 450)
    l = QVBoxLayout(d)
    l.addWidget(QLabel('Vista previa de la respuesta'))
    preview = QTextEdit()
    preview.setObjectName('preview')
    preview.setReadOnly(True)
    l.addWidget(preview)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    l.addWidget(scroll)
    botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    l.addWidget(botones)

    def aceptar():
        if formulario.campos_faltantes():
            QMessageBox.warning(d, 'Campos pendientes', 'Complete todos los campos.')
            return
        d.accept()

    formulario = FormularioVariablesQt(scroll, preview, al_confirmar=aceptar)
    formulario.cargar(contenido, nombres=nombres, iniciales=iniciales)

    botones.accepted.connect(aceptar)
    botones.rejected.connect(d.reject)
    if usar_flotante:
        d.show()
        try:
            from fraseya.infraestructura.teclado_global import forzar_primer_plano
            forzar_primer_plano(int(d.winId()))
        except OSError:
            pass
        d.raise_()
        d.activateWindow()
        if formulario.nombres and formulario.nombres[0] in formulario.entradas:
            formulario.entradas[formulario.nombres[0]].setFocus()
    if d.exec() != QDialog.Accepted:
        return None
    return formulario.valores_limpios()
