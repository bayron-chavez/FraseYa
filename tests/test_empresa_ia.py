from unittest.mock import Mock
import pytest
from fraseya.aplicacion.empresa_ia import EmpresaIA, validar


def test_perfil_y_escritura_estructurada():
    perfil=dict(nombre="Empresa '; DROP TABLE prueba; --",servicios='Internet',horarios='',procedimientos='Wi-Fi o cable')
    cliente=Mock(); cliente.solicitar.return_value=perfil
    empresa=EmpresaIA(cliente)
    assert empresa.leer()==perfil
    empresa.guardar(perfil)
    assert cliente.solicitar.call_args.args==('POST','/rest/v1/rpc/fraseya_empresa_ia_guardar',{'p_perfil':perfil})


@pytest.mark.parametrize('cambio',[{'rol':'administrador'},{'nombre':'x'*201},{'servicios':None},{'procedimientos':'x'*4001}])
def test_perfil_invalido_no_llega_al_servidor(cambio):
    perfil=dict(nombre='',servicios='',horarios='',procedimientos=''); perfil.update(cambio)
    cliente=Mock()
    with pytest.raises(ValueError): EmpresaIA(cliente).guardar(perfil)
    cliente.solicitar.assert_not_called()
