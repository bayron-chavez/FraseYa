# Interfaz nativa Qt de producción

Ejecutar desde la raíz:

```powershell
venv\Scripts\python.exe -m pip install -r requirements-qt.txt
venv\Scripts\python.exe main.py
```

La ventana usa PySide6 y los mismos casos de uso y repositorio SQLite del programa. El lanzador de evaluación utiliza una base temporal en memoria: permite probar búsqueda, filtros, favoritas, creación, edición, duplicación, eliminación con deshacer y variables con vista previa para copiar. Los cambios de demostración desaparecen al cerrar.

El inicio normal y el instalador utilizan Qt, incluido acceso Supabase, sincronización, publicación, categorías, importación Excel, bandeja, expansión de teclado, variables con vista previa y asistente IA con perfil empresarial. Se conserva datos/fraseya.db sin borrar las frases existentes. Las cuentas continúan administrándose en Supabase Authentication y fraseya_perfiles.

Las abreviaturas se suspenden cuando una ventana de FraseYa tiene el foco. Cerrar sesión revoca la sesión y cierra la aplicación. El modo sin conexión permite usar la biblioteca local, sin IA ni acciones centrales.

Pruebas: tests/test_qt_vista.py y tests/test_qt_seguridad.py. main.py --diagnostico construye la ventana sin acceso a la red ni captura del teclado. scripts/vista_qt.py conserva la demostración temporal. El ejecutable excluye Tkinter, WebEngine y QML. Avisos: docs/LICENCIAS_QT.md.
