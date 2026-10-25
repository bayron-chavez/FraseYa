"""Edición del contexto de empresa sin bloquear Tk durante la red."""
import queue
from threading import Thread
import customtkinter as ctk
from fraseya.aplicacion.empresa_ia import EmpresaIA, CAMPOS
from .identidad import configurar_icono


class VentanaEmpresaIA(ctk.CTkToplevel):
    def __init__(self, parent, cliente):
        super().__init__(parent)
        configurar_icono(self)
        self.title('Perfil de empresa para la IA')
        self.geometry('650x660')
        self.servicio = EmpresaIA(cliente)
        self.cola = queue.Queue()
        self.ocupada = False
        ctk.CTkLabel(self, text='Contexto común para todos los usuarios.\n'
                     'Solo información de atención al cliente; no incluya claves ni datos personales.',
                     wraplength=600).pack(pady=10)
        cuerpo = ctk.CTkScrollableFrame(self)
        cuerpo.pack(fill='both', expand=True, padx=14)
        self.campos = {}
        etiquetas = {'nombre':'Nombre de la empresa', 'servicios':'Servicios y productos',
                     'horarios':'Horarios de atención', 'procedimientos':'Políticas y procedimientos de atención'}
        for nombre, maximo in CAMPOS.items():
            ctk.CTkLabel(cuerpo, text=f'{etiquetas[nombre]} (máximo {maximo} caracteres)', anchor='w').pack(fill='x')
            campo = ctk.CTkTextbox(cuerpo, height=50 if nombre=='nombre' else 105)
            campo.pack(fill='x', pady=(0,8))
            self.campos[nombre] = campo
        self.aviso = ctk.CTkLabel(self, text='', wraplength=610)
        self.aviso.pack()
        self.boton = ctk.CTkButton(self, text='Guardar perfil', command=self.guardar)
        self.boton.pack(pady=12)
        self.trabajar('leer', self.servicio.leer)
        self.after(80, self.atender)

    def trabajar(self, tipo, operacion):
        if self.ocupada: return
        self.ocupada = True
        self.boton.configure(state='disabled')
        for campo in self.campos.values(): campo.configure(state='disabled')
        self.aviso.configure(text='Consultando Supabase…')
        def ejecutar():
            try: self.cola.put((tipo, operacion(), None))
            except Exception as error: self.cola.put((tipo, None, str(error)))
        Thread(target=ejecutar, daemon=True).start()

    def guardar(self):
        perfil = {k: c.get('1.0','end-1c') for k,c in self.campos.items()}
        self.trabajar('guardar', lambda: self.servicio.guardar(perfil))

    def atender(self):
        try:
            tipo, resultado, error = self.cola.get_nowait()
            self.ocupada = False
            for campo in self.campos.values(): campo.configure(state='normal')
            self.boton.configure(state='normal')
            if error:
                self.aviso.configure(text='No se pudo acceder al perfil. Compruebe la conexión y los permisos.')
            else:
                if tipo=='leer':
                    for k,c in self.campos.items():
                        c.delete('1.0','end'); c.insert('1.0',resultado[k])
                self.aviso.configure(text='Perfil guardado. Se usará en las próximas consultas.' if tipo=='guardar' else 'Complete solo información verificada de la empresa.')
        except queue.Empty: pass
        self.after(80,self.atender)
