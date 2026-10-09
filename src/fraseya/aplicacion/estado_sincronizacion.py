"""RF-09: estado visible independiente de los mensajes de la red."""
from datetime import datetime, timezone


def resumen_estado(repo, resultado=None, comprobando=False, sin_conexion=False):
    version = max((c['version'] for c in repo.listar_catalogos('compartida')), default=0)
    historial = repo.listar_sincronizaciones()
    ultimo = historial[0] if historial else None
    fecha = 'Nunca'
    if ultimo:
        fecha = datetime.fromisoformat(ultimo['fecha']).replace(tzinfo=timezone.utc).astimezone().strftime('%d/%m/%Y %H:%M:%S')
    estado = resultado.estado if resultado else (ultimo['estado'] if ultimo else 'pendiente')
    detalle = resultado.detalle if resultado else (ultimo['detalle'] if ultimo else 'Sin comprobar')
    if sin_conexion:
        estado, detalle = 'offline', 'Modo sin conexión; se utiliza el catálogo guardado.'
    elif comprobando:
        estado, detalle = 'comprobando', 'Comprobando catálogo compartido…'
    return estado, f'Versión vigente: {version} · Última comprobación: {fecha}\n{detalle}'
