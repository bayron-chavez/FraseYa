"""Paneles Qt integrados dentro de la ventana principal, sin ventanas emergentes."""
import queue
from threading import Thread
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QIcon, QPixmap, QColor
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QLabel as _QtLabel, QPushButton, QLineEdit, QTextEdit, QComboBox, QSpinBox,
    QListWidget, QListWidgetItem, QFrame, QSplitter, QScrollArea, QFileDialog,
)
from fraseya.aplicacion.resolver_variables import detectar, sustituir, valores_iniciales, faltantes
from fraseya.infraestructura.escritor_texto import VELOCIDAD_MAX_MS, VELOCIDAD_MIN_MS
from .qt_temas import ESTILO, ESTILO_OSCURO, hoja_estilo, paleta

PALETA_CATEGORIAS = [
    '#2875E8', '#0EA5E9', '#14B8A6', '#10B981', '#84CC16', '#EAB308',
    '#F97316', '#EF4444', '#EC4899', '#8B5CF6', '#6366F1', '#64748B',
]


def boton(texto, accion, principal=False, estilo=None):
    b = QPushButton(texto)
    if principal:
        b.setObjectName('primary')
    elif estilo:
        b.setObjectName(estilo)
    b.clicked.connect(accion)
    return b


class EtiquetaSegura(_QtLabel):
    """Los textos de usuarios y del modelo se muestran literalmente, sin HTML."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setTextFormat(Qt.PlainText)


QLabel = EtiquetaSegura


class Trabajos:
    def __init__(self, parent):
        self.cola = queue.Queue()
        self.activo = True
        self.pendientes = 0
        self.timer = QTimer(parent)
        self.timer.timeout.connect(self.atender)
        self.timer.start(50)
        parent.destroyed.connect(self.detener)

    def ejecutar(self, operacion, terminado):
        if not self.activo:
            return
        self.pendientes += 1

        def trabajar():
            try:
                resultado, error = operacion(), None
            except Exception as e:
                resultado, error = None, e
            self.cola.put((terminado, resultado, error))

        Thread(target=trabajar, daemon=True).start()

    def atender(self):
        while self.activo:
            try:
                callback, resultado, error = self.cola.get_nowait()
            except queue.Empty:
                return
            self.pendientes -= 1
            callback(resultado, error)

    def detener(self, *_):
        self.activo = False
        self.timer.stop()


def _cabecera_panel(titulo, subtitulo, al_volver=None, texto_volver='← Volver a Mis frases', accion_derecha=None):
    fila = QHBoxLayout()
    fila.setSpacing(12)
    titulos = QVBoxLayout()
    titulos.setSpacing(4)
    if al_volver is not None:
        volver = boton(texto_volver, al_volver, estilo='ghost')
        volver.setFixedHeight(34)
        fila_volver = QHBoxLayout()
        fila_volver.addWidget(volver)
        fila_volver.addStretch()
        titulos.addLayout(fila_volver)
    enc = QLabel(titulo)
    enc.setObjectName('heading')
    titulos.addWidget(enc)
    sub = QLabel(subtitulo)
    sub.setObjectName('muted')
    sub.setWordWrap(True)
    titulos.addWidget(sub)
    fila.addLayout(titulos, 1)
    if accion_derecha is not None:
        fila.addWidget(accion_derecha, 0, Qt.AlignBottom)
    return fila, enc, sub


class PanelIA(QWidget):
    """Asistente IA integrado en la ventana principal."""
    def __init__(self, gestion, cliente, administrador=False, *, al_elegir=None,
                 al_actualizar=None, al_abrir_empresa=None, al_copiar=None,
                 al_toggle_vivo=None, al_probar_vivo=None, al_analizar_portapapeles=None,
                 parent=None, trabajos=None):
        super().__init__(parent)
        from fraseya.aplicacion.recomendaciones_ia import RecomendadorIA
        self.gestion = gestion
        self.servicio = RecomendadorIA(cliente)
        self._al_elegir = al_elegir
        self._al_actualizar = al_actualizar
        self._al_abrir_empresa = al_abrir_empresa
        self._al_copiar = al_copiar
        self._al_toggle_vivo = al_toggle_vivo
        self._al_probar_vivo = al_probar_vivo
        self._al_analizar_portapapeles = al_analizar_portapapeles
        self.trabajos = trabajos or Trabajos(self)
        self._trabajos_propios = trabajos is None
        self.ocupada = False

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(14)

        self.btn_empresa = None
        if administrador and al_abrir_empresa is not None:
            self.btn_empresa = boton('Perfil de empresa', al_abrir_empresa)
        cab, _, _ = _cabecera_panel(
            'Asistente IA',
            'Una respuesta que parte del contexto. Al consultar se envían a Gemini el mensaje, hasta 40 frases y el perfil de empresa.',
            accion_derecha=self.btn_empresa,
        )
        raiz.addLayout(cab)

        tarjeta_vivo = QFrame()
        tarjeta_vivo.setObjectName('card')
        vl_vivo = QVBoxLayout(tarjeta_vivo)
        vl_vivo.setContentsMargins(18, 14, 18, 14)
        vl_vivo.setSpacing(8)

        fila_vivo_sup = QHBoxLayout()
        fila_vivo_sup.setSpacing(10)
        tit_vivo = QLabel('Asistente en vivo sobre WhatsApp (Web y Desktop)')
        tit_vivo.setObjectName('section')
        fila_vivo_sup.addWidget(tit_vivo, 1)

        self.btn_vivo = QPushButton('Activar ventanas flotantes')
        self.btn_vivo.setObjectName('theme_toggle')
        self.btn_vivo.setCheckable(True)
        self.btn_vivo.clicked.connect(self._alternar_vivo)
        fila_vivo_sup.addWidget(self.btn_vivo)

        self.btn_demo_vivo = boton('Probar ventanas flotantes', self._probar_vivo)
        fila_vivo_sup.addWidget(self.btn_demo_vivo)

        self.btn_portapapeles_vivo = boton('Analizar portapapeles', self._analizar_portapapeles_vivo, estilo='ghost')
        fila_vivo_sup.addWidget(self.btn_portapapeles_vivo)
        vl_vivo.addLayout(fila_vivo_sup)

        desc_vivo = QLabel(
            'Al abrir WhatsApp verás la barra flotante con el botón «Leer últimos 3» para obtener 3 opciones '
            'e insertarlas directo en el chat sin volver a FraseYa. Nunca envía mensajes automáticamente.'
        )
        desc_vivo.setObjectName('muted')
        desc_vivo.setWordWrap(True)
        vl_vivo.addWidget(desc_vivo)

        self.estado_vivo = QLabel('Estado: Pausado (opt-in). Activa las ventanas flotantes o pulsa «Probar ventanas flotantes».')
        self.estado_vivo.setObjectName('muted')
        self.estado_vivo.setWordWrap(True)
        vl_vivo.addWidget(self.estado_vivo)
        raiz.addWidget(tarjeta_vivo)

        divisor = QSplitter(Qt.Horizontal)

        entrada = QFrame()
        entrada.setObjectName('panel')
        el = QVBoxLayout(entrada)
        el.setContentsMargins(22, 18, 22, 18)
        el.setSpacing(12)
        t_in = QLabel('Contexto de la conversación')
        t_in.setObjectName('section')
        el.addWidget(t_in)
        info = QLabel('Pega el mensaje del cliente. Si no hay coincidencias en la biblioteca, se generará y guardará una frase propia para que la revises.')
        info.setObjectName('muted')
        info.setWordWrap(True)
        el.addWidget(info)

        self.mensaje = QTextEdit()
        self.mensaje.setAcceptRichText(False)
        self.mensaje.setPlaceholderText('Cliente: …\nAgente: …')
        self.mensaje.setMinimumHeight(140)
        el.addWidget(self.mensaje, 1)

        acciones = QHBoxLayout()
        acciones.addWidget(boton('Pegar mensaje', self.pegar))
        acciones.addWidget(boton('Limpiar', self.limpiar, estilo='ghost'))
        acciones.addStretch()
        self.consultar = boton('Preparar respuesta', self.sugerir, True)
        acciones.addWidget(self.consultar)
        el.addLayout(acciones)

        self.aviso = QLabel('')
        self.aviso.setObjectName('muted')
        self.aviso.setWordWrap(True)
        el.addWidget(self.aviso)
        divisor.addWidget(entrada)

        salida = QFrame()
        salida.setObjectName('panel')
        sl = QVBoxLayout(salida)
        sl.setContentsMargins(22, 18, 22, 18)
        sl.setSpacing(12)
        t_out = QLabel('Propuestas sugeridas')
        t_out.setObjectName('section')
        sl.addWidget(t_out)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        cuerpo = QWidget()
        cuerpo.setObjectName('scroll_content')
        self.resultados = QVBoxLayout(cuerpo)
        self.resultados.setContentsMargins(0, 0, 6, 0)
        self.resultados.setSpacing(12)
        self.resultados.setAlignment(Qt.AlignTop)
        scroll.setWidget(cuerpo)
        sl.addWidget(scroll, 1)
        divisor.addWidget(salida)
        divisor.setSizes([430, 520])
        raiz.addWidget(divisor, 1)

        self._mostrar_placeholder()

    def _alternar_vivo(self, activo=False):
        estado = bool(activo)
        self.btn_vivo.setText('Pausar ventanas flotantes' if estado else 'Activar ventanas flotantes')
        if self._al_toggle_vivo is not None:
            self._al_toggle_vivo(estado)
        else:
            self.estado_vivo.setText(
                'Estado: Activo. Observando ventanas de WhatsApp.'
                if estado else 'Estado: Pausado (opt-in).'
            )

    def establecer_estado_vivo(self, activo, texto_estado=None):
        estado = bool(activo)
        self.btn_vivo.blockSignals(True)
        self.btn_vivo.setChecked(estado)
        self.btn_vivo.setText('Pausar ventanas flotantes' if estado else 'Activar ventanas flotantes')
        self.btn_vivo.blockSignals(False)
        if texto_estado is not None:
            self.estado_vivo.setText(str(texto_estado))

    def _probar_vivo(self):
        if self._al_probar_vivo is not None:
            self._al_probar_vivo()
        else:
            self.estado_vivo.setText('Vista previa de ventanas flotantes no disponible en este contexto.')

    def _analizar_portapapeles_vivo(self):
        if self._al_analizar_portapapeles is not None:
            self._al_analizar_portapapeles()
            return
        texto = QApplication.clipboard().text()
        if not texto.strip():
            self.estado_vivo.setText('Portapapeles vacío. Copia un mensaje del cliente primero.')
            return
        if len(texto) > 4000:
            self.estado_vivo.setText('El mensaje del portapapeles supera 4.000 caracteres.')
            return
        self.mensaje.setPlainText(texto)
        self.estado_vivo.setText('Mensaje del portapapeles pegado en el contexto. Pulsa «Preparar respuesta».')

    def _limpiar_resultados(self):
        while self.resultados.count():
            item = self.resultados.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _mostrar_placeholder(self):
        self._limpiar_resultados()
        vacio = QLabel('Las respuestas recomendadas o generadas aparecerán aquí. Podrás copiarlas directamente o abrirlas en el editor.')
        vacio.setObjectName('muted')
        vacio.setWordWrap(True)
        self.resultados.addWidget(vacio)

    def limpiar(self):
        if self.ocupada:
            return
        self.mensaje.clear()
        self.aviso.setText('')
        self._mostrar_placeholder()

    def pegar(self):
        texto = QApplication.clipboard().text()
        if len(texto) > 4000:
            self.aviso.setText('El mensaje supera 4.000 caracteres.')
            return
        self.mensaje.setPlainText(texto)
        self.aviso.setText('')

    def sugerir(self):
        if self.ocupada:
            return
        from fraseya.aplicacion.recomendaciones_ia import preparar
        texto = self.mensaje.toPlainText()
        frases = self.gestion.listar()
        try:
            preparar(texto, frases)
        except ValueError as e:
            self.aviso.setText(str(e))
            return
        self.ocupada = True
        self.consultar.setEnabled(False)
        self.aviso.setText('Preparando propuesta…')
        self._limpiar_resultados()
        cargando = QLabel('Consultando al asistente…')
        cargando.setObjectName('muted')
        self.resultados.addWidget(cargando)

        def consultar():
            sugerencias = self.servicio.sugerir(texto, frases) if frases else []
            return (sugerencias, None) if sugerencias else ([], self.servicio.generar(texto, frases))

        self.trabajos.ejecutar(consultar, self.terminar)

    def terminar(self, resultado, error):
        from fraseya.aplicacion.recomendaciones_ia import guardar_generada, Sugerencia
        self.ocupada = False
        self.consultar.setEnabled(True)
        self._limpiar_resultados()
        if error:
            self.aviso.setText(str(error) if isinstance(error, (ValueError, PermissionError)) else 'No se pudo consultar la IA.')
            self._mostrar_placeholder()
            return
        sugerencias, generada = resultado
        try:
            if generada:
                f = guardar_generada(self.gestion, generada)
                sugerencias = [Sugerencia(f, 'Generada y guardada como propia. Revise contenido y datos personales.')]
                if self._al_actualizar:
                    self._al_actualizar()
        except ValueError as e:
            self.aviso.setText(str(e))
            self._mostrar_placeholder()
            return
        self.aviso.setText('Revise la respuesta antes de usarla.')
        for s in sugerencias:
            tarjeta = QFrame()
            tarjeta.setObjectName('card')
            tl = QVBoxLayout(tarjeta)
            tl.setContentsMargins(16, 14, 16, 14)
            tl.setSpacing(8)
            titulo = QLabel(s.frase['titulo'])
            titulo.setObjectName('section')
            tl.addWidget(titulo)
            motivo = QLabel(s.motivo)
            motivo.setObjectName('muted')
            motivo.setWordWrap(True)
            tl.addWidget(motivo)
            vista = QTextEdit()
            vista.setReadOnly(True)
            vista.setPlainText(s.frase['contenido'])
            vista.setMinimumHeight(90)
            vista.setMaximumHeight(140)
            tl.addWidget(vista)
            fila_b = QHBoxLayout()
            fila_b.addWidget(boton('Elegir esta frase', lambda checked=False, f=s.frase: self.elegir(f), True))
            if self._al_copiar is not None:
                fila_b.addWidget(boton('Completar y copiar', lambda checked=False, f=s.frase: self._al_copiar(f['contenido'], f['titulo'])))
            fila_b.addStretch()
            tl.addLayout(fila_b)
            self.resultados.addWidget(tarjeta)

    def elegir(self, frase):
        try:
            actual = self.gestion.repo.obtener_frase(frase['id'])
            if any(actual[c] != frase[c] for c in ('origen', 'abreviatura', 'contenido')):
                raise ValueError()
        except (ValueError, KeyError, LookupError):
            self.aviso.setText('La frase cambió. Solicite nuevas recomendaciones.')
            return
        if self._al_elegir:
            self._al_elegir(actual['id'])

    def detener(self):
        if self._trabajos_propios:
            self.trabajos.detener()


class PanelEmpresa(QWidget):
    """Perfil de empresa integrado para administradores."""
    def __init__(self, cliente, *, al_volver=None, parent=None, trabajos=None):
        super().__init__(parent)
        from fraseya.aplicacion.empresa_ia import EmpresaIA, CAMPOS
        self.servicio = EmpresaIA(cliente)
        self.trabajos = trabajos or Trabajos(self)
        self._trabajos_propios = trabajos is None
        self.ocupada = False
        self._cargado = False
        self.campos = {}
        self._contadores = {}

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(16)

        cab, _, _ = _cabecera_panel(
            'Perfil de empresa',
            'Contexto compartido con Gemini para mejorar las respuestas. No incluya claves ni datos personales.',
            al_volver=al_volver,
            texto_volver='← Volver al Asistente IA',
        )
        raiz.addLayout(cab)

        panel = QFrame()
        panel.setObjectName('panel')
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(24, 20, 24, 20)
        pl.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        contenido = QWidget()
        contenido.setObjectName('scroll_content')
        form = QVBoxLayout(contenido)
        form.setContentsMargins(0, 0, 14, 0)
        form.setSpacing(10)
        for k, maximo in CAMPOS.items():
            fila_lbl = QHBoxLayout()
            et = QLabel(k.capitalize())
            et.setObjectName('section')
            contador = QLabel(f'0 / {maximo} caracteres')
            contador.setObjectName('muted')
            contador.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            contador.setMinimumWidth(155)
            fila_lbl.addWidget(et)
            fila_lbl.addStretch()
            fila_lbl.addWidget(contador)
            form.addLayout(fila_lbl)
            e = QTextEdit()
            e.setAcceptRichText(False)
            e.setMinimumHeight(75)
            e.setMaximumHeight(120)
            e.textChanged.connect(lambda clave=k, lim=maximo: self._actualizar_contador(clave, lim))
            self.campos[k] = e
            self._contadores[k] = contador
            form.addWidget(e)
        scroll.setWidget(contenido)
        pl.addWidget(scroll, 1)

        pie = QHBoxLayout()
        self.aviso = QLabel('')
        self.aviso.setObjectName('muted')
        self.aviso.setWordWrap(True)
        pie.addWidget(self.aviso, 1)
        self.btn_recargar = boton('Recargar', self.recargar)
        pie.addWidget(self.btn_recargar)
        self.boton = boton('Guardar perfil', self.guardar, True)
        self.boton.setEnabled(False)
        pie.addWidget(self.boton)
        pl.addLayout(pie)
        raiz.addWidget(panel, 1)

    def _actualizar_contador(self, clave, maximo):
        largo = len(self.campos[clave].toPlainText())
        self._contadores[clave].setText(f'{largo} / {maximo} caracteres')

    def activar(self):
        if not self._cargado and not self.ocupada:
            self.recargar()

    def recargar(self):
        if self.ocupada:
            return
        self.ocupada = True
        self.boton.setEnabled(False)
        self.btn_recargar.setEnabled(False)
        self.aviso.setText('Cargando perfil de empresa…')
        self.trabajos.ejecutar(self.servicio.leer, self.cargar)

    def cargar(self, perfil, error):
        self.ocupada = False
        self.btn_recargar.setEnabled(True)
        if error:
            self.aviso.setText('No se pudo cargar el perfil. Pulsa Recargar para reintentar.')
            return
        self._cargado = True
        for k, e in self.campos.items():
            e.setPlainText(perfil[k])
        self.boton.setEnabled(True)
        self.aviso.setText('')

    def guardar(self):
        if self.ocupada:
            return
        perfil = {k: e.toPlainText() for k, e in self.campos.items()}
        self.ocupada = True
        self.boton.setEnabled(False)
        self.btn_recargar.setEnabled(False)
        self.aviso.setText('Guardando perfil…')
        self.trabajos.ejecutar(lambda: self.servicio.guardar(perfil), self.guardado)

    def guardado(self, _, error):
        self.ocupada = False
        self.boton.setEnabled(True)
        self.btn_recargar.setEnabled(True)
        self.aviso.setText(str(error) if error else 'Perfil guardado correctamente.')

    def detener(self):
        if self._trabajos_propios:
            self.trabajos.detener()


class PanelAjustes(QWidget):
    """Configuración integrada de expansión y sincronización."""
    def __init__(self, configuracion, *, al_guardar=None, parent=None):
        super().__init__(parent)
        from fraseya.infraestructura.teclado_global import TECLAS_CONFIRMACION
        self.configuracion = configuracion
        self._al_guardar = al_guardar

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(16)

        cab, _, _ = _cabecera_panel(
            'Configuración',
            'Personaliza cómo se expanden las abreviaturas y la frecuencia de sincronización.',
        )
        raiz.addLayout(cab)

        panel = QFrame()
        panel.setObjectName('panel')
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(28, 24, 28, 24)
        pl.setSpacing(16)

        form = QFormLayout()
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignLeft)
        self.tecla = QComboBox()
        self.tecla.addItems(list(TECLAS_CONFIRMACION))
        form.addRow(QLabel('Tecla de expansión'), self.tecla)

        self.atajo = QLineEdit()
        form.addRow(QLabel('Buscador rápido'), self.atajo)

        self.velocidad = QSpinBox()
        self.velocidad.setRange(VELOCIDAD_MIN_MS, VELOCIDAD_MAX_MS)
        form.addRow(QLabel('Velocidad de escritura (ms)'), self.velocidad)

        self.intervalo = QSpinBox()
        self.intervalo.setRange(1, 1440)
        form.addRow(QLabel('Sincronización (minutos)'), self.intervalo)

        self.tema = QComboBox()
        self.tema.addItem('Claro', 'claro')
        self.tema.addItem('Oscuro', 'oscuro')
        form.addRow(QLabel('Tema visual'), self.tema)
        pl.addLayout(form)

        ayuda = QLabel('Atajo recomendado: ctrl+alt+espacio. Los cambios se aplican al instante sin reiniciar.')
        ayuda.setObjectName('muted')
        ayuda.setWordWrap(True)
        pl.addWidget(ayuda)

        self.aviso = QLabel('')
        self.aviso.setObjectName('muted')
        self.aviso.setWordWrap(True)
        pl.addWidget(self.aviso)

        acciones = QHBoxLayout()
        acciones.addWidget(boton('Restablecer valores', self.restablecer, estilo='ghost'))
        acciones.addStretch()
        acciones.addWidget(boton('Guardar ajustes', self.guardar, True))
        pl.addLayout(acciones)

        raiz.addWidget(panel)
        raiz.addStretch(1)
        self.cargar()

    def establecer_tema(self, tema):
        indice = self.tema.findData(tema)
        self.tema.setCurrentIndex(indice if indice >= 0 else 0)

    def cargar(self):
        ajustes = self.configuracion.leer()
        self.tecla.setCurrentText(ajustes.tecla_confirmacion)
        self.atajo.setText(ajustes.atajo_buscador)
        self.velocidad.setValue(ajustes.velocidad_ms)
        self.intervalo.setValue(ajustes.intervalo_sincronizacion_min)
        self.establecer_tema(ajustes.tema)
        self.aviso.setText('')

    def restablecer(self):
        from fraseya.aplicacion.configuracion import Ajustes
        base = Ajustes()
        self.tecla.setCurrentText(base.tecla_confirmacion)
        self.atajo.setText(base.atajo_buscador)
        self.velocidad.setValue(base.velocidad_ms)
        self.intervalo.setValue(base.intervalo_sincronizacion_min)
        self.establecer_tema(base.tema)
        self.aviso.setText('Valores predeterminados cargados. Pulsa "Guardar ajustes" para aplicarlos.')

    def guardar(self):
        try:
            cambios = self.configuracion.guardar({
                'tecla_confirmacion': self.tecla.currentText(),
                'atajo_buscador': self.atajo.text(),
                'velocidad_ms': self.velocidad.value(),
                'intervalo_sincronizacion_min': self.intervalo.value(),
                'tema': self.tema.currentData(),
            })
        except ValueError as e:
            self.aviso.setText(str(e))
            return False
        if self._al_guardar:
            self._al_guardar(cambios)
        self.aviso.setText('Ajustes guardados y aplicados.')
        return True


class PanelImportar(QWidget):
    """Importación de frases desde Excel integrada en la ventana principal."""
    def __init__(self, gestion, autenticacion=None, sesion=None, *, al_importar=None, parent=None):
        super().__init__(parent)
        self.gestion = gestion
        self.autenticacion = autenticacion
        self.sesion = sesion
        self._al_importar = al_importar

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(16)

        cab, _, _ = _cabecera_panel(
            'Importar Excel',
            'Agrega frases propias desde una planilla .xlsx sin salir de FraseYa.',
        )
        raiz.addLayout(cab)

        panel = QFrame()
        panel.setObjectName('panel')
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(24, 22, 24, 22)
        pl.setSpacing(14)

        reglas = QLabel('Formato requerido: columnas en orden «categoría, título, abreviatura, contenido». Solo texto plano (sin fórmulas), máximo 10 MB y 10.000 filas.')
        reglas.setObjectName('muted')
        reglas.setWordWrap(True)
        pl.addWidget(reglas)

        fila = QHBoxLayout()
        self.ruta = QLineEdit()
        self.ruta.setPlaceholderText('Selecciona un archivo .xlsx o pega la ruta completa…')
        fila.addWidget(self.ruta, 1)
        fila.addWidget(boton('Examinar archivo…', self.examinar))
        pl.addLayout(fila)

        acciones = QHBoxLayout()
        self.aviso = QLabel('')
        self.aviso.setObjectName('muted')
        self.aviso.setWordWrap(True)
        acciones.addWidget(self.aviso, 1)
        acciones.addWidget(boton('Importar frases', self.ejecutar, True))
        pl.addLayout(acciones)
        raiz.addWidget(panel)

        res = QFrame()
        res.setObjectName('panel')
        rl = QVBoxLayout(res)
        rl.setContentsMargins(24, 20, 24, 20)
        rl.setSpacing(10)
        titulo_res = QLabel('Resultado de la importación')
        titulo_res.setObjectName('section')
        rl.addWidget(titulo_res)
        self.resumen = QLabel('Todavía no se ha importado ningún archivo en esta sesión.')
        self.resumen.setObjectName('muted')
        self.resumen.setWordWrap(True)
        rl.addWidget(self.resumen)
        self.detalle = QTextEdit()
        self.detalle.setObjectName('preview')
        self.detalle.setReadOnly(True)
        self.detalle.setPlaceholderText('Aquí verás el detalle de filas rechazadas si ocurriese algún problema.')
        rl.addWidget(self.detalle, 1)
        raiz.addWidget(res, 1)

    def examinar(self):
        ruta, _ = QFileDialog.getOpenFileName(self, 'Seleccionar archivo Excel', '', 'Excel (*.xlsx)')
        if ruta:
            self.ruta.setText(ruta)
            self.aviso.setText('')

    def ejecutar(self):
        from fraseya.aplicacion.importacion_excel import importar_excel
        ruta = self.ruta.text().strip()
        if not ruta:
            self.aviso.setText('Selecciona primero un archivo .xlsx.')
            return
        try:
            resultado = importar_excel(ruta, self.gestion, self.autenticacion, self.sesion)
        except (ValueError, PermissionError, OSError) as e:
            self.aviso.setText(str(e))
            return
        self.aviso.setText('Importación finalizada.')
        self.resumen.setText(f'Importadas: {resultado.importadas} · Rechazadas: {len(resultado.rechazadas)}')
        if resultado.rechazadas:
            lineas = [f'Fila {num}: {motivo}' for num, motivo in resultado.rechazadas]
            self.detalle.setPlainText('\n'.join(lineas))
        else:
            self.detalle.setPlainText('Todas las filas válidas se importaron sin errores.')
        if self._al_importar:
            self._al_importar()


class PanelCategorias(QWidget):
    """Gestión de categorías para administradores integrada con paleta visual de colores."""
    def __init__(self, gestion, autenticacion, sesion, *, al_cambiar=None, parent=None):
        super().__init__(parent)
        self.gestion = gestion
        self.autenticacion = autenticacion
        self.sesion = sesion
        self._al_cambiar = al_cambiar
        self._actual = None

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(16)

        cab, _, _ = _cabecera_panel(
            'Gestionar categorías',
            'Crea, renombra, asigna color o elimina categorías propias vacías.',
            accion_derecha=boton('+  Nueva categoría', self.nueva, True),
        )
        raiz.addLayout(cab)

        divisor = QSplitter(Qt.Horizontal)

        izq = QFrame()
        izq.setObjectName('panel')
        il = QVBoxLayout(izq)
        il.setContentsMargins(0, 18, 0, 10)
        t_izq = QLabel('Categorías propias')
        t_izq.setObjectName('section')
        t_izq.setContentsMargins(20, 0, 20, 6)
        il.addWidget(t_izq)
        self.lista = QListWidget()
        self.lista.currentItemChanged.connect(self._seleccionar)
        il.addWidget(self.lista)
        divisor.addWidget(izq)

        der = QFrame()
        der.setObjectName('panel')
        dl = QVBoxLayout(der)
        dl.setContentsMargins(24, 22, 24, 22)
        dl.setSpacing(12)

        self.titulo_modo = QLabel('Editar categoría')
        self.titulo_modo.setObjectName('section')
        dl.addWidget(self.titulo_modo)

        dl.addWidget(QLabel('Nombre'))
        self.nombre = QLineEdit()
        self.nombre.setPlaceholderText('Ej. Soporte técnico')
        dl.addWidget(self.nombre)

        dl.addWidget(QLabel('Color (#RRGGBB)'))
        fila_color = QHBoxLayout()
        self.muestra = QFrame()
        self.muestra.setFixedSize(36, 36)
        self.muestra.setStyleSheet('background:#2875E8; border:1px solid rgba(148,163,184,0.45); border-radius:8px;')
        fila_color.addWidget(self.muestra)
        self.color = QLineEdit('#2875E8')
        self.color.textChanged.connect(self._actualizar_muestra)
        fila_color.addWidget(self.color, 1)
        dl.addLayout(fila_color)

        et_paleta = QLabel('PALETA RÁPIDA')
        et_paleta.setObjectName('muted')
        dl.addWidget(et_paleta)

        rejilla = QGridLayout()
        rejilla.setSpacing(8)
        for idx, codigo in enumerate(PALETA_CATEGORIAS):
            b = QPushButton('')
            b.setToolTip(codigo)
            b.setFixedSize(34, 34)
            b.setStyleSheet(f'QPushButton {{background:{codigo}; border:2px solid transparent; border-radius:8px;}} QPushButton:hover {{border:2px solid #94a3b8;}}')
            b.clicked.connect(lambda checked=False, c=codigo: self.color.setText(c))
            rejilla.addWidget(b, idx // 6, idx % 6)
        wrap_paleta = QHBoxLayout()
        wrap_paleta.addLayout(rejilla)
        wrap_paleta.addStretch()
        dl.addLayout(wrap_paleta)

        self.confirmacion = QFrame()
        self.confirmacion.setObjectName('inline_confirm')
        cl = QHBoxLayout(self.confirmacion)
        cl.setContentsMargins(14, 10, 14, 10)
        self.txt_confirmacion = QLabel('')
        self.txt_confirmacion.setWordWrap(True)
        cl.addWidget(self.txt_confirmacion, 1)
        cl.addWidget(boton('Confirmar eliminación', self._confirmar_eliminar, estilo='danger'))
        cl.addWidget(boton('Cancelar', self._ocultar_confirmacion, estilo='ghost'))
        self.confirmacion.hide()
        dl.addWidget(self.confirmacion)

        self.aviso = QLabel('')
        self.aviso.setObjectName('muted')
        self.aviso.setWordWrap(True)
        dl.addWidget(self.aviso)

        dl.addStretch()
        acciones = QHBoxLayout()
        self.btn_eliminar = boton('Eliminar', self._pedir_eliminar)
        acciones.addWidget(self.btn_eliminar)
        acciones.addStretch()
        self.btn_guardar = boton('Guardar cambios', self.guardar, True)
        acciones.addWidget(self.btn_guardar)
        dl.addLayout(acciones)

        divisor.addWidget(der)
        divisor.setSizes([340, 560])
        raiz.addWidget(divisor, 1)
        self.recargar()

    def _actualizar_muestra(self, texto):
        col = QColor(texto.strip())
        if col.isValid():
            self.muestra.setStyleSheet(f'background:{col.name()}; border:1px solid rgba(148,163,184,0.45); border-radius:8px;')

    def recargar(self, seleccionar_id=None):
        self._ocultar_confirmacion()
        self.lista.blockSignals(True)
        self.lista.clear()
        elegida = None
        for c in self.gestion.categorias_propias():
            item = QListWidgetItem(c['nombre'])
            muestra = QPixmap(14, 14)
            muestra.fill(QColor(c['color']))
            item.setIcon(QIcon(muestra))
            item.setData(Qt.UserRole, c)
            self.lista.addItem(item)
            if seleccionar_id is not None and c['id'] == seleccionar_id:
                elegida = item
        self.lista.blockSignals(False)
        if elegida is not None:
            self.lista.setCurrentItem(elegida)
            self._seleccionar(elegida)
        elif self.lista.count():
            self.lista.setCurrentRow(0)
            self._seleccionar(self.lista.item(0))
        else:
            self.nueva()

    def _seleccionar(self, item, *_):
        if item is None:
            return
        self._ocultar_confirmacion()
        self._actual = item.data(Qt.UserRole)
        self.titulo_modo.setText('Editar categoría')
        self.nombre.setText(self._actual['nombre'])
        self.color.setText(self._actual['color'])
        self.btn_guardar.setText('Guardar cambios')
        self.btn_eliminar.setEnabled(True)
        self.aviso.setText('')

    def nueva(self):
        self._ocultar_confirmacion()
        self._actual = None
        self.lista.clearSelection()
        self.titulo_modo.setText('Nueva categoría')
        self.nombre.clear()
        self.color.setText('#2875E8')
        self.btn_guardar.setText('Crear categoría')
        self.btn_eliminar.setEnabled(False)
        self.aviso.setText('')
        self.nombre.setFocus()

    def guardar(self):
        self._ocultar_confirmacion()
        try:
            if self._actual is None:
                nuevo_id = self.gestion.crear_categoria(self.nombre.text(), self.autenticacion, self.sesion, self.color.text())
                self.aviso.setText('Categoría creada.')
                self.recargar(seleccionar_id=nuevo_id)
            else:
                ident = self._actual['id']
                self.gestion.editar_categoria(ident, self.nombre.text(), self.color.text(), self.autenticacion, self.sesion)
                self.aviso.setText('Categoría actualizada.')
                self.recargar(seleccionar_id=ident)
        except (ValueError, PermissionError) as e:
            self.aviso.setText(str(e))
            return
        if self._al_cambiar:
            self._al_cambiar()

    def _pedir_eliminar(self):
        if not self._actual:
            return
        self.txt_confirmacion.setText(f'¿Eliminar la categoría «{self._actual["nombre"]}»? Solo se eliminará si no tiene frases.')
        self.confirmacion.show()

    def _ocultar_confirmacion(self):
        self.confirmacion.hide()

    def _confirmar_eliminar(self):
        if not self._actual:
            return
        try:
            self.gestion.editar_categoria(self._actual['id'], self._actual['nombre'], self._actual['color'], self.autenticacion, self.sesion, eliminar=True)
        except (ValueError, PermissionError) as e:
            self._ocultar_confirmacion()
            self.aviso.setText(str(e))
            return
        self.aviso.setText('Categoría eliminada.')
        self.recargar()
        if self._al_cambiar:
            self._al_cambiar()


class PanelCatalogo(QWidget):
    """Publicación y retiro de frases del catálogo compartido dentro de la ventana principal."""
    def __init__(self, gestion, autenticacion, sesion, *, al_publicado=None, al_volver=None, parent=None, trabajos=None):
        super().__init__(parent)
        self.gestion = gestion
        self.autenticacion = autenticacion
        self.sesion = sesion
        self._al_publicado = al_publicado
        self._al_volver = al_volver
        self.trabajos = trabajos or Trabajos(self)
        self._trabajos_propios = trabajos is None
        self.ocupada = False
        self._modo_eliminar = False
        self._vista_previa = None
        self._servicio = None

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(16)

        cab, self.titulo, self.subtitulo = _cabecera_panel(
            'Publicar catálogo',
            'Revisa el resumen de cambios antes de publicar el catálogo compartido.',
            al_volver=al_volver,
        )
        raiz.addLayout(cab)

        self.panel_retiro = QFrame()
        self.panel_retiro.setObjectName('panel')
        prl = QVBoxLayout(self.panel_retiro)
        prl.setContentsMargins(24, 18, 24, 18)
        prl.setSpacing(10)
        t_ret = QLabel('Selecciona la frase compartida a retirar')
        t_ret.setObjectName('section')
        prl.addWidget(t_ret)
        fila_ret = QHBoxLayout()
        self.selector_retiro = QComboBox()
        fila_ret.addWidget(self.selector_retiro, 1)
        self.btn_preparar_retiro = boton('Preparar retiro', self._preparar)
        fila_ret.addWidget(self.btn_preparar_retiro)
        prl.addLayout(fila_ret)
        self.panel_retiro.hide()
        raiz.addWidget(self.panel_retiro)

        panel = QFrame()
        panel.setObjectName('panel')
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(24, 22, 24, 22)
        pl.setSpacing(14)

        t_res = QLabel('Resumen de cambios')
        t_res.setObjectName('section')
        pl.addWidget(t_res)

        self.tarjeta = QFrame()
        self.tarjeta.setObjectName('card')
        tl = QVBoxLayout(self.tarjeta)
        tl.setContentsMargins(18, 16, 18, 16)
        tl.setSpacing(6)
        self.resumen_version = QLabel('Preparando vista previa…')
        self.resumen_version.setObjectName('section')
        tl.addWidget(self.resumen_version)
        self.resumen_detalle = QLabel('')
        self.resumen_detalle.setObjectName('muted')
        self.resumen_detalle.setWordWrap(True)
        tl.addWidget(self.resumen_detalle)
        pl.addWidget(self.tarjeta)

        self.aviso = QLabel('')
        self.aviso.setObjectName('muted')
        self.aviso.setWordWrap(True)
        pl.addWidget(self.aviso)

        acciones = QHBoxLayout()
        self.btn_recomprobar = boton('Volver a comprobar', self._preparar)
        acciones.addWidget(self.btn_recomprobar)
        acciones.addStretch()
        self.btn_confirmar = boton('Confirmar y publicar', self._confirmar, True)
        self.btn_confirmar.setEnabled(False)
        acciones.addWidget(self.btn_confirmar)
        pl.addLayout(acciones)

        raiz.addWidget(panel)
        raiz.addStretch(1)

    def abrir(self, eliminar=False, frase_seleccionada=None):
        if self.ocupada:
            self.aviso.setText('Ya hay una operación de catálogo en curso.')
            return
        self._modo_eliminar = eliminar
        self._vista_previa = None
        self.btn_confirmar.setEnabled(False)
        if eliminar:
            self.titulo.setText('Retirar del catálogo')
            self.subtitulo.setText('Elige una frase compartida y confirma su retiro del catálogo central.')
            self.btn_confirmar.setText('Confirmar retiro')
            self.btn_confirmar.setObjectName('danger')
            self.btn_confirmar.style().unpolish(self.btn_confirmar)
            self.btn_confirmar.style().polish(self.btn_confirmar)
            self.panel_retiro.show()
            self.selector_retiro.clear()
            compartidas = [f for f in self.gestion.listar() if f['origen'] == 'compartida']
            indice_elegido = 0
            for idx, f in enumerate(compartidas):
                self.selector_retiro.addItem(f"{f['titulo']}  ({f['abreviatura']})", f['abreviatura'])
                if frase_seleccionada and frase_seleccionada.get('id') == f['id']:
                    indice_elegido = idx
            if not compartidas:
                self.btn_preparar_retiro.setEnabled(False)
                self.btn_recomprobar.setEnabled(False)
                self.resumen_version.setText('No hay frases compartidas para retirar.')
                self.resumen_detalle.setText('')
                self.aviso.setText('Primero publica frases en el catálogo compartido.')
                return
            self.btn_preparar_retiro.setEnabled(True)
            self.btn_recomprobar.setEnabled(True)
            self.selector_retiro.setCurrentIndex(indice_elegido)
        else:
            self.titulo.setText('Publicar catálogo')
            self.subtitulo.setText('Revisa el resumen de cambios antes de publicar en el catálogo compartido.')
            self.btn_confirmar.setText('Confirmar y publicar')
            self.btn_confirmar.setObjectName('primary')
            self.btn_confirmar.style().unpolish(self.btn_confirmar)
            self.btn_confirmar.style().polish(self.btn_confirmar)
            self.panel_retiro.hide()
            self.btn_recomprobar.setEnabled(True)
        self._preparar()

    def _preparar(self):
        from fraseya.aplicacion.publicacion_supabase import PublicacionSupabase
        if self.ocupada or not self.sesion or self.sesion.token == 'offline':
            return
        if self._modo_eliminar and self.selector_retiro.count() == 0:
            return
        self._servicio = PublicacionSupabase(self.gestion.repo, self.autenticacion, self.sesion)
        categorias = [] if self._modo_eliminar else self._servicio.recoger_categorias()
        operaciones = self.gestion.operaciones_categorias()
        eliminadas = (self.selector_retiro.currentData(),) if self._modo_eliminar else ()
        self._vista_previa = None
        self.ocupada = True
        self.btn_confirmar.setEnabled(False)
        self.btn_recomprobar.setEnabled(False)
        self.btn_preparar_retiro.setEnabled(False)
        self.resumen_version.setText('Preparando vista previa…')
        self.resumen_detalle.setText('')
        self.aviso.setText('Comprobando cambios con Supabase…')

        def vista_lista(vista, error):
            self.ocupada = False
            self.btn_recomprobar.setEnabled(True)
            self.btn_preparar_retiro.setEnabled(self.selector_retiro.count() > 0)
            if error:
                self.resumen_version.setText('No se pudo preparar la publicación.')
                self.resumen_detalle.setText('')
                self.aviso.setText(str(error))
                return
            self._vista_previa = vista
            self.resumen_version.setText(f'Versión {vista.version} · {vista.cantidad_frases} frases en total')
            self.resumen_detalle.setText(
                f'Nuevas: {vista.nuevas}   ·   Modificadas: {vista.modificadas}   ·   Eliminadas: {vista.eliminadas}'
            )
            self.aviso.setText('Revisa los números y pulsa el botón de confirmación para aplicar los cambios.')
            self.btn_confirmar.setEnabled(True)

        self.trabajos.ejecutar(
            lambda: self._servicio.preparar(categorias, eliminar=eliminadas, operaciones_categorias=operaciones),
            vista_lista,
        )

    def _confirmar(self):
        if self.ocupada or self._vista_previa is None or self._servicio is None:
            return
        vista = self._vista_previa
        self.ocupada = True
        self.btn_confirmar.setEnabled(False)
        self.btn_recomprobar.setEnabled(False)
        self.btn_preparar_retiro.setEnabled(False)
        self.aviso.setText('Publicando cambios en Supabase…')

        def publicado(resultado, error):
            self.ocupada = False
            self.btn_recomprobar.setEnabled(True)
            self.btn_preparar_retiro.setEnabled(self.selector_retiro.count() > 0)
            if error:
                self.aviso.setText(str(error))
                return
            self._vista_previa = None
            self.gestion.limpiar_operaciones_categorias()
            self.resumen_version.setText(f'Publicado correctamente · Versión {resultado.version}')
            self.aviso.setText('El catálogo compartido se actualizó y se iniciará la sincronización.')
            if self._al_publicado:
                self._al_publicado(resultado.version)

        self.trabajos.ejecutar(
            lambda: self._servicio.publicar(vista, confirmar_vacio=vista.cantidad_frases == 0),
            publicado,
        )

    def detener(self):
        if self._trabajos_propios:
            self.trabajos.detener()


class PanelUsuarios(QWidget):
    """Guía integrada para administrar cuentas y roles en Supabase."""
    def __init__(self, *, al_volver=None, parent=None):
        super().__init__(parent)
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(16)

        cab, _, _ = _cabecera_panel(
            'Administrar usuarios',
            'Las cuentas, contraseñas y permisos del equipo se gestionan de forma centralizada en Supabase.',
            al_volver=al_volver,
        )
        raiz.addLayout(cab)

        panel = QFrame()
        panel.setObjectName('panel')
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(28, 24, 28, 24)
        pl.setSpacing(14)

        paso1_t = QLabel('1. Altas y bajas de cuentas')
        paso1_t.setObjectName('section')
        pl.addWidget(paso1_t)
        paso1 = QLabel('Abre tu proyecto en Supabase → Authentication → Users para invitar personas, restablecer contraseñas o revocar accesos.')
        paso1.setObjectName('muted')
        paso1.setWordWrap(True)
        pl.addWidget(paso1)

        paso2_t = QLabel('2. Roles y habilitación')
        paso2_t.setObjectName('section')
        pl.addWidget(paso2_t)
        paso2 = QLabel('En Table Editor → public.fraseya_perfiles puedes activar cuentas (activo = true) y asignar el rol «usuario» o «administrador».')
        paso2.setObjectName('muted')
        paso2.setWordWrap(True)
        pl.addWidget(paso2)

        self.aviso = QLabel('')
        self.aviso.setObjectName('muted')
        pl.addWidget(self.aviso)

        acciones = QHBoxLayout()
        acciones.addWidget(boton('Copiar «fraseya_perfiles»', self._copiar))
        acciones.addStretch()
        pl.addLayout(acciones)

        raiz.addWidget(panel)
        raiz.addStretch(1)

    def _copiar(self):
        QApplication.clipboard().setText('fraseya_perfiles')
        self.aviso.setText('Nombre de tabla copiado al portapapeles.')


class FormularioVariablesQt:
    """Constructor reutilizable de campos y vista previa en vivo para variables de una frase."""

    def __init__(self, scroll: QScrollArea, preview: QTextEdit, *, al_confirmar=None):
        self._scroll = scroll
        self._preview = preview
        self._al_confirmar = al_confirmar
        self.contenido = ''
        self.nombres = []
        self.entradas = {}

    def cargar(self, contenido, nombres=None, iniciales=None):
        self.contenido = contenido
        self.nombres = list(nombres) if nombres is not None else detectar(contenido)
        valores_ini = iniciales if iniciales is not None else valores_iniciales(self.nombres)
        cuerpo = QWidget()
        cuerpo.setObjectName('scroll_content')
        form = QFormLayout(cuerpo)
        form.setContentsMargins(0, 0, 8, 0)
        form.setSpacing(12)
        self.entradas = {}
        primera = None
        for n in self.nombres:
            entrada = QLineEdit(valores_ini.get(n, ''))
            entrada.textChanged.connect(self.actualizar_preview)
            if self._al_confirmar is not None:
                entrada.returnPressed.connect(self._al_confirmar)
            self.entradas[n] = entrada
            form.addRow(QLabel(n.replace('_', ' ').capitalize()), entrada)
            if primera is None:
                primera = entrada
        self._scroll.setWidget(cuerpo)
        self.actualizar_preview()
        if primera is not None:
            primera.setFocus()

    def valores_crudos(self):
        return {n: e.text() for n, e in self.entradas.items()}

    def valores_limpios(self):
        return {n: e.text().strip() for n, e in self.entradas.items()}

    def campos_faltantes(self):
        return faltantes(self.nombres, self.valores_limpios())

    def actualizar_preview(self):
        valores = self.valores_crudos()
        self._preview.setPlainText(sustituir(self.contenido, valores))
        foco = self._scroll.focusWidget()
        for n, e in self.entradas.items():
            if e is foco:
                cursor = self._preview.document().find(e.text() or '{' + n + '}')
                if not cursor.isNull():
                    self._preview.setTextCursor(cursor)
                break


class PanelVariables(QWidget):
    """Panel integrado para completar variables de una frase y copiar la respuesta."""
    def __init__(self, *, al_copiar=None, al_cancelar=None, parent=None):
        super().__init__(parent)
        self._al_copiar = al_copiar
        self._al_cancelar = al_cancelar

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(16)

        cab, self.titulo, self.subtitulo = _cabecera_panel(
            'Completar campos',
            'Completa las variables de la frase y revisa la vista previa antes de copiarla.',
            al_volver=al_cancelar,
        )
        raiz.addLayout(cab)

        divisor = QSplitter(Qt.Horizontal)

        izq = QFrame()
        izq.setObjectName('panel')
        il = QVBoxLayout(izq)
        il.setContentsMargins(22, 20, 22, 20)
        il.setSpacing(12)
        t_campos = QLabel('Valores a completar')
        t_campos.setObjectName('section')
        il.addWidget(t_campos)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        il.addWidget(self._scroll, 1)

        self.aviso = QLabel('')
        self.aviso.setObjectName('muted')
        self.aviso.setWordWrap(True)
        il.addWidget(self.aviso)

        acciones = QHBoxLayout()
        acciones.addWidget(boton('Cancelar', self._cancelar, estilo='ghost'))
        acciones.addStretch()
        acciones.addWidget(boton('Copiar respuesta', self.confirmar, True))
        il.addLayout(acciones)
        divisor.addWidget(izq)

        der = QFrame()
        der.setObjectName('panel')
        dl = QVBoxLayout(der)
        dl.setContentsMargins(22, 20, 22, 20)
        dl.setSpacing(12)
        t_prev = QLabel('Vista previa de la respuesta')
        t_prev.setObjectName('section')
        dl.addWidget(t_prev)
        self.preview = QTextEdit()
        self.preview.setObjectName('preview')
        self.preview.setReadOnly(True)
        dl.addWidget(self.preview, 1)
        divisor.addWidget(der)
        divisor.setSizes([430, 520])
        raiz.addWidget(divisor, 1)

        self._formulario = FormularioVariablesQt(self._scroll, self.preview, al_confirmar=self.confirmar)

    @property
    def entradas(self):
        return self._formulario.entradas

    def cargar(self, contenido, titulo=''):
        self.subtitulo.setText(f'Frase: {titulo}' if titulo else 'Completa las variables y revisa la vista previa.')
        self.aviso.setText('')
        self._formulario.cargar(contenido)

    def confirmar(self):
        if self._formulario.campos_faltantes():
            self.aviso.setText('Complete todos los campos antes de copiar.')
            return False
        texto = sustituir(self._formulario.contenido, self._formulario.valores_limpios())
        QApplication.clipboard().setText(texto)
        if self._al_copiar:
            self._al_copiar(texto)
        return True

    def _cancelar(self):
        if self._al_cancelar:
            self._al_cancelar()
