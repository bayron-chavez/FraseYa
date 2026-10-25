# Recomendaciones de frases con Gemini

FraseYa permite pegar voluntariamente el mensaje de un cliente en «Sugerir respuesta · IA». No lee WhatsApp ni otras conversaciones automáticamente. Gemini recomienda hasta tres frases existentes; el usuario elige y revisa la frase en el editor. Si no hay coincidencias, hace otra consulta para crear una plantilla reutilizable y la guarda automáticamente como propia, con abreviatura libre `!ia`, `!ia2`, etc. Usa categorías existentes y no publica en el catálogo compartido. No se envían respuestas automáticamente.

La instrucción de generación pide sustituir datos personales y de transacciones por variables, y evitar inventar precios o políticas. Esto depende del modelo y no garantiza anonimización completa: revisar la plantilla guardada antes de usarla. Las respuestas con campos inesperados o variables inválidas no se guardan. Una generación idéntica a una frase propia existente reutiliza esa frase. El flujo sin coincidencias consume dos reservas de IA (recomendación y generación).

La selección exige pertinencia para la necesidad concreta y tono profesional; los saludos genéricos y las frases de prueba no son suficientes. La generación usa tratamiento de usted, buena ortografía y preguntas concretas para orientar la atención, sin inventar diagnósticos ni afirmar acciones realizadas. Estas reglas están en `systemInstruction` de la función y se aplican en la siguiente consulta sin reinstalar la aplicación.

El prompt solicita personalización con `{nombre}` y otras variables únicamente cuando aporten información necesaria. Las llaves quedan en la plantilla guardada; se completan al utilizarla mediante el formulario habitual. Las frases existentes no se modifican automáticamente: si carecen de personalización, se pide al modelo generar otra plantilla propia.

## Configuración del servidor

1. Aplicar `supabase/migrations/202610100003_ia.sql` en el SQL Editor.
2. Desplegar `supabase/functions/fraseya-ia`. La configuración `verify_jwt = false` sustituye la verificación antigua del gateway por una consulta a Supabase Auth dentro de la función, seguida de la comprobación del perfil activo.
3. En Edge Functions → Secrets, guardar `GEMINI_API_KEY`. Nunca guardar esa clave en el repositorio, la aplicación ni el instalador.
4. Opcionalmente guardar `GEMINI_MODEL`; el valor predeterminado es `gemini-3.5-flash-lite`. La disponibilidad y cuota dependen de la cuenta de Google.
5. Iniciar sesión en FraseYa, guardar frases y solicitar una recomendación con un mensaje de prueba sin datos personales.

## Perfil de empresa y conversación

Aplicar también `supabase/migrations/202610100004_empresa_ia.sql`. En el panel IA, el administrador dispone de «Configurar perfil de empresa»: nombre, servicios/productos, horarios y políticas/procedimientos. Este contexto es común a los equipos del proyecto Supabase; guardarlo requiere un perfil administrador activo comprobado por el servidor. Los usuarios activos pueden leerlo, pero no modificarlo. No incluir secretos, expedientes ni datos de clientes.

La función carga el perfil desde Supabase en cada consulta y lo envía a Gemini junto al mensaje y las candidatas. Un perfil vacío no introduce políticas ficticias: el prompt solicita aclaraciones. Puede pegar varios mensajes identificados como «Cliente:» y «Agente:», dentro del límite de 4.000 caracteres, para orientar la última necesidad pendiente. No se conserva un historial de conversación ni se leen aplicaciones externas. El modelo puede interpretar mal el contexto: revisar las respuestas antes de enviarlas.

## Datos y límites

Se envía a Gemini el mensaje escrito (hasta 4.000 caracteres), junto con hasta 40 candidatas: identificador, título, categoría y hasta 1.600 caracteres de contenido por frase. La preselección local usa coincidencias de palabras y favoritos. En catálogos mayores puede omitir frases relevantes; no es una búsqueda semántica de todo el catálogo. La frase elegida conserva su contenido original completo.

La función no registra mensajes, claves ni tokens. El contador de solicitudes guarda identificador del usuario, periodo y cantidad. El proveedor recibe los textos enviados; revisar sus condiciones de tratamiento de datos antes de usar conversaciones sensibles.

El servidor permite 5 reservas por minuto y 50 al día por usuario, con un máximo conjunto de 1.000 al día (día UTC). Las llamadas fallidas al proveedor también consumen reserva. Estos límites no sustituyen la configuración de cuotas y facturación en Google. El cliente añade un límite local de 5 solicitudes por minuto.

## Controles verificados

La función exige una sesión válida y un perfil activo. Las tablas de contadores tienen RLS y no permiten lectura ni modificación directa a usuarios o anónimos. La reserva se ejecuta de forma serializada entre equipos. El servidor valida tamaño, campos, identificadores y respuesta del proveedor; rechaza frases inventadas, duplicados o contenido alternativo. Los textos son datos sin herramientas ni ejecución de SQL.

Pruebas: `tests/test_recomendaciones_ia.py`, `tests/test_recomendaciones_ia_gui.py`, `supabase/tests/ia.mjs` y `supabase/tests/ia_permisos.mjs`. Las pruebas simuladas no sustituyen una prueba real del proveedor con la clave y cuota de la cuenta.
