# RF-05: leer el catálogo compartido

`RepositorioCompartido(carpeta, tiempo_maximo_s=10)` está en
`src/fraseya/infraestructura/repositorio_compartido.py`. Acepta carpetas
locales, sincronizadas y rutas UNC. La ruta se guarda en la configuración
existente, mediante Configuración → Carpeta compartida → Guardar.

- `comprobar()` ldevueve `EstadoCarpeta(estado, mensaje)`: sin_configurar,
  inaccesible o disponible. Disponible no significa catálogo válido.
- `leer_version()` devuelve VersionPublicada o None si aún no existe version.json.
- `leer()` devuelve `(version, categorias)` tras validar ambos documentos,
  SHA-256, cantidad de frases y estabilidad de la versión. Reintenta una vez
  después de 0,1 segundos si cambia la versión o no coincide el hash.
- Los errores son CarpetaNoDisponible, CatalogoNoPublicado, FormatoInvalido,
  FormatoNoSoportado y CatalogoEnTransicion, con mensajes en español.

Las operaciones de archivos se ejecutan en un hilo daemon. El plazo abarca
toda la operación, incluido el reintento. Windows puede mantener una llamada
de red bloqueada después del plazo: no se puede cancelar ese hilo, pero no
retiene el cierre del programa. El lector admite una sola operación pendiente
para evitar acumular hilos. Al cambiar de origen se crea otro lector.

La API es síncrona y puede esperar hasta diez segundos. La futura integración
RF-06 debe llamarla desde un trabajador, nunca desde el hilo de eventos de
Tkinter, y entregar el resultado a la interfaz mediante su cola/after.
Este módulo no modifica SQLite, no escribe en el origen y no programa
sincronizaciones automáticas.

## Comprobación manual

Desde la raíz del proyecto, con Python y sus dependencias disponibles:

```powershell
python scripts/prueba_compartido.py docs/ejemplos
python scripts/prueba_compartido.py "C:\Carpeta compartida"
python scripts/prueba_compartido.py
```

Sin argumento consulta carpeta_compartida en la base local en modo solo
lectura; `--bd` permite elegir otra base. Muestra versión, autor y cantidad,
o un error legible con código de salida 1. Prueba también una carpeta vacía,
una carpeta eliminada y una copia del ejemplo con un byte alterado. No edites
los ejemplos originales. La prueba de una unidad de red real desconectada
queda para un equipo con ese recurso disponible.

```powershell
$env:PYTHONPATH = 'src'
python -m unittest discover -s tests -p test_repositorio_compartido.py -v
```

Las pruebas usan carpetas temporales y simulan permisos, lectura bloqueada y
publicación concurrente. Las lecturas válidas conservan los archivos exactos.
