/**
 * Observation geometry (SPICE): orbit, view from Earth, tangent-point map and
 * solar angles for one radio-occultation product.
 */
import { api } from './api.js';
import { toast, themedLayout, plotColors } from './ui.js';
import { style as plotStyle, paletteColor } from './plot_style.js';

const VIEWS = [
  ['orbit-fixed', 'Orbit (planet-fixed)'],
  ['orbit-inertial', 'Orbit (inertial J2000)'],
  ['earth', 'View from Earth'],
  ['map', 'Tangent-point map'],
  ['angles', 'Angles along profile'],
];
const PROJECTIONS = [
  ['equirectangular', 'Cylindrical'], ['north', 'North polar'], ['south', 'South polar'], ['orthographic', 'Orthographic (centred on track)'],
];

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const state = { view: 'orbit-fixed', projection: 'equirectangular', data: null };

async function fetchGeometry(ds, pid) {
  const res = await fetch(`/api/veda/geometry/${encodeURIComponent(ds)}/${encodeURIComponent(pid)}`);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `${res.status} ${res.statusText}`);
  return body.kernels_needed ? { needKernels: body } : { data: body };
}

export async function showGeometry(box, { dataset_id, product_id }) {
  if (!dataset_id) {
    box.innerHTML = '<div class="hint">Geometry is available for archive products (it needs the data set and observation time).</div>';
    return;
  }
  box.innerHTML = '<div class="hint">Computing observation geometry...</div>';
  try {
    const r = await fetchGeometry(dataset_id, product_id);
    if (r.needKernels) return renderKernelPrompt(box, dataset_id, product_id, r.needKernels);
    state.data = r.data;
    render(box);
  } catch (err) {
    box.innerHTML = `<div class="hint text-danger">Geometry unavailable: ${esc(err.message)}</div>`;
  }
}

function renderKernelPrompt(box, ds, pid, info) {
  box.innerHTML = `
    <div class="geo-prompt">
      <p><strong>Observation geometry uses SPICE kernels</strong> (spacecraft orbit, planetary ephemeris and constants).
      These ${info.kernels.length} files, ${info.total_mb} MB in total, are downloaded once and reused for every observation they cover:</p>
      <ul>${info.kernels.map(k => `<li><code>${esc(k.name)}</code> ${k.bytes ? `(${(k.bytes / 1048576).toFixed(1)} MB)` : ''}</li>`).join('')}</ul>
      <button type="button" class="primary" id="geo-download">Download kernels and compute</button>
      <div class="arch-progress" id="geo-progress" hidden><div class="arch-progress-bar"><span id="geo-progress-fill"></span></div><span class="hint" id="geo-progress-text"></span></div>
    </div>`;
  box.querySelector('#geo-download').addEventListener('click', async (e) => {
    e.target.disabled = true;
    const prog = box.querySelector('#geo-progress');
    prog.hidden = false;
    try {
      const res = await fetch(`/api/veda/geometry/${encodeURIComponent(ds)}/${encodeURIComponent(pid)}/prepare`, { method: 'POST' });
      const { job_id, detail } = await res.json();
      if (!job_id) throw new Error(detail || 'Could not start the download');
      for (;;) {
        await new Promise(r => setTimeout(r, 700));
        const job = await api.archiveJob(job_id);
        box.querySelector('#geo-progress-text').textContent = job.message || '';
        box.querySelector('#geo-progress-fill').style.width = `${job.total ? Math.round(100 * job.done / job.total) : 5}%`;
        if (job.status === 'running') continue;
        if (job.status !== 'completed') throw new Error(job.message || 'Kernel download failed');
        break;
      }
      await showGeometry(box, { dataset_id: ds, product_id: pid });
    } catch (err) {
      toast(err.message, 'bad');
      e.target.disabled = false;
      prog.hidden = true;
    }
  });
}

function render(box) {
  const g = state.data;
  const b = g.straight_line_minus_product_radius;
  box.innerHTML = `
    <div class="geo-head">
      <div class="geo-tabs" role="tablist">
        ${VIEWS.map(([k, l]) => `<button type="button" class="view-subtab-btn ${state.view === k ? 'active' : ''}" data-view="${k}">${l}</button>`).join('')}
      </div>
      <label class="geo-proj" ${state.view === 'map' ? '' : 'hidden'}>Projection
        <select id="geo-projection">${PROJECTIONS.map(([k, l]) => `<option value="${k}" ${state.projection === k ? 'selected' : ''}>${l}</option>`).join('')}</select>
      </label>
    </div>
    <div id="geo-plot" class="geo-plot"></div>
    <div class="diagnostics-bar geo-facts">
      <div class="diag-chip"><strong>UTC (Earth reception):</strong> ${esc(g.utc_range[0])} to ${esc(g.utc_range[1].slice(11))}</div>
      <div class="diag-chip"><strong>One-way light time:</strong> ${(g.light_time_s / 60).toFixed(1)} min</div>
      <div class="diag-chip"><strong>Subsolar point:</strong> ${g.subsolar.lat.toFixed(1)}°, ${g.subsolar.lon.toFixed(1)}°E</div>
      <div class="diag-chip"><strong>Sun-Earth-probe:</strong> ${avg(g.profile.sep_deg).toFixed(1)}°</div>
      <div class="diag-chip"><strong>Tangent track:</strong> ${esc(g.tangent_source)}</div>
      ${b ? `<div class="diag-chip" title="Straight-line tangent radius minus the product's refracted tangent radius; large values mean strong ray bending"><strong>Ray bending:</strong> straight-line offset median ${b.median_km.toFixed(1)} km, max ${b.max_abs_km.toFixed(0)} km</div>` : ''}
    </div>
    <p class="hint">Ephemeris: ${esc(g.ephemeris_source)}; kernels ${esc(g.kernels.join(', '))}. Times are Earth-reception times; positions are light-time corrected.</p>`;
  box.querySelectorAll('[data-view]').forEach(btn => btn.addEventListener('click', () => { state.view = btn.dataset.view; render(box); }));
  box.querySelector('#geo-projection')?.addEventListener('change', (e) => { state.projection = e.target.value; draw(); });
  draw();
}

const avg = (a) => a.reduce((s, v) => s + v, 0) / Math.max(1, a.length);

function draw() {
  const div = document.getElementById('geo-plot');
  if (!div || !window.Plotly || !state.data) return;
  ({ 'orbit-fixed': () => orbit3d(div, 'fixed'), 'orbit-inertial': () => orbit3d(div, 'j2000'), earth: () => earthView(div),
    map: () => trackMap(div), angles: () => angles(div) })[state.view]();
}

function sphere(R, sunDir, n = 40) {
  const x = [], y = [], z = [], c = [];
  for (let i = 0; i <= n; i++) {
    const th = Math.PI * i / n;
    const rx = [], ry = [], rz = [], rc = [];
    for (let j = 0; j <= 2 * n; j++) {
      const ph = Math.PI * j / n;
      const ux = Math.sin(th) * Math.cos(ph), uy = Math.sin(th) * Math.sin(ph), uz = Math.cos(th);
      rx.push(R * ux); ry.push(R * uy); rz.push(R * uz);
      rc.push(ux * sunDir[0] + uy * sunDir[1] + uz * sunDir[2] > 0 ? 1 : 0);
    }
    x.push(rx); y.push(ry); z.push(rz); c.push(rc);
  }
  return { type: 'surface', x, y, z, surfacecolor: c, cmin: 0, cmax: 1, showscale: false, hoverinfo: 'skip',
    colorscale: [[0, '#1e293b'], [0.5, '#1e293b'], [0.5, '#e2c08d'], [1, '#e2c08d']], opacity: 1, name: 'Planet (lit side light)' };
}

function arrow(dir, R, color, name) {
  const L = 2.2 * R;
  return { type: 'scatter3d', mode: 'lines+text', x: [0, dir[0] * L], y: [0, dir[1] * L], z: [0, dir[2] * L],
    line: { color, width: 5 }, text: ['', name], textposition: 'top center', name: `${name} direction`, hoverinfo: 'name' };
}

function orbit3d(div, frame) {
  const g = state.data, R = g.radius_km;
  const orb = frame === 'fixed' ? g.orbit.fixed : g.orbit.j2000;
  const dirs = frame === 'fixed' ? g.directions_fixed : g.directions_j2000;
  const col = (a, i) => a.map(p => p[i]);
  const profSc = frame === 'fixed' ? g.profile.sc_fixed : null;
  const traces = [
    sphere(R, dirs.sun),
    { type: 'scatter3d', mode: 'lines', x: col(orb, 0), y: col(orb, 1), z: col(orb, 2), name: 'Orbit (±90 min)',
      line: { color: paletteColor(0), width: 3 }, text: g.orbit.t_s.map(t => `t = ${(t / 60).toFixed(1)} min`), hoverinfo: 'text' },
    arrow(dirs.earth, R, '#22c55e', 'Earth'),
    arrow(dirs.sun, R, '#f59e0b', 'Sun'),
  ];
  if (profSc) {
    traces.push({ type: 'scatter3d', mode: 'lines', x: col(profSc, 0), y: col(profSc, 1), z: col(profSc, 2),
      name: 'During the profile', line: { color: '#ef4444', width: 9 } });
    const p = g.profile, r = p.tangent_alt_km.map(a => R + Math.max(a, 0));
    const lat = p.tangent_lat.map(v => v * Math.PI / 180), lon = p.tangent_lon.map(v => v * Math.PI / 180);
    traces.push({ type: 'scatter3d', mode: 'markers', name: 'Tangent points',
      x: lat.map((la, i) => r[i] * Math.cos(la) * Math.cos(lon[i])), y: lat.map((la, i) => r[i] * Math.cos(la) * Math.sin(lon[i])),
      z: lat.map((la, i) => r[i] * Math.sin(la)), marker: { size: 2.5, color: '#ef4444' },
      text: p.tangent_alt_km.map(a => `${a.toFixed(1)} km`), hoverinfo: 'text' });
  }
  const ax = (t) => ({ title: { text: t }, showbackground: false, gridcolor: plotColors().grid, zerolinecolor: plotColors().zero });
  const frameName = frame === 'fixed' ? g.frame_fixed : 'J2000';
  window.Plotly.newPlot(div, traces, themedLayout({
    title: { text: `${g.body_name}: spacecraft orbit around the occultation (${frameName}, km)` },
    scene: { aspectmode: 'data', xaxis: ax('x'), yaxis: ax('y'), zaxis: ax('z') },
    legend: { orientation: 'h', y: -0.05 }, margin: { l: 0, r: 0, t: 40, b: 0 },
  }), { responsive: true });
}

function earthView(div) {
  const g = state.data, R = g.radius_km;
  const s = g.sky.sun_dir;                     // unit Sun direction in sky coords (x east, y north, z away from Earth)
  const N = 160, xs = [], z = [];
  for (let i = 0; i < N; i++) xs.push(-R + (2 * R * i) / (N - 1));
  for (const yv of xs) {
    const row = [];
    for (const xv of xs) {
      const r2 = xv * xv + yv * yv;
      if (r2 > R * R) { row.push(null); continue; }
      const zf = -Math.sqrt(R * R - r2);       // visible hemisphere faces Earth (negative depth)
      row.push((xv * s[0] + yv * s[1] + zf * s[2]) / R > 0 ? 1 : 0);
    }
    z.push(row);
  }
  const orb = g.orbit.sky, prof = g.profile.sc_sky;
  const front = orb.map(p => (p[2] < 0 || Math.hypot(p[0], p[1]) > R));
  const traces = [
    { type: 'heatmap', x: xs, y: xs, z, showscale: false, hoverinfo: 'skip', colorscale: [[0, '#1e293b'], [1, '#e2c08d']], name: 'Planet disk' },
    { type: 'scatter', mode: 'lines', name: 'Orbit, visible from Earth', x: orb.map((p, i) => (front[i] ? p[0] : null)),
      y: orb.map((p, i) => (front[i] ? p[1] : null)), line: { color: paletteColor(0), width: 2 } },
    { type: 'scatter', mode: 'lines', name: 'Orbit, hidden behind the planet', x: orb.map((p, i) => (front[i] ? null : p[0])),
      y: orb.map((p, i) => (front[i] ? null : p[1])), line: { color: paletteColor(0), width: 2, dash: 'dot' } },
    { type: 'scatter', mode: 'lines', name: 'During the profile', x: prof.map(p => p[0]), y: prof.map(p => p[1]),
      line: { color: '#ef4444', width: 5 } },
  ];
  window.Plotly.newPlot(div, traces, themedLayout({
    title: { text: `${g.body_name} seen from Earth (sky plane, km; north up, east right)` },
    xaxis: { title: { text: 'East (km)' }, scaleanchor: 'y', zeroline: false },
    yaxis: { title: { text: 'North (km)' }, zeroline: false },
    legend: { orientation: 'h', y: -0.15 }, margin: { l: 70, r: 20, t: 50, b: 90 },
  }), { responsive: true });
}

function terminator(sub) {
  // Points 90 degrees from the subsolar point (great circle).
  const la0 = sub.lat * Math.PI / 180, lo0 = sub.lon * Math.PI / 180, lat = [], lon = [];
  for (let k = 0; k <= 360; k += 3) {
    const az = k * Math.PI / 180, d = Math.PI / 2;
    const la = Math.asin(Math.sin(la0) * Math.cos(d) + Math.cos(la0) * Math.sin(d) * Math.cos(az));
    const lo = lo0 + Math.atan2(Math.sin(az) * Math.sin(d) * Math.cos(la0), Math.cos(d) - Math.sin(la0) * Math.sin(la));
    lat.push(la * 180 / Math.PI); lon.push(((lo * 180 / Math.PI) + 540) % 360 - 180);
  }
  return { lat, lon };
}

function trackMap(div) {
  const g = state.data, p = g.profile;
  const lon = p.tangent_lon.map(v => ((v + 540) % 360) - 180);
  const term = terminator(g.subsolar);
  const proj = state.projection;
  const geo = {
    showland: false, showocean: false, showcoastlines: false, showcountries: false, showlakes: false, showrivers: false,
    bgcolor: 'rgba(0,0,0,0)', showframe: true, framecolor: plotColors().zero,
    lataxis: { showgrid: true, gridcolor: plotColors().grid, dtick: 15 }, lonaxis: { showgrid: true, gridcolor: plotColors().grid, dtick: 30 },
    projection: proj === 'north' ? { type: 'stereographic', rotation: { lat: 90 } }
      : proj === 'south' ? { type: 'stereographic', rotation: { lat: -90 } }
      : proj === 'orthographic' ? { type: 'orthographic', rotation: { lat: avg(p.tangent_lat), lon: avg(lon) } }
      : { type: 'equirectangular' },
  };
  const traces = [
    { type: 'scattergeo', mode: 'lines', lat: term.lat, lon: term.lon, name: 'Terminator', line: { color: '#f59e0b', width: 2, dash: 'dash' } },
    { type: 'scattergeo', mode: 'markers', lat: [g.subsolar.lat], lon: [((g.subsolar.lon + 540) % 360) - 180],
      name: 'Subsolar point', marker: { size: 12, color: '#f59e0b', symbol: 'star' } },
    { type: 'scattergeo', mode: 'markers', lat: [g.subearth.lat], lon: [((g.subearth.lon + 540) % 360) - 180],
      name: 'Sub-Earth point', marker: { size: 10, color: '#22c55e', symbol: 'diamond' } },
    { type: 'scattergeo', mode: 'lines+markers', lat: p.tangent_lat, lon, name: 'Tangent-point track',
      line: { color: '#ef4444', width: 3 }, marker: { size: 4, color: p.tangent_alt_km, colorscale: 'Viridis', showscale: true,
        colorbar: { title: { text: 'Altitude (km)' }, thickness: 12, len: 0.6 } },
      text: p.tangent_alt_km.map((a, i) => `${a.toFixed(1)} km, SZA ${p.sza[i].toFixed(1)}°, LST ${p.lst_h[i].toFixed(2)} h`), hoverinfo: 'text' },
  ];
  window.Plotly.newPlot(div, traces, themedLayout({
    title: { text: `${g.body_name}: tangent-point track (planetocentric, east longitude)` },
    geo, legend: { orientation: 'h', y: -0.05 }, margin: { l: 10, r: 10, t: 50, b: 40 },
  }), { responsive: true });
}

function angles(div) {
  const p = state.data.profile;
  const y = p.tangent_alt_km;
  const tr = (x, name, i, xa) => ({ type: 'scatter', mode: 'lines', x, y, name, xaxis: xa, yaxis: 'y', line: { color: paletteColor(i), width: plotStyle.lineWidth } });
  window.Plotly.newPlot(div, [
    tr(p.sza, 'Solar zenith angle (°)', 0, 'x'), tr(p.lst_h, 'Local solar time (h)', 1, 'x2'), tr(p.sep_deg, 'Sun-Earth-probe (°)', 2, 'x3'),
  ], themedLayout({
    title: { text: 'Solar geometry along the profile' },
    xaxis: { domain: [0, 0.3], title: { text: 'SZA (°)' } },
    xaxis2: { domain: [0.35, 0.65], title: { text: 'Local solar time (h)' }, anchor: 'y' },
    xaxis3: { domain: [0.7, 1], title: { text: 'Sun-Earth-probe (°)' }, anchor: 'y' },
    yaxis: { title: { text: 'Tangent altitude (km)' } },
    showlegend: false, margin: { l: 70, r: 20, t: 50, b: 60 },
  }), { responsive: true });
}
