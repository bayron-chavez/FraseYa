"""Diálogos Qt de arranque y expansión global."""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLineEdit,
    QTextEdit, QDialogButtonBox, QMessageBox, QScrollArea, QCheckBox, QFrame,
)
from .identidad import recurso
from .qt_paneles import (
    boton, EtiquetaSegura as QLabel, FormularioVariablesQt, Trabajos,
)
from .qt_temas import estilo_actual


def _maximizar(dialogo):
    dialogo.setWindowFlags(dialogo.windowFlags() | Qt.WindowMinMaxButtonsHint)
    dialogo.setWindowState(Qt.WindowMaximized)


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


def _panel_marca():
    panel = QFrame()
    panel.setObjectName('marca')
    panel.setStyleSheet('QFrame#marca {background:#0a1f5c;}')
    l = QVBoxLayout(panel)
    l.setContentsMargins(80, 40, 60, 40)
    l.setSpacing(18)
    l.addStretch()
    logo = QLabel()
    logo.setPixmap(QPixmap(str(recurso('logo.png'))).scaled(130, 130, Qt.KeepAspectRatio, Qt.SmoothTransformation))
    l.addWidget(logo)
    textos = [('Las palabras,\na su tiempo.', 'color:#ffffff; font-size:44px; font-weight:700;')]
    textos += [('✓   ' + t, 'color:#dbeafe; font-size:18px;') for t in (
        'Expande frases con una abreviatura', 'Encuentra tus textos al instante',
        'Completa variables antes de copiar')]
    for texto, estilo in textos:
        etiqueta = QLabel(texto)
        etiqueta.setWordWrap(True)
        etiqueta.setStyleSheet(estilo)
        l.addWidget(etiqueta)
    l.addStretch()
    return panel


class AccesoQt(DialogoRed):
    def __init__(self, autenticacion):
        super().__init__()
        self.auth = autenticacion
        self.sesion = None
        self.recordar = False
        self.credenciales = None
        self._intento = None
        self.setWindowTitle('FraseYa · Iniciar sesión')
        self.resize(1100, 720)
        exterior = QHBoxLayout(self)
        exterior.setContentsMargins(0, 0, 0, 0)
        exterior.setSpacing(0)
        exterior.addWidget(_panel_marca(), 1)

        # Columna centrada de ancho fijo: el formulario no se estira al maximizar.
        columna = QWidget()
        columna.setFixedWidth(400)
        lado = QHBoxLayout()
        lado.addStretch()
        lado.addWidget(columna)
        lado.addStretch()
        exterior.addLayout(lado, 1)
        l = QVBoxLayout(columna)
        l.setSpacing(12)
        l.addStretch()
        titulo = QLabel('Iniciar sesión')
        titulo.setObjectName('heading')
        l.addWidget(titulo)
        l.addWidget(QLabel('Entra con la cuenta de tu equipo.'))
        l.addSpacing(14)
        l.addWidget(QLabel('Correo electrónico'))
        self.usuario = QLineEdit()
        self.usuario.setPlaceholderText('nombre@empresa.com')
        self.usuario.setMinimumHeight(44)
        l.addWidget(self.usuario)
        l.addWidget(QLabel('Contraseña'))
        self.clave = QLineEdit()
        self.clave.setPlaceholderText('Tu contraseña')
        self.clave.setEchoMode(QLineEdit.Password)
        self.clave.setMinimumHeight(44)
        l.addWidget(self.clave)
        self.casilla_recordar = QCheckBox('Recordar sesión en este equipo')
        l.addWidget(self.casilla_recordar)
        self.aviso = QLabel('')
        self.aviso.setWordWrap(True)
        l.addWidget(self.aviso)
        self.entrar = boton('Iniciar sesión', self.iniciar, True)
        self.entrar.setMinimumHeight(46)
        l.addWidget(self.entrar)
        self.offline = boton('Trabajar sin conexión', self.sin_conexion)
        self.offline.setMinimumHeight(44)
        l.addWidget(self.offline)
        l.addStretch()
        self.clave.returnPressed.connect(self.iniciar)

    def iniciar(self):
        if self.ocupada:
            return
        correo, clave = self.usuario.text(), self.clave.text()
        self.clave.clear()
        self._intento = (correo, clave)
        self.ocupada = True
        self.entrar.setEnabled(False)
        self.offline.setEnabled(False)
        self.aviso.setText('Conectando…')
        self.trabajos.ejecutar(lambda: self.auth.iniciar_sesion(correo, clave), self.terminar)

    def precargar(self, correo, clave):
        self.usuario.setText(correo)
        self.clave.setText(clave)
        self.casilla_recordar.setChecked(True)

    def terminar(self, sesion, error):
        intento, self._intento = self._intento, None
        self.ocupada = False
        self.entrar.setEnabled(True)
        self.offline.setEnabled(True)
        if error:
            self.aviso.setText(str(error) if isinstance(error, (ValueError, PermissionError)) else 'No se pudo iniciar sesión.')
            return
        self.sesion = sesion
        self.recordar = self.casilla_recordar.isChecked()
        self.credenciales = intento if self.recordar else None
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
    _maximizar(d)
    l = QVBoxLayout(d)
    l.setAlignment(Qt.AlignTop)
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
