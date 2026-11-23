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

        v.abrir_usuarios()
        assert v.paginas.currentWidget() is v.panel_usuarios and v.nav_usuarios.isChecked() and sin_dialogos_visibles()

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
            assert v.paginas.currentWidget() is v.panel_catalogo and v.nav_retirar.isChecked()
            assert not v.panel_catalogo.panel_retiro.isHidden()
            limite=time.monotonic()+3
            while v.panel_catalogo.ocupada and time.monotonic()<limite: app.processEvents(); time.sleep(.01)
            assert v.panel_catalogo.selector_retiro.count()==1
        v.close()


def test_cambio_tema_barra_lateral_ajustes_y_persistencia(app, tmp_path):
    from PySide6.QtWidgets import QLabel as QtLabel
    from fraseya.aplicacion.configuracion import Configuracion
    from fraseya.presentacion.qt_dialogos import AjustesQt, DialogoRed
    from fraseya.presentacion.qt_temas import ESTILO, ESTILO_OSCURO

    ruta = tmp_path / 'tema_persistencia.db'
    with RepositorioSQLite(ruta) as repo:
        g = GestionFrases(repo)
        cat = g.categorias_propias()[0]['id']
        g.crear('Saludo', '!hola', 'Hola {nombre}', cat)
        auth = Mock()
        auth.cliente.solicitar.return_value = {'nombre': 'Demo', 'servicios': '', 'horarios': '', 'procedimientos': ''}
        sesion = Sesion('admin@example.test', 'administrador', 'token')

        v = VentanaQt(g, demostracion=False, autenticacion=auth, sesion=sesion)
        temas_notificados = []
        ajustes_notificados = []
        v.al_cambiar_tema = temas_notificados.append
        v.al_configurar = ajustes_notificados.append

        assert v.tema_actual == 'claro'
        assert v.btn_tema.objectName() == 'theme_toggle'
        assert v.btn_tema.text() == 'Tema oscuro'
        assert app.styleSheet() == ESTILO
        assert v.styleSheet() == ESTILO
        assert all(lbl.textFormat() == Qt.PlainText for lbl in v.findChildren(QtLabel))

        # Cambiar a oscuro desde botón rápido de la barra lateral
        v.btn_tema.click()
        assert v.tema_actual == 'oscuro'
        assert v.btn_tema.text() == 'Tema claro'
        assert app.styleSheet() == ESTILO_OSCURO
        assert v.styleSheet() == ESTILO_OSCURO
        assert temas_notificados[-1] == 'oscuro'
        assert ajustes_notificados[-1].tema == 'oscuro'
        assert Configuracion(repo).leer().tema == 'oscuro'

        # Los diálogos heredan la hoja de estilo oscura activa
        dlg = DialogoRed(v)
        assert dlg.styleSheet() == ESTILO_OSCURO
        dlg.close()
        dlg.deleteLater()

        dlg_aj = AjustesQt(v, Configuracion(repo), None)
        assert dlg_aj.styleSheet() == ESTILO_OSCURO
        assert dlg_aj.panel.tema.currentData() == 'oscuro'
        dlg_aj.close()
        dlg_aj.deleteLater()

        # Restablecer y guardar desde PanelAjustes vuelve a 'claro'
        v.ajustes()
        assert v.panel_ajustes.tema.currentData() == 'oscuro'
        v.panel_ajustes.restablecer()
        assert v.panel_ajustes.tema.currentData() == 'claro'
        assert v.panel_ajustes.guardar()
        assert v.tema_actual == 'claro'
        assert app.styleSheet() == ESTILO
        assert Configuracion(repo).leer().tema == 'claro'

        # Cambiar a oscuro desde PanelAjustes y guardar
        idx_oscuro = v.panel_ajustes.tema.findData('oscuro')
        assert idx_oscuro >= 0
        v.panel_ajustes.tema.setCurrentIndex(idx_oscuro)
        assert v.panel_ajustes.guardar()
        assert v.tema_actual == 'oscuro'
        assert Configuracion(repo).leer().tema == 'oscuro'

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

    # Reabrir desde el mismo SQLite conserva el tema oscuro
    with RepositorioSQLite(ruta) as repo2:
        g2 = GestionFrases(repo2)
        v2 = VentanaQt(g2, demostracion=True)
        assert v2.tema_actual == 'oscuro'
        assert v2.btn_tema.text() == 'Tema claro'
        assert v2.styleSheet() == ESTILO_OSCURO
        assert all(lbl.textFormat() == Qt.PlainText for lbl in v2.findChildren(QtLabel))
        v2.close()


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

        v.alternar_tema()
        assert v._controlador_vivo_demo.tema == 'oscuro'

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
