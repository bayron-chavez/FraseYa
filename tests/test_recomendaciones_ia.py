from unittest.mock import Mock
import pytest
from fraseya.aplicacion.recomendaciones_ia import preparar, RecomendadorIA
from fraseya.infraestructura.supabase import ErrorSupabase


def frases():
    return [{'id': 1, 'titulo': 'Pedido', 'abreviatura': '!pedido', 'categoria': 'Ventas',
             'origen': 'propia', 'contenido': 'Tu pedido llegará el {fecha}.'}]


def test_conserva_contenido_original_y_no_envia_datos_de_sesion():
    cliente = Mock()
    cliente.solicitar.return_value = {'sugerencias': [{'id': 1, 'motivo': 'Consulta sobre entrega.'}]}
    resultado = RecomendadorIA(cliente).sugerir('¿Dónde está mi pedido?', frases())
    assert resultado[0].frase['contenido'] == 'Tu pedido llegará el {fecha}.'
    enviado = cliente.solicitar.call_args.args[2]
    assert set(enviado) == {'mensaje', 'frases'}
    assert set(enviado['frases'][0]) == {'id','titulo','categoria','contenido'}


@pytest.mark.parametrize('salida', [
    {'sugerencias': [{'id': 99, 'motivo': 'Inventada'}]},
    {'sugerencias': [{'id': True, 'motivo': 'Booleana'}]},
    {'sugerencias': [{'id': 1, 'motivo': 'Una'}, {'id': 1, 'motivo': 'Repetida'}]},
    {'sugerencias': [{'id': 1, 'motivo': 'x' * 241}]},
    {'sugerencias': [{'id': 1, 'motivo': 'Una', 'contenido': 'Otra respuesta'}]},
    {'sugerencias': [], 'token': 'no permitido'},
])
def test_rechaza_ids_inventados_y_modificaciones(salida):
    cliente = Mock(); cliente.solicitar.return_value = salida
    with pytest.raises(ValueError):
        RecomendadorIA(cliente).sugerir('Pedido', frases())


def test_limite_local_no_envia_sexta_peticion():
    cliente = Mock(); cliente.solicitar.return_value = {'sugerencias': []}
    servicio = RecomendadorIA(cliente)
    for _ in range(5): servicio.sugerir('Pedido', frases())
    with pytest.raises(ValueError): servicio.sugerir('Pedido', frases())
    assert cliente.solicitar.call_count == 5


@pytest.mark.parametrize('mensaje', ['', 'x' * 4001])
def test_validacion_no_consulta(mensaje):
    cliente = Mock()
    with pytest.raises(ValueError): RecomendadorIA(cliente).sugerir(mensaje, frases())
    cliente.solicitar.assert_not_called()


def test_preseleccion_acotada_prioriza_contexto():
    catalogo = [dict(frases()[0], id=i, titulo='Otra', contenido='Sin coincidencia') for i in range(2, 102)] + frases()
    pedido, seleccion = preparar('pedido', catalogo)
    assert len(seleccion) == 40 and pedido['frases'][0]['id'] == 1


def test_servicio_no_configurado_mensaje_claro():
    cliente = Mock(); cliente.solicitar.side_effect = ErrorSupabase('Error genérico', 503)
    with pytest.raises(ErrorSupabase, match='configurada'):
        RecomendadorIA(cliente).sugerir('Pedido', frases())
