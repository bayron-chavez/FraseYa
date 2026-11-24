import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import vm from 'node:vm';

const RUTA_SCRIPT = new URL('../../extension_wsp/content.js', import.meta.url);

class FakeElement {
  constructor(tag, { classes = [], attrs = {}, innerText = '', parent = null } = {}) {
    this.tagName = tag.toUpperCase();
    this.classes = new Set(classes);
    this.attrs = { ...attrs };
    this.innerText = innerText;
    this.parent = parent;
    this.children = [];
    if (parent) parent.children.push(this);
  }

  getAttribute(nombre) {
    return Object.prototype.hasOwnProperty.call(this.attrs, nombre) ? this.attrs[nombre] : null;
  }

  matches(selector) {
    return selector.split(',').some((parte) => {
      const s = parte.trim();
      if (s === '#main') return this.attrs.id === 'main';
      if (s === '[role="application"]') return this.attrs.role === 'application';
      if (s === '[data-id]') return Object.prototype.hasOwnProperty.call(this.attrs, 'data-id');
      if (s === '[data-pre-plain-text]') return Object.prototype.hasOwnProperty.call(this.attrs, 'data-pre-plain-text');
      if (s === '[data-testid="quoted-message"]') return this.attrs['data-testid'] === 'quoted-message';
      if (s === '[data-testid="msg-container"] span.selectable-text') {
        return this.tagName === 'SPAN' && this.classes.has('selectable-text') && Boolean(this.closest('[data-testid="msg-container"]'));
      }
      if (s === '.copyable-text span.selectable-text') {
        return this.tagName === 'SPAN' && this.classes.has('selectable-text') && Boolean(this.closest('.copyable-text'));
      }
      if (s === 'span.selectable-text') return this.tagName === 'SPAN' && this.classes.has('selectable-text');
      if (s === '.copyable-text') return this.classes.has('copyable-text');
      if (s === '[data-testid="msg-container"]') return this.attrs['data-testid'] === 'msg-container';
      if (s === 'div.message-in') return this.tagName === 'DIV' && this.classes.has('message-in');
      if (s === 'div.message-out') return this.tagName === 'DIV' && this.classes.has('message-out');
      if (s === '[data-testid="author"]') return this.attrs['data-testid'] === 'author';
      if (s === 'span[dir="auto"]._ahxt') return this.tagName === 'SPAN' && this.attrs.dir === 'auto' && this.classes.has('_ahxt');
      if (s === '[data-testid="conversation-info-header-chat-title"]') return this.attrs['data-testid'] === 'conversation-info-header-chat-title';
      return false;
    });
  }

  closest(selector) {
    let cur = this;
    while (cur) {
      if (cur.matches(selector)) return cur;
      cur = cur.parent;
    }
    return null;
  }

  querySelectorAll(selector) {
    const out = [];
    const visitar = (nodo) => {
      for (const hijo of nodo.children) {
        if (hijo.matches(selector)) out.push(hijo);
        visitar(hijo);
      }
    };
    visitar(this);
    return out;
  }

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
  }
}

function crearBurbuja(panel, { tipo = 'in', dataId, texto, citado = null, remitente = 'Camila' }) {
  const b = new FakeElement('div', {
    classes: [tipo === 'out' ? 'message-out' : 'message-in'],
    attrs: dataId ? { 'data-id': dataId } : {},
    parent: panel,
  });
  const cont = new FakeElement('div', {
    classes: ['copyable-text'],
    attrs: {
      'data-testid': 'msg-container',
      'data-pre-plain-text': `[12:10, 24/11/2026] ${remitente}: `,
    },
    parent: b,
  });
  if (citado) {
    const q = new FakeElement('div', { attrs: { 'data-testid': 'quoted-message' }, parent: cont });
    new FakeElement('span', { classes: ['selectable-text'], innerText: citado, parent: q });
  }
  new FakeElement('span', { classes: ['selectable-text'], innerText: texto, parent: cont });
  return b;
}

test('extension_wsp/content.js ignora citas, respeta ventana reciente y agrupa ráfagas con debounce', async () => {
  const codigo = await readFile(RUTA_SCRIPT, 'utf8');
  const root = new FakeElement('body');
  const main = new FakeElement('div', { attrs: { id: 'main' }, parent: root });
  const header = new FakeElement('header', { parent: main });
  new FakeElement('span', {
    attrs: { 'data-testid': 'conversation-info-header-chat-title' },
    innerText: 'Camila Cliente',
    parent: header,
  });
  const panel = new FakeElement('div', { attrs: { role: 'application' }, parent: main });

  // Historial previo al conectar el panel
  crearBurbuja(panel, { tipo: 'in', dataId: 'm1', texto: 'Hola, buen día', citado: 'Mensaje citado viejo' });
  crearBurbuja(panel, { tipo: 'out', dataId: 'm2', texto: 'Hola Camila, ¿en qué te ayudamos?' });

  const envios = [];
  const timers = [];
  const observers = [];

  class FakeMutationObserver {
    constructor(cb) {
      this.cb = cb;
      observers.push(this);
    }
    observe() {}
    disconnect() {}
  }

  const sandbox = {
    HTMLElement: FakeElement,
    MutationObserver: FakeMutationObserver,
    WeakSet,
    Set,
    document: {
      readyState: 'complete',
      body: root,
      documentElement: root,
      querySelector: (sel) => {
        if (sel === '#main header [data-testid="conversation-info-header-chat-title"]') {
          return header.querySelector('[data-testid="conversation-info-header-chat-title"]');
        }
        return root.querySelector(sel);
      },
      addEventListener: () => {},
    },
    fetch: (url, init) => {
      envios.push({ url, body: JSON.parse(init.body) });
      return Promise.resolve({ ok: true });
    },
    setTimeout: (fn, ms) => {
      const id = timers.length + 1;
      timers.push({ id, fn, ms, cleared: false });
      return id;
    },
    clearTimeout: (id) => {
      const t = timers.find((x) => x.id === id);
      if (t) t.cleared = true;
    },
  };

  vm.runInNewContext(codigo, sandbox);

  // 1. Al iniciar envía historial inicial omitiendo el texto dentro de quoted-message
  assert.equal(envios.length, 1);
  assert.equal(envios[0].url, 'http://127.0.0.1:47821/mensaje');
  assert.deepEqual(envios[0].body.turnos, [
    { rol: 'cliente', texto: 'Hola, buen día' },
    { rol: 'agente', texto: 'Hola Camila, ¿en qué te ayudamos?' },
  ]);
  assert.ok(!JSON.stringify(envios[0].body).includes('Mensaje citado viejo'));

  // 2. Inserta burbuja antigua al inicio de 10 mensajes -> fuera de los últimos 5 (scroll arriba), se ignora
  const observadorPanel = observers[0];
  const vieja = crearBurbuja(panel, { tipo: 'in', dataId: 'm0', texto: 'Mensaje histórico antiguo' });
  panel.children.pop();
  panel.children.unshift(vieja);
  for (let i = 3; i <= 8; i += 1) {
    crearBurbuja(panel, { tipo: 'in', dataId: `extra-${i}`, texto: `Relleno ${i}` });
  }
  observadorPanel.cb([{ addedNodes: [vieja] }]);
  assert.equal(timers.filter((t) => !t.cleared).length, 0);

  // 3. Ráfaga de mensajes recientes del cliente -> agrupa con debounce de 800 ms en un solo POST
  const nueva1 = crearBurbuja(panel, { tipo: 'in', dataId: 'm9', texto: '¿Tienen envío hoy?' });
  const nueva2 = crearBurbuja(panel, { tipo: 'in', dataId: 'm10', texto: 'Es para Santiago centro' });
  observadorPanel.cb([{ addedNodes: [nueva1] }]);
  observadorPanel.cb([{ addedNodes: [nueva2] }]);

  const activos = timers.filter((t) => !t.cleared);
  assert.equal(activos.length, 1);
  assert.equal(activos[0].ms, 800);
  activos[0].fn();

  assert.equal(envios.length, 2);
  assert.equal(envios[1].body.rol, 'cliente');
  assert.equal(envios[1].body.texto, '¿Tienen envío hoy?\nEs para Santiago centro');
});
