# Resumen del proyecto FraseYa

Actualizado el 1 de octubre de 2026.

FraseYa será una aplicación de escritorio en Python para guardar y utilizar
frases predefinidas. Hasta ahora se prepararon la base de datos local y la
estructura del proyecto. La interfaz completa se integrará después y Supabase
queda para una segunda etapa.

## Lo realizado

**Base de datos:** SQLite guarda la información en `datos/fraseya.db`. Es la
única base del proyecto; se eliminó `catalogo-v1.db`. Sus seis tablas son:

| Tabla | Qué guarda |
| --- | --- |
| CATALOGO | Colecciones de frases, versión, autor y origen |
| CATEGORIA | Grupos de frases y su color |
| FRASE | Título, abreviatura y contenido |
| VARIABLE | Campos por completar, como `{nombre}` |
| SINCRONIZACION | Historial de actualizaciones del catálogo |
| CONFIGURACION | Preferencias mediante clave y valor |

**RepositorioSQLite:** código que permite guardar, consultar, modificar y
eliminar datos. También reemplaza las frases compartidas sin modificar las
personales. Si la actualización falla, revierte todos sus cambios.

**Organización del proyecto:**

| Carpeta | Función |
| --- | --- |
| src/fraseya/presentacion | Interacción con el usuario; actualmente una consola |
| src/fraseya/aplicacion | Coordinar operaciones; actualmente el arranque |
| src/fraseya/dominio | Espacio para integrar las entidades de Diego |
| src/fraseya/infraestructura | Acceso a SQLite y esquema de tablas |
| tests | Pruebas automáticas |
| docs | Guías de base de datos y trabajo en equipo |
| datos | Archivo local fraseya.db |

**Archivos principales:**

- `main.py`: inicia el proyecto, prepara la base y muestra su estado en consola.
- `crear_bd.py`: prepara la misma base de datos sin abrir una interfaz.
- `schema.sql`: define las seis tablas y sus reglas; está en infraestructura.
- `requirements.txt`: lista las bibliotecas previstas del proyecto.
- `pyproject.toml`: configura el paquete Python y las herramientas de pruebas.
- `README.md`: explica la preparación y ejecución del proyecto.
- `preparar_entorno.ps1`: crea el entorno si falta, instala bibliotecas y ejecuta pytest.
- `ejecutar.cmd`: permite comprobar el arranque con doble clic.
- `.gitignore`: excluye bases locales, entorno virtual y archivos temporales de Git.

**Git:** se inicializó un repositorio local en la rama main. Todavía no está
conectado a GitHub ni a un repositorio remoto compartido con Diego.

**Entorno virtual:** se creó `.venv` para separar las dependencias de FraseYa.
No hay que entrar a esa carpeta para ejecutar el programa.

## Cómo ejecutarlo

Abrir PowerShell en la carpeta `Bayron-BD` y ejecutar:

```powershell
.\.venv\Scripts\python.exe main.py
```

Esto usa el Python del entorno virtual sin activarlo. Actualmente muestra el
resultado del arranque en consola; todavía no abre ventanas del software.

Para instalar las dependencias previstas y comprobar pytest:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest
```

## Pruebas y estado en Trello

Pasaron 19 pruebas con la herramienta estándar de Python: 16 del repositorio
y tres del arranque. Se comprobaron persistencia, operaciones de datos,
restricciones y reversión de actualizaciones fallidas.

Las dos tarjetas de Bayron sobre esquema y repositorio se movieron a
«En revisión / Pruebas». La tarjeta compartida «Setup: repositorio y estructura
del proyecto Python» se dejó «En progreso» porque falta verificar pytest.

## Pendiente

La descarga de bibliotecas fue bloqueada por la red de la sesión de trabajo;
no se confirmó su instalación ni la ejecución de pytest. Las bibliotecas
previstas son pynput, openpyxl, pytest, pytest-cov y pyinstaller.

Falta integrar la interfaz, las entidades de Diego, la expansión de texto,
el buscador global y la sincronización automática. También faltan el
repositorio remoto compartido y la comprobación del software integrado.
Las pruebas actuales no acreditan el producto completo ni su cobertura total.
