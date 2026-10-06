# Auditoría de seguridad de FraseYa

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
proyecto existente. Este informe NO afirma que ya se haya aplicado.

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
   usuarios/admin se ejecutaron en la base aislada, no con cuentas reales.

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
