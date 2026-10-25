from unittest.mock import Mock
import pytest
from fraseya.aplicacion.recomendaciones_ia import guardar_generada, RecomendadorIA
from fraseya.aplicacion.gestion_frases import GestionFrases
from fraseya.infraestructura import RepositorioSQLite


def test_guardado_propio_sin_conflictos_y_sin_duplicar():
    with RepositorioSQLite(':memory:') as repo:
        g = GestionFrases(repo)
        categoria = g.categorias_propias()[0]['id']
        g.crear('Anterior', '!ia', 'Anterior', categoria)
        propuesta = dict(titulo='Consulta', categoria='General', contenido='Hola {nombre}, ¿qué necesitas?')
        nueva = guardar_generada(g, propuesta)
        assert nueva['origen'] == 'propia'
        assert nueva['abreviatura'] != '!ia'
        assert guardar_generada(g, propuesta)['id'] == nueva['id']
        assert len(g.listar()) == 2


@pytest.mark.parametrize('cambio', [dict(categoria='Inventada'), dict(contenido='{Nombre}'),
                                    dict(contenido=''), dict(contenido='x'*4001), dict(origen='compartida')])
def test_respuesta_invalida_no_se_guarda(cambio):
    with RepositorioSQLite(':memory:') as repo:
        g = GestionFrases(repo)
        propuesta = dict(titulo='Consulta', categoria='General', contenido='Hola {nombre}')
        propuesta.update(cambio)
        with pytest.raises(ValueError): guardar_generada(g, propuesta)
        assert not g.listar()


def test_generacion_pide_modo_y_no_admite_sql_o_campos_extra():
    cliente = Mock()
    cliente.solicitar.return_value = dict(titulo='Consulta', categoria='General', contenido='Hola {nombre}')
    servicio = RecomendadorIA(cliente)
    frases = [dict(id=1, titulo='Base', categoria='General', contenido='Hola')]
    assert servicio.generar('Necesito ayuda', frases)['contenido'] == 'Hola {nombre}'
    assert cliente.solicitar.call_args.args[2]['modo'] == 'generar'
