import importlib.util
import json
from pathlib import Path

import pytest

especificacion = importlib.util.spec_from_file_location(
    'conexion_instalador', Path(__file__).resolve().parents[1] / 'scripts/preparar_conexion_instalador.py')
modulo = importlib.util.module_from_spec(especificacion)
especificacion.loader.exec_module(modulo)


def test_exportacion_no_incluye_contrasenas_tokens_ni_datos(tmp_path):
    entrada, salida = tmp_path / 'local.json', tmp_path / 'publica.json'
    entrada.write_text(json.dumps({
        'url': 'https://proyecto.supabase.co', 'clave_publica': 'sb_publishable_prueba',
        'password': 'no-exportar', 'access_token': 'no-exportar', 'usuario': 'personal',
        'frases': ['privada'],
    }))
    modulo.exportar(entrada, salida)
    assert json.loads(salida.read_text()) == {
        'url': 'https://proyecto.supabase.co', 'clave_publica': 'sb_publishable_prueba'}


@pytest.mark.parametrize('clave', ['sb_secret_no_permitida', 'contrasena'])
def test_no_empaqueta_claves_privilegiadas(tmp_path, clave):
    entrada, salida = tmp_path / 'local.json', tmp_path / 'publica.json'
    entrada.write_text(json.dumps({'url': 'https://proyecto.supabase.co', 'clave_publica': clave}))
    with pytest.raises(ValueError):
        modulo.exportar(entrada, salida)
    assert not salida.exists()
