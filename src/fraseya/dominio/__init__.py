"""Entidades y reglas de FraseYa.

Esta capa no debe importar SQLite ni componentes de interfaz.
"""
from .entidades import (
    COMPARTIDA,
    PROPIA,
    CatalogoFrases,
    Categoria,
    Frase,
    Variable,
    VersionCatalogo,
)
from .reglas import (
    COLOR_DEFECTO,
    MAX_ABREVIATURA,
    MAX_CONTENIDO_FRASE,
    MAX_NOMBRE_CATEGORIA,
    MAX_TITULO_FRASE,
    VARIABLES_OFICIALES,
    extraer_marcadores,
    normalizar_texto,
    validar_color_hex,
    validar_datos_frase,
    validar_nombre_categoria,
)

__all__ = [
    'COLOR_DEFECTO',
    'COMPARTIDA',
    'MAX_ABREVIATURA',
    'MAX_CONTENIDO_FRASE',
    'MAX_NOMBRE_CATEGORIA',
    'MAX_TITULO_FRASE',
    'PROPIA',
    'VARIABLES_OFICIALES',
    'CatalogoFrases',
    'Categoria',
    'Frase',
    'Variable',
    'VersionCatalogo',
    'extraer_marcadores',
    'normalizar_texto',
    'validar_color_hex',
    'validar_datos_frase',
    'validar_nombre_categoria',
]
