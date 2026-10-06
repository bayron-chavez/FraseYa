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
