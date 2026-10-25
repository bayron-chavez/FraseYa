"""Punto de entrada de FraseYa. Abre la ventana y la expansión por abreviatura. --sin-teclado la desactiva; --consola solo verifica el arranque."""
import sys
from pathlib import Path

PROYECTO = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
sys.path.insert(0, str(PROYECTO / 'src'))

from fraseya.presentacion.consola import ejecutar

RUTA_BD = PROYECTO / 'datos' / 'fraseya.db'

if __name__ == '__main__':
    if '--diagnostico' in sys.argv:
        def fallo_diagnostico(tipo, error, traza):
            import traceback
            (PROYECTO / 'diagnostico.log').write_text(''.join(traceback.format_exception(tipo, error, traza)), encoding='utf8')
        sys.excepthook = fallo_diagnostico
        from fraseya.infraestructura import RepositorioSQLite
        from PySide6.QtWidgets import QApplication
        from fraseya.presentacion.qt_vista import VentanaQt
        from fraseya.aplicacion.gestion_frases import GestionFrases
        from fraseya.aplicacion.importacion_excel import importar_excel
        with RepositorioSQLite(':memory:') as repo:
            assert repo.db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            app = QApplication.instance() or QApplication([])
            ventana = VentanaQt(GestionFrases(repo), demostracion=True)
            ventana.show()
            app.processEvents()
            if '--captura' in sys.argv:
                destino = Path(sys.argv[sys.argv.index('--captura') + 1])
                assert ventana.grab().save(str(destino))
            ventana.close()
        raise SystemExit(0)
    if '--consola' in sys.argv:
        sys.argv.remove('--consola')
        raise SystemExit(ejecutar(ruta_predeterminada=RUTA_BD))
    from fraseya.presentacion.qt_aplicacion import abrir
    from fraseya.infraestructura.supabase import ErrorSupabase
    try:
        abrir(RUTA_BD, con_teclado='--sin-teclado' not in sys.argv, configurar='--configurar' in sys.argv)
    except ErrorSupabase as error:
        from PySide6.QtWidgets import QApplication,QMessageBox
        app=QApplication.instance() or QApplication([])
        QMessageBox.critical(None,'FraseYa',str(error))
        raise SystemExit(1) from None
