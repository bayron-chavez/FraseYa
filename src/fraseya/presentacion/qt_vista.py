"""Interfaz nativa Qt unificada: todas las secciones viven dentro de la misma ventana."""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QKeySequence, QShortcut, QFontDatabase
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QTextEdit, QComboBox, QListWidget, QListWidgetItem,
    QFrame, QScrollArea, QLayout, QStackedWidget,
)
from fraseya.aplicacion.buscador import buscar as buscar_frases
from fraseya.aplicacion.configuracion import Configuracion, TEMA_PREDETERMINADO
from fraseya.aplicacion.resolver_variables import detectar, sustituir
from fraseya.dominio.reglas import VARIABLES_OFICIALES
from . import qt_desplegables, qt_lateral
from .identidad import recurso
from .qt_frases import (
    ColumnaFiltros, DelegadoFrase, barra_acciones, estado_editor, marcar_favorita, poner_icono,
)
from .qt_paneles import (
    boton, EtiquetaSegura, EtiquetaSegura as QLabel, Trabajos,
    PanelIA, PanelEmpresa, PanelAjustes, PanelImportar, PanelCategorias,
    PanelCatalogo, PanelVariables,
)
from .qt_temas import ESTILO, ESTILO_OSCURO, hoja_estilo, paleta


class VentanaQt(QMainWindow):
    def __init__(self, gestion, demostracion=False, autenticacion=None, sesion=None):
        super().__init__()
        qt_desplegables.activar()
        fuente = Path('C:/Windows/Fonts/segoeui.ttf')
        if fuente.exists():
            QFontDatabase.addApplicationFont(str(fuente))
        self.gestion = gestion
        self.demostracion = demostracion
        self.seleccion = None
        self.autenticacion, self.sesion = autenticacion, sesion
        self.al_cambiar = None
        self.al_configurar = None
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
        self.tema_actual = TEMA_PREDETERMINADO

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
        lateral.setObjectName('lateral')
        lateral.setFixedWidth(qt_lateral.ANCHO - 2)
        nav = QVBoxLayout(lateral)
        nav.setContentsMargins(14, 18, 14, 14)
        nav.setSpacing(2)
        nav.addLayout(qt_lateral.marca())
        nav.addSpacing(10)

        def grupo(texto):
            nav.addSpacing(14)
            nav.addWidget(qt_lateral.etiqueta(texto, 'lateral_grupo'))

        grupo('BIBLIOTECA')
        self.nav_frases = self._agregar_nav(nav, 'frases', 'Mis frases', lambda: self.cambiar_vista(False))
        self.nav_favoritas = self._agregar_nav(nav, 'favoritas', 'Favoritas', lambda: self.cambiar_vista(True))

        if not demostracion:
            grupo('HERRAMIENTAS')
            self.nav_ia = self._agregar_nav(nav, 'ia', 'Asistente IA', self.abrir_ia)
            self.nav_ia.setEnabled(online)
            self.nav_importar = self._agregar_nav(nav, 'importar', 'Importar Excel', self.importar_excel)

            if es_admin:
                grupo('ADMINISTRACIÓN')
                self.nav_catalogo = self._agregar_nav(nav, 'publicar', 'Catálogo compartido', lambda: self.publicar(False))
                self.nav_categorias = self._agregar_nav(nav, 'categorias', 'Categorías', self.categorias_admin)

        nav.addStretch()
        if demostracion:
            nav.addWidget(qt_lateral.etiqueta('Demostración · datos temporales', 'lateral_tenue'))
        else:
            self.nav_configuracion = self._agregar_nav(nav, 'configuracion', 'Configuración', self.ajustes)
            self.sincronizacion = qt_lateral.TarjetaSync(self.sincronizar)
            nav.addSpacing(6)
            nav.addWidget(self.sincronizacion)
            if sesion:
                nav.addSpacing(8)
                nav.addWidget(qt_lateral.separador())
                nav.addSpacing(8)
                nav.addLayout(qt_lateral.perfil(sesion.usuario, sesion.rol, self.cerrar_sesion))

        desplazamiento = QScrollArea()
        desplazamiento.setWidgetResizable(True)
        desplazamiento.setFrameShape(QFrame.NoFrame)
        desplazamiento.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        desplazamiento.setFixedWidth(qt_lateral.ANCHO)
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


        QShortcut(QKeySequence('Ctrl+K'), self, activated=self._enfocar_busqueda)
        qss = hoja_estilo(self.tema_actual)
        QApplication.instance().setStyleSheet(qss)
        self.setStyleSheet(qss)
        self.categorias()
        self.cambiar_vista(False)

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
        b = boton('  ' + texto, accion)
        b.setObjectName('nav')
        qt_lateral.poner_icono(b, clave)
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
        pagina.setObjectName('pagina_frases')
        cuerpo = QVBoxLayout(pagina)
        cuerpo.setContentsMargins(0, 0, 0, 0)
        cuerpo.setSpacing(14)

        cabecera = QHBoxLayout()
        titulos = QVBoxLayout()
        titulos.setSpacing(2)
        self.encabezado = QLabel('Mis frases')
        self.encabezado.setObjectName('heading')
        titulos.addWidget(self.encabezado)
        subtitulo = QLabel('Organiza y edita tu biblioteca')
        subtitulo.setObjectName('muted')
        titulos.addWidget(subtitulo)
        cabecera.addLayout(titulos)
        cabecera.addStretch()
        cabecera.addWidget(boton('+  Nueva frase', self.nueva, True))
        cuerpo.addLayout(cabecera)

        columnas = QHBoxLayout()
        columnas.setSpacing(12)

        # Estado de los filtros; se manejan desde la columna de la izquierda.
        self.filtro = QComboBox(pagina)
        self.filtro.addItems(['Todas', 'Propias', 'Compartidas'])
        self.filtro.currentIndexChanged.connect(self.refrescar)
        self.filtro.hide()
        self.filtro_categoria = QComboBox(pagina)
        self.filtro_categoria.addItem('Todas las categorías')
        self.filtro_categoria.currentIndexChanged.connect(self.refrescar)
        self.filtro_categoria.hide()
        self.columna_filtros = ColumnaFiltros(self._filtrar_categoria, self._filtrar_origen)
        columnas.addWidget(self.columna_filtros)

        biblioteca = QFrame()
        biblioteca.setObjectName('panel')
        biblioteca.setMinimumWidth(260)
        biblioteca.setMaximumWidth(380)
        lista_layout = QVBoxLayout(biblioteca)
        lista_layout.setContentsMargins(1, 12, 1, 8)
        buscador_layout = QHBoxLayout()
        buscador_layout.setContentsMargins(11, 0, 11, 4)
        self.busqueda = QLineEdit()
        self.busqueda.setPlaceholderText('Buscar…  (Ctrl+K)')
        self.busqueda.setToolTip('Buscar por título, contenido o abreviatura')
        self.busqueda.textChanged.connect(self.refrescar)
        buscador_layout.addWidget(self.busqueda)
        lista_layout.addLayout(buscador_layout)
        self.lista = QListWidget()
        self.lista.setItemDelegate(DelegadoFrase(self.lista))
        self.lista.setMouseTracking(True)
        self.lista.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.lista.currentItemChanged.connect(self.seleccionar)
        lista_layout.addWidget(self.lista)
        columnas.addWidget(biblioteca, 2)

        editor = QFrame()
        editor.setObjectName('panel')
        campos = QVBoxLayout(editor)
        campos.setContentsMargins(22, 16, 22, 16)
        campos.setSpacing(6)
        superior = QHBoxLayout()
        superior.setSpacing(10)
        self.titulo_editor = QLabel('Editar frase')
        self.titulo_editor.setObjectName('titulo_editor')
        # Estado bajo el título: en una sola fila los botones se cortan.
        encabezado_editor = QVBoxLayout()
        encabezado_editor.setSpacing(3)
        encabezado_editor.addWidget(self.titulo_editor)
        self.origen = QLabel('')
        self.origen.setFixedHeight(22)
        estado_editor(self.origen, 'Propia', 'propia')
        encabezado_editor.addWidget(self.origen, 0, Qt.AlignLeft)
        superior.addLayout(encabezado_editor)
        superior.addStretch()
        self.favorita = boton('', self.alternar)
        marcar_favorita(self.favorita, False)
        self.btn_duplicar = boton(' Duplicar', self.duplicar)
        poner_icono(self.btn_duplicar, 'duplicar')
        self.eliminar = boton(' Eliminar', self.eliminar_frase)
        poner_icono(self.eliminar, 'borrar', '#dc2626')
        superior.addWidget(barra_acciones([self.favorita, self.btn_duplicar, self.eliminar]))
        campos.addLayout(superior)
        separador = QFrame()
        separador.setObjectName('separador_editor')
        separador.setFixedHeight(1)
        campos.addSpacing(6)
        campos.addWidget(separador)
        campos.addSpacing(4)

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
        fila.addLayout(abre, 1)
        fila.addLayout(cate, 1)
        campos.addLayout(fila)

        campos.addWidget(QLabel('Contenido'))
        self.contenido = QTextEdit()
        self.contenido.setMinimumHeight(100)
        self.contenido.setAcceptRichText(False)
        self.contenido.textChanged.connect(self.previsualizar)
        campos.addWidget(self.contenido, 1)

        variables = QHBoxLayout()
        texto_vars = QLabel('Insertar:')
        texto_vars.setObjectName('muted')
        variables.addWidget(texto_vars)
        for nombre in VARIABLES_OFICIALES[:3]:
            variables.addWidget(boton('{' + nombre + '}', lambda checked=False, n=nombre: self.insertar_variable(n),
                                      estilo='variable'))
        otras = QComboBox()
        otras.addItems(['Otra…', *VARIABLES_OFICIALES[3:]])
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

        # La vista previa solo aparece cuando la frase tiene variables.
        self.texto_preview = QLabel('Vista previa con datos de ejemplo')
        self.texto_preview.setObjectName('muted')
        campos.addWidget(self.texto_preview)
        self.preview = QTextEdit()
        self.preview.setObjectName('preview')
        self.preview.setReadOnly(True)
        self.preview.setFixedHeight(64)
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
        acciones.addWidget(boton('Completar y copiar', self.copiar))
        acciones.addStretch()
        self.deshacer = boton('Deshacer', self.deshacer_frase, estilo='enlace')
        acciones.addWidget(self.deshacer)
        self.guardar = boton('Guardar cambios', self.guardar_frase, True)
        acciones.addWidget(self.guardar)
        campos.addSpacing(6)
        campos.addLayout(acciones)

        campos.setSizeConstraint(QLayout.SetMinimumSize)
        editor_scroll = QScrollArea()
        editor_scroll.setWidgetResizable(True)
        editor_scroll.setFrameShape(QFrame.NoFrame)
        editor_scroll.setMinimumWidth(420)
        editor_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        editor_scroll.setWidget(editor)
        columnas.addWidget(editor_scroll, 3)
        cuerpo.addLayout(columnas, 1)
        return pagina

    def _filtrar_categoria(self, nombre):
        indice = self.filtro_categoria.findText(nombre) if nombre else 0
        if indice == self.filtro_categoria.currentIndex():
            self.refrescar()
        else:
            self.filtro_categoria.setCurrentIndex(max(indice, 0))

    def _filtrar_origen(self, nombre):
        # Pulsar de nuevo el origen activo vuelve a mostrar todos.
        self.filtro.setCurrentText('Todas' if self.filtro.currentText() == nombre else nombre)

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
        visibles = [f for f in frases if not self.favoritas or f.get('favorita')]
        cantidades = {c['nombre']: 0 for c in self.gestion.repo.listar_categorias()}
        for f in visibles:
            nombre = f.get('categoria', 'General')
            cantidades[nombre] = cantidades.get(nombre, 0) + 1
        self.columna_filtros.actualizar(cantidades, len(visibles), categoria_filtro, filtro)
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
        marcar_favorita(self.favorita, self.gestion.es_favorita(f))
        self.btn_duplicar.setEnabled(True)
        self.titulo_editor.setText('Editar frase' if propia else 'Ver frase')
        if propia:
            estado_editor(self.origen, 'Propia', 'propia')
        else:
            estado_editor(self.origen, 'Compartida · solo lectura', 'compartida')

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
        marcar_favorita(self.favorita, False)
        self.btn_duplicar.setEnabled(False)
        self.titulo_editor.setText('Nueva frase')
        estado_editor(self.origen, 'Sin guardar', 'nueva')
        self.titulo.setFocus()

    def previsualizar(self):
        texto = self.contenido.toPlainText()
        valores = {'nombre': 'Carolina', 'pedido': '1024', 'fecha': '15/10/2026'}
        self.preview.setPlainText(sustituir(texto, valores))
        hay_variables = bool(detectar(texto))
        self.texto_preview.setVisible(hay_variables)
        self.preview.setVisible(hay_variables)

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
        self.mostrar_pagina('publicar')
        self.panel_catalogo.abrir(eliminar=eliminar, frase_seleccionada=self.seleccion)

    def _catalogo_publicado(self, version):
        self.estado.setText(f'Publicado: versión {version}')
        self.sincronizar()

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
