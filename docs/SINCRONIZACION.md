# Sincronización con Supabase

ServicioSincronizacion inicia una comprobación al abrir FraseYa y después
respeta el intervalo configurado. Sincronizar ahora despierta el servicio.
Cada hilo utiliza su propia conexión SQLite; la interfaz recibe resultados
mediante una cola y aplica los cambios en el hilo de Tkinter.

Se valida el catálogo remoto, su formato y su hash antes de guardarlo. Se
aceptan versiones posteriores del mismo proyecto; las versiones de proyectos
diferentes se distinguen mediante su origen. Una actualización reemplaza solo
las frases compartidas y conserva las propias en una transacción.

Cualquier abreviatura compartida que coincida con una propia, incluso con
contenido idéntico, rechaza toda la actualización. No hay fusión automática de
frases personales. El historial guarda el resultado de cada comprobación.

Un error de red, permiso o formato conserva la última copia local. Trabajar
sin conexión permite expandir, buscar y gestionar datos del equipo, sin
privilegios remotos. Para conectarse nuevamente hay que cerrar e iniciar sesión.

Las pruebas cubren versiones, conflictos, rollback, cambios de intervalo,
conservación de frases en tres bases independientes y cierre durante lectura.
