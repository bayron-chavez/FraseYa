# FraseYa · Lector WhatsApp Web

Extensión ligera (Manifest V3) para enviar el último mensaje entrante de **WhatsApp Web** a tu aplicación local **FraseYa** (`http://127.0.0.1:47821`) y mostrar sugerencias de respuestas aprobadas del catálogo.

## Privacidad y seguridad

- Solo se ejecuta en `https://web.whatsapp.com/*`.
- Solo se comunica con tu propio equipo en `http://127.0.0.1:47821/*`.
- Lee únicamente mensajes **entrantes** en texto plano y nunca guarda conversaciones en disco.
- **Nunca envía mensajes automáticamente**: siempre decides qué opción insertar o editar.

## Cómo instalarla en Chrome o Edge (4 pasos)

1. Abre la página de extensiones de tu navegador:
   - En **Google Chrome**: escribe `chrome://extensions` en la barra de direcciones y presiona **Enter**.
   - En **Microsoft Edge**: escribe `edge://extensions` en la barra de direcciones y presiona **Enter**.
2. Activa el interruptor **Modo de desarrollador** (esquina superior derecha en Chrome o panel izquierdo en Edge).
3. Haz clic en **Cargar descomprimida** (Chrome) o **Cargar desempaquetada** (Edge) y selecciona la carpeta `extension_wsp` dentro del directorio de FraseYa.
4. Abre o recarga [WhatsApp Web](https://web.whatsapp.com), abre FraseYa y activa el asistente en vivo cuando quieras recibir sugerencias automáticas.
