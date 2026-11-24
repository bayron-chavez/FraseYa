import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from unittest.mock import Mock,patch
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QDialog
from fraseya.aplicacion.sesion import Sesion, ruta_bd_sesion
from fraseya.presentacion.qt_aplicacion import abrir
from fraseya.presentacion.qt_expansion import ExpansionQt
from fraseya.presentacion.qt_vista import VentanaQt
from fraseya.aplicacion.gestion_frases import GestionFrases
from fraseya.infraestructura import RepositorioSQLite


def test_arranque_qt_offline_conserva_datos_y_cierra(tmp_path):
    app=QApplication.instance() or QApplication([])
    ruta=tmp_path/'fraseya.db'; (tmp_path/'supabase.json').write_text('{}')
    with RepositorioSQLite(ruta) as repo:
        g=GestionFrases(repo); g.crear('Persistente','!p','Hola {nombre}',g.categorias_propias()[0]['id'])
    auth=Mock(); auth._sesion=None; auth.cliente.url='https://example.supabase.co'
    acceso=Mock(); acceso.exec.return_value=QDialog.Accepted; acceso.sesion=Sesion('Offline','usuario','offline')
    def cerrar():
        for w in app.topLevelWidgets():
            if isinstance(w,VentanaQt): w.close()
    QTimer.singleShot(100,cerrar)
    with patch('fraseya.presentacion.qt_aplicacion.cargar_cliente'),patch('fraseya.presentacion.qt_aplicacion.AutenticacionSupabase',return_value=auth),patch('fraseya.presentacion.qt_aplicacion.AccesoQt',return_value=acceso):
        abrir(ruta,con_teclado=False)
    auth.cerrar.assert_called_once()
    with RepositorioSQLite(ruta) as repo: assert repo.listar_frases()[0]['titulo']=='Persistente'


def test_teclado_se_pausa_en_ventanas_propias():
    app=QApplication.instance() or QApplication([])
    with RepositorioSQLite(':memory:') as repo:
        ventana=VentanaQt(GestionFrases(repo),demostracion=True)
        with patch('fraseya.presentacion.qt_expansion.TecladoGlobal') as teclado:
            expansion=ExpansionQt(ventana,repo)
            with patch.object(QApplication,'activeWindow',return_value=ventana):
                expansion.actualizar_pausa(); assert teclado.return_value.pausado
            with patch.object(QApplication,'activeWindow',return_value=None):
                expansion.actualizar_pausa(); assert not teclado.return_value.pausado
            expansion.detener()
        ventana.close()


def test_expansion_insertar_texto_en_ventana_y_encadenamiento():
    app = QApplication.instance() or QApplication([])
    with RepositorioSQLite(':memory:') as repo:
        ventana = VentanaQt(GestionFrases(repo), demostracion=True)
        notificaciones_previas = []
        ventana.al_cambiar = lambda: notificaciones_previas.append(True)
        with patch('fraseya.presentacion.qt_expansion.TecladoGlobal'), \
             patch('fraseya.presentacion.qt_expansion.EscritorTexto'):
            expansion = ExpansionQt(ventana, repo)
            expansion.motor.insertar = Mock(return_value=True)

            assert expansion.insertar_texto_en_ventana('Respuesta lista', hwnd_destino=98765) is True
            expansion.motor.insertar.assert_called_once_with('Respuesta lista', 98765)
            assert expansion.insertar_texto_en_ventana('', hwnd_destino=98765) is False

            # Con callback enfocar_destino lo reenvía como antes_de_escribir sin pulsar Enter
            enfoques = []
            expansion.motor.insertar.reset_mock()
            assert expansion.insertar_texto_en_ventana(
                'Con foco', hwnd_destino=98765, enfocar_destino=lambda: enfoques.append(98765)
            ) is True
            assert expansion.motor.insertar.call_count == 1
            args, kwargs = expansion.motor.insertar.call_args
            assert args == ('Con foco', 98765)
            assert callable(kwargs.get('antes_de_escribir'))
            with patch('fraseya.presentacion.qt_expansion.activar_ventana') as act_mock, \
                 patch('fraseya.presentacion.qt_expansion.time.sleep'):
                kwargs['antes_de_escribir']()
            act_mock.assert_called_once_with(98765)
            assert enfoques == [98765]

            ventana.frases_cambiaron()
            assert notificaciones_previas == [True]
            expansion.detener()
        ventana.close()


def test_flujo_bajo_demanda_no_bombardea_ia_y_leer_ultimos_3_inserta_en_whatsapp(tmp_path):
    from fraseya.infraestructura.lector_chat import VentanaChat

    app = QApplication.instance() or QApplication([])
    ruta = tmp_path / 'fraseya_bajo_demanda.db'
    (tmp_path / 'supabase.json').write_text('{}', encoding='utf8')
    sesion_agente = Sesion('agente@example.test', 'usuario', 'token-online')
    with RepositorioSQLite(ruta_bd_sesion(ruta, sesion_agente)) as repo:
        g = GestionFrases(repo)
        g.crear('Saludo', '!hola', 'Hola, con gusto te ayudo.', g.categorias_propias()[0]['id'])

    auth = Mock()
    auth._sesion = None
    auth.cliente.url = 'https://example.supabase.co'
    acceso = Mock()
    acceso.exec.return_value = QDialog.Accepted
    acceso.sesion = sesion_agente

    puente_falso = Mock()
    puente_falso.iniciar.return_value = 47821
    servicio_sync_falso = Mock()

    win_wsp = VentanaChat(7777, 'WhatsApp', (40, 40, 900, 680), 'desktop')
    lector_falso = Mock()
    lector_falso.ventana_whatsapp_activa.return_value = win_wsp
    lector_falso.rect_ventana.return_value = win_wsp.rect
    lector_falso.leer_ultimos_mensajes.return_value = ['Hola', 'Quiero comprar sushi']
    lector_falso.enfocar_caja_mensaje.return_value = True

    recomendador_falso = Mock()
    recomendador_falso.sugerir.return_value = []
    recomendador_falso.generar.return_value = {
        'titulo': 'Sushi',
        'categoria': 'General',
        'contenido': '¡Hola! Con gusto tomamos tu pedido de sushi. ¿Qué rolls deseas?',
    }

    expansion_falsa = Mock()
    expansion_falsa.insertar_texto_en_ventana.return_value = True

    controladores = []
    from fraseya.presentacion.qt_flotante import ControladorFlotanteQt as ControladorReal

    def crear_controlador(*args, **kwargs):
        ctrl = ControladorReal(*args, **kwargs)
        controladores.append(ctrl)
        return ctrl

    observado = {}

    def ejecutar_flujo():
        ventanas = [w for w in app.topLevelWidgets() if isinstance(w, VentanaQt) and w.isVisible()]
        if not ventanas:
            QTimer.singleShot(50, ejecutar_flujo)
            return
        v = ventanas[0]
        v.abrir_ia()
        v.panel_ia.btn_vivo.click()
        app.processEvents()

        # Esperar más de 1 tick de _monitorear_whatsapp (800 ms): NO debe llamar a la IA ni leer chat automáticamente
        def verificar_sin_polling_y_pulsar_boton():
            observado['sugerir_antes_boton'] = recomendador_falso.sugerir.call_count
            observado['leer_antes_boton'] = lector_falso.leer_ultimos_mensajes.call_count
            observado['barra_visible_sobre_wsp'] = controladores[0].barra.isVisible()

            # Pulsar "Leer últimos 3" dispara la lectura bajo demanda
            controladores[0].barra.btn_leer_chat.click()

            def verificar_tarjetas_y_usar():
                if len(controladores[0].tarjetas) < 3:
                    QTimer.singleShot(40, verificar_tarjetas_y_usar)
                    return
                observado['tarjetas_generadas'] = len(controladores[0].tarjetas)
                observado['sugerir_despues_boton'] = recomendador_falso.sugerir.call_count
                observado['generar_despues_boton'] = recomendador_falso.generar.call_count

                # Usar tarjeta 1 inserta directo en WhatsApp sin volver a FraseYa
                controladores[0].tarjetas[0].btn_usar.click()
                app.processEvents()
                observado['tarjetas_tras_usar'] = len(controladores[0].tarjetas)
                observado['aviso_tras_usar'] = controladores[0].barra.lbl_aviso.text()
                v.close()

            QTimer.singleShot(80, verificar_tarjetas_y_usar)

        QTimer.singleShot(950, verificar_sin_polling_y_pulsar_boton)

    QTimer.singleShot(80, ejecutar_flujo)
    with patch('fraseya.presentacion.qt_aplicacion.cargar_cliente'), \
         patch('fraseya.presentacion.qt_aplicacion.AutenticacionSupabase', return_value=auth), \
         patch('fraseya.presentacion.qt_aplicacion.AccesoQt', return_value=acceso), \
         patch('fraseya.presentacion.qt_aplicacion.ServicioSincronizacion', return_value=servicio_sync_falso), \
         patch('fraseya.presentacion.qt_aplicacion.PuenteWhatsAppWeb', return_value=puente_falso), \
         patch('fraseya.presentacion.qt_aplicacion.LectorChat', return_value=lector_falso), \
         patch('fraseya.presentacion.qt_aplicacion.RecomendadorIA', return_value=recomendador_falso), \
         patch('fraseya.presentacion.qt_aplicacion.ControladorFlotanteQt', side_effect=crear_controlador), \
         patch('fraseya.presentacion.qt_expansion.ExpansionQt', return_value=expansion_falsa):
        abrir(ruta, con_teclado=True)

    # Cero llamadas automáticas en bucle durante _monitorear_whatsapp
    assert observado['sugerir_antes_boton'] == 0
    assert observado['leer_antes_boton'] == 0
    assert observado['barra_visible_sobre_wsp'] is True
    # Al pulsar "Leer últimos 3": 3 tarjetas con <= 2 llamadas IA
    assert observado['tarjetas_generadas'] == 3
    assert observado['sugerir_despues_boton'] == 1
    assert observado['generar_despues_boton'] == 1
    # Al pulsar "Usar": inserta directo en hwnd de WhatsApp pasando enfocar_destino
    assert expansion_falsa.insertar_texto_en_ventana.call_count == 1
    args, kwargs = expansion_falsa.insertar_texto_en_ventana.call_args
    assert args[1] == 7777
    assert 'sushi' in args[0].casefold()
    assert callable(kwargs.get('enfocar_destino'))
    assert kwargs['enfocar_destino']() is True
    lector_falso.enfocar_caja_mensaje.assert_called_once_with(7777)
    assert observado['tarjetas_tras_usar'] == 0
    assert 'WhatsApp' in observado['aviso_tras_usar']


def test_arranque_qt_online_tema_oscuro_asistente_vivo_y_cierre_limpio(tmp_path):
    from fraseya.aplicacion.configuracion import Configuracion
    from fraseya.presentacion.qt_temas import ESTILO_OSCURO

    app = QApplication.instance() or QApplication([])
    ruta = tmp_path / 'fraseya_online.db'
    (tmp_path / 'supabase.json').write_text('{}', encoding='utf8')
    sesion_agente = Sesion('agente@example.test', 'usuario', 'token-online')
    with RepositorioSQLite(ruta_bd_sesion(ruta, sesion_agente)) as repo:
        g = GestionFrases(repo)
        g.crear('Disculpa', '!disc', 'Lamentamos la demora.', g.categorias_propias()[0]['id'])
        Configuracion(repo).guardar({'tema': 'oscuro'})

    auth = Mock()
    auth._sesion = None
    auth.cliente.url = 'https://example.supabase.co'

    def crear_acceso(_auth):
        acceso = Mock()
        acceso.exec.return_value = QDialog.Accepted
        acceso.sesion = sesion_agente
        return acceso

    puente_falso = Mock()
    puente_falso.iniciar.return_value = 47821

    servicio_sync_falso = Mock()
    controladores = []

    from fraseya.presentacion.qt_flotante import ControladorFlotanteQt as ControladorReal

    def crear_controlador(*args, **kwargs):
        ctrl = ControladorReal(*args, **kwargs)
        controladores.append(ctrl)
        return ctrl

    observado = {}

    def interactuar_y_cerrar():
        ventanas = [w for w in app.topLevelWidgets() if isinstance(w, VentanaQt) and w.isVisible()]
        if not ventanas:
            QTimer.singleShot(50, interactuar_y_cerrar)
            return
        v = ventanas[0]
        observado['tema_inicial'] = v.tema_actual
        observado['estilo_sesion'] = app.styleSheet()
        observado['ctrl_tema_inicial'] = controladores[0].tema
        v.abrir_ia()
        v.panel_ia.btn_demo_vivo.click()
        app.processEvents()
        observado['tarjetas_demo'] = len(controladores[0].tarjetas)
        observado['barra_visible'] = controladores[0].barra.isVisible()
        observado['chip_tema_demo'] = controladores[0].barra.chip_tema.text()

        v.panel_ia.btn_vivo.click()
        app.processEvents()
        observado['activo_despues_toggle'] = controladores[0].activo
        observado['tarjetas_tras_activar'] = len(controladores[0].tarjetas)
        observado['chip_tema_tras_activar'] = controladores[0].barra.chip_tema.text()
        observado['chip_animo_tras_activar'] = controladores[0].barra.chip_animo.text()
        observado['aviso_tras_activar'] = controladores[0].barra.lbl_aviso.text()

        # Cambiar tema desde VentanaQt sincroniza las ventanas flotantes
        v.alternar_tema()
        app.processEvents()
        observado['ctrl_tema_tras_cambio'] = controladores[0].tema

        v.close()

    QTimer.singleShot(120, interactuar_y_cerrar)
    with patch('fraseya.presentacion.qt_aplicacion.cargar_cliente'), \
         patch('fraseya.presentacion.qt_aplicacion.AutenticacionSupabase', return_value=auth), \
         patch('fraseya.presentacion.qt_aplicacion.AccesoQt', side_effect=crear_acceso), \
         patch('fraseya.presentacion.qt_aplicacion.ServicioSincronizacion', return_value=servicio_sync_falso), \
         patch('fraseya.presentacion.qt_aplicacion.PuenteWhatsAppWeb', return_value=puente_falso), \
         patch('fraseya.presentacion.qt_aplicacion.ControladorFlotanteQt', side_effect=crear_controlador):
        abrir(ruta, con_teclado=False)

    assert observado['estilo_sesion'] == ESTILO_OSCURO
    assert observado['tema_inicial'] == 'oscuro'
    assert observado['ctrl_tema_inicial'] == 'oscuro'
    assert observado['tarjetas_demo'] >= 1
    assert observado['barra_visible'] is True
    assert 'Pedido' in observado['chip_tema_demo']
    assert observado['activo_despues_toggle'] is True
    assert observado['tarjetas_tras_activar'] == 0
    assert observado['chip_tema_tras_activar'] == 'Esperando mensaje…'
    assert observado['chip_animo_tras_activar'] == 'Ánimo: —'
    assert 'Escuchando WhatsApp' in observado['aviso_tras_activar']
    assert observado['ctrl_tema_tras_cambio'] == 'claro'
    puente_falso.iniciar.assert_called_once()
    puente_falso.detener.assert_called_once()
    servicio_sync_falso.detener.assert_called_once()
    auth.cerrar.assert_called_once()


def test_arranque_qt_online_tolera_puerto_puente_ocupado(tmp_path):
    app = QApplication.instance() or QApplication([])
    ruta = tmp_path / 'fraseya_puerto.db'
    (tmp_path / 'supabase.json').write_text('{}', encoding='utf8')
    auth = Mock()
    auth._sesion = None
    auth.cliente.url = 'https://example.supabase.co'
    acceso = Mock()
    acceso.exec.return_value = QDialog.Accepted
    acceso.sesion = Sesion('agente@example.test', 'usuario', 'token-online')

    puente_ocupado = Mock()
    puente_ocupado.iniciar.side_effect = OSError('Puerto 47821 ocupado')
    servicio_sync_falso = Mock()
    estado_reportado = []

    def activar_y_cerrar():
        ventanas = [w for w in app.topLevelWidgets() if isinstance(w, VentanaQt) and w.isVisible()]
        if not ventanas:
            QTimer.singleShot(50, activar_y_cerrar)
            return
        v = ventanas[0]
        v.abrir_ia()
        v.panel_ia.btn_vivo.click()
        estado_reportado.append(v.panel_ia.estado_vivo.text())
        v.close()

    QTimer.singleShot(120, activar_y_cerrar)
    with patch('fraseya.presentacion.qt_aplicacion.cargar_cliente'), \
         patch('fraseya.presentacion.qt_aplicacion.AutenticacionSupabase', return_value=auth), \
         patch('fraseya.presentacion.qt_aplicacion.AccesoQt', return_value=acceso), \
         patch('fraseya.presentacion.qt_aplicacion.ServicioSincronizacion', return_value=servicio_sync_falso), \
         patch('fraseya.presentacion.qt_aplicacion.PuenteWhatsAppWeb', return_value=puente_ocupado):
        abrir(ruta, con_teclado=False)

    assert len(estado_reportado) == 1
    assert '47821' in estado_reportado[0]
    auth.cerrar.assert_called_once()


def test_cambio_de_usuario_en_misma_app_aisla_frases_locales_y_conserva_por_correo(tmp_path):
    app = QApplication.instance() or QApplication([])
    ruta = tmp_path / 'fraseya_multi.db'
    (tmp_path / 'supabase.json').write_text('{}', encoding='utf8')

    sesiones = [
        Sesion('ana@empresa.test', 'usuario', 'tok-ana'),
        Sesion('beto@empresa.test', 'usuario', 'tok-beto'),
        Sesion('Ana@Empresa.test', 'usuario', 'tok-ana-2'),
    ]
    auth = Mock()
    auth._sesion = None
    auth.cliente.url = 'https://example.supabase.co'

    def validar_sesion(s, **_kw):
        auth._sesion = s

    auth.validar.side_effect = validar_sesion
    auth.salir.side_effect = lambda _s: setattr(auth, '_sesion', None)

    turno = {'n': 0}
    observado = {'titulos_por_turno': []}

    def crear_acceso(_auth):
        idx = turno['n']
        turno['n'] += 1
        acceso = Mock()
        acceso.exec.return_value = QDialog.Accepted
        acceso.sesion = sesiones[idx]

        def actuar():
            ventanas = [
                w for w in app.topLevelWidgets()
                if isinstance(w, VentanaQt) and w.isVisible() and not w._cerrando
            ]
            if not ventanas:
                QTimer.singleShot(40, actuar)
                return
            v = ventanas[0]
            titulos = [f['titulo'] for f in v.gestion.listar()]
            observado['titulos_por_turno'].append(titulos)
            if idx == 0:
                cat_id = v.gestion.categorias_propias()[0]['id']
                v.gestion.crear('Frase secreta Ana', '!ana', 'Hola desde Ana', cat_id)
                v.cerrar_sesion()
            elif idx == 1:
                cat_id = v.gestion.categorias_propias()[0]['id']
                v.gestion.crear('Frase propia Beto', '!beto', 'Hola desde Beto', cat_id)
                v.cerrar_sesion()
            else:
                v.close()

        QTimer.singleShot(60, actuar)
        return acceso

    servicio_sync_falso = Mock()
    puente_falso = Mock()
    puente_falso.iniciar.return_value = 47821

    with patch('fraseya.presentacion.qt_aplicacion.cargar_cliente'), \
         patch('fraseya.presentacion.qt_aplicacion.AutenticacionSupabase', return_value=auth), \
         patch('fraseya.presentacion.qt_aplicacion.AccesoQt', side_effect=crear_acceso), \
         patch('fraseya.presentacion.qt_aplicacion.ServicioSincronizacion', return_value=servicio_sync_falso), \
         patch('fraseya.presentacion.qt_aplicacion.PuenteWhatsAppWeb', return_value=puente_falso):
        abrir(ruta, con_teclado=False)

    assert turno['n'] == 3
    # Turno 0 (Ana inicial): vacío -> crea 'Frase secreta Ana' y cierra sesión
    assert observado['titulos_por_turno'][0] == []
    # Turno 1 (Beto): aislado, no ve la frase de Ana -> crea 'Frase propia Beto' y cierra sesión
    assert observado['titulos_por_turno'][1] == []
    # Turno 2 (Ana vuelve a entrar, incluso con mayúsculas en el correo): ve su frase local y no la de Beto
    assert observado['titulos_por_turno'][2] == ['Frase secreta Ana']
    assert auth.salir.call_count == 3
    auth.cerrar.assert_called_once()
    # Las rutas en disco no contienen el correo electrónico en texto plano
    archivos_bd = list((tmp_path / 'usuarios').glob('*.db'))
    assert len(archivos_bd) == 2
    assert all('ana' not in a.name and 'beto' not in a.name for a in archivos_bd)


def test_offline_abre_catalogo_del_ultimo_perfil_conectado(tmp_path):
    app = QApplication.instance() or QApplication([])
    ruta = tmp_path / 'fraseya_offline_perfil.db'
    (tmp_path / 'supabase.json').write_text('{}', encoding='utf8')

    sesiones = [
        Sesion('ana@empresa.test', 'usuario', 'tok-ana'),
        Sesion('Offline', 'usuario', 'offline'),
    ]
    auth = Mock()
    auth._sesion = None
    auth.cliente.url = 'https://example.supabase.co'
    auth.validar.side_effect = lambda s, **_kw: setattr(auth, '_sesion', s)
    auth.salir.side_effect = lambda _s: setattr(auth, '_sesion', None)

    turno = {'n': 0}
    observado = {'titulos_por_turno': []}

    def crear_acceso(_auth):
        idx = turno['n']
        turno['n'] += 1
        acceso = Mock()
        acceso.exec.return_value = QDialog.Accepted
        acceso.sesion = sesiones[idx]

        def actuar():
            ventanas = [
                w for w in app.topLevelWidgets()
                if isinstance(w, VentanaQt) and w.isVisible() and not w._cerrando
            ]
            if not ventanas:
                QTimer.singleShot(40, actuar)
                return
            v = ventanas[0]
            observado['titulos_por_turno'].append([f['titulo'] for f in v.gestion.listar()])
            if idx == 0:
                cat_id = v.gestion.categorias_propias()[0]['id']
                v.gestion.crear('Guardada online', '!on', 'Contenido sincronizado', cat_id)
                v.gestion.repo.reemplazar_compartidas(1, 'admin', '2026-10-01', [{
                    'nombre': 'Central',
                    'frases': [{'titulo': 'Compartida Central', 'abreviatura': '!cen', 'contenido': 'Hola'}],
                }])
                v.cerrar_sesion()
            else:
                v.close()

        QTimer.singleShot(60, actuar)
        return acceso

    servicio_sync_falso = Mock()
    puente_falso = Mock()
    puente_falso.iniciar.return_value = 47821

    with patch('fraseya.presentacion.qt_aplicacion.cargar_cliente'), \
         patch('fraseya.presentacion.qt_aplicacion.AutenticacionSupabase', return_value=auth), \
         patch('fraseya.presentacion.qt_aplicacion.AccesoQt', side_effect=crear_acceso), \
         patch('fraseya.presentacion.qt_aplicacion.ServicioSincronizacion', return_value=servicio_sync_falso), \
         patch('fraseya.presentacion.qt_aplicacion.PuenteWhatsAppWeb', return_value=puente_falso):
        abrir(ruta, con_teclado=False)

    assert observado['titulos_por_turno'][0] == []
    assert set(observado['titulos_por_turno'][1]) == {'Compartida Central', 'Guardada online'}
