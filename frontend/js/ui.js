// Small DOM and formatting helpers, plus the Plotly defaults.

export const $  = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

export function el(tag, attrs = {}, ...kids) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') node.className = v;
    else if (k === 'text') node.textContent = v;
    else if (k === 'html') node.innerHTML = v;
    else if (k.startsWith('on')) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v === true ? '' : v);
  }
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    node.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return node;
}

export function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }

// ---------------------------------------------------------------- formatting

export function fmt(v, digits = 2) {
  if (v === null || v === undefined || Number.isNaN(v)) return '-';
  if (typeof v === 'boolean') return v ? 'yes' : 'no';
  if (typeof v !== 'number') return String(v);
  if (v !== 0 && (Math.abs(v) >= 1e5 || Math.abs(v) < 1e-3)) {
    return v.toExponential(2).replace('e+', '\u00d710^').replace('e-', '\u00d710^-');
  }
  return v.toFixed(digits).replace(/\.?0+$/, '') || '0';
}

export function bytes(n) {
  if (!n && n !== 0) return '-';
  const u = ['B', 'kB', 'MB', 'GB', 'TB'];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n < 10 && i > 0 ? n.toFixed(1) : Math.round(n)} ${u[i]}`;
}

export function clock(seconds) {
  if (!seconds || seconds < 0) return '-';
  if (seconds < 60) return `${Math.round(seconds)} s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ${Math.round(seconds % 60)} s`;
  return `${(seconds / 3600).toFixed(1)} h`;
}

export function isoDay(d) { return d.toISOString().slice(0, 10); }

export function timeOf(iso) { return iso ? iso.slice(11, 19) : '-'; }
export function dayOf(iso)  { return iso ? iso.slice(0, 10) : '-'; }

/** Signed degrees to a hemisphere-tagged string. */
export function latlon(v, kind) {
  if (v === null || v === undefined) return '-';
  const h = kind === 'lat' ? (v >= 0 ? 'N' : 'S') : (v >= 0 ? 'E' : 'W');
  return `${Math.abs(v).toFixed(2)}\u00b0${h}`;
}

// ---------------------------------------------------------------- feedback

export function toast(message, kind = '') {
  const node = el('div', {class: `toast ${kind}`, text: message});
  $('#toasts').append(node);
  setTimeout(() => {
    node.style.transition = 'opacity .4s';
    node.style.opacity = '0';
    setTimeout(() => node.remove(), 400);
  }, kind === 'bad' ? 9000 : 4200);
}

export function banner(message, kind = '') {
  const b = $('#banner');
  if (!message) { b.classList.add('hidden'); return; }
  b.className = `banner ${kind}`;
  b.textContent = message;
}

/** Run an async action with a busy button and uniform error reporting. */
export async function withBusy(button, label, fn) {
  const old = button.textContent;
  button.disabled = true;
  button.textContent = label;
  try {
    return await fn();
  } catch (err) {
    toast(err.message || String(err), 'bad');
    return null;
  } finally {
    button.disabled = false;
    button.textContent = old;
  }
}

export function drawer(title, bodyNode) {
  const t = $('#drawer-title');
  if (t) t.textContent = title;
  const body = $('#drawer-body') || $('#drawer-content') || $('.drawer-body');
  if (body) {
    clear(body);
    body.append(bodyNode);
    if (typeof window.renderMathInElement === 'function') {
      try {
        window.renderMathInElement(body, {
          delimiters: [
            {left: '$$', right: '$$', display: true},
            {left: '$', right: '$', display: false},
            {left: '\\(', right: '\\)', display: false},
            {left: '\\[', right: '\\]', display: true}
          ],
          throwOnError: false
        });
      } catch (err) {
        console.warn('LaTeX compilation warning:', err);
      }
    }
  }
  const d = $('#drawer');
  if (d) {
    d.classList.remove('hidden');
    d.setAttribute('aria-hidden', 'false');
  }
  const b = $('#drawer-backdrop');
  if (b) {
    b.classList.remove('hidden');
  }
}

export function closeDrawer() {
  const d = $('#drawer');
  if (d) {
    d.classList.add('hidden');
    d.setAttribute('aria-hidden', 'true');
  }
  const b = $('#drawer-backdrop');
  if (b) {
    b.classList.add('hidden');
  }
}

export function fillSelect(select, options, value) {
  clear(select);
  for (const o of options) {
    const opt = typeof o === 'string' ? {value: o, label: o} : o;
    select.append(el('option', {value: opt.value, title: opt.title || null},
                     opt.label));
  }
  if (value !== undefined && value !== null) select.value = value;
}

// ---------------------------------------------------------------- plotly

export const PALETTE = ['#1f4e79', '#c1440e', '#2b7a4b', '#7b5aa6',
                        '#b08900', '#0f7d8c', '#8c4a6b', '#4a6b8c'];

export const PLOT_CONFIG = {
  displaylogo: false,
  responsive: true,
  // The bundled basemaps make geo plots work with no network access.
  topojsonURL: 'vendor/topojson/',
  toImageButtonOptions: {format: 'png', scale: 2, filename: 'veda_plot'},
  modeBarButtonsToRemove: ['sendDataToCloud', 'select2d'],
};

export function layoutBase(extra = {}) {
  return Object.assign({
    font: {family: '"Segoe UI", system-ui, sans-serif', size: 12, color: '#16191d'},
    paper_bgcolor: '#ffffff',
    plot_bgcolor: '#ffffff',
    margin: {l: 64, r: 18, t: 34, b: 52},
    hovermode: 'closest',
    xaxis: {gridcolor: '#eceff2', zeroline: false, ticks: 'outside',
            ticklen: 4, tickcolor: '#c9d0d8', automargin: true},
    yaxis: {gridcolor: '#eceff2', zeroline: false, ticks: 'outside',
            ticklen: 4, tickcolor: '#c9d0d8', automargin: true},
    legend: {bgcolor: 'rgba(255,255,255,.75)', bordercolor: '#d9dee4',
             borderwidth: 0, font: {size: 11}},
  }, extra);
}

export function emptyPlot(nodeId, message) {
  Plotly.purge(nodeId);
  const node = document.getElementById(nodeId);
  clear(node);
  node.append(el('p', {class: 'hint', style: 'padding:34px 6px;text-align:center'},
                 message));
}
