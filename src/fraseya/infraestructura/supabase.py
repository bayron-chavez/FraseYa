"""Supabase Auth y Data API; claves públicas, sesiones solo en memoria."""
import base64
import json
import time
import re
import secrets
from pathlib import Path
from threading import RLock
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

from fraseya.aplicacion.sesion import Sesion
from fraseya.aplicacion.limite_acceso import LimiteAcceso
from fraseya.aplicacion.formato_catalogo import (
    MAX_BYTES, leer_catalogo, leer_version, verificar_integridad)


class ErrorSupabase(ValueError):
    def __init__(self, mensaje, estado=None):
        super().__init__(mensaje)
        self.estado = estado


class SinRedirecciones(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ErrorSupabase('Supabase respondió con una redirección; se bloqueó para proteger la sesión.')


def validar_conexion(url, clave):
    if not isinstance(url, str):
        raise ValueError('La URL del proyecto debe ser texto.')
    url = url.strip().rstrip('/')
    partes = urlsplit(url)
    if (partes.scheme != 'https' or not partes.hostname or partes.username
            or partes.password or partes.path or partes.query or partes.fragment):
        raise ValueError('Usa la URL HTTPS del proyecto, sin rutas ni credenciales.')
    if (not re.fullmatch(r'[a-z0-9-]{1,63}\.supabase\.co', partes.netloc)
            or '\\' in url or any(c.isspace() for c in url)):
        raise ValueError('La URL debe pertenecer al proyecto alojado en supabase.co.')
    if not isinstance(clave, str) or not clave or len(clave) > 4096 or any(c.isspace() for c in clave):
        raise ValueError('Introduce la clave pública publishable o anon.')
    if not clave.startswith('sb_publishable_'):
        try:
            payload = clave.split('.')[1]
            rol = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))['role']
        except (ValueError, IndexError, KeyError, TypeError):
            raise ValueError('Usa una clave pública publishable o anon.') from None
        if rol != 'anon':
            raise ValueError('No uses claves secret ni service_role en FraseYa.')
    return url, clave


def cargar_cliente(ruta):
    archivo = Path(ruta)
    if not archivo.exists():
        raise ErrorSupabase('Configura Supabase con python scripts/configurar_supabase.py antes de abrir FraseYa.')
    try:
        datos = json.loads(archivo.read_text(encoding='utf-8'))
        return ClienteSupabase(datos['url'], datos['clave_publica'])
    except (OSError, KeyError, ValueError, TypeError) as error:
        raise ErrorSupabase('Revisa la configuración local supabase.json.') from error


class ClienteSupabase:
    def __init__(self, url, clave, transporte=None, reloj=time.time):
        self.url, self.clave = validar_conexion(url, clave)
        self._transporte = transporte or self._http
        self._reloj = reloj
        self._lock = RLock()
        self._access = self._refresh = None
        self._vence = 0
        self._abrir = build_opener(SinRedirecciones()).open
        self.limite_acceso = LimiteAcceso()

    def _http(self, metodo, ruta, cuerpo, headers):
        solicitud = Request(self.url + ruta, data=cuerpo, headers=headers, method=metodo)
        try:
            with self._abrir(solicitud, timeout=10) as respuesta:
                datos = respuesta.read(MAX_BYTES * 2 + 1)
                if len(datos) > MAX_BYTES * 2:
                    raise ErrorSupabase('La respuesta del catálogo excede el tamaño permitido.')
                return json.loads(datos) if datos else None
        except HTTPError as error:
            # No mostrar cuerpos HTTP: pueden contener datos de cuentas o tokens.
            mensajes = {400: 'Solicitud rechazada; revisa tus datos o la versión del catálogo.',
                401: 'Sesión vencida o credenciales incorrectas. Inicia sesión nuevamente.',
                403: 'Tu cuenta no tiene permisos para esta operación.',
                404: 'Falta instalar el esquema de FraseYa en Supabase.',
                429: 'Demasiados intentos. Espera antes de volver a iniciar sesión.',
                409: 'Otro administrador publicó primero. Prepara nuevamente la publicación.'}
            raise ErrorSupabase(mensajes.get(error.code, f'Supabase no está disponible (HTTP {error.code}).'), error.code) from None
        except (URLError, TimeoutError, OSError):
            raise ErrorSupabase('No se pudo conectar a Supabase. Se conserva el catálogo local.') from None
        except ErrorSupabase:
            raise
        except (ValueError, UnicodeError, RecursionError):
            raise ErrorSupabase('Supabase devolvió una respuesta inválida.') from None

    def solicitar(self, metodo, ruta, datos=None, *, autenticado=True):
        with self._lock:
            if autenticado:
                if not self._access:
                    raise ErrorSupabase('Inicia sesión en Supabase para sincronizar o publicar.')
                if self._reloj() >= self._vence - 30:
                    respuesta = self.solicitar('POST', '/auth/v1/token?grant_type=refresh_token',
                        {'refresh_token': self._refresh}, autenticado=False)
                    self._guardar_tokens(respuesta)
            headers = {'apikey': self.clave, 'Content-Type': 'application/json'}
            if autenticado:
                headers['Authorization'] = 'Bearer ' + self._access
            cuerpo = json.dumps(datos).encode('utf-8') if datos is not None else None
            try:
                return self._transporte(metodo, ruta, cuerpo, headers)
            except ErrorSupabase as error:
                if error.estado == 401:
                    self.limpiar()
                raise

    def _guardar_tokens(self, respuesta):
        try:
            access, refresh, ttl = respuesta['access_token'], respuesta['refresh_token'], respuesta['expires_in']
            if (not isinstance(access, str) or not isinstance(refresh, str) or not access or not refresh
                    or any(c.isspace() for c in access + refresh)
                    or type(ttl) is not int or not 30 < ttl <= 86400):
                raise ValueError()
            self._access, self._refresh = access, refresh
            self._vence = self._reloj() + ttl
        except (KeyError, TypeError, ValueError):
            self.limpiar()
            raise ErrorSupabase('Respuesta de sesión inválida.') from None

    def entrar(self, correo, clave):
        self.limpiar()
        if (not isinstance(correo, str) or not isinstance(clave, str)
                or not correo.strip() or len(correo) > 254 or not clave or len(clave) > 1024):
            raise ErrorSupabase('Introduce un correo y una contraseña válidos.')
        self.limite_acceso.reservar()
        try:
            respuesta = self.solicitar('POST', '/auth/v1/token?grant_type=password',
                {'email': correo.strip(), 'password': clave}, autenticado=False)
            self._guardar_tokens(respuesta)
            return self.perfil()
        except ErrorSupabase as error:
            self.limpiar()
            if error.estado == 429:
                self.limite_acceso.bloquear()
            if error.estado in (400, 401):
                raise ErrorSupabase('Correo o contraseña incorrectos.', error.estado) from None
            raise
        except Exception:
            self.limpiar()
            raise

    def perfil(self):
        filas = self.solicitar('POST', '/rest/v1/rpc/fraseya_perfil', {})
        if (not isinstance(filas, list) or len(filas) != 1 or not isinstance(filas[0], dict)
                or filas[0].get('rol') not in ('administrador', 'usuario')
                or not isinstance(filas[0].get('id'), str) or not filas[0]['id']
                or not isinstance(filas[0].get('correo'), str) or not filas[0]['correo']):
            raise ErrorSupabase('Tu cuenta no está habilitada para FraseYa.')
        return filas[0]

    def limpiar(self):
        with self._lock:
            self._access = self._refresh = None
            self._vence = 0


class AutenticacionSupabase:
    def __init__(self, cliente):
        self.cliente = cliente
        self._sesion = None
        self._cerrada = False

    def iniciar_sesion(self, nombre, clave):
        if self._cerrada:
            raise ErrorSupabase('La ventana de acceso se cerró.')
        self._sesion = None
        perfil = self.cliente.entrar(nombre, clave)
        if self._cerrada:
            self.cliente.limpiar()
            raise ErrorSupabase('La ventana de acceso se cerró.')
        self._sesion = Sesion(perfil['correo'], perfil['rol'], secrets.token_urlsafe(32))
        return self._sesion

    def sin_conexion(self):
        self.cliente.limpiar()
        self._sesion = Sesion('Modo sin conexión', 'usuario', 'offline')
        return self._sesion

    def validar(self, sesion, administrador=False):
        if sesion is None or sesion != self._sesion:
            raise PermissionError('Inicia sesión para continuar.')
        if administrador:
            if sesion.token == 'offline' or self.cliente.perfil()['rol'] != 'administrador':
                raise PermissionError('Solo el administrador puede publicar o eliminar del catálogo.')

    def salir(self, sesion):
        try:
            if sesion and sesion.token != 'offline':
                self.cliente.solicitar('POST', '/auth/v1/logout', {})
        except ErrorSupabase:
            pass
        finally:
            self._sesion = None
            self.cliente.limpiar()

    def cerrar(self):
        self._cerrada = True
        self._sesion = None
        self.cliente.limpiar()


class RepositorioSupabase:
    def __init__(self, cliente):
        self.cliente = cliente
        self.identificador = 'supabase:' + cliente.url

    def _snapshot(self):
        filas = self.cliente.solicitar('GET', '/rest/v1/fraseya_catalogo?id=eq.1&select=contenido,metadata')
        if not isinstance(filas, list) or len(filas) > 1 or (filas and not isinstance(filas[0], dict)):
            raise ErrorSupabase('Supabase devolvió un catálogo inválido.')
        if not filas or filas[0]['contenido'] is None:
            return None
        fila = filas[0]
        if not isinstance(fila.get('contenido'), str) or not isinstance(fila.get('metadata'), dict):
            raise ErrorSupabase('Supabase devolvió un catálogo inválido.')
        version = leer_version(json.dumps(fila['metadata']).encode('utf-8'))
        datos = fila['contenido'].encode('utf-8')
        if not verificar_integridad(datos, version):
            raise ErrorSupabase('El catálogo remoto no supera la verificación de integridad.')
        categorias = leer_catalogo(datos)
        if sum(len(c['frases']) for c in categorias) != version.cantidad_frases:
            raise ErrorSupabase('La cantidad de frases del catálogo remoto es incorrecta.')
        return version, categorias

    def leer_version(self):
        snapshot = self._snapshot()
        return snapshot[0] if snapshot else None

    def leer(self):
        snapshot = self._snapshot()
        if snapshot is None:
            raise ErrorSupabase('Todavía no hay un catálogo publicado.')
        return snapshot

    def publicar(self, vista):
        return self.cliente.solicitar('POST', '/rest/v1/rpc/fraseya_publicar', {
            'p_version_anterior': vista.version_anterior,
            'p_contenido': vista.catalogo.decode('utf-8'),
            'p_metadata': json.loads(vista.metadata)})
