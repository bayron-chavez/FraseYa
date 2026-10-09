from unittest.mock import Mock, patch
from queue import Queue
from fraseya.presentacion.bandeja import Bandeja


def test_estado_y_cierre_del_icono():
    with patch('fraseya.presentacion.bandeja.pystray.Icon') as fabrica:
        icono = Mock()
        fabrica.return_value = icono
        bandeja = Bandeja(Queue())
        bandeja.iniciar()
        icono.run_detached.assert_called_once()
        bandeja.actualizar('error', 'Versión vigente: 3\nRed inaccesible')
        assert 'Versión vigente: 3' in icono.title
        assert icono.icon.getpixel((8, 32))[:3] == (185, 28, 28)
        bandeja.detener()
        icono.stop.assert_called_once()


def test_menu_entrega_acciones_sin_llamar_a_tk_desde_otro_hilo():
    eventos = Queue()
    with patch('fraseya.presentacion.bandeja.pystray.Icon') as fabrica:
        Bandeja(eventos)
        for opcion in fabrica.call_args.kwargs['menu'].items:
            opcion(None)
        assert [eventos.get_nowait() for _ in range(3)] == ['abrir', 'sincronizar', 'salir']
