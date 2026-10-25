import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication
from fraseya.aplicacion.gestion_frases import GestionFrases
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
