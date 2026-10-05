"""Acceso local y alta de cuentas desde una sesión administradora."""
import customtkinter as ctk
from tkinter import ttk, messagebox


class VentanaAcceso(ctk.CTk):
    def __init__(self, autenticacion):
        super().__init__()
        self.autenticacion = autenticacion
        self.sesion = None
        self.inicial = not autenticacion.tiene_usuarios()
        self.title('FraseYa — Acceso')
        self.geometry('420x330')
        ctk.CTkLabel(self, text='Crear administrador inicial' if self.inicial else 'Iniciar sesión',
                     font=ctk.CTkFont(size=20, weight='bold')).pack(pady=20)
        self.usuario = ctk.CTkEntry(self, placeholder_text='Usuario', width=320)
        self.usuario.pack(pady=6)
        self.clave = ctk.CTkEntry(self, placeholder_text='Contraseña (mínimo 10 caracteres)', show='●', width=320)
        self.clave.pack(pady=6)
        self.repetida = ctk.CTkEntry(self, placeholder_text='Repetir contraseña', show='●', width=320)
        if self.inicial:
            self.repetida.pack(pady=6)
        self.mensaje = ctk.CTkLabel(self, text='', wraplength=350, text_color='#B91C1C')
        self.mensaje.pack(pady=6)
        ctk.CTkButton(self, text='Crear y entrar' if self.inicial else 'Entrar', command=self.entrar).pack(pady=8)
        self.bind('<Return>', lambda _: self.entrar())

    def entrar(self):
        try:
            if self.inicial:
                if self.clave.get() != self.repetida.get():
                    raise ValueError('Las contraseñas no coinciden.')
                self.autenticacion.crear_administrador_inicial(self.usuario.get(), self.clave.get())
                self.inicial = False
            self.sesion = self.autenticacion.iniciar_sesion(self.usuario.get(), self.clave.get())
        except (ValueError, PermissionError) as error:
            self.mensaje.configure(text=str(error))
            return
        self.destroy()


class VentanaUsuarios(ctk.CTkToplevel):
    def __init__(self, parent, autenticacion, sesion):
        autenticacion.validar(sesion, administrador=True)
        super().__init__(parent)
        self.title('Administrar usuarios')
        self.geometry('620x640')
        self.autenticacion, self.sesion = autenticacion, sesion
        self.seleccion = None
        self.tabla = ttk.Treeview(self, columns=('nombre', 'rol'), show='headings', height=8)
        self.tabla.heading('nombre', text='Usuario')
        self.tabla.heading('rol', text='Rol')
        self.tabla.pack(fill='both', expand=True, padx=20, pady=(16, 8))
        self.tabla.bind('<<TreeviewSelect>>', self.seleccionar)
        ctk.CTkButton(self, text='Nueva cuenta', command=self.nueva).pack(pady=4)
        self.usuario = ctk.CTkEntry(self, placeholder_text='Nombre de usuario', width=320)
        self.usuario.pack(pady=(24, 8))
        self.clave = ctk.CTkEntry(self, placeholder_text='Contraseña (mínimo 10 caracteres)', show='●', width=320)
        self.clave.pack(pady=8)
        self.repetida = ctk.CTkEntry(self, placeholder_text='Repetir contraseña', show='●', width=320)
        self.repetida.pack(pady=8)
        self.rol = ctk.CTkOptionMenu(self, values=['usuario', 'administrador'])
        self.rol.pack(pady=8)
        self.mensaje = ctk.CTkLabel(self, text='', wraplength=350)
        self.mensaje.pack(pady=8)
        ctk.CTkLabel(self, text='Al editar, deja la contraseña vacía para conservarla.').pack(pady=4)
        botones = ctk.CTkFrame(self, fg_color='transparent')
        botones.pack(pady=(4, 16))
        ctk.CTkButton(botones, text='Crear cuenta', command=self.crear).pack(side='left', padx=4)
        self.btn_guardar = ctk.CTkButton(botones, text='Guardar cambios', command=self.guardar)
        self.btn_guardar.pack(side='left', padx=4)
        self.btn_eliminar = ctk.CTkButton(botones, text='Eliminar cuenta', command=self.eliminar, fg_color='#B91C1C')
        self.btn_eliminar.pack(side='left', padx=4)
        self.refrescar()
        self.nueva()

    def refrescar(self):
        cuentas = self.autenticacion.listar_usuarios(self.sesion)
        self.tabla.delete(*self.tabla.get_children())
        for i, cuenta in enumerate(cuentas):
            self.tabla.insert('', 'end', iid=str(i), values=(cuenta['nombre'], cuenta['rol']))

    def _limpiar_claves(self):
        self.clave.delete(0, 'end')
        self.repetida.delete(0, 'end')

    def nueva(self):
        self.seleccion = None
        self.tabla.selection_remove(*self.tabla.selection())
        self.usuario.delete(0, 'end')
        self._limpiar_claves()
        self.rol.set('usuario')
        self.btn_guardar.configure(state='disabled')
        self.btn_eliminar.configure(state='disabled')
        self.mensaje.configure(text='')

    def seleccionar(self, _evento=None):
        seleccion = self.tabla.selection()
        if not seleccion:
            return
        nombre, rol = self.tabla.item(seleccion[0], 'values')
        self.seleccion = nombre
        self.usuario.delete(0, 'end')
        self.usuario.insert(0, nombre)
        self.rol.set(rol)
        self._limpiar_claves()
        self.btn_guardar.configure(state='normal')
        self.btn_eliminar.configure(state='disabled' if nombre == self.sesion.usuario else 'normal')

    def guardar(self):
        if self.seleccion is None:
            return
        try:
            if self.clave.get() != self.repetida.get():
                raise ValueError('Las contraseñas no coinciden.')
            self.autenticacion.actualizar_usuario(self.sesion, self.seleccion,
                self.usuario.get(), self.rol.get(), self.clave.get() or None)
        except (ValueError, PermissionError) as error:
            self.mensaje.configure(text=str(error), text_color='#B91C1C')
            return
        self.refrescar()
        self.nueva()
        self.mensaje.configure(text='Cuenta actualizada.', text_color='#15803D')

    def eliminar(self):
        if self.seleccion is None:
            return
        if not messagebox.askyesno('Eliminar cuenta',
                f'¿Eliminar la cuenta «{self.seleccion}»? No se borrarán las frases.', parent=self):
            return
        try:
            self.autenticacion.eliminar_usuario(self.sesion, self.seleccion)
        except (ValueError, PermissionError) as error:
            self.mensaje.configure(text=str(error), text_color='#B91C1C')
            return
        self.refrescar()
        self.nueva()
        self.mensaje.configure(text='Cuenta eliminada.', text_color='#15803D')

    def crear(self):
        try:
            if self.clave.get() != self.repetida.get():
                raise ValueError('Las contraseñas no coinciden.')
            self.autenticacion.crear_usuario(self.sesion, self.usuario.get(), self.clave.get(), self.rol.get())
        except (ValueError, PermissionError) as error:
            self.mensaje.configure(text=str(error), text_color='#B91C1C')
            return
        self.clave.delete(0, 'end')
        self.repetida.delete(0, 'end')
        self.refrescar()
        self.nueva()
        self.mensaje.configure(text='Cuenta creada.', text_color='#15803D')
