"""Auditoría remota de solo lectura: no muestra claves ni datos del catálogo."""
import sys
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / 'src'))
from fraseya.infraestructura.supabase import cargar_cliente, ErrorSupabase


def main():
    cliente = cargar_cliente(RAIZ / 'datos' / 'supabase.json')
    hallazgos = 0
    for nombre, metodo, ruta, datos in [
        ('Lectura anónima de catálogo', 'GET', '/rest/v1/fraseya_catalogo?select=version&limit=1', None),
        ('Lectura anónima de perfiles', 'GET', '/rest/v1/fraseya_perfiles?select=id&limit=1', None),
        ('Perfil sin iniciar sesión', 'POST', '/rest/v1/rpc/fraseya_perfil', {})]:
        try:
            resultado = cliente.solicitar(metodo, ruta, datos, autenticado=False)
            if resultado:
                hallazgos += 1
                print(nombre + ': FALLO, permite consultar datos sin sesión.')
            else:
                print(nombre + ': no devuelve datos; revisar también privilegios en SQL Editor.')
        except ErrorSupabase as error:
            if error.estado in (401, 403):
                print(nombre + ': acceso denegado correctamente.')
            else:
                hallazgos += 1
                print(nombre + ': no se pudo verificar (' + str(error) + ').')
    return 1 if hallazgos else 0


if __name__ == '__main__':
    raise SystemExit(main())
