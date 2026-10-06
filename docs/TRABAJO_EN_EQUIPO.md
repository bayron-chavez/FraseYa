# Trabajo en equipo

Repositorio compartido: https://github.com/bayron-chavez/FraseYa.
Mantener los cambios dentro de las capas dominio, aplicación, presentación e
infraestructura. Ejecutar las pruebas antes de integrar o subir a main.

Las claves públicas de Supabase no conceden permisos administrativos. Cada
cuenta usa su sesión y las reglas del servidor. No compartir cuentas, claves
secret, contraseñas ni bases personales por GitHub.

Las migraciones SQL se aplican en orden. Una migración nueva es necesaria para
actualizar proyectos existentes; modificar un archivo ya aplicado no cambia
la base remota. Registrar su aplicación y comprobar auditoria_permisos.sql.
