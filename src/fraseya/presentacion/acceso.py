"""Login central de Supabase y acceso explícito a la copia local sin conexión."""
import customtkinter as ctk
import queue
from threading import Thread


class VentanaAcceso(ctk.CTk):
    def __init__(self, autenticacion):
        super().__init__()
        from .identidad import configurar_icono, recurso
        from PIL import Image
        configurar_icono(self)
        self.autenticacion = autenticacion
        self.sesion = None

        self.title('FraseYa — Acceso')
        self.geometry('420x430')
        with Image.open(recurso('logo.png')) as original:
            self._logo = ctk.CTkImage(light_image=original.copy(), dark_image=original.copy(), size=(90, 90))
        ctk.CTkLabel(self, text='', image=self._logo).pack(pady=(12, 0))
        ctk.CTkLabel(self, text='Iniciar sesión',
                     font=ctk.CTkFont(size=20, weight='bold')).pack(pady=20)
        self._entradas = queue.Queue()
        self._entrando = False
        self.usuario = ctk.CTkEntry(self, placeholder_text='Correo de Supabase', width=320)
        self.usuario.pack(pady=6)
        self.clave = ctk.CTkEntry(self, placeholder_text='Contraseña', show='●', width=320)
        self.clave.pack(pady=6)
        self.mensaje = ctk.CTkLabel(self, text='', wraplength=350, text_color='#B91C1C')
        self.mensaje.pack(pady=6)
        self.boton_entrar = ctk.CTkButton(self, text='Entrar', command=self.entrar)
        self.boton_entrar.pack(pady=8)
        ctk.CTkButton(self, text='Trabajar sin conexión', command=self.sin_conexion).pack(pady=4)
        self.after(100, self._atender_entrada)
        self.bind('<Return>', lambda _: self.entrar())

    def entrar(self):
        if self._entrando:
            return
        correo, clave = self.usuario.get(), self.clave.get()
        self._entrando = True
        self.boton_entrar.configure(state='disabled')
        self.mensaje.configure(text='Conectando con Supabase…')
        def conectar():
            try:
                self._entradas.put((True, self.autenticacion.iniciar_sesion(correo, clave)))
            except (ValueError, PermissionError) as error:
                self._entradas.put((False, str(error)))
            except Exception:
                self._entradas.put((False, 'No se pudo iniciar sesión. Vuelve a intentarlo.'))
        Thread(target=conectar, daemon=True).start()
        return

    def _atender_entrada(self):
        try:
            ok, resultado = self._entradas.get_nowait()
            self._entrando = False
            self.boton_entrar.configure(state='normal')
            self.clave.delete(0, 'end')
            if ok:
                self.sesion = resultado
                self.destroy()
                return
            self.mensaje.configure(text=resultado)
        except queue.Empty:
            pass
        self.after(100, self._atender_entrada)

    def sin_conexion(self):
        if self._entrando:
            self.mensaje.configure(text='Espera a que termine el intento de conexión.')
            return
        self.sesion = self.autenticacion.sin_conexion()
        self.destroy()
