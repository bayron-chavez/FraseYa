"""Arranque de producción Qt con Auth, sincronización, bandeja y asistente en vivo."""
import queue
import threading
import time
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import QApplication, QDialog, QSystemTrayIcon, QMenu, QMessageBox
from fraseya.infraestructura import RepositorioSQLite
from fraseya.infraestructura.lector_chat import LectorChat, PuenteWhatsAppWeb, VentanaChat
from fraseya.infraestructura.supabase import cargar_cliente, AutenticacionSupabase, RepositorioSupabase
from fraseya.aplicacion.asistente_vivo import ServicioAsistenteVivo
from fraseya.aplicacion.configuracion import Configuracion
from fraseya.aplicacion.estado_sincronizacion import resumen_estado
from fraseya.aplicacion.gestion_frases import GestionFrases
from fraseya.aplicacion.recomendaciones_ia import RecomendadorIA
from fraseya.aplicacion.servicio_sincronizacion import ServicioSincronizacion
from fraseya.aplicacion.sesion import ruta_bd_sesion
from .qt_dialogos import AccesoQt, configurar_conexion, recurso
from .qt_flotante import ControladorFlotanteQt
from .qt_temas import hoja_estilo
from .qt_vista import VentanaQt, ESTILO


_VENTANA_EXT_ACTIVA_SEG = 20.0


def _leer_tema_inicial(ruta):
    if not Path(ruta).exists():
        return 'claro'
    try:
        with RepositorioSQLite(ruta) as repo:
            return Configuracion(repo).leer().tema
    except Exception:
        return 'claro'


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

    def _ejecutar_sesion(sesion, ruta_usuario):
        with RepositorioSQLite(ruta_usuario) as repo:
            ventana = VentanaQt(GestionFrases(repo), autenticacion=auth, sesion=sesion)
            expansion = None
            eventos = queue.Queue()
            eventos_vivo = queue.Queue()
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

            ventana.al_configurar = configurar_ajustes

            def sincronizar():
                if sesion.token == 'offline':
                    ventana.sincronizacion.setText('Modo sin conexión · copia local')
                    return
                ventana.sincronizacion.setText('Comprobando catálogo…')
                servicio.solicitar()

            ventana.al_sincronizar = sincronizar

            # --- Asistente en vivo (solo sesión online) ---
            lector_chat = None
            servicio_vivo = None
            puente_wsp = None
            controlador_flotante = None
            timer_vivo = None
            puente_disponible = False

            if sesion.token != 'offline':
                frases_lock = threading.Lock()
                frases_snapshot = [dict(f) for f in ventana.gestion.listar()]
                ultimo_hwnd_wsp = None
                ultimo_rect_wsp = None
                ultima_ventana_wsp = None
                ultimo_mensaje_ext_ts = 0.0
                modo_demo_vivo = False
                lectura_en_curso = threading.Event()

                def actualizar_snapshot():
                    copia = [dict(f) for f in ventana.gestion.listar()]
                    with frases_lock:
                        frases_snapshot[:] = copia

                def obtener_frases_snapshot():
                    with frases_lock:
                        return [dict(f) for f in frases_snapshot]

                anterior_cambiar = ventana.al_cambiar

                def _al_cambiar_completo():
                    if anterior_cambiar:
                        anterior_cambiar()
                    actualizar_snapshot()

                ventana.al_cambiar = _al_cambiar_completo

                def _texto_analizando(texto=''):
                    lineas = [l for l in str(texto or '').splitlines() if l.strip()]
                    if len(lineas) > 1:
                        return f'Analizando {len(lineas)} mensajes…'
                    return 'Analizando mensaje…'

                lector_chat = LectorChat()
                servicio_vivo = ServicioAsistenteVivo(
                    RecomendadorIA(auth.cliente),
                    obtener_frases_snapshot,
                    al_resultado=lambda res: eventos_vivo.put(('resultado', res)),
                    al_error=lambda msg: eventos_vivo.put(('error', msg)),
                    al_analizar=lambda txt='': eventos_vivo.put(('analizando', _texto_analizando(txt))),
                )

                def _al_mensaje_puente(texto, meta):
                    nonlocal ultimo_mensaje_ext_ts
                    ultimo_mensaje_ext_ts = time.monotonic()
                    # Solo almacena en el búfer en memoria (sin llamar a Gemini en automático)
                    if servicio_vivo.registrar_mensaje_entrante(texto, chat=meta.get('chat', '')):
                        eventos_vivo.put((
                            'aviso_suave',
                            'Mensaje nuevo en WhatsApp Web · Pulsa «Leer últimos 3»',
                        ))

                try:
                    puente = PuenteWhatsAppWeb(al_mensaje=_al_mensaje_puente)
                    puente.iniciar()
                    puente_wsp = puente
                    puente_disponible = True
                except OSError:
                    puente_wsp = None
                    puente_disponible = False

                def _usar_flotante(_frase, texto):
                    if not texto:
                        return
                    if expansion is not None and ultimo_hwnd_wsp:
                        hwnd_obj = ultimo_hwnd_wsp
                        controlador_flotante.ocultar_sugerencias()
                        try:
                            QApplication.clipboard().setText(texto)
                        except Exception:
                            pass
                        try:
                            from fraseya.infraestructura.teclado_global import activar_ventana
                            activar_ventana(hwnd_obj)
                        except Exception:
                            pass
                        ok = expansion.insertar_texto_en_ventana(
                            texto,
                            hwnd_obj,
                            enfocar_destino=lambda h=hwnd_obj: lector_chat.enfocar_caja_mensaje(h),
                        )
                        if ok:
                            controlador_flotante.mostrar_aviso(
                                'Frase copiada y pegada en WhatsApp. Revísala y envía.'
                            )
                            ventana.estado.setText(
                                'Frase copiada y pegada en WhatsApp. Revísala y envía.'
                            )
                        else:
                            controlador_flotante.mostrar_aviso(
                                'Espera a que termine la inserción en curso.'
                            )
                        return
                    QApplication.clipboard().setText(texto)
                    controlador_flotante.mostrar_aviso(
                        'Copiada al portapapeles. Pégala y revísala antes de enviar.'
                    )
                    ventana.estado.setText(
                        'Sugerencia copiada al portapapeles. Revísala antes de enviarla.'
                    )

                def _toggle_vivo(activo):
                    nonlocal modo_demo_vivo
                    estado = bool(activo)
                    if estado:
                        modo_demo_vivo = False
                        servicio_vivo.activar()
                        controlador_flotante.establecer_activo(True)
                        controlador_flotante.limpiar_contexto()
                        controlador_flotante.mostrar_aviso(
                            'Escuchando WhatsApp · Pulsa «Leer últimos 3» cuando quieras sugerencias.'
                        )
                        detalle = (
                            'Estado: Activo. Al abrir WhatsApp verás la barra flotante con el botón «Leer últimos 3».'
                            if puente_disponible else
                            'Estado: Activo en WhatsApp Desktop y Web (puerto local 47821 ocupado para extensión). '
                            'Usa «Leer últimos 3» en la barra flotante.'
                        )
                        if ventana.panel_ia is not None:
                            ventana.panel_ia.establecer_estado_vivo(True, detalle)
                    else:
                        servicio_vivo.pausar()
                        controlador_flotante.establecer_activo(False)
                        if not modo_demo_vivo:
                            controlador_flotante.ocultar_todo()
                        if ventana.panel_ia is not None:
                            ventana.panel_ia.establecer_estado_vivo(
                                False, 'Estado: Pausado. No se observan chats de WhatsApp.'
                            )

                def _ocultar_flotante():
                    nonlocal modo_demo_vivo
                    modo_demo_vivo = False
                    if servicio_vivo.activo:
                        servicio_vivo.pausar()
                        controlador_flotante.establecer_activo(False)
                        if ventana.panel_ia is not None:
                            ventana.panel_ia.establecer_estado_vivo(
                                False, 'Estado: Pausado al ocultar la barra flotante.'
                            )

                def _analizar_portapapeles():
                    nonlocal modo_demo_vivo
                    texto = QApplication.clipboard().text()
                    if not texto.strip():
                        if controlador_flotante.barra.isVisible():
                            controlador_flotante.mostrar_aviso(
                                'Portapapeles vacío. Copia un mensaje del cliente primero.'
                            )
                        if ventana.panel_ia is not None:
                            ventana.panel_ia.estado_vivo.setText(
                                'Portapapeles vacío. Copia un mensaje del cliente primero.'
                            )
                        return
                    modo_demo_vivo = True
                    controlador_flotante.mostrar_barra(ultimo_rect_wsp)
                    controlador_flotante.establecer_cargando(True)
                    controlador_flotante.mostrar_aviso('Analizando mensaje del portapapeles…')
                    if ventana.panel_ia is not None:
                        ventana.panel_ia.estado_vivo.setText('Analizando mensaje del portapapeles…')
                    servicio_vivo.analizar_manual(texto)

                def _leer_ultimos_3():
                    if detenido or lectura_en_curso.is_set():
                        return
                    lectura_en_curso.set()
                    controlador_flotante.establecer_cargando(True)
                    controlador_flotante.mostrar_aviso('Leyendo últimos 3 mensajes…')
                    if ventana.panel_ia is not None:
                        ventana.panel_ia.estado_vivo.setText('Leyendo últimos 3 mensajes de WhatsApp…')

                    def _trabajar():
                        nonlocal ultimo_hwnd_wsp, ultimo_rect_wsp, ultima_ventana_wsp
                        try:
                            win = lector_chat.ventana_whatsapp_activa()
                            if win is None and ultima_ventana_wsp is not None:
                                win = lector_chat.ventana_por_hwnd(ultima_ventana_wsp.hwnd)
                                if win is None:
                                    rect_vivo = lector_chat.rect_ventana(ultima_ventana_wsp.hwnd)
                                    if rect_vivo is not None:
                                        win = VentanaChat(
                                            hwnd=ultima_ventana_wsp.hwnd,
                                            titulo=ultima_ventana_wsp.titulo,
                                            rect=rect_vivo,
                                            tipo=ultima_ventana_wsp.tipo,
                                        )
                            if win is not None:
                                ultimo_hwnd_wsp = win.hwnd
                                ultimo_rect_wsp = win.rect
                                ultima_ventana_wsp = win

                            extension_reciente = (
                                ultimo_mensaje_ext_ts > 0.0
                                and (time.monotonic() - ultimo_mensaje_ext_ts) <= _VENTANA_EXT_ACTIVA_SEG
                            )
                            mensajes: list[str] = []
                            if win is not None:
                                if win.tipo == 'web' and extension_reciente:
                                    mensajes = servicio_vivo.obtener_ultimos_mensajes(limite=3)
                                    if not mensajes:
                                        mensajes = lector_chat.leer_ultimos_mensajes(win, limite=3)
                                else:
                                    mensajes = lector_chat.leer_ultimos_mensajes(win, limite=3)
                                    if not mensajes and win.tipo == 'web':
                                        mensajes = servicio_vivo.obtener_ultimos_mensajes(limite=3)
                            else:
                                mensajes = servicio_vivo.obtener_ultimos_mensajes(limite=3)

                            if detenido:
                                return
                            if not mensajes:
                                eventos_vivo.put((
                                    'error',
                                    'No se detectaron mensajes visibles. Abre un chat en WhatsApp o usa «Portapapeles».',
                                ))
                                return

                            n = len(mensajes)
                            etiqueta_leidos = (
                                f'Leídos {n} mensajes · Generando 3 opciones…'
                                if n > 1 else
                                'Leído 1 mensaje · Generando 3 opciones…'
                            )
                            eventos_vivo.put(('analizando', etiqueta_leidos))
                            servicio_vivo.analizar_mensajes(mensajes, asincrono=False)
                        except Exception as err:
                            if not detenido:
                                eventos_vivo.put((
                                    'error',
                                    str(err) or 'No se pudieron leer los mensajes del chat.',
                                ))
                        finally:
                            lectura_en_curso.clear()
                            if not detenido:
                                eventos_vivo.put(('fin_carga', None))

                    threading.Thread(
                        target=_trabajar,
                        name='fraseya-leer-ultimos-3',
                        daemon=True,
                    ).start()

                def _probar_vivo():
                    nonlocal modo_demo_vivo
                    modo_demo_vivo = True
                    resultado = ServicioAsistenteVivo.crear_resultado_demo(ventana.gestion.listar())
                    controlador_flotante.aplicar_tema(ventana.tema_actual)
                    controlador_flotante.mostrar_sugerencias(resultado, ultimo_rect_wsp)
                    if ventana.panel_ia is not None:
                        ventana.panel_ia.estado_vivo.setText(
                            'Vista previa abierta: prueba «Usar», «Editar» o descartar cada tarjeta.'
                        )

                controlador_flotante = ControladorFlotanteQt(
                    parent=ventana,
                    tema=ventana.tema_actual,
                    al_usar=_usar_flotante,
                    al_toggle_activo=_toggle_vivo,
                    al_leer_chat=_leer_ultimos_3,
                    al_analizar_portapapeles=_analizar_portapapeles,
                    al_ocultar=_ocultar_flotante,
                )
                ventana.al_cambiar_tema = controlador_flotante.aplicar_tema
                ventana.al_toggle_vivo = _toggle_vivo
                ventana.al_probar_vivo = _probar_vivo
                ventana.al_analizar_portapapeles = _analizar_portapapeles

                timer_vivo = QTimer(ventana)

                def _monitorear_whatsapp():
                    nonlocal ultimo_hwnd_wsp, ultimo_rect_wsp, ultima_ventana_wsp, modo_demo_vivo
                    if detenido or not servicio_vivo.activo:
                        return
                    win = lector_chat.ventana_whatsapp_activa()
                    if win is not None:
                        ultimo_hwnd_wsp = win.hwnd
                        ultimo_rect_wsp = win.rect
                        ultima_ventana_wsp = win
                        modo_demo_vivo = False
                        if not controlador_flotante.barra.isVisible():
                            controlador_flotante.mostrar_barra(win.rect)
                        else:
                            controlador_flotante.reposicionar(win.rect)
                    else:
                        if not controlador_flotante.esta_en_foco_propio() and not modo_demo_vivo:
                            if controlador_flotante.barra.isVisible() or controlador_flotante.tarjetas:
                                controlador_flotante.ocultar_todo()

                timer_vivo.timeout.connect(_monitorear_whatsapp)
                timer_vivo.start(800)

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

            timer = QTimer(ventana)

            def atender():
                while True:
                    try:
                        r = eventos.get_nowait()
                    except queue.Empty:
                        break
                    estado, texto = resumen_estado(repo, r, sin_conexion=sesion.token == 'offline')
                    ventana.sincronizacion.setText(texto)
                    tray.setToolTip('FraseYa · ' + texto)
                    if r.estado == 'actualizada':
                        ventana.categorias()
                        ventana.refrescar()
                        ventana.frases_cambiaron()

                if controlador_flotante is not None:
                    while True:
                        try:
                            tipo, dato = eventos_vivo.get_nowait()
                        except queue.Empty:
                            break
                        if tipo == 'resultado':
                            controlador_flotante.establecer_cargando(False)
                            rect = None
                            if lector_chat is not None and ultimo_hwnd_wsp:
                                rect = lector_chat.rect_ventana(ultimo_hwnd_wsp) or ultimo_rect_wsp
                            else:
                                rect = ultimo_rect_wsp
                            controlador_flotante.mostrar_sugerencias(dato, rect)
                            if ventana.panel_ia is not None:
                                ventana.panel_ia.estado_vivo.setText(
                                    f'Sugerencias listas · {dato.tema} ({dato.animo})'
                                )
                        elif tipo == 'analizando':
                            if controlador_flotante.barra.isVisible() or modo_demo_vivo or servicio_vivo.activo:
                                if not controlador_flotante.barra.isVisible():
                                    controlador_flotante.mostrar_barra(ultimo_rect_wsp)
                                controlador_flotante.mostrar_aviso(str(dato) or 'Analizando mensaje…')
                            if ventana.panel_ia is not None:
                                ventana.panel_ia.estado_vivo.setText(str(dato) or 'Analizando mensaje…')
                        elif tipo == 'aviso_suave':
                            if controlador_flotante.barra.isVisible() and not lectura_en_curso.is_set():
                                controlador_flotante.mostrar_aviso(str(dato))
                        elif tipo == 'fin_carga':
                            controlador_flotante.establecer_cargando(False)
                        elif tipo == 'error':
                            controlador_flotante.establecer_cargando(False)
                            if controlador_flotante.barra.isVisible() or modo_demo_vivo or servicio_vivo.activo:
                                if not controlador_flotante.barra.isVisible():
                                    controlador_flotante.mostrar_barra(ultimo_rect_wsp)
                                controlador_flotante.mostrar_aviso(str(dato))
                            if ventana.panel_ia is not None:
                                ventana.panel_ia.estado_vivo.setText(str(dato))

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
                if timer_vivo is not None:
                    timer_vivo.stop()
                tray.hide()
                servicio.detener()
                if puente_wsp is not None:
                    puente_wsp.detener()
                if servicio_vivo is not None:
                    servicio_vivo.detener()
                if controlador_flotante is not None:
                    controlador_flotante.detener()
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

    try:
        while True:
            app.setStyleSheet(hoja_estilo(_leer_tema_inicial(ruta)))
            acceso = AccesoQt(auth)
            if acceso.exec() != QDialog.Accepted or acceso.sesion is None:
                break
            sesion = acceso.sesion
            auth.validar(sesion)
            ruta_usuario = ruta_bd_sesion(ruta, sesion)
            app.setStyleSheet(hoja_estilo(_leer_tema_inicial(ruta_usuario)))
            relanzar = False
            try:
                relanzar = _ejecutar_sesion(sesion, ruta_usuario)
            finally:
                if auth._sesion:
                    auth.salir(auth._sesion)
            if not relanzar:
                break
    finally:
        if auth._sesion:
            auth.salir(auth._sesion)
        auth.cerrar()
