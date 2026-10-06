# Formato del catálogo compartido de FraseYa

Contrato implementado para RF-05 (lectura), RF-08 (publicación) y RF-06
(sincronización). Formato 1, transportado mediante Supabase.

## Archivos

catalogo.json contiene formato y categorias. Cada categoría tiene nombre,
color y frases; cada frase tiene titulo, abreviatura y contenido. No contiene
ids de SQLite, origen ni variables: es independiente de cada base local.
Las variables se derivan del contenido al guardarlo, por ejemplo {nombre}.

version.json contiene formato, version, fecha, autor, cantidad_frases y
sha256. version empieza en 1 y aumenta en cada publicación. formato
identifica la estructura JSON; no es la versión del catálogo ni del esquema
SQLite. fecha lleva hora y zona horaria ISO 8601. autor es texto y puede estar
vacío. cantidad_frases cuenta las frases de todas las categorías.

Los ejemplos completos están en ejemplos/catalogo.json y ejemplos/version.json.

## Reglas

- UTF-8 sin BOM al escribir; el lector admite BOM.
- Sangría de dos espacios, claves ordenadas y salto de línea final LF.
- Se conserva el orden de categorías y frases; el orden de las claves de
  los diccionarios no altera los bytes. No se normalizan textos ni saltos de línea.
- Máximo de 5 MiB (5.242.880 bytes) por archivo, incluido BOM si existe.
- Nombre de categoría, título, abreviatura y contenido no vacíos.
- Nombres de categoría únicos sin distinguir mayúsculas Unicode; no se
  admiten espacios en sus extremos para evitar ambigüedades al guardar.
- Abreviaturas únicas en todo el catálogo sin distinguir mayúsculas Unicode
  (casefold), sin ningún espacio en blanco, incluido tabulador o salto de línea.
- Color hexadecimal #RRGGBB. Cada frase pertenece a la categoría que la contiene.
- Enteros reales para formato, version y cantidad_frases; true/false no son enteros.
- Se rechazan claves desconocidas, claves JSON repetidas y NaN/Infinity.
- Un catálogo sin frases es válido. RF-08 decide si permite publicarlo.
- Un formato futuro produce un mensaje para actualizar FraseYa.

## API del módulo aplicacion/formato_catalogo.py

- serializar(categorias, version, autor, fecha): devuelve bytes_catalogo y
  bytes_version; calcula cantidad_frases y SHA-256 automáticamente.
- leer_version(bytes): devuelve VersionPublicada, un objeto inmutable con
  los seis campos de version.json.
- leer_catalogo(bytes): devuelve la lista de categorías directamente
  compatible con RepositorioSQLite.reemplazar_compartidas().
- verificar_integridad(bytes_catalogo, version): compara el hash de los
  bytes exactos y devuelve True o False. No valida la estructura ni autentica
  al autor; debe combinarse con leer_catalogo.

ErrorFormato hereda de ValueError y ofrece errores, una lista de mensajes
con rutas como categorias[2].frases[0].abreviatura. Se acumulan los errores
de validación del documento; JSON ilegible se informa como error de archivo.

## Contrato entre publicación y sincronización

Supabase guarda el texto del catálogo y sus metadatos juntos. Los nombres
catalogo.json y version.json de los ejemplos describen el contrato de bytes;
la aplicación no los publica en una carpeta de red.

La función de publicación comprueba la versión anterior y el SHA-256 antes de
hacer la actualización transaccional. El lector verifica el hash y la cantidad
de frases. Un hash inválido conserva la copia local. La sincronización conserva
las frases propias y rechaza las abreviaturas en conflicto.
## Verificación

tests/test_formato_catalogo.py comprueba ida y vuelta con Unicode, determinismo,
hash y alteraciones, BOM, límites, errores múltiples, tipos, duplicados,
formato futuro, catálogo vacío, ejemplos y compatibilidad con SQLite.

Prueba manual: abrir el ejemplo en Bloc de notas y verificar tildes, ñ y
emojis. Si se edita un byte del catálogo sin actualizar version.json,
verificar_integridad debe devolver False.
