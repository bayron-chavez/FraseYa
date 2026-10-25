"""Recomendaciones y plantillas propias generadas, sin envío automático."""
import re
import json
from dataclasses import dataclass
from fraseya.aplicacion.buscador import normalizar
from fraseya.aplicacion.limite_acceso import LimiteAcceso
from fraseya.infraestructura.supabase import ErrorSupabase


@dataclass(frozen=True)
class Sugerencia:
    frase: dict
    motivo: str


def preparar(mensaje, frases):
    if not isinstance(mensaje, str) or not mensaje.strip() or len(mensaje) > 4000:
        raise ValueError('Escribe un mensaje de entre 1 y 4.000 caracteres.')
    palabras = set(re.findall(r'\w{3,}', normalizar(mensaje)))
    def puntuacion(frase):
        texto = normalizar(' '.join(str(frase.get(c, '')) for c in ('titulo', 'categoria', 'contenido')))
        coincidencias = len(palabras & set(re.findall(r'\w{3,}', texto)))
        return (-coincidencias, not frase.get('favorita', False), frase['id'])
    elegidas = sorted(frases, key=puntuacion)[:40]
    if not elegidas:
        raise ValueError('Guarda o sincroniza algunas frases antes de pedir sugerencias.')
    candidatas = [{'id': f['id'], 'titulo': f['titulo'][:200],
                  'categoria': f.get('categoria', '')[:200], 'contenido': f['contenido'][:1600]}
                 for f in elegidas]
    while len(json.dumps({'mensaje': mensaje.strip(), 'frases': candidatas}).encode('utf-8')) > 180000:
        candidatas.pop()
    ids = {f['id'] for f in candidatas}
    return {'mensaje': mensaje.strip(), 'frases': candidatas}, {f['id']: dict(f) for f in elegidas if f['id'] in ids}


class RecomendadorIA:
    def __init__(self, cliente):
        self.cliente = cliente
        self.limite = LimiteAcceso()

    def generar(self, mensaje, frases):
        pedido, _ = preparar(mensaje, frases)
        pedido['modo'] = 'generar'
        self.limite.reservar()
        respuesta = self.cliente.solicitar('POST', '/functions/v1/fraseya-ia', pedido)
        validar_generada(respuesta, {'General', *(f['categoria'] for f in pedido['frases'])})
        return respuesta

    def sugerir(self, mensaje, frases):
        pedido, candidatas = preparar(mensaje, frases)
        self.limite.reservar()
        try:
            respuesta = self.cliente.solicitar('POST', '/functions/v1/fraseya-ia', pedido)
        except ErrorSupabase as error:
            mensajes = {404: 'Falta activar el servicio de IA en Supabase.',
                        429: 'Llegaste al límite de recomendaciones. Espera y vuelve a intentar.',
                        503: 'La IA aún no está configurada o no está disponible.',
                        502: 'Gemini no pudo responder. Revisa su clave y cuota en el servidor.'}
            raise ErrorSupabase(mensajes.get(error.estado, str(error)), error.estado) from None
        if not isinstance(respuesta, dict) or set(respuesta) != {'sugerencias'}:
            raise ValueError('La IA devolvió una respuesta inválida.')
        filas = respuesta['sugerencias']
        if not isinstance(filas, list) or len(filas) > 3:
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
