"""Servidor HTTP estrictamente local (127.0.0.1) para la extensión de WhatsApp Web."""
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets
import threading

PUERTO_PUENTE_WSP = 47821
HOST_PUENTE_WSP = '127.0.0.1'
ORIGEN_WHATSAPP_WEB = 'https://web.whatsapp.com'
MAX_CUERPO_PUENTE = 8192
MAX_LARGO_MENSAJE = 4000


class _ServidorPuente(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _limpiar_turnos(turnos_raw) -> list[dict]:
    if not isinstance(turnos_raw, list):
        return []
    limpios = []
    for item in turnos_raw[:12]:
        if not isinstance(item, dict):
            continue
        t_rol = item.get('rol')
        t_txt = item.get('texto')
        if (
            isinstance(t_rol, str)
            and t_rol.strip().casefold() in ('cliente', 'agente')
            and isinstance(t_txt, str)
            and t_txt.strip()
            and len(t_txt) <= MAX_LARGO_MENSAJE
        ):
            limpios.append({'rol': t_rol.strip().casefold(), 'texto': t_txt.strip()})
    return limpios


class PuenteWhatsAppWeb:
    """Servidor HTTP estrictamente local (127.0.0.1) para recibir contexto desde WhatsApp Web."""

    def __init__(self, al_mensaje, puerto: int = PUERTO_PUENTE_WSP, host: str = HOST_PUENTE_WSP):
        if host != HOST_PUENTE_WSP:
            raise ValueError('PuenteWhatsAppWeb solo puede vincularse a 127.0.0.1.')
        self._al_mensaje = al_mensaje
        self._host = HOST_PUENTE_WSP
        self._puerto_solicitado = int(puerto)
        self.puerto: int = int(puerto)
        self.token_local: str = secrets.token_urlsafe(16)
        self._servidor: _ServidorPuente | None = None
        self._hilo: threading.Thread | None = None
        self._candado = threading.Lock()

    def _crear_manejador(self):
        al_mensaje = self._al_mensaje
        token_esperado = self.token_local

        class _Manejador(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                # Nunca registrar contenido ni metadatos de chat en consola/archivos.
                pass

            def _origin(self) -> str:
                return (self.headers.get('Origin') or '').strip()

            def _agregar_cors(self, origin: str, preflight: bool = False):
                if origin == ORIGEN_WHATSAPP_WEB:
                    self.send_header('Access-Control-Allow-Origin', ORIGEN_WHATSAPP_WEB)
                    self.send_header('Vary', 'Origin')
                    if preflight:
                        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
                        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-FraseYa-Local')
                        self.send_header('Access-Control-Allow-Private-Network', 'true')
                        self.send_header('Access-Control-Max-Age', '600')

            def _responder_json(self, estado: int, carga: dict, origin: str = ''):
                cuerpo = json.dumps(carga, ensure_ascii=False).encode('utf-8')
                self.send_response(estado)
                self._agregar_cors(origin)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)

            def do_GET(self):
                ruta = self.path.split('?', 1)[0]
                if ruta != '/estado':
                    self._responder_json(404, {'ok': False, 'error': 'No encontrado.'})
                    return
                self._responder_json(200, {'ok': True, 'app': 'FraseYa'}, origin=self._origin())

            def do_OPTIONS(self):
                ruta = self.path.split('?', 1)[0]
                if ruta not in ('/mensaje', '/estado'):
                    self._responder_json(404, {'ok': False, 'error': 'No encontrado.'})
                    return
                origin = self._origin()
                if origin != ORIGEN_WHATSAPP_WEB:
                    self._responder_json(403, {'ok': False, 'error': 'Origen no permitido.'})
                    return
                self.send_response(204)
                self._agregar_cors(origin, preflight=True)
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', '0')
                self.end_headers()

            def _autorizado(self, origin: str) -> bool:
                if origin:
                    if origin != ORIGEN_WHATSAPP_WEB:
                        self._responder_json(403, {'ok': False, 'error': 'Origen no permitido.'})
                        return False
                    return True
                cabecera = (self.headers.get('X-FraseYa-Local') or '').strip()
                if not hmac.compare_digest(cabecera, token_esperado):
                    self._responder_json(403, {'ok': False, 'error': 'Cabecera de origen requerida.'})
                    return False
                return True

            def _leer_json(self, origin: str) -> dict | None:
                crudo_largo = self.headers.get('Content-Length')
                if crudo_largo is None:
                    self._responder_json(400, {'ok': False, 'error': 'Falta Content-Length.'}, origin=origin)
                    return None
                try:
                    largo = int(crudo_largo)
                except ValueError:
                    self._responder_json(400, {'ok': False, 'error': 'Content-Length inválido.'}, origin=origin)
                    return None
                if largo < 0:
                    self._responder_json(400, {'ok': False, 'error': 'Content-Length inválido.'}, origin=origin)
                    return None
                if largo > MAX_CUERPO_PUENTE:
                    self.close_connection = True
                    self._responder_json(413, {'ok': False, 'error': 'Carga demasiado grande.'}, origin=origin)
                    return None
                cuerpo = self.rfile.read(largo)
                if len(cuerpo) > MAX_CUERPO_PUENTE:
                    self.close_connection = True
                    self._responder_json(413, {'ok': False, 'error': 'Carga demasiado grande.'}, origin=origin)
                    return None
                try:
                    datos = json.loads(cuerpo.decode('utf-8'))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    self._responder_json(400, {'ok': False, 'error': 'JSON inválido.'}, origin=origin)
                    return None
                if not isinstance(datos, dict):
                    self._responder_json(400, {'ok': False, 'error': 'Se esperaba un objeto JSON.'}, origin=origin)
                    return None
                return datos

            def do_POST(self):
                ruta = self.path.split('?', 1)[0]
                if ruta != '/mensaje':
                    self._responder_json(404, {'ok': False, 'error': 'No encontrado.'})
                    return
                origin = self._origin()
                if not self._autorizado(origin):
                    return
                datos = self._leer_json(origin)
                if datos is None:
                    return

                texto = datos.get('texto')
                if not isinstance(texto, str) or not texto.strip() or len(texto) > MAX_LARGO_MENSAJE:
                    self._responder_json(
                        400,
                        {'ok': False, 'error': 'El texto debe tener entre 1 y 4.000 caracteres.'},
                        origin=origin,
                    )
                    return

                chat = '' if datos.get('chat') is None else datos.get('chat')
                remitente = '' if datos.get('remitente') is None else datos.get('remitente')
                if not isinstance(chat, str) or not isinstance(remitente, str):
                    self._responder_json(400, {'ok': False, 'error': 'Metadatos inválidos.'}, origin=origin)
                    return

                metadatos = {
                    'chat': chat.strip()[:200],
                    'remitente': remitente.strip()[:200],
                    'origen': 'web',
                }
                rol_raw = datos.get('rol')
                if isinstance(rol_raw, str) and rol_raw.strip().casefold() in ('cliente', 'agente'):
                    metadatos['rol'] = rol_raw.strip().casefold()
                turnos_limpios = _limpiar_turnos(datos.get('turnos'))
                if turnos_limpios:
                    metadatos['turnos'] = turnos_limpios

                try:
                    if al_mensaje is not None:
                        al_mensaje(texto.strip(), metadatos)
                except Exception:
                    self._responder_json(500, {'ok': False, 'error': 'Error al procesar mensaje.'}, origin=origin)
                    return

                self._responder_json(200, {'ok': True}, origin=origin)

        return _Manejador

    def iniciar(self) -> int:
        with self._candado:
            if self._servidor is not None:
                return self.puerto
            servidor = _ServidorPuente((self._host, self._puerto_solicitado), self._crear_manejador())
            self._servidor = servidor
            self.puerto = int(servidor.server_address[1])
            hilo = threading.Thread(
                target=servidor.serve_forever,
                kwargs={'poll_interval': 0.1},
                name='fraseya-puente-wsp',
                daemon=True,
            )
            self._hilo = hilo
            hilo.start()
            return self.puerto

    def detener(self) -> None:
        with self._candado:
            servidor = self._servidor
            hilo = self._hilo
            self._servidor = None
            self._hilo = None
        if servidor is not None:
            try:
                servidor.shutdown()
            finally:
                servidor.server_close()
        if hilo is not None and hilo.is_alive():
            hilo.join(timeout=2.0)
