"""Configuración inicial del ejecutable portable, sin editar JSON a mano."""
import json
from pathlib import Path
import customtkinter as ctk
from fraseya.infraestructura.supabase import validar_conexion


def configurar_supabase(ruta):
    ventana = ctk.CTk()
    from .identidad import configurar_icono
    configurar_icono(ventana)
    ventana.title('FraseYa — Configurar proyecto')
    ventana.geometry('550x310')
    ctk.CTkLabel(ventana, text='Conectar FraseYa a Supabase', font=ctk.CTkFont(size=20)).pack(pady=16)
    url = ctk.CTkEntry(ventana, width=470, placeholder_text='https://tu-proyecto.supabase.co')
    url.pack(pady=8)
    clave = ctk.CTkEntry(ventana, width=470, placeholder_text='Clave pública publishable o anon')
    clave.pack(pady=8)
    aviso = ctk.CTkLabel(ventana, text='Usa únicamente la clave pública. No uses secret ni service_role.', wraplength=470)
    aviso.pack(pady=8)
    guardado = False
    def guardar():
        nonlocal guardado
        try:
            proyecto, publica = validar_conexion(url.get(), clave.get())
            archivo = Path(ruta)
            archivo.parent.mkdir(parents=True, exist_ok=True)
            archivo.write_text(json.dumps({'url': proyecto, 'clave_publica': publica}, indent=2), encoding='utf-8')
            guardado = True
            ventana.destroy()
        except (ValueError, OSError) as error:
            aviso.configure(text=str(error), text_color='#B91C1C')
    ctk.CTkButton(ventana, text='Guardar y continuar', command=guardar).pack(pady=12)
    ventana.mainloop()
    return guardado
