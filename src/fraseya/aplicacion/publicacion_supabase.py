"""Publicación remota: conserva frases y usa control de versión transaccional."""
import json
from fraseya.aplicacion.publicacion import ServicioPublicacion, ErrorPublicacion, ErrorAutorizacion, ResultadoPublicacion
from fraseya.aplicacion.formato_catalogo import leer_version, leer_catalogo, verificar_integridad
from fraseya.infraestructura.supabase import RepositorioSupabase


class PublicacionSupabase(ServicioPublicacion):
    def __init__(self, repositorio, autenticacion, sesion):
        super().__init__(repositorio, autenticacion.cliente.url, sesion.usuario,
            autorizar_eliminacion=lambda: autenticacion.validar(sesion, administrador=True))
        self.auth, self.sesion = autenticacion, sesion
        self.remoto = RepositorioSupabase(autenticacion.cliente)

    def _lector(self):
        try:
            self.auth.validar(self.sesion, administrador=True)
        except PermissionError as error:
            raise ErrorAutorizacion(str(error)) from None
        return self.remoto

    def publicar(self, vista, confirmar_vacio=False):
        self.auth.validar(self.sesion, administrador=True)
        version = leer_version(vista.metadata)
        leer_catalogo(vista.catalogo)
        if not verificar_integridad(vista.catalogo, version):
            raise ErrorPublicacion('La vista previa fue modificada. Prepara otra publicación.')
        if version.cantidad_frases == 0 and not confirmar_vacio:
            raise ErrorPublicacion('Confirma la publicación del catálogo vacío.')
        respuesta = self.remoto.publicar(vista)
        publicada = leer_version(json.dumps(respuesta).encode('utf-8'))
        if (publicada.version != version.version or publicada.sha256 != version.sha256
                or publicada.cantidad_frases != version.cantidad_frases):
            raise ErrorPublicacion('La respuesta del servidor no coincide; sincroniza para comprobar el catálogo.')
        return ResultadoPublicacion(publicada.version, publicada.fecha, publicada.cantidad_frases)
