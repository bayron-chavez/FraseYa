from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock
import pytest
from fraseya.aplicacion.limite_acceso import LimiteAcceso
from fraseya.infraestructura.supabase import ClienteSupabase, ErrorSupabase


def test_limite_no_envia_sexto_intento_y_rotar_correo_no_lo_evade():
    reloj = [0]
    transporte = Mock(side_effect=ErrorSupabase('Credenciales inválidas', 400))
    cliente = ClienteSupabase('https://ejemplo.supabase.co', 'sb_publishable_prueba', transporte)
    cliente.limite_acceso = LimiteAcceso(reloj=lambda: reloj[0])
    for n in range(5):
        with pytest.raises(ErrorSupabase, match='Correo o contraseña incorrectos'):
            cliente.entrar(f'{n}@example.test', 'ficticia')
    with pytest.raises(ValueError, match='60 segundos'):
        cliente.entrar('otro@example.test', 'ficticia')
    assert transporte.call_count == 5
    reloj[0] = 60
    with pytest.raises(ErrorSupabase):
        cliente.entrar('otro@example.test', 'ficticia')
    assert transporte.call_count == 6


def test_429_bloquea_cinco_minutos_y_no_guarda_credenciales():
    reloj = [0]
    cliente = ClienteSupabase('https://ejemplo.supabase.co', 'sb_publishable_prueba',
        Mock(side_effect=ErrorSupabase('Demasiados intentos', 429)))
    cliente.limite_acceso = LimiteAcceso(reloj=lambda: reloj[0])
    with pytest.raises(ErrorSupabase):
        cliente.entrar('u@example.test', 'secreto')
    with pytest.raises(ValueError, match='300 segundos'):
        cliente.entrar('u@example.test', 'secreto')
    assert cliente._access is None and cliente._refresh is None


def test_concurrencia_no_supera_presupuesto():
    limite = LimiteAcceso(reloj=lambda: 0)
    def intentar(_):
        try:
            limite.reservar()
            return 1
        except ValueError:
            return 0
    with ThreadPoolExecutor(max_workers=20) as pool:
        assert sum(pool.map(intentar, range(100))) == 5


def test_intento_bloqueado_no_conserva_token_de_cuenta_anterior():
    cliente = ClienteSupabase('https://ejemplo.supabase.co', 'sb_publishable_prueba', Mock())
    cliente._guardar_tokens({'access_token': 'anterior', 'refresh_token': 'r', 'expires_in': 3600})
    cliente.limite_acceso.bloquear()
    with pytest.raises(ValueError, match='Demasiados intentos'):
        cliente.entrar('otra@example.test', 'ficticia')
    assert cliente._access is None and cliente._refresh is None


@pytest.mark.parametrize('correo,clave', [('', 'x'), ('u@example.test', ''), (None, 'x'), ('x'*255, 'x')])
def test_campos_invalidos_no_envian_peticion(correo, clave):
    transporte = Mock()
    cliente = ClienteSupabase('https://ejemplo.supabase.co', 'sb_publishable_prueba', transporte)
    with pytest.raises(ValueError):
        cliente.entrar(correo, clave)
    transporte.assert_not_called()
