from datetime import date

import pytest

from fraseya.aplicacion import resolver_variables as rv
from fraseya.dominio import Frase


def test_detecta_marcadores_en_orden_y_sin_repetir():
    assert rv.detectar('Hola {nombre}, orden {orden}. Adiós {nombre}.') == ['nombre', 'orden']


def test_detecta_los_cuatro_marcadores_del_requerimiento():
    assert rv.detectar('{nombre} {orden} {monto} {fecha}') == ['nombre', 'orden', 'monto', 'fecha']


def test_sin_marcadores_no_hay_nada_que_pedir():
    assert rv.detectar('Buenos días') == []


def test_coincide_con_las_variables_que_calcula_el_dominio():
    contenido = 'Gracias {nombre}, su caso {orden} por {monto} el {fecha}. {nombre}'
    assert rv.detectar(contenido) == [v.nombre for v in Frase('T', 'a', contenido).variables]


def test_sustituye_todas_las_apariciones():
    assert rv.sustituir('{a} y {a} y {b}', {'a': '1', 'b': '2'}) == '1 y 1 y 2'


def test_un_valor_con_llaves_no_se_vuelve_a_sustituir():
    assert rv.sustituir('Hola {nombre}', {'nombre': '{orden}', 'orden': 'X'}) == 'Hola {orden}'


def test_marcador_sin_valor_se_deja_igual():
    assert rv.sustituir('Hola {nombre}', {}) == 'Hola {nombre}'


def test_fecha_viene_prellenada_con_hoy():
    assert rv.valores_iniciales(['nombre', 'fecha'], date(2026, 10, 2)) == {'fecha': '02/10/2026'}
    assert rv.valores_iniciales(['nombre']) == {}


def test_faltantes_incluye_vacios_y_espacios():
    assert rv.faltantes(['a', 'b', 'c'], {'a': 'x', 'b': '   '}) == ['b', 'c']


def test_sin_marcadores_la_insercion_es_inmediata_y_no_abre_formulario():
    def no_debe_llamarse(*_):
        raise AssertionError('No debe abrirse el formulario')

    assert rv.resolver('Buenos días, ¿en qué puedo ayudarle?', no_debe_llamarse) == \
        'Buenos días, ¿en qué puedo ayudarle?'


def test_resuelve_con_los_valores_del_formulario():
    pedidos = []

    def formulario(nombres, iniciales):
        pedidos.append(nombres)
        return {'nombre': ' Ana ', 'orden': '1234'}

    assert rv.resolver('Gracias {nombre}, su caso {orden} quedó registrado.', formulario) == \
        'Gracias Ana, su caso 1234 quedó registrado.'
    assert pedidos == [['nombre', 'orden']]


def test_el_formulario_recibe_la_fecha_de_hoy_como_sugerencia():
    recibido = {}

    def formulario(nombres, iniciales):
        recibido.update(iniciales)
        return {'fecha': iniciales['fecha']}

    rv.resolver('Pago el {fecha}', formulario)
    assert recibido['fecha'] == date.today().strftime('%d/%m/%Y')


def test_cancelar_el_formulario_no_inserta_nada():
    assert rv.resolver('Hola {nombre}', lambda *_: None) is None


def test_valores_incompletos_se_rechazan_con_todos_los_nombres():
    with pytest.raises(ValueError) as e:
        rv.resolver('{a} {b} {c}', lambda *_: {'a': 'x', 'b': '', 'c': ' '})
    assert 'b, c' in str(e.value)
