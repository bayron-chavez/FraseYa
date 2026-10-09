"""Exporta solo la conexión pública validada; nunca cuentas ni tokens."""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / 'src'))
from fraseya.infraestructura.supabase import validar_conexion


def exportar(origen, destino):
    datos = json.loads(Path(origen).read_text(encoding='utf-8'))
    url, clave = validar_conexion(datos['url'], datos['clave_publica'])
    archivo = Path(destino)
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(json.dumps({'url': url, 'clave_publica': clave},
                                  ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    try:
        if len(sys.argv) != 3:
            raise ValueError()
        exportar(sys.argv[1], sys.argv[2])
    except (OSError, ValueError, TypeError, KeyError):
        print('No se pudo preparar la conexión pública. Revisa la URL y usa una clave publishable o anon.', file=sys.stderr)
        raise SystemExit(1) from None
