"""Arranque de producción Qt con Auth, sincronización y bandeja nativa."""
import queue
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon,QAction
from PySide6.QtWidgets import QApplication,QDialog,QSystemTrayIcon,QMenu,QMessageBox
from fraseya.infraestructura import RepositorioSQLite
from fraseya.infraestructura.supabase import cargar_cliente,AutenticacionSupabase,RepositorioSupabase
from fraseya.aplicacion.gestion_frases import GestionFrases
from fraseya.aplicacion.configuracion import Configuracion
from fraseya.aplicacion.servicio_sincronizacion import ServicioSincronizacion
from fraseya.aplicacion.estado_sincronizacion import resumen_estado
from .qt_vista import VentanaQt,ESTILO
from .qt_dialogos import AccesoQt,configurar_conexion,recurso


def abrir(ruta,con_teclado=True,configurar=False):
    app=QApplication.instance() or QApplication([]); app.setApplicationName('FraseYa'); app.setStyleSheet(ESTILO)
    app.setWindowIcon(QIcon(str(recurso('fraseya.ico')))); app.setQuitOnLastWindowClosed(False)
    archivo=Path(ruta).parent/'supabase.json'
    if not archivo.exists() or configurar:
        if not configurar_conexion(archivo): return
    auth=AutenticacionSupabase(cargar_cliente(archivo)); acceso=AccesoQt(auth)
    try:
        if acceso.exec()!=QDialog.Accepted or acceso.sesion is None: return
        sesion=acceso.sesion; auth.validar(sesion)
        with RepositorioSQLite(ruta) as repo:
            ventana=VentanaQt(GestionFrases(repo),autenticacion=auth,sesion=sesion)
            expansion=None; eventos=queue.Queue(); detenido=False
            servicio=ServicioSincronizacion(repo,crear_lector=lambda:RepositorioSupabase(auth.cliente),al_resultado=eventos.put)
            servicio.configurar(Configuracion(repo).leer().intervalo_sincronizacion_min)
            if con_teclado:
                try:
                    from .qt_expansion import ExpansionQt
                    expansion=ExpansionQt(ventana,repo)
                except (ImportError,OSError,RuntimeError) as e: ventana.estado.setText('Expansión de teclado no disponible: '+str(e))
            def configurar_ajustes(a):
                servicio.configurar(a.intervalo_sincronizacion_min)
                if expansion: expansion.aplicar(a)
            ventana.al_configurar=configurar_ajustes
            def sincronizar():
                if sesion.token=='offline': ventana.sincronizacion.setText('Modo sin conexión · copia local'); return
                ventana.sincronizacion.setText('Comprobando catálogo…'); servicio.solicitar()
            ventana.al_sincronizar=sincronizar
            tray=QSystemTrayIcon(QIcon(str(recurso('fraseya.ico'))),ventana); menu=QMenu(ventana)
            def mostrar(): ventana.showNormal(); ventana.raise_(); ventana.activateWindow()
            for texto,accion in [('Abrir FraseYa',mostrar),('Sincronizar',sincronizar),('Ocultar ventana',ventana.hide),('Salir',ventana.close)]:
                a=QAction(texto,menu); a.triggered.connect(accion); menu.addAction(a)
            tray.setContextMenu(menu); tray.activated.connect(lambda motivo:mostrar() if motivo==QSystemTrayIcon.DoubleClick else None)
            if QSystemTrayIcon.isSystemTrayAvailable(): tray.show()
            timer=QTimer(ventana)
            def atender():
                while True:
                    try: r=eventos.get_nowait()
                    except queue.Empty: break
                    estado,texto=resumen_estado(repo,r,sin_conexion=sesion.token=='offline'); ventana.sincronizacion.setText(texto); tray.setToolTip('FraseYa · '+texto)
                    if r.estado=='actualizada': ventana.categorias(); ventana.refrescar(); ventana.frases_cambiaron()
            timer.timeout.connect(atender); timer.start(100)
            _,texto=resumen_estado(repo,sin_conexion=sesion.token=='offline'); ventana.sincronizacion.setText(texto)
            def detener():
                nonlocal detenido
                if detenido: return
                detenido=True; timer.stop(); tray.hide(); servicio.detener()
                if expansion: expansion.detener()
                app.quit()
            ventana.al_salir=detener; ventana.show()
            if sesion.token!='offline': servicio.iniciar()
            try: app.exec()
            finally: detener()
    finally:
        if auth._sesion: auth.salir(auth._sesion)
        auth.cerrar()
