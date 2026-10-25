"""Primera etapa Qt: biblioteca y editor conectados a los casos de uso existentes."""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QKeySequence, QShortcut, QFontDatabase, QPixmap, QColor
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QComboBox, QListWidget, QListWidgetItem,
    QFrame, QSplitter, QMessageBox, QDialog, QFormLayout, QDialogButtonBox, QScrollArea, QLayout)
from fraseya.aplicacion.resolver_variables import detectar, sustituir, valores_iniciales, faltantes

ESTILO = '''
QWidget {font-family: 'Segoe UI'; font-size:13px; color:#26364c; background:#f5f7fb;}
QFrame#sidebar, QFrame#panel {background:white; border:1px solid #e5eaf1; border-radius:12px;}
QFrame#sidebar {border-radius:0; border-left:0; border-top:0; border-bottom:0;}
QLabel {background:transparent;} QLabel#brand {font-size:24px;font-weight:700;color:#246bcc;}
QLabel#heading {font-size:28px;font-weight:600;} QLabel#muted {color:#78889d;font-size:12px;}
QLabel#section {font-weight:600;font-size:14px;}
QPushButton {background:white; border:1px solid #e2e8f1; border-radius:7px;padding:10px 15px;}
QPushButton:hover {background:#eff5fe;} QPushButton:disabled {color:#aab5c4;background:#f4f6fa;}
QPushButton#primary {background:#2875e8;color:white;border:0;font-weight:600;}
QPushButton#primary:hover {background:#2268ce;}
QPushButton#nav {text-align:left;border:0;background:transparent;padding:13px 18px;color:#6c7f97;}
QPushButton#nav:checked {background:#edf4ff;color:#246bcc;font-weight:600;}
QLineEdit,QTextEdit,QComboBox {background:white;border:1px solid #dfe6f0;border-radius:7px;padding:10px;}
QLineEdit:focus,QTextEdit:focus {border:1px solid #2875e8;}
QListWidget {background:white;border:0;outline:0;} QListWidget::item {padding:18px;border-bottom:1px solid #eef1f6;}
QListWidget::item:selected {background:#edf4ff;color:#26364c;border-left:3px solid #2875e8;}
QListWidget::item:hover {background:#f7faff;}
QTextEdit#preview {background:#f8fafc;color:#718299;border:1px solid #edf1f6;}
QSplitter::handle {background:transparent;width:20px;}
QScrollBar:vertical {background:#f5f7fb;width:10px;margin:0;}
QScrollBar::handle:vertical {background:#cbd5e1;border-radius:5px;min-height:35px;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}
QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical {background:transparent;}
'''


def boton(texto, accion, principal=False):
    b=QPushButton(texto)
    if principal: b.setObjectName('primary')
    b.clicked.connect(accion)
    return b


class EtiquetaSegura(QLabel):
    """Los textos de usuarios y del modelo se muestran literalmente, sin HTML."""
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.setTextFormat(Qt.PlainText)


QLabel=EtiquetaSegura


class VentanaQt(QMainWindow):
    def __init__(self, gestion, demostracion=False, autenticacion=None, sesion=None):
        super().__init__()
        fuente=Path('C:/Windows/Fonts/segoeui.ttf')
        if fuente.exists(): QFontDatabase.addApplicationFont(str(fuente))
        self.gestion=gestion; self.demostracion=demostracion; self.seleccion=None
        self.autenticacion,self.sesion=autenticacion,sesion
        self.al_cambiar=None; self.al_configurar=None; self.al_sincronizar=None; self.al_salir=None
        self._publicando=False; self._cerrando=False; self._ia=None
        self.favoritas=False; self.cargando=False
        self.setWindowTitle('FraseYa · Interfaz Qt' + (' · Demostración' if demostracion else ''))
        self.resize(1200,820); self.setMinimumSize(1060,720)
        import sys
        icono=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[3]))/'assets/fraseya.ico'
        self.setWindowIcon(QIcon(str(icono))); self.setStyleSheet(ESTILO)
        central=QWidget(); self.setCentralWidget(central)
        base=QHBoxLayout(central); base.setContentsMargins(0,0,0,0); base.setSpacing(0)
        lateral=QFrame(); lateral.setObjectName('sidebar'); lateral.setFixedWidth(210)
        nav=QVBoxLayout(lateral); nav.setContentsMargins(18,28,18,22); nav.setSpacing(8)
        marca=QLabel('FraseYa'); marca.setObjectName('brand'); nav.addWidget(marca)
        lema=QLabel('Las palabras, a su tiempo.'); lema.setObjectName('muted'); nav.addWidget(lema); nav.addSpacing(28)
        self.nav_frases=boton('Mis frases',lambda:self.cambiar_vista(False))
        self.nav_favoritas=boton('Favoritas',lambda:self.cambiar_vista(True))
        for b in (self.nav_frases,self.nav_favoritas): b.setObjectName('nav'); b.setCheckable(True); nav.addWidget(b)
        if not demostracion:
            self.nav_ia=boton('Asistente IA',self.abrir_ia); self.nav_ia.setObjectName('nav'); nav.addWidget(self.nav_ia)
            self.nav_ia.setEnabled(bool(sesion and sesion.token!='offline'))
            for texto,accion in [('Importar Excel',self.importar_excel),('Configuración',self.ajustes),('Sincronizar ahora',self.sincronizar)]:
                b=boton(texto,accion); b.setObjectName('nav'); nav.addWidget(b)
            self.sincronizacion=QLabel('Catálogo central · Supabase'); self.sincronizacion.setWordWrap(True); self.sincronizacion.setObjectName('muted'); nav.addWidget(self.sincronizacion)
            if sesion and sesion.rol=='administrador' and sesion.token!='offline':
                for texto,accion in [('Publicar catálogo',self.publicar),('Retirar del catálogo',lambda:self.publicar(True)),('Gestionar categorías',self.categorias_admin)]: nav.addWidget(boton(texto,accion))
            if sesion and sesion.rol=='administrador' and sesion.token!='offline':
                nav.addWidget(boton('Administrar usuarios',lambda:QMessageBox.information(self,'Usuarios','Las cuentas se administran en Supabase → Authentication → Users.\nRoles y habilitación: fraseya_perfiles.')))
        nav.addStretch()
        nota=QLabel('Demostración · datos temporales' if demostracion else ((sesion.usuario+'\n'+sesion.rol) if sesion else 'FraseYa')); nota.setWordWrap(True); nota.setObjectName('muted'); nav.addWidget(nota)
        if not demostracion: nav.addWidget(boton('Cerrar sesión',self.cerrar_sesion))
        desplazamiento=QScrollArea(); desplazamiento.setWidgetResizable(True); desplazamiento.setFrameShape(QFrame.NoFrame)
        desplazamiento.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); desplazamiento.setFixedWidth(212)
        desplazamiento.setWidget(lateral); base.addWidget(desplazamiento)
        area=QWidget(); cuerpo=QVBoxLayout(area); cuerpo.setContentsMargins(32,28,32,20); cuerpo.setSpacing(18)
        cabecera=QHBoxLayout(); titulos=QVBoxLayout(); self.encabezado=QLabel('Mis frases'); self.encabezado.setObjectName('heading')
        titulos.addWidget(self.encabezado); subtitulo=QLabel('Encuentra las palabras correctas, sin empezar de cero.'); subtitulo.setObjectName('muted'); titulos.addWidget(subtitulo)
        cabecera.addLayout(titulos); cabecera.addStretch(); cabecera.addWidget(boton('+  Nueva frase',self.nueva,True)); cuerpo.addLayout(cabecera)
        herramientas=QHBoxLayout(); self.busqueda=QLineEdit(); self.busqueda.setPlaceholderText('Buscar por título, contenido o abreviatura…'); self.busqueda.textChanged.connect(self.refrescar)
        herramientas.addWidget(self.busqueda); self.filtro=QComboBox(); self.filtro.addItems(['Todas','Propias','Compartidas']); self.filtro.currentIndexChanged.connect(self.refrescar); herramientas.addWidget(self.filtro)
        self.filtro_categoria=QComboBox(); self.filtro_categoria.addItem('Todas las categorías'); self.filtro_categoria.currentIndexChanged.connect(self.refrescar); herramientas.addWidget(self.filtro_categoria); cuerpo.addLayout(herramientas)
        divisor=QSplitter(Qt.Horizontal)
        biblioteca=QFrame(); biblioteca.setObjectName('panel'); lista_layout=QVBoxLayout(biblioteca)
        lista_layout.setContentsMargins(0,18,0,10); titulo_lista=QLabel('Biblioteca'); titulo_lista.setObjectName('section'); titulo_lista.setContentsMargins(20,0,20,5); lista_layout.addWidget(titulo_lista)
        self.lista=QListWidget(); self.lista.setTextElideMode(Qt.ElideRight); self.lista.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); self.lista.currentItemChanged.connect(self.seleccionar); lista_layout.addWidget(self.lista); divisor.addWidget(biblioteca)
        editor=QFrame(); editor.setObjectName('panel'); campos=QVBoxLayout(editor); campos.setContentsMargins(22,20,22,20); campos.setSpacing(10)
        superior=QHBoxLayout(); titulo_editor=QLabel('Editar frase'); titulo_editor.setObjectName('section'); superior.addWidget(titulo_editor); superior.addStretch(); self.origen=QLabel('Frase propia'); self.origen.setObjectName('muted'); superior.addWidget(self.origen); campos.addLayout(superior)
        campos.addSpacing(8); campos.addWidget(QLabel('Título')); self.titulo=QLineEdit(); campos.addWidget(self.titulo)
        fila=QHBoxLayout(); abre=QVBoxLayout(); abre.addWidget(QLabel('Abreviatura')); self.abreviatura=QLineEdit(); abre.addWidget(self.abreviatura)
        cate=QVBoxLayout(); cate.addWidget(QLabel('Categoría')); self.categoria=QComboBox(); cate.addWidget(self.categoria); fila.addLayout(abre); fila.addLayout(cate); campos.addLayout(fila)
        campos.addWidget(QLabel('Contenido')); self.contenido=QTextEdit(); self.contenido.setMinimumHeight(180); self.contenido.setAcceptRichText(False); self.contenido.textChanged.connect(self.previsualizar); campos.addWidget(self.contenido,2)
        variables=QHBoxLayout(); texto_vars=QLabel('VARIABLES'); texto_vars.setObjectName('muted'); variables.addWidget(texto_vars)
        for nombre in ['nombre','pedido','fecha']: variables.addWidget(boton('{'+nombre+'}',lambda checked=False,n=nombre:self.insertar_variable(n)))
        otras=QComboBox(); otras.addItems(['Otra variable…','monto','correo','telefono','direccion','empresa','orden']); otras.activated.connect(lambda index:(self.insertar_variable(otras.itemText(index)),otras.setCurrentIndex(0)) if index else None); variables.addWidget(otras)
        variables.addStretch(); campos.addLayout(variables)
        texto_preview=QLabel('VISTA PREVIA · DATOS DE EJEMPLO'); texto_preview.setObjectName('muted'); campos.addWidget(texto_preview)
        self.preview=QTextEdit(); self.preview.setObjectName('preview'); self.preview.setReadOnly(True); self.preview.setMinimumHeight(90); self.preview.setMaximumHeight(115); campos.addWidget(self.preview)
        acciones=QHBoxLayout(); self.favorita=boton('Marcar favorita',self.alternar); acciones.addWidget(self.favorita); acciones.addWidget(boton('Duplicar',self.duplicar)); acciones.addStretch(); self.guardar=boton('Guardar cambios',self.guardar_frase,True); acciones.addWidget(self.guardar); campos.addLayout(acciones)
        secundarias=QHBoxLayout(); self.eliminar=boton('Eliminar propia',self.eliminar_frase); secundarias.addWidget(self.eliminar); self.deshacer=boton('Deshacer',self.deshacer_frase); secundarias.addWidget(self.deshacer); secundarias.addWidget(boton('Completar y copiar',self.copiar)); campos.addLayout(secundarias)
        # Si la ventana es pequeña, desplazar el editor en vez de comprimir
        # sus controles hasta que se dibujen encima del contenido.
        campos.setSizeConstraint(QLayout.SetMinimumSize)
        editor_scroll=QScrollArea(); editor_scroll.setWidgetResizable(True); editor_scroll.setFrameShape(QFrame.NoFrame)
        editor_scroll.setMinimumWidth(570); editor_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        editor_scroll.setWidget(editor); divisor.addWidget(editor_scroll); divisor.setSizes([350,600]); cuerpo.addWidget(divisor,1)
        self.estado=QLabel(); self.estado.setObjectName('muted'); cuerpo.addWidget(self.estado); base.addWidget(area,1)
        QShortcut(QKeySequence('Ctrl+K'),self,activated=self.busqueda.setFocus)
        from .qt_dialogos import Trabajos
        self.trabajos=Trabajos(self)
        self.categorias(); self.cambiar_vista(False)

    def categorias(self):
        self.categoria.blockSignals(True)
        self.categoria.clear()
        for c in self.gestion.categorias_propias(): self.categoria.addItem(c['nombre'],c['id'])
        self.categoria.blockSignals(False)
        if hasattr(self,'filtro_categoria'):
            actual=self.filtro_categoria.currentText(); self.filtro_categoria.blockSignals(True); self.filtro_categoria.clear(); self.filtro_categoria.addItem('Todas las categorías')
            for nombre in sorted({c['nombre'] for c in self.gestion.repo.listar_categorias()}): self.filtro_categoria.addItem(nombre)
            self.filtro_categoria.setCurrentText(actual); self.filtro_categoria.blockSignals(False)

    def cambiar_vista(self,favoritas):
        self.favoritas=favoritas; self.nav_frases.setChecked(not favoritas); self.nav_favoritas.setChecked(favoritas)
        self.encabezado.setText('Favoritas' if favoritas else 'Mis frases'); self.refrescar()

    def refrescar(self,*_):
        ident=self.seleccion['id'] if self.seleccion else None
        self.lista.blockSignals(True); self.lista.clear()
        consulta=self.busqueda.text().casefold(); filtro=self.filtro.currentText()
        for f in self.gestion.listar():
            favorita=self.gestion.es_favorita(f)
            if self.favoritas and not favorita: continue
            if self.filtro_categoria.currentIndex()>0 and f.get('categoria')!=self.filtro_categoria.currentText(): continue
            if filtro=='Propias' and f['origen']!='propia' or filtro=='Compartidas' and f['origen']!='compartida': continue
            if consulta not in ' '.join(str(f.get(k,'')) for k in ('titulo','contenido','abreviatura','categoria')).casefold(): continue
            item=QListWidgetItem(('[Favorita]  ' if favorita else '')+f['titulo']+'\n'+f['contenido'].replace('\n',' ')[:65]+'…\n'+f['abreviatura']+'   ·   '+f.get('categoria','General')+'   ·   '+f['origen'].capitalize())
            categoria=next((c for c in self.gestion.repo.listar_categorias() if c['id']==f['categoria_id']),None)
            if categoria:
                muestra=QPixmap(12,12); muestra.fill(QColor(categoria['color'])); item.setIcon(QIcon(muestra))
            item.setData(Qt.UserRole,f); self.lista.addItem(item)
            if f['id']==ident: self.lista.setCurrentItem(item)
        self.lista.blockSignals(False)
        self.estado.setText(f'{self.lista.count()} frases · '+('Demostración: datos temporales; sin conexión ni captura de teclado.' if self.demostracion else 'FraseYa · Biblioteca local y catálogo compartido'))
        self.deshacer.setEnabled(self.gestion.puede_deshacer())
        if self.lista.currentItem(): self.seleccionar(self.lista.currentItem())
        elif self.lista.count(): self.lista.setCurrentRow(0)
        else: self.nueva()

    def seleccionar(self,item,*_):
        if item is None: return
        self.seleccion=item.data(Qt.UserRole); f=self.seleccion; propia=f['origen']=='propia'
        self.titulo.setText(f['titulo']); self.abreviatura.setText(f['abreviatura']); self.contenido.setPlainText(f['contenido'])
        self.titulo.setReadOnly(not propia); self.abreviatura.setReadOnly(not propia); self.contenido.setReadOnly(not propia)
        self.categoria.setEnabled(propia); self.categoria.setCurrentIndex(self.categoria.findData(f['categoria_id']))
        self.guardar.setEnabled(propia); self.eliminar.setEnabled(propia); self.favorita.setEnabled(True)
        self.favorita.setText('Quitar favorita' if self.gestion.es_favorita(f) else 'Marcar favorita'); self.origen.setText('Frase propia' if propia else 'Compartida · solo lectura')

    def nueva(self):
        self.seleccion=None; self.lista.clearSelection()
        for campo in [self.titulo,self.abreviatura]: campo.setReadOnly(False); campo.clear()
        self.contenido.setReadOnly(False); self.contenido.clear(); self.categoria.setEnabled(True); self.categoria.setCurrentIndex(0)
        self.guardar.setEnabled(True); self.eliminar.setEnabled(False); self.favorita.setEnabled(False); self.origen.setText('Nueva frase propia'); self.titulo.setFocus()

    def previsualizar(self):
        texto=self.contenido.toPlainText(); valores={'nombre':'Carolina','pedido':'1024','fecha':'15/10/2026'}
        self.preview.setPlainText(sustituir(texto,valores))

    def insertar_variable(self,nombre):
        if self.contenido.isReadOnly(): return
        existentes=set(detectar(self.contenido.toPlainText()))
        if nombre in existentes:
            d=QMessageBox(self); d.setWindowTitle('Variable repetida'); d.setText('¿Desea reutilizar el mismo valor o completar uno diferente?')
            misma=d.addButton('Mismo valor',QMessageBox.AcceptRole); otra=d.addButton('Otro valor',QMessageBox.ActionRole); d.addButton('Cancelar',QMessageBox.RejectRole); d.exec()
            if d.clickedButton()==otra:
                n=2
                while f'{nombre}_{n}' in existentes: n+=1
                nombre=f'{nombre}_{n}'
            elif d.clickedButton()!=misma: return
        self.contenido.insertPlainText('{'+nombre+'}'); self.contenido.setFocus()

    def operar(self,accion):
        try: accion()
        except (ValueError,PermissionError,LookupError) as error: QMessageBox.warning(self,'FraseYa',str(error)); return
        self.refrescar()
        self.frases_cambiaron()

    def guardar_frase(self):
        def guardar():
            argumentos=(self.titulo.text(),self.abreviatura.text(),self.contenido.toPlainText(),self.categoria.currentData())
            if self.seleccion: self.gestion.editar(self.seleccion['id'],*argumentos)
            else: self.seleccion=self.gestion.repo.obtener_frase(self.gestion.crear(*argumentos))
        self.operar(guardar)

    def alternar(self):
        if self.seleccion: self.operar(lambda:self.gestion.alternar_favorita(self.seleccion['id']))

    def duplicar(self):
        if self.seleccion:
            def duplicar(): self.seleccion=self.gestion.repo.obtener_frase(self.gestion.duplicar(self.seleccion['id']))
            self.operar(duplicar)

    def eliminar_frase(self):
        if self.seleccion and QMessageBox.question(self,'Eliminar frase propia','¿Eliminar esta frase? Puede deshacerlo durante esta sesión.')==QMessageBox.Yes:
            self.operar(lambda:self.gestion.eliminar(self.seleccion['id']))

    def deshacer_frase(self): self.operar(self.gestion.deshacer_eliminacion)

    def copiar(self):
        texto=self.contenido.toPlainText()
        if not texto.strip(): return
        nombres=detectar(texto); valores={}
        if nombres:
            from .qt_dialogos import completar_variables
            valores=completar_variables(self,texto)
            if valores is None: return
            QApplication.clipboard().setText(sustituir(texto,valores)); self.estado.setText('Respuesta copiada. Revísela antes de pegarla.'); return
        QApplication.clipboard().setText(sustituir(texto,valores)); self.estado.setText('Respuesta copiada. Revísela antes de pegarla en la conversación.')

    def mostrar_id(self,ident):
        for i in range(self.lista.count()):
            if self.lista.item(i).data(Qt.UserRole)['id']==ident: self.lista.setCurrentRow(i); return

    def frases_cambiaron(self):
        if self.al_cambiar: self.al_cambiar()

    def abrir_ia(self):
        if not self.sesion or self.sesion.token=='offline': QMessageBox.warning(self,'IA','Inicie sesión con conexión para usar la IA.'); return
        from .qt_dialogos import IAQt
        d=IAQt(self,self.autenticacion.cliente,self.gestion,self.sesion.rol=='administrador'); d.exec()

    def ajustes(self):
        from .qt_dialogos import AjustesQt
        from fraseya.aplicacion.configuracion import Configuracion
        AjustesQt(self,Configuracion(self.gestion.repo),lambda a:self.al_configurar(a) if self.al_configurar else None).exec()

    def sincronizar(self):
        if self.al_sincronizar: self.al_sincronizar()

    def importar_excel(self):
        from PySide6.QtWidgets import QFileDialog
        from fraseya.aplicacion.importacion_excel import importar_excel
        ruta,_=QFileDialog.getOpenFileName(self,'Importar frases','','Excel (*.xlsx)')
        if not ruta: return
        try:
            resultado=importar_excel(ruta,self.gestion,self.autenticacion,self.sesion)
            QMessageBox.information(self,'Importación',f'Importadas: {resultado.importadas}\nRechazadas: {len(resultado.rechazadas)}')
            self.categorias(); self.refrescar(); self.frases_cambiaron()
        except (ValueError,PermissionError,OSError) as e: QMessageBox.warning(self,'Importación',str(e))

    def categorias_admin(self):
        from PySide6.QtWidgets import QColorDialog
        d=QDialog(self); d.setStyleSheet(ESTILO); d.setWindowTitle('Categorías · administrador'); d.resize(480,300)
        l=QVBoxLayout(d); selector=QComboBox(); categorias=self.gestion.categorias_propias()
        for c in categorias: selector.addItem(c['nombre'],c)
        nombre=QLineEdit(); color=QLineEdit(); l.addWidget(selector); l.addWidget(QLabel('Nombre')); l.addWidget(nombre); l.addWidget(QLabel('Color #RRGGBB')); l.addWidget(color)
        def cargar():
            c=selector.currentData(); nombre.setText(c['nombre']); color.setText(c['color'])
        selector.currentIndexChanged.connect(cargar); cargar()
        def elegir_color():
            c=QColorDialog.getColor(parent=d)
            if c.isValid(): color.setText(c.name())
        l.addWidget(boton('Elegir color',elegir_color))
        aviso=QLabel(); aviso.setWordWrap(True); l.addWidget(aviso)
        def cambiar(accion):
            try:
                if accion=='crear': self.gestion.crear_categoria(nombre.text(),self.autenticacion,self.sesion,color.text())
                else: self.gestion.editar_categoria(selector.currentData()['id'],nombre.text(),color.text(),self.autenticacion,self.sesion,eliminar=accion=='eliminar')
            except (ValueError,PermissionError) as e: aviso.setText(str(e)); return
            self.categorias(); self.refrescar(); self.frases_cambiaron(); d.accept()
        fila=QHBoxLayout()
        for texto,accion in [('Crear','crear'),('Guardar','editar'),('Eliminar','eliminar')]: fila.addWidget(boton(texto,lambda checked=False,a=accion:cambiar(a)))
        l.addLayout(fila); d.exec()

    def publicar(self,eliminar=False):
        from fraseya.aplicacion.publicacion_supabase import PublicacionSupabase
        if self._publicando or not self.sesion or self.sesion.token=='offline': return
        if eliminar and (not self.seleccion or self.seleccion['origen']!='compartida'):
            QMessageBox.warning(self,'Catálogo','Seleccione una frase compartida para retirarla.'); return
        servicio=PublicacionSupabase(self.gestion.repo,self.autenticacion,self.sesion)
        categorias=[] if eliminar else servicio.recoger_categorias(); operaciones=self.gestion.operaciones_categorias()
        eliminadas=(self.seleccion['abreviatura'],) if eliminar else ()
        self._publicando=True; self.estado.setText('Preparando publicación…')
        def vista_lista(vista,error):
            if error: self._publicando=False; self.estado.setText(str(error)); return
            resumen=f'Versión {vista.version}: {vista.cantidad_frases} frases.\nNuevas: {vista.nuevas} · Modificadas: {vista.modificadas} · Eliminadas: {vista.eliminadas}\n¿Publicar en el catálogo compartido?'
            if QMessageBox.question(self,'Confirmar publicación',resumen)!=QMessageBox.Yes: self._publicando=False; return
            self.trabajos.ejecutar(lambda:servicio.publicar(vista,confirmar_vacio=vista.cantidad_frases==0),publicado)
        def publicado(resultado,error):
            self._publicando=False; self.estado.setText(str(error) if error else f'Publicado: versión {resultado.version}')
            if not error: self.sincronizar()
        self.trabajos.ejecutar(lambda:servicio.preparar(categorias,eliminar=eliminadas,operaciones_categorias=operaciones),vista_lista)

    def cerrar_sesion(self):
        self._cerrando=True; self.close()

    def closeEvent(self,event):
        if self._publicando or self.trabajos.pendientes:
            QMessageBox.information(self,'Operación en curso','Espere a que termine la operación antes de salir.'); event.ignore(); return
        if self.al_salir: self.al_salir()
        self.trabajos.detener(); event.accept()


