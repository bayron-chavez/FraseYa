"""Vista previa y fusión del catálogo, sin operaciones de archivos."""
from dataclasses import dataclass
from datetime import datetime, timezone
import time
import copy

from fraseya.aplicacion.formato_catalogo import serializar


class ErrorPublicacion(ValueError):
    pass


class ErrorAutorizacion(PermissionError):
    pass


@dataclass(frozen=True)
class VistaPublicacion:
    destino: str
    version_anterior: int
    version: int
    cantidad_frases: int
    cantidad_categorias: int
    nuevas: int
    modificadas: int
    eliminadas: int
    catalogo: bytes
    metadata: bytes
    hash_anterior: str | None


@dataclass(frozen=True)
class ResultadoPublicacion:
    version: int
    fecha: str
    cantidad_frases: int


class ServicioPublicacion:
    def __init__(self, repositorio, destino, autor, *, reloj=time.time, autorizar_eliminacion=None):
        self.repo = repositorio
        self.destino = destino
        self.autor = autor
        self._reloj = reloj
        self._autorizar_eliminacion = autorizar_eliminacion

    def _exigir_administrador(self):
        if self._autorizar_eliminacion is None:
            raise ErrorAutorizacion('Solo el administrador puede eliminar frases compartidas.')
        try:
            self._autorizar_eliminacion()
        except PermissionError as error:
            raise ErrorAutorizacion(str(error)) from None

    def recoger_categorias(self):
        """Debe ejecutarse en el hilo propietario de la conexión SQLite."""
        categorias = {c['id']: c for c in self.repo.listar_categorias()}
        grupos = {}
        propios = {c['id'] for c in self.repo.listar_catalogos('propia')}
        for categoria in categorias.values():
            if categoria['catalogo_id'] in propios:
                grupos.setdefault(categoria['nombre'], {'nombre': categoria['nombre'],
                    'color': categoria['color'], 'frases': []})
        for frase in self.repo.listar_frases('propia'):
            categoria = categorias[frase['categoria_id']]
            clave = categoria['nombre']
            if clave not in grupos:
                grupos[clave] = {'nombre': clave, 'color': categoria['color'], 'frases': []}
            elif grupos[clave]['color'] != categoria['color']:
                raise ErrorPublicacion(f'La categoría {clave} tiene colores distintos en tus catálogos propios.')
            grupos[clave]['frases'].append({k: frase[k] for k in ('titulo', 'abreviatura', 'contenido')})
        return list(grupos.values())

    def preparar(self, categorias=None, *, eliminar=()):
        """Vista previa. Si se pasa un snapshot, no accede a SQLite."""
        categorias = self.recoger_categorias() if categorias is None else categorias
        try:
            lector = self._lector()
            anterior = lector.leer_version()
            viejas = []
            if anterior:
                anterior, viejas = lector.leer()
            version = anterior.version + 1 if anterior else 1
            fecha = datetime.fromtimestamp(self._reloj(), timezone.utc).isoformat()
            # Validar el aporte antes de fusionar: no ocultar duplicados o
            # documentos inválidos al construir los diccionarios de búsqueda.
            serializar(categorias, version, self.autor, fecha)
            categorias = self._fusionar(viejas, categorias)
            if eliminar:
                self._exigir_administrador()
                claves = {clave.casefold() for clave in eliminar}
                existentes = {f['abreviatura'].casefold() for c in viejas for f in c['frases']}
                if not claves <= existentes:
                    raise ErrorPublicacion('La frase a eliminar ya no está en el catálogo publicado.')
                for categoria in categorias:
                    categoria['frases'] = [f for f in categoria['frases']
                                           if f['abreviatura'].casefold() not in claves]
            datos, meta = serializar(categorias, version, self.autor, fecha)
            def frases(lista):
                return {f['abreviatura'].casefold(): (c['nombre'], c['color'], f)
                        for c in lista for f in c['frases']}
            antes, despues = frases(viejas), frases(categorias)
            return VistaPublicacion(self.destino, anterior.version if anterior else 0, version,
                sum(len(c['frases']) for c in categorias), len(categorias),
                len(despues.keys() - antes.keys()),
                sum(antes[k] != despues[k] for k in antes.keys() & despues.keys()),
                len(antes.keys() - despues.keys()), datos, meta, anterior.sha256 if anterior else None)
        except ErrorAutorizacion:
            raise

    @staticmethod
    def _fusionar(publicadas, nuevas):
        """Actualiza por abreviatura y conserva lo no incluido en el aporte."""
        resultado = copy.deepcopy(publicadas)
        reemplazadas = {f['abreviatura'].casefold() for c in nuevas for f in c['frases']}
        for categoria in resultado:
            categoria['frases'] = [f for f in categoria['frases']
                                   if f['abreviatura'].casefold() not in reemplazadas]
        por_nombre = {c['nombre'].casefold(): c for c in resultado}
        for categoria in nuevas:
            clave = categoria['nombre'].casefold()
            if clave not in por_nombre:
                destino = copy.deepcopy(categoria)
                resultado.append(destino)
                por_nombre[clave] = destino
            else:
                destino = por_nombre[clave]
                destino['frases'].extend(copy.deepcopy(categoria['frases']))
                destino['color'] = categoria['color']
        return resultado

    def _lector(self):
        raise NotImplementedError('La publicación requiere un repositorio Supabase.')
