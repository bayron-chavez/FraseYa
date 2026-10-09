from unittest.mock import Mock
from zipfile import ZipFile, ZIP_DEFLATED
import pytest
from openpyxl import Workbook
from fraseya.aplicacion.importacion_excel import importar_excel
from fraseya.aplicacion.gestion_frases import GestionFrases
from fraseya.infraestructura import RepositorioSQLite


def archivo(tmp_path, filas):
    libro = Workbook()
    for fila in filas:
        libro.active.append(fila)
    ruta = tmp_path / 'frases.xlsx'
    libro.save(ruta)
    libro.close()
    return ruta


def test_importa_sin_detenerse_ante_formula_duplicado_o_vacio(tmp_path):
    ruta = archivo(tmp_path, [['categoría', 'título', 'abreviatura', 'contenido'],
        ['General', 'Saludo', 'sal', "'; DROP TABLE FRASE; --"],
        ['General', 'Duplicada', 'SAL', 'Hola'], ['General', 'Formula', 'f', '=1+1'],
        ['General', 'Otra', 'otra', 'Contenido'], ['General', '', 'vacia', 'X']])
    with RepositorioSQLite(':memory:') as repo:
        resultado = importar_excel(ruta, GestionFrases(repo))
        assert resultado.importadas == 2
        assert [n for n, _ in resultado.rechazadas] == [3, 4, 6]
        assert repo.db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert len(repo.listar_frases()) == 2


def test_usuario_no_crea_categorias_admin_si(tmp_path):
    ruta = archivo(tmp_path, [['categoria', 'titulo', 'abreviatura', 'contenido'], ['Ventas', 'A', 'a', 'Texto']])
    with RepositorioSQLite(':memory:') as repo:
        gestion = GestionFrases(repo)
        auth = Mock()
        auth.validar.side_effect = PermissionError('Solo admin')
        assert importar_excel(ruta, gestion, auth, object()).importadas == 0
        assert len(repo.listar_categorias()) == 1
        auth.validar.side_effect = None
        assert importar_excel(ruta, gestion, auth, object()).importadas == 1
        assert any(c['nombre'] == 'Ventas' for c in repo.listar_categorias())


def test_rechaza_zip_bomba_antes_de_parser(tmp_path):
    ruta = tmp_path / 'bomba.xlsx'
    with ZipFile(ruta, 'w', ZIP_DEFLATED) as archivo_zip:
        archivo_zip.writestr('bomba.xml', b'0' * (51 * 1024 * 1024))
    with RepositorioSQLite(':memory:') as repo:
        with pytest.raises(ValueError, match='demasiado grande'):
            importar_excel(ruta, GestionFrases(repo))
        assert repo.listar_frases() == []


def test_rechaza_cabecera_incorrecta(tmp_path):
    with RepositorioSQLite(':memory:') as repo:
        with pytest.raises(ValueError, match='columnas'):
            importar_excel(archivo(tmp_path, [['incorrecto']]), GestionFrases(repo))


def test_xml_no_expande_entidades_externas(tmp_path):
    ruta = archivo(tmp_path, [['categoria', 'titulo', 'abreviatura', 'contenido'], ['General', 'A', 'a', 'Texto']])
    with ZipFile(ruta) as origen:
        partes = {n: origen.read(n) for n in origen.namelist()}
    hoja = partes['xl/worksheets/sheet1.xml'].decode()
    hoja = '<!DOCTYPE worksheet [<!ENTITY xxe SYSTEM "file:///C:/Windows/win.ini">]>' + hoja.replace('Texto', '&xxe;')
    partes['xl/worksheets/sheet1.xml'] = hoja.encode()
    with ZipFile(ruta, 'w', ZIP_DEFLATED) as destino:
        for n, datos in partes.items():
            destino.writestr(n, datos)
    with RepositorioSQLite(':memory:') as repo:
        with pytest.raises(Exception) as rechazado:
            importar_excel(ruta, GestionFrases(repo))
        error = rechazado.value
        while error.__cause__ is not None:
            error = error.__cause__
        assert type(error).__name__ in ('EntitiesForbidden', 'ExternalReferenceForbidden', 'XMLSyntaxError', 'ParseError')
        assert repo.listar_frases() == []
