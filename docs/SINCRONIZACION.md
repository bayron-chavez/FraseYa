# RF-06: sincronización automática

FraseYa comprueba el catálogo al arrancar y cada intervalo configurado
(1–1440 minutos). «Sincronizar ahora» solicita otra comprobación. Configuración
permite cambiar carpeta e intervalo sin reiniciar; el cambio despierta el
trabajador y descarta una lectura del origen anterior que siga en curso.

El servicio lee primero version.json y solo descarga el catálogo completo
cuando la versión es posterior a la instalada. Nunca retrocede. RF-05 valida
formato, cantidad, hash y estabilidad de la publicación antes de aplicar.

La actualización sustituye las frases compartidas en una transacción SQLite
y conserva las frases personales. Política elegida por Bayron: cualquier
abreviatura compartida repetida con una propia rechaza TODO el catálogo,
incluso si su contenido coincide. El mensaje enumera las abreviaturas que
deben renombrarse. Se comparan sin distinguir mayúsculas mediante casefold.

Los resultados son actualizada, sin_cambios y error, registrados en
SINCRONIZACION. reemplazar_compartidas registra el éxito dentro de la misma
transacción. Una solicitud omitida porque otra está ejecutándose no crea un
registro adicional. Las lecturas descartadas por cierre o cambio de origen
tampoco se aplican. Una carpeta inaccesible o un documento inválido conserva
la última versión local para seguir trabajando sin conexión.

Cada ciclo abre y cierra su propia conexión SQLite en el hilo trabajador.
La interfaz recibe resultados mediante una cola atendida con after. Las
actualizaciones refrescan lista, motor y catálogo del buscador desde Tkinter.
Si se estaba viendo una frase compartida retirada, se limpia su selección;
el editor de una frase propia no se reinicia.

El cierre señala un evento y no espera las operaciones de red. El trabajador
es daemon. Una escritura SQLite que ya haya comenzado termina de forma
transaccional; el cierre no la interrumpe a mitad. Los callbacks del servicio
se ejecutan en el hilo que sincroniza: los consumidores gráficos deben
encolarlos, como hace la ventana principal.

## Validación

Las pruebas cubren versiones, primera instalación, conservación de propias,
conflictos incluso idénticos, archivos dañados, rollback, cambio de origen
durante lectura, candado, ciclo con conexión propia, tres bases locales y
recarga del motor. La prueba de ventana verifica recepción por cola y
actualización en el hilo de Tkinter.

RF-08 aún debe implementar la publicación del administrador. Las pruebas
actuales generan publicaciones con serializar; no acreditan todavía el flujo
real administrador → tres equipos ni una unidad de red desconectada.

Prueba manual: elegir una carpeta con un catálogo válido, guardar el ajuste
y comprobar las frases compartidas. Publicar una versión mayor con otra frase
y pulsar «Sincronizar ahora». Renombrar temporalmente la carpeta: debe
mostrarse un error y continuar disponible el catálogo local. Restaurarla y
reintentar. Confirmar que una frase nueva se expande sin reiniciar.
