"""Fachada de compatibilidad para lectura de WhatsApp (UIA + puente local HTTP)."""
from .puente_wsp import (
    HOST_PUENTE_WSP,
    MAX_CUERPO_PUENTE,
    MAX_LARGO_MENSAJE,
    ORIGEN_WHATSAPP_WEB,
    PUERTO_PUENTE_WSP,
    PuenteWhatsAppWeb,
)
from .uia_whatsapp import (
    DiagnosticoLectura,
    LectorChat,
    VentanaChat,
    es_ventana_whatsapp,
)

__all__ = [
    'HOST_PUENTE_WSP',
    'MAX_CUERPO_PUENTE',
    'MAX_LARGO_MENSAJE',
    'ORIGEN_WHATSAPP_WEB',
    'PUERTO_PUENTE_WSP',
    'PuenteWhatsAppWeb',
    'DiagnosticoLectura',
    'LectorChat',
    'VentanaChat',
    'es_ventana_whatsapp',
]
