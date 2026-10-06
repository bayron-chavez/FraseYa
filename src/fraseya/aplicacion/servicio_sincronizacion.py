"""RF-06: sincronización periódica, con conexiones SQLite por hilo."""
from dataclasses import dataclass
from threading import Event, Lock, Thread
import sqlite3

from fraseya.dominio.entidades import VersionCatalogo
from fraseya.infraestructura.repositorio_sqlite import RepositorioSQLite


@dataclass(frozen=True)
class ResultadoSincronizacion:
    estado: str
    version: int | None
    detalle: str


class ServicioSincronizacion:
    def __init__(self, repositorio, crear_lector,
                 al_actualizar=None, al_resultado=None, crear_repositorio_local=None,
                 esperar=None):
        self.repo = repositorio
        self._al_actualizar = al_actualizar
        self._al_resultado = al_resultado
        ruta = repositorio.db.execute('PRAGMA database_list').fetchone()[2]
        self._crear_local = crear_repositorio_local or (
            (lambda: RepositorioSQLite(ruta)) if ruta else None)
        self._candado = Lock()
        self._config = Lock()
        self._parada = Event()
        self._despertar = Event()
        self._esperar = esperar or self._despertar.wait
        self._hilo = None
        self._generacion = 0
        self._intervalo = 15
        self._lector = crear_lector()

    def configurar(self, intervalo):
        if type(intervalo) is not int or not 1 <= intervalo <= 1440:
            raise ValueError('El intervalo debe estar entre 1 y 1440 minutos.')
        with self._config:
            self._intervalo = intervalo
            self._generacion += 1
        self._despertar.set()

    def sincronizar(self, _repo=None):
        """En modo directo debe llamarse desde el hilo dueño de repositorio."""
        repo = _repo or self.repo
        if not self._candado.acquire(blocking=False):
            return ResultadoSincronizacion('sin_cambios', None, 'Ya hay una sincronización en curso.')
        actualizado = False
        try:
            with self._config:
                lector, generacion = self._lector, self._generacion
                origen = lector.identificador
            instalada = max((c['version'] for c in repo.listar_catalogos('compartida')), default=0)
            anterior_origen = repo.leer_configuracion('origen_sincronizado', '')
            if (anterior_origen and anterior_origen != origen) or (
                    not anterior_origen and origen.startswith('supabase:')):
                instalada = 0  # Las versiones de dos orígenes distintos no son comparables.
            try:
                publicada = lector.leer_version()
                if publicada is None:
                    resultado = ResultadoSincronizacion('sin_cambios', instalada, 'Todavía no se ha publicado un catálogo.')
                elif not VersionCatalogo(publicada.version).es_posterior_a(VersionCatalogo(instalada)):
                    resultado = ResultadoSincronizacion('sin_cambios', instalada,
                        f'Ya tienes la última versión instalada (versión {instalada}); no se aplican versiones anteriores.')
                else:
                    version, categorias = lector.leer()
                    with self._config:
                        if generacion != self._generacion or self._parada.is_set():
                            return ResultadoSincronizacion('sin_cambios', instalada, 'Lectura descartada por cambio de configuración o cierre.')
                        # La versión puede cambiar entre leer_version y leer.
                        if version.version <= instalada:
                            resultado = ResultadoSincronizacion('sin_cambios', instalada, 'La versión leída no es posterior a la instalada.')
                        else:
                            categorias = self._resolver_conflictos(repo, categorias)
                            repo.reemplazar_compartidas(version.version, version.autor, version.fecha, categorias,
                                origen_sync=origen)
                            resultado = ResultadoSincronizacion('actualizada', version.version,
                                f'Actualizado a la versión {version.version}.')
                            actualizado = True
            except Exception as error:
                detalle = str(error)
                if isinstance(error, sqlite3.Error):
                    detalle = 'No se pudo guardar el catálogo; se conserva la versión anterior.'
                resultado = ResultadoSincronizacion('error', instalada, detalle)
            if not actualizado:
                repo.registrar_sincronizacion(resultado.estado, resultado.version, resultado.detalle)
        finally:
            self._candado.release()
        if actualizado and self._al_actualizar:
            self._al_actualizar()
        return resultado

    def _resolver_conflictos(self, repo, categorias):
        propias = {f['abreviatura'].casefold(): f for f in repo.listar_frases('propia')}
        resultado, conflictos = [], []
        for categoria in categorias:
            frases = []
            for frase in categoria['frases']:
                propia = propias.get(frase['abreviatura'].casefold())
                if propia:
                    conflictos.append(frase['abreviatura'])
                else:
                    frases.append(frase)
            resultado.append({**categoria, 'frases': frases})
        if conflictos:
            raise ValueError('Renombra tus abreviaturas en conflicto para actualizar: ' + ', '.join(conflictos))
        return resultado

    def iniciar(self):
        if self._hilo and self._hilo.is_alive():
            return
        if self._crear_local is None:
            raise ValueError('Para el hilo se necesita una base en archivo o una fábrica de conexiones.')
        self._parada.clear()
        self._hilo = Thread(target=self._ciclo, daemon=True)
        self._hilo.start()

    def solicitar(self):
        self._despertar.set()

    def _ciclo(self):
        while not self._parada.is_set():
            self._despertar.clear()
            try:
                with self._crear_local() as repo:
                    resultado = self.sincronizar(repo)
            except Exception:
                resultado = ResultadoSincronizacion('error', None, 'No se pudo acceder a la base local; vuelve a intentarlo.')
            if self._parada.is_set():
                break
            if self._al_resultado:
                self._al_resultado(resultado)
            with self._config:
                segundos = self._intervalo * 60
            self._esperar(segundos)

    def detener(self):
        self._parada.set()
        self._despertar.set()
        # No espera al hilo de red: el cierre de Tkinter es inmediato.
