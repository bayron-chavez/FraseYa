import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
pytest.importorskip('PySide6')
from unittest.mock import Mock
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QWidget
from fraseya.aplicacion.gestion_frases import GestionFrases
from fraseya.aplicacion.sesion import Sesion
from fraseya.infraestructura import RepositorioSQLite
from fraseya.presentacion.qt_vista import VentanaQt


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def test_busqueda_favoritas_y_guardado_propio(app):
    with RepositorioSQLite(':memory:') as repo:
        g=GestionFrases(repo); cat=g.categorias_propias()[0]['id']
        uno=g.crear('Conexión','!red','Hola {nombre}',cat)
        g.crear('Pedido','!pedido','Pedido {pedido}',cat)
        g.alternar_favorita(uno)
        v=VentanaQt(g,True)
        v.busqueda.setText('!pedido'); assert v.lista.count()==1
        v.busqueda.clear(); v.cambiar_vista(True); assert v.lista.count()==1
        v.cambiar_vista(False); v.nueva()
        v.titulo.setText('Nueva'); v.abreviatura.setText('!nueva'); v.contenido.setPlainText('Gracias {nombre}')
        v.guardar_frase(); assert len(g.listar())==3
        assert v.seleccion['origen']=='propia'
        assert 'Carolina' in v.preview.toPlainText()
        v.close()


def test_compartida_solo_lectura_y_copia_propia(app):
    with RepositorioSQLite(':memory:') as repo:
        g=GestionFrases(repo); g.categorias_propias()
        catalogo=repo.crear_catalogo('Central','compartida')
        categoria=repo.crear_categoria(catalogo,'General')
        ident=repo.crear_frase(categoria,'Compartida','!central','Texto central','compartida')
        v=VentanaQt(g,True)
        assert v.seleccion['id']==ident
        assert v.contenido.isReadOnly() and not v.guardar.isEnabled() and not v.eliminar.isEnabled()
        v.duplicar()
        assert v.seleccion['origen']=='propia' and not v.contenido.isReadOnly()
        assert repo.obtener_frase(ident)['contenido']=='Texto central'
        v.close()


def test_todas_las_secciones_se_abren_en_la_misma_ventana(app):
    with RepositorioSQLite(':memory:') as repo:
        g=GestionFrases(repo); cat=g.categorias_propias()[0]['id']
        g.crear('Saludo','!hola','Hola {nombre}',cat)
        auth=Mock()
        auth.cliente.solicitar.return_value={'nombre':'Demo','servicios':'','horarios':'','procedimientos':''}
        sesion=Sesion('admin@example.test','administrador','token')
        v=VentanaQt(g,demostracion=False,autenticacion=auth,sesion=sesion)
        v.show(); app.processEvents()

        def sin_dialogos_visibles():
            return not any(isinstance(w,QDialog) and w.isVisible() for w in app.topLevelWidgets())

        v.abrir_ia()
        assert v.paginas.currentWidget() is v.panel_ia and v.nav_ia.isChecked() and sin_dialogos_visibles()

        v.abrir_empresa()
        assert v.paginas.currentWidget() is v.panel_empresa and sin_dialogos_visibles()

        v.importar_excel()
        assert v.paginas.currentWidget() is v.panel_importar and v.nav_importar.isChecked() and sin_dialogos_visibles()

        v.ajustes()
        assert v.paginas.currentWidget() is v.panel_ajustes and v.nav_configuracion.isChecked() and sin_dialogos_visibles()

        v.categorias_admin()
        assert v.paginas.currentWidget() is v.panel_categorias and v.nav_categorias.isChecked() and sin_dialogos_visibles()

        assert not hasattr(v, 'nav_usuarios')

        v.cambiar_vista(False)
        v.copiar()
        assert v.paginas.currentWidget() is v.panel_variables and sin_dialogos_visibles()
        v.panel_variables.entradas['nombre'].setText('Ana')
        assert v.panel_variables.confirmar()
        assert app.clipboard().text()=='Hola Ana'
        assert v.paginas.currentWidget() is v._paginas['frases']

        # Confirmaciones inline sin ventanas emergentes
        v.insertar_variable('nombre')
        assert not v.barra_var_repetida.isHidden() and sin_dialogos_visibles()
        v._resolver_var_repetida(True)
        assert '{nombre_2}' in v.contenido.toPlainText() and v.barra_var_repetida.isHidden()

        v.eliminar_frase()
        assert not v.confirmar_eliminacion.isHidden() and sin_dialogos_visibles()
        v._confirmar_eliminar_frase()
        assert len(g.listar())==0 and v.confirmar_eliminacion.isHidden()

        v.panel_empresa.ocupada=False
        v.trabajos.pendientes=0
        v.close()


def test_ajustes_y_categorias_integrados_persisten(app):
    with RepositorioSQLite(':memory:') as repo:
        g=GestionFrases(repo)
        auth=Mock(); sesion=Sesion('admin@example.test','administrador','token')
        aplicados=[]
        v=VentanaQt(g,demostracion=False,autenticacion=auth,sesion=sesion)
        v.al_configurar=aplicados.append

        v.ajustes()
        v.panel_ajustes.tecla.setCurrentText('enter')
        v.panel_ajustes.velocidad.setValue(35)
        v.panel_ajustes.intervalo.setValue(10)
        assert v.panel_ajustes.guardar()
        assert len(aplicados)==1 and aplicados[0].tecla_confirmacion=='enter' and aplicados[0].velocidad_ms==35

        v.categorias_admin()
        v.panel_categorias.nueva()
        v.panel_categorias.nombre.setText('Ventas')
        v.panel_categorias.color.setText('#10B981')
        v.panel_categorias.guardar()
        assert any(c['nombre']=='Ventas' and c['color']=='#10B981' for c in g.categorias_propias())
        v.close()


def test_publicar_y_retirar_integrados_sin_dialogos(app):
    import time
    from unittest.mock import patch
    from types import SimpleNamespace
    with RepositorioSQLite(':memory:') as repo:
        g=GestionFrases(repo); cat=g.categorias_propias()[0]['id']
        g.crear('Propia','!propia','Hola',cat)
        catalogo=repo.crear_catalogo('Central','compartida')
        categoria=repo.crear_categoria(catalogo,'General')
        repo.crear_frase(categoria,'Compartida','!comp','Texto','compartida')

        auth=Mock(); auth.cliente.url='https://example.supabase.co'
        sesion=Sesion('admin@example.test','administrador','token')
        v=VentanaQt(g,demostracion=False,autenticacion=auth,sesion=sesion)
        sincronizaciones=[]
        v.al_sincronizar=lambda:sincronizaciones.append(True)

        vista_falsa=SimpleNamespace(version=24,cantidad_frases=2,nuevas=1,modificadas=0,eliminadas=0)
        servicio_falso=Mock()
        servicio_falso.recoger_categorias.return_value=[]
        servicio_falso.preparar.return_value=vista_falsa
        servicio_falso.publicar.return_value=SimpleNamespace(version=24)

        with patch('fraseya.aplicacion.publicacion_supabase.PublicacionSupabase',return_value=servicio_falso):
            v.publicar(False)
            assert v.paginas.currentWidget() is v.panel_catalogo
            limite=time.monotonic()+3
            while v.panel_catalogo.ocupada and time.monotonic()<limite: app.processEvents(); time.sleep(.01)
            assert 'Versión 24' in v.panel_catalogo.resumen_version.text()
            assert v.panel_catalogo.btn_confirmar.isEnabled()

            v.panel_catalogo._confirmar()
            limite=time.monotonic()+3
            while v.panel_catalogo.ocupada and time.monotonic()<limite: app.processEvents(); time.sleep(.01)
            assert 'Publicado correctamente' in v.panel_catalogo.resumen_version.text()
            assert len(sincronizaciones)==1

            v.publicar(True)
            assert v.paginas.currentWidget() is v.panel_catalogo and v.nav_catalogo.isChecked()
            assert v.panel_catalogo.btn_modo_retirar.isChecked()
            assert not v.panel_catalogo.panel_retiro.isHidden()
            limite=time.monotonic()+3
            while v.panel_catalogo.ocupada and time.monotonic()<limite: app.processEvents(); time.sleep(.01)
            assert v.panel_catalogo.selector_retiro.count()==1
        v.close()


def test_interfaz_siempre_en_tema_claro_sin_control_para_cambiarlo(app, tmp_path):
    from PySide6.QtWidgets import QLabel as QtLabel
    from fraseya.aplicacion.configuracion import Configuracion
    from fraseya.infraestructura.escritor_texto import VELOCIDAD_MAX_MS, VELOCIDAD_MIN_MS
    from fraseya.presentacion.qt_temas import ESTILO

    ruta = tmp_path / 'tema_persistencia.db'
    with RepositorioSQLite(ruta) as repo:
        g = GestionFrases(repo)
        cat = g.categorias_propias()[0]['id']
        g.crear('Saludo', '!hola', 'Hola {nombre}', cat)
        auth = Mock()
        auth.cliente.solicitar.return_value = {'nombre': 'Demo', 'servicios': '', 'horarios': '', 'procedimientos': ''}
        sesion = Sesion('admin@example.test', 'administrador', 'token')
        # Una preferencia oscura guardada por una versión anterior se ignora.
        Configuracion(repo).guardar({'tema': 'oscuro'})

        v = VentanaQt(g, demostracion=False, autenticacion=auth, sesion=sesion)

        assert v.panel_ajustes.velocidad.minimum() == VELOCIDAD_MIN_MS
        assert v.panel_ajustes.velocidad.maximum() == VELOCIDAD_MAX_MS
        assert v.tema_actual == 'claro'
        assert not hasattr(v, 'btn_tema')
        assert not hasattr(v.panel_ajustes, 'tema')
        assert app.styleSheet() == ESTILO
        assert v.styleSheet() == ESTILO

        v.ajustes()
        v.panel_ajustes.restablecer()
        assert v.panel_ajustes.guardar()
        assert app.styleSheet() == ESTILO

        # Verificar que widgets de scroll usan scroll_content y no background:white
        v.abrir_ia()
        v.copiar()
        assert any(w.objectName() == 'scroll_content' for w in v.panel_ia.findChildren(QWidget))
        assert any(w.objectName() == 'scroll_content' for w in v.panel_empresa.findChildren(QWidget))
        assert any(w.objectName() == 'scroll_content' for w in v.panel_variables.findChildren(QWidget))
        assert all(lbl.textFormat() == Qt.PlainText for lbl in v.findChildren(QtLabel))

        v.panel_empresa.ocupada = False
        v.trabajos.pendientes = 0
        v.close()


def test_panel_ia_modo_vivo_toggle_demo_y_callbacks(app):
    from PySide6.QtWidgets import QLabel as QtLabel
    with RepositorioSQLite(':memory:') as repo:
        g = GestionFrases(repo)
        cat = g.categorias_propias()[0]['id']
        g.crear('Disculpa', '!disc', 'Lamentamos la demora en tu pedido.', cat)
        g.crear('Seguimiento', '!seg', 'Compártenos tu número de orden.', cat)
        g.crear('Escalar', '!esc', 'Derivamos tu caso con prioridad.', cat)
        auth = Mock()
        sesion = Sesion('agente@example.test', 'usuario', 'token')

        v = VentanaQt(g, demostracion=False, autenticacion=auth, sesion=sesion)
        v.abrir_ia()
        panel = v.panel_ia
        assert panel is not None
        assert panel.btn_vivo.isCheckable()
        assert not panel.btn_vivo.isChecked()
        assert panel.estado_vivo.textFormat() == Qt.PlainText
        assert all(lbl.textFormat() == Qt.PlainText for lbl in panel.findChildren(QtLabel))
        assert any('Leer últimos 3' in lbl.text() for lbl in panel.findChildren(QtLabel))

        # Modo autónomo: toggle y demo flotante funcionan y sincronizan tema
        panel.btn_vivo.click()
        assert panel.btn_vivo.isChecked()
        assert 'Pausar' in panel.btn_vivo.text()

        panel.btn_demo_vivo.click()
        app.processEvents()
        assert v._controlador_vivo_demo is not None
        assert v._controlador_vivo_demo.barra.isVisible()
        assert len(v._controlador_vivo_demo.tarjetas) == 3

        assert v._controlador_vivo_demo.tema == 'claro'

        # Usar una tarjeta demo copia al portapapeles
        v._controlador_vivo_demo.tarjetas[0].usar()
        assert app.clipboard().text() != ''

        # Callbacks externos conectados en VentanaQt
        toggles = []
        demos = []
        clips = []
        v.al_toggle_vivo = toggles.append
        v.al_probar_vivo = lambda: demos.append(True)
        v.al_analizar_portapapeles = lambda: clips.append(True)

        panel.btn_vivo.click()
        panel.btn_demo_vivo.click()
        panel.btn_portapapeles_vivo.click()
        assert toggles == [False]
        assert demos == [True]
        assert clips == [True]

        v.close()
        assert v._controlador_vivo_demo is None


def test_publicar_limpia_operaciones_categorias_pendientes(app):
    import time
    from types import SimpleNamespace
    from unittest.mock import patch

    with RepositorioSQLite(':memory:') as repo:
        g = GestionFrases(repo)
        auth = Mock()
        auth.cliente.url = 'https://example.supabase.co'
        sesion = Sesion('admin@example.test', 'administrador', 'token')
        cat_id = g.crear_categoria('Ventas', auth, sesion)
        g.editar_categoria(cat_id, 'Comercial', '#123456', auth, sesion)
        assert len(g.operaciones_categorias()) == 1

        v = VentanaQt(g, demostracion=False, autenticacion=auth, sesion=sesion)
        servicio_falso = Mock()
        servicio_falso.recoger_categorias.return_value = []
        servicio_falso.preparar.return_value = SimpleNamespace(
            version=5, cantidad_frases=0, nuevas=0, modificadas=0, eliminadas=0
        )
        servicio_falso.publicar.return_value = SimpleNamespace(version=5)
        with patch('fraseya.aplicacion.publicacion_supabase.PublicacionSupabase', return_value=servicio_falso):
            v.publicar(False)
            limite = time.monotonic() + 3
            while v.panel_catalogo.ocupada and time.monotonic() < limite:
                app.processEvents()
                time.sleep(.01)
            v.panel_catalogo._confirmar()
            limite = time.monotonic() + 3
            while v.panel_catalogo.ocupada and time.monotonic() < limite:
                app.processEvents()
                time.sleep(.01)
        assert g.operaciones_categorias() == []
        v.close()


def test_panel_importar_y_completar_variables_dialogo(app, tmp_path):
    from unittest.mock import patch
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QLineEdit, QMessageBox
    from openpyxl import Workbook
    from fraseya.presentacion.qt_dialogos import completar_variables

    ruta_xlsx = tmp_path / 'frases.xlsx'
    wb = Workbook()
    ws = wb.active
    ws.append(['categoria', 'titulo', 'abreviatura', 'contenido'])
    ws.append(['General', 'Saludo Excel', '!excel', 'Hola {nombre}'])
    wb.save(ruta_xlsx)

    with RepositorioSQLite(':memory:') as repo:
        g = GestionFrases(repo)
        v = VentanaQt(g, demostracion=False, autenticacion=Mock(), sesion=Sesion('uno@example.test', 'usuario', 'token'))
        v.importar_excel()
        with patch('fraseya.presentacion.qt_paneles.QFileDialog.getOpenFileName', return_value=(str(ruta_xlsx), '')):
            v.panel_importar.examinar()
        assert v.panel_importar.ruta.text() == str(ruta_xlsx)
        v.panel_importar.ejecutar()
        assert any(f['abreviatura'] == '!excel' for f in g.listar())
        v.close()

    def responder_dialogo():
        from PySide6.QtWidgets import QDialogButtonBox
        dlgs = [w for w in app.topLevelWidgets() if isinstance(w, QDialog) and w.isVisible()]
        if not dlgs:
            QTimer.singleShot(20, responder_dialogo)
            return
        d = dlgs[-1]
        campos = d.findChildren(QLineEdit)
        caja = d.findChild(QDialogButtonBox)
        campos[0].setText('')
        caja.accepted.emit()
        for ed in campos:
            ed.setText('Camila')
        caja.accepted.emit()

    with patch.object(QMessageBox, 'warning') as warn_mock:
        QTimer.singleShot(30, responder_dialogo)
        resultado = completar_variables(None, 'Hola {nombre}', ['nombre'], {'nombre': ''}, flotante=True)
        assert resultado == {'nombre': 'Camila'}
        warn_mock.assert_called_once()


def test_expansion_buscador_ordena_favoritas_y_sin_tildes(app):
    from unittest.mock import patch
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QLineEdit, QListWidget
    from fraseya.presentacion.qt_expansion import ExpansionQt

    with RepositorioSQLite(':memory:') as repo:
        g = GestionFrases(repo)
        cat = g.categorias_propias()[0]['id']
        uno = g.crear('Información normal', '!info', 'Detalle normal', cat)
        dos = g.crear('Información prioritaria', '!prio', 'Detalle urgente', cat)
        g.alternar_favorita(dos)
        v = VentanaQt(g, demostracion=True)
        with patch('fraseya.presentacion.qt_expansion.TecladoGlobal'), \
             patch('fraseya.presentacion.qt_expansion.EscritorTexto'), \
             patch('fraseya.presentacion.qt_expansion.forzar_primer_plano'), \
             patch('fraseya.presentacion.qt_expansion.activar_ventana'):
            exp = ExpansionQt(v, repo)
            observado = {}

            def filtrar_y_cerrar():
                dlgs = [w for w in app.topLevelWidgets() if isinstance(w, QDialog) and w.isVisible()]
                if not dlgs:
                    QTimer.singleShot(20, filtrar_y_cerrar)
                    return
                d = dlgs[-1]
                d.findChild(QLineEdit).setText('informacion')
                app.processEvents()
                lista = d.findChild(QListWidget)
                observado['items'] = [lista.item(i).text() for i in range(lista.count())]
                d.reject()

            QTimer.singleShot(30, filtrar_y_cerrar)
            exp.buscador(12345)
            assert len(observado['items']) == 2
            assert observado['items'][0].startswith('[★] Información prioritaria')
            assert uno != dos
            exp.detener()
        v.close()
