# Historial de Commits — FraseYa

Registro cronológico de los cambios realizados en cada commit de la rama base (`main`) al momento de crear la rama `desarrollo-bayron`.

---

## Resumen de commits

1. **`7b62030`** *(2026-10-01 — Bayron)* — **`primer commit`**
   - Estructura inicial del proyecto (`main.py`, `pyproject.toml`, `requirements.txt`, `crear_bd.py`, `ejecutar.cmd`, `preparar_entorno.ps1`).
   - Base de datos SQLite (`src/fraseya/infraestructura/schema.sql`, `repositorio_sqlite.py`), capa de aplicación (`arranque.py`) y presentación por consola (`consola.py`).
   - Documentación inicial (`docs/BASE_DE_DATOS.md`, `docs/TRABAJO_EN_EQUIPO.md`) y pruebas (`tests/test_arranque.py`, `tests/test_repositorio.py`).

2. **`3867bf7`** *(2026-10-01 — Diego Ulloa)* — **`Agrega entidades de dominio`**
   - Define las entidades de dominio en `src/fraseya/dominio/entidades.py` y sus pruebas en `tests/test_dominio.py`.

3. **`496309f`** *(2026-10-01 — Diego Ignacio Ulloa Perez)* — **`Merge pull request #1 from bayron-chavez/dominio`**
   - Integra la rama `dominio` en `main`.

4. **`5901e1b`** *(2026-10-02 — Claude)* — **`Add prueba.txt`**
   - Agrega el archivo temporal `prueba.txt`.

5. **`dd90675`** *(2026-10-01 — Diego Ulloa)* — **`Agrega EscritorTexto y la ventana principal de gestión de frases`**
   - Implementa la escritura automática de texto (`src/fraseya/infraestructura/escritor_texto.py`), gestión de frases (`src/fraseya/aplicacion/gestion_frases.py`) y ventana principal (`src/fraseya/presentacion/ventana_principal.py`).
   - Agrega scripts de prueba (`scripts/prueba_carga.py`, `scripts/prueba_escritor.py`) y pruebas unitarias.

6. **`d06b130`** *(2026-10-01 — Diego Ulloa)* — **`Agrega RF-03: campos variables y formulario de relleno`**
   - Implementa la resolución de campos variables (`src/fraseya/aplicacion/resolver_variables.py`), el formulario de relleno (`src/fraseya/presentacion/formulario_variables.py`), `scripts/prueba_formulario.py` y sus pruebas.

7. **`d6771a0`** *(2026-10-01 — Diego Ulloa)* — **`Agrega RF-01: expansión de texto por abreviatura`**
   - Implementa el motor de expansión (`src/fraseya/aplicacion/motor_expansion.py`), captura de teclado global (`src/fraseya/infraestructura/teclado_global.py`), flujo de expansión en UI (`src/fraseya/presentacion/expansion.py`) y sus pruebas.

8. **`6c6b0a1`** *(2026-10-01 — Diego Ulloa)* — **`Agrega RF-02 (buscador rápido) y RF-11 (pantalla de configuración)`**
   - Añade el buscador rápido (`src/fraseya/aplicacion/buscador.py`, `src/fraseya/presentacion/buscador_rapido.py`), la configuración y su ventana (`src/fraseya/aplicacion/configuracion.py`, `src/fraseya/presentacion/ventana_configuracion.py`) y sus pruebas.

9. **`cb56375`** *(2026-10-05 — Bayron)* — **`Actualiza sincronización, publicación y gestión de usuarios`**
   - Incorpora autenticación (`autenticacion.py`, `acceso.py`), formato de catálogo (`formato_catalogo.py`), publicación y sincronización en repositorio compartido (`publicacion.py`, `servicio_sincronizacion.py`, `repositorio_compartido.py`).
   - Agrega documentación (`FORMATO_CATALOGO.md`, `PUBLICACION.md`, `REPOSITORIO_COMPARTIDO.md`, `SINCRONIZACION.md`), ejemplos y pruebas; elimina `prueba.txt` y `Resumen_Avance.txt`.

10. **`6906989`** *(2026-10-05 — Bayron)* — **`Migra a Supabase, refuerza seguridad y agrega categorias de administrador`**
    - Migra del repositorio compartido a Supabase (`src/fraseya/infraestructura/supabase.py`, `publicacion_supabase.py`, `sesion.py`).
    - Agrega migraciones SQL y auditoría de permisos (`supabase/migrations/`, `supabase/auditoria_permisos.sql`), categorías de administrador y pruebas en Python y Node (`supabase/tests/auditoria.mjs`).

11. **`421b9c3`** *(2026-10-08 — Bayron)* — **`Completa funciones de FraseYa, refuerza acceso y agrega favoritos y recuperacion`**
    - Agrega importación desde Excel (`importacion_excel.py`), límite de intentos de acceso (`limite_acceso.py`), estado de sincronización (`estado_sincronizacion.py`), bandeja del sistema (`bandeja.py`), favoritos, deshacer y recuperación.
    - Añade configuración de empaquetado (`FraseYa.spec`, `scripts/empaquetar.ps1`) y documentación (`MANUAL_USUARIO.md`, `GUIA_ADMINISTRADOR.md`, `VALIDACION.md`, `ACEPTACION_EQUIPOS.md`).

12. **`bccda4b`** *(2026-10-08 — Bayron)* — **`Agrega logo e instalador Windows con conexion publica validada`**
    - Incorpora `assets/logo.png` y `assets/fraseya.ico`, el instalador Windows con Inno Setup (`instalador/FraseYa.iss`), scripts de instalación y validación de conexión pública (`crear_instalador.ps1`, `preparar_conexion_instalador.py`), identidad en UI (`identidad.py`) y `docs/INSTALACION.md`.

13. **`e43cf92`** *(2026-10-25 — Bayron)* — **`Actualiza interfaz Qt y mejoras de seguridad de FraseYa`**
    - Incorpora la interfaz Qt (`qt_aplicacion.py`, `qt_vista.py`, `qt_dialogos.py`, `qt_expansion.py`), recomendaciones e integración con IA (`recomendaciones_ia.py`, `empresa_ia.py`, Edge Function `supabase/functions/fraseya-ia/`, migraciones `202610100003_ia.sql` y `202610100004_empresa_ia.sql`).
    - Agrega licencias (`licenses/GPL-3.0.txt`, `licenses/LGPL-3.0.txt`), maquetas visuales (`docs/maqueta/`), documentación (`docs/IA.md`, `docs/INTERFAZ_QT.md`, `docs/LICENCIAS_QT.md`, `docs/AUDITORIA_QT_2026-10-10.md`) y sus pruebas.
