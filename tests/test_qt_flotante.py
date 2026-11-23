import os
from dataclasses import dataclass

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
if os.name == 'nt':
    os.environ.setdefault('QT_QPA_FONTDIR', r'C:\Windows\Fonts')

import pytest

pytest.importorskip('PySide6')

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QDialog, QLabel as QtLabel, QSizePolicy, QWidget

from fraseya.presentacion.qt_flotante import (
    ANCHO_FLOTANTE,
    COLORES_TONO,
    MARGEN_PANTALLA,
    MARGEN_SUPERIOR_VENTANA,
    SEPARACION_VERTICAL,
    BarraFlotanteIA,
    ControladorFlotanteQt,
    TarjetaSugerenciaFlotante,
)
from fraseya.presentacion.qt_paneles import EtiquetaSegura


@dataclass(frozen=True)
class _OpcionPrueba:
    indice: int
    etiqueta: str
    tono: str
    frase: dict
    motivo: str


@dataclass(frozen=True)
class _ResultadoPrueba:
    tema: str
    animo: str
    urgencia: str
    opciones: tuple
    mensaje_origen: str = ''


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def _resultado_ejemplo():
    return _ResultadoPrueba(
        tema='Pedido y envío',
        animo='Molesto',
        urgencia='Alta',
        opciones=(
            _OpcionPrueba(
                indice=1,
                etiqueta='Opción 1 · Empática',
                tono='empatica',
                frase={
                    'id': 101,
                    'titulo': 'Disculpa por retraso',
                    'contenido': (
                        'Hola, lamento mucho la demora con tu pedido. '
                        'Ya estoy revisando el estado con despacho para darte una respuesta concreta hoy mismo.'
                    ),
                },
                motivo='Valida la molestia del cliente y ofrece seguimiento inmediato.',
            ),
            _OpcionPrueba(
                indice=2,
                etiqueta='Opción 2 · Directa',
                tono='directa',
                frase={
                    'id': 102,
                    'titulo': 'Solicitar número de orden',
                    'contenido': (
                        'Por favor indícame tu número de pedido y correo registrado '
                        'para verificar el seguimiento en este momento.'
                    ),
                },
                motivo='Pide los datos clave para ubicar la orden rápido.',
            ),
            _OpcionPrueba(
                indice=3,
                etiqueta='Opción 3 · Escalar',
                tono='escalar',
                frase={
                    'id': 103,
                    'titulo': 'Derivación a logística',
                    'contenido': (
                        'Voy a escalar tu caso con prioridad al equipo de logística '
                        'para confirmar la entrega y te avisaremos apenas respondan.'
                    ),
                },
                motivo='Útil si el pedido ya superó el plazo comprometido.',
            ),
        ),
        mensaje_origen='Mi pedido lleva tres días atrasado y nadie me responde.',
    )


def _sin_dialogos_visibles(app):
    return not any(isinstance(w, QDialog) and w.isVisible() for w in app.topLevelWidgets())


def _dentro_de_pantalla(widget, avail: QRect):
    rect = QRect(widget.pos(), widget.size())
    return (
        rect.left() >= avail.left()
        and rect.top() >= avail.top()
        and rect.right() <= avail.right()
        and rect.bottom() <= avail.bottom()
    )


def test_creacion_visibilidad_toggle_y_callbacks(app):
    toggles = []
    lecturas = []
    portapapeles = []
    ocultados = []

    ctrl = ControladorFlotanteQt(
        al_toggle_activo=toggles.append,
        al_leer_chat=lambda: lecturas.append(True),
        al_analizar_portapapeles=lambda: portapapeles.append(True),
        al_ocultar=lambda: ocultados.append(True),
        tema='claro',
    )
    try:
        assert ANCHO_FLOTANTE == 390
        assert isinstance(ctrl.barra, BarraFlotanteIA)
        assert ctrl.tarjetas == []
        assert ctrl.activo is False
        assert ctrl.tema == 'claro'
        assert ctrl.barra.btn_estado.text() == 'PAUSADA'
        assert ctrl.barra.btn_leer_chat.text() == 'Leer últimos 3'
        assert ctrl.barra.btn_portapapeles.text() == 'Portapapeles'
        assert bool(ctrl.barra.windowFlags() & Qt.WindowDoesNotAcceptFocus)
        assert bool(ctrl.barra.windowFlags() & Qt.WindowStaysOnTopHint)
        assert bool(ctrl.barra.windowFlags() & Qt.FramelessWindowHint)

        ctrl.mostrar_barra()
        app.processEvents()
        assert ctrl.barra.isVisible()

        # Botón principal "Leer últimos 3" y estado cargando
        ctrl.barra.btn_leer_chat.click()
        assert lecturas == [True]
        ctrl.establecer_cargando(True)
        assert not ctrl.barra.btn_leer_chat.isEnabled()
        assert not ctrl.barra.btn_portapapeles.isEnabled()
        ctrl.barra.btn_leer_chat.click()
        assert lecturas == [True]  # bloqueado mientras carga
        ctrl.establecer_cargando(False)
        assert ctrl.barra.btn_leer_chat.isEnabled()
        assert ctrl.barra.btn_leer_chat.text() == 'Leer últimos 3'

        # Los 3 chips caben completos sin recorte en ANCHO_FLOTANTE = 390
        ctrl.barra.actualizar_contexto('Consulta general', 'Neutral', 'Normal')
        app.processEvents()
        marco_rect = ctrl.barra.marco.contentsRect()
        for chip in (ctrl.barra.chip_tema, ctrl.barra.chip_animo, ctrl.barra.chip_urgencia):
            assert chip.textFormat() == Qt.PlainText
            assert chip.width() >= chip.sizeHint().width()
            assert chip.geometry().right() <= marco_rect.right()

        # Toggle ACTIVA / PAUSADA vía botón
        ctrl.barra.btn_estado.click()
        assert ctrl.activo is True
        assert ctrl.barra.btn_estado.text() == 'ACTIVA'
        assert toggles == [True]

        ctrl.barra.btn_estado.click()
        assert ctrl.activo is False
        assert ctrl.barra.btn_estado.text() == 'PAUSADA'
        assert toggles == [True, False]

        # establecer_activo sincroniza estado sin re-disparar callback
        ctrl.establecer_activo(True)
        assert ctrl.activo is True
        assert ctrl.barra.btn_estado.text() == 'ACTIVA'
        assert toggles == [True, False]

        # Botón "Portapapeles"
        ctrl.barra.btn_portapapeles.click()
        assert portapapeles == [True]

        # Botón "×" oculta todo y llama al_ocultar
        ctrl.barra.btn_cerrar.click()
        app.processEvents()
        assert not ctrl.barra.isVisible()
        assert ocultados == [True]
    finally:
        ctrl.detener()
        app.processEvents()


def test_tarjeta_variables_inline_sin_dialogo_y_con_etiquetas_seguras(app):
    usadas = []
    ctrl = ControladorFlotanteQt(
        al_usar=lambda frase, texto: usadas.append((frase, texto)),
        tema='oscuro',
    )
    try:
        resultado = _ResultadoPrueba(
            tema='Pedido / Envío',
            animo='Apurado',
            urgencia='Alta',
            opciones=(
                _OpcionPrueba(
                    indice=1,
                    etiqueta='Opción 1 · Empática',
                    tono='empatica',
                    frase={
                        'id': 301,
                        'titulo': 'Confirmación pedido',
                        'contenido': 'Hola {nombre}, tu pedido #{pedido} ya va en camino.',
                    },
                    motivo='Completa los datos inline antes de insertar.',
                ),
            ),
        )
        ctrl.mostrar_sugerencias(resultado)
        app.processEvents()
        tarjeta = ctrl.tarjetas[0]
        assert bool(tarjeta.windowFlags() & Qt.WindowDoesNotAcceptFocus)

        # Pulsar Usar en frase con {variables} abre campos inline en la misma tarjeta (sin QDialog)
        tarjeta.btn_usar.click()
        app.processEvents()
        assert tarjeta.en_variables is True
        assert len(usadas) == 0
        assert _sin_dialogos_visibles(app)
        assert not bool(tarjeta.windowFlags() & Qt.WindowDoesNotAcceptFocus)
        assert ctrl.esta_en_foco_propio() is True
        assert list(tarjeta._campos_variables.keys()) == ['nombre', 'pedido']

        # Todas las etiquetas (incluidas las creadas dinámicamente para variables) son Qt.PlainText
        for lbl in tarjeta.findChildren(QtLabel):
            assert isinstance(lbl, EtiquetaSegura)
            assert lbl.textFormat() == Qt.PlainText

        # Confirmar sin completar campos muestra aviso inline y no dispara al_usar
        tarjeta.btn_insertar_variables.click()
        app.processEvents()
        assert tarjeta.en_variables is True
        assert tarjeta.lbl_error_variables.isVisible()
        assert 'nombre' in tarjeta.lbl_error_variables.text()
        assert len(usadas) == 0

        # Completar variables actualiza vista previa en vivo y al confirmar inserta el texto resuelto
        tarjeta._campos_variables['nombre'].setText('Camila')
        tarjeta._campos_variables['pedido'].setText('4821')
        app.processEvents()
        assert tarjeta.lbl_preview_variables.text() == 'Hola Camila, tu pedido #4821 ya va en camino.'

        tarjeta.btn_insertar_variables.click()
        app.processEvents()
        assert tarjeta.en_variables is False
        assert bool(tarjeta.windowFlags() & Qt.WindowDoesNotAcceptFocus)
        assert len(usadas) == 1
        assert usadas[0][0]['id'] == 301
        assert usadas[0][1] == 'Hola Camila, tu pedido #4821 ya va en camino.'
        assert _sin_dialogos_visibles(app)

        # Abrir de nuevo y cancelar vuelve a vista lectura sin llamar al_usar
        tarjeta.btn_usar.click()
        app.processEvents()
        assert tarjeta.en_variables is True
        tarjeta.btn_cancelar_variables.click()
        app.processEvents()
        assert tarjeta.en_variables is False
        assert bool(tarjeta.windowFlags() & Qt.WindowDoesNotAcceptFocus)
        assert len(usadas) == 1
    finally:
        ctrl.detener()
        app.processEvents()


def test_sugerencias_etiquetas_seguras_usar_y_edicion_inline(app):
    usadas = []
    ctrl = ControladorFlotanteQt(al_usar=lambda frase, texto: usadas.append((frase, texto)))
    try:
        base = _resultado_ejemplo()
        # Inyectamos cadenas tipo HTML para verificar que se mantienen literales (Qt.PlainText)
        html_opcion = _OpcionPrueba(
            indice=1,
            etiqueta='Opción 1 · <b>Empática</b>',
            tono='empatica',
            frase={
                'id': 201,
                'titulo': '<script>alert(1)</script>',
                'contenido': 'Hola <b>cliente</b>, revisamos tu orden <img src="x"> ahora mismo.',
            },
            motivo='Motivo <i>seguro</i> sin HTML.',
        )
        cuarta_extra = _OpcionPrueba(
            indice=4,
            etiqueta='Opción 4 · Extra',
            tono='directa',
            frase={'id': 204, 'titulo': 'Extra', 'contenido': 'No debe mostrarse.'},
            motivo='Excede el máximo de 3.',
        )
        resultado = _ResultadoPrueba(
            tema='<b>Envío</b>',
            animo='Molesto',
            urgencia='Alta',
            opciones=(html_opcion, base.opciones[1], base.opciones[2], cuarta_extra),
        )

        ctrl.mostrar_sugerencias(resultado)
        app.processEvents()

        # Máximo 3 tarjetas
        assert len(ctrl.tarjetas) == 3
        assert all(isinstance(t, TarjetaSugerenciaFlotante) for t in ctrl.tarjetas)
        assert all(t.isVisible() for t in ctrl.tarjetas)

        # Chips actualizados en la barra
        assert '<b>Envío</b>' in ctrl.barra.chip_tema.text()
        assert 'Molesto' in ctrl.barra.chip_animo.text()
        assert 'Alta' in ctrl.barra.chip_urgencia.text()

        # Colores de cabecera por tono
        assert ctrl.tarjetas[0].color_cabecera == COLORES_TONO['empatica']
        assert ctrl.tarjetas[1].color_cabecera == COLORES_TONO['directa']
        assert ctrl.tarjetas[2].color_cabecera == COLORES_TONO['escalar']

        # TODAS las QLabel en barra y tarjetas son EtiquetaSegura con Qt.PlainText
        for widget in [ctrl.barra, *ctrl.tarjetas]:
            etiquetas = widget.findChildren(QtLabel)
            assert etiquetas
            for lbl in etiquetas:
                assert isinstance(lbl, EtiquetaSegura)
                assert lbl.textFormat() == Qt.PlainText

        # Pulsar "Usar" en la tarjeta 2 invoca al_usar con frase y texto exactos
        t2 = ctrl.tarjetas[1]
        t2.btn_usar.click()
        assert len(usadas) == 1
        assert usadas[0][0]['id'] == 102
        assert usadas[0][1] == base.opciones[1].frase['contenido']
        assert _sin_dialogos_visibles(app)

        # Pulsar "Editar" en la tarjeta 1 abre edición inline sin QDialog y habilita foco
        t1 = ctrl.tarjetas[0]
        assert bool(t1.windowFlags() & Qt.WindowDoesNotAcceptFocus)
        t1.btn_editar.click()
        app.processEvents()
        assert t1.en_edicion is True
        assert not bool(t1.windowFlags() & Qt.WindowDoesNotAcceptFocus)
        assert ctrl.esta_en_foco_propio() is True
        assert _sin_dialogos_visibles(app)

        # Cancelar vuelve al modo normal sin llamar al_usar
        t1.editor.setPlainText('Texto descartado')
        t1.btn_cancelar_edicion.click()
        app.processEvents()
        assert t1.en_edicion is False
        assert bool(t1.windowFlags() & Qt.WindowDoesNotAcceptFocus)
        assert len(usadas) == 1

        # Edición vacía no dispara al_usar y permanece en modo edición
        t1.btn_editar.click()
        app.processEvents()
        t1.editor.setPlainText('   \n  ')
        t1.btn_insertar_editado.click()
        app.processEvents()
        assert t1.en_edicion is True
        assert len(usadas) == 1

        # Editar + "Insertar editado" entrega el texto editado sin abrir QDialog
        texto_editado = 'Hola Sofía, ya validamos tu despacho y llega hoy a las 18:00.'
        t1.editor.setPlainText(texto_editado)
        t1.btn_insertar_editado.click()
        app.processEvents()
        assert t1.en_edicion is False
        assert bool(t1.windowFlags() & Qt.WindowDoesNotAcceptFocus)
        assert len(usadas) == 2
        assert usadas[1][0]['id'] == 201
        assert usadas[1][1] == texto_editado
        assert _sin_dialogos_visibles(app)

        # Descartar tarjeta 3 con botón "×"
        ctrl.tarjetas[2].btn_descartar.click()
        app.processEvents()
        assert len(ctrl.tarjetas) == 2
    finally:
        ctrl.detener()
        app.processEvents()


def test_compatibilidad_dict_aviso_y_texto_largo(app):
    ctrl = ControladorFlotanteQt()
    try:
        largo = ' '.join(['Este es un mensaje extenso de seguimiento de pedido para verificar el scroll limpio.'] * 6)
        ctrl.mostrar_sugerencias({
            'tema': 'Soporte',
            'animo': 'Neutral',
            'urgencia': 'Normal',
            'opciones': [
                {'indice': 1, 'tono': 'empatica', 'frase': {'id': 1, 'contenido': largo}, 'motivo': 'Texto extenso'},
            ],
        })
        app.processEvents()
        assert len(ctrl.tarjetas) == 1
        assert 80 <= ctrl.tarjetas[0].scroll_contenido.height() <= 160
        assert ctrl.tarjetas[0].scroll_contenido.verticalScrollBar().maximum() > 0
        assert ctrl.tarjetas[0].height() <= 280

        ctrl.mostrar_aviso('<b>Sin coincidencias</b>')
        app.processEvents()
        assert ctrl.barra.lbl_aviso.isVisible()
        assert ctrl.barra.lbl_aviso.textFormat() == Qt.PlainText
        assert ctrl.barra.lbl_aviso.text() == '<b>Sin coincidencias</b>'

        ctrl.ocultar_sugerencias()
        assert ctrl.tarjetas == []
        assert ctrl.barra.isVisible()

        ctrl.ocultar_todo()
        assert not ctrl.barra.isVisible()
    finally:
        ctrl.detener()
        app.processEvents()


def test_limpiar_contexto_borra_chips_demo_y_reajusta_aviso(app):
    ctrl = ControladorFlotanteQt()
    try:
        ctrl.mostrar_sugerencias(_resultado_ejemplo())
        app.processEvents()
        assert len(ctrl.tarjetas) == 3
        assert 'Pedido' in ctrl.barra.chip_tema.text()
        assert 'Molesto' in ctrl.barra.chip_animo.text()
        assert 'Alta' in ctrl.barra.chip_urgencia.text()

        ctrl.limpiar_contexto('Escuchando WhatsApp…')
        app.processEvents()
        assert ctrl.tarjetas == []
        assert ctrl.barra.chip_tema.text() == 'Esperando mensaje…'
        assert ctrl.barra.chip_animo.text() == 'Ánimo: —'
        assert ctrl.barra.chip_urgencia.text() == 'Urgencia: —'
        assert ctrl.barra.lbl_aviso.isVisible()
        assert ctrl.barra.lbl_aviso.text() == 'Escuchando WhatsApp…'
        assert ctrl.barra.lbl_aviso.textFormat() == Qt.PlainText

        alto_con_aviso = ctrl.barra.height()
        ctrl.mostrar_aviso('')
        app.processEvents()
        assert not ctrl.barra.lbl_aviso.isVisible()
        assert ctrl.barra.height() <= alto_con_aviso
    finally:
        ctrl.detener()
        app.processEvents()


def test_reposicionar_ventana_normal_maximizada_y_arrastre(app):
    ctrl = ControladorFlotanteQt()
    try:
        avail = QApplication.primaryScreen().availableGeometry()

        # Caso 1: ventana de chat normal con espacio a la derecha
        ancho_chat = max(220, avail.width() - ANCHO_FLOTANTE - MARGEN_PANTALLA * 3 - 20)
        rect_normal = (avail.left() + 16, avail.top() + 30, ancho_chat, 520)
        ctrl.mostrar_sugerencias(_resultado_ejemplo(), rect_chat=rect_normal)
        app.processEvents()

        elementos = [ctrl.barra, *ctrl.tarjetas]
        assert len(elementos) == 4
        for w in elementos:
            assert _dentro_de_pantalla(w, avail)
            assert w.x() >= rect_normal[0] + rect_normal[2]

        # Apiladas verticalmente con 10px de separación (cuando caben en 1 columna)
        xs = {w.x() for w in elementos}
        if len(xs) == 1:
            for arriba, abajo in zip(elementos, elementos[1:]):
                assert abajo.y() - (arriba.y() + arriba.height()) == SEPARACION_VERTICAL

        # Caso 2: ventana maximizada (no cabe a la derecha -> borde derecho interior debajo de _ □ ×)
        rect_max = (avail.left(), avail.top(), avail.width(), avail.height())
        ctrl.reposicionar(rect_max)
        app.processEvents()

        x_esperada_borde = avail.left() + avail.width() - ANCHO_FLOTANTE - MARGEN_PANTALLA
        assert ctrl.barra.x() == x_esperada_borde
        assert ctrl.barra.y() >= avail.top() + MARGEN_SUPERIOR_VENTANA
        for w in elementos:
            assert _dentro_de_pantalla(w, avail)
            assert w.y() >= avail.top() + MARGEN_SUPERIOR_VENTANA

        # Caso 2b: ventana maximizada en Windows con borde invisible negativo (ry = -8)
        rect_max_win = (avail.left() - 8, avail.top() - 8, avail.width() + 16, avail.height() + 16)
        ctrl.reposicionar(rect_max_win, forzar=True)
        app.processEvents()
        assert ctrl.barra.y() >= avail.top() + MARGEN_SUPERIOR_VENTANA
        assert _dentro_de_pantalla(ctrl.barra, avail)

        # Caso 3: ventana más grande que la pantalla actual (multi-monitor / resolución alta)
        ctrl.reposicionar((0, 0, 2560, 1440))
        app.processEvents()
        for w in elementos:
            assert _dentro_de_pantalla(w, avail)

        # Caso 4: respeta arrastre manual en reposicionar normal y reposiciona con forzar=True
        t0 = ctrl.tarjetas[0]
        t0.move(QPoint(avail.left() + 24, avail.top() + 40))
        t0.arrastrada_manualmente = True
        pos_manual = t0.pos()
        ctrl.reposicionar(rect_max)
        assert t0.pos() == pos_manual
        ctrl.reposicionar(rect_max, forzar=True)
        assert _dentro_de_pantalla(t0, avail)
    finally:
        ctrl.detener()
        app.processEvents()


def test_aplicar_tema_claro_y_oscuro_y_renderizado_compuesto(app, tmp_path):
    ctrl = ControladorFlotanteQt(tema='claro')
    try:
        ctrl.establecer_activo(True)
        ctrl.mostrar_sugerencias(_resultado_ejemplo())
        app.processEvents()

        assert ctrl.tema == 'claro'
        assert '#16263d' in ctrl.barra.styleSheet()
        assert '#ffffff' in ctrl.tarjetas[0].styleSheet()

        ctrl.aplicar_tema('oscuro')
        app.processEvents()
        assert ctrl.tema == 'oscuro'
        assert ctrl.barra.tema == 'oscuro'
        assert all(t.tema == 'oscuro' for t in ctrl.tarjetas)
        assert '#0b1220' in ctrl.barra.styleSheet()
        assert '#2b3a52' in ctrl.barra.styleSheet()
        assert '#1c2533' in ctrl.tarjetas[0].styleSheet()

        # Tema desconocido cae limpiamente a 'claro'
        ctrl.aplicar_tema('inexistente')
        app.processEvents()
        assert ctrl.tema == 'claro'
        assert '#16263d' in ctrl.barra.styleSheet()

        # Comprobación de renderizado compuesto en ambos temas
        for tema, fondo in (('claro', '#eef2f7'), ('oscuro', '#0f141c')):
            ctrl.aplicar_tema(tema)
            app.processEvents()
            widgets = [ctrl.barra, *ctrl.tarjetas]
            margen = 20
            ancho = max(w.width() for w in widgets) + margen * 2
            alto = sum(w.height() for w in widgets) + SEPARACION_VERTICAL * (len(widgets) - 1) + margen * 2
            lienzo = QPixmap(ancho, alto)
            lienzo.fill(QColor(fondo))
            pintor = QPainter(lienzo)
            y = margen
            for w in widgets:
                pintor.drawPixmap(margen, y, w.grab())
                y += w.height() + SEPARACION_VERTICAL
            pintor.end()
            salida = tmp_path / f'flotante_{tema}.png'
            assert lienzo.save(str(salida), 'PNG')
            assert salida.exists() and salida.stat().st_size > 1000
    finally:
        ctrl.detener()
        app.processEvents()


def test_detener_es_idempotente_y_seguro_al_destruir_parent(app):
    parent = QWidget()
    ctrl = ControladorFlotanteQt(parent=parent)
    ctrl.mostrar_sugerencias(_resultado_ejemplo())
    app.processEvents()

    # Detener explícitamente y procesar deleteLater antes de destruir parent
    ctrl.detener()
    app.processEvents()

    # Segunda invocación explícita y llamadas tardías tras detener no deben fallar
    ctrl.detener()
    ctrl.ocultar_todo()
    ctrl.aplicar_tema('oscuro')
    ctrl.establecer_activo(True)
    ctrl.reposicionar((0, 0, 400, 400))
    assert ctrl.esta_en_foco_propio() is False

    # Destruir parent dispara parent.destroyed -> no debe lanzar RuntimeError
    parent.deleteLater()
    app.processEvents()


def test_barra_aviso_multilinea_sin_recorte_y_reposiciona_tarjetas(app):
    ctrl = ControladorFlotanteQt(tema='claro')
    try:
        ctrl.establecer_activo(True)
        ctrl.mostrar_barra()
        app.processEvents()

        alto_sin_aviso = ctrl.barra.height()
        aviso_largo = (
            'No se detectaron mensajes visibles en el chat. '
            'Abre una conversación en WhatsApp o usa «Portapapeles» para analizar un mensaje copiado.'
        )
        ctrl.mostrar_aviso(aviso_largo)
        app.processEvents()

        lbl = ctrl.barra.lbl_aviso
        assert lbl.isVisible()
        assert lbl.wordWrap() is True
        assert lbl.textFormat() == Qt.PlainText
        assert lbl.sizePolicy().verticalPolicy() == QSizePolicy.Minimum

        # Mide altura real requerida por el texto multilínea (2-3 líneas en ANCHO_FLOTANTE=390)
        fm = QFontMetrics(lbl.font())
        ancho_interno = max(80, lbl.width() - 18)
        rect_medido = fm.boundingRect(QRect(0, 0, ancho_interno, 2000), Qt.TextWordWrap, aviso_largo)
        assert rect_medido.height() >= fm.lineSpacing() * 2
        assert lbl.height() >= rect_medido.height() + 10
        assert lbl.geometry().bottom() <= ctrl.barra.marco.contentsRect().bottom() + 2
        assert ctrl.barra.height() > alto_sin_aviso + fm.lineSpacing()

        # Al mostrar tarjetas y luego un aviso largo, reposicionar no recorta el aviso ni superpone tarjetas
        ctrl.mostrar_sugerencias(_resultado_ejemplo())
        ctrl.mostrar_aviso(aviso_largo)
        app.processEvents()
        alto_con_aviso = ctrl.barra.height()
        assert lbl.height() >= rect_medido.height() + 10
        if ctrl.tarjetas and ctrl.tarjetas[0].x() == ctrl.barra.x():
            assert ctrl.tarjetas[0].y() >= ctrl.barra.y() + ctrl.barra.height() + SEPARACION_VERTICAL

        # reposicionar() posterior mantiene la altura completa del aviso sin truncar
        ctrl.reposicionar((0, 0, 1280, 720), forzar=True)
        app.processEvents()
        assert ctrl.barra.height() >= alto_con_aviso
        assert lbl.height() >= rect_medido.height() + 10

        # Ocultar aviso devuelve la barra a su altura compacta
        ctrl.mostrar_aviso('')
        app.processEvents()
        assert not lbl.isVisible()
        assert ctrl.barra.height() <= alto_sin_aviso + 4
    finally:
        ctrl.detener()
        app.processEvents()


def test_edicion_tarjeta_inserta_variables_app_y_abre_formulario_inline(app):
    usados = []
    ctrl = ControladorFlotanteQt(al_usar=lambda frase, texto: usados.append((frase, texto)))
    try:
        ctrl.mostrar_sugerencias({
            'tema': 'Consulta',
            'animo': 'Neutral',
            'urgencia': 'Normal',
            'opciones': [
                {'indice': 1, 'tono': 'directa', 'frase': {'id': 1, 'contenido': 'Hola, revisamos tu caso.'}, 'motivo': 'Base'},
            ],
        })
        app.processEvents()
        tarjeta = ctrl.tarjetas[0]
        tarjeta.btn_editar.click()
        app.processEvents()
        assert tarjeta.en_edicion is True

        # Botones y selector de variables oficiales creadas en la app
        assert set(tarjeta._botones_variables_edicion) == {'nombre', 'pedido', 'fecha'}
        tarjeta._botones_variables_edicion['nombre'].click()
        tarjeta._insertar_variable_editor('empresa')
        app.processEvents()
        assert '{nombre}' in tarjeta.editor.toPlainText()
        assert '{empresa}' in tarjeta.editor.toPlainText()

        # Al confirmar edición con variables, pasa al formulario inline antes de copiar/pegar
        tarjeta.btn_insertar_editado.click()
        app.processEvents()
        assert tarjeta.en_edicion is False
        assert tarjeta.en_variables is True
        assert usados == []

        tarjeta._campos_variables['nombre'].setText('Camila')
        tarjeta._campos_variables['empresa'].setText('ConTech')
        tarjeta.btn_insertar_variables.click()
        app.processEvents()
        assert len(usados) == 1
        assert 'Camila' in usados[0][1]
        assert 'ConTech' in usados[0][1]
    finally:
        ctrl.detener()
        app.processEvents()


