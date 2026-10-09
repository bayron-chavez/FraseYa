# Publicación del catálogo

El administrador puede usar «Crear categoría» junto al selector del editor.
La interfaz actual agrupa estas acciones en «Gestionar categorías», incluyendo
renombrar, asignar color y eliminar categorías vacías. Los renombrados conservan
las frases de la categoría remota. Eliminar se rechaza si hay frases locales
o si la categoría remota contiene frases al preparar la publicación.
Después debe usar «Publicar catálogo» para compartirla. Se publican también
las categorías sin frases. Los demás usuarios reciben las categorías al
sincronizar y pueden seleccionarlas para guardar sus frases propias.

Solo una cuenta administradora habilitada en Supabase puede publicar. La
interfaz recoge las frases propias y muestra una vista previa con las nuevas,
modificadas y eliminadas. El catálogo publicado conserva las frases anteriores
que no aparecen en el aporte. Eliminar requiere una acción explícita.

La función fraseya_publicar valida el rol directamente en PostgreSQL usando
la identidad de Supabase Auth. Las tablas no permiten escrituras directas de
anon ni authenticated. Cambiar un botón o un rol en la memoria del ejecutable
no concede permisos en el servidor.

La publicación usa la versión anterior como condición y bloquea la fila
central durante la transacción. Si otra publicación avanzó primero, se rechaza
la vista previa vieja. Catálogo, versión, fecha y autor se guardan juntos.
El servidor calcula la fecha y toma el autor del perfil habilitado.

El contenido se valida como JSON y nunca se ejecuta como SQL. La migración 002
rechaza claves desconocidas, formatos incorrectos y catálogos excesivos.
El administrador puede publicar un catálogo vacío solo tras confirmación en
la interfaz. La aplicación comprueba también el hash de integridad.

Los usuarios se administran en el panel de Supabase, no en el ejecutable.
Véanse SUPABASE.md y SEGURIDAD.md para configuración, pruebas y límites.
