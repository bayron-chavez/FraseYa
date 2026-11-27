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


def test_preparar_conserva_turnos_cliente_agente_en_mensaje():
    catalogo = [
        dict(frases()[0], id=1, titulo='Pedido', contenido='Tu pedido llegará el {fecha}.'),
        dict(frases()[0], id=2, titulo='Cliente VIP', contenido='Atención preferencial para el cliente y agente.'),
    ]
    hilo = 'Cliente: Hola\nAgente: ¿En qué te ayudo?\nCliente: ¿Dónde está mi pedido?'
    pedido, _ = preparar(hilo, catalogo)
    assert pedido['mensaje'] == hilo
    assert pedido['frases'][0]['id'] == 1


def test_preranking_ignora_stopwords_usa_sinonimos_y_prioriza_ultimo_cliente():
    catalogo = [
        {'id': 10, 'titulo': 'Saludo general', 'abreviatura': '!hola', 'categoria': 'General', 'contenido': 'Hola buenos días, con mucho gusto'},
        {'id': 11, 'titulo': 'Tarifas y planes', 'abreviatura': '!tarifas', 'categoria': 'Ventas', 'contenido': 'Nuestros valores y costos vigentes de servicios'},
        {'id': 12, 'titulo': 'Soporte previo', 'abreviatura': '!sop', 'categoria': 'Soporte', 'contenido': 'Reinicia tu router wifi para verificar conexión'},
    ]
    hilo = 'Cliente: Tengo internet lento\nAgente: Prueba reiniciar tu router\nCliente: ¿Cuál es el precio de sus planes?'
    pedido, _ = preparar(hilo, catalogo)
    assert pedido['frases'][0]['id'] == 11


def test_asistir_valida_variantes_reales_y_hace_fallback_si_servidor_es_antiguo():
    cliente = Mock()
    cliente.solicitar.return_value = {
        'tipo': 'generadas',
        'sugerencias': [],
        'opciones': [
            {
                'tono': 'empatica',
                'titulo': 'Catálogo productos',
                'categoria': 'Ventas',
                'contenido': '¡Hola Camila! 👋 Nuestros productos son:\n  · Producto 1\n  · Producto 2\nEsos son los productos que podemos ofrecerte.',
                'motivo': 'Presentación cercana con viñetas.',
            },
            {
                'tono': 'directa',
                'titulo': 'Lista directa',
                'categoria': 'Ventas',
                'contenido': 'Nuestros productos son:\n  · Producto 1\n  · Producto 2\n¿Cuál te interesa?',
                'motivo': 'Respuesta directa.',
            },
            {
                'tono': 'escalar',
                'titulo': 'Asesoría comercial',
                'categoria': 'Ventas',
                'contenido': 'Nuestros productos son:\n  · Producto 1\n  · Producto 2\n¿Te contacto con un asesor?',
                'motivo': 'Ofrece apoyo comercial.',
            },
        ],
    }
    servicio = RecomendadorIA(cliente)
    res = servicio.asistir('¿Qué productos tienen?', frases(), contexto={'animo': 'Neutral', 'remitente': 'Camila'})
    assert res['tipo'] == 'generadas'
    assert len(res['opciones']) == 3
    enviado = cliente.solicitar.call_args.args[2]
    assert enviado['modo'] == 'asistir'
    assert enviado['contexto']['remitente'] == 'Camila'

    # Fallback ante servidor antiguo (HTTP 400 al enviar modo='asistir')
    cliente_antiguo = Mock()
    cliente_antiguo.solicitar.side_effect = [
        ErrorSupabase('Mensaje o frases inválidos.', 400),
        {'sugerencias': [{'id': 1, 'motivo': 'Coincide con entrega.'}]},
    ]
    res_fb = RecomendadorIA(cliente_antiguo).asistir('¿Dónde está mi pedido?', frases())
    assert res_fb['tipo'] == 'catalogo'
    assert res_fb['sugerencias'][0].frase['id'] == 1
