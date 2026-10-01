# FraseYa

Proyecto Python organizado para que Bayron y Diego integren sus módulos.
Este avance implementa la preparación del proyecto y la persistencia SQLite.
El punto de entrada confirma el arranque en consola; la interfaz de escritorio
y los módulos de expansión de texto se integrarán después.

## Preparación en Windows

Requiere Python 3.10 o posterior. Desde la carpeta del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

También puede ejecutarse `preparar_entorno.ps1` desde PowerShell. Este script
crea el entorno si falta, instala las dependencias y ejecuta las pruebas.
Se puede proporcionar la ruta del Python instalado con su parámetro -Python.

El entorno .venv ya se creó en este equipo. La descarga de dependencias falló
por una restricción de red de la sesión de trabajo. Por eso pytest aún no se
ha ejecutado ni se han fijado las versiones exactas instaladas. Los rangos
de requirements.txt son dependencias previstas, pendientes de instalación.

## Arrancar y probar

```powershell
.\.venv\Scripts\python.exe main.py
.\.venv\Scripts\python.exe -m pytest
```

Si activas el entorno, los comandos de la tarjeta se ejecutan así:

```powershell
.\.venv\Scripts\Activate.ps1
python main.py
pytest
```

La activación es opcional: las rutas completas funcionan sin cambiar la
política de PowerShell. ejecutar.cmd permite comprobar el arranque con doble
clic y deja visible su resultado.

main.py y crear_bd.py crean o abren la misma base: datos/fraseya.db.
Se puede elegir otro archivo mediante `--bd ruta/otra.db`. No es necesario
internet para arrancar o utilizar el repositorio SQLite.

Mientras se habilita la instalación, las pruebas existentes y de arranque se
ejecutan con la biblioteca estándar, sin descargar paquetes:

```powershell
$env:PYTHONPATH = 'src'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Estructura del proyecto

```text
main.py                         Punto de entrada
src/fraseya/
    presentacion/               Interacción con el usuario; consola de arranque
    aplicacion/                 Coordinación de casos de uso; arranque
    dominio/                    Lugar reservado para las entidades de Diego
    infraestructura/            Repositorio SQLite y esquema de seis tablas
tests/                          Pruebas del repositorio y del arranque
docs/                           Guía de base de datos y trabajo en equipo
datos/                          Bases locales, excluidas de Git
requirements.txt                Dependencias previstas del proyecto
pyproject.toml                  Configuración del paquete y de pytest
```

La presentación llama a la aplicación y esta utiliza la infraestructura de
persistencia para el arranque. Las entidades de dominio no deben depender de
la interfaz ni de SQLite. La implementación de dominio sigue siendo una tarea
de Diego. Las importaciones anteriores de RepositorioSQLite se conservan.

## Dependencias previstas

| Dependencia | Uso previsto |
| --- | --- |
| pynput | Captura global de teclado; alternativa elegida frente a keyboard |
| openpyxl | Importación de frases desde Excel |
| pytest y pytest-cov | Ejecución de pruebas y medición de cobertura |
| pyinstaller | Empaquetado futuro para Windows |

El arranque actual no requiere importar estas bibliotecas. SQLite forma parte
de Python. La presencia de estas dependencias no significa que sus módulos
funcionales estén implementados.

## Trabajo en equipo

El repositorio Git local está inicializado en la rama main. No tiene un
repositorio remoto configurado ni se ha publicado en GitHub. El entorno
virtual, las bases de datos, resultados de pruebas y archivos de salida están
excluidos mediante .gitignore.

Consulta docs/TRABAJO_EN_EQUIPO.md para colaborar y docs/BASE_DE_DATOS.md
para entender el módulo implementado por Bayron.
