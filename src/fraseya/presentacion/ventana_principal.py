"""Ventana principal (RF-04): lista de frases y editor de frases propias.

Las frases compartidas se muestran en solo lectura; para modificarlas se
duplican. La lista usa ttk.Treeview (rápido con catálogos grandes) dentro de
widgets de CustomTkinter.
"""
import re
from tkinter import messagebox, ttk
import tkinter as tk

import customtkinter as ctk

from fraseya.aplicacion.gestion_frases import ErroresValidacion, GestionFrases

TODAS = 'Todas las categorías'
COLOR_BLOQUEADO = '#B6BCC4'
_MARCADOR = re.compile(r'\{(\w+)\}')


class VentanaPrincipal(ctk.CTk):
    def __init__(self, gestion: GestionFrases):
        ctk.set_appearance_mode('light')
        super().__init__()
        self.gestion = gestion
        self._colores_boton = {}
        self.seleccion = None  # frase mostrada en el editor; None = frase nueva
        self.title('FraseYa')
        self.geometry('980x600')
        self.minsize(820, 500)
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(1, weight=1)
        self._construir_barra()
        self._construir_lista()
        self._construir_editor()
        self.refrescar()
        self.nueva()

    # ---- construcción -------------------------------------------------
    def _construir_barra(self):
        barra = ctk.CTkFrame(self, fg_color='transparent')
        barra.grid(row=0, column=0, columnspan=2, sticky='ew', padx=16, pady=(14, 8))
        barra.grid_columnconfigure(0, weight=1)
        self.busqueda = ctk.CTkEntry(barra, height=34,
                                     placeholder_text='Buscar por título, abreviatura, categoría o contenido…')
        self.busqueda.grid(row=0, column=0, sticky='ew')
        self.busqueda.bind('<KeyRelease>', lambda _: self.refrescar())
        self.filtro = ctk.CTkOptionMenu(barra, values=[TODAS], width=190, height=34,
                                        command=lambda _: self.refrescar())
        self.filtro.grid(row=0, column=1, padx=8)
        ctk.CTkButton(barra, text='+ Nueva frase', height=34, command=self.nueva).grid(row=0, column=2)

    def _construir_lista(self):
        marco = ctk.CTkFrame(self)
        marco.grid(row=1, column=0, sticky='nsew', padx=(16, 8), pady=(0, 16))
        marco.grid_rowconfigure(0, weight=1)
        marco.grid_columnconfigure(0, weight=1)
        estilo = ttk.Style(self)
        estilo.theme_use('clam')
        estilo.configure('Treeview', rowheight=28, font=('Segoe UI', 10), borderwidth=0,
                         background='#FFFFFF', fieldbackground='#FFFFFF')
        estilo.configure('Treeview.Heading', font=('Segoe UI', 10, 'bold'))
        estilo.map('Treeview', background=[('selected', '#1F6AA5')], foreground=[('selected', 'white')])
        self.tabla = ttk.Treeview(marco, columns=('abrev', 'titulo', 'categoria', 'origen'),
                                  show='headings', selectmode='browse')
        for col, texto, ancho in (('abrev', 'Abreviatura', 100), ('titulo', 'Título', 190),
                                  ('categoria', 'Categoría', 110), ('origen', 'Origen', 80)):
            self.tabla.heading(col, text=texto)
            self.tabla.column(col, width=ancho, anchor='w')
        self.tabla.tag_configure('compartida', foreground='#5B6770')
        barra = ttk.Scrollbar(marco, orient='vertical', command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=barra.set)
        self.tabla.grid(row=0, column=0, sticky='nsew', padx=(6, 0), pady=6)
        barra.grid(row=0, column=1, sticky='ns', pady=6)
        self.tabla.bind('<<TreeviewSelect>>', self._al_seleccionar)
        self.contador = ctk.CTkLabel(marco, text='', anchor='w', text_color='#5B6770')
        self.contador.grid(row=1, column=0, columnspan=2, sticky='ew', padx=12, pady=(0, 8))

    def _construir_editor(self):
        panel = ctk.CTkFrame(self)
        panel.grid(row=1, column=1, sticky='nsew', padx=(8, 16), pady=(0, 16))
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(8, weight=1)
        self.estado = ctk.CTkLabel(panel, text='', font=ctk.CTkFont(size=15, weight='bold'), anchor='w')
        self.estado.grid(row=0, column=0, sticky='ew', padx=16, pady=(14, 6))
        self.titulo = self._campo(panel, 1, 'Título')
        self.abreviatura = self._campo(panel, 2, 'Abreviatura (sin espacios)')
        ctk.CTkLabel(panel, text='Categoría', anchor='w').grid(row=5, column=0, sticky='ew', padx=16)
        self.categoria = ctk.CTkOptionMenu(panel, values=['General'])
        self.categoria.grid(row=6, column=0, sticky='ew', padx=16, pady=(0, 8))
        ctk.CTkLabel(panel, text='Contenido', anchor='w').grid(row=7, column=0, sticky='ew', padx=16)
        self.contenido = ctk.CTkTextbox(panel, height=120, wrap='word')
        self.contenido.grid(row=8, column=0, sticky='nsew', padx=16, pady=(0, 4))
        self.contenido.bind('<KeyRelease>', lambda _: self._mostrar_variables())
        self.variables = ctk.CTkLabel(panel, text='', anchor='w', text_color='#5B6770')
        self.variables.grid(row=9, column=0, sticky='ew', padx=16)
        botones = ctk.CTkFrame(panel, fg_color='transparent')
        botones.grid(row=10, column=0, sticky='ew', padx=16, pady=(8, 4))
        self.btn_guardar = ctk.CTkButton(botones, text='Guardar', width=90, command=self.guardar)
        self.btn_duplicar = ctk.CTkButton(botones, text='Duplicar', width=90, fg_color='#4B5563',
                                          hover_color='#374151', command=self.duplicar)
        self.btn_eliminar = ctk.CTkButton(botones, text='Eliminar', width=90, fg_color='#B91C1C',
                                          hover_color='#991B1B', command=self.eliminar)
        for b in (self.btn_guardar, self.btn_duplicar, self.btn_eliminar):
            b.pack(side='left', padx=(0, 8))
            self._colores_boton[b] = (b.cget('fg_color'), b.cget('hover_color'), b.cget('text_color'))
        self.mensaje = ctk.CTkLabel(panel, text='', anchor='w', wraplength=300, justify='left')
        self.mensaje.grid(row=11, column=0, sticky='ew', padx=16, pady=(0, 12))

    @staticmethod
    def _campo(panel, fila, etiqueta):
        ctk.CTkLabel(panel, text=etiqueta, anchor='w').grid(row=fila * 2 - 1, column=0, sticky='ew', padx=16)
        entrada = ctk.CTkEntry(panel)
        entrada.grid(row=fila * 2, column=0, sticky='ew', padx=16, pady=(0, 8))
        return entrada

    # ---- datos ---------------------------------------------------------
    def refrescar(self, seleccionar=None):
        propias = self.gestion.categorias_propias()
        todas = self.gestion.repo.listar_categorias()
        self._categorias_filtro = {c['nombre']: c['id'] for c in todas}
        self.filtro.configure(values=[TODAS, *sorted(self._categorias_filtro)])
        self._categorias_propias = {c['nombre']: c['id'] for c in propias}
        self.categoria.configure(values=list(self._categorias_propias))
        nombre = self.filtro.get()
        cat_id = self._categorias_filtro.get(nombre) if nombre != TODAS else None
        self.tabla.delete(*self.tabla.get_children())
        texto = self.busqueda.get()
        visibles = self.gestion.listar(texto, cat_id)
        for f in visibles:
            self.tabla.insert('', 'end', iid=str(f['id']), tags=(f['origen'],),
                              values=(f['abreviatura'], f['titulo'], f['categoria'], f['origen'].capitalize()))
        total = self.gestion.listar() if (texto.strip() or cat_id is not None) else visibles
        self.contador.configure(text=self._texto_contador(len(visibles), total))
        if seleccionar is not None and self.tabla.exists(str(seleccionar)):
            self.tabla.selection_set(str(seleccionar))

    @staticmethod
    def _texto_contador(mostradas, total):
        def frases(n):
            return f'{n} frase' if n == 1 else f'{n} frases'
        if mostradas != len(total):
            return f'Mostrando {mostradas} de {frases(len(total))}'
        propias = sum(1 for f in total if f['origen'] == 'propia')
        return f'{frases(len(total))} · {propias} propias · {len(total) - propias} compartidas'

    def _al_seleccionar(self, _evento):
        sel = self.tabla.selection()
        if sel:
            self.mostrar(self.gestion.repo.obtener_frase(int(sel[0])))

    # ---- editor --------------------------------------------------------
    def _poner(self, entrada, texto):
        entrada.configure(state='normal')
        entrada.delete(0, 'end')
        entrada.insert(0, texto)

    def _modo_edicion(self, editable):
        estado = 'normal' if editable else 'disabled'
        for w in (self.titulo, self.abreviatura, self.contenido):
            w.configure(state=estado)
        self.categoria.configure(state=estado)
        self._activar(self.btn_guardar, editable)
        self._activar(self.btn_eliminar, editable)

    def _activar(self, boton, activo):
        """Un botón bloqueado se ve gris; al activarlo recupera su color."""
        if activo:
            fondo, hover, texto = self._colores_boton[boton]
            boton.configure(state='normal', fg_color=fondo, hover_color=hover, text_color=texto)
        else:
            boton.configure(state='disabled', fg_color=COLOR_BLOQUEADO, hover_color=COLOR_BLOQUEADO,
                            text_color_disabled='#F3F4F6')

    def _limpiar_editor(self):
        self._modo_edicion(True)
        self.titulo.delete(0, 'end')
        self.abreviatura.delete(0, 'end')
        self.contenido.delete('1.0', 'end')

    def nueva(self):
        self.seleccion = None
        self.tabla.selection_remove(*self.tabla.selection())
        self._limpiar_editor()
        self.categoria.configure(values=list(self._categorias_propias))
        self.categoria.set(next(iter(self._categorias_propias)))
        self.estado.configure(text='Nueva frase')
        self._activar(self.btn_duplicar, False)
        self._activar(self.btn_eliminar, False)
        self._avisar('')
        self._mostrar_variables()
        self.titulo.focus()

    def mostrar(self, frase):
        self.seleccion = frase
        propia = frase['origen'] == 'propia'
        self._limpiar_editor()
        self.titulo.insert(0, frase['titulo'])
        self.abreviatura.insert(0, frase['abreviatura'])
        self.contenido.insert('1.0', frase['contenido'])
        nombre = next((n for n, i in self._categorias_filtro.items() if i == frase['categoria_id']), '')
        self.categoria.configure(values=list(self._categorias_propias) if propia else [nombre])
        self.categoria.set(nombre)
        self._mostrar_variables()
        self.estado.configure(text='Frase propia' if propia else 'Frase compartida (solo lectura)')
        self._modo_edicion(propia)
        self._activar(self.btn_duplicar, True)
        self._avisar('')

    def _mostrar_variables(self):
        nombres = list(dict.fromkeys(_MARCADOR.findall(self.contenido.get('1.0', 'end'))))
        self.variables.configure(text='Campos variables: ' + ', '.join(f'{{{n}}}' for n in nombres)
                                 if nombres else 'Sin campos variables. Usa {nombre}, {monto}, {fecha}…')

    def _avisar(self, texto, error=False):
        self.mensaje.configure(text=texto, text_color='#B91C1C' if error else '#15803D')

    def _datos(self):
        return (self.titulo.get(), self.abreviatura.get(), self.contenido.get('1.0', 'end').strip(),
                self._categorias_propias[self.categoria.get()])

    def _ejecutar(self, accion):
        """Devuelve (éxito, resultado); un error de validación se muestra en la ventana."""
        try:
            return True, accion()
        except ErroresValidacion as error:
            self._avisar('\n'.join(f'• {e}' for e in error.errores), error=True)
            return False, None
        except (ValueError, PermissionError, LookupError) as error:
            self._avisar(str(error), error=True)
            return False, None

    def guardar(self):
        titulo, abrev, contenido, cat = self._datos()
        if self.seleccion is None:
            ok, ident = self._ejecutar(lambda: self.gestion.crear(titulo, abrev, contenido, cat))
            mensaje = 'Frase creada.'
        else:
            ident = self.seleccion['id']
            ok, _ = self._ejecutar(lambda: self.gestion.editar(ident, titulo, abrev, contenido, cat))
            mensaje = 'Cambios guardados.'
        if ok:
            self.refrescar(seleccionar=ident)
            self.mostrar(self.gestion.repo.obtener_frase(ident))
            self._avisar(mensaje)

    def duplicar(self):
        if self.seleccion is None:
            return
        ok, ident = self._ejecutar(lambda: self.gestion.duplicar(self.seleccion['id']))
        if ok:
            self.refrescar(seleccionar=ident)
            self.mostrar(self.gestion.repo.obtener_frase(ident))
            self._avisar('Copia creada. Ya puedes editarla.')

    def eliminar(self):
        if self.seleccion is None:
            return
        if not messagebox.askyesno('Eliminar frase', f'¿Eliminar «{self.seleccion["titulo"]}»?', parent=self):
            return
        ok, _ = self._ejecutar(lambda: self.gestion.eliminar(self.seleccion['id']))
        if ok:
            self.refrescar()
            self.nueva()
            self._avisar('Frase eliminada.')


def abrir(ruta=None):
    """Abre la ventana principal sobre la base de datos local."""
    from fraseya.infraestructura import RepositorioSQLite
    with RepositorioSQLite(ruta) as repo:
        VentanaPrincipal(GestionFrases(repo)).mainloop()
