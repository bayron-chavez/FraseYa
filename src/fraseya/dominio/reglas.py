"""Reglas y constantes compartidas del dominio FraseYa."""
import re
import unicodedata

COMPARTIDA = 'compartida'
PROPIA = 'propia'
ORIGENES_VALIDOS = (PROPIA, COMPARTIDA)

MAX_NOMBRE_CATEGORIA = 200
MAX_TITULO_FRASE = 500
MAX_ABREVIATURA = 100
MAX_CONTENIDO_FRASE = 100_000
COLOR_DEFECTO = '#64748B'

PATRON_COLOR_HEX = re.compile(r'^#[0-9A-Fa-f]{6}$')
MARCADOR_VARIABLE = re.compile(r'\{(\w+)\}')

VARIABLES_OFICIALES: tuple[str, ...] = (
    'nombre',
    'pedido',
    'fecha',
    'monto',
    'correo',
    'telefono',
    'direccion',
    'empresa',
    'orden',
)


def normalizar_texto(texto: str | None) -> str:
    """Devuelve texto en minúsculas Unicode (casefold) y sin diacríticos."""
    base = unicodedata.normalize('NFD', (texto or '').casefold())
    return ''.join(c for c in base if not unicodedata.combining(c))


def extraer_marcadores(contenido: str) -> list[str]:
    """Devuelve nombres únicos de marcadores {variable} en orden de aparición."""
    return list(dict.fromkeys(MARCADOR_VARIABLE.findall(contenido or '')))


def validar_color_hex(color: str) -> str:
    """Valida formato hexadecimal #RRGGBB y devuelve el color."""
    if not isinstance(color, str) or not PATRON_COLOR_HEX.fullmatch(color):
        raise ValueError('El color debe tener formato #RRGGBB.')
    return color


def validar_nombre_categoria(nombre: str) -> str:
    """Valida nombre de categoría (1..200 caracteres tras strip)."""
    limpio = (nombre or '').strip() if isinstance(nombre, str) else ''
    if not limpio or len(limpio) > MAX_NOMBRE_CATEGORIA:
        raise ValueError(f'El nombre debe tener entre 1 y {MAX_NOMBRE_CATEGORIA} caracteres.')
    return limpio


def validar_datos_frase(titulo: str, abreviatura: str, contenido: str) -> list[str]:
    """Valida título, abreviatura y contenido de una frase; devuelve lista de errores."""
    errores: list[str] = []
    if not isinstance(titulo, str) or not titulo.strip():
        errores.append('El título no puede estar vacío.')
    if not isinstance(abreviatura, str) or not abreviatura.strip():
        errores.append('La abreviatura no puede estar vacía.')
    elif any(c.isspace() for c in abreviatura.strip()):
        errores.append('La abreviatura no puede contener espacios.')
    if not isinstance(contenido, str) or not contenido.strip():
        errores.append('El contenido no puede estar vacío.')
    if (
        (isinstance(titulo, str) and len(titulo) > MAX_TITULO_FRASE)
        or (isinstance(abreviatura, str) and len(abreviatura) > MAX_ABREVIATURA)
        or (isinstance(contenido, str) and len(contenido) > MAX_CONTENIDO_FRASE)
    ):
        errores.append(
            f'Máximos: título {MAX_TITULO_FRASE}, abreviatura {MAX_ABREVIATURA} '
            f'y contenido {MAX_CONTENIDO_FRASE} caracteres.'
        )
    return errores
