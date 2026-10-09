import time
from unittest.mock import Mock
from fraseya.presentacion.acceso import VentanaAcceso


def test_error_de_login_libera_boton_y_limpia_contrasena():
    auth = Mock()
    auth.iniciar_sesion.side_effect = ValueError('Correo o contraseña incorrectos.')
    ventana = VentanaAcceso(auth)
    ventana.withdraw()
    try:
        ventana.usuario.insert(0, 'u@example.test')
        ventana.clave.insert(0, 'ficticia')
        ventana.entrar()
        ventana.entrar()
        limite = time.monotonic()+3
        while ventana._entrando and time.monotonic() < limite:
            ventana.update()
            time.sleep(0.01)
        assert not ventana._entrando
        assert ventana.clave.get() == ''
        assert ventana.sesion is None
        assert ventana.boton_entrar.cget('state') == 'normal'
        assert auth.iniciar_sesion.call_count == 1
    finally:
        ventana.destroy()
