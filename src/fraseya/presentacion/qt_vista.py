"""Interfaz nativa Qt unificada: todas las secciones viven dentro de la misma ventana."""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QKeySequence, QShortcut, QFontDatabase, QPixmap, QColor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QTextEdit, QComboBox, QListWidget, QListWidgetItem,
    QFrame, QSplitter, QScrollArea, QLayout, QStackedWidget,
)
from fraseya.aplicacion.buscador import buscar as buscar_frases
from fraseya.aplicacion.configuracion import Configuracion
from fraseya.aplicacion.resolver_variables import detectar, sustituir
from fraseya.dominio.reglas import COLOR_DEFECTO, VARIABLES_OFICIALES
from .identidad import recurso
from .qt_paneles import (
    boton, EtiquetaSegura, EtiquetaSegura as QLabel, Trabajos,
    PanelIA, PanelEmpresa, PanelAjustes, PanelImportar, PanelCategorias,
    PanelCatalogo, PanelUsuarios, PanelVariables,
)
from .qt_temas import ESTILO, ESTILO_OSCURO, hoja_estilo, normalizar_tema, paleta


class VentanaQt(QMainWindow):
    def __init__(self, gestion, demostracion=False, autenticacion=None, sesion=None):
        super().__init__()
        fuente = Path('C:/Windows/Fonts/segoeui.ttf')
        if fuente.exists():
            QFontDatabase.addApplicationFont(str(fuente))
        self.gestion = gestion
        self.demostracion = demostracion
        self.seleccion = None
        self.autenticacion, self.sesion = autenticacion, sesion
        self.al_cambiar = None
        self.al_configurar = None
        self.al_cambiar_tema = None
        self.al_toggle_vivo = None
        self.al_probar_vivo = None
        self.al_analizar_portapapeles = None
        self.al_sincronizar = None
        self.al_salir = None
        self._cerrando = False
        self.solicito_cerrar_sesion = False
        self._ia = None
        self._controlador_vivo_demo = None
        self.favoritas = False
        self.cargando = False
        self._pagina_actual = 'frases'
        self._origen_variables = 'frases'
        self._var_pendiente = None
        self._nav_botones = {}
        self._paginas = {}
        self.tema_actual = normalizar_tema(Configuracion(self.gestion.repo).leer().tema)

        self.setWindowTitle('FraseYa · Interfaz Qt' + (' · Demostración' if demostracion else ''))
        self.resize(1200, 820)
        self.setMinimumSize(1060, 720)
        self.setWindowIcon(QIcon(str(recurso('fraseya.ico'))))

        self.trabajos = Trabajos(self)
        online = bool(sesion and sesion.token != 'offline')
        es_admin = bool(online and sesion.rol == 'administrador')

        central = QWidget()
        self.setCentralWidget(central)
        base = QHBoxLayout(central)
        base.setContentsMargins(0, 0, 0, 0)
        base.setSpacing(0)

        # Barra lateral
        lateral = QFrame()
        lateral.setObjectName('sidebar')
        lateral.setFixedWidth(216)
        nav = QVBoxLayout(lateral)
        nav.setContentsMargins(16, 26, 16, 20)
        nav.setSpacing(6)
        marca = QLabel('FraseYa')
        marca.setObjectName('brand')
        nav.addWidget(marca)
        lema = QLabel('Las palabras, a su tiempo.')
        lema.setObjectName('muted')
        nav.addWidget(lema)
        nav.addSpacing(22)

        self.nav_frases = self._agregar_nav(nav, 'frases', 'Mis frases', lambda: self.cambiar_vista(False))
        self.nav_favoritas = self._agregar_nav(nav, 'favoritas', 'Favoritas', lambda: self.cambiar_vista(True))

        if not demostracion:
            self.nav_ia = self._agregar_nav(nav, 'ia', 'Asistente IA', self.abrir_ia)
            self.nav_ia.setEnabled(online)
            self.nav_importar = self._agregar_nav(nav, 'importar', 'Importar Excel', self.importar_excel)
            self.nav_configuracion = self._agregar_nav(nav, 'configuracion', 'Configuración', self.ajustes)
            btn_sync = boton('Sincronizar ahora', self.sincronizar)
            btn_sync.setObjectName('nav')
            nav.addWidget(btn_sync)

            self.sincronizacion = QLabel('Catálogo central · Supabase')
            self.sincronizacion.setWordWrap(True)
            self.sincronizacion.setObjectName('muted')
            self.sincronizacion.setContentsMargins(12, 4, 8, 4)
            nav.addWidget(self.sincronizacion)

            if es_admin:
                et_admin = QLabel('ADMINISTRACIÓN')
                et_admin.setObjectName('nav_group')
                nav.addWidget(et_admin)
                self.nav_publicar = self._agregar_nav(nav, 'publicar', 'Publicar catálogo', lambda: self.publicar(False))
                self.nav_retirar = self._agregar_nav(nav, 'retirar', 'Retirar del catálogo', lambda: self.publicar(True))
                self.nav_categorias = self._agregar_nav(nav, 'categorias', 'Gestionar categorías', self.categorias_admin)
                self.nav_usuarios = self._agregar_nav(nav, 'usuarios', 'Administrar usuarios', self.abrir_usuarios)

        nav.addStretch()
        nota = QLabel('Demostración · datos temporales' if demostracion else ((sesion.usuario + '\n' + sesion.rol) if sesion else 'FraseYa'))
        nota.setWordWrap(True)
        nota.setObjectName('muted')
        nota.setContentsMargins(8, 0, 8, 6)
        nav.addWidget(nota)
        self.btn_tema = boton('', self.alternar_tema, estilo='theme_toggle')
        self.btn_tema.setToolTip('Cambiar entre tema claro y tema oscuro')
        nav.addWidget(self.btn_tema)
        if not demostracion:
            nav.addWidget(boton('Cerrar sesión', self.cerrar_sesion))

        desplazamiento = QScrollArea()
        desplazamiento.setWidgetResizable(True)
        desplazamiento.setFrameShape(QFrame.NoFrame)
        desplazamiento.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        desplazamiento.setFixedWidth(218)
        desplazamiento.setWidget(lateral)
        base.addWidget(desplazamiento)

        # Área principal unificada con banner de avisos + stack de vistas
        area = QWidget()
        cuerpo = QVBoxLayout(area)
        cuerpo.setContentsMargins(32, 24, 32, 18)
        cuerpo.setSpacing(14)

        self.banner = QFrame()
        self.banner.setObjectName('banner_info')
        bl = QHBoxLayout(self.banner)
        bl.setContentsMargins(16, 10, 12, 10)
        self._banner_texto = QLabel('')
        self._banner_texto.setWordWrap(True)
        bl.addWidget(self._banner_texto, 1)
        cerrar_banner = boton('Cerrar', self.ocultar_aviso, estilo='ghost')
        cerrar_banner.setFixedHeight(30)
        bl.addWidget(cerrar_banner)
        self.banner.hide()
        cuerpo.addWidget(self.banner)

        self.paginas = QStackedWidget()
        cuerpo.addWidget(self.paginas, 1)

        self.estado = QLabel('')
        self.estado.setObjectName('muted')
        cuerpo.addWidget(self.estado)
        base.addWidget(area, 1)

        # Página 1: Mis frases / Favoritas
        self._registrar_pagina('frases', self._crear_pagina_frases())

        # Página 2: Completar variables y copiar
        self.panel_variables = PanelVariables(
            al_copiar=self._variables_copiadas,
            al_cancelar=self._volver_de_variables,
            parent=self,
        )
        self._registrar_pagina('variables', self.panel_variables)

        # Páginas integradas del programa completo
        self.panel_ia = None
        self.panel_empresa = None
        self.panel_ajustes = None
        self.panel_importar = None
        self.panel_categorias = None
        self.panel_catalogo = None
        self.panel_usuarios = None

        if not demostracion:
            self.panel_ajustes = PanelAjustes(
                Configuracion(self.gestion.repo),
                al_guardar=self._ajustes_guardados,
                parent=self,
            )
            self._registrar_pagina('configuracion', self.panel_ajustes)

            self.panel_importar = PanelImportar(
                self.gestion, self.autenticacion, self.sesion,
                al_importar=self._despues_de_importar,
                parent=self,
            )
            self._registrar_pagina('importar', self.panel_importar)

            if online and self.autenticacion is not None:
                self.panel_ia = PanelIA(
                    self.gestion, self.autenticacion.cliente, es_admin,
                    al_elegir=self._elegir_desde_ia,
                    al_actualizar=self._actualizar_biblioteca,
                    al_abrir_empresa=self.abrir_empresa if es_admin else None,
                    al_copiar=lambda txt, tit: self._iniciar_copia(txt, tit, origen='ia'),
                    al_toggle_vivo=self._manejar_toggle_vivo,
                    al_probar_vivo=self._manejar_probar_vivo,
                    al_analizar_portapapeles=self._manejar_analizar_portapapeles,
                    parent=self, trabajos=self.trabajos,
                )
                self._ia = self.panel_ia
                self._registrar_pagina('ia', self.panel_ia)

            if es_admin and self.autenticacion is not None:
                self.panel_empresa = PanelEmpresa(
                    self.autenticacion.cliente,
                    al_volver=self.abrir_ia,
                    parent=self, trabajos=self.trabajos,
                )
                self._registrar_pagina('empresa', self.panel_empresa)

                self.panel_categorias = PanelCategorias(
                    self.gestion, self.autenticacion, self.sesion,
                    al_cambiar=self._actualizar_biblioteca,
                    parent=self,
                )
                self._registrar_pagina('categorias', self.panel_categorias)

                self.panel_catalogo = PanelCatalogo(
                    self.gestion, self.autenticacion, self.sesion,
                    al_publicado=self._catalogo_publicado,
                    al_volver=lambda: self.cambiar_vista(self.favoritas),
                    parent=self, trabajos=self.trabajos,
                )
                self._registrar_pagina('publicar', self.panel_catalogo)

                self.panel_usuarios = PanelUsuarios(
                    al_volver=lambda: self.cambiar_vista(self.favoritas),
                    parent=self,
                )
                self._registrar_pagina('usuarios', self.panel_usuarios)

        QShortcut(QKeySequence('Ctrl+K'), self, activated=self._enfocar_busqueda)
        self.aplicar_tema(self.tema_actual)
        self.categorias()
        self.cambiar_vista(False)

    def aplicar_tema(self, tema):
        nuevo = normalizar_tema(tema)
        self.tema_actual = nuevo
        qss = hoja_estilo(nuevo)
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(qss)
        self.setStyleSheet(qss)
        if hasattr(self, 'btn_tema'):
            self.btn_tema.setText('Tema claro' if nuevo == 'oscuro' else 'Tema oscuro')
        if self.panel_ajustes is not None:
            self.panel_ajustes.establecer_tema(nuevo)
        if self._controlador_vivo_demo is not None:
            self._controlador_vivo_demo.aplicar_tema(nuevo)
        if self.al_cambiar_tema:
            self.al_cambiar_tema(nuevo)

    def alternar_tema(self):
        nuevo = 'claro' if self.tema_actual == 'oscuro' else 'oscuro'
        cambios = Configuracion(self.gestion.repo).guardar({'tema': nuevo})
        self.aplicar_tema(cambios.tema)
        if self.al_configurar:
            self.al_configurar(cambios)
        if hasattr(self, 'estado'):
            self.estado.setText(f'Tema visual aplicado: {"Oscuro" if cambios.tema == "oscuro" else "Claro"}.')
        return cambios.tema

    def _manejar_toggle_vivo(self, activo):
        if self.al_toggle_vivo is not None:
            self.al_toggle_vivo(bool(activo))
            return
        if self._controlador_vivo_demo is not None:
            self._controlador_vivo_demo.establecer_activo(bool(activo))
        if self.panel_ia is not None:
            self.panel_ia.establecer_estado_vivo(
                bool(activo),
                'Estado: Activo. Observando ventanas de WhatsApp.'
                if activo else 'Estado: Pausado (opt-in).',
            )

    def _manejar_probar_vivo(self):
        if self.al_probar_vivo is not None:
            self.al_probar_vivo()
            return
        from fraseya.aplicacion.asistente_vivo import ServicioAsistenteVivo
        from .qt_flotante import ControladorFlotanteQt

        if self._controlador_vivo_demo is None:
            def _usar_demo(_frase, texto):
                QApplication.clipboard().setText(texto)
                self._controlador_vivo_demo.mostrar_aviso('Copiada al portapapeles. Revísala antes de enviar.')
                self.estado.setText('Sugerencia copiada al portapapeles. Revísala antes de enviarla.')

            self._controlador_vivo_demo = ControladorFlotanteQt(
                parent=self,
                tema=self.tema_actual,
                al_usar=_usar_demo,
                al_toggle_activo=self._manejar_toggle_vivo,
                al_analizar_portapapeles=self._manejar_analizar_portapapeles,
            )
        resultado = ServicioAsistenteVivo.crear_resultado_demo(self.gestion.listar())
        self._controlador_vivo_demo.aplicar_tema(self.tema_actual)
        self._controlador_vivo_demo.mostrar_sugerencias(resultado)
        if self.panel_ia is not None:
            self.panel_ia.estado_vivo.setText(
                'Vista previa abierta: prueba «Usar», «Editar» o descartar cada tarjeta flotante.'
            )

    def _manejar_analizar_portapapeles(self):
        if self.al_analizar_portapapeles is not None:
            self.al_analizar_portapapeles()
            return
        if self.panel_ia is None:
            return
        texto = QApplication.clipboard().text()
        if not texto.strip():
            self.panel_ia.estado_vivo.setText('Portapapeles vacío. Copia un mensaje del cliente primero.')
            return
        if len(texto) > 4000:
            self.panel_ia.estado_vivo.setText('El mensaje del portapapeles supera 4.000 caracteres.')
            return
        self.panel_ia.mensaje.setPlainText(texto)
        self.panel_ia.estado_vivo.setText('Mensaje del portapapeles cargado. Pulsa «Preparar respuesta».')

    def _agregar_nav(self, layout, clave, texto, accion):
        b = boton(texto, accion)
        b.setObjectName('nav')
        b.setCheckable(True)
        layout.addWidget(b)
        self._nav_botones[clave] = b
        return b

    def _registrar_pagina(self, clave, widget):
        self._paginas[clave] = widget
        self.paginas.addWidget(widget)

    def _marcar_nav(self, clave):
        for k, b in self._nav_botones.items():
            b.setChecked(k == clave)

    def mostrar_pagina(self, clave, nav_clave=None):
        if clave not in self._paginas:
            return
        self._pagina_actual = clave
        self.paginas.setCurrentWidget(self._paginas[clave])
        self._marcar_nav(nav_clave if nav_clave is not None else clave)

    def mostrar_aviso(self, texto, tipo='info'):
        mapa = {'info': 'banner_info', 'ok': 'banner_ok', 'aviso': 'banner_aviso', 'error': 'banner_error'}
        self.banner.setObjectName(mapa.get(tipo, 'banner_info'))
        self.banner.style().unpolish(self.banner)
        self.banner.style().polish(self.banner)
        self._banner_texto.setText(texto)
        self.banner.show()

    def ocultar_aviso(self):
        self.banner.hide()

    def _enfocar_busqueda(self):
        self.mostrar_pagina('frases', 'favoritas' if self.favoritas else 'frases')
        self.busqueda.setFocus()

    def _crear_pagina_frases(self):
        pagina = QWidget()
        cuerpo = QVBoxLayout(pagina)
        cuerpo.setContentsMargins(0, 0, 0, 0)
        cuerpo.setSpacing(16)

        cabecera = QHBoxLayout()
        titulos = QVBoxLayout()
        self.encabezado = QLabel('Mis frases')
        self.encabezado.setObjectName('heading')
        titulos.addWidget(self.encabezado)
        subtitulo = QLabel('Encuentra las palabras correctas, sin empezar de cero.')
        subtitulo.setObjectName('muted')
        titulos.addWidget(subtitulo)
        cabecera.addLayout(titulos)
        cabecera.addStretch()
        cabecera.addWidget(boton('+  Nueva frase', self.nueva, True))
        cuerpo.addLayout(cabecera)

        herramientas = QHBoxLayout()
        self.busqueda = QLineEdit()
        self.busqueda.setPlaceholderText('Buscar por título, contenido o abreviatura…')
        self.busqueda.textChanged.connect(self.refrescar)
        herramientas.addWidget(self.busqueda)
        self.filtro = QComboBox()
        self.filtro.addItems(['Todas', 'Propias', 'Compartidas'])
        self.filtro.currentIndexChanged.connect(self.refrescar)
        herramientas.addWidget(self.filtro)
        self.filtro_categoria = QComboBox()
        self.filtro_categoria.addItem('Todas las categorías')
        self.filtro_categoria.currentIndexChanged.connect(self.refrescar)
        herramientas.addWidget(self.filtro_categoria)
        cuerpo.addLayout(herramientas)

        divisor = QSplitter(Qt.Horizontal)
        biblioteca = QFrame()
        biblioteca.setObjectName('panel')
        lista_layout = QVBoxLayout(biblioteca)
        lista_layout.setContentsMargins(0, 18, 0, 10)
        titulo_lista = QLabel('Biblioteca')
        titulo_lista.setObjectName('section')
        titulo_lista.setContentsMargins(20, 0, 20, 5)
        lista_layout.addWidget(titulo_lista)
        self.lista = QListWidget()
        self.lista.setTextElideMode(Qt.ElideRight)
        self.lista.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.lista.currentItemChanged.connect(self.seleccionar)
        lista_layout.addWidget(self.lista)
        divisor.addWidget(biblioteca)

        editor = QFrame()
        editor.setObjectName('panel')
        campos = QVBoxLayout(editor)
        campos.setContentsMargins(22, 16, 22, 16)
        campos.setSpacing(8)
        superior = QHBoxLayout()
        titulo_editor = QLabel('Editar frase')
        titulo_editor.setObjectName('section')
        superior.addWidget(titulo_editor)
        superior.addStretch()
        self.origen = QLabel('Frase propia')
        self.origen.setObjectName('muted')
        superior.addWidget(self.origen)
        campos.addLayout(superior)

        campos.addWidget(QLabel('Título'))
        self.titulo = QLineEdit()
        campos.addWidget(self.titulo)

        fila = QHBoxLayout()
        abre = QVBoxLayout()
        abre.addWidget(QLabel('Abreviatura'))
        self.abreviatura = QLineEdit()
        abre.addWidget(self.abreviatura)
        cate = QVBoxLayout()
        cate.addWidget(QLabel('Categoría'))
        self.categoria = QComboBox()
        cate.addWidget(self.categoria)
        fila.addLayout(abre)
        fila.addLayout(cate)
        campos.addLayout(fila)

        campos.addWidget(QLabel('Contenido'))
        self.contenido = QTextEdit()
        self.contenido.setMinimumHeight(115)
        self.contenido.setAcceptRichText(False)
        self.contenido.textChanged.connect(self.previsualizar)
        campos.addWidget(self.contenido, 2)

        variables = QHBoxLayout()
        texto_vars = QLabel('VARIABLES')
        texto_vars.setObjectName('muted')
        variables.addWidget(texto_vars)
        for nombre in VARIABLES_OFICIALES[:3]:
            variables.addWidget(boton('{' + nombre + '}', lambda checked=False, n=nombre: self.insertar_variable(n)))
        otras = QComboBox()
        otras.addItems(['Otra variable…', *VARIABLES_OFICIALES[3:]])
        otras.activated.connect(lambda index: (self.insertar_variable(otras.itemText(index)), otras.setCurrentIndex(0)) if index else None)
        variables.addWidget(otras)
        variables.addStretch()
        campos.addLayout(variables)

        # Barra inline para variable repetida (reemplaza QMessageBox)
        self.barra_var_repetida = QFrame()
        self.barra_var_repetida.setObjectName('inline_confirm')
        vl = QHBoxLayout(self.barra_var_repetida)
        vl.setContentsMargins(12, 8, 12, 8)
        self._txt_var_repetida = QLabel('')
        self._txt_var_repetida.setWordWrap(True)
        vl.addWidget(self._txt_var_repetida, 1)
        vl.addWidget(boton('Mismo valor', lambda: self._resolver_var_repetida(False)))
        self._btn_var_otra = boton('Otro valor', lambda: self._resolver_var_repetida(True), True)
        vl.addWidget(self._btn_var_otra)
        vl.addWidget(boton('Cancelar', self._ocultar_confirmaciones_editor, estilo='ghost'))
        self.barra_var_repetida.hide()
        campos.addWidget(self.barra_var_repetida)

        texto_preview = QLabel('VISTA PREVIA · DATOS DE EJEMPLO')
        texto_preview.setObjectName('muted')
        campos.addWidget(texto_preview)
        self.preview = QTextEdit()
        self.preview.setObjectName('preview')
        self.preview.setReadOnly(True)
        self.preview.setMinimumHeight(68)
        self.preview.setMaximumHeight(95)
        campos.addWidget(self.preview)

        # Barra inline para confirmar eliminación (reemplaza QMessageBox)
        self.confirmar_eliminacion = QFrame()
        self.confirmar_eliminacion.setObjectName('inline_confirm')
        el = QHBoxLayout(self.confirmar_eliminacion)
        el.setContentsMargins(12, 8, 12, 8)
        self._txt_eliminar = QLabel('')
        self._txt_eliminar.setWordWrap(True)
        el.addWidget(self._txt_eliminar, 1)
        el.addWidget(boton('Confirmar eliminación', self._confirmar_eliminar_frase, estilo='danger'))
        el.addWidget(boton('Cancelar', self._ocultar_confirmaciones_editor, estilo='ghost'))
        self.confirmar_eliminacion.hide()
        campos.addWidget(self.confirmar_eliminacion)

        acciones = QHBoxLayout()
        self.favorita = boton('Marcar favorita', self.alternar)
        acciones.addWidget(self.favorita)
        acciones.addWidget(boton('Duplicar', self.duplicar))
        acciones.addStretch()
        self.guardar = boton('Guardar cambios', self.guardar_frase, True)
        acciones.addWidget(self.guardar)
        campos.addLayout(acciones)

        secundarias = QHBoxLayout()
        self.eliminar = boton('Eliminar propia', self.eliminar_frase)
        secundarias.addWidget(self.eliminar)
        self.deshacer = boton('Deshacer', self.deshacer_frase)
        secundarias.addWidget(self.deshacer)
        secundarias.addWidget(boton('Completar y copiar', self.copiar))
        campos.addLayout(secundarias)

        campos.setSizeConstraint(QLayout.SetMinimumSize)
        editor_scroll = QScrollArea()
        editor_scroll.setWidgetResizable(True)
        editor_scroll.setFrameShape(QFrame.NoFrame)
        editor_scroll.setMinimumWidth(570)
        editor_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        editor_scroll.setWidget(editor)
        divisor.addWidget(editor_scroll)
        divisor.setSizes([350, 600])
        cuerpo.addWidget(divisor, 1)
        return pagina

    def _ocultar_confirmaciones_editor(self):
        self.confirmar_eliminacion.hide()
        self.barra_var_repetida.hide()
        self._var_pendiente = None

    def categorias(self):
        self.categoria.blockSignals(True)
        self.categoria.clear()
        for c in self.gestion.categorias_propias():
            self.categoria.addItem(c['nombre'], c['id'])
        self.categoria.blockSignals(False)
        if hasattr(self, 'filtro_categoria'):
            actual = self.filtro_categoria.currentText()
            self.filtro_categoria.blockSignals(True)
            self.filtro_categoria.clear()
            self.filtro_categoria.addItem('Todas las categorías')
            for nombre in sorted({c['nombre'] for c in self.gestion.repo.listar_categorias()}):
                self.filtro_categoria.addItem(nombre)
            self.filtro_categoria.setCurrentText(actual)
            self.filtro_categoria.blockSignals(False)
        if self.panel_categorias is not None:
            self.panel_categorias.recargar()

    def cambiar_vista(self, favoritas):
        self.favoritas = favoritas
        self.encabezado.setText('Favoritas' if favoritas else 'Mis frases')
        self.mostrar_pagina('frases', 'favoritas' if favoritas else 'frases')
        self.refrescar()

    def refrescar(self, *_):
        self._ocultar_confirmaciones_editor()
        ident = self.seleccion['id'] if self.seleccion else None
        self.lista.blockSignals(True)
        self.lista.clear()
        consulta = self.busqueda.text().strip()
        filtro = self.filtro.currentText()
        categoria_filtro = self.filtro_categoria.currentText() if self.filtro_categoria.currentIndex() > 0 else None
        frases = self.gestion.listar()
        if consulta:
            frases = buscar_frases(frases, consulta)
        for f in frases:
            favorita = bool(f.get('favorita'))
            if self.favoritas and not favorita:
                continue
            if categoria_filtro is not None and f.get('categoria') != categoria_filtro:
                continue
            if filtro == 'Propias' and f['origen'] != 'propia' or filtro == 'Compartidas' and f['origen'] != 'compartida':
                continue
            item = QListWidgetItem(
                ('[Favorita]  ' if favorita else '') + f['titulo'] + '\n'
                + f['contenido'].replace('\n', ' ')[:65] + '…\n'
                + f['abreviatura'] + '   ·   ' + f.get('categoria', 'General') + '   ·   ' + f['origen'].capitalize()
            )
            muestra = QPixmap(12, 12)
            muestra.fill(QColor(f.get('color') or COLOR_DEFECTO))
            item.setIcon(QIcon(muestra))
            item.setData(Qt.UserRole, f)
            self.lista.addItem(item)
            if f['id'] == ident:
                self.lista.setCurrentItem(item)
        self.lista.blockSignals(False)
        self.estado.setText(
            f'{self.lista.count()} frases · '
            + ('Demostración: datos temporales; sin conexión ni captura de teclado.'
               if self.demostracion else 'FraseYa · Biblioteca local y catálogo compartido')
        )
        self.deshacer.setEnabled(self.gestion.puede_deshacer())
        if self.lista.currentItem():
            self.seleccionar(self.lista.currentItem())
        elif self.lista.count():
            self.lista.setCurrentRow(0)
        else:
            self.nueva()

    def seleccionar(self, item, *_):
        if item is None:
            return
        self._ocultar_confirmaciones_editor()
        self.seleccion = item.data(Qt.UserRole)
        f = self.seleccion
        propia = f['origen'] == 'propia'
        self.titulo.setText(f['titulo'])
        self.abreviatura.setText(f['abreviatura'])
        self.contenido.setPlainText(f['contenido'])
        self.titulo.setReadOnly(not propia)
        self.abreviatura.setReadOnly(not propia)
        self.contenido.setReadOnly(not propia)
        self.categoria.setEnabled(propia)
        self.categoria.setCurrentIndex(self.categoria.findData(f['categoria_id']))
        self.guardar.setEnabled(propia)
        self.eliminar.setEnabled(propia)
        self.favorita.setEnabled(True)
        self.favorita.setText('Quitar favorita' if self.gestion.es_favorita(f) else 'Marcar favorita')
        self.origen.setText('Frase propia' if propia else 'Compartida · solo lectura')

    def nueva(self):
        self._ocultar_confirmaciones_editor()
        self.mostrar_pagina('frases', 'favoritas' if self.favoritas else 'frases')
        self.seleccion = None
        self.lista.clearSelection()
        for campo in [self.titulo, self.abreviatura]:
            campo.setReadOnly(False)
            campo.clear()
        self.contenido.setReadOnly(False)
        self.contenido.clear()
        self.categoria.setEnabled(True)
        self.categoria.setCurrentIndex(0)
        self.guardar.setEnabled(True)
        self.eliminar.setEnabled(False)
        self.favorita.setEnabled(False)
        self.origen.setText('Nueva frase propia')
        self.titulo.setFocus()

    def previsualizar(self):
        texto = self.contenido.toPlainText()
        valores = {'nombre': 'Carolina', 'pedido': '1024', 'fecha': '15/10/2026'}
        self.preview.setPlainText(sustituir(texto, valores))

    def insertar_variable(self, nombre):
        if self.contenido.isReadOnly():
            return
        existentes = set(detectar(self.contenido.toPlainText()))
        if nombre in existentes:
            n = 2
            while f'{nombre}_{n}' in existentes:
                n += 1
            self._var_pendiente = (nombre, f'{nombre}_{n}')
            self._txt_var_repetida.setText(f'La variable {{{nombre}}} ya está en la frase. ¿Reutilizar el mismo valor o crear {{{nombre}_{n}}}?')
            self._btn_var_otra.setText(f'Otro valor ({{{nombre}_{n}}})')
            self.barra_var_repetida.show()
            return
        self.contenido.insertPlainText('{' + nombre + '}')
        self.contenido.setFocus()

    def _resolver_var_repetida(self, distinta):
        if not self._var_pendiente:
            return
        original, alternativa = self._var_pendiente
        elegida = alternativa if distinta else original
        self._ocultar_confirmaciones_editor()
        self.contenido.insertPlainText('{' + elegida + '}')
        self.contenido.setFocus()

    def operar(self, accion):
        try:
            accion()
        except (ValueError, PermissionError, LookupError) as error:
            self.mostrar_aviso(str(error), 'aviso')
            return
        self.ocultar_aviso()
        self.refrescar()
        self.frases_cambiaron()

    def guardar_frase(self):
        def guardar():
            argumentos = (self.titulo.text(), self.abreviatura.text(), self.contenido.toPlainText(), self.categoria.currentData())
            if self.seleccion:
                self.gestion.editar(self.seleccion['id'], *argumentos)
            else:
                self.seleccion = self.gestion.repo.obtener_frase(self.gestion.crear(*argumentos))
        self.operar(guardar)

    def alternar(self):
        if self.seleccion:
            self.operar(lambda: self.gestion.alternar_favorita(self.seleccion['id']))

    def duplicar(self):
        if self.seleccion:
            def dup():
                self.seleccion = self.gestion.repo.obtener_frase(self.gestion.duplicar(self.seleccion['id']))
            self.operar(dup)

    def eliminar_frase(self):
        if not self.seleccion:
            return
        self._txt_eliminar.setText(f'¿Eliminar la frase «{self.seleccion["titulo"]}»? Puede deshacerlo durante esta sesión.')
        self.confirmar_eliminacion.show()

    def _confirmar_eliminar_frase(self):
        if not self.seleccion:
            return
        ident = self.seleccion['id']
        self._ocultar_confirmaciones_editor()
        self.operar(lambda: self.gestion.eliminar(ident))

    def deshacer_frase(self):
        self.operar(self.gestion.deshacer_eliminacion)

    def _iniciar_copia(self, texto, titulo='', origen='frases'):
        if not texto.strip():
            return
        nombres = detectar(texto)
        if nombres:
            self._origen_variables = origen
            self.panel_variables.cargar(texto, titulo)
            self.mostrar_pagina('variables', 'ia' if origen == 'ia' else ('favoritas' if self.favoritas else 'frases'))
            return
        QApplication.clipboard().setText(sustituir(texto, {}))
        self.estado.setText('Respuesta copiada. Revísela antes de pegarla en la conversación.')
        self.mostrar_aviso('Respuesta copiada al portapapeles. Revísela antes de pegarla.', 'ok')

    def copiar(self):
        self._iniciar_copia(self.contenido.toPlainText(), self.titulo.text(), origen='frases')

    def _variables_copiadas(self, _texto):
        self.estado.setText('Respuesta copiada. Revísela antes de pegarla.')
        self.mostrar_aviso('Respuesta copiada al portapapeles. Revísela antes de pegarla.', 'ok')
        self._volver_de_variables()

    def _volver_de_variables(self):
        if self._origen_variables == 'ia' and 'ia' in self._paginas:
            self.mostrar_pagina('ia')
        else:
            self.mostrar_pagina('frases', 'favoritas' if self.favoritas else 'frases')

    def mostrar_id(self, ident):
        for i in range(self.lista.count()):
            if self.lista.item(i).data(Qt.UserRole)['id'] == ident:
                self.lista.setCurrentRow(i)
                return

    def frases_cambiaron(self):
        if self.al_cambiar:
            self.al_cambiar()

    def _actualizar_biblioteca(self):
        self.categorias()
        self.refrescar()
        self.frases_cambiaron()

    def _elegir_desde_ia(self, ident):
        self.cambiar_vista(False)
        self.mostrar_id(ident)
        self.mostrar_aviso('Frase seleccionada en el editor.', 'info')

    def abrir_ia(self):
        if not self.sesion or self.sesion.token == 'offline' or self.panel_ia is None:
            self.mostrar_aviso('Inicie sesión con conexión para usar el Asistente IA.', 'aviso')
            return
        self.ocultar_aviso()
        self.mostrar_pagina('ia')

    def abrir_empresa(self):
        if self.panel_empresa is None:
            self.mostrar_aviso('Solo los administradores conectados pueden editar el perfil de empresa.', 'aviso')
            return
        self.ocultar_aviso()
        self.mostrar_pagina('empresa', 'ia')
        self.panel_empresa.activar()

    def ajustes(self):
        if self.panel_ajustes is None:
            return
        self.ocultar_aviso()
        self.panel_ajustes.cargar()
        self.mostrar_pagina('configuracion')

    def _ajustes_guardados(self, cambios):
        if getattr(cambios, 'tema', None) and cambios.tema != self.tema_actual:
            self.aplicar_tema(cambios.tema)
        if self.al_configurar:
            self.al_configurar(cambios)
        self.estado.setText('Ajustes guardados y aplicados.')

    def sincronizar(self):
        if self.al_sincronizar:
            self.al_sincronizar()

    def importar_excel(self):
        if self.panel_importar is None:
            return
        self.ocultar_aviso()
        self.mostrar_pagina('importar')

    def _despues_de_importar(self):
        self.categorias()
        self.refrescar()
        self.frases_cambiaron()

    def categorias_admin(self):
        if self.panel_categorias is None:
            return
        self.ocultar_aviso()
        self.panel_categorias.recargar()
        self.mostrar_pagina('categorias')

    def publicar(self, eliminar=False):
        if self.panel_catalogo is None or not self.sesion or self.sesion.token == 'offline':
            return
        self.ocultar_aviso()
        self.mostrar_pagina('publicar', 'retirar' if eliminar else 'publicar')
        self.panel_catalogo.abrir(eliminar=eliminar, frase_seleccionada=self.seleccion)

    def _catalogo_publicado(self, version):
        self.estado.setText(f'Publicado: versión {version}')
        self.sincronizar()

    def abrir_usuarios(self):
        if self.panel_usuarios is None:
            return
        self.ocultar_aviso()
        self.mostrar_pagina('usuarios')

    def tiene_operacion_en_curso(self):
        return bool(
            self.trabajos.pendientes
            or (self.panel_ia and self.panel_ia.ocupada)
            or (self.panel_empresa and self.panel_empresa.ocupada)
            or (self.panel_catalogo and self.panel_catalogo.ocupada)
        )

    def cerrar_sesion(self):
        if self.tiene_operacion_en_curso():
            self.mostrar_aviso('Espere a que termine la operación en curso antes de cerrar sesión.', 'aviso')
            return
        self.solicito_cerrar_sesion = True
        self._cerrando = True
        self.close()

    def closeEvent(self, event):
        if self.tiene_operacion_en_curso():
            self.mostrar_aviso('Espere a que termine la operación en curso antes de salir.', 'aviso')
            event.ignore()
            return
        if self._controlador_vivo_demo is not None:
            self._controlador_vivo_demo.detener()
            self._controlador_vivo_demo = None
        if self.al_salir:
            self.al_salir()
        self.trabajos.detener()
        event.accept()
