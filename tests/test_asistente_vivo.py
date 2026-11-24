import http.client
import json
from pathlib import Path
import threading
import time
from unittest.mock import Mock

import pytest

from fraseya.aplicacion.asistente_vivo import (
    OpcionFlotante,
    ResultadoVivo,
    ServicioAsistenteVivo,
    _variar_por_tono,
    clasificar_contexto,
    crear_resultado_demo,
    es_consulta_compuesta,
    es_primer_contacto,
    extraer_texto_cliente,
)
from fraseya.aplicacion.recomendaciones_ia import Sugerencia
from fraseya.infraestructura import lector_chat
from fraseya.infraestructura.lector_chat import (
    MAX_CUERPO_PUENTE,
    ORIGEN_WHATSAPP_WEB,
    LectorChat,
    PuenteWhatsAppWeb,
    VentanaChat,
    _IID_IUIAUTOMATION_TEXT_PATTERN,
    _NodoUIA,
    _UIA_CTRL_EDIT,
    _UIA_CTRL_LIST_ITEM,
    _UIA_CTRL_TEXT,
    _UIA_PATTERN_TEXT,
    _extraer_lista_ultimos_mensajes,
    _extraer_mensajes_de_texto_plano,
    _extraer_nodos_chat,
    _extraer_ultimos_mensajes,
    _filtrar_y_recortar_nodos,
    _seleccionar_caja_mensaje,
    es_ventana_whatsapp,
)


def _frases_catalogo():
    return [
        {
            'id': 1,
            'titulo': 'Disculpa demora',
            'abreviatura': '!demora',
            'categoria': 'Envíos',
            'origen': 'compartida',
            'favorita': True,
            'contenido': 'Lamentamos la demora con tu pedido; ya revisamos su estado.',
        },
        {
            'id': 2,
            'titulo': 'Estado envío',
            'abreviatura': '!envio',
            'categoria': 'Envíos',
            'origen': 'compartida',
            'favorita': False,
            'contenido': 'Tu pedido se encuentra en reparto y llegará hoy.',
        },
        {
            'id': 3,
            'titulo': 'Escalar logística',
            'abreviatura': '!escalar',
            'categoria': 'Soporte',
            'origen': 'propia',
            'favorita': False,
            'contenido': 'Derivamos tu caso con prioridad al equipo de logística.',
        },
    ]


def _sugerencias_tres(frases):
    return [
        Sugerencia(frases[0], 'Responde con empatía a la molestia.'),
        Sugerencia(frases[1], 'Entrega estado directo del despacho.'),
        Sugerencia(frases[2], 'Escala el incidente a logística.'),
    ]


# ---- Lista blanca de ventanas WhatsApp --------------------------------------

@pytest.mark.parametrize('titulo', [
    'WhatsApp',
    '(3) WhatsApp',
    '(99+) WhatsApp',
    'WhatsApp Beta',
    'WhatsApp Business',
    'WhatsApp Web',
    '(2) WhatsApp Web',
    'WhatsApp - Google Chrome',
    '(5) WhatsApp - Google Chrome',
    'WhatsApp Web - Google Chrome',
    'WhatsApp - Perfil 1 - Google Chrome',
    'WhatsApp - Microsoft Edge',
    '(1) WhatsApp - Personal - Microsoft\u200b Edge',
    'WhatsApp y 3 páginas más - Personal - Microsoft Edge',
    'WhatsApp — Mozilla Firefox',
    'WhatsApp - Opera',
    'WhatsApp - Opera GX',
    'WhatsApp - Brave',
])
def test_es_ventana_whatsapp_acepta_validas(titulo):
    assert es_ventana_whatsapp(titulo) is True


@pytest.mark.parametrize('titulo', [
    '',
    '   ',
    None,
    'FraseYa',
    'FraseYa - WhatsApp',
    'WhatsApp - FraseYa',
    'WhatsApp Web - FraseYa - Google Chrome',
    'Documento1 - Word',
    'WhatsApp.docx - Microsoft Word',
    'WhatsApp - Microsoft Word',
    'Recibidos - Gmail - Google Chrome',
    'WhatsApp - Gmail - Google Chrome',
    'WhatsApp - usuario@gmail.com - Gmail - Google Chrome',
    'BancoEstado - Google Chrome',
    'Banco de Chile - Microsoft Edge',
    'WhatsApp - BancoEstado - Google Chrome',
    'WhatsApp - Google Search - Google Chrome',
    '1Password',
    'Bitwarden - Google Chrome',
    'WhatsApp - Visual Studio Code',
])
def test_es_ventana_whatsapp_rechaza_otras_apps(titulo):
    assert es_ventana_whatsapp(titulo) is False


def test_lector_chat_detecta_tipo_desktop_y_web_y_degrada_seguro(monkeypatch):
    lector = LectorChat()

    # Fuera de Windows siempre devuelve None sin lanzar excepciones.
    monkeypatch.setattr(lector_chat.sys, 'platform', 'linux')
    assert lector.ventana_whatsapp_activa() is None
    assert lector.rect_ventana(1234) is None
    assert lector.leer_ultimo_mensaje(VentanaChat(1234, 'WhatsApp', (0, 0, 800, 600), 'desktop')) is None

    # Simulación en Windows para desktop y web.
    monkeypatch.setattr(lector_chat.sys, 'platform', 'win32')
    titulos = ['(2) WhatsApp', 'WhatsApp - Google Chrome', 'BancoEstado - Google Chrome']

    class _FakeUser32:
        def __init__(self, titulo):
            self._titulo = titulo

        def GetForegroundWindow(self):
            return 4242

        def GetWindowTextLengthW(self, hwnd):
            return len(self._titulo)

        def GetWindowTextW(self, hwnd, buf, largo):
            buf.value = self._titulo
            return len(self._titulo)

    monkeypatch.setattr(lector, 'rect_ventana', lambda hwnd: (10, 20, 900, 700))

    monkeypatch.setattr(lector_chat, '_user32', lambda: _FakeUser32(titulos[0]))
    v_desktop = lector.ventana_whatsapp_activa()
    assert v_desktop == VentanaChat(4242, '(2) WhatsApp', (10, 20, 900, 700), 'desktop')

    monkeypatch.setattr(lector_chat, '_user32', lambda: _FakeUser32(titulos[1]))
    v_web = lector.ventana_whatsapp_activa()
    assert v_web == VentanaChat(4242, 'WhatsApp - Google Chrome', (10, 20, 900, 700), 'web')

    monkeypatch.setattr(lector_chat, '_user32', lambda: _FakeUser32(titulos[2]))
    assert lector.ventana_whatsapp_activa() is None

    # Nunca intenta leer una ventana fuera de lista blanca aunque se pase manual.
    assert lector.leer_ultimo_mensaje(VentanaChat(4242, 'FraseYa', (0, 0, 500, 500), 'desktop')) is None

    # Si UIA falla inesperadamente, devuelve None sin lanzar.
    monkeypatch.setattr(lector_chat, '_LectorUIA', lambda: (_ for _ in ()).throw(RuntimeError('fallo uia')))
    assert lector.leer_ultimo_mensaje(v_desktop) is None


def test_extraer_ultimos_mensajes_filtra_sidebar_header_horas_y_salientes():
    # Ventana simulada de WhatsApp Desktop 1280x720 (sidebar ~0..435, chat ~435..1280)
    rect_ventana = (0, 0, 1280, 720)
    nodos = [
        # Barra lateral izquierda (debe ignorarse)
        _NodoUIA('Chats', _UIA_CTRL_TEXT, (20, 70, 90, 92)),
        _NodoUIA('Cliente Antiguo', _UIA_CTRL_TEXT, (60, 160, 220, 182)),
        _NodoUIA('Mensaje viejo en barra lateral', _UIA_CTRL_TEXT, (60, 185, 340, 205)),
        # Encabezado del chat activo (debe ignorarse)
        _NodoUIA('Cliente Sushi', _UIA_CTRL_TEXT, (490, 52, 640, 74)),
        _NodoUIA('en línea', _UIA_CTRL_TEXT, (490, 76, 560, 92)),
        # Separador de fecha centrado y aviso de cifrado
        _NodoUIA('Hoy', _UIA_CTRL_TEXT, (830, 140, 880, 160)),
        _NodoUIA('Los mensajes y las llamadas están cifrados de extremo a extremo.', _UIA_CTRL_TEXT, (640, 170, 1080, 195)),
        # Mensaje saliente previo (alineado a la derecha del panel de chat)
        _NodoUIA('¡Hola! ¿En qué te ayudo?', _UIA_CTRL_TEXT, (1010, 240, 1230, 265)),
        _NodoUIA('9:35 p. m.', _UIA_CTRL_TEXT, (1170, 268, 1230, 282)),
        # Dos mensajes entrantes consecutivos del cliente (alineados a la izquierda del panel de chat)
        _NodoUIA('Hola', _UIA_CTRL_TEXT, (480, 320, 530, 342)),
        _NodoUIA('9:39 p. m.', _UIA_CTRL_TEXT, (535, 330, 595, 344)),
        _NodoUIA('Quiero comprar sushi', _UIA_CTRL_TEXT, (480, 370, 680, 394)),
        _NodoUIA('9:39 p. m.', _UIA_CTRL_TEXT, (685, 382, 745, 396)),
        # Compositor inferior y campo contraseña (deben ignorarse)
        _NodoUIA('Escribe un mensaje', _UIA_CTRL_TEXT, (500, 675, 680, 700)),
        _NodoUIA('secreto123', _UIA_CTRL_TEXT, (480, 420, 600, 440), es_contrasena=True),
        _NodoUIA('texto en edit', _UIA_CTRL_EDIT, (480, 450, 620, 470)),
    ]
    assert _extraer_ultimos_mensajes(nodos, rect_ventana, modo_area='ventana') == 'Hola\nQuiero comprar sushi'

    # Si luego el agente responde (mensaje saliente al final), devuelve None
    nodos_respondido = [
        *nodos,
        _NodoUIA('¡Claro! Te comparto nuestra carta de rolls.', _UIA_CTRL_TEXT, (920, 440, 1235, 466)),
        _NodoUIA('9:40 p. m.', _UIA_CTRL_TEXT, (1175, 468, 1235, 482)),
    ]
    assert _extraer_ultimos_mensajes(nodos_respondido, rect_ventana, modo_area='ventana') is None


def test_extraer_ultimos_mensajes_uwp_listitem_y_dedup_con_text():
    rect_lista = (420, 100, 1260, 640)
    # Caso UWP donde ListItem envuelve al Text hijo sin duplicarlo
    nodos = [
        _NodoUIA('Tú: Ya te envío el catálogo, 9:30 p. m., Leído', _UIA_CTRL_LIST_ITEM, (425, 200, 1255, 250)),
        _NodoUIA('Ya te envío el catálogo', _UIA_CTRL_TEXT, (480, 210, 760, 232)),
        _NodoUIA('Quiero comprar sushi, 9:39 p. m.', _UIA_CTRL_LIST_ITEM, (425, 300, 1255, 355)),
        _NodoUIA('Quiero comprar sushi', _UIA_CTRL_TEXT, (470, 312, 690, 336)),
        _NodoUIA('9:39 p. m.', _UIA_CTRL_TEXT, (695, 326, 755, 342)),
    ]
    assert _extraer_ultimos_mensajes(nodos, rect_lista, modo_area='mensajes') == 'Quiero comprar sushi'

    # Caso ListItem sin hijos Text (fallback de accesibilidad)
    nodos_solo_item = [
        _NodoUIA('¿Tienen despacho a domicilio?, 9:41 p. m.', _UIA_CTRL_LIST_ITEM, (425, 380, 1255, 430)),
    ]
    assert _extraer_ultimos_mensajes(nodos_solo_item, rect_lista, modo_area='mensajes') == '¿Tienen despacho a domicilio?'


# ---- Puente HTTP local 127.0.0.1 --------------------------------------------

def _peticion(puerto, metodo, ruta, cuerpo=None, cabeceras=None):
    conn = http.client.HTTPConnection('127.0.0.1', puerto, timeout=3)
    try:
        conn.request(metodo, ruta, body=cuerpo, headers=cabeceras or {})
        resp = conn.getresponse()
        datos = resp.read()
        return resp.status, dict(resp.getheaders()), datos
    finally:
        conn.close()


def test_puente_whatsapp_web_rechaza_host_no_local():
    with pytest.raises(ValueError):
        PuenteWhatsAppWeb(lambda *_: None, puerto=0, host='0.0.0.0')


def test_puente_whatsapp_web_seguridad_y_flujo():
    recibidos = []
    evento = threading.Event()

    def al_mensaje(texto, meta):
        recibidos.append((texto, meta))
        evento.set()

    puente = PuenteWhatsAppWeb(al_mensaje, puerto=0)
    puente.iniciar()
    try:
        assert puente.puerto > 0

        # GET /estado -> 200 y CORS solo para web.whatsapp.com
        estado, hdrs, raw = _peticion(
            puente.puerto, 'GET', '/estado',
            cabeceras={'Origin': ORIGEN_WHATSAPP_WEB},
        )
        assert estado == 200
        assert json.loads(raw.decode('utf-8')) == {'ok': True, 'app': 'FraseYa'}
        assert hdrs.get('Access-Control-Allow-Origin') == ORIGEN_WHATSAPP_WEB

        estado_mal, hdrs_mal, _ = _peticion(
            puente.puerto, 'GET', '/estado',
            cabeceras={'Origin': 'https://evil.test'},
        )
        assert estado_mal == 200
        assert 'Access-Control-Allow-Origin' not in hdrs_mal

        # OPTIONS /mensaje -> 204 permitido solo a web.whatsapp.com, 403 al resto
        st_opt_ok, hdrs_opt, _ = _peticion(
            puente.puerto, 'OPTIONS', '/mensaje',
            cabeceras={'Origin': ORIGEN_WHATSAPP_WEB},
        )
        assert st_opt_ok == 204
        assert hdrs_opt.get('Access-Control-Allow-Origin') == ORIGEN_WHATSAPP_WEB
        assert hdrs_opt.get('Access-Control-Allow-Private-Network') == 'true'

        st_opt_bad, hdrs_opt_bad, _ = _peticion(
            puente.puerto, 'OPTIONS', '/mensaje',
            cabeceras={'Origin': 'https://evil.test'},
        )
        assert st_opt_bad == 403
        assert 'Access-Control-Allow-Origin' not in hdrs_opt_bad

        # POST /mensaje con origen legítimo
        payload = json.dumps({
            'texto': 'Hola, necesito ayuda con mi pedido',
            'chat': 'Cliente Ana',
            'remitente': 'Ana',
        }).encode('utf-8')
        st_ok, hdrs_ok, raw_ok = _peticion(
            puente.puerto, 'POST', '/mensaje',
            cuerpo=payload,
            cabeceras={
                'Origin': ORIGEN_WHATSAPP_WEB,
                'Content-Type': 'application/json',
            },
        )
        assert st_ok == 200
        assert json.loads(raw_ok.decode('utf-8')) == {'ok': True}
        assert hdrs_ok.get('Access-Control-Allow-Origin') == ORIGEN_WHATSAPP_WEB
        assert evento.wait(timeout=2.0)
        assert recibidos[-1] == (
            'Hola, necesito ayuda con mi pedido',
            {'chat': 'Cliente Ana', 'remitente': 'Ana', 'origen': 'web'},
        )

        # POST /mensaje con Origin malicioso -> 403
        cuenta_previa = len(recibidos)
        st_evil, _, _ = _peticion(
            puente.puerto, 'POST', '/mensaje',
            cuerpo=payload,
            cabeceras={'Origin': 'https://evil.test', 'Content-Type': 'application/json'},
        )
        assert st_evil == 403
        assert len(recibidos) == cuenta_previa

        # POST /mensaje sin Origin y sin X-FraseYa-Local -> 403 (anti-CSRF)
        st_sin_origin, _, _ = _peticion(
            puente.puerto, 'POST', '/mensaje',
            cuerpo=payload,
            cabeceras={'Content-Type': 'application/json'},
        )
        assert st_sin_origin == 403
        assert len(recibidos) == cuenta_previa

        # POST /mensaje sin Origin pero con X-FraseYa-Local: 1 -> 200
        st_local, _, _ = _peticion(
            puente.puerto, 'POST', '/mensaje',
            cuerpo=json.dumps({'texto': 'Mensaje local'}).encode('utf-8'),
            cabeceras={'X-FraseYa-Local': '1', 'Content-Type': 'application/json'},
        )
        assert st_local == 200
        assert len(recibidos) == cuenta_previa + 1

        # POST /mensaje con payload > 8KB -> 413
        grande = json.dumps({'texto': 'x' * (MAX_CUERPO_PUENTE + 100)}).encode('utf-8')
        assert len(grande) > MAX_CUERPO_PUENTE
        st_grande, _, _ = _peticion(
            puente.puerto, 'POST', '/mensaje',
            cuerpo=grande,
            cabeceras={'Origin': ORIGEN_WHATSAPP_WEB, 'Content-Type': 'application/json'},
        )
        assert st_grande == 413

        # POST /mensaje con texto > 4000 chars (cuerpo < 8KB) -> 400
        largo = json.dumps({'texto': 'a' * 4001}).encode('utf-8')
        assert len(largo) <= MAX_CUERPO_PUENTE
        st_largo, _, _ = _peticion(
            puente.puerto, 'POST', '/mensaje',
            cuerpo=largo,
            cabeceras={'Origin': ORIGEN_WHATSAPP_WEB, 'Content-Type': 'application/json'},
        )
        assert st_largo == 400

        # POST /mensaje con texto vacío -> 400
        st_vacio, _, _ = _peticion(
            puente.puerto, 'POST', '/mensaje',
            cuerpo=json.dumps({'texto': '   '}).encode('utf-8'),
            cabeceras={'Origin': ORIGEN_WHATSAPP_WEB, 'Content-Type': 'application/json'},
        )
        assert st_vacio == 400
    finally:
        puente.detener()


# ---- Clasificación heurística de contexto -----------------------------------

def test_clasificar_contexto_espanol():
    assert clasificar_contexto('Mi pedido #4821 lleva días de retraso y lo necesito urgente para hoy') == (
        'Pedido / Envío', 'Apurado', 'Alta',
    )
    assert clasificar_contexto('ES UNA ESTAFA!! ME COBRARON DOBLE EN LA TARJETA Y NADIE RESPONDE!!') == (
        'Facturación / Cobro', 'Molesto', 'Alta',
    )
    assert clasificar_contexto('Me sale un error al ingresar a mi cuenta en el sistema') == (
        'Soporte técnico', 'Neutral', 'Media',
    )
    assert clasificar_contexto('Muchas gracias, excelente servicio!') == (
        'Consulta general', 'Positivo', 'Normal',
    )
    assert clasificar_contexto('Hola, ¿cuál es su horario los sábados?') == (
        'Consulta general', 'Neutral', 'Normal',
    )
    assert clasificar_contexto('') == ('Consulta general', 'Neutral', 'Normal')


# ---- ServicioAsistenteVivo --------------------------------------------------

def test_servicio_inicia_pausado_y_agrupa_rafagas_y_deduplica():
    frases = _frases_catalogo()
    recomendador = Mock()
    recomendador.sugerir.return_value = _sugerencias_tres(frases)

    resultados = []
    errores = []
    listo = threading.Event()

    def al_resultado(res):
        resultados.append(res)
        listo.set()

    servicio = ServicioAsistenteVivo(
        recomendador=recomendador,
        obtener_frases=lambda: frases,
        al_resultado=al_resultado,
        al_error=errores.append,
        debounce_seg=0.12,
    )
    try:
        # Opt-in por defecto: inicia pausado e ignora mensajes.
        assert servicio.activo is False
        assert servicio.recibir_mensaje('Hola, ¿dónde está mi pedido?', chat='Cliente 1') is False
        time.sleep(0.18)
        recomendador.sugerir.assert_not_called()
        assert resultados == []

        # Al activar, agrupa ráfagas cortas y deduplica repetidos dentro de la ráfaga.
        servicio.activar()
        assert servicio.activo is True
        servicio.recibir_mensaje('Hola', chat='Cliente 1')
        servicio.recibir_mensaje('Mi pedido #123 no llega', chat='Cliente 1')
        servicio.recibir_mensaje('Mi pedido #123 no llega', chat='Cliente 1')  # duplicado en ráfaga

        assert listo.wait(timeout=2.0)
        assert recomendador.sugerir.call_count == 1
        texto_enviado, frases_enviadas = recomendador.sugerir.call_args.args
        assert texto_enviado == 'Hola\nMi pedido #123 no llega'
        assert frases_enviadas == frases

        assert len(resultados) == 1
        res = resultados[0]
        assert isinstance(res, ResultadoVivo)
        assert res.tema == 'Pedido / Envío'
        assert res.mensaje_origen == 'Hola\nMi pedido #123 no llega'
        assert len(res.opciones) == 3
        assert [o.indice for o in res.opciones] == [1, 2, 3]
        assert [o.tono for o in res.opciones] == ['empatica', 'directa', 'escalar']
        assert res.opciones[0].etiqueta == 'Opción 1 · Empática'
        assert res.opciones[1].etiqueta == 'Opción 2 · Directa'
        assert res.opciones[2].etiqueta == 'Opción 3 · Escalar'
        assert all(isinstance(o, OpcionFlotante) for o in res.opciones)
        assert errores == []

        # Deduplicación posterior: repetir el mismo mensaje en el mismo chat se ignora.
        listo.clear()
        assert servicio.recibir_mensaje('Mi pedido #123 no llega', chat='Cliente 1') is False
        assert servicio.recibir_mensaje('Hola\nMi pedido #123 no llega', chat='Cliente 1') is False
        time.sleep(0.18)
        assert recomendador.sugerir.call_count == 1

        # En OTRO chat el mismo texto sí se procesa.
        assert servicio.recibir_mensaje('Mi pedido #123 no llega', chat='Cliente 2') is True
        assert listo.wait(timeout=2.0)
        assert recomendador.sugerir.call_count == 2
    finally:
        servicio.detener()


def test_servicio_pausar_cancela_pendientes_y_lista_vacia_reporta_error():
    frases = _frases_catalogo()
    recomendador = Mock()
    recomendador.sugerir.return_value = []

    resultados = []
    errores = []
    err_ev = threading.Event()

    def al_error(msg):
        errores.append(msg)
        err_ev.set()

    servicio = ServicioAsistenteVivo(
        recomendador=recomendador,
        obtener_frases=lambda: frases,
        al_resultado=resultados.append,
        al_error=al_error,
        debounce_seg=0.15,
    )
    try:
        servicio.activar()
        servicio.recibir_mensaje('Mensaje que se cancela al pausar', chat='A')
        servicio.pausar()
        assert servicio.activo is False
        time.sleep(0.22)
        recomendador.sugerir.assert_not_called()

        # Cuando sugerir devuelve [] y generar no entrega borrador, reporta error claro.
        servicio.activar()
        servicio.recibir_mensaje('Consulta sin coincidencia', chat='B', inmediato=True)
        assert err_ev.wait(timeout=2.0)
        assert resultados == []
        assert len(errores) == 1
        assert 'frases aprobadas' in errores[0].casefold()
    finally:
        servicio.detener()


def test_servicio_fallback_generar_sin_guardar_en_sqlite_y_callback_analizando():
    frases = _frases_catalogo()
    recomendador = Mock()
    recomendador.sugerir.return_value = []
    recomendador.generar.return_value = {
        'titulo': 'Consulta sushi',
        'categoria': 'General',
        'contenido': '¡Hola! Con gusto te ayudamos con tu pedido de sushi. ¿Qué rolls te gustaría ordenar?',
    }

    analizados = []
    resultados = []
    errores = []
    listo = threading.Event()

    def al_resultado(res):
        resultados.append(res)
        listo.set()

    servicio = ServicioAsistenteVivo(
        recomendador=recomendador,
        obtener_frases=lambda: frases,
        al_resultado=al_resultado,
        al_error=errores.append,
        al_analizar=analizados.append,
        debounce_seg=0.0,
    )
    try:
        servicio.activar()
        servicio.recibir_mensaje('Hola\nQuiero comprar sushi', chat='Cliente Sushi', inmediato=True)
        assert listo.wait(timeout=2.0)

        assert analizados == ['Hola\nQuiero comprar sushi']
        assert errores == []
        recomendador.sugerir.assert_called_once_with('Hola\nQuiero comprar sushi', frases)
        recomendador.generar.assert_called_once_with('Hola\nQuiero comprar sushi', frases)

        assert len(resultados) == 1
        res = resultados[0]
        assert len(res.opciones) == 3
        assert [o.indice for o in res.opciones] == [1, 2, 3]
        assert [o.tono for o in res.opciones] == ['empatica', 'directa', 'escalar']
        for op in res.opciones:
            assert 'Propuesta IA · Revisar' in op.etiqueta
            assert op.frase['origen'] == 'borrador_ia'
            assert 'sushi' in op.frase['contenido'].casefold()
            assert 'borrador generado por ia' in op.motivo.casefold()
        # Las 3 variantes tienen textos diferenciados
        assert len({o.frase['contenido'] for o in res.opciones}) == 3
        # Nunca modifica ni agrega el borrador al catálogo original
        assert len(frases) == 3
    finally:
        servicio.detener()


def test_servicio_fallback_generar_falla_reporta_error_claro():
    frases = _frases_catalogo()
    recomendador = Mock()
    recomendador.sugerir.return_value = []
    recomendador.generar.side_effect = RuntimeError('cuota agotada')

    resultados = []
    errores = []
    err_ev = threading.Event()

    def al_error(msg):
        errores.append(msg)
        err_ev.set()

    servicio = ServicioAsistenteVivo(
        recomendador=recomendador,
        obtener_frases=lambda: frases,
        al_resultado=resultados.append,
        al_error=al_error,
        debounce_seg=0.0,
    )
    try:
        servicio.activar()
        servicio.recibir_mensaje('Quiero comprar sushi', chat='Cliente Sushi', inmediato=True)
        assert err_ev.wait(timeout=2.0)
        assert resultados == []
        assert len(errores) == 1
        assert 'sin coincidencias en el catálogo' in errores[0].casefold()
    finally:
        servicio.detener()


def test_analizar_manual_funciona_inmediato_incluso_pausado():
    frases = _frases_catalogo()
    recomendador = Mock()
    recomendador.sugerir.return_value = _sugerencias_tres(frases)[:2]

    resultados = []
    errores = []
    listo = threading.Event()

    def al_resultado(res):
        resultados.append(res)
        listo.set()

    # debounce_seg alto para comprobar que analizar_manual NO espera debounce.
    servicio = ServicioAsistenteVivo(
        recomendador=recomendador,
        obtener_frases=lambda: frases,
        al_resultado=al_resultado,
        al_error=errores.append,
        debounce_seg=10.0,
    )
    try:
        assert servicio.activo is False

        # Validación de longitud vacía o > 4000 chars reporta error sin consultar IA.
        servicio.analizar_manual('   ')
        servicio.analizar_manual('x' * 4001)
        assert len(errores) == 2
        recomendador.sugerir.assert_not_called()

        # Análisis manual válido corre inmediato sin activar modo continuo y garantiza 3 opciones.
        inicio = time.monotonic()
        servicio.analizar_manual('¿Cuándo llega mi pedido urgente?')
        assert listo.wait(timeout=2.0)
        assert (time.monotonic() - inicio) < 2.0
        assert len(resultados) == 1
        assert len(resultados[0].opciones) == 3
        assert [o.tono for o in resultados[0].opciones] == ['empatica', 'directa', 'escalar']
    finally:
        servicio.detener()


def test_bufer_mensajes_en_memoria_sin_llamar_ia_y_analizar_mensajes_garantiza_3():
    frases = _frases_catalogo()
    recomendador = Mock()
    recomendador.sugerir.return_value = []
    recomendador.generar.return_value = {
        'titulo': 'Pedido de sushi',
        'categoria': 'General',
        'contenido': '¡Hola! Claro, podemos tomar tu pedido de sushi. ¿Qué rolls prefieres?',
    }

    resultados = []
    errores = []
    listo = threading.Event()

    def al_resultado(res):
        resultados.append(res)
        listo.set()

    servicio = ServicioAsistenteVivo(
        recomendador=recomendador,
        obtener_frases=lambda: frases,
        al_resultado=al_resultado,
        al_error=errores.append,
    )
    try:
        # Registrar mensajes entrantes en búfer NO dispara Gemini
        assert servicio.registrar_mensaje_entrante('Mensaje 1 viejo', chat='Ana') is True
        assert servicio.registrar_mensaje_entrante('Hola', chat='Ana') is True
        assert servicio.registrar_mensaje_entrante('Hola', chat='Ana') is True  # dedup consecutivo
        assert servicio.registrar_mensaje_entrante('Quiero comprar sushi', chat='Ana') is True
        assert servicio.registrar_mensaje_entrante('¿Tienen despacho hoy?', chat='Ana') is True

        ultimos = servicio.obtener_ultimos_mensajes(chat='Ana', limite=3)
        assert ultimos == ['Hola', 'Quiero comprar sushi', '¿Tienen despacho hoy?']
        assert servicio.obtener_ultimos_mensajes(limite=3) == ultimos
        recomendador.sugerir.assert_not_called()
        recomendador.generar.assert_not_called()

        # analizar_mensajes con 0 coincidencias en catálogo -> garantiza 3 OpcionFlotante con <= 2 llamadas IA
        servicio.analizar_mensajes(['Hola', 'Quiero comprar sushi'])
        assert listo.wait(timeout=2.0)
        assert errores == []
        assert recomendador.sugerir.call_count == 1
        assert recomendador.generar.call_count == 1
        assert (recomendador.sugerir.call_count + recomendador.generar.call_count) <= 2

        res = resultados[-1]
        assert len(res.opciones) == 3
        assert all(isinstance(o, OpcionFlotante) for o in res.opciones)
        assert [o.tono for o in res.opciones] == ['empatica', 'directa', 'escalar']
        assert all('Propuesta IA · Revisar' in o.etiqueta for o in res.opciones)
        assert all(o.frase['origen'] == 'borrador_ia' for o in res.opciones)
        assert len(frases) == 3  # sin escribir en SQLite ni mutar catálogo

        # Cuando sugerir devuelve 1 frase y catálogo tiene más -> garantiza 3 opciones con <= 2 llamadas
        listo.clear()
        recomendador.sugerir.reset_mock()
        recomendador.generar.reset_mock()
        recomendador.sugerir.return_value = _sugerencias_tres(frases)[:1]
        recomendador.generar.return_value = {
            'titulo': 'Alternativa IA',
            'categoria': 'Envíos',
            'contenido': 'Revisamos tu despacho ahora mismo y te confirmamos el horario.',
        }
        servicio.analizar_mensajes(['Mi pedido no llega'], asincrono=False)
        assert recomendador.sugerir.call_count == 1
        assert recomendador.generar.call_count == 1
        assert len(resultados[-1].opciones) == 3
        assert [o.tono for o in resultados[-1].opciones] == ['empatica', 'directa', 'escalar']

        # Error de cuota/límite -> entrega mensaje claro sin reintentos automáticos
        recomendador.sugerir.reset_mock()
        recomendador.generar.reset_mock()
        recomendador.sugerir.side_effect = ValueError('Demasiados intentos. Espera 15 segundos para volver a intentar.')
        servicio.analizar_mensajes(['Hola'], asincrono=False)
        assert recomendador.sugerir.call_count == 1
        assert recomendador.generar.call_count == 0
        assert len(errores) == 1
        assert 'Demasiados intentos' in errores[0]
    finally:
        servicio.detener()
        # Al detener se limpia el búfer en memoria
        assert servicio.obtener_ultimos_mensajes(limite=3) == []


def test_lector_ultimos_3_mensajes_y_enfocar_caja_mensaje(monkeypatch):
    rect_ventana = (0, 0, 1280, 720)
    nodos = [
        _NodoUIA('Hola', _UIA_CTRL_TEXT, (480, 260, 530, 282)),
        _NodoUIA('Quiero comprar sushi', _UIA_CTRL_TEXT, (480, 310, 680, 334)),
        _NodoUIA('¿Aceptan tarjeta?', _UIA_CTRL_TEXT, (480, 360, 650, 384)),
        _NodoUIA('Ya te confirmo en un momento', _UIA_CTRL_TEXT, (960, 420, 1230, 446)),
    ]
    # Bajo demanda (solo_sin_responder=False) recupera hasta los últimos 3 entrantes en orden cronológico
    lista = _extraer_lista_ultimos_mensajes(
        nodos, rect_ventana, modo_area='ventana', limite=3, solo_sin_responder=False
    )
    assert lista == ['Hola', 'Quiero comprar sushi', '¿Aceptan tarjeta?']

    # Selección de caja de escritura ignora buscador superior-izquierdo y elige compositor inferior-derecho
    candidatos = [
        (0, 'Buscar o empezar un chat nuevo', (40, 110, 360, 145)),
        (1, 'Escribe un mensaje', (480, 660, 1180, 700)),
    ]
    assert _seleccionar_caja_mensaje(candidatos, rect_ventana) == 1
    assert _seleccionar_caja_mensaje([(0, 'Buscar', (40, 110, 360, 145))], rect_ventana) is None

    lector = LectorChat()
    monkeypatch.setattr(lector_chat.sys, 'platform', 'linux')
    assert lector.leer_ultimos_mensajes(VentanaChat(10, 'WhatsApp', (0, 0, 800, 600), 'desktop')) == []
    assert lector.enfocar_caja_mensaje(10) is False

    monkeypatch.setattr(lector_chat.sys, 'platform', 'win32')
    fake_uia = Mock()
    fake_uia.leer_ultimos_textos.return_value = ['Hola', 'Quiero comprar sushi', '¿Tienen envío?']
    fake_uia.enfocar_caja_mensaje.return_value = True
    monkeypatch.setattr(lector_chat, '_LectorUIA', lambda: fake_uia)
    monkeypatch.setattr(lector, '_titulo_ventana', lambda hwnd: 'WhatsApp' if hwnd == 555 else 'FraseYa')

    win = VentanaChat(555, 'WhatsApp', (0, 0, 1280, 720), 'desktop')
    assert lector.leer_ultimos_mensajes(win, limite=3) == ['Hola', 'Quiero comprar sushi', '¿Tienen envío?']
    assert lector.leer_ultimo_mensaje(win) == 'Hola\nQuiero comprar sushi\n¿Tienen envío?'
    assert lector.enfocar_caja_mensaje(555) is True
    assert lector.enfocar_caja_mensaje(999) is False  # rechaza ventana fuera de lista blanca


def test_crear_resultado_demo_con_catalogo_y_vacio():
    frases = _frases_catalogo()
    demo = ServicioAsistenteVivo.crear_resultado_demo(frases)
    assert isinstance(demo, ResultadoVivo)
    assert len(demo.opciones) == 3
    assert demo.opciones[0].frase['contenido'] == frases[0]['contenido']
    assert [o.tono for o in demo.opciones] == ['empatica', 'directa', 'escalar']
    assert demo.tema and demo.animo and demo.urgencia

    demo_vacio = crear_resultado_demo([])
    assert isinstance(demo_vacio, ResultadoVivo)
    assert len(demo_vacio.opciones) == 3
    assert all(o.frase['contenido'].strip() for o in demo_vacio.opciones)


# ---- Validación del manifest de la extensión --------------------------------

def test_extension_wsp_manifest_minimos_privilegios():
    raiz = Path(__file__).resolve().parent.parent / 'extension_wsp'
    manifest = json.loads((raiz / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['manifest_version'] == 3
    assert manifest['name'] == 'FraseYa · Lector WhatsApp Web'
    assert manifest.get('permissions', []) == []
    assert manifest['host_permissions'] == ['http://127.0.0.1:47821/*']
    assert manifest['content_scripts'][0]['matches'] == ['https://web.whatsapp.com/*']
    assert manifest['content_scripts'][0]['js'] == ['content.js']
    assert (raiz / 'content.js').is_file()
    assert (raiz / 'README.md').is_file()


# ---- Lectura rápida WebView2: TextPattern, fallback IsOffscreen y vtables ----

def test_extraer_mensajes_de_texto_plano_whatsapp_desktop():
    texto_real = 'Hoy\nHola\n10:09 p. m.\nQuiero comprar sushi\n10:09 p. m.\nEscribe un mensaje'
    assert _extraer_mensajes_de_texto_plano(texto_real, limite=3) == ['Hola', 'Quiero comprar sushi']

    # Documento WebView2 completo con barra lateral, cifrado, mensaje saliente y objeto embebido \ufffc
    texto_completo = '\n'.join([
        'Chats',
        'Buscar o empezar un chat nuevo',
        'Todos',
        'No leídos',
        'Cliente Viejo',
        'Mensaje viejo en sidebar',
        'Cliente Sushi',
        'en línea',
        'Los mensajes y las llamadas están cifrados de extremo a extremo.',
        'Hoy',
        'Tú: ¡Hola! ¿Qué te gustaría pedir?',
        '10:05 p. m.',
        'Leído',
        '\ufffcHola',
        '10:09 p. m.',
        'Quiero comprar sushi',
        '10:09 p. m.',
        '¿Tienen despacho hoy?',
        '10:10 p. m.',
        'Escribe un mensaje',
        'Texto residual de overlay posterior',
    ])
    assert _extraer_mensajes_de_texto_plano(texto_completo, limite=3) == [
        'Hola',
        'Quiero comprar sushi',
        '¿Tienen despacho hoy?',
    ]

    # Si termina con mensaje saliente marcado con estado "Leído", devuelve los últimos entrantes
    texto_respondido = '\n'.join([
        'Hoy',
        'Hola',
        '10:09 p. m.',
        'Quiero comprar sushi',
        '10:09 p. m.',
        'Ya te envío la carta',
        '10:10 p. m.',
        'Leído',
        'Escribe un mensaje',
    ])
    assert _extraer_mensajes_de_texto_plano(texto_respondido, limite=3) == ['Hola', 'Quiero comprar sushi']


def test_fallback_is_offscreen_cuando_rect_cae_en_chat():
    rect_ventana = (0, 0, 1280, 720)
    nodos = [
        # Sidebar con IsOffscreen=True: nunca debe entrar aunque se active fallback
        _NodoUIA('Mensaje sidebar oculto', _UIA_CTRL_TEXT, (40, 200, 300, 224), fuera_pantalla=True),
        # Contraseña dentro del chat con IsOffscreen=True: nunca debe leerse
        _NodoUIA('clave_secreta', _UIA_CTRL_TEXT, (480, 280, 620, 304), es_contrasena=True, fuera_pantalla=True),
        # Nodo offscreen sin rect válido: no se admite en fallback
        _NodoUIA('Nodo sin geometría', _UIA_CTRL_TEXT, (0, 0, 0, 0), fuera_pantalla=True),
        # Mensajes reales del chat que WebView2 reportó con IsOffscreen=True pero rect visible dentro del chat
        _NodoUIA('Hola', _UIA_CTRL_TEXT, (480, 320, 540, 344), fuera_pantalla=True),
        _NodoUIA('Quiero comprar sushi', _UIA_CTRL_TEXT, (480, 370, 690, 394), fuera_pantalla=True),
    ]
    mensajes, uso_offscreen = _extraer_nodos_chat(
        nodos, rect_ventana, modo_area='ventana', limite=3, max_elementos=360
    )
    assert uso_offscreen is True
    assert mensajes == ['Hola', 'Quiero comprar sushi']


def test_filtrar_area_antes_de_recortar_max_elementos():
    rect_ventana = (0, 0, 1280, 720)
    nodos_chat = [
        _NodoUIA('Hola', _UIA_CTRL_TEXT, (480, 320, 540, 344)),
        _NodoUIA('Quiero comprar sushi', _UIA_CTRL_TEXT, (480, 370, 690, 394)),
    ]
    # 400 nodos posteriores en sidebar/overlays fuera del área del chat
    nodos_overlays = [
        _NodoUIA(f'Overlay {i}', _UIA_CTRL_TEXT, (20, 160 + (i % 40) * 10, 260, 178 + (i % 40) * 10))
        for i in range(400)
    ]
    todos = nodos_chat + nodos_overlays
    recortados = _filtrar_y_recortar_nodos(todos, rect_ventana, modo_area='ventana', max_elementos=10)
    assert len(recortados) == 2
    assert [n.texto for n in recortados] == ['Hola', 'Quiero comprar sushi']

    mensajes, uso_offscreen = _extraer_nodos_chat(
        todos, rect_ventana, modo_area='ventana', limite=3, max_elementos=10
    )
    assert uso_offscreen is False
    assert mensajes == ['Hola', 'Quiero comprar sushi']


def test_vtables_com_uiautomationcore_windows():
    import ctypes
    from ctypes import wintypes
    import sys
    import uuid

    if sys.platform != 'win32':
        pytest.skip('Solo aplicable en Windows')

    assert _UIA_PATTERN_TEXT == 10014

    oleaut32 = ctypes.WinDLL('oleaut32')
    oleaut32.LoadTypeLib.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p)]
    oleaut32.LoadTypeLib.restype = ctypes.c_long
    oleaut32.SysFreeString.argtypes = [ctypes.c_void_p]

    def vcall(obj, idx, restype, argtypes, *args):
        vtbl = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
        fn = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(vtbl[idx])
        return fn(obj, *args)

    def bstr_str(ptr):
        if not ptr or not ptr.value:
            return ''
        try:
            return ctypes.wstring_at(ptr.value)
        finally:
            oleaut32.SysFreeString(ptr)

    class _FUNCDESC(ctypes.Structure):
        _fields_ = [
            ('memid', ctypes.c_long),
            ('lprgscode', ctypes.c_void_p),
            ('lprgelemdescParam', ctypes.c_void_p),
            ('funckind', ctypes.c_int),
            ('invkind', ctypes.c_int),
            ('callconv', ctypes.c_int),
            ('cParams', ctypes.c_short),
            ('cParamsOpt', ctypes.c_short),
            ('oVft', ctypes.c_short),
            ('cScodes', ctypes.c_short),
        ]

    class _TYPEATTR(ctypes.Structure):
        _fields_ = [
            ('guid', ctypes.c_byte * 16),
            ('lcid', wintypes.DWORD),
            ('dwReserved', wintypes.DWORD),
            ('memidConstructor', ctypes.c_long),
            ('memidDestructor', ctypes.c_long),
            ('lpstrSchema', ctypes.c_void_p),
            ('cbSizeInstance', wintypes.DWORD),
            ('typekind', ctypes.c_int),
            ('cFuncs', ctypes.c_ushort),
            ('cVars', ctypes.c_ushort),
            ('cImplTypes', ctypes.c_ushort),
            ('cbSizeVft', ctypes.c_ushort),
            ('cbAlignment', ctypes.c_ushort),
            ('wTypeFlags', ctypes.c_ushort),
            ('wMajorVerNum', ctypes.c_ushort),
            ('wMinorVerNum', ctypes.c_ushort),
        ]

    esperados = {
        'IUIAutomation': {
            'ElementFromHandle': 6,
            'ElementFromPoint': 7,
            'ControlViewWalker': 14,
            'CreateCacheRequest': 20,
            'CreatePropertyCondition': 23,
            'CreateOrCondition': 28,
        },
        'IUIAutomationTreeWalker': {
            'GetParentElement': 3,
        },
        'IUIAutomationElement': {
            'SetFocus': 3,
            'FindFirst': 5,
            'FindAll': 6,
            'FindAllBuildCache': 8,
            'GetCurrentPatternAs': 14,
            'GetCurrentPattern': 16,
        },
        'IUIAutomationTextPattern': {
            'GetVisibleRanges': 6,
            'DocumentRange': 7,
        },
        'IUIAutomationTextRange': {
            'GetText': 12,
        },
    }

    tlib = ctypes.c_void_p()
    assert oleaut32.LoadTypeLib(r'C:\Windows\System32\UIAutomationCore.dll', ctypes.byref(tlib)) == 0
    ptr_size = ctypes.sizeof(ctypes.c_void_p)
    encontrados: dict[str, dict[str, int]] = {}
    guid_text_pattern = None
    try:
        total = vcall(tlib, 3, ctypes.c_uint, [])
        for i in range(total):
            bname = ctypes.c_void_p()
            vcall(
                tlib, 9, ctypes.c_long,
                [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p],
                i, ctypes.byref(bname), None, None, None,
            )
            iface = bstr_str(bname)
            if iface not in esperados:
                continue
            tinfo = ctypes.c_void_p()
            assert vcall(tlib, 4, ctypes.c_long, [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)], i, ctypes.byref(tinfo)) == 0
            pattr = ctypes.POINTER(_TYPEATTR)()
            assert vcall(tinfo, 3, ctypes.c_long, [ctypes.POINTER(ctypes.POINTER(_TYPEATTR))], ctypes.byref(pattr)) == 0
            try:
                if iface == 'IUIAutomationTextPattern':
                    guid_text_pattern = bytes(ctypes.cast(pattr.contents.guid, ctypes.POINTER(ctypes.c_ubyte * 16)).contents)
                slots: dict[str, int] = {}
                for fidx in range(pattr.contents.cFuncs):
                    pfd = ctypes.POINTER(_FUNCDESC)()
                    assert vcall(tinfo, 5, ctypes.c_long, [ctypes.c_uint, ctypes.POINTER(ctypes.POINTER(_FUNCDESC))], fidx, ctypes.byref(pfd)) == 0
                    try:
                        names = (ctypes.c_void_p * 4)()
                        c_names = ctypes.c_uint(0)
                        vcall(
                            tinfo, 7, ctypes.c_long,
                            [ctypes.c_long, ctypes.POINTER(ctypes.c_void_p), ctypes.c_uint, ctypes.POINTER(ctypes.c_uint)],
                            pfd.contents.memid, names, 4, ctypes.byref(c_names),
                        )
                        mname = bstr_str(ctypes.c_void_p(names[0]))
                        for k in range(1, c_names.value):
                            bstr_str(ctypes.c_void_p(names[k]))
                        slots[mname] = pfd.contents.oVft // ptr_size
                    finally:
                        vcall(tinfo, 20, None, [ctypes.POINTER(_FUNCDESC)], pfd)
                encontrados[iface] = slots
            finally:
                vcall(tinfo, 19, None, [ctypes.POINTER(_TYPEATTR)], pattr)
                vcall(tinfo, 2, ctypes.c_ulong, [])
    finally:
        vcall(tlib, 2, ctypes.c_ulong, [])

    for iface, mapa in esperados.items():
        assert iface in encontrados, f'Falta interfaz {iface}'
        for metodo, slot_esperado in mapa.items():
            assert encontrados[iface].get(metodo) == slot_esperado, (
                f'{iface}::{metodo} esperaba slot {slot_esperado}, obtuvo {encontrados[iface].get(metodo)}'
            )
    assert guid_text_pattern == _IID_IUIAUTOMATION_TEXT_PATTERN
    assert uuid.UUID(bytes_le=guid_text_pattern) == uuid.UUID('{32eba289-3583-42c9-9c59-3b6d9a1e9b6a}')


def test_asistente_vivo_genera_tres_opciones_aunque_catalogo_este_vacio():
    recomendador = Mock()
    recomendador.generar.return_value = {
        'titulo': 'Aclaración de servicios',
        'categoria': 'General',
        'contenido': 'Hola, nos dedicamos a automatización y software, por lo que no vendemos sushi.',
    }
    resultados = []
    errores = []
    servicio = ServicioAsistenteVivo(
        recomendador=recomendador,
        obtener_frases=lambda: [],
        al_resultado=resultados.append,
        al_error=errores.append,
    )
    try:
        res = servicio.analizar_mensajes(['Hola', 'Quiero comprar sushi'], asincrono=False)
        assert res is not None
        assert errores == []
        assert len(res.opciones) == 3
        recomendador.sugerir.assert_not_called()
        recomendador.generar.assert_called_once()
        assert len({op.frase['contenido'] for op in res.opciones}) == 3
    finally:
        servicio.detener()


def test_hilo_con_turnos_cliente_y_agente_evita_re_saludo():
    rect_ventana = (0, 0, 1280, 720)
    nodos = [
        _NodoUIA('Hola, quiero consultar por automatizaciones', _UIA_CTRL_TEXT, (480, 220, 760, 244)),
        _NodoUIA('Hola Yaimara, ¿en qué te podemos ayudar hoy en ConTech?', _UIA_CTRL_TEXT, (820, 280, 1230, 304)),
        _NodoUIA('Leído', _UIA_CTRL_TEXT, (1180, 306, 1230, 320)),
        _NodoUIA('Quiero cotizar la automatización de una página web', _UIA_CTRL_TEXT, (480, 350, 800, 374)),
    ]
    hilo = _extraer_lista_ultimos_mensajes(
        nodos, rect_ventana, modo_area='ventana', limite=6, incluir_salientes=True
    )
    assert hilo == [
        'Cliente: Hola, quiero consultar por automatizaciones',
        'Agente: Hola Yaimara, ¿en qué te podemos ayudar hoy en ConTech?',
        'Cliente: Quiero cotizar la automatización de una página web',
    ]

    # También funciona en el fallback TextPattern
    texto_doc = '\n'.join([
        'Hoy',
        'Hola, quiero consultar por automatizaciones',
        '10:01 p. m.',
        'Tú: Hola Yaimara, ¿en qué te podemos ayudar hoy en ConTech?',
        '10:03 p. m.',
        'Leído',
        'Quiero cotizar la automatización de una página web',
        '10:04 p. m.',
        'Escribe un mensaje',
    ])
    assert _extraer_mensajes_de_texto_plano(texto_doc, limite=6, incluir_salientes=True) == hilo

    # Helpers de contexto distinguen primer contacto vs conversación en curso
    texto_hilo = '\n'.join(hilo)
    assert es_primer_contacto(texto_hilo) is False
    assert es_primer_contacto('Cliente: Hola, quiero cotizar') is True
    assert extraer_texto_cliente(texto_hilo) == 'Quiero cotizar la automatización de una página web'

    # En conversación en curso, la variante empática NO antepone '¡Hola!'
    empatica_seguimiento = _variar_por_tono(
        '¿Qué proceso de tu página web necesitas automatizar?',
        'empatica',
        es_primer_contacto_chat=False,
    )
    assert not empatica_seguimiento.casefold().startswith(('hola', '¡hola'))
    assert 'Con gusto te ayudamos.' in empatica_seguimiento

    empatica_inicial = _variar_por_tono(
        '¿Qué proceso de tu página web necesitas automatizar?',
        'empatica',
        es_primer_contacto_chat=True,
    )
    assert empatica_inicial.startswith('¡Hola! ')

    # ServicioAsistenteVivo conserva turnos en memoria y usa contexto sin sesgo del agente
    recomendador = Mock()
    recomendador.sugerir.return_value = []
    recomendador.generar.return_value = {
        'titulo': 'Cotización automatización',
        'categoria': 'General',
        'contenido': '¿Qué proceso de tu página necesitas automatizar y qué herramientas usas hoy?',
    }
    resultados = []
    servicio = ServicioAsistenteVivo(
        recomendador=recomendador,
        obtener_frases=lambda: [],
        al_resultado=resultados.append,
        al_error=lambda _: None,
    )
    try:
        assert servicio.registrar_turno('Hola, quiero consultar por automatizaciones', rol='cliente', chat='Yaimara') is True
        assert servicio.registrar_turno('Hola Yaimara, ¿en qué te podemos ayudar hoy en ConTech?', rol='agente', chat='Yaimara') is True
        assert servicio.registrar_turno('Quiero cotizar la automatización de una página web', rol='cliente', chat='Yaimara') is True

        mensajes = servicio.obtener_ultimos_mensajes(chat='Yaimara', limite=6)
        assert mensajes == hilo

        res = servicio.analizar_mensajes(mensajes, asincrono=False)
        assert res is not None
        assert len(res.opciones) == 3
        for op in res.opciones:
            assert not op.frase['contenido'].casefold().startswith(('hola', '¡hola'))
        assert recomendador.generar.call_args.args[0] == texto_hilo
    finally:
        servicio.detener()


def test_puente_acepta_rol_y_turnos_opcionales_y_extension_observa_salientes():
    recibidos = []
    evento = threading.Event()
    puente = PuenteWhatsAppWeb(lambda t, m: (recibidos.append((t, m)), evento.set()), puerto=0)
    puente.iniciar()
    try:
        payload = json.dumps({
            'texto': 'Quiero cotizar la automatización',
            'chat': 'Yaimara',
            'remitente': 'Yaimara',
            'rol': 'cliente',
            'turnos': [
                {'rol': 'cliente', 'texto': 'Hola'},
                {'rol': 'agente', 'texto': 'Hola Yaimara, ¿en qué te ayudamos?'},
                {'rol': 'cliente', 'texto': 'Quiero cotizar la automatización'},
            ],
        }).encode('utf-8')
        st, _, _ = _peticion(
            puente.puerto,
            'POST',
            '/mensaje',
            cuerpo=payload,
            cabeceras={'Origin': ORIGEN_WHATSAPP_WEB, 'Content-Type': 'application/json'},
        )
        assert st == 200
        assert evento.wait(timeout=2.0)
        _, meta = recibidos[-1]
        assert meta['rol'] == 'cliente'
        assert len(meta['turnos']) == 3
    finally:
        puente.detener()

    js = (Path(__file__).resolve().parent.parent / 'extension_wsp' / 'content.js').read_text(encoding='utf-8')
    assert 'div.message-out' in js
    assert 'turnos' in js


def test_consulta_compuesta_genera_tres_tarjetas_coherentes_y_completar_no_cambia_tema():
    frases = _frases_catalogo() + [
        {
            'id': 99,
            'titulo': 'Dominio y Hosting',
            'abreviatura': '!dom',
            'categoria': 'Web',
            'origen': 'propia',
            'favorita': False,
            'contenido': 'El dominio cuesta $15.000 CLP/año y el hosting $65.000 CLP/año.',
        }
    ]
    recomendador = Mock()
    recomendador.sugerir.return_value = _sugerencias_tres(frases)[:1]
    recomendador.generar.return_value = {
        'titulo': 'Cotización integral web + hosting + chatbot',
        'categoria': 'General',
        'contenido': (
            'El Sitio Web Corporativo cuesta $450.000 CLP (10-15 días, incluye dominio y hosting 1 año, '
            'WebP y diseño responsive) y el Bot de WhatsApp + Agenda $380.000 CLP (7-10 días).'
        ),
    }

    servicio = ServicioAsistenteVivo(
        recomendador=recomendador,
        obtener_frases=lambda: frases,
        al_resultado=lambda _: None,
        al_error=lambda _: None,
    )
    try:
        # Consulta simple donde sugerir devuelve 1 item: la 3ª tarjeta deriva de la propuesta IA, no cambia de tema
        res_simple = servicio.analizar_mensajes(['Mi pedido tiene demora'], asincrono=False)
        assert res_simple is not None
        assert len(res_simple.opciones) == 3
        assert '15.000' not in res_simple.opciones[2].frase['contenido']
        assert '450.000' in res_simple.opciones[2].frase['contenido']

        # Consulta compuesta (web + hosting + chatbot): las 3 tarjetas salen unificadas desde generar()
        recomendador.sugerir.reset_mock()
        recomendador.generar.reset_mock()
        hilo_compuesto = [
            'Cliente: Quiero una página web con chatbot para veterinaria',
            'Agente: Hola Yaimara, ¿qué detalles técnicos necesitas?',
            'Cliente: 1. Dominio y hosting\n2. Velocidad WebP\n3. Diseño responsive y precio total',
        ]
        assert es_consulta_compuesta('\n'.join(hilo_compuesto)) is True
        assert es_consulta_compuesta('¿Cuál es su horario?') is False

        res_comp = servicio.analizar_mensajes(hilo_compuesto, asincrono=False)
        assert res_comp is not None
        recomendador.sugerir.assert_not_called()
        recomendador.generar.assert_called_once()
        assert len(res_comp.opciones) == 3
        for op in res_comp.opciones:
            assert '450.000' in op.frase['contenido']
            assert '380.000' in op.frase['contenido']
    finally:
        servicio.detener()


def test_mensaje_largo_multiparrafo_conserva_turno_agente_previo():
    rect_ventana = (0, 0, 1280, 720)
    nodos = [
        _NodoUIA('Hola, quiero cotizar una página web para veterinaria', _UIA_CTRL_TEXT, (480, 140, 820, 164)),
        _NodoUIA('Hola Yaimara, ¿podrías indicarnos los detalles?', _UIA_CTRL_TEXT, (860, 190, 1230, 214)),
        _NodoUIA('Estoy cotizando el desarrollo web para mi clínica:', _UIA_CTRL_TEXT, (480, 250, 840, 274)),
        _NodoUIA('1. Dominio y hosting propios', _UIA_CTRL_TEXT, (480, 290, 760, 314)),
        _NodoUIA('2. Velocidad menor a 2,5 segundos y WebP', _UIA_CTRL_TEXT, (480, 330, 820, 354)),
        _NodoUIA('3. Diseño responsive mobile-first', _UIA_CTRL_TEXT, (480, 370, 790, 394)),
        _NodoUIA('4. Integración de chatbot para agenda', _UIA_CTRL_TEXT, (480, 410, 800, 434)),
        _NodoUIA('Quedo atento a costos y plazos.', _UIA_CTRL_TEXT, (480, 450, 760, 474)),
    ]
    hilo = _extraer_lista_ultimos_mensajes(
        nodos, rect_ventana, modo_area='ventana', limite=3, incluir_salientes=True
    )
    assert len(hilo) == 3
    assert hilo[0] == 'Cliente: Hola, quiero cotizar una página web para veterinaria'
    assert hilo[1] == 'Agente: Hola Yaimara, ¿podrías indicarnos los detalles?'
    assert hilo[2].startswith('Cliente: Estoy cotizando el desarrollo web para mi clínica:\n1. Dominio y hosting propios')
    assert 'Quedo atento a costos y plazos.' in hilo[2]
    assert es_primer_contacto('\n'.join(hilo)) is False

    # Empática NO antepone '¡Hola! ' porque el turno Agente quedó conservado
    emp = _variar_por_tono('Gestionamos el dominio y hosting.', 'empatica', es_primer_contacto_chat=False)
    assert not emp.startswith('¡Hola!')


def test_enfocar_caja_mensaje_recurre_a_clic_seguro_si_uia_no_expone_edit(monkeypatch):
    lector_uia = lector_chat._LectorUIA()
    monkeypatch.setattr(lector_uia._ole32, 'CoInitializeEx', lambda *_: 0)
    monkeypatch.setattr(lector_uia._ole32, 'CoUninitialize', lambda: None)
    monkeypatch.setattr(lector_uia._ole32, 'CoCreateInstance', lambda *_: -2147467259)
    llamadas = []
    monkeypatch.setattr(
        lector_chat,
        '_clic_seguro_en_caja',
        lambda hwnd, rc=None: (llamadas.append((hwnd, rc)), True)[1],
    )
    assert lector_uia.enfocar_caja_mensaje(12345) is True
    assert llamadas == [(12345, None)]
