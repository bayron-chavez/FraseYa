# Instalador de FraseYa para Windows

## Instalar en otro equipo

1. Copiar `FraseYa-Instalador.exe` al otro equipo.
2. Abrirlo, elegir la carpeta y completar el asistente en español.
3. Elegir si se desea crear el acceso directo del escritorio.
4. Abrir FraseYa desde el menú Inicio o el acceso directo.
5. Iniciar sesión con la cuenta de ese usuario. El instalador incluye la URL y
   la clave pública de nuestro proyecto Supabase; no hay que escribirlas.

El instalador contiene el programa y los manuales. No requiere instalar Python
y no incluye cuentas, contraseñas, tokens ni frases personales
del equipo donde se generó. El catálogo compartido se descarga al sincronizar.
Las frases propias se guardan localmente en cada equipo.
La conexión pública incluida no concede permisos de administrador: siguen
aplicándose el inicio de sesión, los roles y las políticas de la base central.

La ubicación predeterminada es `%LOCALAPPDATA%\Programs\FraseYa` y no solicita
permisos de administrador. Es para Windows 10/11 de 64 bits. La comprobación
ejecutada corresponde a Windows 11 x64; la aceptación en Windows 10 sigue pendiente.

## Actualizar y desinstalar

Para actualizar, cerrar FraseYa y ejecutar el instalador nuevo usando la misma
carpeta. La carpeta `datos` se conserva. Desinstalar desde Configuración de
Windows → Aplicaciones → FraseYa retira el programa y los accesos directos,
conservando `datos` para no perder frases propias accidentalmente. Para borrar
también esos datos, hacerlo manualmente después de respaldarlos.
La conexión que ya existe en un equipo tampoco se sobrescribe durante una
actualización, para respetar una configuración anterior.

El instalador generado no tiene certificado de firma de FraseYa. Su compilador
se descargó de la distribución oficial y se verificó su firma digital válida.

## Generar nuevamente

Con Inno Setup 6 y el portable generado:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/crear_instalador.ps1
```

Para regenerar también el portable, agregar `-Reconstruir`. Si el compilador
no está en una ubicación habitual, indicar `-Compilador "ruta\ISCC.exe"`.
El resultado es `dist/FraseYa-Instalador.exe`; `dist` está excluido de Git.
La generación toma `datos/supabase.json`, valida que la clave sea pública y
exporta exclusivamente `url` y `clave_publica` a una carpeta temporal ignorada.
Puede indicarse otra configuración mediante `-Conexion "ruta\supabase.json"`.
Las claves secret/service_role se rechazan y los campos adicionales no se empaquetan.

## Verificación ejecutada

Se instaló en una carpeta aislada, sin iniciar sesión ni realizar consultas al
catálogo. El diagnóstico del programa instalado terminó con salida 0. Se creó
un archivo de datos ficticios y se comprobó que una actualización lo conserva.
Al desinstalar, el programa y su registro de desinstalación se retiraron y los
datos ficticios permanecieron. No se alteró una instalación personal existente.
