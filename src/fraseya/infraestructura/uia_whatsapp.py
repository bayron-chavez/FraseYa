"""Lectura y enfoque seguro de ventanas de WhatsApp vía UI Automation (solo Windows).

Privacidad estricta (Ley 19.628 / 21.719):
- Lista blanca estricta: solo observa ventanas de WhatsApp Desktop o pestañas
  de WhatsApp Web en navegadores conocidos, excluyendo siempre a FraseYa.
- Nunca persiste conversaciones ni fragmentos de chat en SQLite ni en disco;
  toda lectura vive exclusivamente en memoria durante la consulta.
- Nunca envía mensajes automáticamente ni lee campos de contraseña.
"""
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import os
import re
import sys
import time
import uuid

from .puente_wsp import MAX_LARGO_MENSAJE
from .win32_com import (
    INPUT,
    KEYBDINPUT,
    MOUSEINPUT,
    VARIANT,
    hwnd_render_chat,
    info_punto_win32,
    pid_ventana,
    rect_hwnd_win32,
    user32,
)

_INVISIBLES = re.compile(r'[\u200b\u200c\u200d\ufeff\ufffc]')
_SEPARADORES_TITULO = re.compile(r'\s+[-–—|]\s+')
_SUFIJO_PAGINAS_EDGE = re.compile(
    r'\s+(?:y|and)\s+\d+\s+(?:p[aá]ginas?\s+m[aá]s|more\s+pages?)$',
    re.IGNORECASE,
)
_PREFIJO_WHATSAPP = re.compile(
    r'^(?:\(\d+\+?\)\s*)?whatsapp(?:\s+(?:web|beta|business|desktop))?$',
    re.IGNORECASE,
)
_NAVEGADORES = frozenset({
    'google chrome', 'chrome',
    'microsoft edge', 'edge',
    'mozilla firefox', 'firefox',
    'opera', 'opera gx',
    'brave', 'brave browser',
    'chromium', 'vivaldi',
})
_CLAVES_WEB = ('whatsapp web', 'chrome', 'edge', 'firefox', 'opera', 'brave', 'chromium', 'vivaldi')
_TERCER_SEGMENTO_PROHIBIDO = (
    'gmail', 'outlook', 'hotmail', 'yahoo', 'correo', 'mail',
    'banco', 'bank', 'santander', 'bci', 'scotiabank', 'falabella', 'itau', 'estado',
    'google', 'buscar', 'search', 'bing', 'duckduckgo', 'youtube', 'docs', 'drive',
    'login', 'signin', 'password', 'contrasena', 'contraseña', 'clave',
    '1password', 'bitwarden', 'keepass', 'lastpass', 'word', 'excel', 'powerpoint',
    'visual studio', 'code', 'notepad', 'bloc de notas', '@',
)

# Constantes COM / UI Automation (Windows)
_CLSID_CUIAUTOMATION = uuid.UUID('{ff48dba4-60ef-4201-aa87-54103eef594e}').bytes_le
_IID_IUIAUTOMATION = uuid.UUID('{30cbe57d-d9d0-452a-ab13-7ac5ac4825ee}').bytes_le
_IID_IUIAUTOMATION_TEXT_PATTERN = uuid.UUID('{32eba289-3583-42c9-9c59-3b6d9a1e9b6a}').bytes_le
_CLSCTX_INPROC_SERVER = 0x1
_COINIT_MULTITHREADED = 0x0
_RPC_E_CHANGED_MODE = -2147417850

_UIA_CTRL_TEXT = 50020
_UIA_CTRL_LIST_ITEM = 50007
_UIA_CTRL_LIST = 50008
_UIA_CTRL_EDIT = 50004
_UIA_CTRL_DOCUMENT = 50030

# Property IDs y Pattern IDs de Windows UI Automation (UIAutomationClient.h)
_UIA_PROP_BOUNDING_RECT = 30001
_UIA_PROP_CONTROL_TYPE = 30003
_UIA_PROP_NAME = 30005
_UIA_PROP_AUTOMATION_ID = 30011
_UIA_PROP_IS_PASSWORD = 30019
_UIA_PROP_IS_OFFSCREEN = 30022
_UIA_PATTERN_VALUE = 10002
_UIA_PATTERN_TEXT = 10014
_UIA_TREESCOPE_DESCENDANTS = 4

_TIMEOUT_LECTURA_UIA_SEG = 2.5
_MAX_NODOS_ESCANEADOS_UIA = 2400
_MAX_CHARS_TEXT_PATTERN = 16000
_VT_I4 = 3

_RE_SOLO_HORA = re.compile(
    r'^(?:\d{1,2}:\d{2}(?:\s*[ap]\.?\s*m\.?)?|\d{1,2}/\d{1,2}/\d{2,4}|\d+\+)$',
    re.IGNORECASE,
)
_RE_FECHA_TEXTUAL = re.compile(
    r'^(?:\d{1,2}\s+de\s+[a-záéíóúñ]+(?:\s+de\s+\d{4})?|[a-záéíóúñ]+\s+\d{1,2},?\s+\d{4})$',
    re.IGNORECASE,
)
_RE_NO_LEIDOS = re.compile(r'^\d+\s+mensajes?\s+no\s+le[ií]dos?$|^\d+\s+unread\s+messages?$', re.IGNORECASE)
_RE_SUFIJO_HORA_LISTITEM = re.compile(
    r'(?:,\s*|\s+)(?:\d{1,2}:\d{2}(?:\s*[ap]\.?\s*m\.?)?)(?:,\s*(?:le[ií]do|entregado|enviado|read|delivered|sent))?\s*$',
    re.IGNORECASE,
)
_RE_SALIENTE_ESTADO = re.compile(
    r'(?:,\s*|\s+)(?:le[ií]do|entregado|enviado|read|delivered|sent)\s*$',
    re.IGNORECASE,
)
_TEXTOS_UI_IGNORAR = frozenset({
    'whatsapp', 'whatsapp web', 'whatsapp beta', 'whatsapp business',
    'en línea', 'en linea', 'online', 'escribiendo...', 'escribiendo', 'typing...',
    'grabando audio...', 'hoy', 'ayer', 'today', 'yesterday',
    'lunes', 'martes', 'miércoles', 'miercoles', 'jueves', 'viernes', 'sábado', 'sabado', 'domingo',
    'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
    'leído', 'leido', 'entregado', 'enviado', 'read', 'delivered', 'sent', 'doble check',
    'buscar', 'search', 'chats', 'estados', 'canales', 'comunidades', 'herramientas',
    'todos', 'no leídos', 'no leidos', 'favoritos', 'grupos', 'all', 'unread', 'favorites', 'groups',
    'escribe un mensaje', 'escribe un mensaje aquí', 'escribe un mensaje aqui',
    'escribir un mensaje', 'type a message', 'type a message here', 'mensajes',
    'archivados', 'archived', 'buscar...', 'adjuntar', 'menú', 'menu',
    'configuración', 'configuracion', 'perfil', 'mensaje de voz', 'videollamada', 'llamada de voz',
    'buscar o empezar un chat nuevo', 'buscar un chat o iniciar uno nuevo', 'iniciar un chat nuevo',
    'se eliminó este mensaje', 'se elimino este mensaje', 'this message was deleted',
    'eliminaste este mensaje', 'you deleted this message',
    'reenviado', 'forwarded', 'editado', 'edited',
})
_MARCADORES_COMPOSITOR = frozenset({
    'escribe un mensaje', 'escribe un mensaje aquí', 'escribe un mensaje aqui',
    'escribir un mensaje', 'type a message', 'type a message here',
})
_MARCADORES_SIDEBAR_DOC = frozenset({
    'chats', 'no leídos', 'no leidos', 'archivados', 'archived',
    'buscar o empezar un chat nuevo', 'buscar un chat o iniciar uno nuevo',
})
_MARCADORES_INICIO_CHAT_DOC = frozenset({
    'en línea', 'en linea', 'online', 'escribiendo...', 'escribiendo', 'typing...',
    'hoy', 'ayer', 'today', 'yesterday',
})
_SUBCADENAS_UI_IGNORAR = (
    'cifrados de extremo a extremo',
    'cifrado de extremo a extremo',
    'end-to-end encrypted',
    'haz clic aquí para',
    'haz clic aqui para',
    'click here for',
)
_PREFIJOS_UI_IGNORAR = (
    'últ. vez', 'ult. vez', 'last seen',
    'buscar o empezar', 'search or start',
)
_PREFIJOS_SALIENTES = ('tú:', 'tu:', 'you:', 'enviado:', 'mensaje enviado')
_RE_PREFIJO_SALIENTE = re.compile(r'^(?:t[uú]|you|enviado|mensaje enviado)\s*:\s*', re.IGNORECASE)
_ESTADOS_SALIENTES_SOLOS = frozenset({'leído', 'leido', 'entregado', 'enviado', 'read', 'delivered', 'sent', 'doble check'})
_IDS_CONTENEDOR_MENSAJES = ('MessagesList', 'MessageList', 'ConversationList')
_MAX_ELEMENTOS_UIA = 360
_MAX_MENSAJES_CONSECUTIVOS = 3

_CLAVES_CAJA_MENSAJE = ('mensaje', 'message', 'escrib', 'type', 'responder', 'reply')
_CLAVES_CAJA_BUSCAR = ('buscar', 'search', 'filtrar', 'filter')


@dataclass(frozen=True)
class VentanaChat:
    """Metadatos mínimos en memoria de una ventana activa de WhatsApp."""
    hwnd: int
    titulo: str
    rect: tuple[int, int, int, int]
    tipo: str  # 'desktop' o 'web'


@dataclass(frozen=True)
class DiagnosticoLectura:
    """Telemetría efímera en memoria de una lectura UIA (nunca se persiste)."""
    mensajes: tuple[str, ...]
    duracion_ms: float
    hwnd_original: int
    hwnd_render: int
    uso_render_hijo: bool
    metodo_contenedor: str
    modo_area: str
    nodos_findall: int
    nodos_filtrados: int
    uso_fallback_offscreen: bool
    uso_text_pattern: bool
    chars_text_pattern: int = 0


def _user32():
    return user32(exigir_windows=False)


def _limpiar_titulo(titulo: str) -> str:
    return _INVISIBLES.sub('', titulo).strip()


def _es_navegador(segmento: str) -> bool:
    s = segmento.strip().casefold()
    if s in _NAVEGADORES:
        return True
    return any(s.startswith(nav + ' ') or s.endswith(' ' + nav) for nav in _NAVEGADORES)


def _tipo_ventana(titulo: str) -> str:
    limpio = _limpiar_titulo(titulo).casefold()
    return 'web' if any(clave in limpio for clave in _CLAVES_WEB) else 'desktop'


def es_ventana_whatsapp(titulo: str) -> bool:
    """True solo para WhatsApp Desktop o pestaña de WhatsApp Web en un navegador.

    Excluye estrictamente cualquier ventana cuyo título contenga 'FraseYa',
    documentos, correo, bancos, gestores de contraseñas y otras aplicaciones.
    """
    if not isinstance(titulo, str):
        return False
    limpio = _limpiar_titulo(titulo)
    if not limpio or 'fraseya' in limpio.casefold():
        return False

    partes = [p.strip() for p in _SEPARADORES_TITULO.split(limpio) if p.strip()]
    if not partes:
        return False

    primera = _SUFIJO_PAGINAS_EDGE.sub('', partes[0]).strip()
    if not _PREFIJO_WHATSAPP.match(primera):
        return False

    if len(partes) == 1:
        return True
    if not _es_navegador(partes[-1]):
        return False
    if len(partes) == 2:
        return True
    if len(partes) == 3:
        medio = partes[1].casefold()
        return not any(prohibida in medio for prohibida in _TERCER_SEGMENTO_PROHIBIDO)
    return False


@dataclass(frozen=True)
class _NodoUIA:
    """Instantánea efímera en memoria de un nodo UIA del árbol de WhatsApp."""
    texto: str
    tipo_control: int
    rect: tuple[int, int, int, int]
    automation_id: str = ''
    es_contrasena: bool = False
    fuera_pantalla: bool = False


def _limpiar_texto_uia(texto: str) -> str:
    if not isinstance(texto, str):
        return ''
    sin_inv = _INVISIBLES.sub('', texto)
    return ' '.join(sin_inv.split()).strip()


def _es_ruido_ui(texto: str) -> bool:
    limpio = _limpiar_texto_uia(texto)
    if len(limpio) < 2:
        return True
    bajo = limpio.casefold()
    if bajo in _TEXTOS_UI_IGNORAR:
        return True
    if _RE_SOLO_HORA.match(limpio) or _RE_FECHA_TEXTUAL.match(limpio) or _RE_NO_LEIDOS.match(limpio):
        return True
    if any(sub in bajo for sub in _SUBCADENAS_UI_IGNORAR):
        return True
    if any(bajo.startswith(pref) for pref in _PREFIJOS_UI_IGNORAR):
        return True
    return not any(ch.isalnum() for ch in limpio)


def _es_texto_saliente(texto: str) -> bool:
    limpio = _limpiar_texto_uia(texto)
    if not limpio:
        return False
    bajo = limpio.casefold()
    return any(bajo.startswith(prefijo) for prefijo in _PREFIJOS_SALIENTES) or bool(_RE_SALIENTE_ESTADO.search(bajo))


def _es_texto_mensaje_valido(texto: str) -> bool:
    return not _es_ruido_ui(texto) and not _es_texto_saliente(texto)


def _limpiar_texto_saliente(texto: str) -> str:
    limpio = _limpiar_texto_uia(texto)
    if not limpio:
        return ''
    sin_prefijo = _RE_PREFIJO_SALIENTE.sub('', limpio).strip()
    sin_estado = _RE_SUFIJO_HORA_LISTITEM.sub('', sin_prefijo)
    sin_estado = _RE_SALIENTE_ESTADO.sub('', sin_estado).strip(' ,-')
    if not sin_estado or _es_ruido_ui(sin_estado) or sin_estado.casefold() in _ESTADOS_SALIENTES_SOLOS:
        return ''
    return sin_estado


def _agrupar_turnos_desde_reverso(pares_reverso, max_mensajes: int) -> list[str]:
    """Agrupa párrafos consecutivos del mismo rol ('Cliente'/'Agente') en orden cronológico."""
    turnos: list[tuple[str, list[str]]] = []
    ultimo_turno: tuple[str, str] | None = None
    total_chars = 0
    limite_suave = min(MAX_LARGO_MENSAJE, 3000)
    for txt, es_sal in pares_reverso:
        if es_sal:
            limpio = _limpiar_texto_saliente(txt)
            if not limpio:
                continue
            rol = 'Agente'
        else:
            limpio = txt
            if not _es_texto_mensaje_valido(limpio):
                continue
            rol = 'Cliente'
        clave_turno = (rol, limpio.casefold())
        if ultimo_turno == clave_turno:
            continue
        if turnos and turnos[-1][0] == rol:
            if total_chars + len(limpio) + 1 > MAX_LARGO_MENSAJE:
                continue
            turnos[-1][1].append(limpio)
            total_chars += len(limpio) + 1
        else:
            if len(turnos) >= max_mensajes:
                break
            etiqueta_base = len(rol) + 2 + len(limpio)
            if turnos and (total_chars >= limite_suave or total_chars + etiqueta_base + 1 > MAX_LARGO_MENSAJE):
                break
            turnos.append((rol, [limpio]))
            total_chars += etiqueta_base + 1
        ultimo_turno = clave_turno
    turnos.reverse()
    seleccion = [
        f'{rol}: ' + '\n'.join(reversed(frags))[:MAX_LARGO_MENSAJE]
        for rol, frags in turnos
    ]
    return seleccion if any(s.startswith('Cliente: ') for s in seleccion) else []


def _recoger_entrantes_reverso(
    items_reverso,
    *,
    max_mensajes: int,
    cortar_en_saliente: bool,
    controlar_longitud: bool = True,
) -> list[str]:
    """Recoge mensajes entrantes recientes desde una secuencia invertida `(texto, es_saliente, top, bottom)`."""
    seleccion: list[str] = []
    visto_canon: set[str] = set()
    total_chars = 0
    top_posterior: int | None = None
    limite_suave = min(MAX_LARGO_MENSAJE, 1800)
    for txt, es_sal, top, bottom in items_reverso:
        if es_sal:
            if cortar_en_saliente:
                break
            continue
        if not _es_texto_mensaje_valido(txt):
            continue
        if cortar_en_saliente and top_posterior is not None and bottom > top and (top_posterior - bottom) > 260:
            break
        canon = txt.casefold()
        if canon in visto_canon:
            continue
        if controlar_longitud and seleccion and (total_chars >= limite_suave or total_chars + len(txt) + 1 > MAX_LARGO_MENSAJE):
            break
        seleccion.append(txt[:MAX_LARGO_MENSAJE])
        visto_canon.add(canon)
        total_chars += len(txt) + 1
        if bottom > top:
            top_posterior = top
        if len(seleccion) >= max_mensajes:
            break
    seleccion.reverse()
    return seleccion


def _limpiar_texto_listitem(texto: str) -> str:
    limpio = _limpiar_texto_uia(texto)
    if not limpio:
        return ''
    return _RE_SUFIJO_HORA_LISTITEM.sub('', limpio).strip(' ,-')


def _limites_area_chat(
    rect_area: tuple[int, int, int, int],
    modo_area: str = 'ventana',
) -> tuple[int, int, int, int]:
    """Calcula el sub-rectángulo `(left, top, right, bottom)` del área de mensajes."""
    area_l, area_t, area_r, area_b = rect_area
    area_w = max(1, area_r - area_l)
    area_h = max(1, area_b - area_t)
    if modo_area == 'mensajes':
        return (area_l, area_t, area_r, area_b)
    if modo_area == 'main':
        chat_t = area_t + min(68, int(area_h * 0.14))
        chat_b = area_b - min(62, int(area_h * 0.14))
        return (area_l, chat_t, area_r, max(chat_t + 1, chat_b))
    margen_izq = min(int(area_w * 0.27), 410) if area_w >= 680 else 0
    chat_l = area_l + margen_izq
    chat_t = area_t + min(100, int(area_h * 0.15))
    chat_b = area_b - min(64, int(area_h * 0.13))
    return (chat_l, chat_t, max(chat_l + 1, area_r), max(chat_t + 1, chat_b))


def _rect_en_area_chat(
    rect: tuple[int, int, int, int],
    limites: tuple[int, int, int, int],
    *,
    tiene_area: bool,
    es_listitem: bool = False,
    requerir_rect_no_vacio: bool = False,
) -> bool:
    if not tiene_area:
        return not requerir_rect_no_vacio
    l, t, r, b = rect
    if r <= l or b <= t:
        return not requerir_rect_no_vacio
    chat_l, chat_t, chat_r, chat_b = limites
    cx = (l + r) * 0.5
    cy = (t + b) * 0.5
    if cy < chat_t or cy > chat_b:
        return False
    if es_listitem:
        return cx >= chat_l and cx <= chat_r
    return l >= (chat_l - 8) and r <= (chat_r + 12)


def _filtrar_y_recortar_nodos(
    nodos: list[_NodoUIA],
    rect_area: tuple[int, int, int, int],
    *,
    modo_area: str = 'ventana',
    max_elementos: int = _MAX_ELEMENTOS_UIA,
) -> list[_NodoUIA]:
    """Filtra por área visible del chat antes de recortar a `max_elementos`."""
    tope = max(1, int(max_elementos))
    if len(nodos) <= tope:
        return list(nodos)
    tiene_area = (rect_area[2] - rect_area[0]) > 20 and (rect_area[3] - rect_area[1]) > 20
    if not tiene_area:
        return list(nodos[-tope:])
    limites = _limites_area_chat(rect_area, modo_area=modo_area)
    en_chat = [
        n for n in nodos
        if (not n.es_contrasena)
        and _rect_en_area_chat(
            n.rect,
            limites,
            tiene_area=True,
            es_listitem=(n.tipo_control == _UIA_CTRL_LIST_ITEM),
            requerir_rect_no_vacio=False,
        )
    ]
    return en_chat[-tope:] if en_chat else list(nodos[-tope:])


def _clasificar_geometria(rect: tuple[int, int, int, int], chat_l: int, chat_w: int, tiene_area: bool) -> str:
    """Devuelve 'saliente', 'centrado' o 'entrante' según alineación en el chat."""
    if not tiene_area or chat_w < 260:
        return 'entrante'
    l, t, r, b = rect
    if r <= l or b <= t:
        return 'entrante'
    rel_l = (l - chat_l) / chat_w
    rel_r = (r - chat_l) / chat_w
    rel_c = ((l + r) * 0.5 - chat_l) / chat_w
    ancho_rel = (r - l) / chat_w
    if ancho_rel < 0.80:
        if (rel_l >= 0.22 and rel_r >= 0.78 and rel_c >= 0.54) or (rel_l >= 0.52 and rel_c >= 0.60):
            return 'saliente'
        if chat_w >= 300 and rel_l >= 0.22 and rel_r <= 0.78 and abs(rel_c - 0.5) <= 0.08:
            return 'centrado'
    return 'entrante'


def _extraer_lista_ultimos_mensajes(
    nodos: list[_NodoUIA],
    rect_area: tuple[int, int, int, int],
    *,
    modo_area: str = 'ventana',
    limite: int = _MAX_MENSAJES_CONSECUTIVOS,
    solo_sin_responder: bool = True,
    incluir_offscreen_en_area: bool = False,
    incluir_salientes: bool = False,
) -> list[str]:
    """Extrae hasta `limite` mensajes limpios en orden cronológico."""
    max_mensajes = max(1, int(limite))
    if not nodos:
        return []

    limites = _limites_area_chat(rect_area, modo_area=modo_area)
    chat_l, _chat_t, chat_r, _chat_b = limites
    chat_w = max(1, chat_r - chat_l)
    tiene_area = (rect_area[2] - rect_area[0]) > 20 and (rect_area[3] - rect_area[1]) > 20

    def _nodo_en_area(nodo: _NodoUIA, es_listitem: bool = False) -> bool:
        if nodo.es_contrasena or (nodo.fuera_pantalla and not incluir_offscreen_en_area):
            return False
        return _rect_en_area_chat(
            nodo.rect,
            limites,
            tiene_area=tiene_area,
            es_listitem=es_listitem,
            requerir_rect_no_vacio=nodo.fuera_pantalla,
        )

    bandas_salientes: list[tuple[int, int]] = []
    for nodo in nodos:
        if nodo.es_contrasena or nodo.tipo_control == _UIA_CTRL_EDIT:
            continue
        _l, t, r, b = nodo.rect
        if nodo.tipo_control == _UIA_CTRL_LIST_ITEM and _nodo_en_area(nodo, es_listitem=True):
            if _es_texto_saliente(nodo.texto) and b > t:
                bandas_salientes.append((t, b))
        elif nodo.tipo_control == _UIA_CTRL_TEXT and _nodo_en_area(nodo, es_listitem=False):
            bajo = _limpiar_texto_uia(nodo.texto).casefold()
            if bajo in _ESTADOS_SALIENTES_SOLOS and b > t:
                rel_r = (r - chat_l) / chat_w if tiene_area else 1.0
                if rel_r >= 0.65:
                    bandas_salientes.append((t - 12, b + 6))

    def _en_banda_saliente(rect: tuple[int, int, int, int]) -> bool:
        _l, t, _r, b = rect
        if b <= t:
            return False
        cy = (t + b) * 0.5
        return any(bt <= cy <= bb for bt, bb in bandas_salientes)

    candidatos_text: list[list] = []
    for orden, nodo in enumerate(nodos):
        if nodo.tipo_control != _UIA_CTRL_TEXT or not _nodo_en_area(nodo, es_listitem=False):
            continue
        texto = _limpiar_texto_uia(nodo.texto)
        if not texto or _es_ruido_ui(texto):
            continue
        clase_geo = _clasificar_geometria(nodo.rect, chat_l, chat_w, tiene_area)
        if clase_geo == 'centrado':
            continue
        es_saliente = _es_texto_saliente(texto) or clase_geo == 'saliente' or _en_banda_saliente(nodo.rect)
        l, t, r, b = nodo.rect
        candidatos_text.append([orden, t, l, r, b, texto, es_saliente])

    candidatos_listitem: list[list] = []
    for orden, nodo in enumerate(nodos):
        if nodo.tipo_control != _UIA_CTRL_LIST_ITEM or not _nodo_en_area(nodo, es_listitem=True):
            continue
        crudo = _limpiar_texto_uia(nodo.texto)
        if not crudo:
            continue
        l, t, r, b = nodo.rect
        if b > t and candidatos_text and any(
            (ct[4] > ct[1]) and (ct[1] >= t - 6) and (ct[4] <= b + 6)
            for ct in candidatos_text
        ):
            continue
        es_saliente = _es_texto_saliente(crudo)
        if not es_saliente and b > t:
            ancho_rel = (r - l) / chat_w if tiene_area else 1.0
            if ancho_rel < 0.80 and _clasificar_geometria(nodo.rect, chat_l, chat_w, tiene_area) == 'saliente':
                es_saliente = True
        texto = _limpiar_texto_listitem(crudo)
        if not texto or _es_ruido_ui(texto):
            if es_saliente and crudo:
                texto = crudo
            else:
                continue
        candidatos_listitem.append([orden, t, l, r, b, texto, es_saliente])

    todos = candidatos_text + candidatos_listitem
    if not todos:
        return []
    if any(c[4] > c[1] for c in todos):
        todos.sort(key=lambda c: (c[1], c[2], c[0]))
    else:
        todos.sort(key=lambda c: c[0])

    mensajes: list[list] = []
    for item in todos:
        if (
            mensajes
            and mensajes[-1][6] == item[6]
            and item[4] > item[1]
            and mensajes[-1][4] > mensajes[-1][1]
            and abs(item[1] - mensajes[-1][1]) <= 6
            and item[2] >= mensajes[-1][3] - 6
        ):
            if item[5] != mensajes[-1][5]:
                mensajes[-1][5] = f'{mensajes[-1][5]} {item[5]}'.strip()
            mensajes[-1][3] = max(mensajes[-1][3], item[3])
            mensajes[-1][4] = max(mensajes[-1][4], item[4])
        else:
            mensajes.append(item)

    if not mensajes:
        return []

    def _recoger(*, cortar_en_saliente: bool) -> list[str]:
        if incluir_salientes:
            return _agrupar_turnos_desde_reverso(
                ((item[5], bool(item[6])) for item in reversed(mensajes)),
                max_mensajes,
            )
        return _recoger_entrantes_reverso(
            ((item[5], bool(item[6]), item[1], item[4]) for item in reversed(mensajes)),
            max_mensajes=max_mensajes,
            cortar_en_saliente=cortar_en_saliente,
            controlar_longitud=True,
        )

    if incluir_salientes:
        return _recoger(cortar_en_saliente=False)
    if solo_sin_responder:
        return [] if mensajes[-1][6] else _recoger(cortar_en_saliente=True)
    if not mensajes[-1][6]:
        consecutivos = _recoger(cortar_en_saliente=True)
        if consecutivos:
            return consecutivos
    return _recoger(cortar_en_saliente=False)


def _extraer_nodos_chat(
    nodos: list[_NodoUIA],
    rect_area: tuple[int, int, int, int],
    *,
    modo_area: str = 'ventana',
    limite: int = _MAX_MENSAJES_CONSECUTIVOS,
    max_elementos: int = _MAX_ELEMENTOS_UIA,
    incluir_salientes: bool = False,
) -> tuple[list[str], bool]:
    """Filtra por área antes de recortar y aplica fallback si IsOffscreen=True oculta el chat."""
    recortados = _filtrar_y_recortar_nodos(nodos, rect_area, modo_area=modo_area, max_elementos=max_elementos)
    mensajes = _extraer_lista_ultimos_mensajes(
        recortados,
        rect_area,
        modo_area=modo_area,
        limite=limite,
        solo_sin_responder=False,
        incluir_offscreen_en_area=False,
        incluir_salientes=incluir_salientes,
    )
    if mensajes:
        return (mensajes, False)
    if any(n.fuera_pantalla for n in recortados):
        mensajes_off = _extraer_lista_ultimos_mensajes(
            recortados,
            rect_area,
            modo_area=modo_area,
            limite=limite,
            solo_sin_responder=False,
            incluir_offscreen_en_area=True,
            incluir_salientes=incluir_salientes,
        )
        return (mensajes_off, bool(mensajes_off))
    return ([], False)


def _extraer_mensajes_de_texto_plano(
    texto_doc: str,
    limite: int = _MAX_MENSAJES_CONSECUTIVOS,
    *,
    incluir_salientes: bool = False,
) -> list[str]:
    """Extrae los últimos `limite` mensajes limpios desde TextPattern de WebView2."""
    if not isinstance(texto_doc, str) or not texto_doc.strip():
        return []
    max_mensajes = max(1, int(limite))
    lineas = [_limpiar_texto_uia(l) for l in re.split(r'[\r\n\u2028\u2029]+', texto_doc)]
    lineas = [l for l in lineas if l]
    if not lineas:
        return []

    idx_ultimo_sidebar = -1
    for i, linea in enumerate(lineas):
        bajo = linea.casefold()
        if bajo in _MARCADORES_SIDEBAR_DOC or any(bajo.startswith(p) for p in ('buscar o empezar', 'search or start')):
            idx_ultimo_sidebar = i

    if idx_ultimo_sidebar >= 0:
        for j in range(idx_ultimo_sidebar + 1, len(lineas)):
            bajo = lineas[j].casefold()
            es_inicio = (
                bajo in _MARCADORES_INICIO_CHAT_DOC
                or any(sub in bajo for sub in _SUBCADENAS_UI_IGNORAR)
                or any(bajo.startswith(pref) for pref in ('últ. vez', 'ult. vez', 'last seen'))
                or bool(_RE_FECHA_TEXTUAL.match(lineas[j]))
            )
            if es_inicio:
                lineas = lineas[j + 1:]
                break

    registros: list[list] = []
    for linea in lineas:
        bajo = linea.casefold()
        if bajo in _MARCADORES_COMPOSITOR:
            if registros:
                break
            continue
        if bajo in _ESTADOS_SALIENTES_SOLOS:
            if registros:
                registros[-1][1] = True
            continue
        es_saliente = _es_texto_saliente(linea)
        texto = _limpiar_texto_listitem(linea)
        if not texto or _es_ruido_ui(texto):
            continue
        registros.append([texto[:MAX_LARGO_MENSAJE], es_saliente])

    if not registros:
        return []

    def _recoger(*, cortar_en_saliente: bool) -> list[str]:
        if incluir_salientes:
            return _agrupar_turnos_desde_reverso(
                ((txt, bool(es_sal)) for txt, es_sal in reversed(registros)),
                max_mensajes,
            )
        return _recoger_entrantes_reverso(
            ((txt, bool(es_sal), 0, 0) for txt, es_sal in reversed(registros)),
            max_mensajes=max_mensajes,
            cortar_en_saliente=cortar_en_saliente,
            controlar_longitud=False,
        )

    if incluir_salientes:
        return _recoger(cortar_en_saliente=False)
    if not registros[-1][1]:
        consecutivos = _recoger(cortar_en_saliente=True)
        if consecutivos:
            return consecutivos
    return _recoger(cortar_en_saliente=False)


def _extraer_ultimos_mensajes(
    nodos: list[_NodoUIA],
    rect_area: tuple[int, int, int, int],
    *,
    modo_area: str = 'ventana',
) -> str | None:
    """Extrae los últimos 1-3 mensajes entrantes consecutivos del chat abierto."""
    seleccion = _extraer_lista_ultimos_mensajes(
        nodos,
        rect_area,
        modo_area=modo_area,
        limite=_MAX_MENSAJES_CONSECUTIVOS,
        solo_sin_responder=True,
    )
    if not seleccion:
        return None
    return '\n'.join(seleccion).strip()[:MAX_LARGO_MENSAJE] or None


def _clic_seguro_en_caja(hwnd: int, rc_caja: tuple[int, int, int, int] | None = None) -> bool:
    """Hace clic físico seguro en la caja de texto de WhatsApp solo si está al frente."""
    if sys.platform != 'win32' or not hwnd:
        return False
    try:
        u = _user32()
        if u is None:
            return False
        pid_wsp = pid_ventana(int(hwnd))
        en_frente = False
        for _ in range(12):
            fg = u.GetForegroundWindow()
            pid_fg = pid_ventana(int(fg)) if fg else 0
            if fg == int(hwnd) or (pid_wsp and pid_fg == pid_wsp):
                en_frente = True
                break
            time.sleep(0.03)
        if not en_frente:
            return False

        rect_win = rect_hwnd_win32(hwnd_render_chat(int(hwnd)))
        if rect_win[2] <= rect_win[0] or rect_win[3] <= rect_win[1]:
            rect_win = rect_hwnd_win32(int(hwnd))
        vl, vt, vr, vb = rect_win
        vw, vh = vr - vl, vb - vt
        if rc_caja and rc_caja[2] > rc_caja[0] and rc_caja[3] > rc_caja[1]:
            l, t, r, b = rc_caja
            px = (l + r) // 2
            py = (t + b) // 2
        elif vw >= 300 and vh >= 240:
            px = vl + int(vw * 0.55)
            py = max(vt + 20, vb - 44)
        else:
            return False

        pid_pt, raiz_pt = info_punto_win32(px, py)
        if pid_pt == os.getpid():
            return False
        if raiz_pt != int(hwnd) and not (pid_wsp and pid_pt == pid_wsp):
            return False

        u.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
        u.GetCursorPos.restype = wintypes.BOOL
        u.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
        u.SetCursorPos.restype = wintypes.BOOL

        prev = wintypes.POINT()
        tiene_prev = bool(u.GetCursorPos(ctypes.byref(prev)))
        u.SetCursorPos(int(px), int(py))
        time.sleep(0.02)
        down = INPUT(type=0)
        down.u.mi = MOUSEINPUT(0, 0, 0, 0x0002, 0, 0)
        up = INPUT(type=0)
        up.u.mi = MOUSEINPUT(0, 0, 0, 0x0004, 0, 0)
        arr = (INPUT * 2)(down, up)
        enviado = u.SendInput(2, arr, ctypes.sizeof(INPUT)) == 2
        time.sleep(0.06)
        if tiene_prev:
            u.SetCursorPos(int(prev.x), int(prev.y))
        return bool(enviado)
    except (OSError, ctypes.ArgumentError, ValueError):
        return False


def _seleccionar_caja_mensaje(
    candidatos: list[tuple[int, str, tuple[int, int, int, int]]],
    rect_ventana: tuple[int, int, int, int],
) -> int | None:
    """Elige el índice del control Edit visible en la mitad inferior derecha (compositor)."""
    if not candidatos:
        return None
    v_l, v_t, v_r, v_b = rect_ventana
    v_w = max(0, v_r - v_l)
    v_h = max(0, v_b - v_t)
    tiene_rect_win = v_w > 20 and v_h > 20

    validos: list[tuple[tuple[int, int, float, float], int]] = []
    for idx, nombre, rc in candidatos:
        l, t, r, b = rc
        tiene_rc = r > l and b > t
        if tiene_rect_win and tiene_rc:
            cx = (l + r) * 0.5
            cy = (t + b) * 0.5
            if cy < v_t + v_h * 0.50:
                continue
            if v_w >= 680 and cx < v_l + v_w * 0.25:
                continue
        else:
            cx = float(l)
            cy = float(t)

        bajo = _limpiar_texto_uia(nombre).casefold()
        es_buscar = any(k in bajo for k in _CLAVES_CAJA_BUSCAR)
        es_compositor = any(k in bajo for k in _CLAVES_CAJA_MENSAJE)
        if es_buscar and not es_compositor:
            continue
        puntaje = (1 if es_compositor else 0, 1 if tiene_rc else 0, cy, cx)
        validos.append((puntaje, idx))

    if not validos:
        return None
    validos.sort(key=lambda item: item[0], reverse=True)
    return validos[0][1]


class _LectorUIA:
    """Acceso mínimo, rápido y seguro a Windows UI Automation vía ctypes COM."""

    def __init__(self):
        self._ole32 = ctypes.WinDLL('ole32')
        self._oleaut32 = ctypes.WinDLL('oleaut32')
        self._ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
        self._ole32.CoInitializeEx.restype = ctypes.c_long
        self._ole32.CoUninitialize.argtypes = []
        self._ole32.CoCreateInstance.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p),
        ]
        self._ole32.CoCreateInstance.restype = ctypes.c_long
        self._oleaut32.SysFreeString.argtypes = [ctypes.c_void_p]

    @staticmethod
    def _vcall(obj, indice, restype, argtypes, *args):
        vtbl = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
        fn = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(vtbl[indice])
        return fn(obj, *args)

    def _liberar(self, ptr):
        if ptr and getattr(ptr, 'value', None):
            try:
                self._vcall(ptr, 2, ctypes.c_ulong, [])
            except (OSError, ctypes.ArgumentError, ValueError):
                pass

    def _leer_bstr(self, ptr_bstr) -> str:
        if not ptr_bstr or not ptr_bstr.value:
            return ''
        try:
            return ctypes.wstring_at(ptr_bstr.value)
        finally:
            self._oleaut32.SysFreeString(ptr_bstr)

    @staticmethod
    def _var_i4(valor: int) -> VARIANT:
        v = VARIANT()
        v.vt = _VT_I4
        v.lVal = int(valor)
        return v

    def _crear_condicion_i4(self, uia, prop_id: int, valor: int) -> ctypes.c_void_p:
        cond = ctypes.c_void_p()
        hr = self._vcall(
            uia, 23, ctypes.c_long,
            [ctypes.c_int, VARIANT, ctypes.POINTER(ctypes.c_void_p)],
            prop_id, self._var_i4(valor), ctypes.byref(cond),
        )
        return cond if hr == 0 else ctypes.c_void_p()

    def _rect_elemento(self, elemento, *, cached: bool = False) -> tuple[int, int, int, int]:
        rc = wintypes.RECT()
        slot = 75 if cached else 43
        hr = self._vcall(elemento, slot, ctypes.c_long, [ctypes.POINTER(wintypes.RECT)], ctypes.byref(rc))
        if hr != 0:
            return (0, 0, 0, 0)
        return (int(rc.left), int(rc.top), int(rc.right), int(rc.bottom))

    def _leer_prop_int(self, elemento, slot: int) -> int:
        valor = ctypes.c_int(0)
        hr = self._vcall(elemento, slot, ctypes.c_long, [ctypes.POINTER(ctypes.c_int)], ctypes.byref(valor))
        return int(valor.value) if hr == 0 else 0

    def _leer_prop_str(self, elemento, slot: int) -> str:
        bstr = ctypes.c_void_p()
        hr = self._vcall(elemento, slot, ctypes.c_long, [ctypes.POINTER(ctypes.c_void_p)], ctypes.byref(bstr))
        return self._leer_bstr(bstr) if hr == 0 else ''

    def _leer_value_pattern(self, elemento) -> str:
        pat = ctypes.c_void_p()
        try:
            hr = self._vcall(
                elemento, 16, ctypes.c_long,
                [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)],
                _UIA_PATTERN_VALUE, ctypes.byref(pat),
            )
            if hr != 0 or not pat.value:
                return ''
            return self._leer_prop_str(pat, 4)
        finally:
            self._liberar(pat)

    def _leer_text_pattern(self, elemento, max_chars: int = _MAX_CHARS_TEXT_PATTERN) -> str:
        """Lee texto vía IUIAutomationTextPattern (10014). Nunca lee controles Edit ni IsPassword."""
        if not elemento or not getattr(elemento, 'value', None):
            return ''
        if bool(self._leer_prop_int(elemento, 35)) or self._leer_prop_int(elemento, 21) == _UIA_CTRL_EDIT:
            return ''

        pat = ctypes.c_void_p()
        doc_range = ctypes.c_void_p()
        vis_ranges = ctypes.c_void_p()
        try:
            iid_tp = (ctypes.c_byte * 16).from_buffer_copy(_IID_IUIAUTOMATION_TEXT_PATTERN)
            hr = self._vcall(
                elemento, 14, ctypes.c_long,
                [ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)],
                _UIA_PATTERN_TEXT, ctypes.byref(iid_tp), ctypes.byref(pat),
            )
            if hr != 0 or not pat.value:
                return ''

            texto_doc = ''
            hr_dr = self._vcall(pat, 7, ctypes.c_long, [ctypes.POINTER(ctypes.c_void_p)], ctypes.byref(doc_range))
            if hr_dr == 0 and doc_range.value:
                bstr = ctypes.c_void_p()
                hr_gt = self._vcall(
                    doc_range, 12, ctypes.c_long,
                    [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)],
                    int(max_chars), ctypes.byref(bstr),
                )
                if hr_gt == 0:
                    texto_doc = self._leer_bstr(bstr)

            if not texto_doc.strip() or len(texto_doc) >= int(max_chars):
                hr_vr = self._vcall(pat, 6, ctypes.c_long, [ctypes.POINTER(ctypes.c_void_p)], ctypes.byref(vis_ranges))
                if hr_vr == 0 and vis_ranges.value:
                    n_ranges = self._leer_prop_int(vis_ranges, 3)
                    partes: list[str] = []
                    acum = 0
                    for idx in range(min(n_ranges, 32)):
                        r_item = ctypes.c_void_p()
                        hr_ri = self._vcall(
                            vis_ranges, 4, ctypes.c_long,
                            [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)],
                            idx, ctypes.byref(r_item),
                        )
                        if hr_ri != 0 or not r_item.value:
                            continue
                        try:
                            bstr_v = ctypes.c_void_p()
                            hr_gv = self._vcall(
                                r_item, 12, ctypes.c_long,
                                [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)],
                                min(4000, max(256, int(max_chars) - acum)),
                                ctypes.byref(bstr_v),
                            )
                            if hr_gv == 0:
                                frag = self._leer_bstr(bstr_v)
                                if frag:
                                    partes.append(frag)
                                    acum += len(frag)
                                    if acum >= int(max_chars):
                                        break
                        finally:
                            self._liberar(r_item)
                    texto_vis = '\n'.join(partes).strip()
                    if texto_vis:
                        return texto_vis

            return texto_doc
        finally:
            self._liberar(vis_ranges)
            self._liberar(doc_range)
            self._liberar(pat)

    def _element_from_point(self, uia, x: int, y: int) -> ctypes.c_void_p:
        elem = ctypes.c_void_p()
        hr = self._vcall(
            uia, 7, ctypes.c_long,
            [wintypes.POINT, ctypes.POINTER(ctypes.c_void_p)],
            wintypes.POINT(int(x), int(y)), ctypes.byref(elem),
        )
        return elem if hr == 0 else ctypes.c_void_p()

    def _control_view_walker(self, uia) -> ctypes.c_void_p:
        walker = ctypes.c_void_p()
        hr = self._vcall(uia, 14, ctypes.c_long, [ctypes.POINTER(ctypes.c_void_p)], ctypes.byref(walker))
        return walker if hr == 0 else ctypes.c_void_p()

    def _padre_control(self, walker, elem) -> ctypes.c_void_p:
        padre = ctypes.c_void_p()
        hr = self._vcall(
            walker, 3, ctypes.c_long,
            [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)],
            elem, ctypes.byref(padre),
        )
        return padre if hr == 0 else ctypes.c_void_p()

    def _localizar_por_punto(
        self,
        uia,
        hwnd_top: int,
        hwnd_render: int,
        rect_ventana: tuple[int, int, int, int],
        deadline: float,
    ) -> tuple[ctypes.c_void_p, tuple[int, int, int, int], str, ctypes.c_void_p, ctypes.c_void_p]:
        """Despierta WebView2 con ElementFromPoint y asciende hasta 10 niveles al contenedor del chat."""
        vx, vy, vr, vb = rect_ventana
        vw = vr - vx
        vh = vb - vy
        if vw < 120 or vh < 120:
            return (ctypes.c_void_p(), (0, 0, 0, 0), 'ventana', ctypes.c_void_p(), ctypes.c_void_p())

        mi_pid = os.getpid()
        pids_wsp = {p for p in (pid_ventana(hwnd_top), pid_ventana(hwnd_render)) if p > 0}
        walker = self._control_view_walker(uia)
        if not walker.value:
            return (ctypes.c_void_p(), (0, 0, 0, 0), 'ventana', ctypes.c_void_p(), ctypes.c_void_p())

        puntos = (
            ((0.55, 0.78), (0.55, 0.65), (0.55, 0.52), (0.45, 0.72))
            if vw >= 680 else
            ((0.50, 0.78), (0.50, 0.65), (0.50, 0.50))
        )

        el_hit_guardado = ctypes.c_void_p()
        el_doc_guardado = ctypes.c_void_p()
        try:
            for fx, fy in puntos:
                if time.monotonic() >= deadline:
                    break
                px = vx + int(vw * fx)
                py = vy + int(vh * fy)

                pid_pt, raiz_pt = info_punto_win32(px, py)
                if pid_pt == mi_pid:
                    continue
                if raiz_pt and raiz_pt != hwnd_top and (not pids_wsp or pid_pt not in pids_wsp):
                    continue

                el_hit = self._element_from_point(uia, px, py)
                if not el_hit.value:
                    continue
                el_pid = self._leer_prop_int(el_hit, 20)
                if el_pid == mi_pid or (pids_wsp and el_pid not in pids_wsp and raiz_pt != hwnd_top):
                    self._liberar(el_hit)
                    continue

                actual = el_hit
                mejor_gen = ctypes.c_void_p()
                mejor_gen_rc = (0, 0, 0, 0)
                el_doc_local = ctypes.c_void_p()
                encontrado = ctypes.c_void_p()
                encontrado_rc = (0, 0, 0, 0)
                encontrado_modo = 'ventana'

                for paso in range(11):
                    if not actual.value or time.monotonic() >= deadline:
                        break
                    ctrl = self._leer_prop_int(actual, 21)
                    rc = self._rect_elemento(actual, cached=False)
                    aid = self._leer_prop_str(actual, 29)
                    aria = self._leer_prop_str(actual, 45).casefold()
                    aw = rc[2] - rc[0]
                    ah = rc[3] - rc[1]

                    if ctrl == _UIA_CTRL_DOCUMENT and not el_doc_local.value and actual.value != el_hit.value:
                        el_doc_local = actual

                    es_lado_derecho = (vw < 680) or (rc[0] >= vx + int(vw * 0.18))
                    tam_valido = aw >= 240 and ah >= 140
                    alto_panel = ah >= max(140, int(vh * 0.30)) if vh >= 350 else tam_valido

                    if tam_valido and aid == 'main' and es_lado_derecho:
                        encontrado, encontrado_rc, encontrado_modo = actual, rc, 'main'
                        break
                    if tam_valido and (aid in _IDS_CONTENEDOR_MENSAJES or aria == 'application') and es_lado_derecho:
                        encontrado, encontrado_rc, encontrado_modo = actual, rc, 'mensajes'
                        break
                    if (
                        ctrl == _UIA_CTRL_LIST
                        and tam_valido
                        and alto_panel
                        and es_lado_derecho
                        and (vw < 680 or aw < int(vw * 0.90))
                    ):
                        encontrado, encontrado_rc, encontrado_modo = actual, rc, 'mensajes'
                        break

                    if (
                        not mejor_gen.value
                        and tam_valido
                        and alto_panel
                        and es_lado_derecho
                        and ctrl not in (_UIA_CTRL_TEXT, _UIA_CTRL_LIST_ITEM, _UIA_CTRL_EDIT, 50000)
                        and (vw < 680 or aw < int(vw * 0.90))
                    ):
                        mejor_gen, mejor_gen_rc = actual, rc

                    if paso == 10:
                        break
                    padre = self._padre_control(walker, actual)
                    if not padre.value or padre.value == actual.value:
                        self._liberar(padre)
                        break
                    if actual.value not in (el_hit.value, mejor_gen.value, el_doc_local.value):
                        self._liberar(actual)
                    actual = padre

                if actual.value and actual.value not in (
                    el_hit.value, mejor_gen.value, el_doc_local.value, encontrado.value
                ):
                    self._liberar(actual)

                if encontrado.value:
                    if mejor_gen.value and mejor_gen.value not in (encontrado.value, el_hit.value, el_doc_local.value):
                        self._liberar(mejor_gen)
                    ret_hit = el_hit if el_hit.value != encontrado.value else ctypes.c_void_p()
                    ret_doc = (
                        el_doc_local
                        if el_doc_local.value and el_doc_local.value not in (encontrado.value, ret_hit.value)
                        else ctypes.c_void_p()
                    )
                    self._liberar(el_hit_guardado)
                    self._liberar(el_doc_guardado)
                    return (encontrado, encontrado_rc, encontrado_modo, ret_hit, ret_doc)

                if mejor_gen.value:
                    modo_gen = (
                        'main'
                        if (mejor_gen_rc[1] <= vy + 90 and mejor_gen_rc[3] >= vb - 70)
                        else 'mensajes'
                    )
                    ret_hit = el_hit if el_hit.value != mejor_gen.value else ctypes.c_void_p()
                    ret_doc = (
                        el_doc_local
                        if el_doc_local.value and el_doc_local.value not in (mejor_gen.value, ret_hit.value)
                        else ctypes.c_void_p()
                    )
                    self._liberar(el_hit_guardado)
                    self._liberar(el_doc_guardado)
                    return (mejor_gen, mejor_gen_rc, modo_gen, ret_hit, ret_doc)

                self._liberar(el_hit_guardado)
                self._liberar(el_doc_guardado)
                el_hit_guardado = el_hit
                el_doc_guardado = el_doc_local if el_doc_local.value != el_hit.value else ctypes.c_void_p()
                break

            return (ctypes.c_void_p(), (0, 0, 0, 0), 'ventana', el_hit_guardado, el_doc_guardado)
        finally:
            self._liberar(walker)

    def _buscar_documento_unico(self, uia, raiz) -> ctypes.c_void_p:
        cond = self._crear_condicion_i4(uia, _UIA_PROP_CONTROL_TYPE, _UIA_CTRL_DOCUMENT)
        if not cond.value:
            return ctypes.c_void_p()
        encontrado = ctypes.c_void_p()
        try:
            hr = self._vcall(
                raiz, 5, ctypes.c_long,
                [ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)],
                _UIA_TREESCOPE_DESCENDANTS, cond, ctypes.byref(encontrado),
            )
            return encontrado if hr == 0 else ctypes.c_void_p()
        finally:
            self._liberar(cond)

    def _construir_cache_request(self, uia) -> ctypes.c_void_p:
        req = ctypes.c_void_p()
        hr = self._vcall(uia, 20, ctypes.c_long, [ctypes.POINTER(ctypes.c_void_p)], ctypes.byref(req))
        if hr != 0 or not req.value:
            return ctypes.c_void_p()
        for prop_id in (
            _UIA_PROP_CONTROL_TYPE,
            _UIA_PROP_NAME,
            _UIA_PROP_AUTOMATION_ID,
            _UIA_PROP_IS_PASSWORD,
            _UIA_PROP_IS_OFFSCREEN,
            _UIA_PROP_BOUNDING_RECT,
        ):
            self._vcall(req, 3, ctypes.c_long, [ctypes.c_int], prop_id)
        return req

    def leer_ultimos_textos_con_diagnostico(
        self,
        hwnd: int,
        *,
        limite: int = _MAX_MENSAJES_CONSECUTIVOS,
        max_elementos: int = _MAX_ELEMENTOS_UIA,
        timeout_seg: float = _TIMEOUT_LECTURA_UIA_SEG,
        incluir_salientes: bool = False,
    ) -> DiagnosticoLectura:
        t0 = time.monotonic()
        deadline = t0 + max(0.3, float(timeout_seg))
        hwnd_int = int(hwnd)
        hwnd_render = hwnd_render_chat(hwnd_int)
        uso_render_hijo = (hwnd_render != hwnd_int)
        tope_mensajes = max(1, int(limite))
        tope_elementos = max(1, int(max_elementos))

        def _resultado(
            mensajes: list[str],
            *,
            metodo: str = 'ninguno',
            modo: str = 'ventana',
            nodos_fa: int = 0,
            nodos_filt: int = 0,
            offscreen: bool = False,
            text_pat: bool = False,
            chars_tp: int = 0,
        ) -> DiagnosticoLectura:
            return DiagnosticoLectura(
                mensajes=tuple(mensajes),
                duracion_ms=round((time.monotonic() - t0) * 1000.0, 2),
                hwnd_original=hwnd_int,
                hwnd_render=hwnd_render,
                uso_render_hijo=uso_render_hijo,
                metodo_contenedor=metodo,
                modo_area=modo,
                nodos_findall=nodos_fa,
                nodos_filtrados=nodos_filt,
                uso_fallback_offscreen=offscreen,
                uso_text_pattern=text_pat,
                chars_text_pattern=chars_tp,
            )

        hr_init = self._ole32.CoInitializeEx(None, _COINIT_MULTITHREADED)
        debe_desinicializar = hr_init in (0, 1)
        if hr_init < 0 and hr_init != _RPC_E_CHANGED_MODE:
            return _resultado([])

        uia = ctypes.c_void_p()
        raiz = ctypes.c_void_p()
        objetivo = ctypes.c_void_p()
        liberar_objetivo = False
        el_hit = ctypes.c_void_p()
        el_doc = ctypes.c_void_p()
        el_doc_buscado = ctypes.c_void_p()
        cond_text = ctypes.c_void_p()
        cond_item = ctypes.c_void_p()
        cond_or = ctypes.c_void_p()
        cache_req = ctypes.c_void_p()
        arr = ctypes.c_void_p()
        try:
            clsid = (ctypes.c_byte * 16).from_buffer_copy(_CLSID_CUIAUTOMATION)
            iid = (ctypes.c_byte * 16).from_buffer_copy(_IID_IUIAUTOMATION)
            hr = self._ole32.CoCreateInstance(
                ctypes.byref(clsid), None, _CLSCTX_INPROC_SERVER,
                ctypes.byref(iid), ctypes.byref(uia),
            )
            if hr != 0 or not uia.value:
                return _resultado([])

            hr = self._vcall(
                uia, 6, ctypes.c_long,
                [wintypes.HWND, ctypes.POINTER(ctypes.c_void_p)],
                wintypes.HWND(hwnd_render), ctypes.byref(raiz),
            )
            if (hr != 0 or not raiz.value) and uso_render_hijo:
                uso_render_hijo = False
                hwnd_render = hwnd_int
                hr = self._vcall(
                    uia, 6, ctypes.c_long,
                    [wintypes.HWND, ctypes.POINTER(ctypes.c_void_p)],
                    wintypes.HWND(hwnd_int), ctypes.byref(raiz),
                )
            if hr != 0 or not raiz.value:
                return _resultado([])

            rect_ventana = self._rect_elemento(raiz, cached=False)
            if (rect_ventana[2] - rect_ventana[0]) <= 20 or (rect_ventana[3] - rect_ventana[1]) <= 20:
                rect_ventana = rect_hwnd_win32(hwnd_int)

            cont_pt, rc_pt, modo_pt, el_hit, el_doc = self._localizar_por_punto(
                uia, hwnd_int, hwnd_render, rect_ventana, deadline
            )
            if cont_pt.value:
                objetivo, liberar_objetivo = cont_pt, True
                rect_area, modo_area, metodo = rc_pt, modo_pt, 'element_from_point'
            else:
                objetivo, liberar_objetivo = raiz, False
                rect_area, modo_area = rect_ventana, 'ventana'
                metodo = 'raiz_render' if uso_render_hijo else 'raiz'

            nodos: list[_NodoUIA] = []
            total_fa = 0
            if time.monotonic() < deadline:
                cond_text = self._crear_condicion_i4(uia, _UIA_PROP_CONTROL_TYPE, _UIA_CTRL_TEXT)
                cond_item = self._crear_condicion_i4(uia, _UIA_PROP_CONTROL_TYPE, _UIA_CTRL_LIST_ITEM)
                if cond_text.value and cond_item.value:
                    hr_or = self._vcall(
                        uia, 28, ctypes.c_long,
                        [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)],
                        cond_text, cond_item, ctypes.byref(cond_or),
                    )
                    if hr_or == 0 and cond_or.value:
                        usando_cache = False
                        cache_req = self._construir_cache_request(uia)
                        if cache_req.value:
                            hr_fa = self._vcall(
                                objetivo, 8, ctypes.c_long,
                                [ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)],
                                _UIA_TREESCOPE_DESCENDANTS, cond_or, cache_req, ctypes.byref(arr),
                            )
                            usando_cache = (hr_fa == 0 and bool(arr.value))
                        if not usando_cache and time.monotonic() < deadline:
                            hr_fa = self._vcall(
                                objetivo, 6, ctypes.c_long,
                                [ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)],
                                _UIA_TREESCOPE_DESCENDANTS, cond_or, ctypes.byref(arr),
                            )
                            if hr_fa != 0:
                                self._liberar(arr)
                                arr = ctypes.c_void_p()

                        if arr.value:
                            total_fa = self._leer_prop_int(arr, 3)
                            if total_fa > 0:
                                limites = _limites_area_chat(rect_area, modo_area=modo_area)
                                tiene_area = (
                                    (rect_area[2] - rect_area[0]) > 20
                                    and (rect_area[3] - rect_area[1]) > 20
                                )
                                prefiltrar_area = total_fa > tope_elementos and tiene_area
                                max_scan = 900 if (usando_cache and time.monotonic() >= deadline) else _MAX_NODOS_ESCANEADOS_UIA
                                inicio_scan = max(0, total_fa - max_scan)
                                deadline_cache = max(deadline, time.monotonic() + 0.45) if usando_cache else deadline
                                consultas_value = 0
                                for pos_idx, idx in enumerate(range(inicio_scan, total_fa)):
                                    if pos_idx > 0 and (pos_idx & 63) == 0 and time.monotonic() >= deadline_cache:
                                        break
                                    elem = ctypes.c_void_p()
                                    hr_get = self._vcall(
                                        arr, 4, ctypes.c_long,
                                        [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)],
                                        idx, ctypes.byref(elem),
                                    )
                                    if hr_get != 0 or not elem.value:
                                        continue
                                    try:
                                        if bool(self._leer_prop_int(elem, 67 if usando_cache else 35)):
                                            continue
                                        ctrl = self._leer_prop_int(elem, 53 if usando_cache else 21)
                                        if ctrl not in (_UIA_CTRL_TEXT, _UIA_CTRL_LIST_ITEM):
                                            continue
                                        rect = self._rect_elemento(elem, cached=usando_cache)
                                        if prefiltrar_area and not _rect_en_area_chat(
                                            rect,
                                            limites,
                                            tiene_area=True,
                                            es_listitem=(ctrl == _UIA_CTRL_LIST_ITEM),
                                            requerir_rect_no_vacio=False,
                                        ):
                                            continue
                                        fuera = bool(self._leer_prop_int(elem, 70 if usando_cache else 38))
                                        texto = self._leer_prop_str(elem, 55 if usando_cache else 23)
                                        if (
                                            not texto.strip()
                                            and ctrl == _UIA_CTRL_LIST_ITEM
                                            and consultas_value < 20
                                            and time.monotonic() < deadline
                                        ):
                                            consultas_value += 1
                                            texto = self._leer_value_pattern(elem)
                                        if not texto.strip():
                                            continue
                                        aid = self._leer_prop_str(elem, 61 if usando_cache else 29)
                                        nodos.append(_NodoUIA(
                                            texto=texto,
                                            tipo_control=ctrl,
                                            rect=rect,
                                            automation_id=aid,
                                            es_contrasena=False,
                                            fuera_pantalla=fuera,
                                        ))
                                    finally:
                                        self._liberar(elem)

            mensajes, uso_offscreen = _extraer_nodos_chat(
                nodos,
                rect_area,
                modo_area=modo_area,
                limite=tope_mensajes,
                max_elementos=tope_elementos,
                incluir_salientes=incluir_salientes,
            )
            if mensajes:
                return _resultado(
                    mensajes,
                    metodo=metodo,
                    modo=modo_area,
                    nodos_fa=total_fa,
                    nodos_filt=len(nodos),
                    offscreen=uso_offscreen,
                )

            deadline_tp = deadline + 0.4
            if time.monotonic() < deadline_tp:
                vistos_ptr: set[int] = set()
                candidatos_tp: list[ctypes.c_void_p] = []
                for cand in (objetivo, el_doc, el_hit, raiz):
                    if cand and cand.value and cand.value not in vistos_ptr:
                        vistos_ptr.add(cand.value)
                        candidatos_tp.append(cand)

                chars_tp = 0
                for cand in candidatos_tp:
                    if time.monotonic() >= deadline_tp:
                        break
                    texto_tp = self._leer_text_pattern(cand, max_chars=_MAX_CHARS_TEXT_PATTERN)
                    if texto_tp.strip():
                        chars_tp = max(chars_tp, len(texto_tp))
                        msgs_tp = _extraer_mensajes_de_texto_plano(
                            texto_tp,
                            limite=tope_mensajes,
                            incluir_salientes=incluir_salientes,
                        )
                        if msgs_tp:
                            return _resultado(
                                msgs_tp,
                                metodo=metodo,
                                modo=modo_area,
                                nodos_fa=total_fa,
                                nodos_filt=len(nodos),
                                text_pat=True,
                                chars_tp=len(texto_tp),
                            )

                if not el_doc.value and time.monotonic() < deadline_tp:
                    el_doc_buscado = self._buscar_documento_unico(uia, raiz)
                    if el_doc_buscado.value and el_doc_buscado.value not in vistos_ptr:
                        texto_tp = self._leer_text_pattern(el_doc_buscado, max_chars=_MAX_CHARS_TEXT_PATTERN)
                        if texto_tp.strip():
                            chars_tp = max(chars_tp, len(texto_tp))
                            msgs_tp = _extraer_mensajes_de_texto_plano(
                                texto_tp,
                                limite=tope_mensajes,
                                incluir_salientes=incluir_salientes,
                            )
                            if msgs_tp:
                                return _resultado(
                                    msgs_tp,
                                    metodo=metodo,
                                    modo=modo_area,
                                    nodos_fa=total_fa,
                                    nodos_filt=len(nodos),
                                    text_pat=True,
                                    chars_tp=len(texto_tp),
                                )

                return _resultado(
                    [],
                    metodo=metodo,
                    modo=modo_area,
                    nodos_fa=total_fa,
                    nodos_filt=len(nodos),
                    text_pat=chars_tp > 0,
                    chars_tp=chars_tp,
                )

            return _resultado([], metodo=metodo, modo=modo_area, nodos_fa=total_fa, nodos_filt=len(nodos))
        finally:
            self._liberar(arr)
            self._liberar(cache_req)
            self._liberar(cond_or)
            self._liberar(cond_item)
            self._liberar(cond_text)
            self._liberar(el_doc_buscado)
            self._liberar(el_doc)
            self._liberar(el_hit)
            if liberar_objetivo:
                self._liberar(objetivo)
            self._liberar(raiz)
            self._liberar(uia)
            if debe_desinicializar:
                self._ole32.CoUninitialize()

    def leer_ultimos_textos(
        self,
        hwnd: int,
        *,
        limite: int = _MAX_MENSAJES_CONSECUTIVOS,
        max_elementos: int = _MAX_ELEMENTOS_UIA,
        timeout_seg: float = _TIMEOUT_LECTURA_UIA_SEG,
        incluir_salientes: bool = False,
    ) -> list[str]:
        diag = self.leer_ultimos_textos_con_diagnostico(
            hwnd,
            limite=limite,
            max_elementos=max_elementos,
            timeout_seg=timeout_seg,
            incluir_salientes=incluir_salientes,
        )
        return list(diag.mensajes)

    def leer_ultimo_texto(self, hwnd: int, max_elementos: int = _MAX_ELEMENTOS_UIA) -> str | None:
        mensajes = self.leer_ultimos_textos(hwnd, limite=_MAX_MENSAJES_CONSECUTIVOS, max_elementos=max_elementos)
        if not mensajes:
            return None
        return '\n'.join(mensajes).strip()[:MAX_LARGO_MENSAJE] or None

    def enfocar_caja_mensaje(self, hwnd: int) -> bool:
        """Enfoca el cuadro de escritura de WhatsApp vía UIA SetFocus y/o clic seguro."""
        hr_init = self._ole32.CoInitializeEx(None, _COINIT_MULTITHREADED)
        debe_desinicializar = hr_init in (0, 1)
        if hr_init < 0 and hr_init != _RPC_E_CHANGED_MODE:
            return _clic_seguro_en_caja(int(hwnd), None)

        hwnd_render = hwnd_render_chat(int(hwnd))
        uia = ctypes.c_void_p()
        raiz = ctypes.c_void_p()
        cond_edit = ctypes.c_void_p()
        arr = ctypes.c_void_p()
        elementos_vivos: list[ctypes.c_void_p] = []
        foco_uia = False
        rc_caja: tuple[int, int, int, int] | None = None
        try:
            clsid = (ctypes.c_byte * 16).from_buffer_copy(_CLSID_CUIAUTOMATION)
            iid = (ctypes.c_byte * 16).from_buffer_copy(_IID_IUIAUTOMATION)
            hr = self._ole32.CoCreateInstance(
                ctypes.byref(clsid), None, _CLSCTX_INPROC_SERVER,
                ctypes.byref(iid), ctypes.byref(uia),
            )
            if hr == 0 and uia.value:
                hr = self._vcall(
                    uia, 6, ctypes.c_long,
                    [wintypes.HWND, ctypes.POINTER(ctypes.c_void_p)],
                    wintypes.HWND(hwnd_render), ctypes.byref(raiz),
                )
                if (hr != 0 or not raiz.value) and hwnd_render != int(hwnd):
                    hr = self._vcall(
                        uia, 6, ctypes.c_long,
                        [wintypes.HWND, ctypes.POINTER(ctypes.c_void_p)],
                        wintypes.HWND(int(hwnd)), ctypes.byref(raiz),
                    )

            if raiz.value:
                rect_ventana = self._rect_elemento(raiz, cached=False)
                cond_edit = self._crear_condicion_i4(uia, _UIA_PROP_CONTROL_TYPE, _UIA_CTRL_EDIT)
                if cond_edit.value:
                    hr_fa = self._vcall(
                        raiz, 6, ctypes.c_long,
                        [ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)],
                        _UIA_TREESCOPE_DESCENDANTS, cond_edit, ctypes.byref(arr),
                    )
                    if hr_fa == 0 and arr.value:
                        total = self._leer_prop_int(arr, 3)
                        candidatos: list[tuple[int, str, tuple[int, int, int, int]]] = []
                        candidatos_off: list[tuple[int, str, tuple[int, int, int, int]]] = []
                        for idx in range(min(max(0, total), 40)):
                            elem = ctypes.c_void_p()
                            hr_get = self._vcall(
                                arr, 4, ctypes.c_long,
                                [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)],
                                idx, ctypes.byref(elem),
                            )
                            if hr_get != 0 or not elem.value:
                                continue
                            if bool(self._leer_prop_int(elem, 35)):
                                self._liberar(elem)
                                continue
                            fuera = bool(self._leer_prop_int(elem, 38))
                            nombre = self._leer_prop_str(elem, 23)
                            rc = self._rect_elemento(elem, cached=False)
                            if fuera and (rc[2] <= rc[0] or rc[3] <= rc[1]):
                                self._liberar(elem)
                                continue
                            pos = len(elementos_vivos)
                            elementos_vivos.append(elem)
                            (candidatos_off if fuera else candidatos).append((pos, nombre, rc))

                        elegido = _seleccionar_caja_mensaje(candidatos, rect_ventana)
                        if elegido is None and candidatos_off:
                            elegido = _seleccionar_caja_mensaje(candidatos_off, rect_ventana)
                            lista_elegida = candidatos_off
                        else:
                            lista_elegida = candidatos
                        if elegido is not None:
                            for pos_e, _nom_e, rc_e in lista_elegida:
                                if pos_e == elegido:
                                    rc_caja = rc_e
                                    break
                            foco_uia = self._vcall(elementos_vivos[elegido], 3, ctypes.c_long, []) == 0

            clic_ok = _clic_seguro_en_caja(int(hwnd), rc_caja)
            return bool(foco_uia or clic_ok)
        finally:
            for elem in elementos_vivos:
                self._liberar(elem)
            self._liberar(arr)
            self._liberar(cond_edit)
            self._liberar(raiz)
            self._liberar(uia)
            if debe_desinicializar:
                self._ole32.CoUninitialize()


class LectorChat:
    """Detecta la ventana activa de WhatsApp, lee últimos mensajes y enfoca la caja de texto."""

    def _titulo_ventana(self, hwnd: int) -> str:
        if sys.platform != 'win32' or not hwnd:
            return ''
        try:
            u = _user32()
            if u is None:
                return ''
            largo = u.GetWindowTextLengthW(wintypes.HWND(int(hwnd)))
            if largo <= 0:
                return ''
            buf = ctypes.create_unicode_buffer(largo + 1)
            u.GetWindowTextW(wintypes.HWND(int(hwnd)), buf, largo + 1)
            return buf.value
        except (OSError, ctypes.ArgumentError, ValueError):
            return ''

    def rect_ventana(self, hwnd: int) -> tuple[int, int, int, int] | None:
        if sys.platform != 'win32' or not hwnd:
            return None
        try:
            u = _user32()
            if u is None:
                return None
            rect = wintypes.RECT()
            if not u.GetWindowRect(wintypes.HWND(int(hwnd)), ctypes.byref(rect)):
                return None
            ancho = int(rect.right - rect.left)
            alto = int(rect.bottom - rect.top)
            if ancho <= 0 or alto <= 0:
                return None
            return (int(rect.left), int(rect.top), ancho, alto)
        except (OSError, ctypes.ArgumentError, ValueError):
            return None

    def ventana_whatsapp_activa(self) -> VentanaChat | None:
        if sys.platform != 'win32':
            return None
        try:
            u = _user32()
            if u is None:
                return None
            hwnd = u.GetForegroundWindow()
            if not hwnd:
                return None
            largo = u.GetWindowTextLengthW(hwnd)
            if largo <= 0:
                return None
            buf = ctypes.create_unicode_buffer(largo + 1)
            u.GetWindowTextW(hwnd, buf, largo + 1)
            titulo = buf.value
            if not es_ventana_whatsapp(titulo):
                return None
            rect = self.rect_ventana(int(hwnd))
            if rect is None:
                return None
            return VentanaChat(hwnd=int(hwnd), titulo=titulo, rect=rect, tipo=_tipo_ventana(titulo))
        except (OSError, ctypes.ArgumentError, ValueError):
            return None

    def ventana_por_hwnd(self, hwnd: int) -> VentanaChat | None:
        """Valida un HWND previo contra la lista blanca y devuelve su VentanaChat con rect vivo."""
        if sys.platform != 'win32' or not hwnd:
            return None
        try:
            hwnd_int = int(hwnd)
            if hwnd_int <= 0:
                return None
            titulo = self._titulo_ventana(hwnd_int)
            if not es_ventana_whatsapp(titulo):
                return None
            rect = self.rect_ventana(hwnd_int)
            if rect is None:
                return None
            return VentanaChat(hwnd=hwnd_int, titulo=titulo, rect=rect, tipo=_tipo_ventana(titulo))
        except (OSError, ctypes.ArgumentError, ValueError):
            return None

    def diagnosticar_lectura(
        self, ventana: VentanaChat | None = None, limite: int = 3
    ) -> DiagnosticoLectura | None:
        """Ejecuta la lectura UIA devolviendo métricas en memoria (nunca persiste datos)."""
        if sys.platform != 'win32':
            return None
        try:
            objetivo = ventana if ventana is not None else self.ventana_whatsapp_activa()
            if objetivo is None or not es_ventana_whatsapp(objetivo.titulo) or objetivo.hwnd <= 0:
                return None
            return _LectorUIA().leer_ultimos_textos_con_diagnostico(int(objetivo.hwnd), limite=max(1, int(limite)))
        except Exception:
            return None

    def leer_ultimos_mensajes(
        self,
        ventana: VentanaChat | None = None,
        limite: int = 3,
        incluir_salientes: bool = False,
    ) -> list[str]:
        """Devuelve hasta `limite` mensajes limpios (en orden cronológico)."""
        if sys.platform != 'win32':
            return []
        try:
            objetivo = ventana if ventana is not None else self.ventana_whatsapp_activa()
            if objetivo is None or not es_ventana_whatsapp(objetivo.titulo) or objetivo.hwnd <= 0:
                return []
            tope = max(1, int(limite))
            crudos = _LectorUIA().leer_ultimos_textos(
                int(objetivo.hwnd), limite=tope, incluir_salientes=incluir_salientes
            )
            limpios = [
                item.strip()[:MAX_LARGO_MENSAJE]
                for item in (crudos or [])
                if isinstance(item, str) and item.strip()
            ]
            return limpios[-tope:]
        except Exception:
            return []

    def leer_ultimo_mensaje(self, ventana: VentanaChat | None = None) -> str | None:
        """Une los últimos mensajes entrantes con '\\n'."""
        mensajes = self.leer_ultimos_mensajes(ventana, limite=3)
        if not mensajes:
            return None
        return '\n'.join(mensajes).strip()[:MAX_LARGO_MENSAJE] or None

    def enfocar_caja_mensaje(self, hwnd: int) -> bool:
        """Enfoca el campo de mensaje de WhatsApp vía UIA SetFocus sin lanzar excepciones."""
        if sys.platform != 'win32' or not hwnd:
            return False
        try:
            hwnd_int = int(hwnd)
            if hwnd_int <= 0 or not es_ventana_whatsapp(self._titulo_ventana(hwnd_int)):
                return False
            return bool(_LectorUIA().enfocar_caja_mensaje(hwnd_int))
        except Exception:
            return False
