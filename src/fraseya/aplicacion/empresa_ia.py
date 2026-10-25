"""Perfil compartido de empresa: permisos comprobados también en Supabase."""
CAMPOS = {'nombre': 200, 'servicios': 4000, 'horarios': 1000, 'procedimientos': 4000}


def validar(perfil):
    if (not isinstance(perfil, dict) or set(perfil) != set(CAMPOS)
            or any(not isinstance(perfil[k], str) or len(perfil[k]) > maximo for k, maximo in CAMPOS.items())):
        raise ValueError('Revisa los campos y sus límites en el perfil de empresa.')
    return {k: v.strip() for k, v in perfil.items()}


class EmpresaIA:
    def __init__(self, cliente):
        self.cliente = cliente

    def leer(self):
        return validar(self.cliente.solicitar('POST', '/rest/v1/rpc/fraseya_empresa_ia_leer', {}))

    def guardar(self, perfil):
        self.cliente.solicitar('POST', '/rest/v1/rpc/fraseya_empresa_ia_guardar', {'p_perfil': validar(perfil)})
