"""Piezas del panel lateral: iconos de línea, marca, estado de sincronización y perfil."""
import html
import re

from PySide6.QtCore import Qt, QByteArray, QSize
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QVBoxLayout

from .identidad import recurso
from .qt_paneles import EtiquetaSegura as QLabel

ANCHO = 248
_COLOR = '#c7d5f5'
_COLOR_ACTIVO = '#ffffff'

_ICONOS = {
    'frases': '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/><path d="M8 8h8M8 12h5"/>',
    'favoritas': '<path d="M12 3l2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3 6.4 20.2 7.5 14 3 9.6l6.2-.9z"/>',
    'ia': '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/><path d="M19 16v5M16.5 18.5h5"/>',
    'importar': '<path d="M12 3v12M7 10l5 5 5-5"/><path d="M4 20h16"/>',
    'publicar': '<path d="M12 3L3 8l9 5 9-5z"/><path d="M3 13l9 5 9-5"/>',
    'categorias': '<path d="M3 11V4a1 1 0 0 1 1-1h7l10 10-8 8z"/><circle cx="8" cy="8" r="1.5"/>',
    'configuracion': '<path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2.5"/>'
                     '<circle cx="10" cy="17" r="2.5"/>',
    'salir': '<path d="M9 4H5a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h4"/><path d="M15 8l4 4-4 4M19 12H9"/>',
    'sincronizar': '<path d="M20 11a8 8 0 0 0-14.5-4.5L4 8M4 4v4h4"/>'
                   '<path d="M4 13a8 8 0 0 0 14.5 4.5L20 16M20 20v-4h-4"/>',
}


def _pixmap(nombre, color):
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="%s" '
           'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">%s</svg>') % (color, _ICONOS[nombre])
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    pintor = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode('ascii'))).render(pintor)
    pintor.end()
    return pixmap


def poner_icono(boton, nombre, tam=18):
    icono = QIcon()
    icono.addPixmap(_pixmap(nombre, _COLOR), QIcon.Normal, QIcon.Off)
    icono.addPixmap(_pixmap(nombre, _COLOR_ACTIVO), QIcon.Normal, QIcon.On)
    boton.setIcon(icono)
    boton.setIconSize(QSize(tam, tam))


def etiqueta(texto, nombre):
    e = QLabel(texto)
    e.setObjectName(nombre)
    return e


def boton_icono(nombre, descripcion, accion):
    b = QPushButton()
    b.setObjectName('lateral_icono')
    b.setToolTip(descripcion)
    b.setAccessibleName(descripcion)
    b.setFixedSize(30, 30)
    poner_icono(b, nombre, 17)
    b.clicked.connect(lambda _=False: accion())
    return b


def marca():
    fila = QHBoxLayout()
    fila.setContentsMargins(6, 0, 0, 0)
    fila.setSpacing(10)
    logo = QLabel()
    logo.setPixmap(QPixmap(str(recurso('logo.png'))).scaled(38, 38, Qt.KeepAspectRatio, Qt.SmoothTransformation))
    fila.addWidget(logo)
    textos = QVBoxLayout()
    textos.setSpacing(0)
    textos.addWidget(etiqueta('FraseYa', 'lateral_marca'))
    textos.addWidget(etiqueta('Las palabras, a su tiempo.', 'lateral_tenue'))
    fila.addLayout(textos)
    fila.addStretch()
    return fila


def separador():
    linea = QFrame()
    linea.setObjectName('lateral_linea')
    linea.setFixedHeight(1)
    return linea


_COLORES_ESTADO = {'actualizada': '#34d399', 'sin_cambios': '#34d399', 'error': '#f87171',
                   'offline': '#fbbf24', 'comprobando': '#60a5fa', 'pendiente': '#8ea3d6'}


class TarjetaSync(QFrame):
    """Estado del catálogo en dos líneas; el texto completo queda en la ayuda emergente."""
    def __init__(self, al_sincronizar):
        super().__init__()
        self.setObjectName('lateral_tarjeta')
        fila = QHBoxLayout(self)
        fila.setContentsMargins(12, 9, 8, 9)
        fila.setSpacing(10)
        self.punto = etiqueta('●', 'lateral_punto')
        fila.addWidget(self.punto)
        textos = QVBoxLayout()
        textos.setSpacing(0)
        self.titulo = etiqueta('', 'lateral_usuario')
        self.detalle = etiqueta('', 'lateral_tenue')
        for e in (self.titulo, self.detalle):
            e.setWordWrap(True)
            textos.addWidget(e)
        fila.addLayout(textos, 1)
        fila.addWidget(boton_icono('sincronizar', 'Sincronizar ahora', al_sincronizar))
        self.mostrar('pendiente', 'Catálogo central', 'Supabase')

    def mostrar(self, estado, titulo, detalle, completo=''):
        self.punto.setStyleSheet('color:%s;' % _COLORES_ESTADO.get(estado, '#8ea3d6'))
        self.titulo.setText(titulo)
        self.detalle.setText(detalle)
        # Texto plano: el detalle puede venir del servidor.
        self.setToolTip('<qt>%s</qt>' % html.escape(completo).replace(chr(10), '<br>') if completo else '')


def iniciales(usuario):
    palabra = re.split(r'[\W_]+', usuario.split('@')[0].strip())[0]
    return palabra[:2].upper() or '?'


def perfil(usuario, rol, al_salir=None):
    fila = QHBoxLayout()
    fila.setContentsMargins(6, 0, 0, 0)
    fila.setSpacing(10)
    avatar = etiqueta(iniciales(usuario), 'lateral_avatar')
    avatar.setFixedSize(34, 34)
    avatar.setAlignment(Qt.AlignCenter)
    fila.addWidget(avatar)
    textos = QVBoxLayout()
    textos.setSpacing(0)
    correo = etiqueta('', 'lateral_usuario')
    correo.setText(correo.fontMetrics().elidedText(usuario, Qt.ElideRight, 136))
    correo.setToolTip(usuario)
    textos.addWidget(correo)
    textos.addWidget(etiqueta(rol.capitalize(), 'lateral_tenue'))
    fila.addLayout(textos, 1)
    if al_salir is not None:
        fila.addWidget(boton_icono('salir', 'Cerrar sesión', al_salir))
    return fila
