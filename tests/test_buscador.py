from fraseya.aplicacion.buscador import buscar, normalizar

FRASES = [
    {'abreviatura': 'hola', 'titulo': 'Saludo inicial', 'categoria': 'General',
     'contenido': 'Buenos días, ¿en qué puedo ayudarle?'},
    {'abreviatura': 'cierre', 'titulo': 'Despedida', 'categoria': 'General',
     'contenido': 'Gracias {nombre}, su caso {orden} quedó registrado.'},
    {'abreviatura': 'plazo', 'titulo': 'Plazo de reclamo', 'categoria': 'Normativa',
     'contenido': 'El plazo es de {dias} días hábiles.'},
    {'abreviatura': 'ho', 'titulo': 'Horario', 'categoria': 'Atención',
     'contenido': 'Atendemos de lunes a viernes.'},
]


def abrevs(resultado):
    return [f['abreviatura'] for f in resultado]


def test_normalizar_quita_acentos_y_mayusculas():
    assert normalizar('  DÍA Ñandú Ü ') == '  dia nandu u '


def test_consulta_vacia_devuelve_todas_ordenadas_por_titulo():
    assert abrevs(buscar(FRASES, '')) == ['cierre', 'ho', 'plazo', 'hola']


def test_busca_por_cada_campo():
    assert abrevs(buscar(FRASES, 'despedida')) == ['cierre']          # título
    assert abrevs(buscar(FRASES, 'normativa')) == ['plazo']           # categoría
    assert abrevs(buscar(FRASES, 'viernes')) == ['ho']                # contenido
    assert abrevs(buscar(FRASES, 'cierre')) == ['cierre']             # abreviatura


def test_sin_acentos_ni_mayusculas():
    assert abrevs(buscar(FRASES, 'DIAS habiles')) == ['plazo']
    assert abrevs(buscar(FRASES, 'atencion')) == ['ho']


def test_todas_las_palabras_deben_coincidir_aunque_sea_en_campos_distintos():
    assert abrevs(buscar(FRASES, 'general registrado')) == ['cierre']
    assert buscar(FRASES, 'general viernes') == []


def test_la_abreviatura_exacta_va_antes_que_las_demas():
    # "ho" es abreviatura exacta de Horario y está contenida en "hola"
    assert abrevs(buscar(FRASES, 'ho'))[:2] == ['ho', 'hola']


def test_abreviatura_antes_que_titulo_y_titulo_antes_que_contenido():
    frases = [
        {'abreviatura': 'x1', 'titulo': 'Otra', 'categoria': 'c', 'contenido': 'texto reclamo'},
        {'abreviatura': 'x2', 'titulo': 'Reclamo formal', 'categoria': 'c', 'contenido': 'y'},
        {'abreviatura': 'reclamo', 'titulo': 'Z', 'categoria': 'c', 'contenido': 'y'},
    ]
    assert abrevs(buscar(frases, 'reclamo')) == ['reclamo', 'x2', 'x1']


def test_sin_resultados():
    assert buscar(FRASES, 'zzzz') == []


def test_respeta_el_limite():
    muchas = [{'abreviatura': f'a{i}', 'titulo': f'T{i}', 'categoria': 'c', 'contenido': 'x'}
              for i in range(300)]
    assert len(buscar(muchas, '', limite=50)) == 50


def test_tolera_campos_faltantes():
    assert buscar([{'abreviatura': 'a'}], 'a') == [{'abreviatura': 'a'}]


def test_el_titulo_exacto_va_antes_que_uno_que_solo_empieza_igual():
    frases = [{'abreviatura': f'a{i}', 'titulo': f'Frase {i}', 'categoria': 'c', 'contenido': 'x'}
              for i in (112, 12, 120)]
    assert abrevs(buscar(frases, 'frase 12')) == ['a12', 'a120', 'a112']
