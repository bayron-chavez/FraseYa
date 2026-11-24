"""Medición repetible RNF-02/RNF-08 en datos temporales sobre Qt; no toca el teclado."""
import ctypes
from ctypes import wintypes
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from fraseya.aplicacion.buscador import buscar
from fraseya.aplicacion.gestion_frases import GestionFrases
from fraseya.infraestructura import RepositorioSQLite
from fraseya.presentacion.qt_vista import VentanaQt


class Memoria(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
        (n, ctypes.c_size_t) for n in (
            'PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
            'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage',
            'PagefileUsage', 'PeakPagefileUsage',
        )
    ]


def main():
    app = QApplication.instance() or QApplication([])
    with RepositorioSQLite(':memory:') as repo:
        gestion = GestionFrases(repo)
        cat = gestion.categorias_propias()[0]['id']
        for n in range(1000):
            repo.crear_frase(cat, f'Frase {n}', f'f{n}', f'Texto {n}')
        ventana = VentanaQt(gestion, demostracion=True)
        frases = gestion.listar()
        tiempos = []
        for idx in range(20):
            inicio = time.perf_counter()
            buscar(frases, f'Frase {idx * 10}')
            ventana.busqueda.setText(f'f{idx * 10}')
            ventana.refrescar()
            app.processEvents()
            tiempos.append((time.perf_counter() - inicio) * 1000)

        contador = Memoria()
        contador.cb = ctypes.sizeof(contador)
        kernel = ctypes.WinDLL('kernel32')
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL('psapi')
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Memoria), wintypes.DWORD]
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(contador), contador.cb):
            raise OSError('No se pudo medir la memoria.')

        cpu, reloj = time.process_time(), time.perf_counter()
        QTimer.singleShot(1500, app.quit)
        app.exec()
        resultado = {
            'frases': 1000,
            'busquedas': 20,
            'busqueda_max_ms': round(max(tiempos), 2),
            'busqueda_media_ms': round(sum(tiempos) / len(tiempos), 2),
            'ram_mb': round(contador.WorkingSetSize / 1024 / 1024, 2),
            'cpu_reposo_porcentaje': round(100 * (time.process_time() - cpu) / max(0.001, time.perf_counter() - reloj), 2),
            'alcance': 'Windows actual; Qt offscreen sin hook de teclado ni red; no valida otras máquinas',
        }
        ventana.close()
        app.processEvents()
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
        return resultado


if __name__ == '__main__':
    main()
