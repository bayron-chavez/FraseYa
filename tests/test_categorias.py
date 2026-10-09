from unittest.mock import Mock

import pytest

from fraseya.aplicacion.gestion_frases import GestionFrases
from fraseya.aplicacion.publicacion import ServicioPublicacion
from fraseya.infraestructura import RepositorioSQLite


def test_solo_administrador_crea_sin_duplicados():
    with RepositorioSQLite(':memory:') as repo:
        gestion = GestionFrases(repo)
        auth, sesion = Mock(), object()
        auth.validar.side_effect = PermissionError('Solo administrador')
        with pytest.raises(PermissionError):
            gestion.crear_categoria('Ventas', auth, sesion)
        assert repo.listar_categorias() == []
        auth.validar.side_effect = None
        gestion.crear_categoria(' Ventas ', auth, sesion)
        auth.validar.assert_called_with(sesion, administrador=True)
        with pytest.raises(ValueError, match='Ya existe'):
            gestion.crear_categoria('VENTAS', auth, sesion)
        with pytest.raises(ValueError):
            gestion.crear_categoria(' ', auth, sesion)


def test_categoria_vacia_se_publica_y_usuario_puede_usarla():
    with RepositorioSQLite(':memory:') as repo:
        gestion = GestionFrases(repo)
        gestion.crear_categoria('Ventas', Mock(), object())
        servicio = ServicioPublicacion(repo, 'supabase', 'admin')
        aporte = servicio.recoger_categorias()
        fusion = servicio._fusionar([], aporte)
        assert any(c['nombre'] == 'Ventas' and c['frases'] == [] for c in fusion)
        with RepositorioSQLite(':memory:') as otro:
            otro.reemplazar_compartidas(1, 'admin', '2026-10-05', fusion)
            usuario = GestionFrases(otro)
            ventas = next(c for c in usuario.categorias_propias() if c['nombre'] == 'Ventas')
            usuario.crear('Saludo', 'sal', 'Hola', ventas['id'])
            usuario.categorias_propias()
            assert len([c for c in usuario.categorias_propias() if c['nombre'] == 'Ventas']) == 1
            assert usuario.listar()[0]['categoria'] == 'Ventas'


def test_fusion_conserva_frases_y_categorias_anteriores():
    anteriores = [{'nombre': 'General', 'color': '#64748B', 'frases': [
        {'titulo': 'Hola', 'abreviatura': 'hola', 'contenido': 'Hola'}]}]
    nuevas = [{'nombre': 'Ventas', 'color': '#64748B', 'frases': []}]
    fusion = ServicioPublicacion._fusionar(anteriores, nuevas)
    assert fusion[0] == anteriores[0]
    assert fusion[1] == nuevas[0]


def test_editar_color_renombrar_y_eliminar_categoria_vacia():
    with RepositorioSQLite(':memory:') as repo:
        gestion = GestionFrases(repo)
        auth, sesion = Mock(), object()
        ident = gestion.crear_categoria('Ventas', auth, sesion)
        gestion.editar_categoria(ident, 'Comercial', '#123456', auth, sesion)
        assert repo.obtener_categoria(ident)['nombre'] == 'Comercial'
        assert repo.obtener_categoria(ident)['color'] == '#123456'
        gestion.editar_categoria(ident, '', '#123456', auth, sesion, eliminar=True)
        assert not any(c['nombre'] in ('Ventas', 'Comercial') for c in gestion.categorias_propias())
        assert len(gestion.operaciones_categorias()) == 2


def test_no_elimina_categoria_ocupada_o_usuario_no_autorizado():
    with RepositorioSQLite(':memory:') as repo:
        gestion = GestionFrases(repo)
        auth, sesion = Mock(), object()
        ident = gestion.crear_categoria('Ventas', auth, sesion)
        gestion.crear('Hola', 'hola', 'Hola', ident)
        with pytest.raises(ValueError, match='contiene frases'):
            gestion.editar_categoria(ident, '', '#123456', auth, sesion, eliminar=True)
        auth.validar.side_effect = PermissionError('Solo admin')
        with pytest.raises(PermissionError):
            gestion.editar_categoria(ident, 'Otra', '#123456', auth, sesion)
        assert repo.obtener_categoria(ident)['nombre'] == 'Ventas'


def test_espejos_reciben_color_y_no_republican_categorias_vacias_antiguas():
    with RepositorioSQLite(':memory:') as repo:
        gestion = GestionFrases(repo)
        repo.reemplazar_compartidas(1, 'admin', '2026-10-08', [{'nombre': 'Ventas', 'color': '#112233', 'frases': []}])
        ventas = next(c for c in gestion.categorias_propias() if c['nombre'] == 'Ventas')
        repo.reemplazar_compartidas(2, 'admin', '2026-10-08', [{'nombre': 'Ventas', 'color': '#445566', 'frases': []}])
        ventas_actual = next(c for c in gestion.categorias_propias() if c['nombre'] == 'Ventas')
        assert ventas_actual['id'] == ventas['id']
        assert ventas_actual['color'] == '#445566'
        repo.reemplazar_compartidas(3, 'admin', '2026-10-08', [{'nombre': 'Comercial', 'color': '#445566', 'frases': []}])
        assert not any(c['nombre'] == 'Ventas' for c in gestion.categorias_propias())
        aporte = ServicioPublicacion(repo, 'supabase', 'admin').recoger_categorias()
        assert not any(c['nombre'] in ('Ventas', 'Comercial') for c in aporte)


def test_cambio_color_admin_no_es_revertido_por_cache_compartida():
    with RepositorioSQLite(':memory:') as repo:
        gestion = GestionFrases(repo)
        repo.reemplazar_compartidas(1, 'admin', '2026-10-08', [{'nombre': 'Ventas', 'color': '#112233', 'frases': []}])
        ident = next(c for c in gestion.categorias_propias() if c['nombre'] == 'Ventas')['id']
        gestion.editar_categoria(ident, 'Ventas', '#445566', Mock(), object())
        assert next(c for c in gestion.categorias_propias() if c['nombre'] == 'Ventas')['color'] == '#445566'
        assert next(c for c in ServicioPublicacion(repo, 'supabase', 'admin').recoger_categorias()
            if c['nombre'] == 'Ventas')['color'] == '#445566'
