"""Asistente en vivo para WhatsApp: debounce, deduplicación y contexto en memoria.

Privacidad y seguridad:
- Opt-in por defecto: inicia pausado (activo = False).
- Nunca guarda conversaciones en SQLite ni en archivos de disco; para
  deduplicación solo conserva huellas SHA-256 efímeras en memoria con TTL.
- Reutiliza RecomendadorIA.sugerir sin modificar la Edge Function fraseya-ia.
- Solo sugiere frases aprobadas del catálogo; nunca envía mensajes ni inventa
  respuestas sin revisión cuando el recomendador devuelve lista vacía.
"""
from collections import deque
from dataclasses import dataclass
import hashlib
import re
import threading
import time

from fraseya.aplicacion.buscador import normalizar

MAX_LARGO_MENSAJE = 4000
MAX_OPCIONES_VIVO = 3
_TTL_DEDUP_SEG = 60.0
_MAX_CHATS_MEMORIA = 24
_MAX_HUELLAS_POR_CHAT = 40

TONOS_OPCION: tuple[tuple[str, str], ...] = (
    ('empatica', 'Empática'),
    ('directa', 'Directa'),
    ('escalar', 'Escalar'),
)

_TEMAS_CLAVES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ('Facturación / Cobro', (
        'factura', 'boleta', 'cobro', 'cobraron', 'cobrar', 'pago', 'pagar',
        'reembolso', 'devolucion', 'cargo', 'tarjeta', 'transferencia', 'cuota',
        'descuento', 'precio', 'cotizacion', 'presupuesto', 'comprobante',
        'monto', 'duplicado', 'doble cobro', 'cobraron doble',
    )),
    ('Pedido / Envío', (
        'pedido', 'envio', 'despacho', 'entrega', 'paquete', 'tracking',
        'seguimiento', 'encomienda', 'courier', 'sucursal', 'retiro',
        'demora', 'retraso', 'atraso', 'direccion', 'orden', 'no llega',
        'no llego', 'llega', 'llego',
    )),
    ('Soporte técnico', (
        'error', 'falla', 'problema', 'no funciona', 'caido', 'acceso',
        'ingresar', 'clave', 'contrasena', 'login', 'cuenta', 'bloquear',
        'bloqueada', 'bloqueado', 'app', 'sistema', 'pantalla', 'bug',
        'actualizar', 'instalar', 'tecnico', 'soporte', 'configuracion',
    )),
    ('Cancelación / Cambio', (
        'cancelar', 'anulacion', 'anular', 'dar de baja', 'cambiar', 'cambio',
        'garantia', 'roto', 'danado', 'defectuoso', 'equivocado',
    )),
)

_ANIMO_MOLESTO: tuple[str, ...] = (
    'molesto', 'molesta', 'enojado', 'enojada', 'furioso', 'furiosa',
    'indignado', 'indignada', 'harto', 'harta', 'cansado', 'cansada',
    'pesimo', 'pesima', 'horrible', 'terrible', 'estafa', 'verguenza',
    'inaceptable', 'reclamo', 'sernac', 'demanda', 'queja', 'nadie responde',
    'mal servicio', 'decepcion', 'decepcionado', 'basta', 'desastre',
    'abusivo', 'robo', 'una burla',
)

_ANIMO_APURADO: tuple[str, ...] = (
    'urgente', 'urgencia', 'rapido', 'ahora mismo', 'hoy mismo', 'para hoy',
    'inmediato', 'inmediatamente', 'cuanto antes', 'apuro', 'apurado',
    'apurada', 'necesito ya', 'pronto', 'hace horas', 'hace dias',
    'esperando', 'todavia no', 'aun no', 'sigo esperando', 'lleva dias',
)

_ANIMO_POSITIVO: tuple[str, ...] = (
    'gracias', 'muchas gracias', 'excelente', 'genial', 'perfecto', 'super',
    'encantado', 'encantada', 'feliz', 'contento', 'contenta', 'amable',
    'buen servicio', 'agradecido', 'agradecida', 'felicitaciones',
)

_URGENCIA_ALTA: tuple[str, ...] = (
    'urgente', 'urgencia', 'inmediato', 'inmediatamente', 'hoy mismo',
    'ahora mismo', 'emergencia', 'bloqueado', 'bloqueada', 'doble cobro',
    'cobraron doble', 'cobro duplicado', 'estafa', 'sernac', 'demanda',
    'no funciona', 'caido', 'roto', 'danado', 'hace dias', 'para hoy',
)

_URGENCIA_MEDIA: tuple[str, ...] = (
    'retraso', 'demora', 'atraso', 'problema', 'error', 'falla', 'esperando',
    'todavia no', 'aun no', 'reembolso', 'devolucion', 'cambio', 'cancelar',
    'reclamo', 'factura', 'cobro', 'pago', 'pedido', 'envio', 'despacho',
)


@dataclass(frozen=True)
class OpcionFlotante:
    indice: int
    etiqueta: str
    tono: str  # 'empatica' | 'directa' | 'escalar'
    frase: dict
    motivo: str


@dataclass(frozen=True)
class ResultadoVivo:
    tema: str
    animo: str
    urgencia: str
    opciones: tuple[OpcionFlotante, ...]
    mensaje_origen: str


def _contiene_termino(texto_norm: str, termino: str) -> bool:
    return re.search(rf'\b{re.escape(termino)}\b', texto_norm) is not None


def _contar_coincidencias(texto_norm: str, terminos: tuple[str, ...]) -> int:
    return sum(1 for t in terminos if _contiene_termino(texto_norm, t))


def _grito_mayusculas(texto_original: str) -> bool:
    letras = [c for c in texto_original if c.isalpha()]
    if len(letras) < 10:
        return False
    mayus = sum(1 for c in letras if c.isupper())
    return (mayus / len(letras)) >= 0.7


def clasificar_contexto(texto: str) -> tuple[str, str, str]:
    """Heurística ligera en español que infiere (tema, animo, urgencia)."""
    if not isinstance(texto, str) or not texto.strip():
        return ('Consulta general', 'Neutral', 'Normal')

    norm = normalizar(texto)

    # Tema por mayor cantidad de coincidencias.
    tema = 'Consulta general'
    mejor_puntaje = 0
    for nombre_tema, claves in _TEMAS_CLAVES:
        puntaje = _contar_coincidencias(norm, claves)
        if puntaje > mejor_puntaje:
            mejor_puntaje = puntaje
            tema = nombre_tema

    # Ánimo del cliente.
    exclamaciones = '!!' in texto
    if _contar_coincidencias(norm, _ANIMO_MOLESTO) > 0 or _grito_mayusculas(texto) or exclamaciones:
        animo = 'Molesto'
    elif _contar_coincidencias(norm, _ANIMO_APURADO) > 0:
        animo = 'Apurado'
    elif _contar_coincidencias(norm, _ANIMO_POSITIVO) > 0:
        animo = 'Positivo'
    else:
        animo = 'Neutral'

    # Nivel de urgencia.
    if animo == 'Molesto' or _contar_coincidencias(norm, _URGENCIA_ALTA) > 0:
        urgencia = 'Alta'
    elif animo == 'Apurado' or _contar_coincidencias(norm, _URGENCIA_MEDIA) > 0:
        urgencia = 'Media'
    else:
        urgencia = 'Normal'

    return (tema, animo, urgencia)


def _limpiar_texto(texto: str) -> str:
    if not isinstance(texto, str):
        return ''
    lineas = [linea.strip() for linea in texto.splitlines()]
    return '\n'.join(l for l in lineas if l).strip()


def _huella(texto: str) -> str:
    canonico = ' '.join(texto.strip().split()).casefold()
    return hashlib.sha256(canonico.encode('utf-8')).hexdigest()


def _envolver_sugerencias(sugerencias) -> tuple[OpcionFlotante, ...]:
    opciones = []
    for idx, sug in enumerate(list(sugerencias)[:MAX_OPCIONES_VIVO], start=1):
        tono, nombre_tono = TONOS_OPCION[idx - 1]
        frase = dict(sug.frase) if isinstance(sug.frase, dict) else {}
        motivo = str(getattr(sug, 'motivo', '') or '').strip()
        opciones.append(OpcionFlotante(
            indice=idx,
            etiqueta=f'Opción {idx} · {nombre_tono}',
            tono=tono,
            frase=frase,
            motivo=motivo,
        ))
    return tuple(opciones)


_PREFIJOS_SALUDO = (
    'hola', '¡hola', 'buenos', 'buenas', 'estimad', 'gracias', 'lament', 'disculp', 'entendemos',
)
_RE_TURNO_AGENTE = re.compile(r'(?im)^agente\s*:\s*\S')
_RE_LINEA_TURNO = re.compile(r'^(cliente|agente)\s*:\s*(.*)$', re.IGNORECASE)
_RE_ITEM_LISTA = re.compile(r'(?m)^\s*(?:\d+[.)]|[-•*])\s+\S')
_GRUPOS_CONSULTA_COMPUESTA: tuple[tuple[str, ...], ...] = (
    ('pagina web', 'sitio web', 'landing', 'tienda online', 'ecommerce', 'e-commerce', 'web corporativa'),
    ('hosting', 'dominio', 'velocidad', 'webp', 'responsive', 'mobile-first', 'mantenimiento'),
    ('automatizacion', 'automatizar', 'chatbot', 'chat bot', 'bot', 'agenda automatica', 'n8n', 'make'),
    ('software a medida', 'sistema', 'crm', 'erp', 'saas', 'aplicacion'),
)


def es_consulta_compuesta(texto: str) -> bool:
    """True cuando el cliente consulta varios puntos técnicos o servicios a la vez."""
    if not isinstance(texto, str) or not texto.strip():
        return False
    solo_cliente = extraer_texto_cliente(texto)
    if len(_RE_ITEM_LISTA.findall(solo_cliente)) >= 2:
        return True
    norm = normalizar(texto)
    grupos_activos = sum(
        1 for grupo in _GRUPOS_CONSULTA_COMPUESTA
        if any(termino in norm for termino in grupo)
    )
    return grupos_activos >= 2


def es_primer_contacto(texto: str) -> bool:
    """True si no se detectan respuestas previas del agente en la conversación."""
    if not isinstance(texto, str) or not texto.strip():
        return True
    return _RE_TURNO_AGENTE.search(texto) is None


def extraer_texto_cliente(texto: str) -> str:
    """Extrae los mensajes del cliente para clasificar tema/ánimo sin sesgo del agente."""
    if not isinstance(texto, str) or not texto.strip():
        return ''
    lineas = texto.splitlines()
    tiene_etiquetas = any(_RE_LINEA_TURNO.match(l.strip()) for l in lineas if l.strip())
    if not tiene_etiquetas:
        return texto.strip()

    despues_ultimo_agente: list[str] = []
    todos_cliente: list[str] = []
    rol_actual = 'cliente'
    for linea in lineas:
        limpia = linea.strip()
        if not limpia:
            continue
        m = _RE_LINEA_TURNO.match(limpia)
        if m:
            rol_actual = m.group(1).casefold()
            cuerpo = m.group(2).strip()
        else:
            cuerpo = limpia
        if not cuerpo:
            continue
        if rol_actual == 'agente':
            despues_ultimo_agente.clear()
        else:
            todos_cliente.append(cuerpo)
            despues_ultimo_agente.append(cuerpo)

    elegidos = despues_ultimo_agente or todos_cliente
    return '\n'.join(elegidos).strip() or texto.strip()


def _variar_por_tono(
    contenido: str,
    tono: str,
    animo: str = 'Neutral',
    es_primer_contacto_chat: bool = True,
) -> str:
    """Genera una variante breve y natural en español según tono, sin llamadas extra."""
    base = (contenido or '').strip()
    if not base:
        return ''
    bajo = base.casefold()
    tiene_saludo = any(bajo.startswith(pref) for pref in _PREFIJOS_SALUDO)
    if tono == 'empatica':
        if animo == 'Molesto':
            if bajo.startswith(('entend', 'lament', 'disculp')):
                texto = f'{base} Con gusto te ayudamos.' if 'con gusto' not in bajo else base
            else:
                texto = f'Entendemos tu molestia. {base}'
        elif es_primer_contacto_chat and not tiene_saludo:
            texto = f'¡Hola! {base}'
        elif 'con gusto' not in bajo:
            texto = f'{base} Con gusto te ayudamos.'
        else:
            texto = f'{base} Quedamos atentos para ayudarte.'
        return texto[:MAX_LARGO_MENSAJE]
    if tono == 'directa':
        return base[:MAX_LARGO_MENSAJE]
    # tono == 'escalar' (seguimiento / derivación breve)
    if base.endswith('?'):
        texto = f'{base} ¿Lo revisamos con un asesor?'
    else:
        texto = f'{base} ¿Te gustaría que un asesor te oriente?'
    return texto[:MAX_LARGO_MENSAJE]


def _construir_tres_borradores_ia(
    generada: dict,
    animo: str = 'Neutral',
    es_primer_contacto_chat: bool = True,
) -> tuple[OpcionFlotante, ...]:
    """A partir de un único borrador IA, construye 3 opciones flotantes diferenciadas por tono."""
    titulo = str(generada.get('titulo') or 'Propuesta IA').strip()[:200]
    categoria = str(generada.get('categoria') or 'General').strip()[:200]
    base = str(generada.get('contenido') or '').strip()[:MAX_LARGO_MENSAJE]
    motivos = (
        'Borrador generado por IA (tono empático y cercano). Revísalo antes de usar.',
        'Borrador generado por IA (tono directo y conciso). Revísalo antes de usar.',
        'Borrador generado por IA (seguimiento o derivación). Revísalo antes de usar.',
    )
    opciones: list[OpcionFlotante] = []
    for idx, (tono, nombre_tono) in enumerate(TONOS_OPCION, start=1):
        variante = _variar_por_tono(
            base,
            tono,
            animo=animo,
            es_primer_contacto_chat=es_primer_contacto_chat,
        )
        frase_borrador = {
            'id': -idx,
            'titulo': titulo,
            'categoria': categoria,
            'contenido': variante,
            'origen': 'borrador_ia',
        }
        opciones.append(OpcionFlotante(
            indice=idx,
            etiqueta=f'Propuesta IA · Revisar ({nombre_tono})',
            tono=tono,
            frase=frase_borrador,
            motivo=motivos[idx - 1],
        ))
    return tuple(opciones)


def _rankear_frases_relevantes(texto: str, frases: list[dict]) -> list[dict]:
    palabras = set(re.findall(r'\w{3,}', normalizar(texto)))

    def _clave(f: dict):
        cuerpo = normalizar(' '.join(str(f.get(c, '')) for c in ('titulo', 'categoria', 'contenido')))
        coincidencias = len(palabras & set(re.findall(r'\w{3,}', cuerpo)))
        return (-coincidencias, not f.get('favorita', False), str(f.get('titulo', '')), f.get('id', 0))

    validas = [
        dict(f) for f in (frases or [])
        if isinstance(f, dict) and isinstance(f.get('contenido'), str) and f['contenido'].strip()
    ]
    validas.sort(key=_clave)
    return validas


def crear_resultado_demo(frases: list[dict]) -> ResultadoVivo:
    """Construye un ResultadoVivo realista para probar las tarjetas flotantes al instante."""
    mensaje_demo = 'Hola, mi pedido #4821 lleva 3 días de retraso y lo necesito urgente para hoy.'
    tema, animo, urgencia = clasificar_contexto(mensaje_demo)

    motivos_demo = (
        'Muestra cercanía y valida la urgencia del cliente.',
        'Entrega información clara y concreta para resolver rápido.',
        'Propone derivación prioritaria para destrabar el caso.',
    )
    catalogo_valido = [
        dict(f) for f in (frases or [])
        if isinstance(f, dict) and isinstance(f.get('contenido'), str) and f['contenido'].strip()
    ]
    catalogo_valido.sort(key=lambda f: (not f.get('favorita', False), str(f.get('titulo', ''))))

    if catalogo_valido:
        seleccion = catalogo_valido[:MAX_OPCIONES_VIVO]
    else:
        seleccion = [
            {
                'id': -1,
                'titulo': 'Ejemplo · Disculpa por demora',
                'abreviatura': '!demo1',
                'categoria': 'Demo',
                'origen': 'demo',
                'contenido': (
                    'Lamentamos mucho la demora con tu pedido. Ya estamos revisando '
                    'el estado con prioridad para darte una solución hoy mismo.'
                ),
            },
            {
                'id': -2,
                'titulo': 'Ejemplo · Seguimiento directo',
                'abreviatura': '!demo2',
                'categoria': 'Demo',
                'origen': 'demo',
                'contenido': (
                    'Por favor compártenos tu número de orden y correo para confirmar '
                    'de inmediato la fecha y horario exacto de entrega.'
                ),
            },
            {
                'id': -3,
                'titulo': 'Ejemplo · Derivación prioritaria',
                'abreviatura': '!demo3',
                'categoria': 'Demo',
                'origen': 'demo',
                'contenido': (
                    'Derivamos tu caso con prioridad al equipo de logística para agilizar '
                    'el despacho y te contactaremos apenas tengamos confirmación.'
                ),
            },
        ]

    opciones = []
    for idx, frase in enumerate(seleccion, start=1):
        tono, nombre_tono = TONOS_OPCION[idx - 1]
        opciones.append(OpcionFlotante(
            indice=idx,
            etiqueta=f'Opción {idx} · {nombre_tono}',
            tono=tono,
            frase=frase,
            motivo=motivos_demo[idx - 1],
        ))

    return ResultadoVivo(
        tema=tema,
        animo=animo,
        urgencia=urgencia,
        opciones=tuple(opciones),
        mensaje_origen=mensaje_demo,
    )


class ServicioAsistenteVivo:
    """Coordina lectura continua opt-in, agrupación de ráfagas y análisis manual."""

    def __init__(
        self,
        recomendador,
        obtener_frases,
        al_resultado,
        al_error=None,
        debounce_seg: float = 1.5,
        al_analizar=None,
    ):
        self._recomendador = recomendador
        self._obtener_frases = obtener_frases
        self._al_resultado = al_resultado
        self._al_error = al_error
        self._al_analizar = al_analizar
        self.debounce_seg: float = max(0.0, float(debounce_seg))
        self.activo: bool = False  # Opt-in por defecto

        self._candado = threading.Lock()
        self._epoca: int = 0
        self._detenido: bool = False
        self._pendientes: dict[str, list[str]] = {}
        self._timers: dict[str, threading.Timer] = {}
        self._recientes: dict[str, deque[tuple[str, float]]] = {}
        self._buffer_mensajes: dict[str, deque[str]] = {}
        self._ultimo_chat_buffer: str = ''

    def activar(self) -> None:
        with self._candado:
            self._detenido = False
            self.activo = True

    def pausar(self) -> None:
        with self._candado:
            self.activo = False
            self._epoca += 1
            timers = list(self._timers.values())
            self._timers.clear()
            self._pendientes.clear()
        for t in timers:
            t.cancel()

    def detener(self) -> None:
        with self._candado:
            self.activo = False
            self._detenido = True
            self._epoca += 1
            timers = list(self._timers.values())
            self._timers.clear()
            self._pendientes.clear()
            self._recientes.clear()
            self._buffer_mensajes.clear()
            self._ultimo_chat_buffer = ''
        for t in timers:
            t.cancel()

    def registrar_turno(
        self,
        texto: str,
        rol: str = 'cliente',
        chat: str = '',
        turnos: list[dict] | None = None,
    ) -> bool:
        """Guarda turnos recientes ('Cliente:' / 'Agente:') en el búfer efímero en memoria."""
        rol_norm = 'agente' if str(rol or '').strip().casefold() == 'agente' else 'cliente'
        limpio = _limpiar_texto(texto)
        if not turnos and (not limpio or len(limpio) > MAX_LARGO_MENSAJE):
            return False

        entradas: list[str] = []
        if isinstance(turnos, list) and turnos:
            for item in turnos[-8:]:
                if not isinstance(item, dict):
                    continue
                t_txt = _limpiar_texto(str(item.get('texto') or ''))
                if not t_txt or len(t_txt) > MAX_LARGO_MENSAJE:
                    continue
                t_rol = 'Agente' if str(item.get('rol') or '').strip().casefold() == 'agente' else 'Cliente'
                etiquetado = f'{t_rol}: {t_txt}'[:MAX_LARGO_MENSAJE]
                if not entradas or _huella(entradas[-1]) != _huella(etiquetado):
                    entradas.append(etiquetado)
        if not entradas:
            if not limpio or len(limpio) > MAX_LARGO_MENSAJE:
                return False
            pref = 'Agente' if rol_norm == 'agente' else 'Cliente'
            entradas = [f'{pref}: {limpio}'[:MAX_LARGO_MENSAJE]]

        clave_chat = (chat or '').strip().casefold()
        with self._candado:
            if self._detenido:
                return False
            cola = self._buffer_mensajes.get(clave_chat)
            if cola is None:
                if len(self._buffer_mensajes) >= _MAX_CHATS_MEMORIA:
                    mas_antiguo = next(iter(self._buffer_mensajes))
                    self._buffer_mensajes.pop(mas_antiguo, None)
                cola = deque(maxlen=8)
                self._buffer_mensajes[clave_chat] = cola
            if len(entradas) > 1:
                cola.clear()
                cola.extend(entradas)
            else:
                etiquetado = entradas[0]
                if not cola or _huella(cola[-1]) != _huella(etiquetado):
                    cola.append(etiquetado)
            self._ultimo_chat_buffer = clave_chat
        return True

    def registrar_mensaje_entrante(self, texto: str, chat: str = '') -> bool:
        """Guarda un mensaje entrante en el búfer efímero en memoria (sin llamar a la IA)."""
        limpio = _limpiar_texto(texto)
        if not limpio or len(limpio) > MAX_LARGO_MENSAJE:
            return False
        clave_chat = (chat or '').strip().casefold()
        with self._candado:
            if self._detenido:
                return False
            cola = self._buffer_mensajes.get(clave_chat)
            if cola is None:
                if len(self._buffer_mensajes) >= _MAX_CHATS_MEMORIA:
                    mas_antiguo = next(iter(self._buffer_mensajes))
                    self._buffer_mensajes.pop(mas_antiguo, None)
                cola = deque(maxlen=8)
                self._buffer_mensajes[clave_chat] = cola
            if not cola or _huella(cola[-1]) != _huella(limpio):
                cola.append(limpio)
            self._ultimo_chat_buffer = clave_chat
        return True

    def obtener_ultimos_mensajes(self, chat: str = '', limite: int = 3) -> list[str]:
        """Devuelve hasta `limite` últimos mensajes entrantes del búfer en memoria."""
        tope = max(1, int(limite))
        clave_pedida = (chat or '').strip().casefold()
        with self._candado:
            clave = clave_pedida if clave_pedida else self._ultimo_chat_buffer
            cola = self._buffer_mensajes.get(clave)
            if not cola and not clave_pedida:
                for c in reversed(list(self._buffer_mensajes.values())):
                    if c:
                        cola = c
                        break
            if not cola:
                return []
            return list(cola)[-tope:]

    def _purgar_recientes_locked(self, clave_chat: str, ahora: float) -> deque[tuple[str, float]]:
        cola = self._recientes.get(clave_chat)
        if cola is None:
            if len(self._recientes) >= _MAX_CHATS_MEMORIA:
                mas_antiguo = next(iter(self._recientes))
                self._recientes.pop(mas_antiguo, None)
            cola = deque(maxlen=_MAX_HUELLAS_POR_CHAT)
            self._recientes[clave_chat] = cola
            return cola
        while cola and (ahora - cola[0][1]) > _TTL_DEDUP_SEG:
            cola.popleft()
        return cola

    def _fue_procesado_locked(self, clave_chat: str, texto: str, ahora: float) -> bool:
        cola = self._purgar_recientes_locked(clave_chat, ahora)
        h = _huella(texto)
        return any(item_h == h for item_h, _ in cola)

    def _registrar_procesado_locked(self, clave_chat: str, textos: list[str], ahora: float) -> None:
        cola = self._purgar_recientes_locked(clave_chat, ahora)
        existentes = {item_h for item_h, _ in cola}
        for t in textos:
            h = _huella(t)
            if h not in existentes:
                cola.append((h, ahora))
                existentes.add(h)

    def recibir_mensaje(self, texto: str, chat: str = '', inmediato: bool = False) -> bool:
        """Recibe un mensaje entrante si el asistente está activo.

        Deduplica repeticiones recientes por chat y agrupa ráfagas durante
        debounce_seg antes de consultar RecomendadorIA en un hilo daemon.
        """
        limpio = _limpiar_texto(texto)
        if not limpio:
            return False

        clave_chat = (chat or '').strip().casefold()
        timer_anterior = None
        despachar_ahora: tuple[str, int] | None = None

        with self._candado:
            if not self.activo or self._detenido:
                return False
            ahora = time.monotonic()
            if self._fue_procesado_locked(clave_chat, limpio, ahora):
                return False

            cola_chat = self._pendientes.setdefault(clave_chat, [])
            huella_nueva = _huella(limpio)
            if any(_huella(existente) == huella_nueva for existente in cola_chat):
                return False
            cola_chat.append(limpio)

            timer_anterior = self._timers.pop(clave_chat, None)
            if inmediato or self.debounce_seg == 0:
                fragmentos = self._pendientes.pop(clave_chat, [])
                agrupado = '\n'.join(fragmentos)[-MAX_LARGO_MENSAJE:].strip()
                if not agrupado or self._fue_procesado_locked(clave_chat, agrupado, ahora):
                    despachar_ahora = None
                else:
                    self._registrar_procesado_locked(clave_chat, [*fragmentos, agrupado], ahora)
                    despachar_ahora = (agrupado, self._epoca)
            else:
                epoca_actual = self._epoca
                nuevo_timer = threading.Timer(
                    self.debounce_seg,
                    self._disparar_rafaga,
                    args=(clave_chat, epoca_actual),
                )
                nuevo_timer.daemon = True
                self._timers[clave_chat] = nuevo_timer
                nuevo_timer.start()

        if timer_anterior is not None:
            timer_anterior.cancel()

        if despachar_ahora is not None:
            texto_final, epoca_envio = despachar_ahora
            self._lanzar_hilo_consulta(texto_final, epoca=epoca_envio, exigir_activo=True)

        return True

    def _disparar_rafaga(self, clave_chat: str, epoca_esperada: int) -> None:
        with self._candado:
            if not self.activo or self._detenido or epoca_esperada != self._epoca:
                self._pendientes.pop(clave_chat, None)
                self._timers.pop(clave_chat, None)
                return
            self._timers.pop(clave_chat, None)
            fragmentos = self._pendientes.pop(clave_chat, [])
            if not fragmentos:
                return
            agrupado = '\n'.join(fragmentos)[-MAX_LARGO_MENSAJE:].strip()
            ahora = time.monotonic()
            if not agrupado or self._fue_procesado_locked(clave_chat, agrupado, ahora):
                return
            self._registrar_procesado_locked(clave_chat, [*fragmentos, agrupado], ahora)
            epoca_actual = self._epoca

        self._lanzar_hilo_consulta(agrupado, epoca=epoca_actual, exigir_activo=True)

    def analizar_mensajes(self, mensajes: list[str], *, asincrono: bool = True):
        """Analiza bajo demanda hasta los últimos 3 mensajes entrantes y garantiza 3 opciones."""
        with self._candado:
            if self._detenido:
                return None
            epoca = self._epoca

        if isinstance(mensajes, str):
            crudos = [mensajes]
        elif isinstance(mensajes, (list, tuple)):
            crudos = list(mensajes)
        else:
            self._notificar_error('No hay mensajes válidos para analizar.')
            return None

        limpios = [_limpiar_texto(m) for m in crudos if isinstance(m, str) and _limpiar_texto(m)]
        ultimos = limpios[-8:]
        if not ultimos:
            self._notificar_error('No se detectaron mensajes visibles en el chat.')
            return None

        texto = '\n'.join(ultimos).strip()
        if len(texto) > MAX_LARGO_MENSAJE:
            texto = texto[-MAX_LARGO_MENSAJE:].strip()
        if not texto:
            self._notificar_error('No se detectaron mensajes visibles en el chat.')
            return None

        if asincrono:
            return self._lanzar_hilo_consulta(texto, epoca=epoca, exigir_activo=False)
        return self._ejecutar_consulta(texto, epoca=epoca, exigir_activo=False)

    def analizar_manual(self, texto: str, *, asincrono: bool = True):
        """Plan B manual (atajo/portapapeles): analiza de inmediato sin requerir modo activo."""
        with self._candado:
            if self._detenido:
                return None
            epoca = self._epoca

        if not isinstance(texto, str) or not texto.strip() or len(texto) > MAX_LARGO_MENSAJE:
            self._notificar_error('Copia o escribe un mensaje de entre 1 y 4.000 caracteres.')
            return None

        limpio = _limpiar_texto(texto)
        if not limpio or len(limpio) > MAX_LARGO_MENSAJE:
            self._notificar_error('Copia o escribe un mensaje de entre 1 y 4.000 caracteres.')
            return None

        if asincrono:
            return self._lanzar_hilo_consulta(limpio, epoca=epoca, exigir_activo=False)
        return self._ejecutar_consulta(limpio, epoca=epoca, exigir_activo=False)

    def _lanzar_hilo_consulta(self, texto: str, *, epoca: int, exigir_activo: bool) -> threading.Thread:
        hilo = threading.Thread(
            target=self._ejecutar_consulta,
            args=(texto,),
            kwargs={'epoca': epoca, 'exigir_activo': exigir_activo},
            name='fraseya-asistente-vivo',
            daemon=True,
        )
        hilo.start()
        return hilo

    def _puede_emitir(self, epoca: int, exigir_activo: bool) -> bool:
        with self._candado:
            if self._detenido:
                return False
            if exigir_activo and (not self.activo or epoca != self._epoca):
                return False
            return True

    def _generar_borrador_crudo(self, texto: str, frases: list[dict]) -> tuple[dict | None, str | None]:
        generar = getattr(self._recomendador, 'generar', None)
        if not callable(generar):
            return None, None
        try:
            generada = generar(texto, frases)
        except Exception as error:
            return None, str(error) or 'No se pudo generar un borrador con IA.'
        if not isinstance(generada, dict):
            return None, None
        contenido = generada.get('contenido')
        if not isinstance(contenido, str) or not contenido.strip():
            return None, None
        return generada, None

    def _completar_hasta_tres(
        self,
        opciones_base: tuple[OpcionFlotante, ...],
        texto: str,
        frases: list[dict],
        animo: str,
        *,
        texto_busqueda: str | None = None,
        es_primer_contacto_chat: bool = True,
    ) -> tuple[OpcionFlotante, ...]:
        """Completa 1 o 2 opciones hasta 3 usando a lo sumo 1 llamada a generar y/o catálogo."""
        lista = list(opciones_base)[:MAX_OPCIONES_VIVO]
        if len(lista) >= MAX_OPCIONES_VIVO:
            return tuple(lista)

        usados_id = {op.frase.get('id') for op in lista if op.frase.get('id') is not None}
        usados_txt = {_huella(str(op.frase.get('contenido') or '')) for op in lista}

        # 1. A lo sumo 1 llamada a generar(...) para aportar una propuesta contextualizada
        generada, _err = self._generar_borrador_crudo(texto, frases)
        if generada is not None and len(lista) < MAX_OPCIONES_VIVO:
            idx = len(lista) + 1
            tono, nombre_tono = TONOS_OPCION[idx - 1]
            contenido_gen = str(generada.get('contenido') or '').strip()[:MAX_LARGO_MENSAJE]
            if contenido_gen and _huella(contenido_gen) not in usados_txt:
                frase_borrador = {
                    'id': -idx,
                    'titulo': str(generada.get('titulo') or 'Propuesta IA').strip()[:200],
                    'categoria': str(generada.get('categoria') or 'General').strip()[:200],
                    'contenido': contenido_gen,
                    'origen': 'borrador_ia',
                }
                lista.append(OpcionFlotante(
                    indice=idx,
                    etiqueta=f'Propuesta IA · Revisar ({nombre_tono})',
                    tono=tono,
                    frase=frase_borrador,
                    motivo='Borrador generado por IA para complementar tus opciones. Revísalo antes de usar.',
                ))
                usados_txt.add(_huella(contenido_gen))
                # Si aún falta la 3ª tarjeta, crea una variante de tono de la propia propuesta IA
                # para no mezclar otro tema distinto desde el catálogo.
                while len(lista) < MAX_OPCIONES_VIVO:
                    idx_var = len(lista) + 1
                    tono_var, nombre_var = TONOS_OPCION[idx_var - 1]
                    variante_gen = (
                        _variar_por_tono(
                            contenido_gen,
                            tono_var,
                            animo=animo,
                            es_primer_contacto_chat=es_primer_contacto_chat,
                        )
                        or contenido_gen
                    )
                    if _huella(variante_gen) in usados_txt:
                        break
                    lista.append(OpcionFlotante(
                        indice=idx_var,
                        etiqueta=f'Propuesta IA · Revisar ({nombre_var})',
                        tono=tono_var,
                        frase={
                            **frase_borrador,
                            'id': -idx_var,
                            'contenido': variante_gen,
                        },
                        motivo=f'Variante en tono {nombre_var.lower()} sobre el mismo contexto. Revísalo antes de usar.',
                    ))
                    usados_txt.add(_huella(variante_gen))

        # 2. Frases más relevantes del catálogo solo si la IA no generó borrador suficiente
        if len(lista) < MAX_OPCIONES_VIVO:
            for cand in _rankear_frases_relevantes(texto_busqueda or texto, frases):
                if len(lista) >= MAX_OPCIONES_VIVO:
                    break
                cid = cand.get('id')
                ctxt = str(cand.get('contenido') or '').strip()
                if not ctxt:
                    continue
                if (cid is not None and cid in usados_id) or _huella(ctxt) in usados_txt:
                    continue
                idx = len(lista) + 1
                tono, nombre_tono = TONOS_OPCION[idx - 1]
                lista.append(OpcionFlotante(
                    indice=idx,
                    etiqueta=f'Opción {idx} · {nombre_tono}',
                    tono=tono,
                    frase=cand,
                    motivo='Sugerencia complementaria del catálogo relevante para este contexto.',
                ))
                if cid is not None:
                    usados_id.add(cid)
                usados_txt.add(_huella(ctxt))

        # 3. Si el catálogo no alcanza para 3 distintas, completa con variantes de tono de la opción base
        if lista and len(lista) < MAX_OPCIONES_VIVO:
            base_frase = dict(lista[0].frase)
            base_contenido = str(base_frase.get('contenido') or '').strip()
            while len(lista) < MAX_OPCIONES_VIVO:
                idx = len(lista) + 1
                tono, nombre_tono = TONOS_OPCION[idx - 1]
                variante = (
                    _variar_por_tono(
                        base_contenido,
                        tono,
                        animo=animo,
                        es_primer_contacto_chat=es_primer_contacto_chat,
                    )
                    or base_contenido
                )
                frase_var = {
                    **base_frase,
                    'id': -idx,
                    'contenido': variante,
                    'origen': base_frase.get('origen', 'borrador_ia'),
                }
                lista.append(OpcionFlotante(
                    indice=idx,
                    etiqueta=f'Opción {idx} · {nombre_tono}',
                    tono=tono,
                    frase=frase_var,
                    motivo=f'Variante en tono {nombre_tono.lower()} para completar las 3 opciones.',
                ))

        return tuple(lista[:MAX_OPCIONES_VIVO])

    def _ejecutar_consulta(self, texto: str, *, epoca: int, exigir_activo: bool) -> ResultadoVivo | None:
        try:
            frases = list(self._obtener_frases() or [])
            if not self._puede_emitir(epoca, exigir_activo):
                return None
            primer_contacto = es_primer_contacto(texto)
            texto_cliente = extraer_texto_cliente(texto)
            tema, animo, urgencia = clasificar_contexto(texto_cliente)
            self._notificar_analizando(texto_cliente)

            compuesta = es_consulta_compuesta(texto)
            sugerencias = (
                self._recomendador.sugerir(texto, frases)
                if (frases and not compuesta) else []
            )
            if not self._puede_emitir(epoca, exigir_activo):
                return None

            if sugerencias:
                opciones_base = _envolver_sugerencias(sugerencias)
                opciones = self._completar_hasta_tres(
                    opciones_base,
                    texto,
                    frases,
                    animo,
                    texto_busqueda=texto_cliente,
                    es_primer_contacto_chat=primer_contacto,
                )
                if not self._puede_emitir(epoca, exigir_activo):
                    return None
            else:
                generada, error_gen = self._generar_borrador_crudo(texto, frases)
                if not self._puede_emitir(epoca, exigir_activo):
                    return None
                if generada is None:
                    if error_gen:
                        self._notificar_error(
                            f'Sin coincidencias en el catálogo y la IA no respondió: {error_gen}'
                        )
                    else:
                        self._notificar_error(
                            'Sin coincidencias en el catálogo de frases aprobadas para este mensaje.'
                        )
                    return None
                opciones = _construir_tres_borradores_ia(
                    generada,
                    animo=animo,
                    es_primer_contacto_chat=primer_contacto,
                )

            resultado = ResultadoVivo(
                tema=tema,
                animo=animo,
                urgencia=urgencia,
                opciones=opciones,
                mensaje_origen=texto,
            )
            self._notificar_resultado(resultado)
            return resultado
        except Exception as error:
            if self._puede_emitir(epoca, exigir_activo):
                self._notificar_error(str(error) or 'No se pudieron obtener sugerencias de IA.')
            return None

    def _notificar_analizando(self, texto: str) -> None:
        if self._al_analizar is not None:
            try:
                self._al_analizar(texto)
            except Exception:
                pass

    def _notificar_resultado(self, resultado: ResultadoVivo) -> None:
        if self._al_resultado is not None:
            try:
                self._al_resultado(resultado)
            except Exception:
                pass

    def _notificar_error(self, mensaje: str) -> None:
        if self._al_error is not None:
            try:
                self._al_error(mensaje)
            except Exception:
                pass

    crear_resultado_demo = staticmethod(crear_resultado_demo)
