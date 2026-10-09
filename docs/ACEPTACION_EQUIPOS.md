# Prueba de aceptación en equipos reales

Ejecutar una copia del portable por equipo. No copiar la carpeta `datos` de
otro usuario. Configurar la URL y clave pública del mismo proyecto Supabase e
iniciar sesión con una cuenta de usuario general. No compartir contraseñas ni
incluirlas en este registro. No publicar ni borrar contenido del catálogo para
esta prueba.

## Procedimiento por equipo

1. Abrir `FraseYa.exe` desde la carpeta extraída, sin instalar ni ejecutar como
   administrador. Anotar Windows y el resultado del arranque.
2. Iniciar sesión y pulsar **Sincronizar ahora**. Anotar la versión indicada y
   el número de frases compartidas. En los tres equipos deben coincidir cuando
   no se haya publicado otra versión entre pruebas.
3. Seleccionar una categoría y buscar una frase conocida. Confirmar que se
   filtra correctamente y que la categoría muestra su color.
4. Crear una frase **propia** de prueba con una abreviatura que no exista,
   por ejemplo `!pruebaequipo1`, y contenido `Prueba local de FraseYa`.
   Usar un número distinto en cada equipo. Confirmar que figura como propia.
5. Abrir Bloc de notas y escribir esa abreviatura siguiendo el mecanismo de
   expansión descrito en el manual. Confirmar que el texto se inserta completo.
   Repetir en la aplicación de texto que se utilizará habitualmente.
6. Cerrar FraseYa, desconectar temporalmente la red y volver a abrirlo en modo
   sin conexión. Confirmar búsqueda de frases compartidas ya descargadas y
   expansión de la frase propia. Anotar la versión conservada. Las operaciones
   centrales de administración deben quedar inaccesibles.
7. Reconectar la red, cerrar y abrir FraseYa, iniciar sesión y sincronizar.
   Confirmar que la frase propia continúa y que el catálogo vuelve a estar
   disponible. Comprobar apertura desde la bandeja y cierre completo.
8. Si se desea limpiar la prueba, eliminar únicamente la frase **propia**
   creada en el paso 4. No eliminar frases compartidas.

Si algo falla, detener ese paso y registrar el mensaje y los pasos para
reproducirlo. No enviar capturas que contengan claves, contraseñas o frases
personales. La versión y el conteo bastan para comparar el catálogo.

## Registro

Pendiente significa que no se ha probado; no equivale a aprobado.

| Comprobación | Equipo 1 | Equipo 2 | Equipo 3 |
| --- | --- | --- | --- |
| Fecha y Windows (versión / x64) | Pendiente | Pendiente | Pendiente |
| Arranque portable sin permisos elevados | Pendiente | Pendiente | Pendiente |
| Inicio de sesión de usuario general | Pendiente | Pendiente | Pendiente |
| Versión y cantidad de compartidas | Pendiente | Pendiente | Pendiente |
| Categoría, color y búsqueda | Pendiente | Pendiente | Pendiente |
| Frase propia conservada tras sincronizar | Pendiente | Pendiente | Pendiente |
| Expansión en Bloc de notas | Pendiente | Pendiente | Pendiente |
| Expansión en aplicación habitual (indicar nombre) | Pendiente | Pendiente | Pendiente |
| Búsqueda y expansión sin conexión | Pendiente | Pendiente | Pendiente |
| Versión conservada al reabrir sin red | Pendiente | Pendiente | Pendiente |
| Reconexión y sincronización | Pendiente | Pendiente | Pendiente |
| Bandeja y cierre completo | Pendiente | Pendiente | Pendiente |
| Incidencias y resultado final | Pendiente | Pendiente | Pendiente |

Las pruebas automatizadas de seguridad se documentan en `SEGURIDAD.md`.
Este procedimiento no requiere ataques repetidos a cuentas reales. El límite
local de acceso se verifica con pruebas automatizadas y la configuración del
límite por IP se comprobó en el panel de Supabase.

La aceptación de tres equipos solo se cierra cuando las tres columnas tienen
evidencia. La entrega al cliente requiere además su aceptación explícita.
