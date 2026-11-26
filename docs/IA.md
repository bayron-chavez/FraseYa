# Recomendaciones de frases con Gemini

FraseYa ofrece dos modalidades asistidas por Gemini (siempre bajo control del operador y sin envío automático):

1. **Panel manual («Sugerir respuesta · IA»):** el usuario pega voluntariamente el mensaje o hilo del cliente.
2. **Asistente en vivo opcional (barra flotante):** cuando el usuario lo activa explícitamente en sesión conectada, observa únicamente la ventana activa de WhatsApp Desktop (vía Windows UI Automation, solo texto en memoria) o pestañas de WhatsApp Web (con la extensión local opcional en `127.0.0.1:47821`). Al pulsar **«Leer últimos 3»** o **«Portapapeles»**, propone hasta 3 opciones de respuesta.

En ambos flujos, Gemini recomienda hasta tres frases existentes o, mediante el modo unificado `asistir` del asistente en vivo, evalúa el catálogo y genera directamente hasta 3 variantes reales diferenciadas por tono (`Empática`, `Directa` y `Escalar`) en una sola consulta. Permite emojis sobrios y moderados cuando el cliente no está molesto, y formatea las enumeraciones de productos o servicios en líneas separadas con viñetas (`  · `). Cuando el usuario inserta o edita desde el asistente en vivo, **nunca modifica ni muta frases compartidas existentes**: las variantes reescritas se etiquetan como borradores efímeros en memoria (`borrador_ia`) y el guardado desde el panel manual genera únicamente una frase propia con abreviatura libre (`!ia`, `!ia2`, etc.), sin publicar en el catálogo compartido.

La instrucción de generación pide sustituir datos personales y de transacciones por variables oficiales cuando corresponda, y evitar inventar precios o políticas. Esto depende del modelo y no garantiza anonimización completa: revisa la plantilla antes de enviarla o guardarla. Las respuestas con campos inesperados o variables inválidas se rechazan. Una generación idéntica a una frase propia existente reutiliza esa frase.

La selección exige pertinencia para la necesidad concreta y tono profesional; los saludos genéricos y las frases de prueba no son suficientes. Cuando el contexto incluye turnos previos identificados como `Cliente:` y `Agente:`, el asistente continúa la conversación sin volver a saludar ni reiniciar el hilo. Estas reglas están en `systemInstruction` dentro de `supabase/functions/fraseya-ia/logica.mjs`.

## Configuración del servidor

1. Aplicar `supabase/migrations/202610100003_ia.sql` en el SQL Editor.
2. Desplegar `supabase/functions/fraseya-ia`. La configuración `verify_jwt = false` sustituye la verificación antigua del gateway por una consulta a Supabase Auth dentro de la función, seguida de la comprobación del perfil activo.
3. En Edge Functions → Secrets, guardar `GEMINI_API_KEY`. Nunca guardar esa clave en el repositorio, la aplicación ni el instalador.
4. Opcionalmente guardar `GEMINI_MODEL`; el valor predeterminado es `gemini-3.8-flash`. La disponibilidad y cuota dependen de la cuenta de Google.
5. Iniciar sesión en FraseYa, guardar frases y solicitar una recomendación con un mensaje de prueba sin datos personales.

## Perfil de empresa y conversación

Aplicar también `supabase/migrations/202610100004_empresa_ia.sql`. En el panel IA, el administrador dispone de «Configurar perfil de empresa»: nombre, servicios/productos, horarios y políticas/procedimientos. Este contexto es común a los equipos del proyecto Supabase; guardarlo requiere un perfil administrador activo comprobado por el servidor. Los usuarios activos pueden leerlo, pero no modificarlo. No incluir secretos, expedientes ni datos de clientes.

La función carga el perfil desde Supabase en cada consulta y lo envía a Gemini junto al mensaje y las candidatas. Un perfil vacío no introduce políticas ficticias: el prompt solicita aclaraciones. Los textos leídos en vivo desde WhatsApp se mantienen estrictamente en RAM durante la sesión y nunca se persisten en SQLite ni en disco.

## Datos y límites

Se envía a Gemini el mensaje escrito o leído bajo demanda (hasta 4.000 caracteres), junto con hasta 40 candidatas: identificador, título, categoría y hasta 1.600 caracteres de contenido por frase. La preselección local usa coincidencias de palabras y favoritos. La frase elegida conserva su contenido original completo.

La función no registra mensajes, claves ni tokens. El contador de solicitudes guarda identificador del usuario, periodo y cantidad. El proveedor recibe los textos enviados; revisa sus condiciones de tratamiento de datos antes de usar conversaciones sensibles.

El servidor permite 5 reservas por minuto y 50 al día por usuario, con un máximo conjunto de 1.000 al día (día UTC). Las llamadas fallidas al proveedor también consumen reserva. El cliente añade un límite local de 5 solicitudes por minuto.

## Controles verificados

La función exige una sesión válida y un perfil activo. Las tablas de contadores tienen RLS y no permiten lectura ni modificación directa a usuarios o anónimos. La reserva se ejecuta de forma serializada entre equipos. El servidor valida tamaño, campos, identificadores y respuesta del proveedor; rechaza frases inventadas, duplicados o contenido alternativo.

Pruebas: `tests/test_recomendaciones_ia.py`, `tests/test_ia_generacion.py`, `tests/test_asistente_vivo.py`, `tests/test_qt_vista.py`, `supabase/tests/ia.mjs`, `supabase/tests/ia_permisos.mjs` y `supabase/tests/extension_wsp.test.mjs`. Las pruebas simuladas no sustituyen una prueba real del proveedor con la clave y cuota de la cuenta.
