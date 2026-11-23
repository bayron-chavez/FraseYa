"""Diagnóstico de lectura UIA en WhatsApp (solo lectura, sin guardar en disco).

Uso:
  .\\venv\\Scripts\\python.exe scripts\\diagnostico_wsp.py
  .\\venv\\Scripts\\python.exe scripts\\diagnostico_wsp.py --mostrar
"""
import argparse
import ctypes
from ctypes import wintypes
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))

from fraseya.infraestructura.lector_chat import LectorChat, es_ventana_whatsapp


def _buscar_ventana_whatsapp(lector: LectorChat):
    activa = lector.ventana_whatsapp_activa()
    if activa is not None:
        return activa
    if sys.platform != 'win32':
        return None
    u = ctypes.WinDLL('user32', use_last_error=True)
    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    u.EnumWindows.argtypes = [enum_proc, wintypes.LPARAM]
    u.EnumWindows.restype = wintypes.BOOL
    u.IsWindowVisible.argtypes = [wintypes.HWND]
    u.IsWindowVisible.restype = wintypes.BOOL
    encontrada = []

    def _cb(hwnd, _lparam):
        if u.IsWindowVisible(hwnd):
            win = lector.ventana_por_hwnd(int(hwnd))
            if win is not None and es_ventana_whatsapp(win.titulo):
                encontrada.append(win)
                return False
        return True

    u.EnumWindows(enum_proc(_cb), 0)
    return encontrada[0] if encontrada else None


def main() -> int:
    parser = argparse.ArgumentParser(description='Diagnóstico rápido de lectura UIA para WhatsApp.')
    parser.add_argument('--mostrar', action='store_true', help='Muestra el texto de los mensajes detectados.')
    parser.add_argument('--limite', type=int, default=3, help='Cantidad máxima de mensajes (default: 3).')
    parser.add_argument('--espera', type=float, default=0.0, help='Segundos de espera antes de leer (para cambiar a WhatsApp).')
    args = parser.parse_args()

    if args.espera > 0:
        print(f'Esperando {args.espera:.1f} s (pon WhatsApp al frente)...')
        time.sleep(args.espera)

    lector = LectorChat()
    win = _buscar_ventana_whatsapp(lector)
    if win is None:
        print('No se encontró ninguna ventana visible de WhatsApp.')
        return 1

    diag = lector.diagnosticar_lectura(win, limite=max(1, args.limite))
    if diag is None:
        print('No se pudo ejecutar UI Automation sobre la ventana detectada.')
        return 1

    print(f'Ventana: tipo={win.tipo} hwnd={diag.hwnd_original} rect={win.rect}')
    print(f'Render hijo Chrome_RenderWidgetHostHWND: {"SI" if diag.uso_render_hijo else "NO"} (hwnd={diag.hwnd_render})')
    print(f'Contenedor: metodo={diag.metodo_contenedor} modo_area={diag.modo_area}')
    print(f'Nodos FindAllBuildCache: total={diag.nodos_findall} filtrados={diag.nodos_filtrados}')
    print(f'Fallback IsOffscreen: {"SI" if diag.uso_fallback_offscreen else "NO"}')
    print(f'Fallback TextPattern(10014): {"SI" if diag.uso_text_pattern else "NO"} (chars={diag.chars_text_pattern})')
    print(f'Tiempo total: {diag.duracion_ms:.1f} ms')
    print(f'Mensajes detectados: {len(diag.mensajes)} | longitudes={[len(m) for m in diag.mensajes]}')
    if args.mostrar:
        for i, msg in enumerate(diag.mensajes, start=1):
            print(f'  [{i}] {msg}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
