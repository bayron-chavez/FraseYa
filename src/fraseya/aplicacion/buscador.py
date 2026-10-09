"""RF-02: búsqueda incremental de frases por título, abreviatura, categoría o contenido.

Sin acentos ni mayúsculas ("dia" encuentra "Día"). Cada palabra de la consulta
debe aparecer en algún campo; las coincidencias en la abreviatura y el título
van primero.
"""
import unicodedata

# Menor es mejor: dónde y cómo coincide cada palabra de la consulta.
_PESO = {'abrev_exacta': 0, 'abrev_inicio': 1, 'abrev': 2, 'titulo_inicio': 3, 'titulo': 4,
         'categoria': 5, 'contenido': 6}


def normalizar(texto):
    """Minúsculas y sin acentos, para comparar."""
    base = unicodedata.normalize('NFD', (texto or '').casefold())
    return ''.join(c for c in base if not unicodedata.combining(c))


def _mejor_peso(palabra, campos):
    abrev, titulo, categoria, contenido = campos
    if palabra == abrev:
        return _PESO['abrev_exacta']
    if abrev.startswith(palabra):
        return _PESO['abrev_inicio']
    if palabra in abrev:
        return _PESO['abrev']
    if titulo.startswith(palabra):
        return _PESO['titulo_inicio']
    if palabra in titulo:
        return _PESO['titulo']
    if palabra in categoria:
        return _PESO['categoria']
    if palabra in contenido:
        return _PESO['contenido']
    return None


def buscar(frases, consulta, limite=100):
    """Frases (dicts con abreviatura, titulo, categoria, contenido) que coinciden, mejores primero."""
    palabras = normalizar(consulta).split()
    completa = ' '.join(palabras)
    resultado = []
    for frase in frases:
        campos = (normalizar(frase.get('abreviatura')), normalizar(frase.get('titulo')),
                  normalizar(frase.get('categoria')), normalizar(frase.get('contenido')))
        pesos = [_mejor_peso(p, campos) for p in palabras]
        if any(p is None for p in pesos):
            continue
        titulo = campos[1]
        bono = -3 if titulo == completa else (-1 if titulo.startswith(completa) else 0)
        resultado.append((sum(pesos) + (bono if palabras else 0), titulo, frase))
    resultado.sort(key=lambda r: (not r[2].get('favorita', False), r[0], r[1]))
    return [r[2] for r in resultado[:limite]]
