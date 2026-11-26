"""Piezas de «Mis frases»: columna de categorías y filas de la lista."""
from PySide6.QtCore import Qt, QByteArray, QRect, QRectF, QSize
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QScrollArea, QStyle, QStyledItemDelegate, QVBoxLayout, QWidget

from fraseya.dominio.reglas import COLOR_DEFECTO
from .qt_paneles import EtiquetaSegura as QLabel

ALTO_FILA = 88

_ICONOS = {
    'estrella': '<path d="M12 3l2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3 6.4 20.2 7.5 14 3 9.6l6.2-.9z"/>',
    'duplicar': '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a1 1 0 0 1 1-1h10"/>',
    'borrar': '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
}


def _pixmap(nombre, color, relleno):
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="{relleno}" stroke="{color}" '
           f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{_ICONOS[nombre]}</svg>')
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    pintor = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode('ascii'))).render(pintor)
    pintor.end()
    return pixmap


def poner_icono(boton, nombre, color='#0a1f5c', relleno='none'):
    icono = QIcon()
    icono.addPixmap(_pixmap(nombre, color, relleno), QIcon.Normal)
    icono.addPixmap(_pixmap(nombre, '#a8b3c4', 'none'), QIcon.Disabled)
    boton.setIcon(icono)
    boton.setIconSize(QSize(17, 17))


def marcar_favorita(boton, es_favorita):
    boton.setText(' Favorita')
    boton.setToolTip('Quitar de favoritas' if es_favorita else 'Marcar como favorita')
    if es_favorita:
        poner_icono(boton, 'estrella', '#d98c00', '#fbbf24')
    else:
        poner_icono(boton, 'estrella')


def barra_acciones(botones):
    """Une los botones en una sola barra con separadores."""
    barra = QFrame()
    barra.setObjectName('barra_acciones')
    fila = QHBoxLayout(barra)
    fila.setContentsMargins(1, 1, 1, 1)
    fila.setSpacing(0)
    for posicion, boton in enumerate(botones):
        boton.setObjectName('segmento_peligro' if posicion == len(botones) - 1 else 'segmento')
        boton.setMinimumHeight(34)
        fila.addWidget(boton)
    return barra


def estado_editor(etiqueta, texto, tipo):
    """Etiqueta de estado del editor: propia, compartida o nueva."""
    etiqueta.setText(texto)
    etiqueta.setObjectName('estado_' + tipo)
    etiqueta.style().unpolish(etiqueta)
    etiqueta.style().polish(etiqueta)


class DelegadoFrase(QStyledItemDelegate):
    """Título, abreviatura, extracto y categoría de cada frase."""

    def sizeHint(self, option, index):
        return QSize(200, ALTO_FILA)

    def paint(self, pintor, option, index):
        f = index.data(Qt.UserRole)
        if not f:
            return super().paint(pintor, option, index)
        pintor.save()
        pintor.setRenderHint(QPainter.Antialiasing)
        r = option.rect
        elegida = bool(option.state & QStyle.State_Selected)
        encima = bool(option.state & QStyle.State_MouseOver)
        pintor.fillRect(r, QColor('#eef4ff' if elegida else '#f8fafc' if encima else '#ffffff'))
        if elegida:
            pintor.fillRect(QRect(r.left(), r.top(), 3, r.height()), QColor('#2875e8'))
        pintor.fillRect(QRect(r.left(), r.bottom(), r.width(), 1), QColor('#eef1f6'))
        x, ancho = r.left() + 16, r.width() - 30

        mono = QFont('Consolas')
        mono.setPixelSize(12)
        abreviatura = QFontMetrics(mono).elidedText(f['abreviatura'], Qt.ElideRight, ancho // 2)
        ancho_abr = QFontMetrics(mono).horizontalAdvance(abreviatura) + 16
        caja = QRectF(x + ancho - ancho_abr, r.top() + 12, ancho_abr, 22)
        pintor.setPen(Qt.NoPen)
        pintor.setBrush(QColor('#eef2f7'))
        pintor.drawRoundedRect(caja, 6, 6)
        pintor.setFont(mono)
        pintor.setPen(QColor('#334155'))
        pintor.drawText(caja, Qt.AlignCenter, abreviatura)

        def linea(texto, y, alto, tam, peso, color, sangria=0, disponible=ancho):
            fuente = QFont('Segoe UI')
            fuente.setPixelSize(tam)
            fuente.setWeight(peso)
            pintor.setFont(fuente)
            pintor.setPen(QColor(color))
            recortado = QFontMetrics(fuente).elidedText(texto, Qt.ElideRight, disponible - sangria)
            pintor.drawText(QRect(x + sangria, r.top() + y, disponible - sangria, alto),
                            Qt.AlignLeft | Qt.AlignVCenter, recortado)

        titulo = ('★ ' if f.get('favorita') else '') + f['titulo']
        linea(titulo, 12, 22, 13, QFont.Bold, '#0f172a', disponible=ancho - ancho_abr - 8)
        linea(f['contenido'].replace('\n', ' '), 37, 20, 12, QFont.Medium, '#475569')
        pintor.setPen(Qt.NoPen)
        pintor.setBrush(QColor(f.get('color') or COLOR_DEFECTO))
        pintor.drawEllipse(QRectF(x, r.top() + 65, 8, 8))
        linea(f"{f.get('categoria', 'General')}  ·  {f['origen'].capitalize()}",
              59, 20, 12, QFont.Medium, '#475569', sangria=14)
        pintor.restore()


class ColumnaFiltros(QFrame):
    """Categorías con su cantidad y origen; controla los filtros de la lista."""

    def __init__(self, al_categoria, al_origen):
        super().__init__()
        self.setObjectName('panel')
        self.setFixedWidth(190)
        self._al_categoria, self._al_origen = al_categoria, al_origen
        exterior = QVBoxLayout(self)
        exterior.setContentsMargins(8, 12, 8, 12)
        zona = QScrollArea()
        zona.setWidgetResizable(True)
        zona.setFrameShape(QFrame.NoFrame)
        zona.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cuerpo = QWidget()
        cuerpo.setObjectName('scroll_content')
        self._layout = QVBoxLayout(cuerpo)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(2)
        self._layout.addWidget(self._grupo('CATEGORÍAS'))
        self._categorias = QVBoxLayout()
        self._categorias.setSpacing(2)
        self._layout.addLayout(self._categorias)
        self._layout.addSpacing(14)
        self._layout.addWidget(self._grupo('ORIGEN'))
        self.origenes = {}
        for nombre in ('Propias', 'Compartidas'):
            self.origenes[nombre] = self._boton(nombre, lambda n=nombre: self._al_origen(n))
            self._layout.addWidget(self.origenes[nombre])
        self._layout.addStretch()
        zona.setWidget(cuerpo)
        exterior.addWidget(zona)
        self.categorias = {}

    @staticmethod
    def _grupo(texto):
        etiqueta = QLabel(texto)
        etiqueta.setObjectName('filtro_grupo')
        return etiqueta

    @staticmethod
    def _boton(texto, accion):
        b = QPushButton(texto)
        b.setObjectName('filtro')
        b.setCheckable(True)
        b.clicked.connect(lambda _=False: accion())
        return b

    def actualizar(self, cantidades, total, elegida, origen):
        """cantidades: {categoría: número}. elegida es None cuando se ven todas."""
        while self._categorias.count():
            anterior = self._categorias.takeAt(0).widget()
            anterior.hide()
            anterior.deleteLater()
        self.categorias = {}
        for nombre, numero in [(None, total), *sorted(cantidades.items())]:
            texto = f'{nombre or "Todas"}   ({numero})'
            # «&» marcaría un atajo de teclado dentro del botón.
            b = self._boton(texto.replace('&', '&&'), lambda n=nombre: self._al_categoria(n))
            b.setToolTip(nombre or 'Todas las categorías')
            b.setChecked(nombre == elegida)
            self._categorias.addWidget(b)
            self.categorias[nombre] = b
        for nombre, b in self.origenes.items():
            b.setChecked(nombre == origen)
