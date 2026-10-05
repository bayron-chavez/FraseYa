"""Contrato JSON del catálogo compartido, sin acceso a archivos ni interfaz."""
from dataclasses import dataclass
from datetime import datetime
import hashlib
import hmac
import json
import re

FORMATO = 1
MAX_BYTES = 5 * 1024 * 1024


class ErrorFormato(ValueError):
    """Agrupa errores con su ubicación, para mostrarlos todos al usuario."""
    def __init__(self, errores):
        self.errores = list(errores)
        super().__init__('\n'.join(self.errores))


@dataclass(frozen=True)
class VersionPublicada:
    formato: int
    version: int
    fecha: str
    autor: str
    cantidad_frases: int
    sha256: str


def _texto(valor, ruta, errores):
    if not isinstance(valor, str) or not valor.strip():
        errores.append(f'{ruta}: debe ser texto no vacío.')
        return False
    return True


def _claves(objeto, claves, ruta, errores):
    if not isinstance(objeto, dict):
        errores.append(f'{ruta}: debe ser un objeto.')
        return False
    for clave in sorted(set(objeto) - set(claves)):
        errores.append(f'{ruta}.{clave}: clave no admitida por el formato 1.')
    return True


def _formato(valor, errores):
    if type(valor) is not int or valor != FORMATO:
        if type(valor) is int and valor > FORMATO:
            errores.append('formato: actualiza FraseYa para leer esta versión del formato.')
        else:
            errores.append('formato: debe ser el entero 1.')


def _categorias(categorias, errores):
    if not isinstance(categorias, list):
        errores.append('categorias: debe ser una lista.')
        return
    nombres, abreviaturas = set(), set()
    for i, categoria in enumerate(categorias):
        ruta = f'categorias[{i}]'
        if not _claves(categoria, ('nombre', 'color', 'frases'), ruta, errores):
            continue
        nombre = categoria.get('nombre')
        if _texto(nombre, ruta + '.nombre', errores):
            if nombre != nombre.strip():
                errores.append(ruta + '.nombre: no debe tener espacios en los extremos.')
            normalizado = nombre.strip().casefold()
            if normalizado in nombres:
                errores.append(ruta + '.nombre: categoría repetida.')
            nombres.add(normalizado)
        color = categoria.get('color')
        if not isinstance(color, str) or not re.fullmatch(r'#[0-9A-Fa-f]{6}', color):
            errores.append(ruta + '.color: debe tener formato #RRGGBB.')
        frases = categoria.get('frases')
        if not isinstance(frases, list):
            errores.append(ruta + '.frases: debe ser una lista.')
            continue
        for j, frase in enumerate(frases):
            lugar = f'{ruta}.frases[{j}]'
            if not _claves(frase, ('titulo', 'abreviatura', 'contenido'), lugar, errores):
                continue
            for clave in ('titulo', 'contenido'):
                _texto(frase.get(clave), lugar + '.' + clave, errores)
            abreviatura = frase.get('abreviatura')
            if _texto(abreviatura, lugar + '.abreviatura', errores):
                if any(c.isspace() for c in abreviatura):
                    errores.append(lugar + '.abreviatura: no debe contener espacios.')
                normalizada = abreviatura.casefold()
                if normalizada in abreviaturas:
                    errores.append(lugar + '.abreviatura: abreviatura repetida en el catálogo.')
                abreviaturas.add(normalizada)


def _metadata(objeto, errores):
    _formato(objeto.get('formato'), errores)
    version = objeto.get('version')
    if type(version) is not int or version < 1:
        errores.append('version: debe ser un entero mayor o igual a 1.')
    cantidad = objeto.get('cantidad_frases')
    if type(cantidad) is not int or cantidad < 0:
        errores.append('cantidad_frases: debe ser un entero no negativo.')
    if not isinstance(objeto.get('autor'), str):
        errores.append('autor: debe ser texto.')
    fecha = objeto.get('fecha')
    try:
        if not isinstance(fecha, str) or 'T' not in fecha:
            raise ValueError()
        instante = datetime.fromisoformat(fecha.replace('Z', '+00:00'))
        if instante.tzinfo is None or instante.utcoffset() is None:
            raise ValueError()
    except ValueError:
        errores.append('fecha: debe ser una fecha ISO 8601 con hora y zona horaria.')
    sha = objeto.get('sha256')
    if not isinstance(sha, str) or not re.fullmatch(r'[0-9a-f]{64}', sha):
        errores.append('sha256: debe contener 64 dígitos hexadecimales en minúsculas.')


def _cargar(datos):
    if not isinstance(datos, bytes):
        raise ErrorFormato(['archivo: se esperan bytes.'])
    if len(datos) > MAX_BYTES:
        raise ErrorFormato(['archivo: supera el máximo de 5 MiB.'])
    duplicadas = []
    def pares(items):
        resultado = {}
        for clave, valor in items:
            if clave in resultado:
                duplicadas.append(f'archivo.{clave}: clave JSON duplicada.')
            resultado[clave] = valor
        return resultado
    def constante(_):
        raise ValueError('Constante JSON no válida')
    try:
        valor = json.loads(datos.decode('utf-8-sig'), object_pairs_hook=pares,
                           parse_constant=constante)
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise ErrorFormato(['archivo: JSON o codificación UTF-8 inválidos.']) from exc
    if duplicadas:
        raise ErrorFormato(duplicadas)
    if not isinstance(valor, dict):
        raise ErrorFormato(['archivo: el documento debe ser un objeto JSON.'])
    return valor


def _bytes(objeto):
    datos = (json.dumps(objeto, ensure_ascii=False, indent=2, sort_keys=True,
                        allow_nan=False) + '\n').encode('utf-8')
    if len(datos) > MAX_BYTES:
        raise ErrorFormato(['archivo: supera el máximo de 5 MiB.'])
    return datos


def serializar(categorias, version, autor, fecha):
    """Devuelve los bytes de catalogo.json y version.json, respectivamente."""
    errores = []
    _categorias(categorias, errores)
    cantidad = sum(len(c.get('frases', [])) for c in categorias
                   if isinstance(c, dict) and isinstance(c.get('frases'), list)) if isinstance(categorias, list) else 0
    metadata = dict(formato=FORMATO, version=version, autor=autor, fecha=fecha,
                    cantidad_frases=cantidad, sha256='0' * 64)
    _metadata(metadata, errores)
    if errores:
        raise ErrorFormato(errores)
    try:
        contenido = _bytes({'formato': FORMATO, 'categorias': categorias})
        metadata['sha256'] = hashlib.sha256(contenido).hexdigest()
        return contenido, _bytes(metadata)
    except (UnicodeEncodeError, RecursionError) as exc:
        raise ErrorFormato(['archivo: texto Unicode inválido o estructura demasiado profunda.']) from exc


def leer_version(datos):
    objeto = _cargar(datos)
    errores = []
    _claves(objeto, ('formato', 'version', 'fecha', 'autor', 'cantidad_frases', 'sha256'), 'version', errores)
    _metadata(objeto, errores)
    if errores:
        raise ErrorFormato(errores)
    return VersionPublicada(**objeto)


def leer_catalogo(datos):
    objeto = _cargar(datos)
    errores = []
    _claves(objeto, ('formato', 'categorias'), 'catalogo', errores)
    _formato(objeto.get('formato'), errores)
    _categorias(objeto.get('categorias'), errores)
    if errores:
        raise ErrorFormato(errores)
    return objeto['categorias']


def verificar_integridad(datos_catalogo, version):
    """Compara el SHA-256 de los bytes exactos, incluido un eventual BOM.

    No sustituye leer_catalogo: el hash valida consistencia, no autenticidad.
    """
    if not isinstance(datos_catalogo, bytes) or len(datos_catalogo) > MAX_BYTES:
        raise ErrorFormato(['archivo: se esperan bytes de hasta 5 MiB.'])
    if not isinstance(version, VersionPublicada):
        raise ErrorFormato(['version: se espera una VersionPublicada.'])
    return hmac.compare_digest(hashlib.sha256(datos_catalogo).hexdigest(), version.sha256)
