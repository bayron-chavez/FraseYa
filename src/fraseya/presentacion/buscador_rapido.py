"""Ventana emergente del buscador rápido (RF-02).

Se crea una sola vez, oculta, y se muestra al pulsar el atajo: así aparece casi
al instante (RNF-02: ≤ 300 ms). Escribe para filtrar, ↑↓ para elegir, Enter para
insertar y Esc para cerrar.
"""
import time
import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

from fraseya.aplicacion.buscador import buscar

ANCHO, ALTO = 580, 430
MARGEN_FOCO_S = 0.5     # al abrir, el foco tarda un instante en llegar: no cerrar por eso


class VentanaBuscador(ctk.CTkToplevel):
    def __init__(self, parent, al_elegir, al_cancelar=None, al_mostrar=None, al_ocultar=None,
                 forzar_primer_plano=None, hwnd_de=None):
        """al_elegir(frase, origen); al_cancelar(origen); forzar_primer_plano(hwnd) y hwnd_de(ventana)
        traen la ventana al frente aunque otra aplicación tenga el foco."""
        super().__init__(parent)
        self._al_elegir = al_elegir
        self._al_cancelar = al_cancelar
        self._al_mostrar = al_mostrar
        self._al_ocultar = al_ocultar
        self._forzar = forzar_primer_plano
        self._hwnd_de = hwnd_de
        self.frases = []
        self.resultados = []
        self.origen = None
        self.visible = False
        self._abierta_en = 0.0
        self.withdraw()
        self.title('Buscar frase')
        self.resizable(False, False)
        self.protocol('WM_DELETE_WINDOW', self.cancelar)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self.texto = tk.StringVar()
        self.texto.trace_add('write', lambda *_: self.refrescar())
        self.entrada = ctk.CTkEntry(self, textvariable=self.texto, height=40, font=ctk.CTkFont(size=15))
        self.entrada.grid(row=0, column=0, sticky='ew', padx=14, pady=(14, 8))

        marco = ctk.CTkFrame(self)
        marco.grid(row=1, column=0, sticky='nsew', padx=14)
        marco.rowconfigure(0, weight=1)
        marco.columnconfigure(0, weight=1)
        self.tabla = ttk.Treeview(marco, columns=('abrev', 'titulo', 'categoria'), show='headings',
                                  selectmode='browse', height=9)
        for col, texto, ancho in (('abrev', 'Abreviatura', 110), ('titulo', 'Título', 280),
                                  ('categoria', 'Categoría', 140)):
            self.tabla.heading(col, text=texto)
            self.tabla.column(col, width=ancho, anchor='w')
        self.tabla.tag_configure('compartida', foreground='#5B6770')
        self.tabla.grid(row=0, column=0, sticky='nsew', padx=4, pady=4)
        self.tabla.bind('<<TreeviewSelect>>', lambda _e: self._mostrar_vista_previa())
        self.tabla.bind('<Double-1>', lambda _e: self.elegir())

        self.vista_previa = ctk.CTkLabel(self, text='', anchor='nw', justify='left', wraplength=ANCHO - 50,
                                         height=44, text_color='#374151')
        self.vista_previa.grid(row=2, column=0, sticky='ew', padx=16, pady=(8, 0))
        ctk.CTkLabel(self, text='↑↓ elegir   ·   Enter insertar   ·   Esc cerrar', anchor='w',
                     text_color='#6B7280').grid(row=3, column=0, sticky='ew', padx=16, pady=(2, 10))

        for widget in (self.entrada, self.tabla):
            widget.bind('<Down>', lambda _e: self._mover(1) or 'break')
            widget.bind('<Up>', lambda _e: self._mover(-1) or 'break')
            widget.bind('<Return>', lambda _e: self.elegir() or 'break')
            widget.bind('<Escape>', lambda _e: self.cancelar() or 'break')
        self.bind('<FocusOut>', lambda _e: self.after(150, self._cerrar_si_perdio_el_foco))

    # ---- mostrar / ocultar -----------------------------------------------
    def mostrar(self, frases, origen):
        """Abre el buscador sobre `origen` (la ventana que tenía el foco)."""
        self.frases = frases
        self.origen = origen
        self.entrada.delete(0, 'end')
        self.refrescar()
        x = (self.winfo_screenwidth() - ANCHO) // 2
        y = max(40, self.winfo_screenheight() // 5)
        self.geometry(f'{ANCHO}x{ALTO}+{x}+{y}')
        self.deiconify()
        self.attributes('-topmost', True)
        self.lift()
        self.update_idletasks()
        if self._forzar and self._hwnd_de:
            self._forzar(self._hwnd_de(self))
        self.entrada.focus_force()
        self._abierta_en = time.monotonic()
        if not self.visible:
            self.visible = True
            if self._al_mostrar:
                self._al_mostrar()

    def ocultar(self):
        if not self.visible:
            return
        self.visible = False
        self.withdraw()
        if self._al_ocultar:
            self._al_ocultar()

    def cancelar(self):
        origen = self.origen
        self.ocultar()
        if self._al_cancelar and origen:
            self._al_cancelar(origen)

    def _cerrar_si_perdio_el_foco(self):
        if (self.visible and time.monotonic() - self._abierta_en > MARGEN_FOCO_S
                and self.focus_displayof() is None):
            self.ocultar()      # hizo clic en otra aplicación: no se le devuelve el foco por la fuerza

    # ---- lista ----------------------------------------------------------
    def refrescar(self):
        self.resultados = buscar(self.frases, self.texto.get())
        self.tabla.delete(*self.tabla.get_children())
        for i, f in enumerate(self.resultados):
            self.tabla.insert('', 'end', iid=str(i), tags=(f.get('origen', ''),),
                              values=(f['abreviatura'], ('★ ' if f.get('favorita') else '') + f['titulo'], f.get('categoria', '')))
        if self.resultados:
            self.tabla.selection_set('0')
            self.tabla.focus('0')
        self._mostrar_vista_previa()

    def _mover(self, paso):
        n = len(self.resultados)
        if not n:
            return
        sel = self.tabla.selection()
        actual = int(sel[0]) if sel else -1
        nuevo = min(n - 1, max(0, actual + paso))
        self.tabla.selection_set(str(nuevo))
        self.tabla.focus(str(nuevo))
        self.tabla.see(str(nuevo))

    def seleccionada(self):
        sel = self.tabla.selection()
        return self.resultados[int(sel[0])] if sel else None

    def _mostrar_vista_previa(self):
        frase = self.seleccionada()
        if frase is None:
            self.vista_previa.configure(text='Sin resultados' if self.texto.get().strip() else '')
            return
        contenido = ' '.join(frase['contenido'].split())
        self.vista_previa.configure(text=contenido if len(contenido) <= 170 else contenido[:167] + '…')

    def elegir(self):
        frase = self.seleccionada()
        if frase is None:
            return
        origen = self.origen
        self.ocultar()
        self._al_elegir(frase, origen)
