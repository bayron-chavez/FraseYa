"""Mensaje pegado voluntariamente y sugerencias revisables, sin envío automático."""
import queue
from threading import Thread
import customtkinter as ctk
from fraseya.aplicacion.recomendaciones_ia import RecomendadorIA, Sugerencia, preparar, guardar_generada
from fraseya.infraestructura.supabase import ErrorSupabase
from .identidad import configurar_icono


class VentanaIA(ctk.CTkToplevel):
    def __init__(self, parent, cliente, gestion, al_elegir, al_cerrar=None, administrador=False):
        super().__init__(parent)
        configurar_icono(self)
        self.title('FraseYa — Sugerir respuesta')
        self.geometry('680x650')
        self.minsize(550, 550)
        self.gestion, self.al_elegir = gestion, al_elegir
        self._al_cerrar = al_cerrar
        self.servicio = RecomendadorIA(cliente)
        self.cola, self.ocupada = queue.Queue(), False
        ctk.CTkLabel(self, text='Mensaje o conversación del cliente', font=ctk.CTkFont(size=18, weight='bold')).pack(pady=(16, 8))
        self._empresa = None
        if administrador:
            def configurar_empresa():
                if self._empresa is not None and self._empresa.winfo_exists():
                    self._empresa.lift(); return
                from .empresa_ia import VentanaEmpresaIA
                self._empresa = VentanaEmpresaIA(self, cliente)
            ctk.CTkButton(self, text='Configurar perfil de empresa', command=configurar_empresa).pack(pady=4)
        self.mensaje = ctk.CTkTextbox(self, height=115)
        self.mensaje.pack(fill='x', padx=16)
        ctk.CTkButton(self, text='Pegar mensaje copiado', command=self.pegar).pack(pady=6)
        ctk.CTkLabel(self, text='Al sugerir, este mensaje y hasta 40 frases candidatas se envían a Gemini.\n'
                     'También se utiliza el perfil de empresa. Puede pegar varios mensajes indicando Cliente y Agente.\n'
                     'Pega solo lo necesario y evita datos sensibles.', wraplength=620).pack(padx=16, pady=4)
        self.boton = ctk.CTkButton(self, text='Sugerir con Gemini', command=self.sugerir)
        self.boton.pack(pady=6)
        self.aviso = ctk.CTkLabel(self, text='', wraplength=620)
        self.aviso.pack(padx=16)
        ctk.CTkLabel(self, text='Si no hay coincidencias, se genera y guarda una frase propia automáticamente.\n'
                     'Revisa el contenido y los datos personales antes de usarla.', wraplength=620).pack(padx=16)
        self.resultados = ctk.CTkScrollableFrame(self)
        self.resultados.pack(fill='both', expand=True, padx=16, pady=(6, 16))
        self.after(80, self.atender)

    def destroy(self):
        callback, self._al_cerrar = getattr(self, '_al_cerrar', None), None
        if callback:
            callback()
        super().destroy()

    def pegar(self):
        try:
            texto = self.clipboard_get()
            if len(texto) > 4000:
                raise ValueError('El mensaje debe tener como máximo 4.000 caracteres.')
            self.mensaje.delete('1.0', 'end')
            self.mensaje.insert('1.0', texto)
        except Exception:
            self.aviso.configure(text='Copia un mensaje de texto de hasta 4.000 caracteres y vuelve a pegarlo.')

    def sugerir(self):
        if self.ocupada:
            return
        mensaje, frases = self.mensaje.get('1.0', 'end-1c'), self.gestion.listar()
        try:
            preparar(mensaje, frases)
        except ValueError as error:
            self.aviso.configure(text=str(error))
            return
        self.ocupada = True
        self.boton.configure(state='disabled')
        for widget in self.resultados.winfo_children():
            widget.destroy()
        self.aviso.configure(text=f'Buscando entre {min(40, len(frases))} de {len(frases)} frases…')
        def consultar():
            try:
                sugerencias = self.servicio.sugerir(mensaje, frases)
                if sugerencias:
                    self.cola.put((True, sugerencias))
                else:
                    self.cola.put(('generada', self.servicio.generar(mensaje, frases)))
            except (ErrorSupabase, ValueError, PermissionError) as error:
                self.cola.put((False, str(error)))
            except Exception:
                self.cola.put((False, 'No se pudo consultar la IA. Inténtalo nuevamente.'))
        Thread(target=consultar, daemon=True, name='sugerencias-ia').start()

    def atender(self):
        try:
            ok, resultado = self.cola.get_nowait()
            self.ocupada = False
            self.boton.configure(state='normal')
            if ok == 'generada':
                try:
                    frase = guardar_generada(self.gestion, resultado)
                    resultado = [Sugerencia(frase, 'Generada con IA y guardada como propia. Revisa la plantilla antes de usarla.')]
                except ValueError as error:
                    ok, resultado = False, str(error)
            if not ok:
                self.aviso.configure(text=resultado)
            else:
                self.aviso.configure(text='Revisa la frase antes de usarla.' if resultado else 'No se encontró una frase adecuada. Prueba con más contexto.')
                for sugerencia in resultado:
                    tarjeta = ctk.CTkFrame(self.resultados)
                    tarjeta.pack(fill='x', pady=5)
                    ctk.CTkLabel(tarjeta, text=sugerencia.frase['titulo'], anchor='w', font=ctk.CTkFont(weight='bold')).pack(fill='x', padx=12, pady=(8, 0))
                    ctk.CTkLabel(tarjeta, text=sugerencia.motivo, wraplength=570, justify='left').pack(fill='x', padx=12)
                    vista = ctk.CTkTextbox(tarjeta, height=90)
                    vista.pack(fill='x', padx=12, pady=4)
                    vista.insert('1.0', sugerencia.frase['contenido'])
                    vista.configure(state='disabled')
                    ctk.CTkButton(tarjeta, text='Elegir esta frase', command=lambda s=sugerencia: self.elegir(s.frase)).pack(pady=(0, 8))
        except queue.Empty:
            pass
        self.after(80, self.atender)

    def elegir(self, frase):
        try:
            actual = self.gestion.repo.obtener_frase(frase['id'])
            if any(actual[c] != frase[c] for c in ('origen', 'abreviatura', 'contenido')):
                raise ValueError()
        except (ValueError, KeyError, LookupError):
            self.aviso.configure(text='Esta frase cambió. Solicita nuevas sugerencias.')
            return
        self.al_elegir(actual)
        self.destroy()
