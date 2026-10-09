import pytest

from fraseya.aplicacion.gestion_frases import GestionFrases, ErroresValidacion
from fraseya.aplicacion.buscador import buscar
from fraseya.infraestructura import RepositorioSQLite


def crear(g, abrev='!saludo'):
    return g.crear('Saludo', abrev, 'Hola {nombre}', g.categorias_propias()[0]['id'])


def test_favoritas_persisten_y_siguen_edicion(tmp_path):
    ruta = tmp_path / 'frases.db'
    with RepositorioSQLite(ruta) as repo:
        g = GestionFrases(repo)
        ident = crear(g)
        assert g.alternar_favorita(ident)
        g.editar(ident, 'Nuevo saludo', '!nuevo', 'Hola', g.categorias_propias()[0]['id'])
    with RepositorioSQLite(ruta) as repo:
        g = GestionFrases(repo)
        assert g.listar()[0]['favorita']
        assert not g.alternar_favorita(ident)
        assert not g.listar()[0]['favorita']


def test_favorita_compartida_sobrevive_ids_de_sincronizacion():
    with RepositorioSQLite(':memory:') as repo:
        g = GestionFrases(repo)
        catalogo = [{'nombre': 'General', 'frases': [
            {'titulo': 'Central', 'abreviatura': '!central', 'contenido': 'Compartida'}]}]
        repo.reemplazar_compartidas(1, 'admin', '2026-10-08', catalogo)
        g.alternar_favorita(g.listar()[0]['id'])
        repo.reemplazar_compartidas(2, 'admin', '2026-10-08', catalogo)
        frase = next(f for f in g.listar() if f['origen'] == 'compartida')
        assert frase['favorita']
        with pytest.raises(PermissionError):
            g.eliminar(frase['id'])
        assert not g.puede_deshacer()
        assert repo.obtener_frase(frase['id'])['contenido'] == 'Compartida'


def test_deshacer_recupera_frase_variables_y_favorita_una_sola_vez():
    with RepositorioSQLite(':memory:') as repo:
        g = GestionFrases(repo)
        ident = crear(g)
        g.alternar_favorita(ident)
        g.eliminar(ident)
        assert g.listar() == [] and g.puede_deshacer()
        nuevo = g.deshacer_eliminacion()
        frase = repo.obtener_frase(nuevo)
        assert frase['contenido'] == 'Hola {nombre}' and frase['origen'] == 'propia'
        assert [v['nombre'] for v in frase['variables']] == ['nombre']
        assert g.listar()[0]['favorita']
        assert not g.puede_deshacer()
        with pytest.raises(ValueError):
            g.deshacer_eliminacion()


def test_deshacer_conflicto_no_sobrescribe_y_permite_reintentar():
    with RepositorioSQLite(':memory:') as repo:
        g = GestionFrases(repo)
        g.eliminar(crear(g))
        ocupado = crear(g)
        with pytest.raises(ErroresValidacion):
            g.deshacer_eliminacion()
        assert len(g.listar()) == 1 and g.puede_deshacer()
        g.editar(ocupado, 'Otra', '!otra', 'Otro texto', g.categorias_propias()[0]['id'])
        g.deshacer_eliminacion()
        assert len(g.listar()) == 2


def test_ultima_eliminacion_y_categoria_retirada():
    with RepositorioSQLite(':memory:') as repo:
        g = GestionFrases(repo)
        general = g.categorias_propias()[0]['id']
        categoria = repo.crear_categoria(g._catalogo_propio(), 'Temporal')
        primero = crear(g, '!primero')
        ultimo = g.crear('Último', '!ultimo', 'Texto', categoria)
        g.eliminar(primero)
        g.eliminar(ultimo)
        repo.eliminar_categoria(categoria)
        ident = g.deshacer_eliminacion()
        assert repo.obtener_frase(ident)['categoria_id'] == general
        assert g.listar()[0]['abreviatura'] == '!ultimo'


def test_favoritas_primero_sin_incluir_frases_que_no_coinciden():
    frases = [
        {'titulo': 'A', 'abreviatura': 'a', 'contenido': 'saludo'},
        {'titulo': 'Z', 'abreviatura': 'z', 'contenido': 'saludo', 'favorita': True},
        {'titulo': 'Otra', 'abreviatura': 'otra', 'contenido': 'distinto', 'favorita': True},
    ]
    assert [f['titulo'] for f in buscar(frases, 'saludo')] == ['Z', 'A']
