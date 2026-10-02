"""Formulario de RF-03: un campo por variable, en el orden en que aparecen en la frase."""
import customtkinter as ctk

from fraseya.aplicacion.resolver_variables import faltantes


class FormularioVariables(ctk.CTkToplevel):
    """Ventana modal. Tras cerrarse, `resultado` es {nombre: valor} o None si se canceló."""

    def __init__(self, parent, nombres, iniciales=None, titulo='Completar campos'):
        super().__init__(parent)
        self.nombres = list(nombres)
        self.resultado = None
        self.title(titulo)
        self.resizable(False, False)
        self.columnconfigure(0, weight=1)
        iniciales = iniciales or {}
        self.entradas = {}
        for fila, nombre in enumerate(self.nombres):
            ctk.CTkLabel(self, text=nombre.capitalize(), anchor='w').grid(
                row=fila * 2, column=0, sticky='ew', padx=20, pady=(14 if fila == 0 else 6, 0))
            entrada = ctk.CTkEntry(self, width=320)
            entrada.grid(row=fila * 2 + 1, column=0, sticky='ew', padx=20)
            if nombre in iniciales:
                entrada.insert(0, iniciales[nombre])
            entrada.bind('<Return>', lambda _e: self.aceptar())
            self.entradas[nombre] = entrada
        self.mensaje = ctk.CTkLabel(self, text='', anchor='w', text_color='#B91C1C',
                                    wraplength=320, justify='left')
        self.mensaje.grid(row=len(self.nombres) * 2, column=0, sticky='ew', padx=20, pady=(8, 0))
        botones = ctk.CTkFrame(self, fg_color='transparent')
        botones.grid(row=len(self.nombres) * 2 + 1, column=0, sticky='e', padx=20, pady=14)
        ctk.CTkButton(botones, text='Cancelar', width=90, fg_color='#4B5563',
                      hover_color='#374151', command=self.cancelar).pack(side='left', padx=(0, 8))
        ctk.CTkButton(botones, text='Insertar', width=90, command=self.aceptar).pack(side='left')
        self.bind('<Escape>', lambda _e: self.cancelar())
        self.protocol('WM_DELETE_WINDOW', self.cancelar)
        primera = self.entradas[self.nombres[0]]
        self.after(150, lambda: self._mostrar(primera))

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


def pedir_valores(nombres, iniciales=None, parent=None):
    """Abre el formulario y espera. Devuelve {nombre: valor} o None si se cancela."""
    raiz = None
    if parent is None:
        raiz = parent = ctk.CTk()
        raiz.withdraw()
    try:
        formulario = FormularioVariables(parent, nombres, iniciales)
        parent.wait_window(formulario)
        return formulario.resultado
    finally:
        if raiz is not None:
            raiz.destroy()
