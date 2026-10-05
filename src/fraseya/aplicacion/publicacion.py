"""RF-08: publicación del catálogo propio con vista previa y escritura segura."""
from dataclasses import dataclass
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import tempfile
import time
import uuid
import copy

from fraseya.aplicacion.formato_catalogo import serializar, leer_version, leer_catalogo
from fraseya.infraestructura.repositorio_compartido import RepositorioCompartido


class ErrorPublicacion(ValueError):
    pass


class ErrorAutorizacion(PermissionError):
    pass


@dataclass(frozen=True)
class VistaPublicacion:
    carpeta: str
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
    def __init__(self, repositorio, carpeta, autor=None, *, reloj=time.time, autorizar_eliminacion=None):
        self.repo = repositorio
        self.carpeta = str(carpeta or '').strip()
        self.autor = getpass.getuser() if autor is None else autor
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
        for frase in self.repo.listar_frases('propia'):
            categoria = categorias[frase['categoria_id']]
            clave = categoria['nombre']
            if clave not in grupos:
                grupos[clave] = {'nombre': clave, 'color': categoria['color'], 'frases': []}
            elif grupos[clave]['color'] != categoria['color']:
                raise ErrorPublicacion(f'La categoría {clave} tiene colores distintos en tus catálogos propios.')
            grupos[clave]['frases'].append({k: frase[k] for k in ('titulo', 'abreviatura', 'contenido')})
        return list(grupos.values())

    def _ruta(self):
        if not self.carpeta:
            raise ErrorPublicacion('Configura la carpeta compartida antes de publicar.')
        ruta = Path(self.carpeta)
        if not ruta.is_dir():
            raise ErrorPublicacion('La carpeta compartida no existe o no está disponible.')
        return ruta

    def preparar(self, categorias=None, *, eliminar=()):
        """Vista previa. Si se pasa un snapshot, no accede a SQLite."""
        categorias = self.recoger_categorias() if categorias is None else categorias
        try:
            self._ruta()
            lector = RepositorioCompartido(self.carpeta)
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
                categorias = [c for c in categorias if c['frases']]
            datos, meta = serializar(categorias, version, self.autor, fecha)
            def frases(lista):
                return {f['abreviatura'].casefold(): (c['nombre'], c['color'], f)
                        for c in lista for f in c['frases']}
            antes, despues = frases(viejas), frases(categorias)
            return VistaPublicacion(self.carpeta, anterior.version if anterior else 0, version,
                sum(len(c['frases']) for c in categorias), len(categorias),
                len(despues.keys() - antes.keys()),
                sum(antes[k] != despues[k] for k in antes.keys() & despues.keys()),
                len(antes.keys() - despues.keys()), datos, meta, anterior.sha256 if anterior else None)
        except ErrorAutorizacion:
            raise
        except OSError:
            raise ErrorPublicacion('No se puede leer la carpeta; revisa la red y los permisos.') from None

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
        return [c for c in resultado if c['frases']]

    def _tomar_candado(self, ruta):
        candado = ruta / 'publicando.lock'
        token = uuid.uuid4().hex
        contenido = json.dumps({'autor': self.autor, 'fecha': self._reloj(), 'token': token}).encode('utf-8')
        for _ in range(2):
            try:
                descriptor = os.open(candado, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                try:
                    with candado.open('rb') as archivo:
                        crudo = archivo.read(4096)
                    info = json.loads(crudo)
                    fecha = info['fecha']
                    if not isinstance(fecha, (int, float)):
                        raise ValueError()
                except (ValueError, KeyError, OSError):
                    raise ErrorPublicacion('Hay un candado de publicación ilegible; revisa si otro administrador está publicando.') from None
                if self._reloj() - fecha <= 120:
                    instante = datetime.fromtimestamp(fecha, timezone.utc).isoformat()
                    raise ErrorPublicacion(f'Ya está publicando {info.get("autor", "otro usuario")} desde {instante}.')
                # Solo retirar la misma marca caducada que se inspeccionó.
                if candado.read_bytes() == crudo:
                    candado.unlink()
                continue
            archivo = os.fdopen(descriptor, 'wb')
            try:
                archivo.write(contenido)
                archivo.flush()
                os.fsync(archivo.fileno())
            except Exception:
                archivo.close()
                candado.unlink(missing_ok=True)
                raise
            # Windows impide borrar esta marca mientras su descriptor siga
            # abierto, incluso si una operación de red excede su caducidad.
            return candado, token, archivo
        raise ErrorPublicacion('Otro administrador ha tomado el candado; vuelve a intentarlo.')

    @staticmethod
    def _temporal(ruta, datos):
        descriptor, nombre = tempfile.mkstemp(prefix='.fraseya-', suffix='.tmp', dir=ruta)
        temporal = Path(nombre)
        try:
            with os.fdopen(descriptor, 'wb') as archivo:
                archivo.write(datos)
                archivo.flush()
                os.fsync(archivo.fileno())
            return temporal
        except Exception:
            temporal.unlink(missing_ok=True)
            raise

    def publicar(self, vista=None, *, confirmar_vacio=False):
        vista = self.preparar() if vista is None else vista
        if vista.carpeta != self.carpeta:
            raise ErrorPublicacion('La vista previa corresponde a otra carpeta; prepara una nueva.')
        if vista.cantidad_frases == 0 and not confirmar_vacio:
            raise ErrorPublicacion('Publicar cero frases requiere confirmación explícita: borrará el catálogo compartido de los equipos.')
        candado = None
        archivo_candado = None
        temporales = []
        anteriores = {}
        cambios = False
        try:
            ruta = self._ruta()
            candado, token, archivo_candado = self._tomar_candado(ruta)
            actual = RepositorioCompartido(self.carpeta).leer_version()
            if ((actual.version if actual else 0) != vista.version_anterior or
                    (actual.sha256 if actual else None) != vista.hash_anterior):
                raise ErrorPublicacion('El catálogo cambió desde la vista previa; revisa las diferencias y confirma de nuevo.')
            if actual:
                _, categorias_actuales = RepositorioCompartido(self.carpeta).leer()
                claves_actuales = {f['abreviatura'].casefold() for c in categorias_actuales for f in c['frases']}
                claves_nuevas = {f['abreviatura'].casefold() for c in leer_catalogo(vista.catalogo) for f in c['frases']}
                if claves_actuales - claves_nuevas:
                    self._exigir_administrador()
            for nombre in ('catalogo.json', 'version.json'):
                archivo = ruta / nombre
                if archivo.exists():
                    with archivo.open('rb') as fuente:
                        datos = fuente.read(5 * 1024 * 1024 + 1)
                    if len(datos) > 5 * 1024 * 1024:
                        raise ErrorPublicacion('El catálogo anterior supera el límite; no se reemplazará.')
                    anteriores[nombre] = datos
                else:
                    anteriores[nombre] = None
            for datos in (vista.catalogo, vista.metadata):
                temporales.append(self._temporal(ruta, datos))
            cambios = True
            os.replace(temporales[0], ruta / 'catalogo.json')
            os.replace(temporales[1], ruta / 'version.json')
            version, _ = RepositorioCompartido(self.carpeta).leer()
            esperada = leer_version(vista.metadata)
            if version != esperada:
                raise ErrorPublicacion('La verificación posterior no coincide con la publicación.')
            return ResultadoPublicacion(version.version, version.fecha, version.cantidad_frases)
        except Exception as error:
            if cambios:
                try:
                    for nombre, datos in anteriores.items():
                        if datos is None:
                            (ruta / nombre).unlink(missing_ok=True)
                        else:
                            restaurar = self._temporal(ruta, datos)
                            temporales.append(restaurar)
                            os.replace(restaurar, ruta / nombre)
                except OSError:
                    raise ErrorPublicacion('La publicación falló y no se pudo restaurar el catálogo anterior; revisa la carpeta antes de volver a publicar.') from None
            if isinstance(error, ErrorAutorizacion):
                raise
            if isinstance(error, OSError):
                raise ErrorPublicacion('No se pudo escribir el catálogo; revisa permisos, red y espacio en disco.') from None
            raise
        finally:
            for temporal in temporales:
                try:
                    temporal.unlink(missing_ok=True)
                except OSError:
                    pass
            if candado:
                if archivo_candado:
                    archivo_candado.close()
                try:
                    info = json.loads(candado.read_bytes())
                    if info.get('token') == token:
                        candado.unlink()
                except (OSError, ValueError):
                    pass
