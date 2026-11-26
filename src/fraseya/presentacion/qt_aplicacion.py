"""Arranque de producción Qt con Auth, sincronización, bandeja y asistente en vivo."""
import queue
import threading
import time
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import QApplication, QDialog, QSystemTrayIcon, QMenu
from fraseya.infraestructura import RepositorioSQLite
from fraseya.infraestructura.lector_chat import LectorChat, PuenteWhatsAppWeb, VentanaChat
from fraseya.infraestructura.supabase import cargar_cliente, AutenticacionSupabase, RepositorioSupabase
from fraseya.infraestructura.teclado_global import activar_ventana
from fraseya.aplicacion.asistente_vivo import ServicioAsistenteVivo
from fraseya.aplicacion.configuracion import Configuracion
from fraseya.aplicacion.estado_sincronizacion import resumen_estado
from fraseya.aplicacion.gestion_frases import GestionFrases
from fraseya.aplicacion.recomendaciones_ia import RecomendadorIA
from fraseya.aplicacion.servicio_sincronizacion import ServicioSincronizacion
from fraseya.aplicacion.sesion import registrar_ultimo_perfil, ruta_bd_sesion
from .identidad import recurso
from .qt_dialogos import AccesoQt, configurar_conexion
from .qt_flotante import ControladorFlotanteQt
from .qt_temas import hoja_estilo
from .qt_vista import VentanaQt


_VENTANA_EXT_ACTIVA_SEG = 20.0


def _leer_tema_inicial(ruta):
    if not Path(ruta).exists():
        return 'claro'
    try:
        with RepositorioSQLite(ruta) as repo:
            return Configuracion(repo).leer().tema
    except Exception:
        return 'claro'


def _texto_analizando(texto=''):
    lineas = [l for l in str(texto or '').splitlines() if l.strip()]
    if len(lineas) > 1:
        return f'Analizando {len(lineas)} mensajes…'
    return 'Analizando mensaje…'


class _AsistenteVivoQt:
    """Coordina el puente WhatsApp Web, lectura UIA, barra flotante e inserción en ventana."""

    def __init__(self, ventana, cliente, obtener_expansion):
        self.ventana = ventana
        self.obtener_expansion = obtener_expansion
        self.eventos = queue.Queue()
        self.detenido = False

        self._frases_lock = threading.Lock()
        self._frases_snapshot = [dict(f) for f in ventana.gestion.listar()]
        self._ultimo_hwnd = None
        self._ultimo_rect = None
        self._ultima_ventana = None
        self._ultimo_mensaje_ext_ts = 0.0
        self._modo_demo = False
        self._lectura_en_curso = threading.Event()
        self._lector_chat = LectorChat()

        anterior_cambiar = ventana.al_cambiar

        def _al_cambiar_completo():
            if anterior_cambiar:
                anterior_cambiar()
            self.actualizar_snapshot()

        ventana.al_cambiar = _al_cambiar_completo

        self.servicio = ServicioAsistenteVivo(
            RecomendadorIA(cliente),
            self._obtener_frases_snapshot,
            al_resultado=lambda res: self.eventos.put(('resultado', res)),
            al_error=lambda msg: self.eventos.put(('error', msg)),
            al_analizar=lambda txt='': self.eventos.put(('analizando', _texto_analizando(txt))),
        )

        self.puente = None
        self.puente_disponible = False
        try:
            puente = PuenteWhatsAppWeb(al_mensaje=self._al_mensaje_puente)
            puente.iniciar()
            self.puente = puente
            self.puente_disponible = True
        except OSError:
            self.puente = None
            self.puente_disponible = False

        self.controlador = ControladorFlotanteQt(
            parent=ventana,
            tema=ventana.tema_actual,
            al_usar=self.usar_sugerencia,
            al_toggle_activo=self.toggle_vivo,
            al_leer_chat=self.leer_ultimos_3,
            al_analizar_portapapeles=self.analizar_portapapeles,
            al_ocultar=self.ocultar_flotante,
        )
        ventana.al_cambiar_tema = self.controlador.aplicar_tema
        ventana.al_toggle_vivo = self.toggle_vivo
        ventana.al_probar_vivo = self.probar_vivo
        ventana.al_analizar_portapapeles = self.analizar_portapapeles

        self.timer = QTimer(ventana)
        self.timer.timeout.connect(self._monitorear_whatsapp)
        self.timer.start(800)

    def actualizar_snapshot(self):
        copia = [dict(f) for f in self.ventana.gestion.listar()]
        with self._frases_lock:
            self._frases_snapshot[:] = copia

    def _obtener_frases_snapshot(self):
        with self._frases_lock:
            return [dict(f) for f in self._frases_snapshot]

    def _al_mensaje_puente(self, texto, meta):
        self._ultimo_mensaje_ext_ts = time.monotonic()
        chat_meta = meta.get('chat', '') if isinstance(meta, dict) else ''
        remitente_meta = meta.get('remitente', '') if isinstance(meta, dict) else ''
        rol_meta = meta.get('rol') if isinstance(meta, dict) else None
        turnos_meta = meta.get('turnos') if isinstance(meta, dict) else None
        if rol_meta or turnos_meta:
            registrado = self.servicio.registrar_turno(
                texto,
                rol=rol_meta or 'cliente',
                chat=chat_meta,
                turnos=turnos_meta,
                remitente=remitente_meta,
            )
        else:
            registrado = self.servicio.registrar_mensaje_entrante(
                texto,
                chat=chat_meta,
                remitente=remitente_meta,
            )
        if registrado and (rol_meta or 'cliente') == 'cliente':
            self.eventos.put((
                'aviso_suave',
                'Mensaje nuevo en WhatsApp Web · Pulsa «Leer últimos 3»',
            ))

    def usar_sugerencia(self, _frase, texto):
        if not texto:
            return
        if not self._ultimo_hwnd:
            win_act = self._lector_chat.ventana_whatsapp_activa()
            if win_act is not None:
                self._ultimo_hwnd = win_act.hwnd
                self._ultimo_rect = win_act.rect
                self._ultima_ventana = win_act

        expansion = self.obtener_expansion()
        if expansion is not None and self._ultimo_hwnd:
            hwnd_obj = self._ultimo_hwnd
            self.controlador.ocultar_sugerencias()
            expansion.desarmar_pegado_al_clic()
            QApplication.clipboard().setText(texto)
            try:
                activar_ventana(hwnd_obj)
            except Exception:
                pass

            def _al_terminar_insercion(ok_ins, err_ins):
                if self.detenido:
                    return
                if ok_ins:
                    self.eventos.put((
                        'estado_insercion',
                        'Frase copiada y pegada en WhatsApp. Revísala y envía.',
                    ))
                elif err_ins == 'sin_foco':
                    expansion.armar_pegado_al_clic(
                        texto,
                        hwnd_obj,
                        al_pegar=lambda ok_c, _e: (
                            self.eventos.put((
                                'estado_insercion',
                                'Frase copiada y pegada en WhatsApp. Revísala y envía.'
                                if ok_c else
                                'Copiada al portapapeles. Pégala en el chat con Ctrl+V.',
                            ))
                            if not self.detenido else None
                        ),
                    )
                    self.eventos.put((
                        'estado_insercion',
                        'Copiada al portapapeles · Haz clic en la caja del chat de WhatsApp para pegarla.',
                    ))
                else:
                    self.eventos.put((
                        'estado_insercion',
                        'Copiada al portapapeles (pegado automático bloqueado). Pégala con Ctrl+V.',
                    ))

            ok = expansion.insertar_texto_en_ventana(
                texto,
                hwnd_obj,
                enfocar_destino=lambda h=hwnd_obj: self._lector_chat.enfocar_caja_mensaje(h),
                al_terminar=_al_terminar_insercion,
            )
            aviso = 'Insertando frase en WhatsApp…' if ok else 'Espera a que termine la inserción en curso.'
            self.controlador.mostrar_aviso(aviso)
            if ok:
                self.ventana.estado.setText(aviso)
            return

        QApplication.clipboard().setText(texto)
        self.controlador.mostrar_aviso('Copiada al portapapeles. Pégala y revísala antes de enviar.')
        self.ventana.estado.setText('Sugerencia copiada al portapapeles. Revísala antes de enviarla.')

    def toggle_vivo(self, activo):
        if bool(activo):
            self._modo_demo = False
            self.servicio.activar()
            self.controlador.establecer_activo(True)
            self.controlador.limpiar_contexto()
            self.controlador.mostrar_aviso(
                'Escuchando WhatsApp · Pulsa «Leer últimos 3» cuando quieras sugerencias.'
            )
            detalle = (
                'Estado: Activo. Al abrir WhatsApp verás la barra flotante con el botón «Leer últimos 3».'
                if self.puente_disponible else
                'Estado: Activo en WhatsApp Desktop y Web (puerto local 47821 ocupado para extensión). '
                'Usa «Leer últimos 3» en la barra flotante.'
            )
            if self.ventana.panel_ia is not None:
                self.ventana.panel_ia.establecer_estado_vivo(True, detalle)
        else:
            self.servicio.pausar()
            self.controlador.establecer_activo(False)
            if not self._modo_demo:
                self.controlador.ocultar_todo()
            if self.ventana.panel_ia is not None:
                self.ventana.panel_ia.establecer_estado_vivo(
                    False, 'Estado: Pausado. No se observan chats de WhatsApp.'
                )

    def ocultar_flotante(self):
        self._modo_demo = False
        if self.servicio.activo:
            self.servicio.pausar()
            self.controlador.establecer_activo(False)
            if self.ventana.panel_ia is not None:
                self.ventana.panel_ia.establecer_estado_vivo(
                    False, 'Estado: Pausado al ocultar la barra flotante.'
                )

    def analizar_portapapeles(self):
        texto = QApplication.clipboard().text()
        if not texto.strip():
            if self.controlador.barra.isVisible():
                self.controlador.mostrar_aviso('Portapapeles vacío. Copia un mensaje del cliente primero.')
            if self.ventana.panel_ia is not None:
                self.ventana.panel_ia.estado_vivo.setText('Portapapeles vacío. Copia un mensaje del cliente primero.')
            return
        self._modo_demo = True
        self.controlador.mostrar_barra(self._ultimo_rect)
        self.controlador.establecer_cargando(True)
        self.controlador.mostrar_aviso('Analizando mensaje del portapapeles…')
        if self.ventana.panel_ia is not None:
            self.ventana.panel_ia.estado_vivo.setText('Analizando mensaje del portapapeles…')
        self.servicio.analizar_manual(texto)

    def leer_ultimos_3(self):
        if self.detenido or self._lectura_en_curso.is_set():
            return
        self._lectura_en_curso.set()
        self.controlador.establecer_cargando(True)
        self.controlador.mostrar_aviso('Leyendo últimos 3 mensajes…')
        if self.ventana.panel_ia is not None:
            self.ventana.panel_ia.estado_vivo.setText('Leyendo últimos 3 mensajes de WhatsApp…')
        threading.Thread(target=self._trabajar_lectura, name='fraseya-leer-ultimos-3', daemon=True).start()

    def _resolver_ventana_actual(self):
        win = self._lector_chat.ventana_whatsapp_activa()
        if win is None and self._ultima_ventana is not None:
            win = self._lector_chat.ventana_por_hwnd(self._ultima_ventana.hwnd)
            if win is None:
                rect_vivo = self._lector_chat.rect_ventana(self._ultima_ventana.hwnd)
                if rect_vivo is not None:
                    win = VentanaChat(
                        hwnd=self._ultima_ventana.hwnd,
                        titulo=self._ultima_ventana.titulo,
                        rect=rect_vivo,
                        tipo=self._ultima_ventana.tipo,
                    )
        if win is not None:
            self._ultimo_hwnd = win.hwnd
            self._ultimo_rect = win.rect
            self._ultima_ventana = win
        return win

    def _trabajar_lectura(self):
        try:
            win = self._resolver_ventana_actual()
            extension_reciente = (
                self._ultimo_mensaje_ext_ts > 0.0
                and (time.monotonic() - self._ultimo_mensaje_ext_ts) <= _VENTANA_EXT_ACTIVA_SEG
            )
            mensajes: list[str] = []
            if win is not None:
                if win.tipo == 'web' and extension_reciente:
                    mensajes = self.servicio.obtener_ultimos_mensajes(limite=8)
                    if not mensajes:
                        mensajes = self._lector_chat.leer_ultimos_mensajes(win, limite=8, incluir_salientes=True)
                else:
                    mensajes = self._lector_chat.leer_ultimos_mensajes(win, limite=8, incluir_salientes=True)
                    if not mensajes and win.tipo == 'web':
                        mensajes = self.servicio.obtener_ultimos_mensajes(limite=8)
            else:
                mensajes = self.servicio.obtener_ultimos_mensajes(limite=8)

            if self.detenido:
                return
            if not mensajes:
                self.eventos.put((
                    'error',
                    'No se detectaron mensajes visibles. Abre un chat en WhatsApp o usa «Portapapeles».',
                ))
                return

            n = len(mensajes)
            etiqueta = f'Leídos {n} mensajes · Generando 3 opciones…' if n > 1 else 'Leído 1 mensaje · Generando 3 opciones…'
            self.eventos.put(('analizando', etiqueta))
            self.servicio.analizar_mensajes(mensajes, asincrono=False)
        except Exception as err:
            if not self.detenido:
                self.eventos.put(('error', str(err) or 'No se pudieron leer los mensajes del chat.'))
        finally:
            self._lectura_en_curso.clear()
            if not self.detenido:
                self.eventos.put(('fin_carga', None))

    def probar_vivo(self):
        self._modo_demo = True
        resultado = ServicioAsistenteVivo.crear_resultado_demo(self.ventana.gestion.listar())
        self.controlador.aplicar_tema(self.ventana.tema_actual)
        self.controlador.mostrar_sugerencias(resultado, self._ultimo_rect)
        if self.ventana.panel_ia is not None:
            self.ventana.panel_ia.estado_vivo.setText(
                'Vista previa abierta: prueba «Usar», «Editar» o descartar cada tarjeta.'
            )

    def _monitorear_whatsapp(self):
        if self.detenido or not self.servicio.activo:
            return
        win = self._lector_chat.ventana_whatsapp_activa()
        if win is not None:
            self._ultimo_hwnd = win.hwnd
            self._ultimo_rect = win.rect
            self._ultima_ventana = win
            self._modo_demo = False
            if not self.controlador.barra.isVisible():
                self.controlador.mostrar_barra(win.rect)
            else:
                self.controlador.reposicionar(win.rect)
        elif not self.controlador.esta_en_foco_propio() and not self._modo_demo:
            if self.controlador.esta_visible():
                self.controlador.ocultar_temporalmente()

    def procesar_eventos(self):
        while True:
            try:
                tipo, dato = self.eventos.get_nowait()
            except queue.Empty:
                break
            if tipo == 'resultado':
                self.controlador.establecer_cargando(False)
                rect = (
                    self._lector_chat.rect_ventana(self._ultimo_hwnd) or self._ultimo_rect
                    if self._ultimo_hwnd else self._ultimo_rect
                )
                self.controlador.mostrar_sugerencias(dato, rect)
                if self.ventana.panel_ia is not None:
                    self.ventana.panel_ia.estado_vivo.setText(
                        f'Sugerencias listas · {dato.tema} ({dato.animo})'
                    )
            elif tipo == 'analizando':
                if self.controlador.barra.isVisible() or self._modo_demo or self.servicio.activo:
                    if not self.controlador.barra.isVisible():
                        self.controlador.mostrar_barra(self._ultimo_rect)
                    self.controlador.mostrar_aviso(str(dato) or 'Analizando mensaje…')
                if self.ventana.panel_ia is not None:
                    self.ventana.panel_ia.estado_vivo.setText(str(dato) or 'Analizando mensaje…')
            elif tipo == 'aviso_suave':
                if self.controlador.barra.isVisible() and not self._lectura_en_curso.is_set():
                    self.controlador.mostrar_aviso(str(dato))
            elif tipo == 'estado_insercion':
                self.controlador.mostrar_aviso(str(dato))
                self.ventana.estado.setText(str(dato))
            elif tipo == 'fin_carga':
                self.controlador.establecer_cargando(False)
            elif tipo == 'error':
                self.controlador.establecer_cargando(False)
                if self.controlador.barra.isVisible() or self._modo_demo or self.servicio.activo:
                    if not self.controlador.barra.isVisible():
                        self.controlador.mostrar_barra(self._ultimo_rect)
                    self.controlador.mostrar_aviso(str(dato))
                if self.ventana.panel_ia is not None:
                    self.ventana.panel_ia.estado_vivo.setText(str(dato))

    def detener(self):
        if self.detenido:
            return
        self.detenido = True
        self.timer.stop()
        if self.puente is not None:
            self.puente.detener()
        self.servicio.detener()
        self.controlador.detener()


def _crear_bandeja(ventana, sincronizar):
    tray = QSystemTrayIcon(QIcon(str(recurso('fraseya.ico'))), ventana)
    menu = QMenu(ventana)

    def mostrar():
        ventana.showNormal()
        ventana.raise_()
        ventana.activateWindow()

    for texto, accion in [
        ('Abrir FraseYa', mostrar),
        ('Sincronizar', sincronizar),
        ('Ocultar ventana', ventana.hide),
        ('Salir', ventana.close),
    ]:
        a = QAction(texto, menu)
        a.triggered.connect(accion)
        menu.addAction(a)
    tray.setContextMenu(menu)
    tray.activated.connect(lambda motivo: mostrar() if motivo == QSystemTrayIcon.DoubleClick else None)
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray.show()
    return tray


def _ejecutar_sesion(app, auth, sesion, ruta_usuario, con_teclado):
    with RepositorioSQLite(ruta_usuario) as repo:
        ventana = VentanaQt(GestionFrases(repo), autenticacion=auth, sesion=sesion)
        expansion = None
        eventos = queue.Queue()
        detenido = False

        servicio = ServicioSincronizacion(
            repo,
            crear_lector=lambda: RepositorioSupabase(auth.cliente),
            al_resultado=eventos.put,
        )
        servicio.configurar(Configuracion(repo).leer().intervalo_sincronizacion_min)

        if con_teclado:
            try:
                from .qt_expansion import ExpansionQt
                expansion = ExpansionQt(ventana, repo)
            except (ImportError, OSError, RuntimeError) as e:
                ventana.estado.setText('Expansión de teclado no disponible: ' + str(e))

        def configurar_ajustes(a):
            servicio.configurar(a.intervalo_sincronizacion_min)
            if expansion:
                expansion.aplicar(a)

        def sincronizar():
            if sesion.token == 'offline':
                ventana.sincronizacion.setText('Modo sin conexión · copia local')
                return
            ventana.sincronizacion.setText('Comprobando catálogo…')
            servicio.solicitar()

        ventana.al_configurar = configurar_ajustes
        ventana.al_sincronizar = sincronizar

        asistente_vivo = (
            _AsistenteVivoQt(ventana, auth.cliente, lambda: expansion)
            if sesion.token != 'offline'
            else None
        )
        tray = _crear_bandeja(ventana, sincronizar)
        timer = QTimer(ventana)

        def atender():
            while True:
                try:
                    r = eventos.get_nowait()
                except queue.Empty:
                    break
                _estado, texto = resumen_estado(repo, r, sin_conexion=sesion.token == 'offline')
                ventana.sincronizacion.setText(texto)
                tray.setToolTip('FraseYa · ' + texto)
                if r.estado == 'actualizada':
                    ventana.categorias()
                    ventana.refrescar()
                    ventana.frases_cambiaron()
            if asistente_vivo is not None:
                asistente_vivo.procesar_eventos()

        timer.timeout.connect(atender)
        timer.start(100)

        _, texto = resumen_estado(repo, sin_conexion=sesion.token == 'offline')
        ventana.sincronizacion.setText(texto)

        def detener():
            nonlocal detenido
            if detenido:
                return
            detenido = True
            timer.stop()
            tray.hide()
            servicio.detener()
            if asistente_vivo is not None:
                asistente_vivo.detener()
            if expansion is not None:
                expansion.detener()
            app.quit()

        ventana.al_salir = detener
        ventana.show()
        if sesion.token != 'offline':
            servicio.iniciar()
        try:
            app.exec()
        finally:
            relanzar = bool(getattr(ventana, 'solicito_cerrar_sesion', False))
            detener()
            ventana.deleteLater()
            app.processEvents()
        return relanzar


def abrir(ruta, con_teclado=True, configurar=False):
    app = QApplication.instance() or QApplication([])
    app.setApplicationName('FraseYa')
    app.setStyleSheet(hoja_estilo(_leer_tema_inicial(ruta)))
    app.setWindowIcon(QIcon(str(recurso('fraseya.ico'))))
    app.setQuitOnLastWindowClosed(False)

    archivo = Path(ruta).parent / 'supabase.json'
    if not archivo.exists() or configurar:
        if not configurar_conexion(archivo):
            return

    auth = AutenticacionSupabase(cargar_cliente(archivo))
    try:
        while True:
            app.setStyleSheet(hoja_estilo(_leer_tema_inicial(ruta)))
            acceso = AccesoQt(auth)
            if acceso.exec() != QDialog.Accepted or acceso.sesion is None:
                break
            sesion = acceso.sesion
            auth.validar(sesion)
            registrar_ultimo_perfil(ruta, sesion)
            ruta_usuario = ruta_bd_sesion(ruta, sesion)
            app.setStyleSheet(hoja_estilo(_leer_tema_inicial(ruta_usuario)))
            relanzar = False
            try:
                relanzar = _ejecutar_sesion(app, auth, sesion, ruta_usuario, con_teclado)
            finally:
                if auth._sesion:
                    auth.salir(auth._sesion)
            if not relanzar:
                break
    finally:
        if auth._sesion:
            auth.salir(auth._sesion)
        auth.cerrar()
