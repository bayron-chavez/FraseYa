"""Diálogos Qt. Red en trabajadores; widgets y SQLite solo en el hilo de interfaz."""
import queue
from threading import Thread
from pathlib import Path
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QLineEdit,
    QTextEdit,QPushButton,QComboBox,QSpinBox,QDialogButtonBox,QMessageBox,QScrollArea,QWidget)
from .qt_vista import ESTILO, boton, EtiquetaSegura as QLabel


class Trabajos:
    def __init__(self,parent):
        self.cola=queue.Queue(); self.activo=True; self.pendientes=0
        self.timer=QTimer(parent); self.timer.timeout.connect(self.atender); self.timer.start(50)
        parent.destroyed.connect(self.detener)

    def ejecutar(self,operacion,terminado):
        if not self.activo: return
        self.pendientes+=1
        def trabajar():
            try: resultado,error=operacion(),None
            except Exception as e: resultado,error=None,e
            self.cola.put((terminado,resultado,error))
        Thread(target=trabajar,daemon=True).start()

    def atender(self):
        while self.activo:
            try: callback,resultado,error=self.cola.get_nowait()
            except queue.Empty: return
            self.pendientes-=1; callback(resultado,error)

    def detener(self,*_): self.activo=False; self.timer.stop()


class DialogoRed(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setStyleSheet(ESTILO); self.trabajos=Trabajos(self); self.ocupada=False
        self.setWindowIcon(QIcon(str(recurso('fraseya.ico'))))

    def reject(self):
        if self.ocupada: return
        self.trabajos.detener(); super().reject()

    def closeEvent(self,event):
        if self.ocupada: event.ignore()
        else: self.trabajos.detener(); event.accept()


def recurso(nombre):
    import sys
    return Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[3]))/'assets'/nombre


class AccesoQt(DialogoRed):
    def __init__(self,autenticacion):
        super().__init__(); self.auth=autenticacion; self.sesion=None
        self.setWindowTitle('FraseYa · Iniciar sesión'); self.resize(430,460)
        l=QVBoxLayout(self); l.setContentsMargins(40,25,40,25); l.setSpacing(14)
        logo=QLabel(); logo.setAlignment(Qt.AlignCenter); logo.setPixmap(QPixmap(str(recurso('logo.png'))).scaled(78,78,Qt.KeepAspectRatio,Qt.SmoothTransformation)); l.addWidget(logo)
        titulo=QLabel('Bienvenido a FraseYa'); titulo.setObjectName('heading'); l.addWidget(titulo)
        self.usuario=QLineEdit(); self.usuario.setPlaceholderText('Correo electrónico'); l.addWidget(self.usuario)
        self.clave=QLineEdit(); self.clave.setPlaceholderText('Contraseña'); self.clave.setEchoMode(QLineEdit.Password); l.addWidget(self.clave)
        self.aviso=QLabel(''); self.aviso.setWordWrap(True); l.addWidget(self.aviso)
        self.entrar=boton('Iniciar sesión',self.iniciar,True); l.addWidget(self.entrar)
        self.offline=boton('Trabajar sin conexión',self.sin_conexion); l.addWidget(self.offline)
        self.clave.returnPressed.connect(self.iniciar)

    def iniciar(self):
        if self.ocupada: return
        correo,clave=self.usuario.text(),self.clave.text(); self.clave.clear(); self.ocupada=True
        self.entrar.setEnabled(False); self.offline.setEnabled(False); self.aviso.setText('Conectando…')
        self.trabajos.ejecutar(lambda:self.auth.iniciar_sesion(correo,clave),self.terminar)

    def terminar(self,sesion,error):
        self.ocupada=False; self.entrar.setEnabled(True); self.offline.setEnabled(True)
        if error: self.aviso.setText(str(error) if isinstance(error,(ValueError,PermissionError)) else 'No se pudo iniciar sesión.'); return
        self.sesion=sesion; self.trabajos.detener(); self.accept()

    def sin_conexion(self):
        if self.ocupada: return
        self.sesion=self.auth.sin_conexion(); self.trabajos.detener(); self.accept()


def configurar_conexion(ruta,parent=None):
    from fraseya.infraestructura.supabase import validar_conexion
    import json
    d=QDialog(parent); d.setStyleSheet(ESTILO); d.setWindowTitle('Conexión de FraseYa'); d.resize(570,280)
    l=QVBoxLayout(d); l.addWidget(QLabel('URL de Supabase y clave pública publishable o anon.'))
    url,clave=QLineEdit(),QLineEdit(); url.setPlaceholderText('https://proyecto.supabase.co'); clave.setPlaceholderText('Clave pública'); l.addWidget(url); l.addWidget(clave)
    aviso=QLabel(); aviso.setWordWrap(True); l.addWidget(aviso)
    botones=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); l.addWidget(botones)
    def guardar():
        try:
            direccion,publica=validar_conexion(url.text(),clave.text()); Path(ruta).parent.mkdir(parents=True,exist_ok=True)
            Path(ruta).write_text(json.dumps({'url':direccion,'clave_publica':publica}),encoding='utf8')
        except (ValueError,OSError) as e: aviso.setText(str(e)); return
        d.accept()
    botones.accepted.connect(guardar); botones.rejected.connect(d.reject)
    return d.exec()==QDialog.Accepted


def completar_variables(parent,contenido,nombres=None,iniciales=None):
    from fraseya.aplicacion.resolver_variables import detectar,sustituir,valores_iniciales,faltantes
    nombres=nombres or detectar(contenido); iniciales=iniciales or valores_iniciales(nombres)
    d=QDialog(parent); d.setWindowTitle('Completar campos'); d.setStyleSheet(ESTILO); d.resize(570,450)
    l=QVBoxLayout(d); l.addWidget(QLabel('Vista previa de la respuesta'))
    preview=QTextEdit(); preview.setReadOnly(True); l.addWidget(preview)
    scroll=QScrollArea(); scroll.setWidgetResizable(True); cuerpo=QWidget(); form=QFormLayout(cuerpo); entradas={}
    def actualizar():
        preview.setPlainText(sustituir(contenido,{n:e.text() for n,e in entradas.items()}))
        foco=d.focusWidget()
        for n,e in entradas.items():
            if e is foco:
                cursor=preview.document().find(e.text() or '{'+n+'}')
                if not cursor.isNull(): preview.setTextCursor(cursor)
                break
    for n in nombres:
        entrada=QLineEdit(iniciales.get(n,'')); entradas[n]=entrada; entrada.textChanged.connect(actualizar)
        form.addRow(n.replace('_',' ').capitalize(),entrada)
    scroll.setWidget(cuerpo); l.addWidget(scroll)
    botones=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel); l.addWidget(botones)
    def aceptar():
        if faltantes(nombres,{n:e.text() for n,e in entradas.items()}): QMessageBox.warning(d,'Campos pendientes','Complete todos los campos.'); return
        d.accept()
    botones.accepted.connect(aceptar); botones.rejected.connect(d.reject); actualizar()
    if d.exec()!=QDialog.Accepted: return None
    return {n:e.text().strip() for n,e in entradas.items()}


class EmpresaQt(DialogoRed):
    def __init__(self,parent,cliente):
        super().__init__(parent)
        from fraseya.aplicacion.empresa_ia import EmpresaIA,CAMPOS
        self.servicio=EmpresaIA(cliente); self.setWindowTitle('Perfil de empresa'); self.resize(630,650)
        l=QVBoxLayout(self); aviso=QLabel('Contexto compartido con Gemini. No incluya claves ni datos personales.'); aviso.setWordWrap(True); l.addWidget(aviso)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); contenido=QWidget(); form=QVBoxLayout(contenido); self.campos={}
        for k,maximo in CAMPOS.items():
            form.addWidget(QLabel(k.capitalize()+f' · máximo {maximo} caracteres')); e=QTextEdit(); e.setAcceptRichText(False); e.setMaximumHeight(100); self.campos[k]=e; form.addWidget(e)
        scroll.setWidget(contenido); l.addWidget(scroll)
        self.aviso=QLabel(); self.aviso.setWordWrap(True); l.addWidget(self.aviso); self.boton=boton('Guardar perfil',self.guardar,True); self.boton.setEnabled(False); l.addWidget(self.boton)
        self.ocupada=True; self.trabajos.ejecutar(self.servicio.leer,self.cargar)

    def cargar(self,perfil,error):
        self.ocupada=False
        if error: self.aviso.setText('No se pudo cargar el perfil. Reabra la ventana para reintentar.'); return
        for k,e in self.campos.items(): e.setPlainText(perfil[k])
        self.boton.setEnabled(True)

    def guardar(self):
        if self.ocupada: return
        perfil={k:e.toPlainText() for k,e in self.campos.items()}; self.ocupada=True; self.boton.setEnabled(False)
        self.trabajos.ejecutar(lambda:self.servicio.guardar(perfil),self.guardado)

    def guardado(self,_,error):
        self.ocupada=False; self.boton.setEnabled(True); self.aviso.setText(str(error) if error else 'Perfil guardado.')


class IAQt(DialogoRed):
    def __init__(self,parent,cliente,gestion,administrador=False):
        super().__init__(parent)
        from fraseya.aplicacion.recomendaciones_ia import RecomendadorIA
        self.gestion=gestion; self.servicio=RecomendadorIA(cliente); self.parent_window=parent
        self.setWindowTitle('FraseYa · Asistente IA'); self.resize(720,740)
        l=QVBoxLayout(self); titulo=QLabel('Una respuesta que parte del contexto'); titulo.setObjectName('heading'); l.addWidget(titulo)
        info=QLabel('Al consultar se envían a Gemini el mensaje, hasta 40 frases y el perfil de empresa.\nSi no hay coincidencias, se genera y guarda una frase propia. Revise la propuesta.'); info.setWordWrap(True); l.addWidget(info)
        self.mensaje=QTextEdit(); self.mensaje.setAcceptRichText(False); self.mensaje.setPlaceholderText('Cliente: …\nAgente: …'); self.mensaje.setMaximumHeight(150); l.addWidget(self.mensaje)
        fila=QHBoxLayout(); fila.addWidget(boton('Pegar mensaje',self.pegar))
        if administrador: fila.addWidget(boton('Perfil de empresa',lambda:EmpresaQt(self,cliente).exec()))
        self.consultar=boton('Preparar respuesta',self.sugerir,True); fila.addWidget(self.consultar); l.addLayout(fila)
        self.aviso=QLabel(); self.aviso.setWordWrap(True); l.addWidget(self.aviso)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); cuerpo=QWidget(); self.resultados=QVBoxLayout(cuerpo); self.resultados.setAlignment(Qt.AlignTop); scroll.setWidget(cuerpo); l.addWidget(scroll)

    def pegar(self):
        texto=QApplication.clipboard().text()
        if len(texto)>4000: self.aviso.setText('El mensaje supera 4.000 caracteres.'); return
        self.mensaje.setPlainText(texto)

    def sugerir(self):
        if self.ocupada: return
        from fraseya.aplicacion.recomendaciones_ia import preparar
        texto=self.mensaje.toPlainText(); frases=self.gestion.listar()
        try: preparar(texto,frases)
        except ValueError as e: self.aviso.setText(str(e)); return
        self.ocupada=True; self.consultar.setEnabled(False); self.aviso.setText('Preparando propuesta…')
        while self.resultados.count():
            w=self.resultados.takeAt(0).widget()
            if w: w.deleteLater()
        def consultar():
            sugerencias=self.servicio.sugerir(texto,frases)
            return (sugerencias,None) if sugerencias else ([],self.servicio.generar(texto,frases))
        self.trabajos.ejecutar(consultar,self.terminar)

    def terminar(self,resultado,error):
        from fraseya.aplicacion.recomendaciones_ia import guardar_generada,Sugerencia
        self.ocupada=False; self.consultar.setEnabled(True)
        if error: self.aviso.setText(str(error) if isinstance(error,(ValueError,PermissionError)) else 'No se pudo consultar la IA.'); return
        sugerencias,generada=resultado
        try:
            if generada:
                f=guardar_generada(self.gestion,generada); sugerencias=[Sugerencia(f,'Generada y guardada como propia. Revise contenido y datos personales.')]; self.parent_window.refrescar(); self.parent_window.frases_cambiaron()
        except ValueError as e: self.aviso.setText(str(e)); return
        self.aviso.setText('Revise la respuesta antes de usarla.')
        for s in sugerencias:
            titulo=QLabel(s.frase['titulo']); titulo.setObjectName('section'); self.resultados.addWidget(titulo)
            motivo=QLabel(s.motivo); motivo.setWordWrap(True); self.resultados.addWidget(motivo)
            vista=QTextEdit(); vista.setReadOnly(True); vista.setPlainText(s.frase['contenido']); vista.setMaximumHeight(125); self.resultados.addWidget(vista)
            self.resultados.addWidget(boton('Elegir esta frase',lambda checked=False,f=s.frase:self.elegir(f),True))

    def elegir(self,frase):
        try:
            actual=self.gestion.repo.obtener_frase(frase['id'])
            if any(actual[c]!=frase[c] for c in ('origen','abreviatura','contenido')): raise ValueError()
        except (ValueError,KeyError,LookupError): self.aviso.setText('La frase cambió. Solicite nuevas recomendaciones.'); return
        self.parent_window.refrescar(); self.parent_window.mostrar_id(actual['id']); self.accept()


class AjustesQt(QDialog):
    def __init__(self,parent,configuracion,al_guardar):
        super().__init__(parent); self.setStyleSheet(ESTILO); self.setWindowTitle('Configuración'); self.resize(560,350)
        from fraseya.infraestructura.teclado_global import TECLAS_CONFIRMACION
        ajustes=configuracion.leer(); l=QVBoxLayout(self); form=QFormLayout(); l.addLayout(form)
        tecla=QComboBox(); tecla.addItems(list(TECLAS_CONFIRMACION)); tecla.setCurrentText(ajustes.tecla_confirmacion); form.addRow('Tecla de expansión',tecla)
        atajo=QLineEdit(ajustes.atajo_buscador); form.addRow('Buscador rápido',atajo)
        velocidad=QSpinBox(); velocidad.setRange(0,1000); velocidad.setValue(ajustes.velocidad_ms); form.addRow('Velocidad de escritura (ms)',velocidad)
        intervalo=QSpinBox(); intervalo.setRange(1,1440); intervalo.setValue(ajustes.intervalo_sincronizacion_min); form.addRow('Sincronización (minutos)',intervalo)
        aviso=QLabel('Atajo recomendado: ctrl+alt+espacio.'); aviso.setWordWrap(True); l.addWidget(aviso)
        def guardar():
            try:
                cambios=configuracion.guardar({'tecla_confirmacion':tecla.currentText(),'atajo_buscador':atajo.text(),'velocidad_ms':velocidad.value(),'intervalo_sincronizacion_min':intervalo.value()}); al_guardar(cambios)
            except ValueError as e: aviso.setText(str(e)); return
            self.accept()
        l.addWidget(boton('Guardar ajustes',guardar,True))


from PySide6.QtWidgets import QApplication
