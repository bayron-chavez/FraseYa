# Configuración de Supabase

FraseYa usa Supabase Auth para el login por correo y su Data API para el catálogo.
SQLite mantiene las frases propias y la última copia compartida.

## Proyecto nuevo

1. Crear el proyecto alojado en supabase.com. Habilitar Data API y RLS automático;
   deshabilitar la exposición automática de tablas.
2. Ejecutar en SQL Editor, en orden y una sola vez, las migraciones 001 y 002
   de supabase/migrations.
3. Crear las cuentas en Authentication → Users. En fraseya_perfiles habilitar
   activo y asignar rol usuario o administrador. El registro no habilita acceso
   por sí solo: todas las cuentas nuevas nacen inactivas.
4. Desde la raíz del proyecto ejecutar python scripts/configurar_supabase.py.
   Introducir la URL del proyecto *.supabase.co y su clave pública publishable
   o anon heredada. No usar la contraseña PostgreSQL, secret ni service_role.
5. Abrir python main.py e iniciar sesión con la cuenta creada.

## Proyecto existente

Si ya ejecutaste 001 y FraseYa funciona, ejecuta SOLO
supabase/migrations/202610050002_seguridad.sql. Conserva perfiles y catálogo.
Después ejecuta supabase/auditoria_permisos.sql: los controles deben ser true.
La migración no se aplica automáticamente desde la aplicación.

## Dos equipos

Configurar ambos con el mismo proyecto y crear una cuenta habilitada para cada
persona. Publicar desde el administrador, sincronizar desde el usuario y
comprobar las frases. El usuario no puede publicar ni eliminar el catálogo.
Probar también una cuenta inactiva y una publicación con versión obsoleta.

## Cuenta y datos del equipo

Las cuentas se administran en Authentication → Users y los roles en
fraseya_perfiles. Se retiró el CRUD local y la publicación por carpeta de red.
No se migran ni borran automáticamente bases de cuentas anteriores del equipo.
La copia SQLite no está cifrada ni separada por correo; proteger la cuenta de
Windows y no compartir su perfil entre personas que requieran datos aislados.

Trabajar sin conexión abre la copia local sin autenticar contra el servidor.
No permite publicar o sincronizar. No puede descargar datos nuevos mientras
Supabase no esté disponible. Contraseñas y tokens remotos permanecen en memoria.

## Alcance

El ERS original excluía servicios web y autenticación. Actualizar esos apartados
y RNF-06/RNF-10 para reflejar el cambio autorizado; el informe DOCX no se ha
modificado. El plan gratuito tiene límites y puede pausar proyectos con poca
actividad. La app no implementa respaldos del catálogo en la nube.

Fuentes: https://supabase.com/pricing,
https://supabase.com/docs/guides/database/postgres/row-level-security,
https://supabase.com/docs/guides/database/functions.
