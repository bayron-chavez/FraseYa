import pytest

from fraseya.aplicacion.configuracion import Ajustes, Configuracion, normalizar_atajo
from fraseya.aplicacion.gestion_frases import ErroresValidacion
from fraseya.infraestructura import RepositorioSQLite

VALIDOS = {'tecla_confirmacion': 'enter', 'atajo_buscador': 'ctrl+shift+k', 'velocidad_ms': '35',
           'intervalo_sincronizacion_min': '10'}


@pytest.fixture
def repo():
    with RepositorioSQLite(':memory:') as r:
        yield r


@pytest.fixture
def config(repo):
    return Configuracion(repo)


def test_sin_nada_guardado_se_usan_los_valores_predeterminados(config):
    assert config.leer() == Ajustes()
    a = config.leer()
    assert (a.tecla_confirmacion, a.atajo_buscador, a.velocidad_ms) == ('tab', 'ctrl+alt+espacio', 20)
    assert a.intervalo_sincronizacion_min == 15


def test_guardar_y_leer_devuelve_los_valores_con_su_tipo(config):
    config.guardar(VALIDOS)
    a = config.leer()
    assert a == Ajustes('enter', 'ctrl+shift+k', 35, 10)
    assert isinstance(a.velocidad_ms, int) and isinstance(a.intervalo_sincronizacion_min, int)


def test_persiste_entre_sesiones(tmp_path):
    ruta = tmp_path / 'f.db'
    with RepositorioSQLite(ruta) as r:
        Configuracion(r).guardar(VALIDOS)
    with RepositorioSQLite(ruta) as r:                  # "reiniciar la aplicación"
        assert Configuracion(r).leer().velocidad_ms == 35
        assert Configuracion(r).leer().atajo_buscador == 'ctrl+shift+k'


def test_guardar_solo_un_campo_conserva_los_demas(config):
    config.guardar(VALIDOS)
    config.guardar({'velocidad_ms': '50'})
    a = config.leer()
    assert a.velocidad_ms == 50 and a.tecla_confirmacion == 'enter'


def test_el_atajo_se_normaliza(config):
    assert normalizar_atajo(' Shift + Ctrl + K ') == 'ctrl+shift+k'
    config.guardar({'atajo_buscador': 'Shift + Ctrl + K'})
    assert config.leer().atajo_buscador == 'ctrl+shift+k'


def test_muestra_todos_los_errores_juntos_y_no_guarda_nada(config):
    with pytest.raises(ErroresValidacion) as e:
        config.guardar({'tecla_confirmacion': 'f13', 'atajo_buscador': 'k', 'velocidad_ms': '5',
                        'intervalo_sincronizacion_min': '0'})
    assert len(e.value.errores) == 4
    assert config.leer() == Ajustes()                   # ni siquiera lo válido se guardó


@pytest.mark.parametrize('velocidad', ['9', '61', '', 'abc', '20.5', '-5'])
def test_velocidad_fuera_de_rango_o_no_numerica(config, velocidad):
    with pytest.raises(ErroresValidacion, match='velocidad'):
        config.guardar({'velocidad_ms': velocidad})


@pytest.mark.parametrize('velocidad', ['10', '60', ' 25 '])
def test_velocidad_en_los_limites_es_valida(config, velocidad):
    assert config.guardar({'velocidad_ms': velocidad}).velocidad_ms == int(velocidad)


@pytest.mark.parametrize('intervalo', ['0', '1441', 'x', ''])
def test_intervalo_invalido(config, intervalo):
    with pytest.raises(ErroresValidacion, match='intervalo'):
        config.guardar({'intervalo_sincronizacion_min': intervalo})



@pytest.mark.parametrize('atajo', ['ctrl+c', 'ctrl+v', 'ctrl+z', 'k', 'ctrl+', 'alt+tab'])
def test_atajos_que_pisarian_el_teclado_normal_se_rechazan(config, atajo):
    with pytest.raises(ErroresValidacion):
        config.guardar({'atajo_buscador': atajo})


def test_la_tecla_windows_se_rechaza(config):
    with pytest.raises(ErroresValidacion, match='Windows'):
        config.guardar({'atajo_buscador': 'win+k'})


def test_ctrl_alt_con_letra_se_rechaza_por_altgr(config):
    with pytest.raises(ErroresValidacion, match='AltGr'):
        config.guardar({'atajo_buscador': 'ctrl+alt+q'})
    with pytest.raises(ErroresValidacion, match='AltGr'):
        config.guardar({'atajo_buscador': 'ctrl+alt+2'})


@pytest.mark.parametrize('atajo', ['ctrl+alt+espacio', 'ctrl+alt+f9', 'alt+f9', 'ctrl+shift+k',
                                   'alt+shift+espacio', 'ctrl+shift+7'])
def test_atajos_razonables_se_aceptan(config, atajo):
    assert config.guardar({'atajo_buscador': atajo}).atajo_buscador == atajo


@pytest.mark.parametrize('atajo', ['alt+f4', 'ctrl+shift+t', 'ctrl+shift+n'])
def test_atajos_reservados_por_otras_aplicaciones(config, atajo):
    with pytest.raises(ErroresValidacion, match='otras aplicaciones'):
        config.guardar({'atajo_buscador': atajo})


def test_tecla_de_confirmacion_solo_admite_las_conocidas(config):
    assert config.guardar({'tecla_confirmacion': 'Espacio'}).tecla_confirmacion == 'espacio'
    with pytest.raises(ErroresValidacion):
        config.guardar({'tecla_confirmacion': 'enter2'})


def test_un_valor_corrupto_en_la_base_no_rompe_la_lectura(repo, config):
    repo.guardar_configuracion('velocidad_ms', 'rápido')
    repo.guardar_configuracion('tecla_confirmacion', 'enter')
    a = config.leer()
    assert a.velocidad_ms == 20 and a.tecla_confirmacion == 'enter'   # solo se descarta lo inválido


def test_restablecer_vuelve_a_los_predeterminados_y_los_guarda(config):
    config.guardar(VALIDOS)
    assert config.restablecer() == Ajustes()
    assert config.leer() == Ajustes()


def test_guardar_varias_claves_es_todo_o_nada(repo):
    with pytest.raises(ValueError):
        repo.guardar_configuraciones({'a': '1', 'b': 2})
    assert repo.leer_configuracion('a') is None


# ---- atajos recomendados ------------------------------------------------------

def test_todos_los_atajos_recomendados_pasan_la_validacion(config):
    from fraseya.aplicacion.configuracion import ATAJOS_RECOMENDADOS
    for atajo, _descripcion in ATAJOS_RECOMENDADOS:
        assert config.guardar({'atajo_buscador': atajo}).atajo_buscador == atajo


def test_los_recomendados_estan_ya_normalizados_sin_repetir_y_con_descripcion():
    from fraseya.aplicacion.configuracion import ATAJOS_RECOMENDADOS
    atajos = [a for a, _ in ATAJOS_RECOMENDADOS]
    assert atajos == [normalizar_atajo(a) for a in atajos]
    assert len(set(atajos)) == len(atajos) and all(d for _, d in ATAJOS_RECOMENDADOS)


def test_el_atajo_predeterminado_es_el_primer_recomendado():
    from fraseya.aplicacion.configuracion import ATAJOS_RECOMENDADOS
    assert ATAJOS_RECOMENDADOS[0][0] == Ajustes().atajo_buscador


def test_ningun_recomendado_usa_alt_shift_que_cambia_el_idioma_del_teclado():
    from fraseya.aplicacion.configuracion import ATAJOS_RECOMENDADOS
    assert not any({'alt', 'shift'} <= set(a.split('+')) for a, _ in ATAJOS_RECOMENDADOS)
