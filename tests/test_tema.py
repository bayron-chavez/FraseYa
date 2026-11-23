import os
import re

import pytest

from fraseya.aplicacion.configuracion import (
    Ajustes,
    Configuracion,
    TEMA_PREDETERMINADO,
    TEMAS_VALIDOS,
)
from fraseya.aplicacion.gestion_frases import ErroresValidacion
from fraseya.infraestructura import RepositorioSQLite
from fraseya.presentacion.qt_temas import ESTILO, ESTILO_OSCURO, hoja_estilo, paleta

CLAVES_PALETA = {
    'fondo',
    'superficie',
    'panel',
    'tarjeta',
    'texto',
    'texto_tenue',
    'borde',
    'primario',
    'primario_hover',
    'pill_fondo',
    'pill_texto',
    'acento_empatica',
    'acento_directa',
    'acento_escalar',
    'peligro',
    'campo_fondo',
}

SELECTORES_ESPERADOS = (
    '#sidebar',
    '#panel',
    '#card',
    '#inline_confirm',
    '#banner_info',
    '#banner_ok',
    '#banner_aviso',
    '#banner_error',
    '#brand',
    '#heading',
    '#muted',
    '#section',
    '#nav_group',
    '#chip',
    '#primary',
    '#danger',
    '#ghost',
    '#nav',
    '#preview',
    '#theme_toggle',
    '#toggle_tema',
    'QScrollBar',
    'QScrollArea',
    'QListWidget',
    'QComboBox',
    'QComboBox QAbstractItemView',
    'QSpinBox',
    'QLineEdit',
    'QTextEdit',
    'QMenu',
    'QDialog',
)


@pytest.fixture
def repo():
    with RepositorioSQLite(':memory:') as r:
        yield r


@pytest.fixture
def config(repo):
    return Configuracion(repo)


def test_ajustes_por_defecto_y_compatibilidad_posicional():
    assert TEMAS_VALIDOS == ('claro', 'oscuro')
    assert TEMA_PREDETERMINADO == 'claro'

    base = Ajustes()
    assert base.tema == 'claro'

    compat = Ajustes('enter', 'ctrl+shift+k', 35, 10)
    assert compat.tecla_confirmacion == 'enter'
    assert compat.atajo_buscador == 'ctrl+shift+k'
    assert compat.velocidad_ms == 35
    assert compat.intervalo_sincronizacion_min == 10
    assert compat.tema == 'claro'

    explicito = Ajustes('enter', 'ctrl+shift+k', 35, 10, 'oscuro')
    assert explicito.tema == 'oscuro'


def test_configuracion_valida_y_normaliza_tema(config):
    assert config.leer().tema == 'claro'

    assert config.guardar({'tema': 'oscuro'}).tema == 'oscuro'
    assert config.leer().tema == 'oscuro'

    assert config.guardar({'tema': '  CLARO  '}).tema == 'claro'
    assert config.leer().tema == 'claro'

    assert config.guardar({'tema': ' Oscuro '}).tema == 'oscuro'
    # Guardar otro campo no borra el tema seleccionado.
    actualizado = config.guardar({'velocidad_ms': '30'})
    assert actualizado.velocidad_ms == 30
    assert actualizado.tema == 'oscuro'


def test_configuracion_persiste_y_restablece_tema_en_sqlite(tmp_path):
    ruta = tmp_path / 'tema.db'
    with RepositorioSQLite(ruta) as r:
        guardado = Configuracion(r).guardar({'tema': 'oscuro', 'velocidad_ms': '40'})
        assert guardado.tema == 'oscuro'

    with RepositorioSQLite(ruta) as r:
        leido = Configuracion(r).leer()
        assert leido.tema == 'oscuro'
        assert leido.velocidad_ms == 40
        restablecido = Configuracion(r).restablecer()
        assert restablecido == Ajustes()
        assert restablecido.tema == 'claro'

    with RepositorioSQLite(ruta) as r:
        assert Configuracion(r).leer().tema == 'claro'


@pytest.mark.parametrize('valor', ['', '   ', 'dark', 'light', 'azul', 'neon', None, 123])
def test_configuracion_rechaza_tema_invalido(config, valor):
    config.guardar({'tema': 'oscuro'})
    with pytest.raises(ErroresValidacion, match='tema'):
        config.guardar({'tema': valor})
    assert config.leer().tema == 'oscuro'


def test_tema_corrupto_en_sqlite_cae_a_predeterminado_sin_perder_otros_campos(repo, config):
    repo.guardar_configuracion('tema', 'neon')
    repo.guardar_configuracion('tecla_confirmacion', 'enter')
    ajustes = config.leer()
    assert ajustes.tema == 'claro'
    assert ajustes.tecla_confirmacion == 'enter'


def test_paleta_devuelve_claves_semanticas_validas_y_fallback():
    claro = paleta('claro')
    oscuro = paleta('oscuro')

    assert set(claro) == CLAVES_PALETA
    assert set(oscuro) == CLAVES_PALETA
    assert claro != oscuro

    patron_hex = re.compile(r'^#[0-9a-fA-F]{6}$')
    for nombre, valores in (('claro', claro), ('oscuro', oscuro)):
        for clave, color in valores.items():
            assert patron_hex.match(color), f'Color inválido en {nombre}.{clave}: {color}'

    # Devolver copia protege la paleta interna.
    claro['fondo'] = '#000000'
    assert paleta('claro')['fondo'] != '#000000'

    # Normalización y fallback seguro.
    assert paleta('  OSCURO ') == oscuro
    for desconocido in ('desconocido', '', None, 42):
        assert paleta(desconocido) == paleta('claro')


def test_hoja_estilo_selectores_contraste_y_fallback():
    assert ESTILO == hoja_estilo('claro')
    assert ESTILO_OSCURO == hoja_estilo('oscuro')
    assert ESTILO != ESTILO_OSCURO
    assert hoja_estilo('  OSCURO  ') == ESTILO_OSCURO

    for desconocido in ('invalido', '', None, 99):
        assert hoja_estilo(desconocido) == ESTILO

    for selector in SELECTORES_ESPERADOS:
        assert selector in ESTILO, f'Falta {selector} en ESTILO'
        assert selector in ESTILO_OSCURO, f'Falta {selector} en ESTILO_OSCURO'

    # Colores distintivos de tema claro vs oscuro.
    assert '#f5f7fb' in ESTILO
    assert '#26364c' in ESTILO
    for color_oscuro in ('#0f141c', '#161d28', '#1c2533', '#111824', '#2a3649', '#eef2f7', '#94a3b8', '#3b82f6'):
        assert color_oscuro in ESTILO_OSCURO


def test_hojas_estilo_se_aplican_en_qt_sin_advertencias():
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtCore import qInstallMessageHandler
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QDialog,
        QLineEdit,
        QListWidget,
        QMenu,
        QPushButton,
        QScrollArea,
        QSpinBox,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )

    app = QApplication.instance() or QApplication([])
    advertencias = []

    def capturar(tipo, _ctx, mensaje):
        if 'stylesheet' in mensaje.lower() or 'unknown property' in mensaje.lower() or 'could not parse' in mensaje.lower():
            advertencias.append(mensaje)

    previo = qInstallMessageHandler(capturar)
    try:
        for tema in ('claro', 'oscuro'):
            dialogo = QDialog()
            dialogo.setStyleSheet(hoja_estilo(tema))
            layout = QVBoxLayout(dialogo)
            combo = QComboBox()
            combo.addItems(['claro', 'oscuro'])
            layout.addWidget(combo)
            layout.addWidget(QLineEdit('ejemplo'))
            layout.addWidget(QTextEdit('contenido'))
            layout.addWidget(QSpinBox())
            lista = QListWidget()
            lista.addItem('Elemento 1')
            layout.addWidget(lista)
            scroll = QScrollArea()
            scroll.setWidget(QWidget())
            layout.addWidget(scroll)
            toggle = QPushButton('Tema')
            toggle.setObjectName('theme_toggle')
            toggle.setCheckable(True)
            layout.addWidget(toggle)
            menu = QMenu(dialogo)
            menu.addAction('Acción')
            dialogo.ensurePolished()
            dialogo.show()
            app.processEvents()
            dialogo.close()
            dialogo.deleteLater()
            app.processEvents()
    finally:
        qInstallMessageHandler(previo)

    assert advertencias == []
