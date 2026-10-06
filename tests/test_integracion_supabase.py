import json
import time
import threading
import tkinter as tk
import pytest
from fraseya.aplicacion.formato_catalogo import serializar
from fraseya.aplicacion.sesion import Sesion
from fraseya.aplicacion.gestion_frases import GestionFrases
from fraseya.infraestructura import RepositorioSQLite
from fraseya.infraestructura.supabase import ClienteSupabase, AutenticacionSupabase
from fraseya.presentacion import ventana_principal as vp


def autenticacion(estado):
    def transporte(metodo, ruta, cuerpo, headers):
        if 'fraseya_perfil' in ruta:
            return [{'id':'uuid','correo':'admin@example.test','rol':'administrador'}]
        if 'fraseya_publicar' in ruta:
            datos=json.loads(cuerpo)
            estado[:] = [{'contenido':datos['p_contenido'],'metadata':datos['p_metadata']}]
            return datos['p_metadata']
        if 'fraseya_catalogo' in ruta:
            return estado
        return None
    cliente=ClienteSupabase('https://ejemplo.supabase.co','sb_publishable_prueba',transporte)
    cliente._guardar_tokens({'access_token':'a','refresh_token':'r','expires_in':3600})
    auth=AutenticacionSupabase(cliente)
    auth._sesion=Sesion('admin@example.test','administrador','sesion-de-prueba')
    return auth


def test_sincronizacion_entrega_cambios_en_hilo_tk(tmp_path,monkeypatch):
    datos,meta=serializar([{'nombre':'Equipo','color':'#123456','frases':[
        {'titulo':'Compartida','abreviatura':'equipo','contenido':'Hola equipo'}]}],
        1,'admin@example.test','2026-10-05T12:00:00Z')
    auth=autenticacion([{'contenido':datos.decode(),'metadata':json.loads(meta)}])
    llamadas=[]
    principal=threading.get_ident()
    def ciclo(v):
        v.withdraw()
        v.al_cambiar=lambda:llamadas.append(threading.get_ident())
        v.al_sincronizar()
        limite=time.monotonic()+4
        try:
            while not llamadas and time.monotonic()<limite:
                v.update(); time.sleep(0.01)
            assert llamadas==[principal]
            assert v.gestion.repo.listar_frases('compartida')[0]['abreviatura']=='equipo'
        finally:
            v.tk.call(v.protocol('WM_DELETE_WINDOW'))
    monkeypatch.setattr(vp.VentanaPrincipal,'mainloop',ciclo)
    vp.abrir(tmp_path/'local.db',con_teclado=False,autenticacion=auth,sesion=auth._sesion)


def test_cancelar_publicacion_no_escribe_y_confirmar_si(monkeypatch):
    estado=[]
    auth=autenticacion(estado)
    with RepositorioSQLite(':memory:') as repo:
        gestion=GestionFrases(repo)
        for intento in range(5):
            try:
                v=vp.VentanaPrincipal(gestion,autenticacion=auth,sesion=auth._sesion)
                break
            except tk.TclError as error:
                if 'usable tk.tcl' not in str(error):
                    raise
                time.sleep(0.1)
        else:
            pytest.skip('El runtime Tk del entorno no permite crear otro intérprete; ejecutar esta prueba por separado.')
        v.withdraw()
        try:
            cat=gestion.categorias_propias()[0]['id']
            repo.crear_frase(cat,'Saludo','hola','Hola equipo')
            def esperar():
                limite=time.monotonic()+4
                while v._publicando and time.monotonic()<limite:
                    v.update(); time.sleep(0.01)
                assert not v._publicando
            monkeypatch.setattr(vp.messagebox,'askyesno',lambda *a,**k:False)
            v.publicar_catalogo(); esperar()
            assert estado==[]
            monkeypatch.setattr(vp.messagebox,'askyesno',lambda *a,**k:True)
            v.publicar_catalogo(); esperar()
            assert estado[0]['metadata']['cantidad_frases']==1
            assert 'Publicado: versión 1' in v.estado_publicacion.cget('text')
        finally:
            v.destroy()
