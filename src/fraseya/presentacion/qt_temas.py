"""Temas visuales (claro y oscuro) y paletas semánticas para la interfaz Qt de FraseYa."""
from fraseya.aplicacion.configuracion import TEMA_PREDETERMINADO, TEMAS_VALIDOS
from .identidad import recurso

_FLECHA = recurso('chevron.svg').as_posix()

_PALETAS = {
    'claro': {
        'fondo': '#f5f7fb',
        'superficie': '#ffffff',
        'panel': '#ffffff',
        'tarjeta': '#f8fafc',
        'texto': '#000000',
        'texto_tenue': '#1f2937',
        'borde': '#e5eaf1',
        'primario': '#2875e8',
        'primario_hover': '#2268ce',
        'pill_fondo': '#16263d',
        'pill_texto': '#f8fafc',
        'acento_empatica': '#10b981',
        'acento_directa': '#2875e8',
        'acento_escalar': '#8b5cf6',
        'peligro': '#dc2626',
        'campo_fondo': '#ffffff',
    },
    'oscuro': {
        'fondo': '#0f141c',
        'superficie': '#161d28',
        'panel': '#161d28',
        'tarjeta': '#1c2533',
        'texto': '#eef2f7',
        'texto_tenue': '#94a3b8',
        'borde': '#2a3649',
        'primario': '#3b82f6',
        'primario_hover': '#2563eb',
        'pill_fondo': '#0b1220',
        'pill_texto': '#eef2f7',
        'acento_empatica': '#10b981',
        'acento_directa': '#3b82f6',
        'acento_escalar': '#8b5cf6',
        'peligro': '#dc2626',
        'campo_fondo': '#111824',
    },
}

_DETALLES = {
    'claro': {
        'brand': '#246bcc',
        'nav_group': '#1f2937',
        'chip_fondo': '#edf4ff',
        'chip_texto': '#246bcc',
        'inline_confirm_fondo': '#fff7ed',
        'inline_confirm_borde': '#fed7aa',
        'banner_info_fondo': '#edf4ff',
        'banner_info_borde': '#bfdbfe',
        'banner_ok_fondo': '#ecfdf5',
        'banner_ok_borde': '#a7f3d0',
        'banner_aviso_fondo': '#fffbeb',
        'banner_aviso_borde': '#fde68a',
        'banner_error_fondo': '#fef2f2',
        'banner_error_borde': '#fecaca',
        'boton_fondo': '#ffffff',
        'boton_borde': '#e2e8f1',
        'boton_hover': '#eff5fe',
        'boton_hover_borde': '#cfe0f7',
        'boton_pressed': '#e2ecf9',
        'boton_disabled_texto': '#6b7280',
        'boton_disabled_fondo': '#f4f6fa',
        'boton_disabled_borde': '#e5eaf1',
        'primario_pressed': '#1c57b0',
        'primario_disabled_fondo': '#a5c4f4',
        'primario_disabled_texto': '#ffffff',
        'peligro_hover': '#b91c1c',
        'peligro_pressed': '#991b1b',
        'peligro_disabled_fondo': '#fca5a5',
        'peligro_disabled_texto': '#ffffff',
        'ghost_borde': '#dfe6f0',
        'ghost_texto': '#1f2937',
        'ghost_hover_fondo': '#eff5fe',
        'ghost_hover_texto': '#246bcc',
        'ghost_disabled_texto': '#aab5c4',
        'nav_texto': '#1f2937',
        'nav_hover_fondo': '#f2f6fc',
        'nav_hover_texto': '#000000',
        'nav_checked_fondo': '#edf4ff',
        'nav_checked_texto': '#246bcc',
        'nav_disabled_texto': '#b8c3d1',
        'toggle_fondo': '#f1f5f9',
        'toggle_borde': '#dfe6f0',
        'toggle_texto': '#000000',
        'toggle_hover_fondo': '#e6effb',
        'toggle_hover_borde': '#bfdbfe',
        'toggle_hover_texto': '#246bcc',
        'toggle_checked_fondo': '#edf4ff',
        'toggle_checked_borde': '#93c5fd',
        'toggle_checked_texto': '#246bcc',
        'campo_borde': '#dfe6f0',
        'campo_disabled_fondo': '#f4f6fa',
        'campo_disabled_texto': '#94a3b8',
        'campo_readonly_fondo': '#f8fafc',
        'campo_readonly_texto': '#1f2937',
        'popup_fondo': '#ffffff',
        'popup_borde': '#dfe6f0',
        'popup_sel_fondo': '#0a1f5c',
        'popup_sel_texto': '#ffffff',
        'lista_borde_item': '#eef1f6',
        'lista_sel_fondo': '#edf4ff',
        'lista_sel_inactiva_fondo': '#f1f5fb',
        'lista_sel_texto': '#000000',
        'lista_hover_fondo': '#f7faff',
        'preview_fondo': '#f8fafc',
        'preview_texto': '#1f2937',
        'preview_borde': '#edf1f6',
        'scroll_track': '#f5f7fb',
        'scroll_handle': '#cbd5e1',
        'scroll_handle_hover': '#94a3b8',
        'menu_fondo': '#ffffff',
        'menu_borde': '#dfe6f0',
        'menu_sel_fondo': '#edf4ff',
        'menu_sel_texto': '#246bcc',
        'menu_disabled_texto': '#aab5c4',
        'tooltip_fondo': '#1e293b',
        'tooltip_texto': '#f8fafc',
        'tooltip_borde': '#334155',
    },
    'oscuro': {
        'brand': '#60a5fa',
        'nav_group': '#8395ad',
        'chip_fondo': '#1a2d4d',
        'chip_texto': '#93c5fd',
        'inline_confirm_fondo': '#2a1f14',
        'inline_confirm_borde': '#7c4a1d',
        'banner_info_fondo': '#14233a',
        'banner_info_borde': '#2563eb',
        'banner_ok_fondo': '#102821',
        'banner_ok_borde': '#059669',
        'banner_aviso_fondo': '#2a2112',
        'banner_aviso_borde': '#b45309',
        'banner_error_fondo': '#2d161b',
        'banner_error_borde': '#b91c1c',
        'boton_fondo': '#1e293b',
        'boton_borde': '#334155',
        'boton_hover': '#273549',
        'boton_hover_borde': '#475569',
        'boton_pressed': '#172030',
        'boton_disabled_texto': '#64748b',
        'boton_disabled_fondo': '#131a24',
        'boton_disabled_borde': '#222d3d',
        'primario_pressed': '#1d4ed8',
        'primario_disabled_fondo': '#1e3a5f',
        'primario_disabled_texto': '#93b4d8',
        'peligro_hover': '#b91c1c',
        'peligro_pressed': '#991b1b',
        'peligro_disabled_fondo': '#4c1d24',
        'peligro_disabled_texto': '#d89aa2',
        'ghost_borde': '#334155',
        'ghost_texto': '#cbd5e1',
        'ghost_hover_fondo': '#1e2d45',
        'ghost_hover_texto': '#93c5fd',
        'ghost_disabled_texto': '#64748b',
        'nav_texto': '#94a3b8',
        'nav_hover_fondo': '#1e293b',
        'nav_hover_texto': '#eef2f7',
        'nav_checked_fondo': '#1a2d4d',
        'nav_checked_texto': '#60a5fa',
        'nav_disabled_texto': '#4b5c73',
        'toggle_fondo': '#1e293b',
        'toggle_borde': '#334155',
        'toggle_texto': '#eef2f7',
        'toggle_hover_fondo': '#273549',
        'toggle_hover_borde': '#3b82f6',
        'toggle_hover_texto': '#93c5fd',
        'toggle_checked_fondo': '#1a2d4d',
        'toggle_checked_borde': '#3b82f6',
        'toggle_checked_texto': '#93c5fd',
        'campo_borde': '#2a3649',
        'campo_disabled_fondo': '#141b26',
        'campo_disabled_texto': '#64748b',
        'campo_readonly_fondo': '#141b26',
        'campo_readonly_texto': '#cbd5e1',
        'popup_fondo': '#161d28',
        'popup_borde': '#334155',
        'popup_sel_fondo': '#1e3a5f',
        'popup_sel_texto': '#eef2f7',
        'lista_borde_item': '#232e40',
        'lista_sel_fondo': '#1a2d4d',
        'lista_sel_inactiva_fondo': '#182740',
        'lista_sel_texto': '#eef2f7',
        'lista_hover_fondo': '#1c2636',
        'preview_fondo': '#121925',
        'preview_texto': '#cbd5e1',
        'preview_borde': '#263245',
        'scroll_track': '#0f141c',
        'scroll_handle': '#334155',
        'scroll_handle_hover': '#475569',
        'menu_fondo': '#161d28',
        'menu_borde': '#2a3649',
        'menu_sel_fondo': '#1a2d4d',
        'menu_sel_texto': '#93c5fd',
        'menu_disabled_texto': '#64748b',
        'tooltip_fondo': '#1c2533',
        'tooltip_texto': '#eef2f7',
        'tooltip_borde': '#334155',
    },
}


def normalizar_tema(tema: str = TEMA_PREDETERMINADO) -> str:
    """Normaliza el nombre del tema; cualquier valor desconocido cae a 'claro'."""
    if isinstance(tema, str):
        limpio = tema.strip().lower()
        if limpio in TEMAS_VALIDOS:
            return limpio
    return TEMA_PREDETERMINADO


def paleta(tema: str = TEMA_PREDETERMINADO) -> dict:
    """Devuelve una copia del diccionario de colores semánticos para 'claro' u 'oscuro'."""
    return dict(_PALETAS[normalizar_tema(tema)])


PALETA_FLOTANTE = {
    'claro': {
        'barra_fondo': '#16263d',
        'barra_borde': '#243b5a',
        'barra_texto': '#f8fafc',
        'barra_boton_fondo': '#223654',
        'barra_boton_hover': '#2d466b',
        'barra_boton_borde': '#355078',
        'barra_boton_texto': '#e2e8f0',
        'barra_cerrar_hover': '#304769',
        'activo_fondo': '#10b981',
        'activo_hover': '#059669',
        'activo_texto': '#ffffff',
        'pausada_fondo': '#475569',
        'pausada_hover': '#64748b',
        'pausada_texto': '#e2e8f0',
        'chip_tema_fondo': '#1e3a5f',
        'chip_tema_borde': '#2e5b94',
        'chip_tema_texto': '#bfdbfe',
        'chip_animo_rojo_fondo': '#472226',
        'chip_animo_rojo_borde': '#86343b',
        'chip_animo_rojo_texto': '#fecaca',
        'chip_animo_ambar_fondo': '#45331a',
        'chip_animo_ambar_borde': '#855d20',
        'chip_animo_ambar_texto': '#fde68a',
        'chip_urgencia_alta_fondo': '#4a2a16',
        'chip_urgencia_alta_borde': '#934b1c',
        'chip_urgencia_alta_texto': '#fed7aa',
        'chip_urgencia_neutra_fondo': '#23344d',
        'chip_urgencia_neutra_borde': '#3b5273',
        'chip_urgencia_neutra_texto': '#cbd5e1',
        'aviso_fondo': '#233a59',
        'aviso_borde': '#3b6496',
        'aviso_texto': '#fef3c7',
        'tarjeta_fondo': '#ffffff',
        'tarjeta_borde': '#d7e1ee',
        'tarjeta_texto': '#1e293b',
        'tarjeta_muted': '#64748b',
        'btn_primario_fondo': '#2875e8',
        'btn_primario_hover': '#1d64d1',
        'btn_primario_disabled': '#93c5fd',
        'btn_primario_texto': '#ffffff',
        'btn_sec_fondo': '#f8fafc',
        'btn_sec_hover': '#edf4ff',
        'btn_sec_borde': '#cbd5e1',
        'btn_sec_texto': '#334155',
        'editor_fondo': '#f8fafc',
        'editor_borde': '#cbd5e1',
        'editor_foco': '#2875e8',
        'editor_texto': '#1e293b',
        'preview_vars_fondo': '#f1f5f9',
        'preview_vars_borde': '#cbd5e1',
        'error_vars_texto': '#dc2626',
        'scroll_handle': '#cbd5e1',
    },
    'oscuro': {
        'barra_fondo': '#0b1220',
        'barra_borde': '#2b3a52',
        'barra_texto': '#f8fafc',
        'barra_boton_fondo': '#152033',
        'barra_boton_hover': '#1f2e47',
        'barra_boton_borde': '#2b3a52',
        'barra_boton_texto': '#e2e8f0',
        'barra_cerrar_hover': '#223149',
        'activo_fondo': '#10b981',
        'activo_hover': '#059669',
        'activo_texto': '#ffffff',
        'pausada_fondo': '#334155',
        'pausada_hover': '#475569',
        'pausada_texto': '#cbd5e1',
        'chip_tema_fondo': '#142945',
        'chip_tema_borde': '#244a7a',
        'chip_tema_texto': '#93c5fd',
        'chip_animo_rojo_fondo': '#3a1a1f',
        'chip_animo_rojo_borde': '#732c34',
        'chip_animo_rojo_texto': '#fca5a5',
        'chip_animo_ambar_fondo': '#362712',
        'chip_animo_ambar_borde': '#73501c',
        'chip_animo_ambar_texto': '#fde68a',
        'chip_urgencia_alta_fondo': '#3a2011',
        'chip_urgencia_alta_borde': '#7c3f18',
        'chip_urgencia_alta_texto': '#fdba74',
        'chip_urgencia_neutra_fondo': '#162133',
        'chip_urgencia_neutra_borde': '#2b3c56',
        'chip_urgencia_neutra_texto': '#94a3b8',
        'aviso_fondo': '#192a42',
        'aviso_borde': '#315380',
        'aviso_texto': '#fde68a',
        'tarjeta_fondo': '#1c2533',
        'tarjeta_borde': '#2d3b50',
        'tarjeta_texto': '#eef2f7',
        'tarjeta_muted': '#94a3b8',
        'btn_primario_fondo': '#2875e8',
        'btn_primario_hover': '#3b82f6',
        'btn_primario_disabled': '#334e78',
        'btn_primario_texto': '#ffffff',
        'btn_sec_fondo': '#243044',
        'btn_sec_hover': '#2f3e58',
        'btn_sec_borde': '#394a64',
        'btn_sec_texto': '#e2e8f0',
        'editor_fondo': '#111824',
        'editor_borde': '#334155',
        'editor_foco': '#3b82f6',
        'editor_texto': '#eef2f7',
        'preview_vars_fondo': '#131c2b',
        'preview_vars_borde': '#2b3a52',
        'error_vars_texto': '#fca5a5',
        'scroll_handle': '#3b4b63',
    },
}


def estilo_actual() -> str:
    """Devuelve la hoja de estilos activa en QApplication o el tema claro por defecto."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is not None:
        qss = app.styleSheet()
        if qss:
            return qss
    return ESTILO


def hoja_estilo(tema: str = TEMA_PREDETERMINADO) -> str:
    """Genera la hoja de estilos QSS completa para el tema indicado ('claro' u 'oscuro')."""
    clave = normalizar_tema(tema)
    c = {**_PALETAS[clave], **_DETALLES[clave]}
    return f'''
QWidget {{font-family: 'Segoe UI'; font-size:13px; font-weight:600; color:{c['texto']}; background:{c['fondo']};}}
QMainWindow, QDialog, QMessageBox {{background:{c['fondo']}; color:{c['texto']};}}
QStackedWidget {{background:transparent;}}
QScrollArea {{background:transparent; border:0;}}
QScrollArea > QWidget {{background:transparent;}}
QScrollArea > QWidget > QWidget {{background:transparent;}}
QWidget#scroll_content {{background:transparent;}}
QFrame#sidebar, QFrame#panel {{background:{c['panel']}; border:1px solid {c['borde']}; border-radius:12px;}}
QFrame#sidebar {{border-radius:0; border-left:0; border-top:0; border-bottom:0;}}
QFrame#card {{background:{c['tarjeta']}; border:1px solid {c['borde']}; border-radius:10px;}}
QFrame#inline_confirm {{background:{c['inline_confirm_fondo']}; border:1px solid {c['inline_confirm_borde']}; border-radius:10px;}}
QFrame#banner_info {{background:{c['banner_info_fondo']}; border:1px solid {c['banner_info_borde']}; border-radius:10px;}}
QFrame#banner_ok {{background:{c['banner_ok_fondo']}; border:1px solid {c['banner_ok_borde']}; border-radius:10px;}}
QFrame#banner_aviso {{background:{c['banner_aviso_fondo']}; border:1px solid {c['banner_aviso_borde']}; border-radius:10px;}}
QFrame#banner_error {{background:{c['banner_error_fondo']}; border:1px solid {c['banner_error_borde']}; border-radius:10px;}}
QLabel {{background:transparent; color:{c['texto']};}}
QLabel#brand {{font-size:24px; font-weight:700; color:{c['brand']};}}
QLabel#heading {{font-size:28px; font-weight:600; color:{c['texto']};}}
QLabel#muted {{color:{c['texto_tenue']}; font-size:12px;}}
QLabel#section {{font-weight:700; font-size:14px; color:{c['texto']};}}
QLabel#nav_group {{color:{c['nav_group']}; font-size:11px; font-weight:600; padding:8px 18px 2px 18px;}}
QLabel#chip {{background:{c['chip_fondo']}; color:{c['chip_texto']}; border-radius:6px; padding:4px 10px; font-weight:600; font-size:12px;}}
QCheckBox, QRadioButton {{background:transparent; color:{c['texto']};}}
QCheckBox::indicator {{width:16px; height:16px; border:2px solid #475569; border-radius:4px; background:{c['campo_fondo']};}}
QCheckBox::indicator:checked {{background:{c['primario']}; border:2px solid {c['primario']};}}
QPushButton {{background:{c['boton_fondo']}; color:{c['texto']}; border:1px solid {c['boton_borde']}; border-radius:7px; padding:10px 15px;}}
QPushButton:hover {{background:{c['boton_hover']}; border:1px solid {c['boton_hover_borde']};}}
QPushButton:pressed {{background:{c['boton_pressed']};}}
QPushButton:disabled {{color:{c['boton_disabled_texto']}; background:{c['boton_disabled_fondo']}; border:1px solid {c['boton_disabled_borde']};}}
QPushButton#primary {{background:{c['primario']}; color:#ffffff; border:0; font-weight:600;}}
QPushButton#primary:hover {{background:{c['primario_hover']}; border:0;}}
QPushButton#primary:pressed {{background:{c['primario_pressed']}; border:0;}}
QPushButton#primary:disabled {{background:{c['primario_disabled_fondo']}; color:{c['primario_disabled_texto']}; border:0;}}
QPushButton#danger {{background:{c['peligro']}; color:#ffffff; border:0; font-weight:600;}}
QPushButton#danger:hover {{background:{c['peligro_hover']}; border:0;}}
QPushButton#danger:pressed {{background:{c['peligro_pressed']}; border:0;}}
QPushButton#danger:disabled {{background:{c['peligro_disabled_fondo']}; color:{c['peligro_disabled_texto']}; border:0;}}
QPushButton#ghost {{background:transparent; border:1px solid {c['ghost_borde']}; color:{c['ghost_texto']}; padding:8px 12px;}}
QPushButton#ghost:hover {{background:{c['ghost_hover_fondo']}; color:{c['ghost_hover_texto']}; border:1px solid {c['ghost_borde']};}}
QPushButton#ghost:disabled {{color:{c['ghost_disabled_texto']}; background:transparent; border:1px solid {c['boton_disabled_borde']};}}
QPushButton#nav {{text-align:left; border:0; background:transparent; padding:11px 16px; color:{c['nav_texto']}; border-radius:8px;}}
QPushButton#nav:hover {{background:{c['nav_hover_fondo']}; color:{c['nav_hover_texto']}; border:0;}}
QPushButton#nav:checked {{background:{c['nav_checked_fondo']}; color:{c['nav_checked_texto']}; font-weight:600; border:0;}}
QPushButton#nav:disabled {{color:{c['nav_disabled_texto']}; background:transparent; border:0;}}
QPushButton#theme_toggle, QPushButton#toggle_tema {{background:{c['toggle_fondo']}; color:{c['toggle_texto']}; border:1px solid {c['toggle_borde']}; border-radius:8px; padding:8px 12px; font-weight:600;}}
QPushButton#theme_toggle:hover, QPushButton#toggle_tema:hover {{background:{c['toggle_hover_fondo']}; border:1px solid {c['toggle_hover_borde']}; color:{c['toggle_hover_texto']};}}
QPushButton#theme_toggle:checked, QPushButton#toggle_tema:checked {{background:{c['toggle_checked_fondo']}; border:1px solid {c['toggle_checked_borde']}; color:{c['toggle_checked_texto']};}}
QPushButton#theme_toggle:disabled, QPushButton#toggle_tema:disabled {{color:{c['boton_disabled_texto']}; background:{c['boton_disabled_fondo']}; border:1px solid {c['boton_disabled_borde']};}}
QFrame#lateral {{background:#0a1f5c; border:0;}}
QFrame#lateral QLabel {{background:transparent; color:#c7d5f5;}}
QFrame#lateral QLabel#lateral_marca {{color:#ffffff; font-size:17px; font-weight:700;}}
QFrame#lateral QLabel#lateral_tenue {{color:#a9bbe6; font-size:11px; font-weight:500;}}
QFrame#lateral QLabel#lateral_grupo {{color:#8ea3d6; font-size:10px; font-weight:700; padding:0 12px 4px 12px;}}
QFrame#lateral QLabel#lateral_usuario {{color:#ffffff; font-size:12px; font-weight:600;}}
QFrame#lateral QLabel#lateral_avatar {{background:#00b8e6; color:#ffffff; border-radius:17px; font-size:12px; font-weight:700;}}
QFrame#lateral QFrame#lateral_linea {{background:#1d3478; border:0;}}
QFrame#lateral QFrame#lateral_tarjeta {{background:#132b6e; border:1px solid #1d3478; border-radius:10px;}}
QFrame#lateral QLabel#lateral_punto {{font-size:13px;}}
QFrame#lateral QPushButton#nav {{text-align:left; padding:9px 12px; font-weight:500; color:#c7d5f5; background:transparent; border:0; border-radius:8px;}}
QFrame#lateral QPushButton#nav:hover {{background:#132b6e; color:#ffffff;}}
QFrame#lateral QPushButton#nav:checked {{background:#2875e8; color:#ffffff; font-weight:600;}}
QFrame#lateral QPushButton#nav:disabled {{color:#5c73ad; background:transparent;}}
QFrame#lateral QPushButton#lateral_icono {{background:transparent; border:0; padding:0; border-radius:8px;}}
QFrame#lateral QPushButton#lateral_icono:hover {{background:#132b6e;}}
QWidget#pagina_frases QLabel, QWidget#pagina_frases QPushButton, QWidget#pagina_frases QLineEdit, QWidget#pagina_frases QTextEdit, QWidget#pagina_frases QComboBox {{font-weight:500;}}
QWidget#pagina_frases QLabel#heading, QWidget#pagina_frases QLabel#section, QWidget#pagina_frases QPushButton#primary {{font-weight:700;}}
QWidget#pagina_frases QLabel#muted {{color:#475569;}}
QLabel#filtro_grupo {{color:#475569; font-size:11px; font-weight:700; padding:6px 10px 4px 10px;}}
QPushButton#filtro {{text-align:left; background:transparent; border:0; border-radius:7px; padding:8px 10px; font-weight:500;}}
QPushButton#filtro:hover {{background:{c['nav_hover_fondo']}; border:0;}}
QPushButton#filtro:checked {{background:{c['nav_checked_fondo']}; color:{c['nav_checked_texto']}; font-weight:700;}}
QPushButton#enlace {{background:transparent; border:0; padding:6px 8px; color:#334155;}}
QPushButton#enlace:hover {{background:{c['nav_hover_fondo']}; border:0;}}
QPushButton#enlace:disabled {{background:transparent; border:0; color:{c['boton_disabled_texto']};}}
QPushButton#variable {{border-radius:14px; padding:5px 12px;}}
QWidget#pagina_frases QLabel#titulo_editor {{font-size:18px; font-weight:700;}}
QWidget#pagina_frases QLabel#estado_propia, QWidget#pagina_frases QLabel#estado_compartida, QWidget#pagina_frases QLabel#estado_nueva {{border-radius:11px; padding:0 11px; font-size:12px; font-weight:600;}}
QWidget#pagina_frases QLabel#estado_propia {{background:#e8f0fe; color:#1d5fd1;}}
QWidget#pagina_frases QLabel#estado_compartida {{background:#eef2f7; color:#334155;}}
QWidget#pagina_frases QLabel#estado_nueva {{background:#fff4e0; color:#8a4d00;}}
QFrame#separador_editor {{background:{c['lista_borde_item']}; border:0;}}
QFrame#barra_acciones {{background:{c['campo_fondo']}; border:1px solid {c['campo_borde']}; border-radius:9px;}}
QPushButton#segmento, QPushButton#segmento_peligro {{background:transparent; border:0; border-radius:0; padding:6px 8px; color:#0a1f5c;}}
QPushButton#segmento {{border-right:1px solid {c['campo_borde']};}}
QPushButton#segmento_peligro {{color:#dc2626;}}
QPushButton#segmento:hover {{background:{c['nav_hover_fondo']};}}
QPushButton#segmento_peligro:hover {{background:#fef2f2;}}
QPushButton#segmento:disabled, QPushButton#segmento_peligro:disabled {{background:transparent; color:#a8b3c4;}}
QDialogButtonBox QPushButton {{min-width:84px;}}
QLineEdit, QTextEdit, QComboBox, QSpinBox {{background:{c['campo_fondo']}; color:{c['texto']}; border:1px solid {c['campo_borde']}; border-radius:7px; padding:10px; selection-background-color:{c['primario']}; selection-color:#ffffff;}}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {{border:1px solid {c['primario']};}}
QLineEdit:disabled, QTextEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{background:{c['campo_disabled_fondo']}; color:{c['campo_disabled_texto']}; border:1px solid {c['boton_disabled_borde']};}}
QLineEdit[readOnly="true"], QTextEdit[readOnly="true"] {{background:{c['campo_readonly_fondo']}; color:{c['campo_readonly_texto']};}}
QComboBox {{padding-right:44px; combobox-popup:0;}}
QComboBox::drop-down {{subcontrol-origin:padding; subcontrol-position:center right; width:26px; height:26px; right:6px; border:0; border-radius:7px; background:#0a1f5c;}}
QComboBox::drop-down:disabled {{background:#a3acc4;}}
QComboBox::down-arrow {{image:url("{_FLECHA}"); width:14px; height:14px;}}
QComboBox QAbstractItemView {{background-color:{c['popup_fondo']}; color:{c['texto']}; border:1px solid {c['popup_borde']}; selection-background-color:{c['popup_sel_fondo']}; selection-color:{c['popup_sel_texto']}; outline:0; padding:4px;}}
QComboBox QAbstractItemView::item {{padding:8px 12px; min-height:24px;}}
QComboBox QAbstractItemView::item:selected {{background:{c['popup_sel_fondo']}; color:{c['popup_sel_texto']}; border-radius:6px;}}
QListWidget {{background:{c['panel']}; color:{c['texto']}; border:0; outline:0;}}
QListWidget::item {{padding:16px 18px; border-bottom:1px solid {c['lista_borde_item']}; color:{c['texto']};}}
QListWidget::item:selected {{background:{c['lista_sel_fondo']}; color:{c['lista_sel_texto']}; border-left:3px solid {c['primario']};}}
QListWidget::item:selected:!active {{background:{c['lista_sel_inactiva_fondo']}; color:{c['lista_sel_texto']}; border-left:3px solid {c['primario']};}}
QListWidget::item:hover {{background:{c['lista_hover_fondo']};}}
QTextEdit#preview {{background:{c['preview_fondo']}; color:{c['preview_texto']}; border:1px solid {c['preview_borde']};}}
QMenu {{background:{c['menu_fondo']}; color:{c['texto']}; border:1px solid {c['menu_borde']}; border-radius:8px; padding:6px;}}
QMenu::item {{background:transparent; color:{c['texto']}; padding:8px 18px; border-radius:6px;}}
QMenu::item:selected {{background:{c['menu_sel_fondo']}; color:{c['menu_sel_texto']};}}
QMenu::item:disabled {{color:{c['menu_disabled_texto']};}}
QMenu::separator {{height:1px; background:{c['borde']}; margin:4px 8px;}}
QToolTip {{background:{c['tooltip_fondo']}; color:{c['tooltip_texto']}; border:1px solid {c['tooltip_borde']}; border-radius:6px; padding:6px 10px;}}
QSplitter::handle {{background:transparent; width:20px;}}
QScrollBar:vertical {{background:{c['scroll_track']}; width:10px; margin:0;}}
QScrollBar::handle:vertical {{background:{c['scroll_handle']}; border-radius:5px; min-height:35px;}}
QScrollBar::handle:vertical:hover {{background:{c['scroll_handle_hover']};}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{height:0;}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{background:transparent;}}
QScrollBar:horizontal {{background:{c['scroll_track']}; height:10px; margin:0;}}
QScrollBar::handle:horizontal {{background:{c['scroll_handle']}; border-radius:5px; min-width:35px;}}
QScrollBar::handle:horizontal:hover {{background:{c['scroll_handle_hover']};}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{width:0;}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{background:transparent;}}
'''


ESTILO = hoja_estilo('claro')
ESTILO_OSCURO = hoja_estilo('oscuro')
