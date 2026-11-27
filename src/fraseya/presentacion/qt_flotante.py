"""Ventanas flotantes no intrusivas del asistente IA de FraseYa (sin envío automático)."""
from PySide6.QtCore import QObject, QPoint, QRect, Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QScrollBar,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
try:
    from shiboken6 import isValid as _qt_valido
except ImportError:  # pragma: no cover
    def _qt_valido(obj):
        return obj is not None
from fraseya.aplicacion.resolver_variables import (
    detectar as _detectar_variables,
    faltantes as _variables_faltantes,
    sustituir as _sustituir_variables,
    valores_iniciales as _valores_iniciales_variables,
)
from fraseya.dominio.reglas import VARIABLES_OFICIALES, normalizar_texto
from fraseya.presentacion.qt_paneles import EtiquetaSegura
from fraseya.presentacion.qt_temas import PALETA_FLOTANTE, normalizar_tema

QLabel = EtiquetaSegura

ANCHO_FLOTANTE = 390
SEPARACION_VERTICAL = 10
MARGEN_PANTALLA = 16
MARGEN_SUPERIOR_VENTANA = 56
SEPARACION_CHAT = 12
MAX_TARJETAS = 3

FLAGS_FLOTANTE = (
    Qt.Tool
    | Qt.FramelessWindowHint
    | Qt.WindowStaysOnTopHint
    | Qt.WindowDoesNotAcceptFocus
)
FLAGS_FLOTANTE_EDICION = (
    Qt.Tool
    | Qt.FramelessWindowHint
    | Qt.WindowStaysOnTopHint
)

COLORES_TONO = {
    'empatica': '#10b981',
    'directa': '#2875e8',
    'escalar': '#8b5cf6',
}

NOMBRES_TONO = {
    'empatica': 'Empática',
    'directa': 'Directa',
    'escalar': 'Escalar',
}

TONOS_ORDEN = ('empatica', 'directa', 'escalar')


def _sin_tildes(texto):
    return normalizar_texto(texto)


def _normalizar_tono(tono, indice=1):
    clave = _sin_tildes(tono)
    if clave in COLORES_TONO:
        return clave
    return TONOS_ORDEN[(max(1, int(indice)) - 1) % len(TONOS_ORDEN)]


def _leer_campo(objeto, clave, defecto=None):
    if isinstance(objeto, dict):
        return objeto.get(clave, defecto)
    return getattr(objeto, clave, defecto)


def _extraer_opcion(opcion, indice_defecto=1):
    indice = _leer_campo(opcion, 'indice', indice_defecto)
    try:
        indice = int(indice) if indice is not None else indice_defecto
    except (TypeError, ValueError):
        indice = indice_defecto
    tono = _normalizar_tono(_leer_campo(opcion, 'tono', ''), indice)
    etiqueta = _leer_campo(opcion, 'etiqueta', '')
    if not isinstance(etiqueta, str) or not etiqueta.strip():
        etiqueta = f'Opción {indice} · {NOMBRES_TONO.get(tono, "Sugerida")}'
    frase_raw = _leer_campo(opcion, 'frase', None)
    if isinstance(frase_raw, dict):
        frase = frase_raw
    elif isinstance(opcion, dict) and 'contenido' in opcion:
        frase = opcion
    else:
        frase = {'contenido': str(frase_raw or '')}
    if 'contenido' not in frase or frase['contenido'] is None:
        frase = {**frase, 'contenido': ''}
    motivo = _leer_campo(opcion, 'motivo', '')
    motivo = str(motivo).strip() if motivo is not None else ''
    return {
        'indice': indice,
        'tono': tono,
        'etiqueta': etiqueta.strip(),
        'frase': frase,
        'motivo': motivo,
    }


def _extraer_resultado(resultado):
    tema = str(_leer_campo(resultado, 'tema', '') or '').strip()
    animo = str(_leer_campo(resultado, 'animo', '') or '').strip()
    urgencia = str(_leer_campo(resultado, 'urgencia', '') or '').strip()
    opciones = _leer_campo(resultado, 'opciones', ()) or ()
    return tema, animo, urgencia, list(opciones)[:MAX_TARJETAS]


class _VentanaFlotanteBase(QWidget):
    """Ventana superior sin bordes, arrastrable y que no roba foco por defecto."""

    def __init__(self, parent=None, *, tema='claro'):
        super().__init__(parent)
        self.tema = normalizar_tema(tema)
        self.arrastrada_manualmente = False
        self._arrastrando = False
        self._offset_arrastre = QPoint()

        self.setWindowFlags(FLAGS_FLOTANTE)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFixedWidth(ANCHO_FLOTANTE)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            hijo = self.childAt(event.position().toPoint())
            if isinstance(hijo, (QScrollBar, QAbstractButton, QComboBox, QLineEdit, QTextEdit)):
                super().mousePressEvent(event)
                return
            self._arrastrando = True
            self._offset_arrastre = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._arrastrando and (event.buttons() & Qt.LeftButton):
            self.move(event.globalPosition().toPoint() - self._offset_arrastre)
            self.arrastrada_manualmente = True
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._arrastrando:
            self._arrastrando = False
            event.accept()
            return
        super().mouseReleaseEvent(event)


class BarraFlotanteIA(_VentanaFlotanteBase):
    """Píldora flotante compacta con estado del asistente IA y contexto del chat."""

    def __init__(
        self,
        parent=None,
        *,
        activo=False,
        tema='claro',
        al_toggle_activo=None,
        al_leer_chat=None,
        al_analizar_portapapeles=None,
        al_ocultar=None,
    ):
        super().__init__(parent, tema=tema)
        self.activo = bool(activo)
        self._cargando = False
        self._al_toggle_activo = al_toggle_activo
        self._al_leer_chat = al_leer_chat
        self._al_analizar_portapapeles = al_analizar_portapapeles
        self._al_ocultar = al_ocultar
        self._tema_chat = ''
        self._animo_chat = ''
        self._urgencia_chat = ''

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        self.marco = QFrame(self)
        self.marco.setObjectName('barra_marco')
        ml = QVBoxLayout(self.marco)
        ml.setContentsMargins(12, 10, 12, 10)
        ml.setSpacing(7)

        fila_sup = QHBoxLayout()
        fila_sup.setContentsMargins(0, 0, 0, 0)
        fila_sup.setSpacing(6)

        self.indicador = QFrame(self.marco)
        self.indicador.setObjectName('barra_indicador')
        self.indicador.setFixedSize(8, 8)
        fila_sup.addWidget(self.indicador)

        self.lbl_titulo = QLabel('FraseYa IA', self.marco)
        self.lbl_titulo.setObjectName('barra_titulo')
        fila_sup.addWidget(self.lbl_titulo)

        self.btn_estado = QPushButton(self.marco)
        self.btn_estado.setObjectName('btn_estado')
        self.btn_estado.setCursor(Qt.PointingHandCursor)
        self.btn_estado.setToolTip('Activar o pausar la barra flotante sobre WhatsApp')
        self.btn_estado.clicked.connect(self._alternar_estado)
        fila_sup.addWidget(self.btn_estado)

        fila_sup.addStretch(1)

        self.btn_cerrar = QPushButton('×', self.marco)
        self.btn_cerrar.setObjectName('btn_cerrar')
        self.btn_cerrar.setFixedSize(22, 22)
        self.btn_cerrar.setCursor(Qt.PointingHandCursor)
        self.btn_cerrar.setToolTip('Ocultar ventanas flotantes')
        self.btn_cerrar.clicked.connect(self._invocar_ocultar)
        fila_sup.addWidget(self.btn_cerrar)

        ml.addLayout(fila_sup)

        fila_acciones = QHBoxLayout()
        fila_acciones.setContentsMargins(0, 0, 0, 0)
        fila_acciones.setSpacing(6)

        self.btn_leer_chat = QPushButton('Leer últimos 3', self.marco)
        self.btn_leer_chat.setObjectName('btn_leer_chat')
        self.btn_leer_chat.setCursor(Qt.PointingHandCursor)
        self.btn_leer_chat.setToolTip('Leer los últimos mensajes del chat (cliente y agente) y sugerir 3 respuestas')
        self.btn_leer_chat.clicked.connect(self._invocar_leer_chat)
        fila_acciones.addWidget(self.btn_leer_chat)

        self.btn_portapapeles = QPushButton('Portapapeles', self.marco)
        self.btn_portapapeles.setObjectName('btn_portapapeles')
        self.btn_portapapeles.setCursor(Qt.PointingHandCursor)
        self.btn_portapapeles.setToolTip('Analizar manualmente el mensaje copiado en el portapapeles')
        self.btn_portapapeles.clicked.connect(self._invocar_portapapeles)
        fila_acciones.addWidget(self.btn_portapapeles)

        fila_acciones.addStretch(1)
        ml.addLayout(fila_acciones)

        fila_chips = QHBoxLayout()
        fila_chips.setContentsMargins(0, 0, 0, 0)
        fila_chips.setSpacing(5)

        self.chip_tema = QLabel('En espera', self.marco)
        self.chip_tema.setObjectName('chip_tema')
        self.chip_tema.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        fila_chips.addWidget(self.chip_tema)

        self.chip_animo = QLabel('Ánimo: —', self.marco)
        self.chip_animo.setObjectName('chip_animo')
        self.chip_animo.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        fila_chips.addWidget(self.chip_animo)

        self.chip_urgencia = QLabel('Urgencia: —', self.marco)
        self.chip_urgencia.setObjectName('chip_urgencia')
        self.chip_urgencia.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        fila_chips.addWidget(self.chip_urgencia)

        fila_chips.addStretch(1)
        ml.addLayout(fila_chips)

        self.lbl_aviso = QLabel('', self.marco)
        self.lbl_aviso.setObjectName('barra_aviso')
        self.lbl_aviso.setWordWrap(True)
        self.lbl_aviso.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.lbl_aviso.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.lbl_aviso.setMaximumHeight(16777215)
        self.lbl_aviso.hide()
        ml.addWidget(self.lbl_aviso)

        raiz.addWidget(self.marco)

        self._actualizar_visual_estado()
        self.aplicar_tema(self.tema)
        self._recalcular_altura()

    def _alternar_estado(self):
        self.establecer_activo(not self.activo)
        if self._al_toggle_activo is not None:
            self._al_toggle_activo(self.activo)

    def _invocar_leer_chat(self):
        if self._cargando:
            return
        if self._al_leer_chat is not None:
            self._al_leer_chat()

    def _invocar_portapapeles(self):
        if self._cargando:
            return
        if self._al_analizar_portapapeles is not None:
            self._al_analizar_portapapeles()

    def _invocar_ocultar(self):
        if self._al_ocultar is not None:
            self._al_ocultar()
        else:
            self.hide()

    def _actualizar_visual_estado(self):
        self.btn_estado.setText('ACTIVA' if self.activo else 'PAUSADA')
        self.btn_estado.setProperty('activo', self.activo)
        self.indicador.setProperty('activo', self.activo)

    def establecer_activo(self, activo):
        self.activo = bool(activo)
        self._actualizar_visual_estado()
        self.aplicar_tema(self.tema)

    def establecer_cargando(self, cargando):
        self._cargando = bool(cargando)
        self.btn_leer_chat.setEnabled(not self._cargando)
        self.btn_leer_chat.setText('Leyendo…' if self._cargando else 'Leer últimos 3')
        self.btn_portapapeles.setEnabled(not self._cargando)

    def _recalcular_altura(self):
        ancho_barra = self.width() or ANCHO_FLOTANTE
        ml = self.marco.layout()
        margen_h = (ml.contentsMargins().left() + ml.contentsMargins().right()) if ml is not None else 24
        ancho_aviso = max(120, ancho_barra - margen_h - 2)  # 2 px por borde de barra_marco

        texto_aviso = self.lbl_aviso.text().strip()
        if texto_aviso and not self.lbl_aviso.isHidden():
            self.lbl_aviso.ensurePolished()
            self.lbl_aviso.setMaximumHeight(16777215)
            # Ancho interno real del texto dentro de barra_aviso: padding 8px*2 + border 1px*2 = 18px
            ancho_texto = max(80, ancho_aviso - 18)
            fm = QFontMetrics(self.lbl_aviso.font())
            rect_txt = fm.boundingRect(QRect(0, 0, ancho_texto, 2000), Qt.TextWordWrap, texto_aviso)
            # Padding vertical 5px*2 + border 1px*2 + 4px de holgura
            alto_fm = rect_txt.height() + 16
            alto_hfw = self.lbl_aviso.heightForWidth(ancho_aviso)
            alto_aviso = max(alto_fm, alto_hfw if alto_hfw > 0 else 0, fm.lineSpacing() + 12)
            self.lbl_aviso.setMinimumHeight(alto_aviso)
        else:
            self.lbl_aviso.setMinimumHeight(0)

        self.lbl_aviso.updateGeometry()
        if ml is not None:
            ml.invalidate()
            ml.activate()
        self.marco.updateGeometry()
        if self.layout() is not None:
            self.layout().invalidate()
            self.layout().activate()
        self.updateGeometry()

        alto_hfw_win = self.layout().totalHeightForWidth(ancho_barra) if (
            self.layout() is not None and self.layout().hasHeightForWidth()
        ) else -1
        hint = self.sizeHint()
        min_hint = self.minimumSizeHint()
        alto_final = max(
            alto_hfw_win if alto_hfw_win > 0 else 0,
            hint.height() if hint.isValid() else 0,
            min_hint.height() if min_hint.isValid() else 0,
        )
        if alto_final > 0:
            self.resize(ancho_barra, alto_final)
        else:
            super().adjustSize()

    def adjustSize(self):
        self._recalcular_altura()

    def actualizar_contexto(self, tema='', animo='', urgencia=''):
        self._tema_chat = str(tema or '').strip()
        self._animo_chat = str(animo or '').strip()
        self._urgencia_chat = str(urgencia or '').strip()

        def _acortar(valor, limite=22):
            return valor if len(valor) <= limite else valor[: limite - 1].rstrip() + '…'

        self.chip_tema.setText(_acortar(self._tema_chat) if self._tema_chat else 'En espera')
        self.chip_animo.setText(
            f'Ánimo: {_acortar(self._animo_chat, 14)}' if self._animo_chat else 'Ánimo: —'
        )
        self.chip_urgencia.setText(
            f'Urgencia: {_acortar(self._urgencia_chat, 12)}' if self._urgencia_chat else 'Urgencia: —'
        )
        self.aplicar_tema(self.tema)
        self._recalcular_altura()

    def limpiar_contexto(self, estado='Esperando mensaje…'):
        self._tema_chat = ''
        self._animo_chat = ''
        self._urgencia_chat = ''
        texto_estado = str(estado or 'Esperando mensaje…').strip()
        self.chip_tema.setText(texto_estado)
        self.chip_animo.setText('Ánimo: —')
        self.chip_urgencia.setText('Urgencia: —')
        self.lbl_aviso.setText('')
        self.lbl_aviso.hide()
        self.aplicar_tema(self.tema)
        self._recalcular_altura()

    def mostrar_aviso(self, texto=''):
        limpio = str(texto or '').strip()
        self.lbl_aviso.setText(limpio)
        self.lbl_aviso.setVisible(bool(limpio))
        self._recalcular_altura()

    def aplicar_tema(self, tema):
        self.tema = normalizar_tema(tema)
        p = PALETA_FLOTANTE[self.tema]

        animo_norm = _sin_tildes(self._animo_chat)
        animo_rojo = any(k in animo_norm for k in ('molest', 'enoj', 'frustr', 'reclam', 'negativ'))
        animo_bg = p['chip_animo_rojo_fondo'] if animo_rojo else p['chip_animo_ambar_fondo']
        animo_bd = p['chip_animo_rojo_borde'] if animo_rojo else p['chip_animo_ambar_borde']
        animo_fg = p['chip_animo_rojo_texto'] if animo_rojo else p['chip_animo_ambar_texto']

        urg_norm = _sin_tildes(self._urgencia_chat)
        urg_alta = any(k in urg_norm for k in ('alta', 'urgent', 'media', 'crit'))
        urg_bg = p['chip_urgencia_alta_fondo'] if urg_alta else p['chip_urgencia_neutra_fondo']
        urg_bd = p['chip_urgencia_alta_borde'] if urg_alta else p['chip_urgencia_neutra_borde']
        urg_fg = p['chip_urgencia_alta_texto'] if urg_alta else p['chip_urgencia_neutra_texto']

        estado_bg = p['activo_fondo'] if self.activo else p['pausada_fondo']
        estado_hover = p['activo_hover'] if self.activo else p['pausada_hover']
        estado_fg = p['activo_texto'] if self.activo else p['pausada_texto']

        self.setStyleSheet(f'''
            QWidget {{
                font-family: 'Segoe UI';
                font-size: 12px;
                background: transparent;
            }}
            QFrame#barra_marco {{
                background: {p['barra_fondo']};
                border: 1px solid {p['barra_borde']};
                border-radius: 12px;
            }}
            QFrame#barra_indicador {{
                background: {estado_bg};
                border-radius: 4px;
                border: 0;
            }}
            QLabel#barra_titulo {{
                color: {p['barra_texto']};
                font-size: 13px;
                font-weight: 700;
                background: transparent;
            }}
            QLabel#barra_aviso {{
                background: {p['aviso_fondo']};
                color: {p['aviso_texto']};
                border: 1px solid {p['aviso_borde']};
                border-radius: 7px;
                padding: 5px 8px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton#btn_estado {{
                background: {estado_bg};
                color: {estado_fg};
                border: 0;
                border-radius: 9px;
                padding: 3px 8px;
                font-size: 10px;
                font-weight: 700;
            }}
            QPushButton#btn_estado:hover {{
                background: {estado_hover};
            }}
            QPushButton#btn_leer_chat {{
                background: {p['btn_primario_fondo']};
                color: {p['btn_primario_texto']};
                border: 0;
                border-radius: 7px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 700;
            }}
            QPushButton#btn_leer_chat:hover {{
                background: {p['btn_primario_hover']};
            }}
            QPushButton#btn_leer_chat:disabled {{
                background: {p['btn_primario_disabled']};
            }}
            QPushButton#btn_portapapeles {{
                background: {p['barra_boton_fondo']};
                color: {p['barra_boton_texto']};
                border: 1px solid {p['barra_boton_borde']};
                border-radius: 7px;
                padding: 4px 9px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton#btn_portapapeles:hover {{
                background: {p['barra_boton_hover']};
            }}
            QPushButton#btn_portapapeles:disabled {{
                opacity: 0.6;
            }}
            QPushButton#btn_cerrar {{
                background: transparent;
                color: {p['barra_boton_texto']};
                border: 0;
                border-radius: 6px;
                font-size: 15px;
                font-weight: 700;
                padding: 0;
            }}
            QPushButton#btn_cerrar:hover {{
                background: {p['barra_cerrar_hover']};
            }}
            QLabel#chip_tema {{
                background: {p['chip_tema_fondo']};
                color: {p['chip_tema_texto']};
                border: 1px solid {p['chip_tema_borde']};
                border-radius: 6px;
                padding: 2px 6px;
                font-size: 11px;
                font-weight: 600;
            }}
            QLabel#chip_animo {{
                background: {animo_bg};
                color: {animo_fg};
                border: 1px solid {animo_bd};
                border-radius: 6px;
                padding: 2px 6px;
                font-size: 11px;
                font-weight: 600;
            }}
            QLabel#chip_urgencia {{
                background: {urg_bg};
                color: {urg_fg};
                border: 1px solid {urg_bd};
                border-radius: 6px;
                padding: 2px 6px;
                font-size: 11px;
                font-weight: 600;
            }}
        ''')


class TarjetaSugerenciaFlotante(_VentanaFlotanteBase):
    """Tarjeta flotante independiente para una respuesta aprobada con edición inline."""

    def __init__(
        self,
        opcion,
        parent=None,
        *,
        indice=1,
        tema='claro',
        al_usar=None,
        al_descartar=None,
        al_cambiar_tamano=None,
        nombre_contacto='',
    ):
        super().__init__(parent, tema=tema)
        datos = _extraer_opcion(opcion, indice_defecto=indice)
        self.opcion = opcion
        self.indice = datos['indice']
        self.tono = datos['tono']
        self.etiqueta = datos['etiqueta']
        self.frase = datos['frase']
        self.motivo = datos['motivo']
        self._nombre_contacto = str(nombre_contacto or '').strip()[:120]
        self.color_cabecera = COLORES_TONO.get(self.tono, COLORES_TONO['directa'])
        self.en_edicion = False
        self.en_variables = False
        self._nombres_variables: list[str] = []
        self._campos_variables: dict[str, QLineEdit] = {}

        self._al_usar = al_usar
        self._al_descartar = al_descartar
        self._al_cambiar_tamano = al_cambiar_tamano

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        self.marco = QFrame(self)
        self.marco.setObjectName('tarjeta_marco')
        ml = QVBoxLayout(self.marco)
        ml.setContentsMargins(1, 1, 1, 1)
        ml.setSpacing(0)

        # Encabezado de color según tono
        self.cabecera = QFrame(self.marco)
        self.cabecera.setObjectName('tarjeta_cabecera')
        self.cabecera.setFixedHeight(34)
        self.cabecera.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        cl = QHBoxLayout(self.cabecera)
        cl.setContentsMargins(12, 6, 8, 6)
        cl.setSpacing(6)

        self.lbl_etiqueta = QLabel(self.etiqueta, self.cabecera)
        self.lbl_etiqueta.setObjectName('tarjeta_etiqueta')
        cl.addWidget(self.lbl_etiqueta)
        cl.addStretch(1)

        self.btn_descartar = QPushButton('×', self.cabecera)
        self.btn_descartar.setObjectName('btn_descartar')
        self.btn_descartar.setFixedSize(22, 22)
        self.btn_descartar.setCursor(Qt.PointingHandCursor)
        self.btn_descartar.setToolTip('Descartar esta sugerencia')
        self.btn_descartar.clicked.connect(self.descartar)
        cl.addWidget(self.btn_descartar)
        ml.addWidget(self.cabecera)

        # Cuerpo principal
        self.cuerpo = QWidget(self.marco)
        self.cuerpo.setObjectName('tarjeta_cuerpo')
        bl = QVBoxLayout(self.cuerpo)
        bl.setContentsMargins(13, 10, 13, 11)
        bl.setSpacing(8)

        # Vista normal (lectura)
        self._vista_lectura = QWidget(self.cuerpo)
        vl = QVBoxLayout(self._vista_lectura)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(7)

        self.scroll_contenido = QScrollArea(self._vista_lectura)
        self.scroll_contenido.setObjectName('scroll_contenido')
        self.scroll_contenido.setWidgetResizable(True)
        self.scroll_contenido.setFrameShape(QFrame.NoFrame)
        self.scroll_contenido.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_contenido.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_contenido.setFocusPolicy(Qt.WheelFocus)
        self.scroll_contenido.viewport().setAutoFillBackground(False)

        self.lbl_contenido = QLabel(self.frase.get('contenido', ''), self.scroll_contenido)
        self.lbl_contenido.setObjectName('tarjeta_contenido')
        self.lbl_contenido.setWordWrap(True)
        self.lbl_contenido.setMinimumWidth(10)
        self.lbl_contenido.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        self.lbl_contenido.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.scroll_contenido.setWidget(self.lbl_contenido)
        vl.addWidget(self.scroll_contenido)

        self.lbl_motivo = QLabel(self.motivo, self._vista_lectura)
        self.lbl_motivo.setObjectName('muted')
        self.lbl_motivo.setWordWrap(True)
        if not self.motivo:
            self.lbl_motivo.hide()
        vl.addWidget(self.lbl_motivo)

        fila_acc = QHBoxLayout()
        fila_acc.setContentsMargins(0, 2, 0, 0)
        fila_acc.setSpacing(8)

        self.btn_usar = QPushButton('Usar', self._vista_lectura)
        self.btn_usar.setObjectName('btn_usar')
        self.btn_usar.setCursor(Qt.PointingHandCursor)
        self.btn_usar.clicked.connect(self.usar)
        fila_acc.addWidget(self.btn_usar)

        self.btn_editar = QPushButton('Editar', self._vista_lectura)
        self.btn_editar.setObjectName('btn_editar')
        self.btn_editar.setCursor(Qt.PointingHandCursor)
        self.btn_editar.clicked.connect(self.entrar_edicion)
        fila_acc.addWidget(self.btn_editar)

        fila_acc.addStretch(1)
        vl.addLayout(fila_acc)
        bl.addWidget(self._vista_lectura)

        # Vista edición inline (oculta por defecto)
        self._vista_edicion = QWidget(self.cuerpo)
        el = QVBoxLayout(self._vista_edicion)
        el.setContentsMargins(0, 0, 0, 0)
        el.setSpacing(7)

        self.lbl_ayuda_edicion = QLabel('Edita la respuesta antes de insertarla:', self._vista_edicion)
        self.lbl_ayuda_edicion.setObjectName('muted')
        el.addWidget(self.lbl_ayuda_edicion)

        self.editor = QTextEdit(self._vista_edicion)
        self.editor.setObjectName('tarjeta_editor')
        self.editor.setAcceptRichText(False)
        self.editor.setMinimumHeight(80)
        self.editor.setMaximumHeight(118)
        self.editor.setPlainText(self.frase.get('contenido', ''))
        el.addWidget(self.editor)

        fila_vars = QHBoxLayout()
        fila_vars.setContentsMargins(0, 0, 0, 0)
        fila_vars.setSpacing(4)
        self._botones_variables_edicion = {}
        for nombre_var in VARIABLES_OFICIALES[:3]:
            btn_v = QPushButton('{' + nombre_var + '}', self._vista_edicion)
            btn_v.setObjectName('btn_var_chip')
            btn_v.setCursor(Qt.PointingHandCursor)
            btn_v.clicked.connect(lambda _c=False, n=nombre_var: self._insertar_variable_editor(n))
            self._botones_variables_edicion[nombre_var] = btn_v
            fila_vars.addWidget(btn_v)

        self.combo_otras_variables = QComboBox(self._vista_edicion)
        self.combo_otras_variables.setObjectName('combo_var_flotante')
        self.combo_otras_variables.addItems(['Otra…', *VARIABLES_OFICIALES[3:]])
        self.combo_otras_variables.activated.connect(
            lambda idx: (
                self._insertar_variable_editor(self.combo_otras_variables.itemText(idx)),
                self.combo_otras_variables.setCurrentIndex(0),
            )
            if idx else None
        )
        fila_vars.addWidget(self.combo_otras_variables)
        fila_vars.addStretch(1)
        el.addLayout(fila_vars)

        fila_ed = QHBoxLayout()
        fila_ed.setContentsMargins(0, 2, 0, 0)
        fila_ed.setSpacing(8)

        self.btn_insertar_editado = QPushButton('Insertar editado', self._vista_edicion)
        self.btn_insertar_editado.setObjectName('btn_usar')
        self.btn_insertar_editado.setCursor(Qt.PointingHandCursor)
        self.btn_insertar_editado.clicked.connect(self.confirmar_edicion)
        fila_ed.addWidget(self.btn_insertar_editado)

        self.btn_cancelar_edicion = QPushButton('Cancelar', self._vista_edicion)
        self.btn_cancelar_edicion.setObjectName('btn_editar')
        self.btn_cancelar_edicion.setCursor(Qt.PointingHandCursor)
        self.btn_cancelar_edicion.clicked.connect(self.cancelar_edicion)
        fila_ed.addWidget(self.btn_cancelar_edicion)

        fila_ed.addStretch(1)
        el.addLayout(fila_ed)
        self._vista_edicion.hide()
        bl.addWidget(self._vista_edicion)

        # Vista de variables inline (oculta por defecto; permite completar {variables} sin volver a FraseYa)
        self._vista_variables = QWidget(self.cuerpo)
        varl = QVBoxLayout(self._vista_variables)
        varl.setContentsMargins(0, 0, 0, 0)
        varl.setSpacing(6)

        self.lbl_ayuda_variables = QLabel('Completa los datos para insertar en WhatsApp:', self._vista_variables)
        self.lbl_ayuda_variables.setObjectName('muted')
        self.lbl_ayuda_variables.setWordWrap(True)
        varl.addWidget(self.lbl_ayuda_variables)

        self._contenedor_variables = QWidget(self._vista_variables)
        self._layout_variables = QVBoxLayout(self._contenedor_variables)
        self._layout_variables.setContentsMargins(0, 0, 0, 0)
        self._layout_variables.setSpacing(5)
        varl.addWidget(self._contenedor_variables)

        self.lbl_preview_variables = QLabel('', self._vista_variables)
        self.lbl_preview_variables.setObjectName('tarjeta_preview_vars')
        self.lbl_preview_variables.setWordWrap(True)
        varl.addWidget(self.lbl_preview_variables)

        self.lbl_error_variables = QLabel('', self._vista_variables)
        self.lbl_error_variables.setObjectName('tarjeta_error_vars')
        self.lbl_error_variables.setWordWrap(True)
        self.lbl_error_variables.hide()
        varl.addWidget(self.lbl_error_variables)

        fila_var = QHBoxLayout()
        fila_var.setContentsMargins(0, 2, 0, 0)
        fila_var.setSpacing(8)

        self.btn_insertar_variables = QPushButton('Insertar en WhatsApp', self._vista_variables)
        self.btn_insertar_variables.setObjectName('btn_usar')
        self.btn_insertar_variables.setCursor(Qt.PointingHandCursor)
        self.btn_insertar_variables.clicked.connect(self.confirmar_variables)
        fila_var.addWidget(self.btn_insertar_variables)

        self.btn_cancelar_variables = QPushButton('Cancelar', self._vista_variables)
        self.btn_cancelar_variables.setObjectName('btn_editar')
        self.btn_cancelar_variables.setCursor(Qt.PointingHandCursor)
        self.btn_cancelar_variables.clicked.connect(self.cancelar_variables)
        fila_var.addWidget(self.btn_cancelar_variables)

        fila_var.addStretch(1)
        varl.addLayout(fila_var)
        self._vista_variables.hide()
        bl.addWidget(self._vista_variables)

        ml.addWidget(self.cuerpo)
        raiz.addWidget(self.marco)

        self.aplicar_tema(self.tema)
        self._ajustar_altura_contenido()
        self.adjustSize()

    def _ajustar_altura_contenido(self):
        self.lbl_contenido.ensurePolished()
        texto = self.lbl_contenido.text() or ' '
        fm = QFontMetrics(self.lbl_contenido.font())
        ancho_texto = max(120, ANCHO_FLOTANTE - 42)
        rect_medido = fm.boundingRect(QRect(0, 0, ancho_texto, 2400), Qt.TextWordWrap, texto)
        alto_linea = max(18, fm.lineSpacing())
        alto_max = alto_linea * 7 + 8
        alto_min = alto_linea * 2 + 4
        alto = min(max(rect_medido.height() + 6, alto_min), alto_max)
        self.scroll_contenido.setFixedHeight(alto)

    def _limpiar_campos_variables(self):
        self._campos_variables.clear()
        while self._layout_variables.count():
            item = self._layout_variables.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def _valores_actuales_variables(self) -> dict[str, str]:
        return {n: campo.text() for n, campo in self._campos_variables.items() if _qt_valido(campo)}

    def _actualizar_preview_variables(self):
        contenido = self.frase.get('contenido', '')
        valores = {
            n: v.strip() for n, v in self._valores_actuales_variables().items() if v.strip()
        }
        self.lbl_preview_variables.setText(_sustituir_variables(contenido, valores))
        if self.lbl_error_variables.isVisible():
            self.lbl_error_variables.hide()
            self.adjustSize()
            if self._al_cambiar_tamano is not None:
                self._al_cambiar_tamano(self)

    def usar(self):
        contenido = self.frase.get('contenido', '')
        nombres = _detectar_variables(contenido)
        if nombres:
            self.entrar_variables(nombres)
            return
        if self._al_usar is not None:
            self._al_usar(self.frase, contenido)

    def entrar_variables(self, nombres=None):
        contenido = self.frase.get('contenido', '')
        lista_nombres = list(nombres) if nombres is not None else _detectar_variables(contenido)
        if not lista_nombres:
            if self._al_usar is not None:
                self._al_usar(self.frase, contenido)
            return

        pos = self.pos()
        estaba_visible = self.isVisible()
        self.en_edicion = False
        self.en_variables = True
        self._nombres_variables = lista_nombres
        self._limpiar_campos_variables()
        iniciales = _valores_iniciales_variables(lista_nombres)
        if 'nombre' in lista_nombres and self._nombre_contacto:
            iniciales.setdefault('nombre', self._nombre_contacto)

        for idx, nombre in enumerate(lista_nombres):
            fila_widget = QWidget(self._contenedor_variables)
            fl = QHBoxLayout(fila_widget)
            fl.setContentsMargins(0, 0, 0, 0)
            fl.setSpacing(6)

            et = QLabel(f'{nombre}:', fila_widget)
            et.setObjectName('etiqueta_variable')
            et.setMinimumWidth(78)
            fl.addWidget(et)

            campo = QLineEdit(fila_widget)
            campo.setObjectName('campo_variable')
            campo.setPlaceholderText(f'Escribe {nombre}…')
            if nombre in iniciales:
                campo.setText(iniciales[nombre])
            campo.textChanged.connect(self._actualizar_preview_variables)
            fl.addWidget(campo, 1)

            self._campos_variables[nombre] = campo
            self._layout_variables.addWidget(fila_widget)

        # Enter en un campo salta al siguiente o confirma en el último
        for idx, nombre in enumerate(lista_nombres):
            campo = self._campos_variables[nombre]
            if idx + 1 < len(lista_nombres):
                siguiente = self._campos_variables[lista_nombres[idx + 1]]
                campo.returnPressed.connect(siguiente.setFocus)
            else:
                campo.returnPressed.connect(self.confirmar_variables)

        self.lbl_error_variables.setText('')
        self.lbl_error_variables.hide()
        self._actualizar_preview_variables()

        self._vista_lectura.hide()
        self._vista_edicion.hide()
        self._vista_variables.show()

        self.setAttribute(Qt.WA_ShowWithoutActivating, False)
        self.setWindowFlags(FLAGS_FLOTANTE_EDICION)
        if self.layout() is not None:
            self.layout().activate()
        self.adjustSize()
        hint = self.sizeHint()
        if hint.isValid() and hint.height() > 0:
            self.resize(self.width(), hint.height())
        if estaba_visible:
            self.show()
            self.move(pos)
            self.raise_()
            self.activateWindow()

        primer_vacio = next(
            (self._campos_variables[n] for n in lista_nombres if not self._campos_variables[n].text().strip()),
            self._campos_variables[lista_nombres[0]],
        )
        primer_vacio.setFocus()
        if self._al_cambiar_tamano is not None:
            self._al_cambiar_tamano(self)

    def _salir_variables(self):
        if not self.en_variables:
            return
        pos = self.pos()
        estaba_visible = self.isVisible()
        self.en_variables = False
        self._vista_variables.hide()
        self._vista_lectura.show()

        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setWindowFlags(FLAGS_FLOTANTE)
        if self.layout() is not None:
            self.layout().activate()
        self.adjustSize()
        hint = self.sizeHint()
        if hint.isValid() and hint.height() > 0:
            self.resize(self.width(), hint.height())
        if estaba_visible:
            self.show()
            self.move(pos)
        if self._al_cambiar_tamano is not None:
            self._al_cambiar_tamano(self)

    def confirmar_variables(self):
        if not self.en_variables:
            return
        valores = self._valores_actuales_variables()
        pendientes = _variables_faltantes(self._nombres_variables, valores)
        if pendientes:
            self.lbl_error_variables.setText('Completa: ' + ', '.join(pendientes))
            self.lbl_error_variables.show()
            self.adjustSize()
            if self._al_cambiar_tamano is not None:
                self._al_cambiar_tamano(self)
            primero = self._campos_variables.get(pendientes[0])
            if primero is not None and _qt_valido(primero):
                primero.setFocus()
            return
        contenido = self.frase.get('contenido', '')
        texto_final = _sustituir_variables(
            contenido,
            {n: valores[n].strip() for n in self._nombres_variables},
        )
        self._salir_variables()
        if self._al_usar is not None:
            self._al_usar(self.frase, texto_final)

    def cancelar_variables(self):
        self._salir_variables()

    def entrar_edicion(self):
        if self.en_edicion:
            self.editor.setFocus()
            return
        pos = self.pos()
        estaba_visible = self.isVisible()
        self.en_variables = False
        self.en_edicion = True
        self.editor.setPlainText(self.frase.get('contenido', ''))
        self._vista_lectura.hide()
        self._vista_variables.hide()
        self._vista_edicion.show()

        self.setAttribute(Qt.WA_ShowWithoutActivating, False)
        self.setWindowFlags(FLAGS_FLOTANTE_EDICION)
        if self.layout() is not None:
            self.layout().activate()
        self.adjustSize()
        hint = self.sizeHint()
        if hint.isValid() and hint.height() > 0:
            self.resize(self.width(), hint.height())
        if estaba_visible:
            self.show()
            self.move(pos)
            self.raise_()
            self.activateWindow()
        self.editor.setFocus()
        if self._al_cambiar_tamano is not None:
            self._al_cambiar_tamano(self)

    def _salir_edicion(self):
        if not self.en_edicion:
            return
        pos = self.pos()
        estaba_visible = self.isVisible()
        self.en_edicion = False
        self._vista_edicion.hide()
        self._vista_lectura.show()

        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setWindowFlags(FLAGS_FLOTANTE)
        if self.layout() is not None:
            self.layout().activate()
        self.adjustSize()
        hint = self.sizeHint()
        if hint.isValid() and hint.height() > 0:
            self.resize(self.width(), hint.height())
        if estaba_visible:
            self.show()
            self.move(pos)
        if self._al_cambiar_tamano is not None:
            self._al_cambiar_tamano(self)

    def _insertar_variable_editor(self, nombre: str):
        limpio = (nombre or '').strip()
        if not limpio:
            return
        self.editor.insertPlainText('{' + limpio + '}')
        self.editor.setFocus()

    def confirmar_edicion(self):
        texto_final = self.editor.toPlainText()
        if not texto_final.strip():
            self.editor.setFocus()
            return
        self.frase = {**self.frase, 'contenido': texto_final}
        self.lbl_contenido.setText(texto_final)
        self._ajustar_altura_contenido()
        self._salir_edicion()
        nombres = _detectar_variables(texto_final)
        if nombres:
            self.entrar_variables(nombres)
            return
        if self._al_usar is not None:
            self._al_usar(self.frase, texto_final)

    def cancelar_edicion(self):
        self._salir_edicion()

    def descartar(self):
        self.en_edicion = False
        self.en_variables = False
        self.hide()
        if self._al_descartar is not None:
            self._al_descartar(self)

    def aplicar_tema(self, tema):
        self.tema = normalizar_tema(tema)
        p = PALETA_FLOTANTE[self.tema]
        self.setStyleSheet(f'''
            QWidget {{
                font-family: 'Segoe UI';
                font-size: 12px;
                background: transparent;
            }}
            QFrame#tarjeta_marco {{
                background: {p['tarjeta_fondo']};
                border: 1px solid {p['tarjeta_borde']};
                border-radius: 12px;
            }}
            QFrame#tarjeta_cabecera {{
                background: {self.color_cabecera};
                border: 0;
                border-top-left-radius: 11px;
                border-top-right-radius: 11px;
            }}
            QLabel#tarjeta_etiqueta {{
                color: #ffffff;
                font-size: 12px;
                font-weight: 700;
                background: transparent;
            }}
            QPushButton#btn_descartar {{
                background: transparent;
                color: #ffffff;
                border: 0;
                border-radius: 6px;
                font-size: 15px;
                font-weight: 700;
                padding: 0;
            }}
            QPushButton#btn_descartar:hover {{
                background: rgba(255, 255, 255, 0.22);
            }}
            QWidget#tarjeta_cuerpo {{
                background: transparent;
            }}
            QScrollArea#scroll_contenido, QScrollArea#scroll_contenido > QWidget > QWidget {{
                background: transparent;
                border: 0;
            }}
            QLabel#tarjeta_contenido {{
                color: {p['tarjeta_texto']};
                font-size: 13px;
                background: transparent;
            }}
            QLabel#muted {{
                color: {p['tarjeta_muted']};
                font-size: 11px;
                background: transparent;
            }}
            QPushButton#btn_usar {{
                background: {p['btn_primario_fondo']};
                color: {p['btn_primario_texto']};
                border: 0;
                border-radius: 7px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton#btn_usar:hover {{
                background: {p['btn_primario_hover']};
            }}
            QPushButton#btn_usar:disabled {{
                background: {p['btn_primario_disabled']};
            }}
            QPushButton#btn_editar {{
                background: {p['btn_sec_fondo']};
                color: {p['btn_sec_texto']};
                border: 1px solid {p['btn_sec_borde']};
                border-radius: 7px;
                padding: 6px 13px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton#btn_editar:hover {{
                background: {p['btn_sec_hover']};
            }}
            QPushButton#btn_var_chip {{
                background: {p['btn_sec_fondo']};
                color: {p['btn_sec_texto']};
                border: 1px solid {p['btn_sec_borde']};
                border-radius: 5px;
                padding: 2px 6px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton#btn_var_chip:hover {{
                background: {p['btn_sec_hover']};
            }}
            QComboBox#combo_var_flotante {{
                background: {p['btn_sec_fondo']};
                color: {p['btn_sec_texto']};
                border: 1px solid {p['btn_sec_borde']};
                border-radius: 5px;
                padding: 2px 6px;
                font-size: 11px;
            }}
            QComboBox#combo_var_flotante QAbstractItemView {{
                background: {p['tarjeta_fondo']};
                color: {p['tarjeta_texto']};
                border: 1px solid {p['tarjeta_borde']};
            }}
            QTextEdit#tarjeta_editor {{
                background: {p['editor_fondo']};
                color: {p['editor_texto']};
                border: 1px solid {p['editor_borde']};
                border-radius: 7px;
                padding: 6px 8px;
                font-size: 12px;
            }}
            QTextEdit#tarjeta_editor:focus {{
                border: 1px solid {p['editor_foco']};
            }}
            QLabel#etiqueta_variable {{
                color: {p['tarjeta_texto']};
                font-size: 12px;
                font-weight: 600;
                background: transparent;
            }}
            QLineEdit#campo_variable {{
                background: {p['editor_fondo']};
                color: {p['editor_texto']};
                border: 1px solid {p['editor_borde']};
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 12px;
            }}
            QLineEdit#campo_variable:focus {{
                border: 1px solid {p['editor_foco']};
            }}
            QLabel#tarjeta_preview_vars {{
                background: {p['preview_vars_fondo']};
                color: {p['tarjeta_texto']};
                border: 1px solid {p['preview_vars_borde']};
                border-radius: 7px;
                padding: 6px 8px;
                font-size: 12px;
            }}
            QLabel#tarjeta_error_vars {{
                color: {p['error_vars_texto']};
                font-size: 11px;
                font-weight: 600;
                background: transparent;
            }}
            QScrollBar:vertical {{
                background: rgba(128, 128, 128, 0.14);
                width: 9px;
                border-radius: 4px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {p['scroll_handle']};
                border-radius: 4px;
                min-height: 24px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
        ''')


class ControladorFlotanteQt(QObject):
    """Coordina la barra flotante IA y hasta 3 tarjetas sugeridas alrededor del chat."""

    def __init__(
        self,
        parent=None,
        *,
        al_usar=None,
        al_toggle_activo=None,
        al_leer_chat=None,
        al_analizar_portapapeles=None,
        al_ocultar=None,
        tema='claro',
    ):
        super().__init__(parent)
        self.tema = normalizar_tema(tema)
        self.activo = False
        self._al_usar = al_usar
        self._al_toggle_activo = al_toggle_activo
        self._al_leer_chat = al_leer_chat
        self._al_analizar_portapapeles = al_analizar_portapapeles
        self._al_ocultar = al_ocultar
        self._ultimo_rect_chat = None
        self._detenido = False
        self._parent_ref = parent

        self.tarjetas: list[TarjetaSugerenciaFlotante] = []
        self.barra = BarraFlotanteIA(
            activo=self.activo,
            tema=self.tema,
            al_toggle_activo=self._manejar_toggle,
            al_leer_chat=self._manejar_leer_chat,
            al_analizar_portapapeles=self._manejar_portapapeles,
            al_ocultar=self._manejar_ocultar,
        )
        if parent is not None:
            parent.destroyed.connect(self.detener)

    def _barra_viva(self):
        return not self._detenido and self.barra is not None and _qt_valido(self.barra)

    def _manejar_toggle(self, nuevo_estado):
        if self._detenido:
            return
        self.activo = bool(nuevo_estado)
        if self._al_toggle_activo is not None:
            self._al_toggle_activo(self.activo)

    def _manejar_leer_chat(self):
        if self._detenido:
            return
        if self._al_leer_chat is not None:
            self._al_leer_chat()

    def _manejar_portapapeles(self):
        if self._detenido:
            return
        if self._al_analizar_portapapeles is not None:
            self._al_analizar_portapapeles()

    def _manejar_ocultar(self):
        if self._detenido:
            return
        self.ocultar_todo()
        if self._al_ocultar is not None:
            self._al_ocultar()

    def _manejar_usar(self, frase, texto_final):
        if self._detenido:
            return
        if self._al_usar is not None:
            self._al_usar(frase, texto_final)

    def _descartar_tarjeta(self, tarjeta):
        if tarjeta in self.tarjetas:
            self.tarjetas.remove(tarjeta)
            if _qt_valido(tarjeta):
                try:
                    tarjeta.close()
                    tarjeta.deleteLater()
                except RuntimeError:
                    pass
            if self.tarjetas and self._barra_viva():
                self.reposicionar(self._ultimo_rect_chat)

    def _al_cambiar_tamano_tarjeta(self, _tarjeta):
        if not self._barra_viva():
            return
        if self.barra.isVisible() or any(_qt_valido(t) and t.isVisible() for t in self.tarjetas):
            self.reposicionar(self._ultimo_rect_chat)

    def aplicar_tema(self, tema: str):
        self.tema = normalizar_tema(tema)
        if not self._barra_viva():
            return
        self.barra.aplicar_tema(self.tema)
        for tarjeta in self.tarjetas:
            if _qt_valido(tarjeta):
                tarjeta.aplicar_tema(self.tema)

    def establecer_activo(self, activo: bool):
        self.activo = bool(activo)
        if self._barra_viva():
            self.barra.establecer_activo(self.activo)

    def establecer_cargando(self, cargando: bool):
        if self._barra_viva():
            self.barra.establecer_cargando(cargando)

    def limpiar_contexto(self, aviso: str = ''):
        if not self._barra_viva():
            return
        self.ocultar_sugerencias()
        self.barra.limpiar_contexto()
        if aviso:
            self.barra.mostrar_aviso(aviso)
        if self.barra.isVisible():
            self.reposicionar(self._ultimo_rect_chat)

    def mostrar_aviso(self, texto: str = ''):
        if not self._barra_viva():
            return
        self.barra.mostrar_aviso(texto)
        if self.barra.isVisible() or any(_qt_valido(t) and t.isVisible() for t in self.tarjetas):
            self.reposicionar(self._ultimo_rect_chat)

    def mostrar_barra(self, rect_chat=None):
        if not self._barra_viva():
            return
        self.barra.adjustSize()
        self.barra.show()
        vivas = []
        for tarjeta in self.tarjetas:
            if _qt_valido(tarjeta):
                tarjeta.adjustSize()
                tarjeta.show()
                vivas.append(tarjeta)
        self.tarjetas = vivas
        self.reposicionar(rect_chat if rect_chat is not None else self._ultimo_rect_chat)

    def mostrar_sugerencias(self, resultado, rect_chat=None):
        if not self._barra_viva():
            return
        tema_chat, animo_chat, urgencia_chat, opciones = _extraer_resultado(resultado)
        nombre_contacto = str(_leer_campo(resultado, 'nombre_contacto', '') or '').strip()
        self.barra.mostrar_aviso('')
        self.barra.actualizar_contexto(tema_chat, animo_chat, urgencia_chat)

        self.ocultar_sugerencias()
        for idx, opcion in enumerate(opciones[:MAX_TARJETAS], start=1):
            tarjeta = TarjetaSugerenciaFlotante(
                opcion,
                indice=idx,
                tema=self.tema,
                al_usar=self._manejar_usar,
                al_descartar=self._descartar_tarjeta,
                al_cambiar_tamano=self._al_cambiar_tamano_tarjeta,
                nombre_contacto=nombre_contacto,
            )
            self.tarjetas.append(tarjeta)

        self.barra.adjustSize()
        self.barra.show()
        for tarjeta in self.tarjetas:
            tarjeta.adjustSize()
            tarjeta.show()

        rect_objetivo = rect_chat if rect_chat is not None else self._ultimo_rect_chat
        self.reposicionar(rect_objetivo, forzar=True)

    def _geometria_pantalla(self, rect_chat):
        pantalla = None
        if rect_chat is not None and len(rect_chat) == 4:
            rx, ry, rw, rh = (int(v) for v in rect_chat)
            if rw > 0 and rh > 0:
                pantalla = QApplication.screenAt(QPoint(rx + rw // 2, ry + rh // 2))
        if pantalla is None:
            pantalla = QApplication.primaryScreen()
        if pantalla is None:
            return QRect(0, 0, 1280, 720)
        return pantalla.availableGeometry()

    def reposicionar(self, rect_chat, *, forzar=False):
        if not self._barra_viva():
            return
        if rect_chat is not None:
            self._ultimo_rect_chat = tuple(int(v) for v in rect_chat)
        avail = self._geometria_pantalla(rect_chat)

        elementos = []
        if forzar or not self.barra.arrastrada_manualmente:
            elementos.append(self.barra)
        for tarjeta in self.tarjetas:
            if _qt_valido(tarjeta) and (forzar or not tarjeta.arrastrada_manualmente):
                elementos.append(tarjeta)
        if not elementos:
            return

        for w in elementos:
            w.adjustSize()

        avail_x = avail.left()
        avail_y = avail.top()
        avail_w = avail.width()
        avail_h = avail.height()

        ancho_pila = max(w.width() for w in elementos)
        alto_total = sum(w.height() for w in elementos) + SEPARACION_VERTICAL * (len(elementos) - 1)

        # Determina columna inicial: al costado derecho del chat si cabe; si no, borde derecho interior
        # debajo de la barra de título de Windows/WhatsApp (MARGEN_SUPERIOR_VENTANA) para no tapar _ □ ×.
        x_col = avail_x + avail_w - ancho_pila - MARGEN_PANTALLA
        y_min_superior = avail_y + MARGEN_SUPERIOR_VENTANA
        y_inicio = y_min_superior
        cabe_fuera_derecha = False

        if rect_chat is not None and len(rect_chat) == 4:
            rx, ry, rw, rh = (int(v) for v in rect_chat)
            if rw > 0 and rh > 0:
                x_derecha = rx + rw + SEPARACION_CHAT
                limite_der = avail_x + avail_w - MARGEN_PANTALLA
                if x_derecha + ancho_pila <= limite_der:
                    cabe_fuera_derecha = True
                    x_col = max(avail_x + MARGEN_PANTALLA, x_derecha)
                    y_min_superior = avail_y + MARGEN_PANTALLA
                    y_inicio = max(y_min_superior, ry)
                else:
                    # Superpuesta dentro de la ventana de WhatsApp (maximizada o ancha):
                    # deja al menos 56 px desde el borde superior del chat/pantalla para no tapar _ □ ×.
                    borde_sup_chat = max(avail_y, ry)
                    y_min_superior = max(avail_y + MARGEN_SUPERIOR_VENTANA, borde_sup_chat + MARGEN_SUPERIOR_VENTANA)
                    y_inicio = y_min_superior

        # Garantiza margen horizontal dentro del área disponible
        x_max = max(avail_x, avail_x + avail_w - ancho_pila - MARGEN_PANTALLA)
        x_col = max(avail_x + MARGEN_PANTALLA, min(x_col, x_max))
        if x_col + ancho_pila > avail_x + avail_w:
            x_col = max(avail_x, avail_x + avail_w - ancho_pila)

        # Determina margen vertical seguro sin salirse de pantalla ni invadir la barra de título
        margen_v = MARGEN_PANTALLA
        if alto_total > avail_h - 2 * MARGEN_PANTALLA:
            margen_v = max(4, min(MARGEN_PANTALLA, (avail_h - alto_total) // 2))
            if margen_v < 0:
                margen_v = 4

        limite_inf = avail_y + avail_h - margen_v
        max_h_elem = max(w.height() for w in elementos)
        if not cabe_fuera_derecha:
            # Si la pantalla es extremadamente baja, ajusta solo lo imprescindible para caber.
            y_min_superior = min(y_min_superior, max(avail_y + 4, limite_inf - max_h_elem))
        else:
            y_min_superior = min(y_min_superior, avail_y + margen_v)

        y_inicio = max(y_min_superior, y_inicio)
        if y_inicio + alto_total > limite_inf:
            y_inicio = max(y_min_superior, limite_inf - alto_total)

        y_actual = y_inicio
        x_actual = x_col
        for w in elementos:
            h_w = w.height()
            w_w = w.width()
            if y_actual + h_w > limite_inf and y_actual > y_min_superior:
                # Si la pantalla es demasiado baja para toda la pila en una columna,
                # abre columna adyacente a la izquierda respetando el margen superior seguro.
                x_alt = x_actual - ancho_pila - SEPARACION_VERTICAL
                if x_alt >= avail_x + MARGEN_PANTALLA:
                    x_actual = x_alt
                    y_actual = y_min_superior

            px = max(avail_x, min(x_actual, avail_x + avail_w - w_w))
            py = max(avail_y, min(y_actual, avail_y + avail_h - h_w))
            w.move(px, py)
            y_actual = py + h_w + SEPARACION_VERTICAL

    def esta_en_foco_propio(self) -> bool:
        if not self._barra_viva():
            return False
        tarjetas_vivas = [t for t in self.tarjetas if _qt_valido(t)]
        ventanas = [self.barra, *tarjetas_vivas]
        activa = QApplication.activeWindow()
        if activa in ventanas:
            return True
        if self.barra.isActiveWindow() or self.barra.hasFocus():
            return True
        for tarjeta in tarjetas_vivas:
            if (
                tarjeta.en_edicion
                or tarjeta.en_variables
                or tarjeta.isActiveWindow()
                or tarjeta.hasFocus()
                or (_qt_valido(tarjeta.editor) and tarjeta.editor.hasFocus())
                or any(_qt_valido(c) and c.hasFocus() for c in tarjeta._campos_variables.values())
            ):
                return True
        return False

    def ocultar_sugerencias(self):
        for tarjeta in list(self.tarjetas):
            if _qt_valido(tarjeta):
                try:
                    tarjeta.en_edicion = False
                    tarjeta.en_variables = False
                    tarjeta.hide()
                    tarjeta.close()
                    tarjeta.deleteLater()
                except RuntimeError:
                    pass
        self.tarjetas.clear()

    def esta_visible(self) -> bool:
        if not self._barra_viva():
            return False
        if self.barra.isVisible():
            return True
        return any(_qt_valido(t) and t.isVisible() for t in self.tarjetas)

    def ocultar_temporalmente(self):
        """Oculta barra y tarjetas al cambiar de ventana sin destruir las sugerencias activas."""
        for tarjeta in self.tarjetas:
            if _qt_valido(tarjeta):
                try:
                    tarjeta.hide()
                except RuntimeError:
                    pass
        if self.barra is not None and _qt_valido(self.barra):
            try:
                self.barra.hide()
            except RuntimeError:
                pass

    def ocultar_todo(self):
        self.ocultar_sugerencias()
        if self.barra is not None and _qt_valido(self.barra):
            try:
                self.barra.hide()
            except RuntimeError:
                pass

    def detener(self, *_args):
        if self._detenido:
            return
        self._detenido = True
        parent = self._parent_ref
        self._parent_ref = None
        if parent is not None and _qt_valido(parent):
            try:
                parent.destroyed.disconnect(self.detener)
            except (RuntimeError, TypeError):
                pass
        self.ocultar_todo()
        if self.barra is not None and _qt_valido(self.barra):
            try:
                self.barra.close()
                self.barra.deleteLater()
            except RuntimeError:
                pass
