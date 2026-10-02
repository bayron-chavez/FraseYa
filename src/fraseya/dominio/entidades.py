"""Entidades del problema: frases, categorías y versiones del catálogo."""
import re
from dataclasses import dataclass, field
from datetime import datetime

COMPARTIDA = 'compartida'
PROPIA = 'propia'
_MARCADOR = re.compile(r'\{(\w+)\}')


def _texto(valor, campo):
    valor = (valor or '').strip()
    if not valor:
        raise ValueError(f'{campo} no puede estar vacío')
    return valor


@dataclass(frozen=True)
class Variable:
    nombre: str
    orden: int

    def __post_init__(self):
        _texto(self.nombre, 'Nombre de la variable')
        if self.orden < 0:
            raise ValueError('El orden no puede ser negativo')


@dataclass
class Frase:
    titulo: str
    abreviatura: str
    contenido: str
    origen: str = PROPIA
    id: int = None
    variables: list = field(default_factory=list)

    def __post_init__(self):
        self.titulo = _texto(self.titulo, 'Título')
        self.abreviatura = _texto(self.abreviatura, 'Abreviatura')
        self.contenido = _texto(self.contenido, 'Contenido')
        if self.origen not in (PROPIA, COMPARTIDA):
            raise ValueError(f'Origen inválido: {self.origen}')
        nombres = list(dict.fromkeys(_MARCADOR.findall(self.contenido)))
        self.variables = [Variable(n, i) for i, n in enumerate(nombres)]

    @property
    def es_compartida(self):
        return self.origen == COMPARTIDA

    def duplicar(self, abreviatura):
        """Copia propia (editable) de la frase con otra abreviatura."""
        return Frase(self.titulo, abreviatura, self.contenido, PROPIA)


class Categoria:
    """Compone frases; cada frase pertenece a una sola categoría."""

    def __init__(self, nombre, color='#64748B', id=None):
        self.nombre = _texto(nombre, 'Nombre de la categoría')
        if not re.fullmatch(r'#[0-9A-Fa-f]{6}', color):
            raise ValueError('El color debe tener formato #RRGGBB')
        self.color = color
        self.id = id
        self.frases = []

    def agregar(self, frase):
        if any(f.abreviatura.lower() == frase.abreviatura.lower() for f in self.frases):
            raise ValueError(f'Abreviatura repetida: {frase.abreviatura}')
        self.frases.append(frase)

    def quitar(self, frase):
        self.frases.remove(frase)


@dataclass(frozen=True)
class VersionCatalogo:
    numero: int
    fecha: datetime = None
    autor: str = ''

    def __post_init__(self):
        if self.numero < 0:
            raise ValueError('La versión no puede ser negativa')

    def es_posterior_a(self, otra):
        return self.numero > otra.numero


class CatalogoFrases:
    """Agrega categorías y permite reemplazar solo las frases compartidas."""

    def __init__(self, version=None):
        self.version = version or VersionCatalogo(0)
        self.categorias = []

    def agregar_categoria(self, categoria):
        if any(c.nombre.lower() == categoria.nombre.lower() for c in self.categorias):
            raise ValueError(f'Categoría repetida: {categoria.nombre}')
        self.categorias.append(categoria)

    def frases(self, origen=None):
        return [f for c in self.categorias for f in c.frases
                if origen is None or f.origen == origen]

    def buscar(self, abreviatura):
        clave = abreviatura.lower()
        return next((f for f in self.frases() if f.abreviatura.lower() == clave), None)

    def reemplazar_compartidas(self, version, categorias):
        """Sustituye las frases compartidas por las del catálogo publicado.

        Las propias se conservan intactas. Si hay conflicto de abreviaturas,
        no se modifica nada.
        """
        if not version.es_posterior_a(self.version):
            raise ValueError('La versión publicada no es posterior a la vigente')
        propias = {f.abreviatura.lower() for f in self.frases(PROPIA)}
        for c in categorias:
            for f in c.frases:
                if f.origen != COMPARTIDA:
                    raise ValueError('El catálogo publicado solo admite frases compartidas')
                if f.abreviatura.lower() in propias:
                    raise ValueError(f'Abreviatura en conflicto con una frase propia: {f.abreviatura}')
        for c in self.categorias:
            c.frases = [f for f in c.frases if f.origen == PROPIA]
        por_nombre = {c.nombre.lower(): c for c in self.categorias}
        for nueva in categorias:
            destino = por_nombre.get(nueva.nombre.lower())
            if destino is None:
                destino = Categoria(nueva.nombre, nueva.color)
                self.categorias.append(destino)
                por_nombre[nueva.nombre.lower()] = destino
            destino.color = nueva.color
            for f in nueva.frases:
                destino.agregar(f)
        self.version = version
