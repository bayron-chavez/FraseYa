# FraseYa

Aplicación de escritorio Windows para expandir frases por abreviatura, buscar
textos y rellenar variables. Supabase proporciona las cuentas y el catálogo
central. SQLite guarda frases propias y la última copia del catálogo.

## Preparación

Requiere Python 3.10 o posterior:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/configurar_supabase.py
.\.venv\Scripts\python.exe main.py
```

Configura primero el proyecto siguiendo [SUPABASE.md](docs/SUPABASE.md).
Los proyectos existentes deben aplicar la migración de seguridad 002; no deben
volver a ejecutar la migración inicial 001.

La configuración pública está en datos/supabase.json. No se guardan contraseñas
ni tokens de Supabase en disco. Sin configuración válida la aplicación informa
el problema y no crea cuentas locales como alternativa.

El botón Trabajar sin conexión abre los datos de este equipo; no permite leer
el servidor ni publicar. Protege el equipo mediante su cuenta de Windows.
La aplicación no aísla las frases propias por correo cuando varias personas
comparten el mismo perfil de Windows.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pytest
```

También puedes usar el portable de `dist/FraseYa-portable.zip`, que incluye un
asistente de configuración inicial y no necesita Python. Consulta
[MANUAL_USUARIO.md](docs/MANUAL_USUARIO.md),
[GUIA_ADMINISTRADOR.md](docs/GUIA_ADMINISTRADOR.md) y
[VALIDACION.md](docs/VALIDACION.md). Para regenerarlo: `scripts/empaquetar.ps1`.

La interfaz permite crear/renombrar/eliminar categorías vacías y asignarles
color (solo administradores), importar Excel e identificar el estado de
sincronización en la ventana y en la bandeja. El login limita peticiones locales
y respeta las respuestas HTTP 429 del servidor.

Las pruebas gráficas requieren un escritorio Windows. La auditoría PostgreSQL
se ejecuta en una base aislada con PGlite:

```powershell
cd supabase/tests
npm install --ignore-scripts
npm test
```

Consulta [SEGURIDAD.md](docs/SEGURIDAD.md) para los resultados y límites de la
revisión. Las pruebas de PGlite no sustituyen comprobar los permisos reales
mediante supabase/auditoria_permisos.sql en SQL Editor.

## Archivos

- src/fraseya: dominio, aplicación, presentación e infraestructura.
- tests: pruebas de funcionamiento y seguridad.
- supabase/migrations: creación del esquema y refuerzo de permisos.
- datos: bases y configuración privadas del equipo, excluidas de Git.
- docs: contrato del catálogo, sincronización, publicación y auditoría.

El repositorio compartido es https://github.com/bayron-chavez/FraseYa.
No incluyas datos, entornos virtuales, capturas ni credenciales en los commits.
