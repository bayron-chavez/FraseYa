"""Diálogos Qt (arranque y expansión global) y envoltorios de compatibilidad."""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QTextEdit, QDialogButtonBox, QMessageBox, QScrollArea, QWidget,
)
from .qt_paneles import (
    ESTILO, boton, EtiquetaSegura as QLabel, Trabajos,
    PanelIA, PanelEmpresa, PanelAjustes,
)


def _estilo_actual():
    app = QApplication.instance()
    if app is not None:
        qss = app.styleSheet()
        if qss:
            return qss
    return ESTILO


class DialogoRed(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(_estilo_actual())
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


def recurso(nombre):
    import sys
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[3])) / 'assets' / nombre


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
    d.setStyleSheet(_estilo_actual())
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
    from fraseya.aplicacion.resolver_variables import detectar, sustituir, valores_iniciales, faltantes
    nombres = nombres or detectar(contenido)
    iniciales = iniciales or valores_iniciales(nombres)
    usar_flotante = bool(flotante or parent is None)
    d = QDialog(None if usar_flotante else parent)
    if usar_flotante:
        d.setWindowFlags(d.windowFlags() | Qt.WindowStaysOnTopHint)
    d.setWindowTitle('Completar campos')
    d.setStyleSheet(_estilo_actual())
    d.resize(570, 450)
    l = QVBoxLayout(d)
    l.addWidget(QLabel('Vista previa de la respuesta'))
    preview = QTextEdit()
    preview.setReadOnly(True)
    l.addWidget(preview)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    cuerpo = QWidget()
    cuerpo.setObjectName('scroll_content')
    form = QFormLayout(cuerpo)
    entradas = {}

    def actualizar():
        preview.setPlainText(sustituir(contenido, {n: e.text() for n, e in entradas.items()}))
        foco = d.focusWidget()
        for n, e in entradas.items():
            if e is foco:
                cursor = preview.document().find(e.text() or '{' + n + '}')
                if not cursor.isNull():
                    preview.setTextCursor(cursor)
                break

    for n in nombres:
        entrada = QLineEdit(iniciales.get(n, ''))
        entradas[n] = entrada
        entrada.textChanged.connect(actualizar)
        form.addRow(QLabel(n.replace('_', ' ').capitalize()), entrada)
    scroll.setWidget(cuerpo)
    l.addWidget(scroll)
    botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    l.addWidget(botones)

    def aceptar():
        if faltantes(nombres, {n: e.text() for n, e in entradas.items()}):
            QMessageBox.warning(d, 'Campos pendientes', 'Complete todos los campos.')
            return
        d.accept()

    botones.accepted.connect(aceptar)
    botones.rejected.connect(d.reject)
    actualizar()
    if usar_flotante:
        d.show()
        try:
            from fraseya.infraestructura.teclado_global import forzar_primer_plano
            forzar_primer_plano(int(d.winId()))
        except Exception:
            pass
        d.raise_()
        d.activateWindow()
        if nombres and nombres[0] in entradas:
            entradas[nombres[0]].setFocus()
    if d.exec() != QDialog.Accepted:
        return None
    return {n: e.text().strip() for n, e in entradas.items()}


class EmpresaQt(DialogoRed):
    """Envoltorio de compatibilidad sobre PanelEmpresa."""
    def __init__(self, parent, cliente):
        super().__init__(parent)
        self.setWindowTitle('Perfil de empresa')
        self.resize(630, 650)
        l = QVBoxLayout(self)
        l.setContentsMargins(20, 20, 20, 20)
        self.panel = PanelEmpresa(cliente, parent=self, trabajos=self.trabajos)
        l.addWidget(self.panel)
        self.campos = self.panel.campos
        self.aviso = self.panel.aviso
        self.boton = self.panel.boton
        self.panel.recargar()

    @property
    def ocupada(self):
        return self.panel.ocupada if hasattr(self, 'panel') else False

    @ocupada.setter
    def ocupada(self, valor):
        if hasattr(self, 'panel'):
            self.panel.ocupada = valor

    def guardar(self):
        self.panel.guardar()


class IAQt(DialogoRed):
    """Envoltorio de compatibilidad sobre PanelIA."""
    def __init__(self, parent, cliente, gestion, administrador=False):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle('FraseYa · Asistente IA')
        self.resize(860, 680)
        l = QVBoxLayout(self)
        l.setContentsMargins(20, 20, 20, 20)

        def al_elegir(ident):
            if parent is not None:
                parent.refrescar()
                parent.mostrar_id(ident)
            self.accept()

        def al_actualizar():
            if parent is not None:
                parent.refrescar()
                parent.frases_cambiaron()

        abrir_empresa = (lambda: EmpresaQt(self, cliente).exec()) if administrador else None
        self.panel = PanelIA(
            gestion, cliente, administrador,
            al_elegir=al_elegir, al_actualizar=al_actualizar,
            al_abrir_empresa=abrir_empresa, parent=self, trabajos=self.trabajos,
        )
        l.addWidget(self.panel)
        self.gestion = gestion
        self.servicio = self.panel.servicio
        self.mensaje = self.panel.mensaje
        self.consultar = self.panel.consultar
        self.aviso = self.panel.aviso
        self.resultados = self.panel.resultados

    @property
    def ocupada(self):
        return self.panel.ocupada if hasattr(self, 'panel') else False

    @ocupada.setter
    def ocupada(self, valor):
        if hasattr(self, 'panel'):
            self.panel.ocupada = valor

    def pegar(self):
        self.panel.pegar()

    def sugerir(self):
        self.panel.sugerir()

    def elegir(self, frase):
        self.panel.elegir(frase)


class AjustesQt(QDialog):
    """Envoltorio de compatibilidad sobre PanelAjustes."""
    def __init__(self, parent, configuracion, al_guardar):
        super().__init__(parent)
        self.setStyleSheet(_estilo_actual())
        self.setWindowTitle('Configuración')
        self.resize(580, 420)
        l = QVBoxLayout(self)
        l.setContentsMargins(20, 20, 20, 20)

        def guardar_y_cerrar(cambios):
            if al_guardar:
                al_guardar(cambios)
            self.accept()

        self.panel = PanelAjustes(configuracion, al_guardar=guardar_y_cerrar, parent=self)
        l.addWidget(self.panel)
