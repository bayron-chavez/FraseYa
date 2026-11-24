"""Teclado global y motor existente, con puente al hilo principal Qt."""
import queue
import time
from threading import Event,Thread
from PySide6.QtCore import QTimer,Qt
from PySide6.QtWidgets import QApplication,QDialog,QVBoxLayout,QLineEdit,QListWidget,QListWidgetItem
from fraseya.aplicacion.configuracion import Configuracion
from fraseya.aplicacion.motor_expansion import MotorExpansion
from fraseya.infraestructura.escritor_texto import EscritorTexto
from fraseya.infraestructura.teclado_global import TecladoGlobal,ventana_activa,activar_ventana,forzar_primer_plano
from .qt_dialogos import completar_variables
from .qt_vista import ESTILO


def _estilo_actual():
    app = QApplication.instance()
    if app is not None:
        qss = app.styleSheet()
        if qss:
            return qss
    return ESTILO


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
        pedir=lambda nombres,iniciales:self.puente.llamar(lambda:completar_variables(None,' '.join('{'+n+'}' for n in nombres),nombres,iniciales,flotante=True))
        contexto=lambda nombres,iniciales,contenido:self.puente.llamar(lambda:completar_variables(None,contenido,nombres,iniciales,flotante=True))
        self.motor=MotorExpansion(self.escritor,pedir,ventana_activa,activar_ventana,pedir_con_contexto=contexto)
        self.recargar(); self.teclado=TecladoGlobal(self.motor,ajustes.tecla_confirmacion,ajustes.atajo_buscador)
        self.teclado.al_atajo=self.atajo
        self.timer=QTimer(ventana); self.timer.timeout.connect(self.actualizar_pausa); self.timer.start(30)
        # Nunca expandir teclas en los campos propios, contraseña incluida.
        QApplication.instance().focusWindowChanged.connect(self.actualizar_pausa)
        self.teclado.iniciar()
        anterior_cambiar = ventana.al_cambiar

        def _al_cambiar_encadenado():
            self.recargar()
            if anterior_cambiar:
                anterior_cambiar()

        ventana.al_cambiar = _al_cambiar_encadenado

    def actualizar_pausa(self,*_):
        self.teclado.pausado=self.pausado or QApplication.activeWindow() is not None

    def recargar(self):
        self.catalogo[:]=self.ventana.gestion.listar(); self.motor.actualizar_frases(self.catalogo)

    def aplicar(self,a):
        self.escritor.velocidad_ms=a.velocidad_ms; self.teclado.configurar(a.tecla_confirmacion,a.atajo_buscador)

    def desarmar_pegado_al_clic(self):
        if hasattr(self.teclado, 'desarmar_pegado_al_clic'):
            self.teclado.desarmar_pegado_al_clic()

    def armar_pegado_al_clic(self, texto, hwnd_destino=None, al_pegar=None, timeout_seg=10.0):
        """Espera un único clic en WhatsApp y pega la frase al soltar el botón."""
        if not isinstance(texto, str) or not texto or not hasattr(self.teclado, 'armar_pegado_al_clic'):
            return False

        def _al_clic():
            time.sleep(0.08)
            try:
                from fraseya.infraestructura.lector_chat import LectorChat
                activa = ventana_activa()
                es_destino = bool(hwnd_destino and activa == hwnd_destino)
                if not es_destino:
                    es_destino = LectorChat().ventana_whatsapp_activa() is not None
                if not es_destino:
                    if callable(al_pegar):
                        al_pegar(False, 'fuera_whatsapp')
                    return
                self.escritor.escribir(texto)
                if callable(al_pegar):
                    al_pegar(True, None)
            except Exception as err:
                if callable(al_pegar):
                    al_pegar(False, str(err) or 'error_pegado')

        self.teclado.armar_pegado_al_clic(_al_clic, timeout_seg=timeout_seg)
        return True

    def insertar_texto_en_ventana(self, texto, hwnd_destino=None, enfocar_destino=None, al_terminar=None):
        """Inserta texto en la ventana indicada usando MotorExpansion (nunca pulsa Enter).

        Si `enfocar_destino` se entrega (callback opcional), tras activar la ventana de
        destino espera brevemente (~120 ms) y llama a `enfocar_destino()` para enfocar el
        cuadro de escritura antes de insertar.
        """
        if not isinstance(texto, str) or not texto:
            return False
        destino = hwnd_destino if hwnd_destino is not None else ventana_activa()
        kwargs = {}
        if al_terminar is not None:
            kwargs['al_terminar'] = al_terminar
        if enfocar_destino is None:
            try:
                return bool(self.motor.insertar(texto, destino, **kwargs))
            except TypeError:
                return bool(self.motor.insertar(texto, destino))

        def _enfocar_con_pausa():
            if destino:
                try:
                    activar_ventana(destino)
                except Exception:
                    pass
                time.sleep(0.12)
            try:
                ok_foco = bool(enfocar_destino())
                time.sleep(0.40)
                return ok_foco
            except Exception:
                return False

        try:
            return bool(self.motor.insertar(
                texto,
                destino,
                antes_de_escribir=_enfocar_con_pausa,
                **kwargs,
            ))
        except TypeError:
            try:
                return bool(self.motor.insertar(texto, destino, antes_de_escribir=_enfocar_con_pausa))
            except TypeError:
                _enfocar_con_pausa()
                return bool(self.motor.insertar(texto, destino))

    def atajo(self):
        origen=ventana_activa(); self.puente.publicar(lambda:self.buscador(origen))

    def buscador(self,origen):
        self.pausado=True; self.actualizar_pausa()
        d=QDialog(None); d.setWindowFlags(d.windowFlags() | Qt.WindowStaysOnTopHint); d.setStyleSheet(_estilo_actual()); d.setWindowTitle('Buscar e insertar frase'); d.resize(600,420)
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
        self.pausado=False; self.actualizar_pausa()
        if seleccion:
            Thread(target=lambda:(activar_ventana(origen),time.sleep(0.18),self.motor.insertar(seleccion[0]['contenido'],origen)),daemon=True).start()
        else:
            activar_ventana(origen)

    def detener(self):
        self.timer.stop(); self.teclado.detener(); self.puente.detener()
