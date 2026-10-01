"""Entidades y reglas de FraseYa.

Esta capa no debe importar SQLite ni componentes de interfaz.
"""
from .entidades import (COMPARTIDA, PROPIA, CatalogoFrases, Categoria, Frase,
                        VersionCatalogo, Variable)

__all__ = ['COMPARTIDA', 'PROPIA', 'CatalogoFrases', 'Categoria', 'Frase',
           'VersionCatalogo', 'Variable']
