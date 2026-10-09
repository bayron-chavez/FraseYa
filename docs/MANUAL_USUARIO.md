# Manual de usuario de FraseYa

FraseYa inserta textos predefinidos en el campo activo de Windows. Tus frases
propias se guardan en este equipo; el catálogo compartido llega desde Supabase.
La aplicación no envía mensajes en tu nombre ni lee conversaciones.

## Iniciar

Descomprime toda la carpeta portable dentro de tu perfil de Windows y abre
FraseYa.exe. Conserva la carpeta `_internal` junto al ejecutable. En el primer
inicio introduce la URL del proyecto y su clave pública, proporcionadas por el
administrador. Entra con tu correo y contraseña de Supabase. Nunca introduzcas
la contraseña de la base ni una clave secret/service_role.

La aplicación admite cinco intentos por minuto. Si el servidor limita intentos,
espera cinco minutos antes de reintentar. Las contraseñas y tokens no se guardan
en disco. El límite local se reinicia al cerrar el programa; Supabase aplica sus
propios límites en el servidor.

## Crear y utilizar frases

1. Pulsa «Nueva frase».
2. Completa título, abreviatura sin espacios, categoría y contenido.
3. Pulsa «Guardar».

Las abreviaturas no pueden repetirse, aunque cambien las mayúsculas. Los máximos
son 500 caracteres para título, 100 para abreviatura y 100.000 para contenido.
El motor de expansión reconoce abreviaturas de hasta 64 caracteres; usa ese
límite cuando necesites expandirlas desde el teclado.

Escribe la abreviatura en tu aplicación y pulsa la tecla de confirmación
configurada. Sin confirmación no se expande. Para insertar mediante búsqueda,
usa el atajo de Configuración, escribe parte del título, categoría, abreviatura
o texto, selecciona con las flechas y pulsa Enter. Esc cancela.

Mientras escribes el contenido, abre «Insertar variable…» y selecciona Nombre,
Monto, Fecha u otra opción. FraseYa coloca las llaves automáticamente donde está
el cursor y puedes seguir escribiendo. También puedes escribir `{nombre}`,
`{orden}`, `{monto}`, `{fecha}` u otros nombres manualmente para
solicitar esos valores antes de insertar. No se abre formulario si no hay
marcadores. Los saltos de línea se simulan con Shift+Enter; el envío definitivo
queda bajo tu control. No escribas mientras se completa la inserción.

Si agregas desde el menú una variable que ya existe, puedes elegir «Reutilizar
el mismo valor» o «Agregar otro valor». La primera opción repite el dato; la
segunda crea automáticamente otro campo, como `{nombre_2}` y luego
`{nombre_3}`, sin cambiar lo que ya escribiste. Al utilizar la frase completarás
Nombre, Nombre 2 y Nombre 3 por separado. Cancelar no cambia el contenido.

El formulario muestra arriba una vista previa de toda la frase, que se actualiza
al completar los campos. El campo seleccionado se resalta en su lugar dentro
del texto; si se repite, se resaltan todas sus apariciones. Los campos vacíos
aparecen como `[Nombre]` o `[Nombre 2]` para identificar dónde van. Esta vista
no inserta texto: pulsa «Insertar» cuando hayas revisado la frase.

## Gestionar y filtrar

Selecciona una frase guardada y pulsa «Marcar favorita». Las favoritas muestran
una estrella y aparecen primero en la lista y en el buscador rápido. «Solo
favoritas» permite ver únicamente esas frases, combinando búsqueda y categoría.
Puedes marcar frases propias o compartidas: la marca se guarda localmente y no
modifica el catálogo central. Se conserva al reabrir FraseYa y al sincronizar;
«Quitar de favoritas» desmarca la frase.

Tras borrar una frase propia, pulsa «Deshacer eliminación» para recuperar la
última eliminada, con su contenido, variables y marca de favorita. Está disponible
durante la sesión actual y se reemplaza cuando eliminas otra frase propia.
Si la abreviatura ya está ocupada, se avisa y no se sobrescribe ninguna frase;
puedes liberar esa abreviatura y reintentar. Si la categoría original ya no existe,
se recupera en General o en una categoría propia disponible. Las eliminaciones
del catálogo compartido no se deshacen con este botón.

Selecciona una frase propia para editarla, duplicarla o eliminarla. Las frases
compartidas son de solo lectura. Duplicarlas crea una frase propia con otra
abreviatura. El filtro superior permite ver las frases de una categoría, tanto
propias como compartidas. Solo el administrador gestiona los nombres y colores
de categorías. Los cambios compartidos llegan tras publicar y sincronizar.

## Importar Excel

Usa «Importar Excel» y selecciona un `.xlsx`. En la primera hoja deben aparecer,
en este orden, las columnas categoría, título, abreviatura y contenido. Cada fila
debe contener texto; no se admiten fórmulas. Se informan las filas rechazadas y
se continúa con las válidas. Los usuarios deben usar categorías existentes; el
administrador puede crear las que falten. No se publica automáticamente.
Límites: 10 MB de archivo, 50 MB descomprimidos y 10.000 filas de datos.

## Sincronizar y trabajar sin conexión

FraseYa comprueba el catálogo al abrir y según el intervalo de Configuración.
«Sincronizar ahora» solicita una comprobación adicional. La ventana muestra la
versión instalada, la última comprobación y el resultado. Si una abreviatura
propia coincide con una compartida, renombra la propia: se rechaza la actualización
completa y se conserva la versión anterior.

«Trabajar sin conexión» abre la copia local y desactiva las peticiones periódicas.
Puedes buscar, expandir y gestionar frases propias. No puedes publicar ni crear
categorías de administrador sin validar el rol en el servidor. Esas operaciones
centrales requieren conexión. Usa perfiles separados de Windows si compartes el
equipo: la copia local no está cifrada ni separada por correo.

La bandeja usa verde para catálogo comprobado, naranja al comprobar, rojo para
error y gris para modo sin conexión. Su menú permite abrir la ventana,
sincronizar o salir. Cerrar la ventana termina FraseYa y retira el icono.

## Configuración y datos

Configura tecla de confirmación, atajo del buscador, velocidad de 10 a 60 ms por
carácter e intervalo de comprobación de 1 a 1.440 minutos. Los cambios se aplican
sin reiniciar. Una frase de 1.000 caracteres tarda al menos 10 segundos con esa
velocidad; el procesamiento de búsqueda y el tiempo de escritura son distintos.

La carpeta `datos` junto al ejecutable contiene `fraseya.db` y `supabase.json`.
Respáldala con FraseYa cerrado. No la subas a GitHub ni la distribuyas a terceros.
