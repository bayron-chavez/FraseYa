"""Icono de bandeja; sus acciones se entregan a Tk mediante una cola."""
from PIL import Image, ImageDraw
import pystray
from .identidad import recurso


class Bandeja:
    def __init__(self, eventos):
        self.eventos = eventos
        self.icono = pystray.Icon('FraseYa', self._imagen('pendiente'), 'FraseYa', menu=pystray.Menu(
            pystray.MenuItem('Abrir FraseYa', lambda *_: eventos.put('abrir'), default=True),
            pystray.MenuItem('Sincronizar ahora', lambda *_: eventos.put('sincronizar')),
            pystray.MenuItem('Salir', lambda *_: eventos.put('salir'))))

    @staticmethod
    def _imagen(estado):
        color = {'error': '#B91C1C', 'offline': '#64748B', 'comprobando': '#D97706',
                 'actualizada': '#15803D', 'sin_cambios': '#15803D'}.get(estado, '#2563EB')
        with Image.open(recurso('logo.png')) as original:
            imagen = original.convert('RGBA').resize((64, 64), Image.Resampling.LANCZOS)
        dibujo = ImageDraw.Draw(imagen)
        dibujo.ellipse((44, 44, 63, 63), fill=color, outline='white', width=2)
        return imagen

    def iniciar(self):
        self.icono.run_detached()

    def actualizar(self, estado, texto):
        self.icono.icon = self._imagen(estado)
        self.icono.title = ('FraseYa · ' + texto.replace('\n', ' · '))[:127]

    def detener(self):
        self.icono.stop()
