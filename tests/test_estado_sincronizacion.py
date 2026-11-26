from fraseya.aplicacion.estado_sincronizacion import resumen_corto, resumen_estado
from fraseya.aplicacion.servicio_sincronizacion import ResultadoSincronizacion
from fraseya.infraestructura import RepositorioSQLite


def test_estado_persiste_version_y_error_sin_perder_catalogo():
    with RepositorioSQLite(':memory:') as repo:
        assert 'Nunca' in resumen_estado(repo)[1]
        repo.reemplazar_compartidas(3, 'admin', '2026-10-08', [])
        repo.registrar_sincronizacion('error', 3, 'Red inaccesible')
        estado, texto = resumen_estado(repo)
        assert estado == 'error'
        assert 'Versión vigente: 3' in texto
        assert 'Red inaccesible' in texto and 'Nunca' not in texto
        estado, texto = resumen_estado(repo, comprobando=True)
        assert estado == 'comprobando' and 'Versión vigente: 3' in texto
        assert resumen_estado(repo, sin_conexion=True)[0] == 'offline'
        assert resumen_estado(repo, ResultadoSincronizacion('sin_cambios', 3, 'Al día'))[1].endswith('Al día')


def test_resumen_corto_para_el_panel_e_iniciales():
    from fraseya.presentacion.qt_lateral import iniciales

    with RepositorioSQLite(':memory:') as repo:
        assert resumen_corto(repo, 'pendiente')[0] == 'Sin comprobar'
        assert resumen_corto(repo, 'offline')[0] == 'Sin conexión'
        assert resumen_corto(repo, 'error')[0] == 'No se pudo sincronizar'
    assert iniciales('a.perez@example.test') == 'A'
    assert iniciales('demo@example.test') == 'DE'

