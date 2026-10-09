import json
import customtkinter as ctk
from fraseya.presentacion.configuracion_supabase import configurar_supabase


def test_asistente_rechaza_clave_privada_y_guarda_solo_configuracion_publica(tmp_path, monkeypatch):
    ruta = tmp_path/'supabase.json'
    def ciclo(ventana):
        ventana.withdraw()
        entradas = [w for w in ventana.winfo_children() if isinstance(w, ctk.CTkEntry)]
        boton = next(w for w in ventana.winfo_children() if isinstance(w, ctk.CTkButton))
        entradas[0].insert(0, 'https://ejemplo.supabase.co')
        entradas[1].insert(0, 'sb_secret_ficticia')
        boton.invoke()
        assert not ruta.exists()
        entradas[1].delete(0, 'end')
        entradas[1].insert(0, 'sb_publishable_ficticia')
        boton.invoke()
    monkeypatch.setattr(ctk.CTk, 'mainloop', ciclo)
    assert configurar_supabase(ruta)
    assert json.loads(ruta.read_text()) == {'url': 'https://ejemplo.supabase.co', 'clave_publica': 'sb_publishable_ficticia'}
