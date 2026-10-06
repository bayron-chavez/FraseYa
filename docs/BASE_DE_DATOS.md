# Base de datos de FraseYa

## SQLite del equipo

El esquema está en src/fraseya/infraestructura/schema.sql y contiene seis tablas:

| Tabla | Finalidad |
| --- | --- |
| CATALOGO | Versión, autor, fecha y origen propia/compartida |
| CATEGORIA | Nombre y color; pertenece a un catálogo |
| FRASE | Título, abreviatura única, contenido y origen |
| VARIABLE | Marcadores de la frase y su orden |
| SINCRONIZACION | Fecha, versión, resultado y detalle de comprobación |
| CONFIGURACION | Ajustes de teclado y sincronización |

RepositorioSQLite activa claves foráneas y transacciones. Las consultas usan
parámetros SQL. Los fragmentos dinámicos son cláusulas fijas del programa, no
nombres de tabla o instrucciones recibidas del usuario. El esquema se carga
desde un recurso del paquete, no desde el catálogo remoto.

La sincronización reemplaza el conjunto compartido completo en una transacción,
conserva las frases propias y rechaza conflictos de abreviatura. El origen del
proyecto Supabase se guarda junto a la copia para comparar versiones correctas.
No se almacenan contraseñas ni tokens remotos en esta base.

SQLite no cifra la copia ni aísla frases por correo. El perfil de Windows y los
permisos de archivo son el límite de acceso local, incluido el modo sin conexión.

## PostgreSQL central

Supabase Auth mantiene las cuentas y credenciales. fraseya_perfiles registra el
UUID del usuario, correo, rol y habilitación. Las cuentas nuevas quedan inactivas.
Los clientes no tienen permisos para escribir perfiles o asignarse roles.

fraseya_catalogo contiene una fila con el catálogo completo y sus metadatos.
Los miembros activos pueden leerla mediante RLS. Solo fraseya_publicar puede
modificarla desde la API; comprueba el administrador, valida el documento,
bloquea la versión vigente y guarda todo en una transacción.

Las migraciones 001 y 002 crean y refuerzan este contrato. La auditoría de
permisos de la base real se ejecuta con supabase/auditoria_permisos.sql.
