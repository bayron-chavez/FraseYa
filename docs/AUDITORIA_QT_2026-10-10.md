# Migración y auditoría de seguridad — 10 de octubre de 2026

## Resultado y alcance

La entrada principal y el instalador 0.2.0 utilizan la interfaz Qt de producción. Conservan SQLite y Supabase. Se migraron biblioteca, edición, favoritas/deshacer, variables, acceso, sincronización, publicación, categorías, importación Excel, perfil empresarial, IA, bandeja y buscador/expansión. No se modificaron cuentas reales ni datos del catálogo durante la auditoría.

## Verificación

- 312 pruebas de Python de dominio, infraestructura y Qt, más 33 subpruebas, correctas. Incluyen conservación de datos al cerrar, pausa del teclado en ventanas propias, acceso fallido, ausencia de doble petición de login y generación IA guardada en el hilo de SQLite.
- 63 pruebas de regresión de la interfaz anterior correctas, ejecutadas en un proceso separado por las restricciones gráficas de Windows.
- 31 controles en PostgreSQL aislado correctos: roles, RLS, revocación, inyección SQL, publicación atómica y control de versiones.
- Auditoría PostgreSQL adicional de IA y empresa correcta: anónimo/inactivo bloqueados, edición solo administrativa, campos acotados y límites de consumo.
- 11 pruebas de la función IA correctas: sesión, cuenta activa, cuota, datos de entrada, claves solo al proveedor y rechazo de identificadores inventados por inyección de prompt.
- Consultas reales de solo lectura al proyecto Supabase: catálogo, perfiles, perfil RPC y función IA rechazan acceso anónimo. Estas comprobaciones no equivalen a una prueba de intrusión autenticada contra toda la configuración desplegada.
- pip-audit sobre las versiones instaladas y sus dependencias: sin vulnerabilidades conocidas en el registro consultado. No garantiza que no existan vulnerabilidades nuevas.
- Ejecutable Qt: diagnóstico con SQLite en memoria y construcción/cierre de la ventana, código de salida 0. Instalador compilado con conexión pública validada, sin copiar las bases locales, cuentas ni la clave Gemini.

## Protecciones revisadas y correcciones

SQLite usa parámetros en las consultas con datos introducidos por usuarios. Las funciones SQL remotas validan roles y cuentas activas; modificar botones del cliente no concede privilegios. No se incluyen claves secret/service_role en el cliente; Gemini permanece como secreto de la función. Los tokens de sesión se mantienen en memoria, las contraseñas se limpian del formulario y los errores HTTP no revelan cuerpos ni tokens. URL HTTPS validada y redirecciones bloqueadas.

El login tiene límite local de cinco peticiones por minuto y respeta el bloqueo HTTP 429. La ventana admite una sola petición simultánea. La IA tiene cuotas en servidor. Excel limita tamaño/expansión ZIP, rechaza fórmulas y usa un parser XML protegido.

Los textos de usuarios y de IA se muestran como texto plano: se evita que Qt interprete etiquetas HTML o cargue imágenes remotas en etiquetas. No se accede a SQLite desde los trabajadores de red. No se cierra una ventana durante una publicación pendiente. El teclado global se pausa cuando FraseYa tiene foco.

Se corrigió la definición de las estructuras ctypes del teclado para permitir más de una instancia. Se excluyó una DLL ICU de otra herramienta encontrada por el empaquetador que impedía iniciar Qt; se utiliza el ICU del sistema en Windows 10 1809 o superior.

## Riesgos y límites que permanecen

1. **Datos locales:** SQLite no está cifrado ni separado por cuenta de Supabase. Dos personas que usan el mismo perfil de Windows pueden acceder a la misma biblioteca y caché; el modo sin conexión también permite leerla. No almacenar información confidencial en un perfil de Windows compartido. Esta auditoría no cambió la estructura ni trasladó los datos existentes.
2. **Abuso del login:** el límite local se puede eludir modificando o reiniciando el cliente. La protección real depende de los límites de Supabase Auth y, cuando corresponda, CAPTCHA. No se verificaron ni modificaron sus valores de configuración en el dashboard durante esta auditoría.
3. **IA:** el mensaje y las frases candidatas se envían al proveedor. La generación puede conservar datos personales aportados o producir información incorrecta. Debe revisarse antes de enviar; no hay garantía de anonimización. La validación de la salida limita el formato, pero no prueba que todas las afirmaciones sean ciertas.
4. **Cuota compartida:** cuentas activas pueden consumir la cuota global diaria. La reserva protegida por RLS no elimina todo riesgo de denegación de servicio entre usuarios autenticados.
5. **Distribución:** instalador sin firma de código. No se probó en tres equipos físicos ni se hizo una prueba destructiva contra producción. Las pruebas de roles/inyección se ejecutaron en una base aislada con las migraciones del repositorio.

No se afirma que el programa sea imposible de hackear. Los resultados describen los controles comprobados y los límites de la revisión.
