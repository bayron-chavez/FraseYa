"""Formulario de RF-03: un campo por variable, en el orden en que aparecen en la frase."""
import customtkinter as ctk
import re

from fraseya.aplicacion.resolver_variables import faltantes


class FormularioVariables(ctk.CTkToplevel):
    """Ventana modal. Tras cerrarse, `resultado` es {nombre: valor} o None si se canceló."""

    def __init__(self, parent, nombres, iniciales=None, titulo='Completar campos', contenido=None):
        super().__init__(parent)
        self.nombres = list(nombres)
        self.resultado = None
        self.title(titulo)
        self.resizable(False, False)
        self.columnconfigure(0, weight=1)
        iniciales = iniciales or {}
        self.entradas = {}
        self.contenido = contenido
        self._variable_activa = self.nombres[0] if self.nombres else None
        desplazamiento = 0
        if contenido is not None:
            ctk.CTkLabel(self, text='Así quedará tu frase', anchor='w').grid(
                row=0, column=0, sticky='ew', padx=20, pady=(14, 4))
            self.vista_previa = ctk.CTkTextbox(self, width=480, height=140, wrap='word')
            self.vista_previa.grid(row=1, column=0, sticky='ew', padx=20)
            self.vista_previa.tag_config('campo', foreground='#1D4ED8')
            self.vista_previa.tag_config('activo', background='#DBEAFE', foreground='#1E3A8A')
            ctk.CTkLabel(self, text='El campo seleccionado se resalta en la frase.',
                         anchor='w').grid(row=2, column=0, sticky='ew', padx=20, pady=(4, 0))
            desplazamiento = 3
        for fila, nombre in enumerate(self.nombres):
            ctk.CTkLabel(self, text=nombre.replace('_', ' ').capitalize(), anchor='w').grid(
                row=desplazamiento + fila * 2, column=0, sticky='ew', padx=20, pady=(14 if fila == 0 else 6, 0))
            entrada = ctk.CTkEntry(self, width=320)
            entrada.grid(row=desplazamiento + fila * 2 + 1, column=0, sticky='ew', padx=20)
            if nombre in iniciales:
                entrada.insert(0, iniciales[nombre])
            entrada.bind('<Return>', lambda _e: self.aceptar())
            self.entradas[nombre] = entrada
            entrada.configure(textvariable=ctk.StringVar(value=entrada.get()))
            entrada.cget('textvariable').trace_add('write', lambda *_: self._actualizar_vista())
            entrada.bind('<FocusIn>', lambda _e, n=nombre: self._resaltar_variable(n))
        self.mensaje = ctk.CTkLabel(self, text='', anchor='w', text_color='#B91C1C',
                                    wraplength=320, justify='left')
        self.mensaje.grid(row=desplazamiento + len(self.nombres) * 2, column=0, sticky='ew', padx=20, pady=(8, 0))
        botones = ctk.CTkFrame(self, fg_color='transparent')
        botones.grid(row=desplazamiento + len(self.nombres) * 2 + 1, column=0, sticky='e', padx=20, pady=14)
        ctk.CTkButton(botones, text='Cancelar', width=90, fg_color='#4B5563',
                      hover_color='#374151', command=self.cancelar).pack(side='left', padx=(0, 8))
        ctk.CTkButton(botones, text='Insertar', width=90, command=self.aceptar).pack(side='left')
        self.bind('<Escape>', lambda _e: self.cancelar())
        self.protocol('WM_DELETE_WINDOW', self.cancelar)
        primera = self.entradas[self.nombres[0]]
        self.after(150, lambda: self._mostrar(primera))
        self._actualizar_vista()

    def _resaltar_variable(self, nombre):
        self._variable_activa = nombre
        self._actualizar_vista()

    def _actualizar_vista(self):
        if self.contenido is None:
            return
        valores = self.valores()
        vista = self.vista_previa
        vista.configure(state='normal')
        vista.delete('1.0', 'end')
        cursor = 0
        primer_activo = None
        for marcador in re.finditer(r'\{(\w+)\}', self.contenido):
            vista.insert('end', self.contenido[cursor:marcador.start()])
            nombre = marcador.group(1)
            valor = valores.get(nombre, '').strip()
            texto = valor or '[' + nombre.replace('_', ' ').capitalize() + ']'
            inicio = vista.index('end-1c')
            vista.insert('end', texto)
            fin = vista.index('end-1c')
            vista.tag_add('campo', inicio, fin)
            if nombre == self._variable_activa:
                vista.tag_add('activo', inicio, fin)
                primer_activo = primer_activo or inicio
            cursor = marcador.end()
        vista.insert('end', self.contenido[cursor:])
        if primer_activo:
            vista.see(primer_activo)
        vista.configure(state='disabled')

    def _mostrar(self, primera):
        if not self.winfo_exists():
            return
        self.attributes('-topmost', True)
        self.lift()
        primera.focus_force()
        try:
            self.grab_set()
        except Exception:  # la ventana aún no es visible; el foco ya está puesto
            pass

    def valores(self):
        return {n: e.get() for n, e in self.entradas.items()}

    def aceptar(self):
        valores = self.valores()
        pendientes = faltantes(self.nombres, valores)
        if pendientes:
            self.mensaje.configure(text='\n'.join(f'• Falta completar: {n}' for n in pendientes))
            self.entradas[pendientes[0]].focus_set()
            return
        self.resultado = {n: v.strip() for n, v in valores.items()}
        self.destroy()

    def cancelar(self):
        self.resultado = None
        self.destroy()


def pedir_valores(nombres, iniciales=None, parent=None, contenido=None):
    """Abre el formulario y espera. Devuelve {nombre: valor} o None si se cancela."""
    raiz = None
    if parent is None:
        raiz = parent = ctk.CTk()
        raiz.withdraw()
    try:
        formulario = FormularioVariables(parent, nombres, iniciales, contenido=contenido)
        parent.wait_window(formulario)
        return formulario.resultado
    finally:
        if raiz is not None:
            raiz.destroy()
