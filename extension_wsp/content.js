/* FraseYa · Lector WhatsApp Web (solo lectura de contexto en memoria).
 * - Observa burbujas div.message-in (cliente) y div.message-out (agente) dentro de #main.
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
  const MAX_TURNOS_HISTORIAL = 6;
  const MAX_LARGO_TURNO_HISTORIAL = 800;
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

  function extraerCita(nodoMensaje) {
    const citado = nodoMensaje.querySelector('[data-testid="quoted-message"]');
    if (!citado) return '';
    const spans = citado.querySelectorAll('span.selectable-text');
    const textos = [];
    for (const sp of spans) {
      const t = limpiarTexto(sp.innerText || '');
      if (t && !textos.includes(t)) textos.push(t);
    }
    const txt = textos.join(' ') || limpiarTexto(citado.innerText || '');
    if (!txt) return '';
    return txt.replace(/\s+/g, ' ').slice(0, 140).trim();
  }

  function extraerTextoPlano(nodoMensaje) {
    const cita = extraerCita(nodoMensaje);
    const prefijoCita = cita ? `[Respondiendo a: "${cita}"]\n` : '';
    // Selectores estables para el cuerpo textual de la burbuja.
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
      if (unido) return `${prefijoCita}${unido}`.slice(0, MAX_LARGO);
    }

    const contenedor = nodoMensaje.querySelector('.copyable-text');
    if (contenedor && contenedor.innerText) {
      return `${prefijoCita}${limpiarTexto(contenedor.innerText)}`.slice(0, MAX_LARGO);
    }
    return '';
  }

  function rolDeNodo(el) {
    if (!(el instanceof HTMLElement)) return null;
    if (el.matches('div.message-out')) return 'agente';
    if (el.matches('div.message-in') && !el.closest('div.message-out')) return 'cliente';
    return null;
  }

  function claveDeMensaje(nodoMensaje, chat, texto, rol) {
    const contenedorId = nodoMensaje.closest('[data-id]') || nodoMensaje.querySelector('[data-id]');
    const dataId = contenedorId ? contenedorId.getAttribute('data-id') : '';
    if (dataId) return `id:${dataId}`;
    return `txt:${rol}:${chat.toLowerCase()}::${texto.toLowerCase()}`;
  }

  function buscarMensajesEn(raiz) {
    const encontrados = [];
    if (!(raiz instanceof HTMLElement)) return encontrados;
    const rolRaiz = rolDeNodo(raiz);
    if (rolRaiz) {
      encontrados.push({ nodo: raiz, rol: rolRaiz });
      return encontrados;
    }
    const hijos = raiz.querySelectorAll('div.message-in, div.message-out');
    for (const hijo of hijos) {
      const rol = rolDeNodo(hijo);
      if (rol) {
        encontrados.push({ nodo: hijo, rol });
      }
    }
    return encontrados;
  }

  function enviarPayload(payload) {
    try {
      fetch(ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }).catch(() => {
        // Silencio total si FraseYa no está abierto o el puente está pausado.
      });
    } catch (_err) {
      // Sin ruido en consola.
    }
  }

  function compactarTurnos(lista) {
    const turnos = [];
    for (const item of lista) {
      if (!item || !item.texto) continue;
      const rol = item.rol === 'agente' ? 'agente' : 'cliente';
      const txt = item.texto.slice(0, MAX_LARGO_TURNO_HISTORIAL).trim();
      if (!txt) continue;
      const ultimo = turnos[turnos.length - 1];
      if (ultimo && ultimo.rol === rol) {
        if (!ultimo.texto.includes(txt)) {
          ultimo.texto = `${ultimo.texto}\n${txt}`.slice(-MAX_LARGO_TURNO_HISTORIAL).trim();
        }
      } else {
        turnos.push({ rol, texto: txt });
      }
    }
    return turnos.slice(-MAX_TURNOS_HISTORIAL);
  }

  function enviarCola() {
    temporizador = null;
    if (colaMensajes.length === 0) return;

    const turnos = compactarTurnos(colaMensajes);
    const { chat, remitente } = ultimoMeta;
    colaMensajes = [];
    if (turnos.length === 0) return;

    const ultimo = turnos[turnos.length - 1];
    const texto = ultimo.texto.slice(-MAX_LARGO).trim();
    if (!texto) return;

    const payload = { texto, chat, remitente, rol: ultimo.rol };
    if (turnos.length > 1) {
      payload.turnos = turnos;
    }
    enviarPayload(payload);
  }

  function encolarMensaje(nodoMensaje, rol) {
    if (nodosVistos.has(nodoMensaje)) return;
    nodosVistos.add(nodoMensaje);

    const texto = extraerTextoPlano(nodoMensaje);
    if (!texto) return;

    const chat = obtenerNombreChat();
    const clave = claveDeMensaje(nodoMensaje, chat, texto, rol);
    if (!registrarClave(clave)) return;

    const remitente = rol === 'cliente' ? extraerRemitente(nodoMensaje, chat) : chat;
    const ultimo = colaMensajes[colaMensajes.length - 1];
    if (!ultimo || ultimo.rol !== rol || ultimo.texto !== texto) {
      colaMensajes.push({ rol, texto });
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

    const chat = obtenerNombreChat();
    const historialValido = [];
    let ultimoRemitenteCliente = chat;

    for (let i = 0; i < burbujas.length; i += 1) {
      const burbuja = burbujas[i];
      const rol = rolDeNodo(burbuja);
      if (!rol) continue;
      nodosVistos.add(burbuja);
      const txt = extraerTextoPlano(burbuja);
      if (!txt) continue;
      registrarClave(claveDeMensaje(burbuja, chat, txt, rol));
      historialValido.push({ rol, texto: txt });
      if (rol === 'cliente') {
        ultimoRemitenteCliente = extraerRemitente(burbuja, chat);
      }
    }

    const recientes = compactarTurnos(historialValido.slice(-MAX_TURNOS_HISTORIAL));
    if (recientes.length === 0) return;
    const tieneCliente = recientes.some((t) => t.rol === 'cliente');
    if (!tieneCliente) return;

    const ultimo = recientes[recientes.length - 1];
    enviarPayload({
      texto: ultimo.texto.slice(-MAX_LARGO),
      chat,
      remitente: ultimoRemitenteCliente,
      rol: ultimo.rol,
      turnos: recientes,
    });
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
    if (temporizador !== null) {
      clearTimeout(temporizador);
      temporizador = null;
    }
    colaMensajes = [];
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
          const mensajes = buscarMensajesEn(nodo);
          for (const { nodo: mensaje, rol } of mensajes) {
            if (esRecienteAlFinal(panel, mensaje)) {
              encolarMensaje(mensaje, rol);
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
