# Validación de FraseYa

Revisión del 8 de octubre de 2026. Se conserva la separación en capas del ERS.
La elección posterior de Supabase sustituye la carpeta de red en RF-05/RF-08
y modifica las restricciones originales de RNF-06/RNF-10: se transmiten cuentas
y catálogo al proyecto configurado. No se leen conversaciones ni se integra
la aplicación con plataformas de mensajería.

## Evidencia ejecutada

La ejecución completa final pasó 319 pruebas y 33 subpruebas, con 85,84 % de
cobertura. La prueba adicional del asistente portable también pasó: total 320
pruebas y cobertura acumulada 86,90 %. La cobertura
mínima de 70 % está configurada para fallar la validación si no se alcanza.

Tras agregar el menú de variables, la vista previa, favoritos y recuperación de
frases propias, la suite completa volvió a pasar: 335 pruebas y 33 subpruebas.
Esta ejecución adicional no volvió a medir cobertura. Incluye conservación de
favoritas al reabrir y sincronizar, recuperación con variables, rechazo de
eliminación de compartidas y rechazo de recuperación con abreviatura ocupada.

| Objetivo | Comprobación |
| --- | --- |
| RF-09 | Versión persistida, fecha local, error y bandeja; inicio/actualización/cierre nativos en Windows |
| RF-10 | Crear, renombrar, eliminar vacío, color, filtro; autorización admin y conservación de frases al publicar |
| RF-12 | Filas válidas/rechazadas, fórmulas prohibidas, duplicados, categorías admin y rechazo de ZIP de más de 50 MB |
| RF-07 e integración | Tres bases y clientes aislados: publicación, cambio de categoría, sincronización, corte de red, búsqueda, expansión y edición local, reapertura |
| QA | Cobertura global superior al mínimo del 70 %, incluyendo pruebas gráficas |
| Base central | 31 controles PostgreSQL aislados: RLS, roles, revocación, parámetros SQL, hash y versiones |
| Base real | Tres consultas anónimas rechazadas; once controles de permisos true y función de publicación coincidente con migración 002 |
| Login | Tokens, URLs, redirecciones, rol falsificado/revocado, sesión antigua, intentos simultáneos y HTTP 429; servidor configurado a 15 accesos/IP/5 minutos |
| Portable | PyInstaller Windows x64; diagnóstico del ejecutable con salida 0; sin configuración personal en el paquete |

Medición local con 1.000 frases, veinte aperturas del buscador y cinco segundos
en reposo: máximo 109,97 ms, media 82,32 ms, RAM 47,85 MB y CPU 1,56 %.
El escenario usa la interfaz sin hook de teclado ni red y no certifica el consumo
de todas las configuraciones ni de otras máquinas. Repetir con
`python scripts/verificar_rendimiento.py` en los puestos de destino.

## Límites de aceptación

RNF-02 exige insertar 1.000 caracteres en 500 ms, mientras RNF-03 exige esperar
10 a 60 ms por carácter: la duración mínima de escritura es diez segundos.
Ambos límites no pueden cumplirse simultáneamente con ese modo de escritura.
Esta versión conserva la velocidad configurable; no declara cumplido el tiempo
total de inserción de 500 ms. El buscador sí cumplió 300 ms en el escenario medido.

RNF-07 se aplica a las funciones locales. La administración remota y publicación
necesitan red; el modo offline no concede privilegios de administrador.

El diagnóstico del portable y las pruebas se ejecutaron en Windows 11 x64.
Windows 10, aplicaciones externas y tres ordenadores físicos necesitan aceptación
en sus entornos reales. No se afirma que el cliente haya recibido ni aceptado
la versión por generar el ZIP. Los permisos y la función segura de la migración
002 se comprobaron en el proyecto real. El rate limit de Supabase se guardó
a 15 accesos por IP cada cinco minutos; no se bombardearon cuentas reales para
provocar su límite.
