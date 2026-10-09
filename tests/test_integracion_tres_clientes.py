import json
from unittest.mock import Mock
import pytest
from fraseya.aplicacion.formato_catalogo import leer_catalogo
from fraseya.aplicacion.gestion_frases import GestionFrases
from fraseya.aplicacion.publicacion_supabase import PublicacionSupabase
from fraseya.aplicacion.servicio_sincronizacion import ServicioSincronizacion
from fraseya.aplicacion.motor_expansion import MotorExpansion
from fraseya.aplicacion.buscador import buscar
from fraseya.aplicacion.sesion import Sesion
from fraseya.infraestructura import RepositorioSQLite
from fraseya.infraestructura.supabase import ClienteSupabase, RepositorioSupabase, ErrorSupabase


def test_publicar_renombrar_sincronizar_offline_tres_clientes(tmp_path):
    remoto = []
    disponible = [True]
    def transporte(metodo, ruta, cuerpo, headers):
        if not disponible[0]:
            raise ErrorSupabase('Sin red')
        if 'fraseya_publicar' in ruta:
            datos = json.loads(cuerpo)
            actual = remoto[0]['metadata']['version'] if remoto else 0
            if datos['p_version_anterior'] != actual:
                raise ErrorSupabase('Versión obsoleta', 409)
            remoto[:] = [{'contenido': datos['p_contenido'], 'metadata': datos['p_metadata']}]
            return datos['p_metadata']
        return remoto
    cliente = ClienteSupabase('https://ejemplo.supabase.co', 'sb_publishable_prueba', transporte)
    cliente._guardar_tokens({'access_token': 'a', 'refresh_token': 'r', 'expires_in': 3600})
    auth = Mock(cliente=cliente)
    sesion = Sesion('admin@example.test', 'administrador', 'nonce')
    with RepositorioSQLite(tmp_path/'admin.db') as admin:
        gestion = GestionFrases(admin)
        ident = gestion.crear_categoria('Ventas', auth, sesion)
        gestion.crear('Saludo', 'saludo', 'Hola equipo', ident)
        servicio = PublicacionSupabase(admin, auth, sesion)
        vista = servicio.preparar()
        servicio.publicar(vista)
        gestion.editar_categoria(ident, 'Comercial', '#112233', auth, sesion)
        nueva = servicio.preparar(operaciones_categorias=gestion.operaciones_categorias())
        categorias = leer_catalogo(nueva.catalogo)
        assert not any(c['nombre'] == 'Ventas' for c in categorias)
        assert next(c for c in categorias if c['nombre'] == 'Comercial')['frases'][0]['contenido'] == 'Hola equipo'
        servicio.publicar(nueva)
        with pytest.raises(ErrorSupabase):
            servicio.publicar(vista)
    for numero in range(3):
        ruta = tmp_path/f'cliente{numero}.db'
        with RepositorioSQLite(ruta) as repo:
            local = GestionFrases(repo)
            cat = local.categorias_propias()[0]['id']
            ident = local.crear('Propia', f'mia{numero}', 'Texto propio', cat)
            sync = ServicioSincronizacion(repo, lambda: RepositorioSupabase(cliente))
            assert sync.sincronizar().estado == 'actualizada'
            assert repo.obtener_frase(ident)['contenido'] == 'Texto propio'
            disponible[0] = False
            assert sync.sincronizar().estado == 'error'
            frases = local.listar()
            assert buscar(frases, 'Comercial')
            escritor = Mock()
            motor = MotorExpansion(escritor, lambda *_: None, lanzar=lambda fn: fn())
            motor.actualizar_frases(frases)
            for letra in 'saludo':
                motor.caracter(letra)
            assert motor.confirmar()
            assert escritor.reemplazar.call_args.args[-1] == 'Hola equipo'
            local.editar(ident, 'Editada', f'mia{numero}', 'Editada sin red', cat)
            disponible[0] = True
        with RepositorioSQLite(ruta) as repo:
            assert repo.obtener_frase(ident)['contenido'] == 'Editada sin red'
            assert repo.listar_catalogos('compartida')[0]['version'] == 2
