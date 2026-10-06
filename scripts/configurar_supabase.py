"""Configuración pública local. Ejecutar: python scripts/configurar_supabase.py."""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / 'src'))
from fraseya.infraestructura.supabase import validar_conexion


def main():
    print('Configurar Supabase. No introduzcas claves secret ni service_role.')
    try:
        url, clave = validar_conexion(input('URL del proyecto: '), input('Clave pública publishable/anon: '))
    except ValueError as error:
        print(error)
        return 1
    archivo = RAIZ / 'datos' / 'supabase.json'
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(json.dumps({'url': url, 'clave_publica': clave}, indent=2), encoding='utf-8')
    print('Configuración guardada en datos/supabase.json. Reinicia FraseYa.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
