# RF-08: publicar el catálogo

En Configuración elige una carpeta existente y accesible para los equipos.
Pulsa «Publicar catálogo…». La aplicación toma una copia de tus frases propias,
agrupadas por categoría con su color. Las frases compartidas instaladas no se
incluyen. Antes de escribir muestra la versión siguiente, carpeta, número de
frases/categorías y diferencias por abreviatura: nuevas, modificadas y eliminadas.
Cancelar no escribe archivos. Una publicación sin aportes conserva las frases
existentes. Publicar ahora fusiona el catálogo anterior y el aporte por abreviatura:
añade las nuevas y actualiza las coincidentes sin retirar las demás.

La eliminación solo se solicita con «Eliminar del catálogo…», seleccionando una
frase y confirmando la nueva versión. Se exige una sesión administradora tanto
al preparar como al escribir. Un usuario no puede publicar una vista que retire
frases. El autor es el usuario de la sesión (Windows en el uso directo del servicio)
y la fecha se guarda en UTC. La nueva
versión es la publicada + 1, independientemente de la versión de la base local.

La preparación y escritura trabajan fuera de Tkinter, con un snapshot tomado
en el hilo dueño de SQLite. Los mensajes y la confirmación se atienden mediante
una cola en el hilo de la interfaz. El snapshot confirmado puede diferir de
cambios hechos en el editor después de pulsar el botón: vuelve a publicar para
incorporarlos. No se publica automáticamente.

## Integridad y concurrencia

El servicio valida con el contrato existente. Crea publicando.lock de forma
exclusiva con autor, hora y token; rechaza una marca vigente e intenta retirar
una caducada después de dos minutos. Mantiene abierto su descriptor mientras
publica (Windows impide borrar un candado que sigue abierto). No elimina una
marca de otro propietario. En carpetas sincronizadas, la exclusividad local
no sustituye un bloqueo distribuido: usa un único administrador por carpeta.

Se escriben temporales en la misma carpeta, se vacían buffers con flush/fsync
y se reemplazan los archivos mediante os.replace: catalogo.json primero y
version.json al final. Se relee con RF-05 para verificar versión e integridad.
Si otra publicación cambió la versión/hash desde la vista previa, se exige
preparar y confirmar otra vista.

Los fallos controlados después de comenzar los reemplazos intentan restaurar
los bytes anteriores y limpiar temporales y candado. Si la restauración falla
por pérdida de red o permisos, el mensaje indica que la carpeta requiere revisión.

**Límite:** dos archivos separados no forman una transacción del sistema de
archivos. Un corte de energía o finalización forzada entre reemplazos puede
dejar el catálogo nuevo junto con la versión anterior. RF-05 rechaza esa pareja
por su hash y RF-06 conserva el catálogo local instalado; no acepta datos a
medias. No se garantiza recuperar los archivos anteriores tras una interrupción
abrupta. El requisito de que el lector vea siempre la pareja anterior completa
durante ese intervalo requiere un formato con generaciones o manifiesto,
pendiente de revisión. Evita cerrar la aplicación durante una publicación.

## Política de frases personales

Bayron eligió rechazar cualquier abreviatura compartida que coincida con una
propia, aunque el contenido sea idéntico. Por ello el equipo que publica sigue
usando sus frases propias y su sincronización puede informar conflictos con su
propio catálogo. No se cambió esa política. Los otros equipos reciben las frases
como compartidas si no tienen abreviaturas personales en conflicto.

## Acceso y roles locales

Al iniciar la aplicación se solicita usuario y contraseña. En el primer arranque
se crea el administrador inicial; no hay credenciales predeterminadas. Desde
esa sesión, «Administrar usuarios» permite listar cuentas y crear usuarios o
administradores. Selecciona una fila para cambiar el nombre, rol o contraseña;
una contraseña vacía conserva la actual. «Eliminar cuenta» exige confirmación
y no elimina frases. No se puede borrar ni renombrar/degradar la propia cuenta
activa, ni dejar la instalación sin administradores. Los cambios invalidan las
sesiones anteriores de la cuenta afectada; si cambias tu propia contraseña,
solo tu sesión actual se conserva. Los usuarios generales no pueden listar ni
modificar cuentas. La tabla nunca muestra hashes, sales ni contraseñas.
Las claves requieren diez caracteres y se almacenan mediante PBKDF2-SHA256
con 600.000 iteraciones y sal aleatoria, nunca como texto. Cerrar sesión cierra
la aplicación e invalida la sesión; vuelve a abrirla para entrar con otra cuenta.

Las cuentas están en usuarios.db junto a la base local. Son por instalación;
no constituyen un servidor de autenticación compartido. El control de rol se
aplica dentro de FraseYa. Quien tenga acceso de escritura directo a la carpeta
o a las bases puede modificar los archivos fuera del programa; los permisos
de Windows/red deben administrarse para proteger esos recursos.

Eliminar del catálogo no borra tu copia personal. Si luego publicas esa copia
otra vez, se vuelve a añadir al catálogo. Eliminar una frase personal con el
botón del editor tampoco retira la publicada: son acciones separadas.

## Pruebas

tests/test_publicacion.py cubre primera/segunda versión, diferencias,
Unicode/variables/colores, origen propio, catálogo vacío, vista obsoleta,
candado vigente/caducado, fallo entre reemplazos con restauración, disco lleno,
permisos, validación múltiple, verificación posterior y publicación/sincronización
de dos versiones hacia tres bases con frases personales distintas.
La prueba gráfica cubre falta de carpeta, resumen, cancelar sin escritura y
publicación confirmada en una carpeta temporal.

Falta comprobar en equipos Windows reales la carpeta de red, permisos,
interrupciones de red y expansión de las frases recibidas. La prueba de tres
bases es automatizada en un equipo, no una prueba de tres computadores físicos.
