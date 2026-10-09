# Auditoría de seguridad de FraseYa

## Revisión adicional del 8 de octubre de 2026

Se repitieron los 31 controles PostgreSQL aislados y las tres consultas anónimas
al proyecto real: acceso al catálogo, perfiles y RPC de perfil denegado.
Se añadió protección local de login con cinco intentos por minuto por instancia,
independiente del correo, sincronizada entre hilos. Ante HTTP 429 se impide enviar
nuevos intentos durante cinco minutos. No se reinicia el presupuesto por logout
o por login correcto; cerrar la aplicación sí reinicia este límite local.
El 8 de octubre se redujo el límite real de inicios de sesión/registro de
Supabase de 30 a 15 peticiones por IP cada cinco minutos y se verificó el guardado.
No se ejecutó una ráfaga de contraseñas contra cuentas reales para alcanzar
el límite: el manejo de HTTP 429 y la concurrencia se probaron con transportes
aislados. La configuración en servidor cubre llamadas directas y varias instancias.

La consulta de auditoría real devolvió true en sus once controles. La función
fraseya_publicar coincide con el cuerpo de la migración 002 (comparación del hash
normalizando espacios); es SECURITY DEFINER con search_path vacío. No fue
necesario aplicar migraciones ni modificar datos de cuentas o del catálogo.

El login rechaza campos vacíos/excesivos antes de la petición, invalida la sesión
anterior al intentar otra cuenta y borra la contraseña del formulario tras la
respuesta. El backend mantiene tokens solo en RAM y los descarta tras un fallo.
Las pruebas incluyen cien intentos concurrentes sobre el limitador: solo cinco
obtienen permiso; credenciales erróneas producen un mensaje común.

Excel se procesa con XML protegido, sin fórmulas ni macros y con límites de
archivo, número de partes, tamaño descomprimido y filas. Se probaron fórmulas,
duplicados, ZIP excesivo y entidades XML externas. Los textos con instrucciones
SQL se almacenan como datos. La creación de categorías nuevas requiere verificar
administrador. Los permisos de publicación siguen comprobándose en PostgreSQL.

La recuperación de SQLite se probó terminando un proceso con una transacción
abierta: la reapertura conserva las frases y versión anterior y pasa integrity_check.
La revisión actual de dependencias, incluidas Pillow, pystray y defusedxml, no
encontró vulnerabilidades conocidas. Consulta `DEPENDENCIAS_AUDITADAS.txt` para
las versiones revisadas. Esto no constituye una garantía frente a nuevos ataques.

Referencias: [límites de Supabase Auth](https://supabase.com/docs/guides/auth/rate-limits)
y [configuración de producción](https://supabase.com/docs/guides/deployment/going-into-prod).

Fecha: 5 de octubre de 2026. Alcance: código actual, SQLite, cliente Supabase,
funciones y permisos SQL entregados, pruebas locales y consultas anónimas al
proyecto configurado. No se realizó una prueba de penetración integral ni se
verificó toda la configuración del dashboard. No garantiza ausencia de ataques.

## Hallazgos corregidos

| Riesgo | Evidencia anterior | Corrección |
| --- | --- | --- |
| Envío del login a un servidor ajeno | La configuración aceptaba cualquier URL HTTPS | Solo se aceptan proyectos alojados en *.supabase.co, sin credenciales, puertos ni rutas |
| Filtración de sesión por redirección | urllib seguía redirecciones automáticamente | Se rechazan las redirecciones antes de reenviar la solicitud |
| Reutilización de sesión local | El identificador de sesión era el UUID estable de la cuenta | Identificador aleatorio nuevo por login; sesión anterior inválida |
| Ruta alternativa de autenticación | Si faltaba configuración se abría el login local | Solo Supabase; ausencia de configuración produce error explícito |
| Datos remotos fuera del contrato | El servidor permitía claves adicionales y tipos de formato demasiado permisivos | Migración 002 valida claves, tipos, límites y metadatos antes de guardar |
| Permisos heredados adicionales | La migración inicial no revocaba permisos de PUBLIC ni posibles grants por columna | Migración 002 revoca ambos y añade RLS restrictivo para miembros activos |
| Tokens y respuestas inválidas | Algunas respuestas malformadas podían dejar sesión parcial o producir errores internos | Validación de tokens/perfil/catálogo y descarte de sesión ante HTTP 401 |

La migración 002 es necesaria para aplicar los refuerzos del servidor al
proyecto existente. La comprobación del 8 de octubre confirma sus permisos
y función de publicación en el proyecto revisado.

## Inyección SQL

No se identificó concatenación de entradas del usuario en SQL ejecutable.
SQLite utiliza placeholders. Los WHERE dinámicos se componen únicamente con
cláusulas fijas; los valores se pasan separados. La función PostgreSQL utiliza
parámetros y SQL estático; no usa EXECUTE dinámico ni interpreta los textos del
catálogo como comandos. Las pruebas almacenan texto con DROP TABLE y comprueban
que se conserva literalmente y que las tablas siguen existiendo.

## Evidencia

- Las consultas anónimas reales al catálogo, perfiles y RPC de perfil fueron
  rechazadas por Supabase. No se descargaron contenidos ni se imprimieron claves.
- PostgreSQL aislado con PGlite: 31 controles correctos, incluyendo ambos scripts
  de migración, RLS, permisos anónimos, usuario inactivo, escalamiento de rol,
  revocación de administrador, versión obsoleta/nula, hash y SQL malicioso.
- pip-audit 2.10.1 revisó 20 paquetes instalados del proyecto y sus dependencias:
  no encontró vulnerabilidades conocidas en la consulta realizada. Esto no
  certifica el runtime de Python/Tk ni versiones que se instalen posteriormente.
- Las pruebas Python de seguridad, persistencia, contrato, sincronización y GUI
  verifican conservación de datos, rechazo de conflictos y cancelación antes
  de publicación. La matriz de permisos real aún requiere ejecutar el SQL de
  auditoría en el proyecto después de aplicar 002.

## Riesgos y controles pendientes

1. La copia SQLite está en texto claro. Trabajar sin conexión abre los datos
   del perfil de Windows sin autenticar remotamente. Varias cuentas que usen
   el mismo perfil no tienen frases personales aisladas por correo. Usar
   perfiles de Windows separados; cifrado local y separación por cuenta serían
   cambios adicionales de producto, no implementados en esta revisión.
2. Quien administra el proyecto Supabase o posee una service_role/secret key
   puede saltarse RLS. No distribuir esas claves en el ejecutable ni GitHub.
   Revisar los administradores del dashboard y habilitar MFA en esas cuentas.
3. Revisar en Auth los límites de intentos, política de contraseña y el registro
   público. Las cuentas nuevas quedan inactivas incluso si el registro público
   está habilitado. Supabase tiene límites de autenticación, pero no se midió
   resistencia a abuso ni se habilitó CAPTCHA en esta auditoría.
4. Hay un solo catálogo por proyecto. No hay separación por empresas o grupos.
   Cada grupo que requiera aislamiento necesita su propio proyecto o un cambio
   explícito de modelo y reglas de acceso.
5. Configurar respaldos y recuperación, especialmente en el plan gratuito.
   FraseYa no implementa backup remoto. El dueño de Windows puede modificar el
   ejecutable, configuración y SQLite; no se promete protegerlo contra su propio
   administrador del sistema.
6. Falta comprobar en el dashboard todas las extensiones, políticas adicionales
   y credenciales históricas. La auditoría real fue anónima; los controles con
  usuarios/admin se ejecutaron en la base aislada, no mediante inicios de sesión
  con contraseñas reales. El 8 de octubre también se comprobaron permisos y la
  función de publicación desde SQL Editor en la base real.

## Aplicar y comprobar

Ejecutar SOLO supabase/migrations/202610050002_seguridad.sql en el proyecto
existente; no repetir 001. Luego ejecutar supabase/auditoria_permisos.sql y
comprobar que todos los controles resultan true. La migración no elimina
cuentas ni catálogo. Reiniciar FraseYa tras actualizar el código.

Para repetir el control público: python scripts/auditar_acceso_publico.py.
Para PostgreSQL aislado: en supabase/tests, npm install --ignore-scripts y npm test.

Referencias oficiales: https://supabase.com/docs/guides/api/securing-your-api,
https://supabase.com/docs/guides/database/functions,
https://supabase.com/docs/guides/auth/rate-limits,
https://supabase.com/docs/guides/auth/password-security.
