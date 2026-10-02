"""Ventana principal Tkinter: lista y gestión de frases (RF-04)."""
import tkinter as tk
from tkinter import messagebox, ttk


class FormularioFrase(tk.Toplevel):
    """Crear o editar: se completa con título, abreviatura y contenido y un clic en Guardar."""

    def __init__(self, master, guardar, frase=None, avisar=messagebox.showerror):
        super().__init__(master)
        self.title('Editar frase' if frase else 'Nueva frase')
        self._guardar, self._avisar = guardar, avisar
        self.columnconfigure(1, weight=1)
        self.rowconfigure(2, weight=1)
        self.titulo = tk.StringVar(value=frase['titulo'] if frase else '')
        self.abreviatura = tk.StringVar(value=frase['abreviatura'] if frase else '')
        ttk.Label(self, text='Título').grid(row=0, column=0, sticky='w', padx=8, pady=4)
        ttk.Entry(self, textvariable=self.titulo).grid(row=0, column=1, sticky='ew', padx=8)
        ttk.Label(self, text='Abreviatura').grid(row=1, column=0, sticky='w', padx=8, pady=4)
        ttk.Entry(self, textvariable=self.abreviatura).grid(row=1, column=1, sticky='ew', padx=8)
        ttk.Label(self, text='Contenido').grid(row=2, column=0, sticky='nw', padx=8, pady=4)
        self.contenido = tk.Text(self, width=50, height=10, wrap='word')
        self.contenido.grid(row=2, column=1, sticky='nsew', padx=8)
        if frase:
            self.contenido.insert('1.0', frase['contenido'])
        ttk.Label(self, text='Use {nombre} para campos variables.', foreground='#64748B').grid(
            row=3, column=1, sticky='w', padx=8)
        ttk.Button(self, text='Guardar', command=self.guardar).grid(row=4, column=1, sticky='e', padx=8, pady=8)

    def guardar(self):
        try:
            self._guardar(self.titulo.get(), self.abreviatura.get(),
                          self.contenido.get('1.0', 'end-1c'))
        except ValueError as error:
            self._avisar('FraseYa', str(error), parent=self)
            return False
        self.destroy()
        return True


class VentanaPrincipal(tk.Tk):
    def __init__(self, gestor, avisar=messagebox.showerror, confirmar=messagebox.askyesno):
        super().__init__()
        self.title('FraseYa')
        self.geometry('720x420')
        self.gestor, self._avisar, self._confirmar = gestor, avisar, confirmar
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        barra = ttk.Frame(self)
        barra.grid(row=0, column=0, sticky='ew', padx=8, pady=8)
        self.botones = {}
        for texto, comando in (('Nueva', self.nueva), ('Editar', self.editar),
                               ('Duplicar', self.duplicar), ('Eliminar', self.eliminar)):
            boton = ttk.Button(barra, text=texto, command=comando)
            boton.pack(side='left', padx=(0, 6))
            self.botones[texto] = boton
        self.tabla = ttk.Treeview(self, columns=('titulo', 'abreviatura', 'origen'),
                                  show='headings', selectmode='browse')
        for col, texto, ancho in (('titulo', 'Título', 320), ('abreviatura', 'Abreviatura', 140),
                                  ('origen', 'Origen', 120)):
            self.tabla.heading(col, text=texto)
            self.tabla.column(col, width=ancho)
        self.tabla.grid(row=1, column=0, sticky='nsew', padx=8, pady=(0, 8))
        self.tabla.bind('<<TreeviewSelect>>', lambda _e: self._actualizar_botones())
        self.refrescar()

    def refrescar(self):
        previa = self.tabla.selection()
        self.tabla.delete(*self.tabla.get_children())
        for f in self.gestor.listar():
            etiqueta = 'Compartida (solo lectura)' if f['origen'] == 'compartida' else 'Propia'
            self.tabla.insert('', 'end', iid=str(f['id']),
                              values=(f['titulo'], f['abreviatura'], etiqueta))
        if previa and self.tabla.exists(previa[0]):
            self.tabla.selection_set(previa[0])
        self._actualizar_botones()

    def _seleccion(self):
        sel = self.tabla.selection()
        return int(sel[0]) if sel else None

    def _es_compartida(self, ident):
        return 'Compartida' in self.tabla.item(str(ident), 'values')[2]

    def _actualizar_botones(self):
        ident = self._seleccion()
        estado = lambda ok: 'normal' if ok else 'disabled'
        self.botones['Duplicar'].config(state=estado(ident is not None))
        propia = ident is not None and not self._es_compartida(ident)
        self.botones['Editar'].config(state=estado(propia))
        self.botones['Eliminar'].config(state=estado(propia))

    def nueva(self):
        def guardar(*datos):
            self.gestor.crear(*datos)
            self.refrescar()
        return FormularioFrase(self, guardar, avisar=self._avisar)

    def editar(self):
        ident = self._seleccion()
        if ident is None or self._es_compartida(ident):
            return None
        frase = self.gestor.repo.obtener_frase(ident)

        def guardar(*datos):
            self.gestor.editar(ident, *datos)
            self.refrescar()
        return FormularioFrase(self, guardar, frase, avisar=self._avisar)

    def duplicar(self):
        ident = self._seleccion()
        if ident is not None:
            nuevo = self.gestor.duplicar(ident)
            self.refrescar()
            self.tabla.selection_set(str(nuevo))

    def eliminar(self):
        ident = self._seleccion()
        if ident is None or self._es_compartida(ident):
            return
        if self._confirmar('FraseYa', '¿Eliminar la frase seleccionada?', parent=self):
            try:
                self.gestor.eliminar(ident)
            except ValueError as error:
                self._avisar('FraseYa', str(error), parent=self)
            self.refrescar()


def abrir(ruta):
    from fraseya.aplicacion.gestor_frases import GestorFrases
    from fraseya.infraestructura import RepositorioSQLite
    with RepositorioSQLite(ruta) as repo:
        VentanaPrincipal(GestorFrases(repo)).mainloop()
