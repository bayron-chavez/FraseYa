"""Prepara la persistencia y entrega información del arranque."""
from fraseya.infraestructura import RepositorioSQLite


def preparar_aplicacion(ruta):
    with RepositorioSQLite(ruta) as repo:
        version = repo.db.execute('PRAGMA user_version').fetchone()[0]
        return {'version_esquema': version, 'cantidad_frases': len(repo.listar_frases())}
