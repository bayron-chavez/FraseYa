"""Medición repetible RNF-02/RNF-08 en datos temporales; no toca el teclado."""
import ctypes
from ctypes import wintypes
import json
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from fraseya.infraestructura import RepositorioSQLite
from fraseya.aplicacion.gestion_frases import GestionFrases
from fraseya.presentacion.ventana_principal import VentanaPrincipal
from fraseya.presentacion.buscador_rapido import VentanaBuscador


class Memoria(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
        (n, ctypes.c_size_t) for n in ('PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
        'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]


def main():
    with RepositorioSQLite(':memory:') as repo:
        gestion = GestionFrases(repo)
        cat = gestion.categorias_propias()[0]['id']
        for n in range(1000):
            repo.crear_frase(cat, f'Frase {n}', f'f{n}', f'Texto {n}')
        ventana = VentanaPrincipal(gestion)
        ventana.withdraw()
        buscador = VentanaBuscador(ventana, lambda *_: None)
        ventana.update()
        frases = gestion.listar()
        tiempos = []
        for _ in range(20):
            inicio = time.perf_counter()
            buscador.mostrar(frases, None)
            ventana.update()
            tiempos.append((time.perf_counter() - inicio) * 1000)
            buscador.ocultar()
            ventana.update()
        contador = Memoria()
        contador.cb = ctypes.sizeof(contador)
        kernel = ctypes.WinDLL('kernel32')
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL('psapi')
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Memoria), wintypes.DWORD]
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(contador), contador.cb):
            raise OSError('No se pudo medir la memoria.')
        cpu, reloj = time.process_time(), time.perf_counter()
        ventana.after(5000, ventana.quit)
        ventana.mainloop()
        resultado = {'frases': 1000, 'aperturas': 20, 'buscador_max_ms': round(max(tiempos), 2),
            'buscador_media_ms': round(sum(tiempos)/len(tiempos), 2),
            'ram_mb': round(contador.WorkingSetSize/1024/1024, 2),
            'cpu_reposo_porcentaje': round(100*(time.process_time()-cpu)/(time.perf_counter()-reloj), 2),
            'alcance': 'Windows actual; UI sin hook de teclado ni red; no valida otras máquinas'}
        ventana.destroy()
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
        return resultado


if __name__ == '__main__':
    main()
