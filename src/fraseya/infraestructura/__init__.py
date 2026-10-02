"""Acceso a SQLite, al teclado del sistema y, en el futuro, al catálogo compartido."""
from .escritor_texto import EscritorTexto
from .repositorio_sqlite import RepositorioSQLite

__all__ = ['EscritorTexto', 'RepositorioSQLite']
