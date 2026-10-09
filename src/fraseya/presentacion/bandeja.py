"""Icono de bandeja; sus acciones se entregan a Tk mediante una cola."""
from PIL import Image, ImageDraw
import pystray


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
        imagen = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        dibujo = ImageDraw.Draw(imagen)
        dibujo.rounded_rectangle((4, 4, 60, 60), radius=12, fill=color)
        dibujo.line((23, 48, 23, 17, 44, 17), fill='white', width=6)
        dibujo.line((23, 31, 39, 31), fill='white', width=6)
        return imagen

    def iniciar(self):
        self.icono.run_detached()

    def actualizar(self, estado, texto):
        self.icono.icon = self._imagen(estado)
        self.icono.title = ('FraseYa · ' + texto.replace('\n', ' · '))[:127]

    def detener(self):
        self.icono.stop()
