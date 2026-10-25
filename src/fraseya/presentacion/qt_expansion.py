"""Teclado global y motor existente, con puente al hilo principal Qt."""
import queue
from threading import Event,Thread
from PySide6.QtCore import QTimer,Qt
from PySide6.QtWidgets import QApplication,QDialog,QVBoxLayout,QLineEdit,QListWidget,QListWidgetItem
from fraseya.aplicacion.configuracion import Configuracion
from fraseya.aplicacion.motor_expansion import MotorExpansion
from fraseya.infraestructura.escritor_texto import EscritorTexto
from fraseya.infraestructura.teclado_global import TecladoGlobal,ventana_activa,activar_ventana,forzar_primer_plano
from .qt_dialogos import completar_variables
from .qt_vista import ESTILO


class PuenteQt:
    def __init__(self,parent):
        self.cola=queue.Queue(); self.activo=True
        self.timer=QTimer(parent); self.timer.timeout.connect(self.atender); self.timer.start(25)

    def llamar(self,funcion):
        if not self.activo: raise RuntimeError('La ventana se cerró.')
        pedido={'funcion':funcion,'listo':Event(),'resultado':None,'error':None}
        self.cola.put(pedido); pedido['listo'].wait()
        if pedido['error']: raise pedido['error']
        return pedido['resultado']

    def publicar(self,funcion):
        if self.activo: self.cola.put({'funcion':funcion,'listo':Event(),'resultado':None,'error':None})

    def atender(self):
        while self.activo:
            try: p=self.cola.get_nowait()
            except queue.Empty: return
            try: p['resultado']=p['funcion']()
            except Exception as e: p['error']=e
            finally: p['listo'].set()

    def detener(self):
        self.activo=False; self.timer.stop()
        while True:
            try: p=self.cola.get_nowait()
            except queue.Empty: return
            p['error']=RuntimeError('La ventana se cerró.'); p['listo'].set()


class ExpansionQt:
    def __init__(self,ventana,repo):
        self.ventana=ventana; self.puente=PuenteQt(ventana); self.catalogo=[]; self.pausado=False
        ajustes=Configuracion(repo).leer(); self.escritor=EscritorTexto(ajustes.velocidad_ms)
        pedir=lambda nombres,iniciales:self.puente.llamar(lambda:completar_variables(ventana,' '.join('{'+n+'}' for n in nombres),nombres,iniciales))
        contexto=lambda nombres,iniciales,contenido:self.puente.llamar(lambda:completar_variables(ventana,contenido,nombres,iniciales))
        self.motor=MotorExpansion(self.escritor,pedir,ventana_activa,activar_ventana,pedir_con_contexto=contexto)
        self.recargar(); self.teclado=TecladoGlobal(self.motor,ajustes.tecla_confirmacion,ajustes.atajo_buscador)
        self.teclado.al_atajo=self.atajo
        self.timer=QTimer(ventana); self.timer.timeout.connect(self.actualizar_pausa); self.timer.start(30)
        # Nunca expandir teclas en los campos propios, contraseña incluida.
        QApplication.instance().focusWindowChanged.connect(self.actualizar_pausa)
        self.teclado.iniciar(); ventana.al_cambiar=self.recargar

    def actualizar_pausa(self,*_):
        self.teclado.pausado=self.pausado or QApplication.activeWindow() is not None

    def recargar(self):
        self.catalogo[:]=self.ventana.gestion.listar(); self.motor.actualizar_frases(self.catalogo)

    def aplicar(self,a):
        self.escritor.velocidad_ms=a.velocidad_ms; self.teclado.configurar(a.tecla_confirmacion,a.atajo_buscador)

    def atajo(self):
        origen=ventana_activa(); self.puente.publicar(lambda:self.buscador(origen))

    def buscador(self,origen):
        self.pausado=True; self.actualizar_pausa()
        d=QDialog(self.ventana); d.setStyleSheet(ESTILO); d.setWindowTitle('Buscar e insertar frase'); d.resize(600,420)
        layout=QVBoxLayout(d); buscar=QLineEdit(); buscar.setPlaceholderText('Buscar frase…'); layout.addWidget(buscar)
        lista=QListWidget(); layout.addWidget(lista); seleccion=[]
        def filtrar():
            lista.clear(); texto=buscar.text().casefold()
            for f in self.catalogo:
                if texto in (f['titulo']+' '+f['contenido']+' '+f['abreviatura']).casefold():
                    item=QListWidgetItem(f['titulo']+' · '+f['abreviatura']); item.setData(Qt.UserRole,f); lista.addItem(item)
            if lista.count(): lista.setCurrentRow(0)
        def aceptar(*_):
            if lista.currentItem(): seleccion.append(lista.currentItem().data(Qt.UserRole)); d.accept()
        lista.itemDoubleClicked.connect(aceptar); buscar.returnPressed.connect(aceptar); buscar.textChanged.connect(filtrar); filtrar()
        d.show(); forzar_primer_plano(int(d.winId())); buscar.setFocus(); d.exec()
        self.pausado=False; self.actualizar_pausa(); activar_ventana(origen)
        if seleccion: Thread(target=lambda:self.motor.insertar(seleccion[0]['contenido'],origen),daemon=True).start()

    def detener(self):
        self.timer.stop(); self.teclado.detener(); self.puente.detener()
