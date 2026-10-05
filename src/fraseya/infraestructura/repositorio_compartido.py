"""RF-05: lectura acotada del catálogo publicado; nunca modifica el origen."""
from dataclasses import dataclass
from pathlib import Path
from queue import Queue, Empty
from threading import Thread, Lock
import math
import time

from fraseya.aplicacion import formato_catalogo as formato


class CarpetaNoDisponible(Exception):
    pass


class CatalogoNoPublicado(Exception):
    pass


class FormatoInvalido(Exception):
    pass


class FormatoNoSoportado(FormatoInvalido):
    pass


class CatalogoEnTransicion(Exception):
    pass


@dataclass(frozen=True)
class EstadoCarpeta:
    estado: str
    mensaje: str


class RepositorioCompartido:
    def __init__(self, carpeta, tiempo_maximo_s=10, pausa=time.sleep):
        if not math.isfinite(tiempo_maximo_s) or tiempo_maximo_s <= 0:
            raise ValueError('El tiempo máximo debe ser positivo y finito.')
        self.carpeta = str(carpeta or '').strip()
        self.tiempo_maximo_s = tiempo_maximo_s
        self._pausa = pausa
        self._ocupado = Lock()

    def _ejecutar(self, operacion):
        # Un hilo daemon no retiene el cierre del programa si Windows sigue
        # esperando a la red. El lock evita acumular hilos en este lector.
        if not self._ocupado.acquire(blocking=False):
            raise CarpetaNoDisponible('La carpeta no responde; hay una lectura pendiente.')
        resultado = Queue(maxsize=1)
        def trabajar():
            try:
                resultado.put((True, operacion()))
            except Exception as error:
                resultado.put((False, error))
            finally:
                self._ocupado.release()
        try:
            Thread(target=trabajar, daemon=True).start()
        except Exception:
            self._ocupado.release()
            raise
        try:
            correcto, valor = resultado.get(timeout=self.tiempo_maximo_s)
        except Empty:
            raise CarpetaNoDisponible('La carpeta no responde dentro del tiempo máximo.') from None
        if correcto:
            return valor
        raise valor

    def _ruta(self):
        if not self.carpeta:
            raise CarpetaNoDisponible('Configura la carpeta del catálogo compartido.')
        ruta = Path(self.carpeta)
        try:
            if not ruta.is_dir():
                raise CarpetaNoDisponible('La carpeta no existe o no está disponible.')
        except OSError:
            raise CarpetaNoDisponible('No se puede acceder a la carpeta; revisa la red y los permisos.') from None
        return ruta

    def _archivo(self, nombre, opcional=False):
        ruta = self._ruta() / nombre
        try:
            with ruta.open('rb') as archivo:
                datos = archivo.read(formato.MAX_BYTES + 1)
        except FileNotFoundError:
            if opcional:
                return None
            raise CatalogoNoPublicado(f'No se ha publicado {nombre} en la carpeta compartida.') from None
        except OSError:
            raise CarpetaNoDisponible(f'No se puede leer {nombre}; revisa la red y los permisos.') from None
        if len(datos) > formato.MAX_BYTES:
            raise FormatoInvalido(f'{nombre}: supera el máximo de 5 MiB.')
        return datos

    @staticmethod
    def _validar(lector, datos):
        try:
            return lector(datos)
        except formato.ErrorFormato as error:
            tipo = FormatoNoSoportado if any('actualiza FraseYa' in e for e in error.errores) else FormatoInvalido
            raise tipo(str(error)) from None

    def comprobar(self):
        if not self.carpeta:
            return EstadoCarpeta('sin_configurar', 'Configura la carpeta del catálogo compartido.')
        try:
            self._ejecutar(lambda: self._archivo('version.json', opcional=True))
        except (CarpetaNoDisponible, CatalogoNoPublicado) as error:
            return EstadoCarpeta('inaccesible', str(error))
        except FormatoInvalido:
            pass  # La carpeta es accesible aunque el archivo no sea válido.
        return EstadoCarpeta('disponible', 'La carpeta compartida está disponible.')

    def leer_version(self):
        def leer():
            datos = self._archivo('version.json', opcional=True)
            return None if datos is None else self._validar(formato.leer_version, datos)
        return self._ejecutar(leer)

    def leer(self):
        def leer():
            for intento in range(2):
                version = self._validar(formato.leer_version, self._archivo('version.json'))
                datos = self._archivo('catalogo.json')
                categorias = self._validar(formato.leer_catalogo, datos)
                posterior = self._validar(formato.leer_version, self._archivo('version.json'))
                if version == posterior and formato.verificar_integridad(datos, version):
                    if sum(len(c['frases']) for c in categorias) != version.cantidad_frases:
                        raise FormatoInvalido('La cantidad de frases no coincide con version.json.')
                    return version, categorias
                if intento == 0:
                    self._pausa(0.1)
            raise CatalogoEnTransicion('El catálogo está cambiando o su integridad no coincide; vuelve a intentarlo más tarde.')
        return self._ejecutar(leer)
