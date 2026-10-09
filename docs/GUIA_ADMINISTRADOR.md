# Guía del administrador de FraseYa

Esta versión usa Supabase Auth y PostgreSQL para cuentas, permisos y catálogo;
cada equipo conserva frases propias y una copia compartida en SQLite.

## Preparar el proyecto

Sigue `SUPABASE.md`. En un proyecto nuevo aplica las migraciones 001 y 002 en
orden. En uno existente con 001 instalada aplica solo 002. Ejecuta después
`supabase/auditoria_permisos.sql`: todos los controles deben dar true. No se
da por aplicada una migración por tener el archivo en GitHub.

Crea las cuentas en Authentication → Users. En `fraseya_perfiles` habilita
`activo` y establece `rol` como `usuario` o `administrador`. No compartas cuentas
administradoras. Los clientes no pueden asignarse roles ni modificar perfiles.
Una cuenta recién creada está inactiva hasta su habilitación explícita.

En Authentication → Rate Limits revisa el límite de inicios de sesión/registro
por IP. En el proyecto revisado se configuraron 15 peticiones cada cinco minutos.
La aplicación limita cinco peticiones por minuto por instancia y espera
cinco minutos ante HTTP 429, pero esa protección no sustituye los límites del
servidor. Mantén deshabilitado el registro público si todas las cuentas las crea
el administrador; revisa la política de contraseña y MFA de los propietarios
del proyecto. No actives CAPTCHA sin integrar su desafío en el cliente.

## Publicar y gestionar categorías

Prepara frases propias o importa Excel. «Gestionar categorías» permite crear,
renombrar y asignar color. Eliminar solo se admite si la categoría no tiene
frases; General se conserva. Reasigna las frases antes de eliminar categorías.
La publicación vuelve a comprobar la categoría remota: si otra persona añadió
frases mientras tanto, rechaza la eliminación.

Pulsa «Publicar catálogo» y revisa la versión y los recuentos antes de confirmar.
La publicación conserva las frases que no incluiste en tu aporte, mantiene las
categorías vacías y aplica cambios de nombres/colores. El servidor valida el rol
actual, el hash, los límites y la versión en una transacción. Si otro administrador
publicó primero, prepara una nueva vista previa.

«Eliminar del catálogo» retira explícitamente una frase compartida tras la vista
previa. Los usuarios la dejan de ver al sincronizar. Publicar no borra tus frases
propias; si una abreviatura propia coincide con una compartida, la sincronización
se rechaza conforme a la política elegida. Renombra o elimina la copia propia
cuando quieras adoptar esa frase desde el catálogo central.

Los renombrados/eliminaciones de categorías quedan registrados localmente para
publicar. No distribuyas la base SQLite del administrador a los otros usuarios.
Para recuperar un fallo de publicación, sincroniza y prepara de nuevo; la
condición de versión evita sobrescribir silenciosamente una publicación reciente.

## Distribuir

El portable completo está en `dist/FraseYa-portable.zip`. Distribuye toda su
carpeta, incluido `_internal`. Cada equipo configura la misma URL/clave pública
y utiliza su propia cuenta. Los paquetes se generan sin `datos`, contraseñas,
tokens, claves privadas ni bases personales. No requieren instalar Python ni
permisos de administrador. El ejecutable no tiene firma digital de un proveedor.

Para recompilar instala `requirements.txt` y ejecuta `scripts/empaquetar.ps1`.
El comando `FraseYa.exe --diagnostico` comprueba las dependencias y el esquema
sin conectarse ni crear una base personal; un código de salida cero indica éxito.
`FraseYa.exe --configurar` abre la configuración inicial nuevamente.

## Respaldo y validación

Respalda las bases locales con la aplicación cerrada y establece recuperación
para el proyecto Supabase. Comprueba la versión y una frase de prueba en cada
equipo después de publicar. Ejecuta las pruebas y lee `VALIDACION.md` y
`SEGURIDAD.md` antes de considerar una entrega en producción. Las pruebas de
tres clientes aislados en un ordenador no certifican tres equipos físicos.
