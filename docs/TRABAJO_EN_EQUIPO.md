# Trabajo de Bayron y Diego

La tarjeta compartida Setup prepara el proyecto para integrar ambos trabajos.
Esta carpeta es un repositorio Git local. Aún falta elegir y conectar el
repositorio remoto común del equipo; no se han enviado archivos a terceros.

## Responsabilidades

- Bayron: persistencia SQLite, gestión de frases, categorías y sincronización.
- Diego: entidades de dominio, expansión de texto, buscador global y otros
  módulos asignados en Trello.
- Ambos: acordar interfaces, integrar los módulos y revisar los cambios.

## Flujo recomendado

1. Utilizar el mismo repositorio remoto cuando el equipo lo acuerde.
2. Crear una rama por tarea, por ejemplo bayron/catalogo o diego/dominio.
3. Mantener los cambios dentro de la capa correspondiente.
4. Ejecutar las pruebas antes de compartir un cambio.
5. Revisar e integrar los cambios con el otro integrante.

Los resultados actuales del repositorio son diccionarios. Las entidades de
Diego pueden incorporarse mediante adaptadores, conservando el contrato de
persistencia. No duplicar el esquema ni incluir bases personales en Git.

## Estado de la tarjeta Setup

- Repositorio Git local: creado en main.
- README y .gitignore: preparados.
- Capas presentacion, aplicacion, dominio e infraestructura: preparadas.
- Entorno virtual: creado.
- requirements.txt: preparado.
- Punto de entrada main.py: implementado.
- Instalación de dependencias: bloqueada por la red de esta sesión.
- Ejecución de pytest: pendiente hasta instalarlo.

La tarjeta debe permanecer En progreso hasta verificar pytest sin errores.
El arranque y las pruebas pueden comprobarse con Python estándar mientras
se resuelve esa instalación. La tarjeta no exige publicar en GitHub; el
remoto compartido sigue siendo una decisión pendiente del equipo.
