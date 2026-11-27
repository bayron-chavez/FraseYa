"""Recomendaciones y plantillas propias generadas, sin envío automático."""
from dataclasses import dataclass
import json
import re

from fraseya.aplicacion.buscador import normalizar
from fraseya.aplicacion.limite_acceso import LimiteAcceso
from fraseya.infraestructura.supabase import ErrorSupabase

_TONOS_ASISTIR = ('empatica', 'directa', 'escalar')
_CLAVES_CONTEXTO = ('tema', 'animo', 'urgencia', 'primer_contacto', 'remitente')

_STOPWORDS_ES = frozenset({
    'hola', 'buenos', 'buenas', 'dias', 'tardes', 'noches', 'para', 'con', 'que',
    'por', 'favor', 'como', 'tengo', 'quiero', 'necesito', 'puedo', 'pueden',
    'una', 'uno', 'unos', 'unas', 'las', 'los', 'del', 'sobre', 'este', 'esta',
    'esto', 'estos', 'estas', 'muy', 'mas', 'pero', 'solo', 'cliente', 'agente',
    'respondiendo', 'aqui', 'alla', 'donde', 'cuando', 'quien', 'cual', 'cuales',
    'tiene', 'tienen', 'estan', 'soy', 'somos', 'puede', 'puedes', 'gracias',
    'muchas', 'saludos', 'disculpa', 'disculpe', 'perdon', 'hay', 'sin', 'nos',
})

_GRUPOS_SINONIMOS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ('_g_envio', ('envio', 'envios', 'despacho', 'despachos', 'entrega', 'entregas', 'tracking', 'seguimiento', 'encomienda', 'courier')),
    ('_g_precio', ('precio', 'precios', 'valor', 'valores', 'costo', 'costos', 'tarifa', 'tarifas', 'cotizacion', 'cotizar', 'presupuesto', 'vale', 'cuesta')),
    ('_g_catalogo', ('producto', 'productos', 'catalogo', 'catalogos', 'servicio', 'servicios', 'plan', 'planes', 'ofrecen', 'venden', 'menu', 'carta')),
    ('_g_cobro', ('factura', 'facturas', 'boleta', 'boletas', 'cobro', 'cobros', 'pago', 'pagos', 'comprobante', 'tarjeta', 'transferencia', 'monto')),
    ('_g_demora', ('demora', 'demoras', 'retraso', 'retrasos', 'atraso', 'atrasos', 'tarda', 'tardanza', 'esperando')),
    ('_g_cambio', ('devolucion', 'reembolso', 'reembolsos', 'cancelar', 'cancelacion', 'anular', 'anulacion', 'cambio', 'cambios', 'garantia')),
    ('_g_conexion', ('internet', 'wifi', 'red', 'conexion', 'cable', 'router', 'fibra', 'lento', 'lenta', 'caido')),
    ('_g_horario', ('horario', 'horarios', 'atencion', 'atienden', 'abierto', 'cerrado', 'hora', 'horas')),
)
_MAPA_SINONIMOS = {palabra: grupo for grupo, palabras in _GRUPOS_SINONIMOS for palabra in palabras}


@dataclass(frozen=True)
class Sugerencia:
    frase: dict
    motivo: str


def _tokens_relevantes(texto: str) -> set[str]:
    limpio = re.sub(r'(?im)^(?:cliente|agente)\s*:\s*', '', texto or '')
    crudos = re.findall(r'\w{3,}', normalizar(limpio))
    tokens = {t for t in crudos if t not in _STOPWORDS_ES}
    if not tokens:
        tokens = set(crudos)
    for t in list(tokens):
        grupo = _MAPA_SINONIMOS.get(t)
        if grupo:
            tokens.add(grupo)
    return tokens


def _ultimo_turno_cliente(texto: str) -> str:
    lineas = (texto or '').splitlines()
    if not any(re.match(r'^(?:cliente|agente)\s*:', l.strip(), re.IGNORECASE) for l in lineas if l.strip()):
        return texto or ''
    despues_agente: list[str] = []
    todos_cliente: list[str] = []
    rol = 'cliente'
    for linea in lineas:
        limpia = linea.strip()
        if not limpia:
            continue
        m = re.match(r'^(cliente|agente)\s*:\s*(.*)$', limpia, re.IGNORECASE)
        cuerpo = m.group(2).strip() if m else limpia
        if m:
            rol = m.group(1).casefold()
        if not cuerpo:
            continue
        if rol == 'agente':
            despues_agente.clear()
        else:
            todos_cliente.append(cuerpo)
            despues_agente.append(cuerpo)
    return '\n'.join(despues_agente or todos_cliente) or (texto or '')


def frases_relevantes_con_puntaje(texto: str, frases: list[dict]) -> list[tuple[int, dict]]:
    """Ordena frases válidas por relevancia léxica ponderada (3x último mensaje del cliente) y favoritas."""
    tokens_ultimo = _tokens_relevantes(_ultimo_turno_cliente(texto))
    tokens_hilo = _tokens_relevantes(texto)

    evaluadas: list[tuple[tuple[int, bool, int], int, dict]] = []
    for frase in (frases or []):
        if not isinstance(frase, dict) or not isinstance(frase.get('contenido'), str) or not frase['contenido'].strip():
            continue
        copia = dict(frase)
        cuerpo = ' '.join(str(copia.get(c, '')) for c in ('titulo', 'categoria', 'contenido'))
        tokens_frase = _tokens_relevantes(cuerpo)
        puntaje = 3 * len(tokens_ultimo & tokens_frase) + len(tokens_hilo & tokens_frase)
        clave_orden = (-puntaje, not copia.get('favorita', False), copia.get('id', 0))
        evaluadas.append((clave_orden, puntaje, copia))

    evaluadas.sort(key=lambda item: item[0])
    return [(puntaje, copia) for _, puntaje, copia in evaluadas]


def rankear_frases_relevantes(texto: str, frases: list[dict]) -> list[dict]:
    """Ordena frases válidas por coincidencia léxica con `texto` y preferencia de favoritas."""
    return [frase for _, frase in frases_relevantes_con_puntaje(texto, frases)]


def _sanitizar_contexto(contexto: dict | None) -> dict:
    if not isinstance(contexto, dict):
        return {}
    limpio = {}
    for clave in _CLAVES_CONTEXTO:
        if clave not in contexto:
            continue
        valor = contexto[clave]
        if clave == 'primer_contacto':
            if isinstance(valor, bool):
                limpio[clave] = valor
        elif isinstance(valor, str) and valor.strip():
            limpio[clave] = valor.strip()[:120]
    return limpio


def _validar_lista_sugerencias(filas, candidatas: dict, *, permitir_vacio: bool) -> list[Sugerencia]:
    if not isinstance(filas, list) or len(filas) > 3 or (not permitir_vacio and not filas):
        raise ValueError('La IA devolvió una respuesta inválida.')
    usadas, resultado = set(), []
    for fila in filas:
        if (not isinstance(fila, dict) or set(fila) != {'id', 'motivo'}
                or type(fila['id']) is not int or fila['id'] not in candidatas
                or fila['id'] in usadas or not isinstance(fila['motivo'], str)
                or not fila['motivo'].strip() or len(fila['motivo']) > 240):
            raise ValueError('La IA recomendó una frase que no pertenece a la selección.')
        usadas.add(fila['id'])
        resultado.append(Sugerencia(candidatas[fila['id']], fila['motivo']))
    return resultado


def preparar(mensaje, frases, permitir_vacio=False):
    if not isinstance(mensaje, str) or not mensaje.strip() or len(mensaje) > 4000:
        raise ValueError('Escribe un mensaje de entre 1 y 4.000 caracteres.')
    elegidas = rankear_frases_relevantes(mensaje, frases)[:40]
    if not elegidas and not permitir_vacio:
        raise ValueError('Guarda o sincroniza algunas frases antes de pedir sugerencias.')
    candidatas = [
        {
            'id': f['id'],
            'titulo': f['titulo'][:200],
            'categoria': f.get('categoria', '')[:200],
            'contenido': f['contenido'][:1600],
        }
        for f in elegidas
    ]
    while len(json.dumps({'mensaje': mensaje.strip(), 'frases': candidatas}).encode('utf-8')) > 180000:
        candidatas.pop()
    ids = {f['id'] for f in candidatas}
    return {'mensaje': mensaje.strip(), 'frases': candidatas}, {f['id']: dict(f) for f in elegidas if f['id'] in ids}


class RecomendadorIA:
    _MENSAJES_HTTP = {
        404: 'Falta activar el servicio de IA en Supabase.',
        429: 'Llegaste al límite de recomendaciones. Espera y vuelve a intentar.',
        503: 'La IA aún no está configurada o no está disponible.',
        502: 'Gemini no pudo responder. Revisa su clave y cuota en el servidor.',
    }

    def __init__(self, cliente):
        self.cliente = cliente
        self.limite = LimiteAcceso()

    def _invocar(self, pedido):
        self.limite.reservar()
        try:
            return self.cliente.solicitar('POST', '/functions/v1/fraseya-ia', pedido)
        except ErrorSupabase as error:
            raise ErrorSupabase(self._MENSAJES_HTTP.get(error.estado, str(error)), error.estado) from None

    def generar(self, mensaje, frases, *, contexto=None):
        pedido, _ = preparar(mensaje, frases, permitir_vacio=True)
        pedido['modo'] = 'generar'
        ctx = _sanitizar_contexto(contexto)
        if ctx:
            pedido['contexto'] = ctx
        respuesta = self._invocar(pedido)
        validar_generada(respuesta, {'General', *(f['categoria'] for f in pedido['frases'])})
        return respuesta

    def sugerir(self, mensaje, frases):
        pedido, candidatas = preparar(mensaje, frases)
        respuesta = self._invocar(pedido)
        if not isinstance(respuesta, dict) or set(respuesta) != {'sugerencias'}:
            raise ValueError('La IA devolvió una respuesta inválida.')
        return _validar_lista_sugerencias(respuesta['sugerencias'], candidatas, permitir_vacio=True)

    def asistir(self, mensaje, frases, *, contexto=None):
        """Resuelve en una sola llamada: sugiere frases del catálogo o genera hasta 3 variantes reales."""
        pedido, candidatas = preparar(mensaje, frases, permitir_vacio=True)
        pedido['modo'] = 'asistir'
        ctx = _sanitizar_contexto(contexto)
        if ctx:
            pedido['contexto'] = ctx
        try:
            respuesta = self._invocar(pedido)
        except ErrorSupabase as error:
            # Compatibilidad si la Edge Function remota aún no fue redesplegada con modo='asistir'.
            if error.estado == 400:
                sugerencias = self.sugerir(mensaje, frases) if frases else []
                if sugerencias:
                    return {'tipo': 'catalogo', 'sugerencias': sugerencias, 'opciones': []}
                generada = self.generar(mensaje, frases)
                return {'tipo': 'generadas', 'sugerencias': [], 'opciones': [generada]}
            raise

        if not isinstance(respuesta, dict) or set(respuesta) != {'tipo', 'sugerencias', 'opciones'}:
            raise ValueError('La IA devolvió una respuesta inválida.')
        tipo = respuesta['tipo']
        if tipo == 'catalogo':
            if respuesta['opciones'] != []:
                raise ValueError('La IA devolvió una respuesta inválida.')
            sugerencias = _validar_lista_sugerencias(respuesta['sugerencias'], candidatas, permitir_vacio=False)
            return {'tipo': 'catalogo', 'sugerencias': sugerencias, 'opciones': []}

        if tipo == 'generadas':
            filas = respuesta['opciones']
            if respuesta['sugerencias'] != [] or not isinstance(filas, list) or not (1 <= len(filas) <= 3):
                raise ValueError('La IA devolvió una respuesta inválida.')
            categorias = {'General', *(f['categoria'] for f in pedido['frases'])}
            tonos_usados = set()
            opciones_validas = []
            for fila in filas:
                if (not isinstance(fila, dict) or set(fila) != {'tono', 'titulo', 'categoria', 'contenido', 'motivo'}
                        or fila['tono'] not in _TONOS_ASISTIR or fila['tono'] in tonos_usados
                        or not isinstance(fila['motivo'], str) or not fila['motivo'].strip()
                        or len(fila['motivo']) > 240):
                    raise ValueError('La IA devolvió una variante inválida.')
                validar_generada(
                    {'titulo': fila['titulo'], 'categoria': fila['categoria'], 'contenido': fila['contenido']},
                    categorias,
                )
                tonos_usados.add(fila['tono'])
                opciones_validas.append(dict(fila))
            return {'tipo': 'generadas', 'sugerencias': [], 'opciones': opciones_validas}

        raise ValueError('La IA devolvió una respuesta inválida.')


def validar_generada(frase, categorias):
    if (not isinstance(frase, dict) or set(frase) != {'titulo', 'categoria', 'contenido'}
            or not isinstance(frase['titulo'], str) or not frase['titulo'].strip() or len(frase['titulo']) > 200
            or not isinstance(frase['categoria'], str) or frase['categoria'] not in categorias
            or not isinstance(frase['contenido'], str) or not frase['contenido'].strip() or len(frase['contenido']) > 4000):
        raise ValueError('La IA devolvió una plantilla inválida; no se guardó.')
    resto = re.sub(r'\{[a-z][a-z0-9_]{0,39}\}', '', frase['contenido'])
    if re.search(r'[{}\x00-\x08\x0b\x0c\x0e-\x1f]', resto):
        raise ValueError('La plantilla tiene variables inválidas; no se guardó.')


def guardar_generada(gestion, frase):
    categorias = gestion.categorias_propias()
    validar_generada(frase, {c['nombre'] for c in categorias})
    # Repetir una generación idéntica no añade otra copia ni cambia frases existentes.
    for existente in gestion.listar():
        if existente['origen'] == 'propia' and existente['contenido'] == frase['contenido'].strip():
            return existente
    categoria = next(c for c in categorias if c['nombre'] == frase['categoria'])
    abreviatura = gestion._abreviatura_libre('!ia')
    ident = gestion.crear(frase['titulo'].strip(), abreviatura, frase['contenido'].strip(), categoria['id'])
    return gestion.repo.obtener_frase(ident)
