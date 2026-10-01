# Base de datos local de FraseYa

Implementación de las dos tarjetas de Bayron que estaban en **Por hacer**:

- Esquema SQLite local de seis tablas.
- RepositorioSQLite con operaciones de datos y pruebas con BD en memoria.

No modifica el prototipo de interfaz ni incluye sincronización de carpetas,
Supabase o las entidades de dominio de Diego. Esta entrega se integra después.

## Ejecutar

Requiere Python 3.10 o posterior y únicamente su biblioteca estándar.

```powershell
python crear_bd.py ./datos/fraseya.db
$env:PYTHONPATH = 'src'
python -m unittest discover -s tests -v
```

Sin argumento, crear_bd.py prepara `datos/fraseya.db` dentro del proyecto,
igual que main.py.
La primera construcción de RepositorioSQLite crea carpetas, tablas, índices,
restricciones y disparadores automáticamente. Las siguientes conservan datos.
Puede usarse `:memory:` para pruebas.

## Integración con el software

```python
from fraseya import RepositorioSQLite

with RepositorioSQLite('datos/fraseya.db') as repo:
    catalogo = repo.crear_catalogo('Personal')
    categoria = repo.crear_categoria(catalogo, 'Atención', '#2563EB')
    frase = repo.crear_frase(categoria, 'Saludo', 'sal', 'Hola {nombre}')
    print(repo.obtener_frase(frase))
```

Los resultados son diccionarios. Los métodos no dependen de las clases de
dominio, para que Diego pueda añadir sus adaptadores. El programa consumidor
debe evitar crear catálogos repetidos en cada arranque. Crear el esquema no
crea frases ni catálogos de ejemplo.

SQLite mantiene cada conexión en su hilo de origen. El futuro servicio de
sincronización debe abrir su propia instancia en el hilo de trabajo; no debe
compartir la conexión de la interfaz. Las escrituras emplean transacciones y
esperan hasta cinco segundos si otro escritor mantiene bloqueada la base.

## Modelo de seis tablas

| Tabla | Datos y relaciones |
| --- | --- |
| CATALOGO | Nombre, versión entera no negativa, fecha, autor y origen |
| CATEGORIA | Nombre y color hexadecimal, FK a catálogo, nombre único por catálogo |
| FRASE | Título, abreviatura única sin distinguir mayúsculas ASCII, contenido, origen y fecha; FK a categoría |
| VARIABLE | Nombre y orden desde cero, FK a frase; nombre y orden únicos por frase |
| SINCRONIZACION | Fecha UTC generada por SQLite, versión aplicada, estado y detalle |
| CONFIGURACION | Clave única y valor de texto |

El esquema exacto está en `src/fraseya/infraestructura/schema.sql`. La versión del esquema se
guarda en PRAGMA user_version y no se confunde con la versión del catálogo.
El color acepta #RRGGBB. El origen admite propia o compartida y debe coincidir
entre frase y catálogo. Eliminar una frase elimina sus variables. Eliminar
una categoría con frases se rechaza para evitar pérdidas accidentales.

Los marcadores `{nombre}` se extraen del contenido al crear o editar una frase,
sin duplicados y en orden de primera aparición. Hay operaciones independientes
para variables; los cambios de contenido regeneran esa lista. El repositorio
no completa los campos ni inserta texto en otras aplicaciones.

## Contrato de reemplazo del conjunto compartido

`reemplazar_compartidas(version, autor, fecha_publicacion, categorias)` recibe:

```python
categorias = [{
    'nombre': 'Equipo', 'color': '#2563EB',
    'frases': [{'titulo': 'Saludo', 'abreviatura': 'equipo_sal',
                'contenido': 'Hola {nombre}'}]
}]
```

Reemplaza todas las frases y catálogos compartidos en una sola transacción,
incluidas sus categorías y variables, y registra el éxito. Conserva las frases
propias. Una abreviatura repetida, una FK inválida o datos incompletos revierten
toda la operación. Una lista vacía publica un catálogo compartido vacío.

El futuro ServicioSincronizacion decide si la versión recibida es posterior,
lee la carpeta y registra los fallos mediante registrar_sincronizacion().
Este método no compara versiones ni accede a red. Se admite un catálogo
compartido vigente por base local.

## Compatibilidad y validación

El proyecto utiliza una sola base llamada datos/fraseya.db con seis tablas.
Las bases de otras estructuras no se sobrescriben ni se migran automáticamente.
Una base ajena sin versión o una versión no soportada se rechaza.
La actualización futura del esquema requiere una migración explícita.

Las pruebas cubren las operaciones de datos, persistencia al reabrir, seis
tablas, claves foráneas, colores, variables, configuración, sincronizaciones,
preservación de frases propias y reversión ante conflictos. No acreditan
las tarjetas de interfaz, cobertura ≥70% del producto completo ni pruebas
de integración en tres equipos.

