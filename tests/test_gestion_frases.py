import pytest

from fraseya.aplicacion.gestion_frases import ErroresValidacion, GestionFrases
from fraseya.infraestructura import RepositorioSQLite


@pytest.fixture
def gestion():
    with RepositorioSQLite(':memory:') as repo:
        yield GestionFrases(repo)


def categoria(gestion):
    return gestion.categorias_propias()[0]['id']


def compartida(gestion, abreviatura='sal'):
    gestion.repo.reemplazar_compartidas(1, 'admin', '2026-10-01', [
        {'nombre': 'Normativa', 'color': '#112233',
         'frases': [{'titulo': 'Saludo', 'abreviatura': abreviatura, 'contenido': 'Hola {nombre}'}]}])
    return next(f for f in gestion.listar() if f['origen'] == 'compartida')['id']


def test_crea_categoria_general_si_no_hay(gestion):
    assert [c['nombre'] for c in gestion.categorias_propias()] == ['General']
    assert len(gestion.categorias_propias()) == 1  # idempotente


def test_crear_editar_y_listar_con_categoria(gestion):
    ident = gestion.crear('Saludo', 'hola', 'Hola {nombre}', categoria(gestion))
    gestion.editar(ident, 'Saludo formal', 'hola', 'Estimado {nombre}', categoria(gestion))
    frase = gestion.listar()[0]
    assert (frase['titulo'], frase['categoria'], [v['nombre'] for v in frase['variables']]) == \
           ('Saludo formal', 'General', ['nombre'])


def test_abreviatura_unica_sin_distinguir_mayusculas(gestion):
    gestion.crear('A', 'hola', 'x', categoria(gestion))
    with pytest.raises(ValueError, match='ya está en uso'):
        gestion.crear('B', 'HOLA', 'y', categoria(gestion))


def test_editar_conservando_su_propia_abreviatura_no_es_conflicto(gestion):
    ident = gestion.crear('A', 'hola', 'x', categoria(gestion))
    gestion.editar(ident, 'A2', 'hola', 'y', categoria(gestion))


def test_abreviatura_no_puede_chocar_con_una_compartida(gestion):
    compartida(gestion, 'sal')
    with pytest.raises(ValueError, match='ya está en uso'):
        gestion.crear('X', 'sal', 'y', categoria(gestion))


@pytest.mark.parametrize('abreviatura', ['', '   ', 'dos palabras'])
def test_abreviatura_invalida(gestion, abreviatura):
    with pytest.raises(ValueError):
        gestion.crear('A', abreviatura, 'x', categoria(gestion))


@pytest.mark.parametrize('titulo,contenido', [('', 'x'), ('A', '  ')])
def test_titulo_y_contenido_obligatorios(gestion, titulo, contenido):
    with pytest.raises(ValueError):
        gestion.crear(titulo, 'a', contenido, categoria(gestion))


def test_compartidas_son_de_solo_lectura(gestion):
    ident = compartida(gestion)
    with pytest.raises(PermissionError):
        gestion.editar(ident, 'T', 'sal', 'x', categoria(gestion))
    with pytest.raises(PermissionError):
        gestion.eliminar(ident)
    assert gestion.repo.obtener_frase(ident)['contenido'] == 'Hola {nombre}'


def test_duplicar_compartida_crea_propia_editable(gestion):
    copia = gestion.duplicar(compartida(gestion))
    frase = gestion.repo.obtener_frase(copia)
    assert frase['origen'] == 'propia' and frase['abreviatura'] == 'sal2'
    assert frase['contenido'] == 'Hola {nombre}'
    gestion.editar(copia, 'Mi saludo', 'sal2', 'Buenas', categoria(gestion))


def test_duplicar_propia_mantiene_categoria_y_evita_colisiones(gestion):
    ident = gestion.crear('A', 'a', 'x', categoria(gestion))
    gestion.duplicar(ident)
    assert gestion.repo.obtener_frase(gestion.duplicar(ident))['abreviatura'] == 'a3'


def test_eliminar_propia(gestion):
    ident = gestion.crear('A', 'a', 'x', categoria(gestion))
    gestion.eliminar(ident)
    assert gestion.listar() == []


def test_no_se_puede_guardar_propia_en_categoria_compartida(gestion):
    compartida(gestion)
    cat_compartida = next(c for c in gestion.repo.listar_categorias() if c['nombre'] == 'Normativa')['id']
    with pytest.raises(ValueError, match='categoría propia'):
        gestion.crear('A', 'a', 'x', cat_compartida)


def test_filtrado_por_texto_y_categoria(gestion):
    gestion.crear('Saludo', 'hola', 'Buenos días', categoria(gestion))
    gestion.crear('Cierre', 'chao', 'Hasta luego', categoria(gestion))
    assert [f['abreviatura'] for f in gestion.listar('LUEGO')] == ['chao']
    assert [f['abreviatura'] for f in gestion.listar('general')] == ['chao', 'hola']
    assert gestion.listar(categoria_id=categoria(gestion) + 99) == []


def test_las_propias_sobreviven_a_la_sincronizacion(gestion):
    gestion.crear('Mía', 'mia', 'x', categoria(gestion))
    compartida(gestion)
    assert {f['abreviatura'] for f in gestion.listar() if f['origen'] == 'propia'} == {'mia'}


def test_muestra_todos_los_errores_juntos(gestion):
    with pytest.raises(ErroresValidacion) as e:
        gestion.crear('', 'dos palabras', '  ', categoria(gestion))
    assert e.value.errores == ['El título no puede estar vacío.',
                               'La abreviatura no puede contener espacios.',
                               'El contenido no puede estar vacío.']
    assert str(e.value).count(' | ') == 2
    assert gestion.listar() == []


def test_un_solo_error_se_informa_solo(gestion):
    with pytest.raises(ErroresValidacion) as e:
        gestion.crear('A', 'a', '', categoria(gestion))
    assert e.value.errores == ['El contenido no puede estar vacío.']


def test_edicion_tambien_junta_los_errores(gestion):
    ident = gestion.crear('A', 'a', 'x', categoria(gestion))
    gestion.crear('B', 'b', 'y', categoria(gestion))
    with pytest.raises(ErroresValidacion) as e:
        gestion.editar(ident, '', 'B', '', categoria(gestion))
    assert len(e.value.errores) == 3 and 'ya está en uso' in e.value.errores[1]
