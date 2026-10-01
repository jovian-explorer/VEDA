/**
 * Plot style: one set of user choices applied to every profile plot.
 * Saved per computer (localStorage); "Journal" presets give print-ready figures.
 */
import { plotColors, el } from './ui.js';

const KEY = 'veda_plot_style_v1';

export const PALETTES = {
  veda: ['#38bdf8', '#f97316', '#a78bfa', '#22c55e', '#f43f5e', '#eab308', '#14b8a6', '#ec4899', '#64748b', '#84cc16'],
  okabe_ito: ['#0072B2', '#E69F00', '#009E73', '#D55E00', '#CC79A7', '#56B4E9', '#F0E442', '#000000'],
  tableau10: ['#4E79A7', '#F28E2B', '#E15759', '#76B7B2', '#59A14F', '#EDC948', '#B07AA1', '#FF9DA7', '#9C755F', '#BAB0AC'],
  viridis: ['#440154', '#414487', '#2A788E', '#22A884', '#7AD151', '#FDE725'],
  grayscale: ['#000000', '#555555', '#888888', '#AAAAAA', '#333333', '#777777'],
};
export const PALETTE_LABELS = {
  veda: 'VEDA (screen)', okabe_ito: 'Okabe-Ito (colour-blind safe)', tableau10: 'Tableau 10',
  viridis: 'Viridis (perceptually uniform)', grayscale: 'Greyscale (print)',
};

// Journal presets: single/double column widths in mm and the fonts journals ask for.
export const JOURNALS = {
  agu: { label: 'AGU (JGR, GRL)', single_mm: 95, double_mm: 190, font: 'Arial, Helvetica, sans-serif', size: 9 },
  icarus: { label: 'Icarus / PSS (Elsevier)', single_mm: 90, double_mm: 190, font: 'Times New Roman, Times, serif', size: 9 },
  aa: { label: 'A&A', single_mm: 88, double_mm: 180, font: 'Times New Roman, Times, serif', size: 9 },
  mnras: { label: 'MNRAS', single_mm: 84, double_mm: 174, font: 'Times New Roman, Times, serif', size: 8 },
};

export const DEFAULTS = {
  mode: 'lines',            // lines | markers | lines+markers
  lineWidth: 2,
  dash: 'solid',            // solid | dot | dash | dashdot
  markerSize: 4,
  markerSymbol: 'circle',
  palette: 'veda',
  uncertainty: 'band',      // none | bars | band
  vertical: 'altitude',     // altitude | pressure
  swapAxes: false,
  xScale: 'auto',           // auto | linear | log
  xMin: '', xMax: '', yMin: '', yMax: '',
  grid: true,
  mirror: false,            // frame on all four sides
  ticks: 'outside',         // outside | inside
  fontFamily: 'sans',       // sans | serif
  fontSize: 12,
  legend: 'bottom',         // bottom | right | top-inside | hidden
  template: 'screen',       // screen | journal
  journal: 'agu',
  exportColumns: 'single',  // single | double
  exportFormat: 'png',      // png | svg
  exportDpi: 300,
};

export const style = load();

function load() {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) || '{}');
    return { ...DEFAULTS, ...saved };
  } catch (_) {
    return { ...DEFAULTS };
  }
}

export function saveStyle(patch = {}) {
  Object.assign(style, patch);
  try { localStorage.setItem(KEY, JSON.stringify(style)); } catch (_) {}
}

export function resetStyle() {
  Object.keys(style).forEach(k => delete style[k]);
  Object.assign(style, DEFAULTS);
  try { localStorage.removeItem(KEY); } catch (_) {}
}

export function paletteColor(i) {
  const p = PALETTES[style.palette] || PALETTES.veda;
  return p[i % p.length];
}

function fontFamily() {
  if (style.template === 'journal') return (JOURNALS[style.journal] || JOURNALS.agu).font;
  return style.fontFamily === 'serif' ? 'Times New Roman, Times, serif' : 'Segoe UI, Helvetica, Arial, sans-serif';
}

/** Style a data trace in place.  `xy` = {x, y} arrays already in plot orientation. */
export function styleTrace(trace, i, opts = {}) {
  const color = opts.color || paletteColor(i);
  trace.mode = style.mode;
  trace.line = { ...(trace.line || {}), color, width: opts.width || style.lineWidth, dash: opts.dash || style.dash };
  trace.marker = { ...(trace.marker || {}), color, size: style.markerSize, symbol: style.markerSymbol };
  if (opts.sigma && style.uncertainty === 'bars') {
    const err = { type: 'data', array: opts.sigma.map(v => (v == null ? 0 : v)), visible: true, color, thickness: 1, width: 0 };
    if (style.swapAxes) trace.error_y = err; else trace.error_x = err;
  }
  return trace;
}

/** Shaded +/-1 sigma band around a profile (two traces; add before the line). */
export function sigmaBand(values, coord, sigma, color, name) {
  if (!sigma || style.uncertainty !== 'band') return [];
  const lo = values.map((v, k) => (v == null || sigma[k] == null ? null : v - sigma[k]));
  const hi = values.map((v, k) => (v == null || sigma[k] == null ? null : v + sigma[k]));
  const fill = hexToRgba(color, 0.18);
  const make = (vals, extra) => (style.swapAxes ? { x: coord, y: vals } : { x: vals, y: coord });
  return [
    { ...make(lo), type: 'scatter', mode: 'lines', line: { width: 0, color: 'transparent' }, showlegend: false, hoverinfo: 'skip' },
    { ...make(hi), type: 'scatter', mode: 'lines', line: { width: 0, color: 'transparent' }, hoverinfo: 'skip',
      fill: style.swapAxes ? 'tonexty' : 'tonextx', fillcolor: fill, name: `${name} ±1σ`, showlegend: true },
  ];
}

function hexToRgba(hex, a) {
  const m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex || '');
  if (!m) return `rgba(56,189,248,${a})`;
  return `rgba(${parseInt(m[1], 16)},${parseInt(m[2], 16)},${parseInt(m[3], 16)},${a})`;
}

const num = (v) => (v === '' || v == null || Number.isNaN(Number(v)) ? null : Number(v));

/**
 * Apply axes, fonts, grid and legend choices to a layout whose x axis holds the
 * variable and y axis the vertical coordinate (swapping is done here).
 */
export function styleLayout(layout, { xLog = false, varTitle = '', coordTitle = '' } = {}) {
  const journal = style.template === 'journal';
  const c = plotColors();
  const ink = journal ? '#000000' : c.ink;
  const size = journal ? (JOURNALS[style.journal] || JOURNALS.agu).size + 2 : style.fontSize;
  const varAxis = {
    ...(layout.xaxis || {}),
    title: { text: varTitle || (layout.xaxis && layout.xaxis.title && layout.xaxis.title.text) || '' },
    type: style.xScale === 'auto' ? (xLog ? 'log' : 'linear') : style.xScale,
  };
  const coordIsPressure = style.vertical === 'pressure';
  const coordAxis = {
    ...(layout.yaxis || {}),
    title: { text: coordTitle || (layout.yaxis && layout.yaxis.title && layout.yaxis.title.text) || '' },
    type: coordIsPressure ? 'log' : 'linear',
    autorange: coordIsPressure ? 'reversed' : true,
  };
  const xr = [num(style.xMin), num(style.xMax)];
  const yr = [num(style.yMin), num(style.yMax)];
  const range = (r, ax) => {
    if (r[0] == null || r[1] == null) return;
    ax.autorange = false;
    ax.range = ax.type === 'log' ? r.map(v => Math.log10(Math.max(v, 1e-300))) : r;
    if (ax === coordAxis && coordIsPressure) ax.range = ax.range.slice().reverse();
  };
  range(xr, varAxis);
  range(yr, coordAxis);
  for (const ax of [varAxis, coordAxis]) {
    ax.showgrid = style.grid;
    ax.mirror = style.mirror || journal ? 'ticks' : false;
    ax.ticks = journal ? 'inside' : style.ticks;
    ax.showline = journal || style.mirror;
    ax.linecolor = ink;
    ax.zeroline = false;
    ax.title = { ...ax.title, font: { size, color: ink, family: fontFamily() } };
    ax.tickfont = { size: size - 1, color: ink, family: fontFamily() };
  }
  const out = { ...layout };
  out.xaxis = style.swapAxes ? coordAxis : varAxis;
  out.yaxis = style.swapAxes ? varAxis : coordAxis;
  out.font = { ...(layout.font || {}), family: fontFamily(), size, color: ink };
  if (out.title) out.title = { ...out.title, font: { ...(out.title.font || {}), family: fontFamily(), color: ink, size: size + 2 } };
  if (journal) {
    out.meta = { ...(out.meta || {}), journal: true };   // themedLayout leaves journal figures alone
    out.paper_bgcolor = '#ffffff';
    out.plot_bgcolor = '#ffffff';
    out.xaxis.gridcolor = '#e5e5e5';
    out.yaxis.gridcolor = '#e5e5e5';
  }
  const legends = {
    bottom: { orientation: 'h', x: 0, y: -0.18, yanchor: 'top' },
    right: { orientation: 'v', x: 1.02, y: 1, xanchor: 'left' },
    'top-inside': { orientation: 'v', x: 0.99, y: 0.99, xanchor: 'right', yanchor: 'top', bgcolor: journal ? 'rgba(255,255,255,0.8)' : 'rgba(0,0,0,0.25)' },
  };
  out.showlegend = style.legend !== 'hidden';
  if (out.showlegend) out.legend = { ...(layout.legend || {}), ...legends[style.legend], font: { size: size - 1, color: ink, family: fontFamily() } };
  const m = out.margin || {};
  out.margin = { ...m, b: style.legend === 'bottom' ? Math.max(m.b || 0, 110) : 60, r: style.legend === 'right' ? 160 : 25 };
  return out;
}

/** Put (value, coordinate) into plot orientation. */
export function orient(values, coord) {
  return style.swapAxes ? { x: coord, y: values } : { x: values, y: coord };
}

/** Download a plot at journal column width, or at its on-screen size. */
export function exportFigure(gd, filename) {
  if (!window.Plotly || !gd) return;
  const j = JOURNALS[style.journal] || JOURNALS.agu;
  const mm = style.exportColumns === 'double' ? j.double_mm : j.single_mm;
  const widthPx = Math.round(mm / 25.4 * 96);           // CSS px at 96 per inch
  const heightPx = Math.round(widthPx * (style.exportColumns === 'double' ? 0.6 : 1.15));
  const scale = style.exportFormat === 'svg' ? 1 : style.exportDpi / 96;
  return window.Plotly.downloadImage(gd, {
    format: style.exportFormat, filename, width: widthPx, height: heightPx, scale,
  });
}

// ---------------------------------------------------------------- controls


function select(id, value, options, onChange) {
  return el('select', { id, onchange: (e) => onChange(e.target.value) },
    ...options.map(([v, label]) => el('option', { value: v, selected: String(value) === String(v) }, label)));
}

function row(label, control, hint) {
  return el('label', { class: 'settings-field' },
    el('span', { class: 'settings-label' }, label), control, hint ? el('span', { class: 'hint' }, hint) : null);
}

function check(id, label, value, onChange) {
  return el('label', { class: 'settings-check' },
    el('input', { type: 'checkbox', id, checked: !!value, onchange: (e) => onChange(e.target.checked) }),
    el('span', {}, label));
}

/** Plot style panel; `onApply()` re-draws the open plots. `exportTarget()` returns {gd, name}. */
export function plotStyleBody(onApply, exportTarget) {
  const set = (k) => (v) => { saveStyle({ [k]: v }); onApply(); };
  const setNum = (k) => (v) => { saveStyle({ [k]: v === '' ? '' : Number(v) }); onApply(); };
  const number = (k, min, max, step) => el('input', {
    type: 'number', value: style[k], min, max, step, onchange: (e) => setNum(k)(e.target.value),
  });
  const box = el('div', { class: 'stack settings-form' });
  box.append(
    el('fieldset', {}, el('legend', {}, 'Lines and markers'),
      row('Draw as', select('ps-mode', style.mode, [['lines', 'Lines'], ['markers', 'Markers'], ['lines+markers', 'Lines and markers']], set('mode'))),
      row('Line width', number('lineWidth', 0.5, 6, 0.5)),
      row('Line style', select('ps-dash', style.dash, [['solid', 'Solid'], ['dash', 'Dashed'], ['dot', 'Dotted'], ['dashdot', 'Dash-dot']], set('dash'))),
      row('Marker size', number('markerSize', 1, 14, 1)),
      row('Marker', select('ps-sym', style.markerSymbol, [['circle', 'Circle'], ['square', 'Square'], ['diamond', 'Diamond'], ['triangle-up', 'Triangle'], ['cross', 'Cross'], ['x', 'X']], set('markerSymbol')))),
    el('fieldset', {}, el('legend', {}, 'Colours and uncertainty'),
      row('Palette', select('ps-pal', style.palette, Object.entries(PALETTE_LABELS), set('palette'))),
      row('Uncertainty', select('ps-unc', style.uncertainty, [['band', 'Shaded ±1σ band'], ['bars', 'Error bars'], ['none', 'Hidden']], set('uncertainty')),
        'Shown where the product provides 1σ values (e.g. MaRS, Akatsuki L4).')),
    el('fieldset', {}, el('legend', {}, 'Axes'),
      row('Vertical coordinate', select('ps-vert', style.vertical, [['altitude', 'Altitude (km)'], ['pressure', 'Pressure (log, top at top)']], set('vertical')),
        'Pressure needs a pressure column; profiles without one stay on altitude.'),
      check('ps-swap', 'Swap axes (variable on the vertical axis)', style.swapAxes, set('swapAxes')),
      row('Variable axis scale', select('ps-xs', style.xScale, [['auto', 'Automatic'], ['linear', 'Linear'], ['log', 'Logarithmic']], set('xScale'))),
      el('div', { class: 'ps-range' },
        row('Variable min', number('xMin', null, null, 'any')), row('Variable max', number('xMax', null, null, 'any'))),
      el('div', { class: 'ps-range' },
        row('Vertical min', number('yMin', null, null, 'any')), row('Vertical max', number('yMax', null, null, 'any'))),
      check('ps-grid', 'Grid lines', style.grid, set('grid')),
      check('ps-mirror', 'Frame on all sides', style.mirror, set('mirror')),
      row('Tick marks', select('ps-ticks', style.ticks, [['outside', 'Outside'], ['inside', 'Inside']], set('ticks')))),
    el('fieldset', {}, el('legend', {}, 'Text and legend'),
      row('Font', select('ps-font', style.fontFamily, [['sans', 'Sans-serif'], ['serif', 'Serif (Times)']], set('fontFamily'))),
      row('Font size', number('fontSize', 8, 24, 1)),
      row('Legend', select('ps-leg', style.legend, [['bottom', 'Below the plot'], ['right', 'Right of the plot'], ['top-inside', 'Inside, top right'], ['hidden', 'Hidden']], set('legend')))),
    el('fieldset', {}, el('legend', {}, 'Figure template and export'),
      row('Template', select('ps-tpl', style.template, [['screen', 'Screen (follows the theme)'], ['journal', 'Journal (white, framed, journal fonts)']], set('template'))),
      row('Journal', select('ps-jr', style.journal, Object.entries(JOURNALS).map(([k, j]) => [k, j.label]), set('journal'))),
      row('Width', select('ps-cols', style.exportColumns, [['single', 'Single column'], ['double', 'Double column']], set('exportColumns'))),
      row('Format', select('ps-fmt', style.exportFormat, [['png', 'PNG'], ['svg', 'SVG (vector)']], set('exportFormat'))),
      row('PNG resolution (DPI)', number('exportDpi', 72, 1200, 1)),
      el('div', { class: 'settings-actions' },
        el('button', {
          type: 'button', class: 'primary', onclick: () => {
            const t = exportTarget && exportTarget();
            if (!t || !t.gd || !t.gd.data) return;
            exportFigure(t.gd, t.name);
          },
        }, 'Export current plot'),
        el('button', {
          type: 'button', class: 'ghost', onclick: () => { resetStyle(); onApply(true); },
        }, 'Reset plot style'))),
  );
  return box;
}
