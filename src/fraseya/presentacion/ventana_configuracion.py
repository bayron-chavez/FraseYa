"""Pantalla de configuración (RF-11).

Atajo del buscador, tecla de confirmación, velocidad de escritura e intervalo de sincronización con Supabase. Los valores se validan juntos,
se guardan y se aplican al instante (sin reiniciar).
"""

import customtkinter as ctk

from fraseya.aplicacion.configuracion import (ATAJOS_RECOMENDADOS, INTERVALO_MAX, INTERVALO_MIN,
                                              Configuracion, normalizar_atajo)
from fraseya.aplicacion.gestion_frases import ErroresValidacion
from fraseya.infraestructura.escritor_texto import VELOCIDAD_MAX_MS, VELOCIDAD_MIN_MS

TECLAS = {'Tab': 'tab', 'Enter': 'enter', 'Espacio': 'espacio'}
NOMBRE_DE_TECLA = {v: k for k, v in TECLAS.items()}


class VentanaConfiguracion(ctk.CTkToplevel):
    def __init__(self, parent, configuracion: Configuracion, al_guardar=None, al_cerrar=None):
        """al_guardar(ajustes) aplica los cambios; al_cerrar() se llama al cerrar la pantalla."""
        super().__init__(parent)
        self.configuracion = configuracion
        self._al_guardar = al_guardar
        self._al_cerrar = al_cerrar
        self.guardado = None            # Ajustes guardados, si se pulsó Guardar con éxito
        self.title('Configuración')
        self.resizable(False, False)
        self.columnconfigure(0, weight=1)
        self.protocol('WM_DELETE_WINDOW', self.cancelar)
        self.bind('<Escape>', lambda _e: self.cancelar())

        fila = 0
        fila = self._seccion(fila, 'Escritura', primera=True)
        self.atajo = self._campo_atajo(fila)
        fila += 4
        ctk.CTkLabel(self, text='Tecla de confirmación de la expansión', anchor='w').grid(
            row=fila, column=0, sticky='ew', padx=24, pady=(10, 0))
        self.tecla = ctk.CTkSegmentedButton(self, values=list(TECLAS))
        self.tecla.grid(row=fila + 1, column=0, sticky='w', padx=24)
        ctk.CTkLabel(self, text='Escribes la abreviatura y pulsas esta tecla para expandirla.', anchor='w',
                     text_color='#6B7280').grid(row=fila + 2, column=0, sticky='ew', padx=24)
        fila += 3
        self.etiqueta_velocidad = ctk.CTkLabel(self, text='', anchor='w')
        self.etiqueta_velocidad.grid(row=fila, column=0, sticky='ew', padx=24, pady=(10, 0))
        self.velocidad = ctk.CTkSlider(self, from_=VELOCIDAD_MIN_MS, to=VELOCIDAD_MAX_MS,
                                       number_of_steps=VELOCIDAD_MAX_MS - VELOCIDAD_MIN_MS,
                                       command=lambda _v: self._mostrar_velocidad())
        self.velocidad.grid(row=fila + 1, column=0, sticky='ew', padx=24)
        ctk.CTkLabel(self, text='Más lento es más seguro en aplicaciones que pierden letras.', anchor='w',
                     text_color='#6B7280').grid(row=fila + 2, column=0, sticky='ew', padx=24)
        fila += 3

        fila = self._seccion(fila, 'Catálogo compartido')
        self.intervalo = self._campo(fila, f'Revisar actualizaciones cada (minutos, {INTERVALO_MIN}–{INTERVALO_MAX})',
                                     'Cada cuánto se comprueba si hay una versión nueva del catálogo.')
        fila += 3

        self.mensaje = ctk.CTkLabel(self, text='', anchor='w', justify='left', text_color='#B91C1C', wraplength=440)
        self.mensaje.grid(row=fila, column=0, sticky='ew', padx=24, pady=(10, 0))
        botones = ctk.CTkFrame(self, fg_color='transparent')
        botones.grid(row=fila + 1, column=0, sticky='ew', padx=24, pady=16)
        ctk.CTkButton(botones, text='Restablecer', width=100, fg_color='transparent', border_width=1,
                      text_color='#374151', hover_color='#E5E7EB', command=self.restablecer).pack(side='left')
        ctk.CTkButton(botones, text='Guardar', width=100, command=self.guardar).pack(side='right')
        ctk.CTkButton(botones, text='Cancelar', width=100, fg_color='#4B5563', hover_color='#374151',
                      command=self.cancelar).pack(side='right', padx=(0, 8))

        self.cargar(self.configuracion.leer())
        self.after(150, self._tomar_foco)

    # ---- construcción ---------------------------------------------------
    def _seccion(self, fila, titulo, primera=False):
        ctk.CTkLabel(self, text=titulo, anchor='w', font=ctk.CTkFont(size=15, weight='bold')).grid(
            row=fila, column=0, sticky='ew', padx=24, pady=(18 if primera else 20, 0))
        return fila + 1

    def _campo(self, fila, etiqueta, ayuda):
        ctk.CTkLabel(self, text=etiqueta, anchor='w').grid(row=fila, column=0, sticky='ew', padx=24, pady=(10, 0))
        entrada = ctk.CTkEntry(self, width=440)
        entrada.grid(row=fila + 1, column=0, sticky='ew', padx=24)
        ctk.CTkLabel(self, text=ayuda, anchor='w', text_color='#6B7280').grid(
            row=fila + 2, column=0, sticky='ew', padx=24)
        return entrada

    def _campo_atajo(self, fila):
        """Entrada del atajo con botones de atajos recomendados y una línea de ayuda."""
        ctk.CTkLabel(self, text='Atajo del buscador', anchor='w').grid(
            row=fila, column=0, sticky='ew', padx=24, pady=(10, 0))
        entrada = ctk.CTkEntry(self, width=440)
        entrada.grid(row=fila + 1, column=0, sticky='ew', padx=24)
        entrada.bind('<KeyRelease>', lambda _e: self._marcar_atajo())
        marco = ctk.CTkFrame(self, fg_color='transparent')
        marco.grid(row=fila + 2, column=0, sticky='ew', padx=24, pady=(6, 0))
        marco.columnconfigure((0, 1), weight=1, uniform='atajos')
        self.botones_atajo = {}
        for i, (atajo, _descripcion) in enumerate(ATAJOS_RECOMENDADOS):
            boton = ctk.CTkButton(marco, text=self._nombre_atajo(atajo), height=28,
                                  command=lambda a=atajo: self.usar_atajo(a))
            boton.grid(row=i // 2, column=i % 2, sticky='ew', padx=(0, 6) if i % 2 == 0 else (0, 0),
                       pady=(0, 4))
            self.botones_atajo[atajo] = boton
        self.ayuda_atajo = ctk.CTkLabel(self, text='', anchor='w', justify='left', wraplength=440,
                                        text_color='#6B7280')
        self.ayuda_atajo.grid(row=fila + 3, column=0, sticky='ew', padx=24)
        return entrada

    @staticmethod
    def _nombre_atajo(atajo):
        return '+'.join(p.capitalize() for p in atajo.split('+'))

    def usar_atajo(self, atajo):
        """Pone un atajo recomendado en la entrada (se guarda al pulsar Guardar)."""
        self._poner(self.atajo, atajo)
        self._marcar_atajo()

    def _marcar_atajo(self):
        """Resalta el botón que coincide con lo escrito y explica ese atajo."""
        actual = normalizar_atajo(self.atajo.get())
        descripciones = dict(ATAJOS_RECOMENDADOS)
        for atajo, boton in self.botones_atajo.items():
            elegido = atajo == actual
            boton.configure(fg_color='#1F6AA5' if elegido else '#D1D5DB',
                            hover_color='#16507F' if elegido else '#B8BEC7',
                            text_color='#FFFFFF' if elegido else '#1F2937')
        self.ayuda_atajo.configure(
            text=descripciones.get(actual, 'Escribe otro, por ejemplo ctrl+shift+f9, o elige uno de los recomendados.'))

    def _tomar_foco(self):
        if not self.winfo_exists():
            return
        self.lift()
        self.atajo.focus_set()
        try:
            self.grab_set()
        except Exception:      # aún no visible; se podrá usar igual
            pass

    # ---- datos ----------------------------------------------------------
    @staticmethod
    def _poner(entrada, texto):
        entrada.delete(0, 'end')
        entrada.insert(0, texto)

    def cargar(self, ajustes):
        self._poner(self.atajo, ajustes.atajo_buscador)
        self._marcar_atajo()
        self.tecla.set(NOMBRE_DE_TECLA[ajustes.tecla_confirmacion])
        self.velocidad.set(ajustes.velocidad_ms)
        self._mostrar_velocidad()
        self._poner(self.intervalo, str(ajustes.intervalo_sincronizacion_min))

    def valores(self):
        return {'atajo_buscador': self.atajo.get(),
                'tecla_confirmacion': TECLAS.get(self.tecla.get(), ''),
                'velocidad_ms': str(int(round(self.velocidad.get()))),
                'intervalo_sincronizacion_min': self.intervalo.get()}

    def _mostrar_velocidad(self):
        self.etiqueta_velocidad.configure(
            text=f'Velocidad de escritura: {int(round(self.velocidad.get()))} ms por carácter')

    # ---- acciones -------------------------------------------------------
    def restablecer(self):
        """Muestra los valores predeterminados; solo se guardan al pulsar Guardar."""
        from fraseya.aplicacion.configuracion import Ajustes
        self.cargar(Ajustes())
        self.mensaje.configure(text='Valores predeterminados cargados. Pulsa Guardar para aplicarlos.',
                               text_color='#374151')

    def guardar(self):
        try:
            ajustes = self.configuracion.guardar(self.valores())
        except ErroresValidacion as error:
            self.mensaje.configure(text='\n'.join(f'• {e}' for e in error.errores), text_color='#B91C1C')
            return
        self.guardado = ajustes
        if self._al_guardar:
            self._al_guardar(ajustes)
        self._cerrar()

    def cancelar(self):
        self.guardado = None
        self._cerrar()

    def _cerrar(self):
        if self._al_cerrar:
            self._al_cerrar()
        self.destroy()
