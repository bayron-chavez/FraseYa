/* FraseYa · Lector WhatsApp Web (solo lectura de mensajes entrantes en memoria).
 * - Observa únicamente div.message-in dentro del chat activo (#main).
 * - Extrae texto plano con innerText (nunca HTML ni campos de escritura).
 * - Agrupa ráfagas cortas (debounce 800 ms) y evita duplicados.
 * - Envía solo a http://127.0.0.1:47821/mensaje y falla en silencio si FraseYa está cerrado.
 * - Nunca guarda conversaciones ni envía mensajes automáticamente.
 */
(() => {
  'use strict';

  const ENDPOINT = 'http://127.0.0.1:47821/mensaje';
  const DEBOUNCE_MS = 800;
  const MAX_LARGO = 4000;
  const MAX_CLAVES_VISTAS = 300;

  const nodosVistos = new WeakSet();
  const clavesVistas = [];
  const conjuntoClaves = new Set();

  let panelActual = null;
  let observadorPanel = null;
  let temporizador = null;
  let colaMensajes = [];
  let ultimoMeta = { chat: '', remitente: '' };

  function limpiarTexto(valor) {
    if (typeof valor !== 'string') return '';
    return valor
      .split(/\r?\n/)
      .map((linea) => linea.trim())
      .filter(Boolean)
      .join('\n')
      .trim();
  }

  function registrarClave(clave) {
    if (!clave || conjuntoClaves.has(clave)) return false;
    conjuntoClaves.add(clave);
    clavesVistas.push(clave);
    if (clavesVistas.length > MAX_CLAVES_VISTAS) {
      const antigua = clavesVistas.shift();
      conjuntoClaves.delete(antigua);
    }
    return true;
  }

  function obtenerNombreChat() {
    const selectores = [
      '#main header [data-testid="conversation-info-header-chat-title"]',
      '#main header span[dir="auto"][title]',
      '#main header span[title]',
    ];
    for (const sel of selectores) {
      const el = document.querySelector(sel);
      if (el) {
        const txt = limpiarTexto(el.innerText || el.getAttribute('title') || '');
        if (txt) return txt.slice(0, 200);
      }
    }
    return '';
  }

  function extraerRemitente(nodoMensaje, chat) {
    const pre = nodoMensaje.querySelector('[data-pre-plain-text]');
    const attr = pre ? pre.getAttribute('data-pre-plain-text') || '' : '';
    const coincidencia = attr.match(/\]\s*([^:]+):\s*$/);
    if (coincidencia && coincidencia[1]) {
      return limpiarTexto(coincidencia[1]).slice(0, 200);
    }
    const autor = nodoMensaje.querySelector('[data-testid="author"], span[dir="auto"]._ahxt');
    if (autor && autor.innerText) {
      const txt = limpiarTexto(autor.innerText);
      if (txt) return txt.slice(0, 200);
    }
    return chat;
  }

  function extraerTextoPlano(nodoMensaje) {
    // Selectores estables para el cuerpo textual del mensaje entrante.
    const bloques = nodoMensaje.querySelectorAll(
      '[data-testid="msg-container"] span.selectable-text, .copyable-text span.selectable-text, span.selectable-text'
    );
    if (bloques.length > 0) {
      const partes = [];
      for (const bloque of bloques) {
        if (bloque.closest('[data-testid="quoted-message"]')) continue;
        const txt = limpiarTexto(bloque.innerText || '');
        if (txt && !partes.includes(txt)) {
          partes.push(txt);
        }
      }
      const unido = partes.join('\n').trim();
      if (unido) return unido.slice(0, MAX_LARGO);
    }

    const contenedor = nodoMensaje.querySelector('.copyable-text');
    if (contenedor && contenedor.innerText) {
      return limpiarTexto(contenedor.innerText).slice(0, MAX_LARGO);
    }
    return '';
  }

  function claveDeMensaje(nodoMensaje, chat, texto) {
    const contenedorId = nodoMensaje.closest('[data-id]') || nodoMensaje.querySelector('[data-id]');
    const dataId = contenedorId ? contenedorId.getAttribute('data-id') : '';
    if (dataId) return `id:${dataId}`;
    return `txt:${chat.toLowerCase()}::${texto.toLowerCase()}`;
  }

  function esNodoEntrante(el) {
    if (!(el instanceof HTMLElement)) return false;
    if (el.classList.contains('message-out') || el.closest('div.message-out')) return false;
    return el.matches('div.message-in');
  }

  function buscarEntrantesEn(raiz) {
    const encontrados = [];
    if (!(raiz instanceof HTMLElement)) return encontrados;
    if (esNodoEntrante(raiz)) {
      encontrados.push(raiz);
    }
    const hijos = raiz.querySelectorAll('div.message-in');
    for (const hijo of hijos) {
      if (esNodoEntrante(hijo)) {
        encontrados.push(hijo);
      }
    }
    return encontrados;
  }

  function enviarCola() {
    temporizador = null;
    if (colaMensajes.length === 0) return;

    const texto = colaMensajes.join('\n').slice(-MAX_LARGO).trim();
    const { chat, remitente } = ultimoMeta;
    colaMensajes = [];
    if (!texto) return;

    try {
      fetch(ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ texto, chat, remitente }),
      }).catch(() => {
        // Silencio total si FraseYa no está abierto o el puente está pausado.
      });
    } catch (_err) {
      // Sin ruido en consola.
    }
  }

  function encolarMensaje(nodoMensaje) {
    if (nodosVistos.has(nodoMensaje)) return;
    nodosVistos.add(nodoMensaje);

    const texto = extraerTextoPlano(nodoMensaje);
    if (!texto) return;

    const chat = obtenerNombreChat();
    const clave = claveDeMensaje(nodoMensaje, chat, texto);
    if (!registrarClave(clave)) return;

    const remitente = extraerRemitente(nodoMensaje, chat);
    if (!colaMensajes.includes(texto)) {
      colaMensajes.push(texto);
    }
    ultimoMeta = { chat, remitente };

    if (temporizador !== null) {
      clearTimeout(temporizador);
    }
    temporizador = setTimeout(enviarCola, DEBOUNCE_MS);
  }

  function marcarHistorialExistente(panel) {
    const burbujas = panel.querySelectorAll('div.message-in, div.message-out');
    if (burbujas.length === 0) return;

    const ultima = burbujas[burbujas.length - 1];
    const chat = obtenerNombreChat();

    for (let i = 0; i < burbujas.length; i += 1) {
      const burbuja = burbujas[i];
      if (!esNodoEntrante(burbuja)) continue;
      if (burbuja === ultima) {
        // Si al abrir el chat el último mensaje es del cliente, lo sugerimos una sola vez.
        encolarMensaje(burbuja);
      } else {
        nodosVistos.add(burbuja);
        const txt = extraerTextoPlano(burbuja);
        if (txt) {
          registrarClave(claveDeMensaje(burbuja, chat, txt));
        }
      }
    }
  }

  function esRecienteAlFinal(panel, nodoMensaje) {
    // Evita disparar sugerencias al hacer scroll hacia arriba cargando historial antiguo.
    const burbujas = panel.querySelectorAll('div.message-in, div.message-out');
    if (burbujas.length === 0) return true;
    const ventanaReciente = Math.max(0, burbujas.length - 5);
    for (let i = ventanaReciente; i < burbujas.length; i += 1) {
      if (burbujas[i] === nodoMensaje) return true;
    }
    return false;
  }

  function conectarPanel(panel) {
    if (panel === panelActual) return;
    if (observadorPanel) {
      observadorPanel.disconnect();
      observadorPanel = null;
    }
    panelActual = panel;
    if (!panel) return;

    marcarHistorialExistente(panel);

    observadorPanel = new MutationObserver((mutaciones) => {
      for (const mutacion of mutaciones) {
        for (const nodo of mutacion.addedNodes) {
          const entrantes = buscarEntrantesEn(nodo);
          for (const mensaje of entrantes) {
            if (esRecienteAlFinal(panel, mensaje)) {
              encolarMensaje(mensaje);
            } else {
              nodosVistos.add(mensaje);
            }
          }
        }
      }
    });

    observadorPanel.observe(panel, { childList: true, subtree: true });
  }

  function localizarPanelMensajes() {
    const main = document.querySelector('#main');
    if (!main) return null;
    return main.querySelector('[role="application"]') || main;
  }

  function iniciar() {
    const actualizarPanel = () => {
      const panel = localizarPanelMensajes();
      if (panel !== panelActual) {
        conectarPanel(panel);
      }
    };

    actualizarPanel();

    const raiz = document.body || document.documentElement;
    if (!raiz) return;
    const observadorNavegacion = new MutationObserver(actualizarPanel);
    observadorNavegacion.observe(raiz, { childList: true, subtree: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', iniciar, { once: true });
  } else {
    iniciar();
  }
})();
