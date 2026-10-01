/**
 * Product viewer: plots any archive product, whatever the payload.
 *
 *  - tables: choose the x field and any number of y fields; vector fields
 *    (a spectrum or energy channels per row) are drawn as a spectrogram with
 *    their mean spectrum;
 *  - images and maps: stretch, colour map, band, value read-out, line transects;
 *  - spectral cubes: band slider and the spectrum at any clicked pixel.
 *
 * Data come from /api/veda/product/... already decimated (peaks kept), so a
 * product with millions of rows stays responsive.
 */
import { api } from './api.js';
import { toast, themedLayout, plotColors, drawer } from './ui.js';
import { styleTrace, styleGeneric, paletteColor, plotStyleBody, exportFigure } from './plot_style.js';

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const CMAPS = ['gray', 'inferno', 'viridis', 'magma', 'plasma', 'cividis', 'twilight', 'RdBu_r', 'jet'];
const STRETCHES = [['percentile', 'Percentile 0.5-99.5%'], ['zscale', 'ZScale'], ['linear', 'Linear (min-max)'],
  ['sqrt', 'Square root'], ['log', 'Log'], ['asinh', 'Asinh'], ['histeq', 'Histogram equalised']];

const st = { box: null, p: null, structure: null, object: null, token: 0, table: null, image: null, onGeometry: null };

/** Open product ``p`` ({dataset_id, product_id, ...}) in ``box``. */
export async function showProductViewer(box, p, { onGeometry } = {}) {
  st.box = box; st.p = p; st.onGeometry = onGeometry || null;
  const token = ++st.token;
  box.innerHTML = `<div class="empty-state">Downloading and reading <code>${esc(p.product_id)}</code>&hellip;</div>`;
  try {
    const s = await api.productStructure(p.dataset_id, p.product_id);
    if (token !== st.token) return;
    st.structure = s;
    render(s.objects[0]?.name);
  } catch (err) {
    if (token !== st.token) return;
    box.innerHTML = `<div class="empty-state">This product could not be plotted: ${esc(err.message)}
      <br><span class="hint">It is still downloaded in the cache; you can open the folder from Settings &gt; Data folders.</span></div>`;
  }
}

function render(objectName) {
  const s = st.structure;
  const obj = s.objects.find(o => o.name === objectName) || s.objects[0];
  st.object = obj;
  const meta = s.metadata || {};
  const prod = s.product || st.p;
  const facts = [
    prod.mission_id && prod.mission_id.toUpperCase(), prod.instrument, prod.level,
    (prod.start_time || meta.START_TIME || '').replace('T', ' ').slice(0, 19), meta.TARGET_NAME,
  ].filter(Boolean).map(esc).join(' &middot; ');
  st.box.innerHTML = `
    <div class="pv">
      <div class="viewer-toolbar">
        <div class="viewer-title">
          <h3><code>${esc(st.p.product_id)}</code></h3>
          <div class="hint">${facts} &middot; ${esc(s.format)}${prod.product_type ? ` &middot; ${esc(prod.product_type)}` : ''}</div>
        </div>
        <div class="toolbar-actions">
          <button type="button" class="btn small ghost" data-pv="style">&#127912; Plot style</button>
          <button type="button" class="btn small ghost" data-pv="export">&#128444;&#65039; Export figure</button>
          ${st.onGeometry ? '<button type="button" class="btn small ghost" data-pv="geometry">&#128752;&#65039; Geometry</button>' : ''}
          ${obj.kind === 'table' ? '<button type="button" class="btn small ghost" data-pv="csv">&#128229; CSV of shown fields</button>' : ''}
        </div>
      </div>
      ${s.objects.length > 1 ? `<div class="pv-objects" role="tablist">${s.objects.map(o => `
        <button type="button" role="tab" class="view-subtab-btn ${o.name === obj.name ? 'active' : ''}" data-obj="${esc(o.name)}"
          title="${esc(o.description)}">${esc(o.name)} <span class="hint">${esc(o.kind)} ${o.shape.filter(Boolean).join('&times;')}</span></button>`).join('')}</div>` : ''}
      <div class="pv-body"></div>
    </div>`;
  st.box.querySelectorAll('[data-obj]').forEach(b => b.addEventListener('click', () => render(b.dataset.obj)));
  st.box.querySelector('[data-pv="style"]').addEventListener('click', () =>
    drawer('Plot style', plotStyleBody(() => redraw(), plotDiv())));
  st.box.querySelector('[data-pv="export"]').addEventListener('click', () => {
    const gd = plotDiv();
    if (gd) exportFigure(gd, `veda_${st.p.product_id}_${obj.name}`.replace(/[^\w.-]+/g, '_'));
  });
  st.box.querySelector('[data-pv="geometry"]')?.addEventListener('click', () => st.onGeometry(st.p));
  st.box.querySelector('[data-pv="csv"]')?.addEventListener('click', downloadCsv);
  const body = st.box.querySelector('.pv-body');
  if (obj.kind === 'table') renderTableControls(body, obj);
  else renderImageControls(body, obj);
}

function plotDiv() { return st.box?.querySelector('.pv-plot.js-plotly-plot') || st.box?.querySelector('.pv-plot'); }
function redraw() { if (st.object?.kind === 'table') drawTable(); else drawImage(); }

// ================================================================ tables

function guessY(obj, x) {
  const skip = /(^|[ _.])(SAMPLE|RECORD|ROW|INDEX|PACKET|SEQUENCE|FRAME|COUNTER)([ _]?(NUMBER|NO|ID|COUNT))?$|EPHEMERIS|SCLK|(^|[ _])(ET|TIME|UTC|YEAR|MONTH|DAY|HOUR|MINUTE|SECOND)([ _]|$)|^(ET|UTC|SCET|ERT)[A-Z]{0,4}$|QUALITY|FLAG|MODE|STATUS|SPARE/i;
  const nums = obj.fields.filter(f => f.kind === 'number' && f.name !== x);
  const pick = nums.find(f => f.items === 1 && !skip.test(f.name)) || nums.find(f => f.items > 1 && !skip.test(f.name)) || nums[0];
  return pick ? [pick.name] : [];
}

function renderTableControls(body, obj) {
  const timeField = obj.fields.find(f => f.kind === 'time');
  const saved = st.table && st.table.object === obj.name && st.table.product === st.p.product_id ? st.table : null;
  const x = saved ? saved.x : (timeField ? timeField.name : '');
  const y = saved ? saved.y : guessY(obj, x);
  st.table = { object: obj.name, product: st.p.product_id, x, y, panels: saved?.panels ?? 'shared', logy: saved?.logy ?? false,
               logz: saved?.logz ?? true, data: null };
  const fieldLabel = (f) => `${f.name}${f.unit ? ` [${f.unit}]` : ''}${f.items > 1 ? ` (${f.items} values per row)` : ''}`;
  body.innerHTML = `
    <div class="pv-table">
      <div class="pv-controls">
        <label>X axis <select class="pv-x">
          <option value="">Row number</option>
          ${obj.fields.filter(f => f.items === 1 && f.kind !== 'text').map(f => `<option value="${esc(f.name)}" ${f.name === x ? 'selected' : ''}>${esc(fieldLabel(f))}${f.kind === 'time' ? ' (time)' : ''}</option>`).join('')}
        </select></label>
        <label>Panels <select class="pv-panels">
          <option value="shared">One plot</option><option value="separate">One panel per field</option>
        </select></label>
        <label class="inline"><input type="checkbox" class="pv-logy" /> Log y</label>
        <label class="inline"><input type="checkbox" class="pv-logz" checked /> Log colour (spectrograms)</label>
        <span class="hint pv-count"></span>
      </div>
      <div class="pv-split">
        <div class="pv-fields">
          <input type="search" class="pv-filter" placeholder="Filter ${obj.fields.length} fields..." aria-label="Filter fields" />
          <div class="pv-field-list">${obj.fields.map(f => `
            <label class="pv-field ${f.kind !== 'number' ? 'pv-field-text' : ''}" title="${esc(f.description || '')}">
              <input type="checkbox" value="${esc(f.name)}" ${y.includes(f.name) ? 'checked' : ''} ${f.kind !== 'number' ? 'disabled' : ''} />
              <span>${esc(f.name)}</span><span class="hint">${esc(f.unit || '')}${f.items > 1 ? ` &times;${f.items}` : ''}${f.kind !== 'number' ? ` ${esc(f.kind)}` : ''}</span>
            </label>`).join('')}</div>
        </div>
        <div class="pv-plot-wrap"><div class="pv-plot" style="min-height:460px"></div></div>
      </div>
    </div>`;
  const q = (s) => body.querySelector(s);
  q('.pv-panels').value = st.table.panels;
  q('.pv-logy').checked = st.table.logy;
  q('.pv-logz').checked = st.table.logz;
  q('.pv-x').addEventListener('change', (e) => { st.table.x = e.target.value; loadTable(); });
  q('.pv-panels').addEventListener('change', (e) => { st.table.panels = e.target.value; drawTable(); });
  q('.pv-logy').addEventListener('change', (e) => { st.table.logy = e.target.checked; drawTable(); });
  q('.pv-logz').addEventListener('change', (e) => { st.table.logz = e.target.checked; drawTable(); });
  q('.pv-filter').addEventListener('input', (e) => {
    const t = e.target.value.trim().toLowerCase();
    body.querySelectorAll('.pv-field').forEach(l => { l.hidden = t && !l.textContent.toLowerCase().includes(t); });
  });
  body.querySelectorAll('.pv-field input').forEach(cb => cb.addEventListener('change', () => {
    const chosen = [...body.querySelectorAll('.pv-field input:checked')].map(c => c.value);
    if (chosen.length > 8) { cb.checked = false; return toast('Up to 8 fields at a time', 'bad'); }
    st.table.y = chosen;
    loadTable();
  }));
  loadTable();
}

let tableDebounce = null;
function loadTable() {
  clearTimeout(tableDebounce);
  tableDebounce = setTimeout(async () => {
    const t = st.table, token = st.token;
    const div = plotDiv();
    if (!t.y.length) { div.innerHTML = '<div class="empty-state">Tick one or more fields to plot.</div>'; return; }
    div.classList.add('loading');
    try {
      const d = await api.productTable(st.p.dataset_id, st.p.product_id, { object: t.object, x: t.x, y: t.y });
      if (token !== st.token || t !== st.table) return;
      t.data = d;
      const c = st.box.querySelector('.pv-count');
      if (c) c.textContent = d.shown < d.rows ? `${d.rows.toLocaleString()} rows; ${d.shown.toLocaleString()} drawn (minima and maxima kept)` : `${d.rows.toLocaleString()} rows`;
      drawTable();
    } catch (err) {
      div.innerHTML = `<div class="empty-state">Could not read these fields: ${esc(err.message)}</div>`;
    } finally {
      div.classList.remove('loading');
    }
  }, 120);
}

function axisTitle(name, unit) { return unit ? `${name} [${unit}]` : name; }
const shortTitle = (s, n = 34) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

function drawTable() {
  const t = st.table, d = t?.data;
  const div = plotDiv();
  if (!d || !div) return;
  if (div.firstElementChild && !div.classList.contains('js-plotly-plot')) div.innerHTML = '';
  const xIsTime = d.x.kind === 'time';
  const xs = d.x.values;
  const traces = [];
  const layout = { margin: { l: 70, r: 30, t: 30, b: 50 }, showlegend: true, hovermode: 'closest' };
  const scalars = d.series.filter(s => s.values);
  const vectors = d.vectors || [];
  const panels = (t.panels === 'separate' ? scalars.length : (scalars.length ? 1 : 0)) + vectors.length * 2;
  const n = Math.max(panels, 1);
  const gap = 0.04, h = (1 - gap * (n - 1)) / n;
  const domain = (k) => [Math.max(0, 1 - (k + 1) * h - k * gap), 1 - k * (h + gap)];
  let k = 0;
  const yaxis = (i) => (i === 0 ? 'y' : `y${i + 1}`);
  const yLayout = (i, title, extra = {}) => {
    layout[i === 0 ? 'yaxis' : `yaxis${i + 1}`] = { domain: domain(i), title: { text: title }, anchor: 'x',
      type: t.logy && !extra.noLog ? 'log' : 'linear', automargin: true, ...extra };
  };
  scalars.forEach((s, i) => {
    const panel = t.panels === 'separate' ? k + i : k;
    traces.push(styleTrace({ type: 'scattergl', x: xs, y: s.values, name: axisTitle(s.name, s.unit), xaxis: 'x', yaxis: yaxis(panel),
      hovertemplate: `%{y:.5g} ${esc(s.unit || '')}<extra>${esc(s.name)}</extra>` }, i));
    if (t.panels === 'separate' || i === 0) {
      yLayout(panel, t.panels === 'separate' || scalars.length === 1 ? shortTitle(axisTitle(s.name, s.unit)) : 'Value');
    }
  });
  k += t.panels === 'separate' ? scalars.length : (scalars.length ? 1 : 0);
  vectors.forEach((v) => {
    traces.push({ type: 'heatmap', x: v.x, z: transpose(v.z), colorscale: 'Viridis', xaxis: 'x', yaxis: yaxis(k),
      name: v.name, zsmooth: false, hoverongaps: false,
      transforms: [], colorbar: { title: { text: v.unit || '' }, len: h, y: (domain(k)[0] + domain(k)[1]) / 2, thickness: 12 },
      ...(t.logz ? { z: transpose(v.z).map(r => r.map(val => (val != null && val > 0 ? Math.log10(val) : null))),
                    colorbar: { title: { text: `log10 ${v.unit || ''}` }, len: h, y: (domain(k)[0] + domain(k)[1]) / 2, thickness: 12 } } : {}),
      hovertemplate: `channel %{y}<br>%{z:.4g}<extra>${esc(v.name)}</extra>` });
    yLayout(k, `${v.name} channel${v.channel_step > 1 ? ` (/${v.channel_step})` : ''}`, { noLog: true });
    k += 1;
    // mean spectrum on its own x axis
    const xa = `x${k + 1}`;
    traces.push(styleTrace({ type: 'scatter', x: v.mean.map((_, i) => i), y: v.mean, name: `${v.name} (mean over rows)`,
      xaxis: xa, yaxis: yaxis(k) }, k));
    layout[`xaxis${k + 1}`] = { anchor: yaxis(k), title: { text: 'Channel' }, domain: [0, 1] };
    yLayout(k, axisTitle('Mean', v.unit));
    k += 1;
  });
  const anchorAxis = n === 1 ? 'y' : yaxis(Math.max(0, scalars.length && t.panels === 'separate' ? scalars.length - 1 : 0));
  layout.xaxis = { title: { text: axisTitle(d.x.name, d.x.unit) }, type: xIsTime ? 'date' : 'linear', anchor: anchorAxis, automargin: true };
  if (n > 1) layout.height = Math.max(460, 230 * n);
  if (!traces.length) { div.innerHTML = '<div class="empty-state">The chosen fields contain no numbers.</div>'; return; }
  const finalLayout = themedLayout(styleGeneric(layout));
  window.Plotly.react(div, traces, finalLayout, { responsive: true, displaylogo: false });
}

function transpose(rows) {
  if (!rows.length) return [];
  const out = rows[0].map(() => new Array(rows.length));
  rows.forEach((r, i) => r.forEach((v, j) => { out[j][i] = v; }));
  return out;
}

function downloadCsv() {
  const d = st.table?.data;
  if (!d) return;
  const cols = [d.x, ...d.series.filter(s => s.values || s.text)];
  const header = cols.map(c => `"${axisTitle(c.name, c.unit).replace(/"/g, '""')}"`).join(',');
  const lines = d.x.values.map((xv, i) => [xv, ...cols.slice(1).map(c => (c.values ? c.values[i] : c.text[i]))]
    .map(v => (v == null ? '' : typeof v === 'string' ? `"${v.replace(/"/g, '""')}"` : v)).join(','));
  const note = d.shown < d.rows ? `# ${d.shown} of ${d.rows} rows (decimated, minima and maxima kept)\n` : '';
  const blob = new Blob([`# ${st.p.dataset_id} / ${st.p.product_id} / ${d.object}\n${note}${header}\n${lines.join('\n')}\n`], { type: 'text/csv' });
  const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: `${st.p.product_id}_${d.object}.csv`.replace(/[^\w.-]+/g, '_') });
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

// ================================================================ images and cubes

function renderImageControls(body, obj) {
  const bands = obj.shape[0] || 1;
  const prev = st.image && st.image.object === obj.name && st.image.product === st.p.product_id ? st.image : null;
  st.image = { object: obj.name, product: st.p.product_id, band: prev?.band ?? 0, stretch: prev?.stretch ?? 'percentile',
               cmap: prev?.cmap ?? (obj.extent?.x ? 'inferno' : 'gray'), tool: obj.kind === 'cube' ? 'spectrum' : 'value',
               clicks: [], stats: null, flip: false };
  const isMap = !!(obj.extent && obj.extent.x && obj.extent.y);
  body.innerHTML = `
    <div class="pv-image">
      <div class="pv-controls">
        ${bands > 1 ? `<label>Band <input type="range" class="pv-band" min="0" max="${bands - 1}" value="${st.image.band}" />
          <output class="pv-band-out">${st.image.band + 1} / ${bands}</output></label>` : ''}
        <label>Stretch <select class="pv-stretch">${STRETCHES.map(([v, l]) => `<option value="${v}">${l}</option>`).join('')}</select></label>
        <label>Colours <select class="pv-cmap">${CMAPS.map(c => `<option>${c}</option>`).join('')}</select></label>
        <label>Click to <select class="pv-tool">
          <option value="value">read the value</option>
          <option value="transect">draw a transect (two clicks)</option>
          ${bands > 1 ? '<option value="spectrum">plot the spectrum</option>' : ''}
        </select></label>
        ${isMap ? '' : '<label class="inline"><input type="checkbox" class="pv-flip" /> Flip vertically</label>'}
        <span class="hint pv-readout"></span>
      </div>
      <div class="pv-plot" style="min-height:520px"></div>
      <div class="pv-side">
        <div class="pv-side-plot"></div>
        <div class="hint pv-stats"></div>
      </div>
    </div>`;
  const q = (s) => body.querySelector(s);
  q('.pv-stretch').value = st.image.stretch;
  q('.pv-cmap').value = st.image.cmap;
  q('.pv-tool').value = st.image.tool;
  q('.pv-stretch').addEventListener('change', (e) => { st.image.stretch = e.target.value; drawImage(); });
  q('.pv-cmap').addEventListener('change', (e) => { st.image.cmap = e.target.value; drawImage(); });
  q('.pv-tool').addEventListener('change', (e) => { st.image.tool = e.target.value; st.image.clicks = []; });
  q('.pv-flip')?.addEventListener('change', (e) => { st.image.flip = e.target.checked; drawImage(); });
  const band = q('.pv-band');
  if (band) {
    let t = null;
    band.addEventListener('input', () => {
      q('.pv-band-out').textContent = `${+band.value + 1} / ${bands}`;
      clearTimeout(t);
      t = setTimeout(() => { st.image.band = +band.value; drawImage(); }, 180);
    });
  }
  drawImage();
}

async function drawImage() {
  const im = st.image, obj = st.object, token = st.token;
  const div = plotDiv();
  if (!im || !div) return;
  const [, lines, samples] = obj.shape.length === 3 ? obj.shape : [1, ...obj.shape.slice(-2)];
  const url = api.productImageUrl(st.p.dataset_id, st.p.product_id,
    { object: obj.name, band: im.band, stretch: im.stretch, cmap: im.cmap, flip: im.flip });
  let stats = null;
  try {
    stats = await api.productImageStats(st.p.dataset_id, st.p.product_id, { object: obj.name, band: im.band });
  } catch (err) {
    div.innerHTML = `<div class="empty-state">Could not read this image: ${esc(err.message)}</div>`;
    return;
  }
  if (token !== st.token || im !== st.image) return;
  im.stats = stats;
  const ex = obj.extent || {};
  const isMap = !!(ex.x && ex.y);
  // pixel centres -> axis coordinates
  const x0 = isMap ? ex.x[0] : 0, x1 = isMap ? ex.x[1] : samples - 1;
  const y0 = isMap ? ex.y[0] : 0, y1 = isMap ? ex.y[1] : lines - 1;
  const dx = samples > 1 ? (x1 - x0) / (samples - 1) : 1, dy = lines > 1 ? (y1 - y0) / (lines - 1) : 1;
  im.toPixel = (x, y) => ({ sample: Math.round((x - x0) / dx), line: Math.round(isMap || !im.flip ? (y - y0) / dy : (y1 - y) / dy) });
  // For a map the first row is at y0 (e.g. -90): the PNG's first row must sit at y0, i.e. at the bottom.
  const top = isMap ? Math.max(y0, y1) : y0 - dy / 2;
  const sizey = Math.abs(y1 - y0) + Math.abs(dy);
  const flipRows = isMap && y0 < y1;
  const src = flipRows ? api.productImageUrl(st.p.dataset_id, st.p.product_id,
    { object: obj.name, band: im.band, stretch: im.stretch, cmap: im.cmap, flip: true }) : url;
  const xr = [x0 - dx / 2, x1 + dx / 2];
  const yr = isMap ? [Math.min(y0, y1) - Math.abs(dy) / 2, Math.max(y0, y1) + Math.abs(dy) / 2] : [lines - 0.5, -0.5];
  const layout = {
    margin: { l: 70, r: 20, t: 30, b: 50 }, height: Math.min(720, Math.max(420, 600 * lines / Math.max(samples, 1))),
    xaxis: { range: xr, title: { text: isMap ? `${ex.x[2]} [${ex.x[3]}]` : 'Sample' }, showgrid: false, zeroline: false, constrain: 'domain' },
    yaxis: { range: yr, title: { text: isMap ? `${ex.y[2]} [${ex.y[3]}]` : 'Line' }, showgrid: false, zeroline: false,
             scaleanchor: isMap ? undefined : 'x', constrain: 'domain' },
    images: [{ source: src, xref: 'x', yref: 'y', x: xr[0], y: isMap ? top + Math.abs(dy) / 2 : -0.5,
               sizex: xr[1] - xr[0], sizey: isMap ? sizey : lines, sizing: 'stretch', layer: 'below',
               yanchor: isMap ? 'top' : 'top' }],
    showlegend: false, dragmode: 'pan', hovermode: false,
    title: { text: `${esc(obj.name)}${obj.unit ? ` [${esc(obj.unit)}]` : ''}${(obj.shape[0] || 1) > 1 ? ` &middot; band ${im.band + 1}` : ''}`, font: { size: 13 } },
  };
  if (!isMap) layout.images[0].y = -0.5;
  const marks = { type: 'scatter', mode: 'lines+markers', x: [], y: [], line: { color: '#ffeb3b', width: 2 },
                  marker: { color: '#ffeb3b', size: 7 }, hoverinfo: 'skip' };
  await window.Plotly.react(div, [marks], themedLayout(styleGeneric(layout)), { responsive: true, displaylogo: false, scrollZoom: true });
  bindImageClicks(div);
  const s = st.box.querySelector('.pv-stats');
  if (s) {
    s.innerHTML = stats.min == null ? 'No valid pixels in this band.' :
      `min ${fmt(stats.min)} &middot; mean ${fmt(stats.mean)} &middot; max ${fmt(stats.max)} ${esc(stats.unit || '')}
       &middot; ${(100 * stats.valid_fraction).toFixed(1)}% valid pixels &middot; ${samples}&times;${lines} pixels${stats.step > 1 ? ` (shown at 1/${stats.step})` : ''}`;
  }
  if (!st.box.querySelector('.pv-side-plot').dataset.used) drawHistogram(stats);
}

function fmt(v) { return v == null ? '-' : Math.abs(v) >= 1e5 || (Math.abs(v) < 1e-3 && v !== 0) ? v.toExponential(3) : (+v).toPrecision(5); }

function bindImageClicks(div) {
  if (div.dataset.bound) return;
  div.dataset.bound = '1';
  div.addEventListener('click', async (e) => {
    const im = st.image, gd = div;
    const xa = gd._fullLayout?.xaxis, ya = gd._fullLayout?.yaxis;
    if (!xa || !ya) return;
    const rect = gd.getBoundingClientRect();
    const px = e.clientX - rect.left - xa._offset, py = e.clientY - rect.top - ya._offset;
    if (px < 0 || py < 0 || px > xa._length || py > ya._length) return;
    const x = xa.p2c(px), y = ya.p2c(py);
    const { line, sample } = im.toPixel(x, y);
    const [, lines, samples] = st.object.shape.length === 3 ? st.object.shape : [1, ...st.object.shape.slice(-2)];
    if (line < 0 || sample < 0 || line >= lines || sample >= samples) return;
    const readout = st.box.querySelector('.pv-readout');
    try {
      if (im.tool === 'transect') {
        im.clicks.push({ x, y, line, sample });
        window.Plotly.restyle(gd, { x: [im.clicks.map(c => c.x)], y: [im.clicks.map(c => c.y)] }, [0]);
        if (im.clicks.length < 2) { readout.textContent = 'Click the end of the transect'; return; }
        const [a, b] = im.clicks; im.clicks = [];
        const t = await api.productTransect(st.p.dataset_id, st.p.product_id,
          { object: st.object.name, band: im.band, x0: a.sample, y0: a.line, x1: b.sample, y1: b.line });
        readout.textContent = `Transect (${a.sample}, ${a.line}) to (${b.sample}, ${b.line})`;
        drawSide([{ x: t.distances_pixels, y: t.intensities, name: 'Transect' }], 'Distance along the line (pixels)', axisTitle('Value', t.unit));
      } else {
        const sp = await api.productSpectrum(st.p.dataset_id, st.p.product_id,
          { object: st.object.name, line, sample, box: im.tool === 'spectrum' ? 1 : 0 });
        const v = sp.values[Math.min(im.band, sp.values.length - 1)];
        readout.textContent = `line ${line}, sample ${sample}${st.object.extent?.x ? ` (${x.toFixed(2)}, ${y.toFixed(2)})` : ''}: ${fmt(v)} ${sp.unit || ''}`;
        window.Plotly.restyle(gd, { x: [[x]], y: [[y]] }, [0]);
        if (im.tool === 'spectrum') {
          const prev = (st.box.querySelector('.pv-side-plot').data || []).filter(tr => tr.name?.startsWith('Pixel')).slice(-4);
          drawSide([...prev.map(p => ({ x: p.x, y: p.y, name: p.name })), { x: sp.band.map(b => b + 1), y: sp.values, name: `Pixel ${sample}, ${line}` }],
            'Band', axisTitle('Value (3x3 mean)', sp.unit));
        }
      }
    } catch (err) {
      readout.textContent = `Could not read the pixel: ${err.message}`;
    }
  });
}

function drawHistogram(stats) {
  const h = stats.histogram || {};
  if (!h.bins?.length) return;
  drawSide([{ x: h.bins, y: h.counts, name: 'Histogram', type: 'bar' }], axisTitle('Value', stats.unit), 'Pixels', true);
}

function drawSide(series, xTitle, yTitle, isHist = false) {
  const div = st.box.querySelector('.pv-side-plot');
  if (!div) return;
  if (!isHist) div.dataset.used = '1';
  const traces = series.map((s, i) => (s.type === 'bar'
    ? { type: 'bar', x: s.x, y: s.y, name: s.name, marker: { color: plotColors().accent || paletteColor(0) } }
    : styleTrace({ type: 'scatter', x: s.x, y: s.y, name: s.name }, i)));
  window.Plotly.react(div, traces, themedLayout(styleGeneric({ height: 300, margin: { l: 60, r: 20, t: 20, b: 45 },
    xaxis: { title: { text: xTitle } }, yaxis: { title: { text: yTitle } }, showlegend: series.length > 1, bargap: 0 })),
    { responsive: true, displaylogo: false });
}
