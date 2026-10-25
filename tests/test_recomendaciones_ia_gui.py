import time
from unittest.mock import Mock
import customtkinter as ctk
import pytest
from fraseya.aplicacion.gestion_frases import GestionFrases
from fraseya.infraestructura import RepositorioSQLite
from fraseya.presentacion.recomendaciones_ia import VentanaIA


@pytest.fixture(scope='module')
def raiz():
    ventana=ctk.CTk(); ventana.withdraw()
    yield ventana
    ventana.destroy()


def test_consulta_unica_y_frase_revisable_sin_modificar_base(raiz):
    with RepositorioSQLite(':memory:') as repo:
        g=GestionFrases(repo)
        ident=g.crear('Pedido','!pedido','Tu pedido {orden}',g.categorias_propias()[0]['id'])
        cliente=Mock(); cliente.solicitar.return_value={'sugerencias':[{'id':ident,'motivo':'Consulta de pedido.'}]}
        elegir, cerrar=Mock(), Mock()
        v=VentanaIA(raiz,cliente,g,elegir,al_cerrar=cerrar); v.withdraw()
        try:
            v.mensaje.insert('1.0','¿Dónde está mi pedido?')
            v.sugerir(); v.sugerir()
            limite=time.monotonic()+3
            while v.ocupada and time.monotonic()<limite:
                raiz.update(); time.sleep(0.01)
            assert not v.ocupada
            assert cliente.solicitar.call_count==1
            assert len(v.resultados.winfo_children())==1
            elegir.assert_not_called()
            assert repo.obtener_frase(ident)['contenido']=='Tu pedido {orden}'
            v.elegir(g.listar()[0])
            elegir.assert_called_once(); cerrar.assert_called_once()
        finally:
            if v.winfo_exists(): v.destroy()


def test_frase_eliminada_no_se_elige(raiz):
    with RepositorioSQLite(':memory:') as repo:
        g=GestionFrases(repo)
        ident=g.crear('Pedido','!pedido','Tu pedido',g.categorias_propias()[0]['id'])
        frase=g.listar()[0]
        elegido=Mock(); v=VentanaIA(raiz,Mock(),g,elegido); v.withdraw()
        g.eliminar(ident)
        v.elegir(frase)
        elegido.assert_not_called()
        assert 'cambió' in v.aviso.cget('text')
        v.destroy()


def test_sin_coincidencias_genera_y_guarda_una_sola_vez(raiz):
    with RepositorioSQLite(':memory:') as repo:
        g=GestionFrases(repo)
        g.crear('Base','!base','Texto base',g.categorias_propias()[0]['id'])
        cliente=Mock()
        cliente.solicitar.side_effect=[{'sugerencias':[]},
            {'titulo':'Ayuda','categoria':'General','contenido':'Hola {nombre}, ¿en qué puedo ayudarte?'}]
        elegir=Mock(); v=VentanaIA(raiz,cliente,g,elegir); v.withdraw()
        try:
            v.mensaje.insert('1.0','Necesito ayuda')
            v.sugerir(); v.sugerir()
            limite=time.monotonic()+3
            while v.ocupada and time.monotonic()<limite:
                raiz.update(); time.sleep(0.01)
            assert not v.ocupada
            assert cliente.solicitar.call_count==2
            nuevas=[f for f in g.listar() if f['titulo']=='Ayuda']
            assert len(nuevas)==1 and nuevas[0]['origen']=='propia'
            assert len(v.resultados.winfo_children())==1
            elegir.assert_not_called()
        finally:
            v.destroy()
