/**
 * VEDA: Visualization, Exploration, and Data Analysis
 * Main Application Shell and Orchestrator
 */
import { api, state } from './api.js';
import { $, $$, el, banner, toast, drawer, closeDrawer, renderMath, updatePlotlyFonts, rethemePlots, installPlotJanitor } from './ui.js';
import { initVeda, switchMode, vedaState, applyUserPreferences } from './veda_app.js';

const FONT_SCALES = [0.85, 0.92, 1.0, 1.10, 1.20, 1.32, 1.45];
let currentScaleIdx = 2; // Default 1.0 (100%)

export function applyFontScale(scale) {
  const s = Math.min(Math.max(scale, 0.8), 1.6);
  document.documentElement.style.setProperty('--font-scale', s.toFixed(2));
  const basePx = (state && state.meta && state.meta.settings && state.meta.settings.ui_font_size) || 14;
  document.documentElement.style.fontSize = `${(basePx * s).toFixed(1)}px`;
  document.body.style.fontSize = `${(basePx * s).toFixed(1)}px`;
  const disp = $('#font-scale-display');
  if (disp) disp.textContent = `${Math.round(s * 100)}%`;
  try {
    localStorage.setItem('veda_font_scale', s.toString());
  } catch (_) {}
  updatePlotlyFonts();
  setTimeout(() => {
    window.dispatchEvent(new Event('resize'));
    if (window.Plotly && typeof window.Plotly.Plots?.resize === 'function') {
      document.querySelectorAll('.js-plotly-plot').forEach(p => window.Plotly.Plots.resize(p));
    }
    updatePlotlyFonts();
  }, 80);
}

function wireFontScaling() {
  const saved = localStorage.getItem('veda_font_scale');
  if (saved) {
    const val = parseFloat(saved);
    if (!Number.isNaN(val) && val >= 0.8 && val <= 1.6) {
      const closest = FONT_SCALES.reduce((prev, curr) =>
        Math.abs(curr - val) < Math.abs(prev - val) ? curr : prev
      );
      currentScaleIdx = FONT_SCALES.indexOf(closest);
      applyFontScale(closest);
    }
  }

  $('#btn-font-dec')?.addEventListener('click', () => {
    if (currentScaleIdx > 0) {
      currentScaleIdx--;
      applyFontScale(FONT_SCALES[currentScaleIdx]);
    }
  });

  $('#btn-font-inc')?.addEventListener('click', () => {
    if (currentScaleIdx < FONT_SCALES.length - 1) {
      currentScaleIdx++;
      applyFontScale(FONT_SCALES[currentScaleIdx]);
    }
  });

  $('#font-scale-display')?.addEventListener('click', () => {
    currentScaleIdx = 2; // 100%
    applyFontScale(FONT_SCALES[currentScaleIdx]);
  });
}

function wireChrome() {
  wireFontScaling();
  const btnBody = $('#btn-mode-body');
  const btnMission = $('#btn-mode-mission');
  const btnGuide = $('#btn-mode-guide');

  if (btnBody) btnBody.addEventListener('click', () => switchMode('body'));
  if (btnMission) btnMission.addEventListener('click', () => switchMode('mission'));
  if (btnGuide) btnGuide.addEventListener('click', () => switchMode('guide'));

  // Load File button / file input are wired in veda_app.js (setupWorkflowGuideInteractions).

  const btnVars = $('#btn-veda-vars');
  if (btnVars) {
    btnVars.addEventListener('click', () => drawer('Planetary Science Variables & Algorithm Catalog', variablesCatalogBody()));
  }

  $('#btn-cite')?.addEventListener('click', async () => {
    const { citeBody } = await import('./citations.js');
    drawer('What to cite', citeBody());
  });
  const btnDataPolicy = $('#btn-veda-data-policy');
  if (btnDataPolicy) {
    btnDataPolicy.addEventListener('click', () => drawer('Data & Licenses', dataPolicyBody()));
  }

  const btnSettings = $('#btn-settings');
  if (btnSettings) {
    btnSettings.addEventListener('click', () => drawer('Settings', settingsBody()));
  }

  const btnAbout = $('#btn-about');
  if (btnAbout) {
    btnAbout.addEventListener('click', () => drawer('About VEDA', aboutBody()));
  }

  const btnHelp = $('#btn-help');
  if (btnHelp) {
    btnHelp.addEventListener('click', () => drawer('Help', helpBody()));
  }

  const closeBtn = $('#drawer-close');
  if (closeBtn) {
    closeBtn.addEventListener('click', closeDrawer);
  }

  const backdrop = $('#drawer-backdrop');
  if (backdrop) {
    backdrop.addEventListener('click', closeDrawer);
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeDrawer();
  });

  if (state.meta && state.meta.settings) {
    applySettings(state.meta.settings);
  }
}

const REPO_URL = 'https://github.com/jovian-explorer/VEDA';

function appVersion() {
  return (state.meta && state.meta.app && state.meta.app.version) || '';
}

/** "0.2.0 build 42" for published builds, "0.2.0" from source. */
function appBuildLabel() {
  const b = state.meta && state.meta.build;
  return appVersion() + (b && b.build ? ` build ${b.build}` : '');
}

/**
 * Tell the user when a newer build has been published (every tested change to VEDA
 * is published as the latest release).  One check per session; a dismissed build is
 * not announced again.
 */
async function checkForUpdate({ force = false, quiet = true } = {}) {
  let r;
  try { r = await api.updateCheck(force); } catch (err) { if (!quiet) toast(err.message, 'bad'); return null; }
  if (!r.checked) {
    if (!quiet) toast(r.error ? `Could not check for updates: ${r.error}` : 'Update checks are off (Settings > Network)', 'bad');
    return r;
  }
  if (!r.newer) {
    if (!quiet) toast(`VEDA ${appBuildLabel()} is the latest version`, 'good');
    return r;
  }
  let dismissed = '';
  try { dismissed = localStorage.getItem('veda.update.dismissed') || ''; } catch (_) { /* storage blocked */ }
  if (quiet && dismissed === r.latest.tag) return r;
  const b = $('#banner');
  b.className = 'banner update';
  b.replaceChildren(
    el('span', {}, `A newer VEDA is available: ${r.latest.name || r.latest.tag}. `),
    el('a', { href: r.url, target: '_blank', rel: 'noopener' }, 'Download it'),
    el('span', {}, ' (your data, settings and downloads are kept). '),
    el('button', {
      type: 'button', class: 'ghost small',
      onclick: () => {
        try { localStorage.setItem('veda.update.dismissed', r.latest.tag); } catch (_) { /* storage blocked */ }
        b.classList.add('hidden');
      },
    }, 'Dismiss'));
  return r;
}

function vedaBibtex() {
  return `@software{Aggarwal_VEDA_${new Date().getFullYear()},
  author    = {Keshav Aggarwal},
  title     = {{VEDA: Visualization, Exploration, and Data Analysis - A Multi-Mission Planetary Science Data Laboratory}},
  year      = {${new Date().getFullYear()}},
  version   = {${appVersion()}},
  url       = {${REPO_URL}},
  address   = {Thiruvananthapuram, Kerala, India}
}`;
}

// "system" follows the operating system's light/dark preference.
const systemDark = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;

function resolvedTheme(theme) {
  if (theme === 'system') return systemDark && !systemDark.matches ? 'light' : 'dark';
  return theme === 'light' ? 'light' : 'dark';
}

function applySettings(settings) {
  if (!settings) return;
  document.documentElement.dataset.theme = resolvedTheme(settings.ui_theme);
  if (settings.ui_font_size) {
    document.documentElement.style.setProperty('--ui-font-size', `${settings.ui_font_size}px`);
    applyFontScale(FONT_SCALES[currentScaleIdx]);
  }
  rethemePlots();
}

if (systemDark) {
  systemDark.addEventListener('change', () => {
    const s = state.meta && state.meta.settings;
    if (s && s.ui_theme === 'system') applySettings(s);
  });
}

function choice(id, current, options) {
  return el('select', { id },
    ...options.map(([value, label]) => el('option', { value, selected: String(current) === String(value) }, label)));
}

function field(label, control, hint) {
  return el('label', { class: 'settings-field' },
    el('span', { class: 'settings-label' }, label),
    control,
    hint ? el('span', { class: 'hint' }, hint) : null);
}

function settingsBody() {
  const s = (state.meta && state.meta.settings) || {};
  const paths = (state.meta && state.meta.paths) || {};
  const bodies = (vedaState.bodies || []).map(b => [b.id, b.name]);
  const missions = (vedaState.missions || []).map(m => [m.id, m.name]);
  const currentScale = FONT_SCALES[currentScaleIdx];
  const cpuCount = (state.meta && state.meta.system && state.meta.system.cpu_count) || 64;

  const errorBox = el('div', { class: 'settings-error hidden', role: 'alert' });
  const showError = (msg) => {
    errorBox.textContent = msg;
    errorBox.classList.toggle('hidden', !msg);
  };

  const commit = async (request, okMessage) => {
    showError('');
    try {
      const updated = await request();
      if (state.meta) state.meta.settings = updated;
      applySettings(updated);
      applyUserPreferences(updated);
      toast(okMessage, 'good');
      return updated;
    } catch (err) {
      showError(err.message);
      return null;
    }
  };

  const form = el('form', {
    class: 'settings-form',
    onsubmit: async (e) => {
      e.preventDefault();
      const patch = {
        ui_theme: $('#s-theme').value,
        ui_font_size: parseInt($('#s-font').value, 10),
        units_temperature: $('#s-units-temp').value,
        units_pressure: $('#s-units-pres').value,
        plot_dpi: parseInt($('#s-plot-dpi').value, 10),
        network_enabled: $('#s-network').checked,
        network_timeout_s: parseInt($('#s-timeout').value, 10),
        check_updates: $('#s-check-updates').checked,
        spice_auto_download: $('#s-spice-auto').checked,
        spice_auto_limit_mb: parseInt($('#s-spice-limit').value, 10),
        product_confirm_mb: parseInt($('#s-product-limit').value, 10),
        cpu_workers: parseInt($('#s-cpu-workers').value, 10),
        download_workers: parseInt($('#s-download-workers').value, 10),
      };
      if ($('#s-default-body')) patch.default_body = $('#s-default-body').value;
      if ($('#s-default-mission')) patch.default_mission = $('#s-default-mission').value;
      await commit(() => api.saveSettings(patch), 'Settings saved');
    },
  });

  const folderRow = (which, label, path) => el('div', { class: 'settings-folder' },
    el('div', {},
      el('div', { class: 'settings-label' }, label),
      el('code', { class: 'settings-path', title: path || '' }, path || 'unknown')),
    el('button', {
      type: 'button', class: 'ghost small',
      onclick: async () => {
        try { await api.revealFolder(which); } catch (err) { toast(err.message, 'bad'); }
      },
    }, 'Open'));

  form.append(
    errorBox,
    el('fieldset', {},
      el('legend', {}, 'Appearance'),
      field('Theme', choice('s-theme', s.ui_theme || 'dark',
        [['dark', 'Dark'], ['light', 'Light'], ['system', 'Follow system']])),
      field('Base font size (px)',
        el('input', { type: 'number', id: 's-font', value: s.ui_font_size || 14, min: 11, max: 20, required: true }),
        '11 to 20. Use A- / A+ in the toolbar to zoom the whole interface.'),
      field('Interface zoom', el('select', {
        id: 's-font-scale',
        onchange: (e) => {
          const v = parseFloat(e.target.value);
          currentScaleIdx = Math.max(0, FONT_SCALES.indexOf(v));
          applyFontScale(v);
        },
      }, ...FONT_SCALES.map(v => el('option', { value: String(v), selected: v === currentScale }, `${Math.round(v * 100)}%`))),
        'Saved on this computer only.')),
    el('fieldset', {},
      el('legend', {}, 'Units'),
      field('Temperature', choice('s-units-temp', s.units_temperature || 'K', [['K', 'Kelvin (K)'], ['C', 'Celsius (°C)']])),
      field('Pressure', choice('s-units-pres', s.units_pressure || 'hPa', [['hPa', 'Hectopascal (hPa)'], ['bar', 'bar'], ['Pa', 'Pascal (Pa)']]))),
    el('fieldset', {},
      el('legend', {}, 'Start-up'),
      bodies.length ? field('Open on body', choice('s-default-body', s.default_body || 'venus', bodies)) : null,
      missions.length ? field('Default mission', choice('s-default-mission', s.default_mission || 'akatsuki', missions),
        'Used the next time VEDA starts.') : null),
    el('fieldset', {},
      el('legend', {}, 'Figures'),
      field('Publication figure DPI',
        el('input', { type: 'number', id: 's-plot-dpi', value: s.plot_dpi || 300, min: 72, max: 1200, step: 1, required: true }),
        '72 to 1200. Journals usually ask for 300 or 600.')),
    el('fieldset', {},
      el('legend', {}, 'Network'),
      el('label', { class: 'settings-check' },
        el('input', { type: 'checkbox', id: 's-network', checked: s.network_enabled !== false }),
        el('span', {}, 'Allow downloads from online archives (NASA PDS, ESA PSA, JAXA DARTS, ISRO ISSDC)')),
      el('label', { class: 'settings-check' },
        el('input', { type: 'checkbox', id: 's-check-updates', checked: s.check_updates !== false }),
        el('span', {}, 'Tell me when a newer VEDA is published (one request to GitHub at start-up)')),
      field('Download timeout (seconds)',
        el('input', { type: 'number', id: 's-timeout', value: s.network_timeout_s || 30, min: 5, max: 300, required: true }),
        'How long to wait for a slow archive before giving up.'),
      field('Ask before downloading a product file larger than (MB)',
        el('input', { type: 'number', id: 's-product-limit', value: s.product_confirm_mb || 250, min: 10, max: 20000, required: true }),
        'Most products are well under 50 MB; photon lists (Juno UVS) and full cubes can exceed 1 GB.')),
    el('fieldset', {},
      el('legend', {}, 'Performance'),
      field(`CPU worker processes (this computer has ${cpuCount})`,
        el('input', { type: 'number', id: 's-cpu-workers', value: s.cpu_workers || 1, min: 1, max: Math.min(64, cpuCount), required: true }),
        'Used to read and derive many profiles at once (comparisons, batch analysis). 1 runs everything in the main process; '
        + 'more is faster for large comparisons, up to about the number of physical cores. Takes effect on the next comparison.'),
      field('Parallel downloads',
        el('input', { type: 'number', id: 's-download-workers', value: s.download_workers || 4, min: 1, max: 16, required: true }),
        '1 to 16. Archives may throttle many simultaneous connections; 4 is a good default.')),
    el('fieldset', {},
      el('legend', {}, 'Observation geometry (SPICE)'),
      el('label', { class: 'settings-check' },
        el('input', { type: 'checkbox', id: 's-spice-auto', checked: s.spice_auto_download !== false }),
        el('span', {}, 'Download the SPICE kernels for the opened mission and observation automatically')),
      field('Ask first when the kernels are larger than (MB)',
        el('input', { type: 'number', id: 's-spice-limit', value: s.spice_auto_limit_mb || 400, min: 10, max: 5000, required: true }),
        'Generic kernels are about 100 MB; spacecraft ephemerides are 1 to 200 MB. Downloaded kernels are kept and reused.')),
    el('fieldset', {},
      el('legend', {}, 'Data folders'),
      folderRow('data', 'VEDA data', paths.data_root),
      folderRow('cache', 'Downloads & uploads cache', paths.cache),
      folderRow('exports', 'Exports', paths.exports),
      folderRow('logs', 'Logs', paths.logs)),
    el('div', { class: 'settings-actions' },
      el('button', { class: 'primary', type: 'submit' }, 'Save settings'),
      el('button', {
        class: 'ghost', type: 'button',
        onclick: async () => {
          if (!confirm('Reset all settings to their defaults?')) return;
          const updated = await commit(() => api.resetSettings(), 'Settings reset to defaults');
          if (updated) drawer('Settings', settingsBody());
        },
      }, 'Reset to defaults')),
  );

  return el('div', { class: 'stack' }, form);
}

function helpBody() {
  const container = el('div', { class: 'stack help-body' });
  container.innerHTML = `
    <input type="search" id="help-search" class="help-search" placeholder="Search help..." aria-label="Search help" />

    <section data-help>
      <h3>Quick start: find everything observed on a date</h3>
      <ol>
        <li>Pick a planet or moon under <strong>By Celestial Body</strong>.</li>
        <li>In <strong>Find observations of &hellip;</strong> set <em>From</em> and <em>To</em> (or leave them empty for the whole archive) and press <strong>Search all missions</strong>. VEDA reads the official archive indexes of every connected mission for that body the first time (this needs the internet once) and lists every product in the range.</li>
        <li>Press <strong>Open</strong> on a row to download and plot that profile, or tick several rows and press <strong>Compare selected</strong> to overlay them.</li>
        <li><strong>Download selected</strong> keeps the products in the cache so they also work offline.</li>
      </ol>
      <p>Only real archive products are listed. Nothing is simulated: if a mission has no data in your range, it simply does not appear.</p>
    </section>

    <section data-help>
      <h3>Browsing one mission and choosing payloads</h3>
      <p><strong>By Planetary Mission</strong> opens <strong>Archive data</strong> for that spacecraft. The chips at the top are its payloads and data sets (instrument, processing level, archive); tick the ones you want. Filter by date, product type, free text (product id, orbit), <em>Profiles only</em> or <em>Downloaded only</em>, and sort oldest or newest first. Indexing a large data set runs in the background with a progress bar.</p>
      <p><strong>ISRO ISSDC (Mars Orbiter Mission, Chandrayaan-2)</strong> requires a PRADAN account. Press <strong>Sign in to ISRO ISSDC</strong>, download the products on the PRADAN website, then press <strong>Import downloaded files</strong> and select them.</p>
    </section>

    <section data-help>
      <h3>Live data sets (every payload)</h3>
      <p>Chips marked <span class="badge badge-live">live search</span> cover a whole instrument archive that is searched on the server for the dates you give: the ESA PSA for Mars Express, Venus Express, Rosetta, BepiColombo and Huygens, the NASA PDS Registry for MAVEN, Juno, New Horizons, MESSENGER, LRO, Galileo, Magellan, MGS, MRO, Pioneer Venus and Dawn, and OPUS for Cassini, Galileo and New Horizons imaging and spectra. Give <em>From</em> and <em>To</em> dates to include them; up to 5,000 products per data set and window are listed (narrow the dates if VEDA says there are more). Results are remembered for a week.</p>
    </section>

    <section data-help>
      <h3>Viewing any product</h3>
      <p><strong>View</strong> opens anything that is not an atmosphere profile, and <strong>All fields</strong> opens a profile's whole table. Tables: choose the X field and up to 8 Y fields, one plot or one panel per field, log axes; large tables are drawn at a few thousand points keeping every minimum and maximum. Vector fields become spectrograms; tables with a profile in each row (e.g. MRO MCS) can be shown as <em>Profiles (one per row)</em>. Images and maps: stretch, colours, bands, click for the value, two clicks for a transect. Cubes: click a pixel for its spectrum.</p>
    </section>

    <section data-help>
      <h3>What to cite</h3>
      <p><strong>Cite</strong> lists the references for exactly the data sets and features you used on this computer (data sets with the archive identifiers of the products you opened, instrument and mission papers, archive acknowledgements, SPICE if you used geometry, the libraries behind derived quantities and figures, and VEDA), with BibTeX and a data availability statement to copy. <em>Start a new list</em> clears it for a new paper.</p>
    </section>

    <section data-help>
      <h3>Plotting, derived parameters and comparison</h3>
      <p>An opened profile shows every quantity the product contains (temperature, pressure, number or electron density, refractivity, absorptivity, H<sub>2</sub>SO<sub>4</sub>, &hellip;) with the archived &plusmn;1&sigma; uncertainty where the product gives one. VEDA also derives lapse rate, scale height, potential temperature, mass density, Brunt-V&auml;is&auml;l&auml; frequency, gravity-wave perturbations, tropopause and, for ionospheres, the peak and VTEC, using the body's constants. The time, latitude, longitude, solar zenith angle and local time come from the product.</p>
      <p>In a comparison the profiles are put on a common altitude grid with their mean and &plusmn;1&sigma; spread; colour the curves by mission, date or latitude.</p>
    </section>

    <section data-help>
      <h3>Plot style and figure export</h3>
      <p><strong>&#127912; Plot style</strong> sets line width and dash, markers, palette, uncertainty bands or error bars, log or linear axes, swapped axes, grid, ticks, fonts and legend, altitude or pressure as the vertical axis, and journal templates (AGU, Elsevier, A&amp;A, MNRAS). <strong>Export figure</strong> saves PNG (at the DPI you choose) or vector SVG at the journal's single- or double-column width. Your style is remembered on this computer.</p>
    </section>

    <section data-help>
      <h3>Observation geometry (SPICE)</h3>
      <p><strong>&#128752; Geometry</strong> works for every mission with public SPICE kernels (all except the Mars Orbiter Mission and Chandrayaan-2). For radio occultations: <em>Orbit (planet-fixed)</em>, <em>Orbit (inertial J2000)</em>, <em>View from Earth</em>, <em>Tangent-point map</em> (cylindrical, polar or orthographic) and <em>Angles along profile</em>; times are Earth-received and light-time corrected. For any other observation: the orbit, the sub-spacecraft <em>Ground track</em>, and altitude, solar zenith, emission and phase angles and local time over the observation.</p>
      <p>Kernels download by themselves: a mission's generic and body kernels when you open it, the spacecraft ephemeris when you open an observation. <strong>Settings &gt; Observation geometry</strong> turns this off or sets the size above which VEDA asks first. Kernels are kept and reused.</p>
    </section>

    <section data-help>
      <h3>Loading your own files</h3>
      <p>Use <strong>Load File</strong> or drag files onto the window. Supported: PDS3 tables (<code>.lbl</code> + <code>.tab</code>), CSV and plain-text tables (<code>.csv</code>, <code>.txt</code>, <code>.dat</code>, <code>.asc</code>), FITS images (<code>.fit</code>, <code>.fits</code>, <code>.fts</code>) and PNG/JPEG images.</p>
      <p>For a PDS3 product, select the <code>.lbl</code> label <em>and</em> its <code>.tab</code> table together: the label describes the columns. Text tables need an altitude column (ALTITUDE, ALT, HEIGHT, Z or RADIUS); temperature, pressure, electron density and refractivity columns are detected by name. Loaded files appear under the <em>user_imported</em> mission so you can reopen them.</p>
    </section>

    <section data-help>
      <h3>Units and settings</h3>
      <p>The quick unit switcher (K / &deg;C, bar / hPa / Pa) changes the comparison plot straight away. Default units, the start-up body, figure DPI, network access and the theme are in <strong>Settings</strong>.</p>
    </section>

    <section data-help>
      <h3>Keyboard</h3>
      <ul>
        <li><kbd>Esc</kbd> closes this panel.</li>
        <li><kbd>Tab</kbd> / <kbd>Shift</kbd>+<kbd>Tab</kbd> move between controls; <kbd>Enter</kbd> or <kbd>Space</kbd> activates them.</li>
        <li>Plots: drag to zoom, double-click to reset, use the toolbar to pan or save a PNG.</li>
      </ul>
    </section>

    <section data-help>
      <h3>Troubleshooting</h3>
      <dl class="help-faq">
        <dt>"... is a PDS3 label and its data table was not included"</dt>
        <dd>Select the <code>.lbl</code> and <code>.tab</code> files together in the file dialog (Ctrl/Cmd-click) or drop both at once.</dd>
        <dt>"No altitude column found"</dt>
        <dd>The table has no recognisable altitude axis. Rename the column (e.g. <code>altitude</code>) or load the PDS3 label with it.</dd>
        <dt>The comparison plot is empty</dt>
        <dd>None of the ticked missions measured the chosen variable. Pick another variable or tick more missions.</dd>
        <dt>A download fails or times out</dt>
        <dd>Check your internet connection, make sure downloads are allowed in Settings &gt; Network, or raise the timeout. Archives are sometimes offline for maintenance.</dd>
        <dt>The window is blank or does not open</dt>
        <dd>VEDA also runs in your web browser: start it with <code>veda-server</code> and open the address it prints. On Linux the desktop window needs GTK or Qt (see the README).</dd>
        <dt>Where are my files?</dt>
        <dd>Settings &gt; Data folders shows the cache, export and log folders and opens them. The log file helps when reporting a problem.</dd>
      </dl>
      <p>Still stuck? <a href="${REPO_URL}/issues" target="_blank" rel="noopener">Open an issue on GitHub</a> and attach the log file.</p>
    </section>

    <section data-help>
      <h3>The science: diagnostics and equations</h3>
      <ul>
        <li><strong>Hydrostatic balance and ideal gas:</strong>
          <p>$$\\frac{dP}{dz} = -\\rho(z) g(z), \\quad P(z) = \\rho(z) R_{spec} T(z)$$</p>
          with $R_{spec} = R_{univ} / \\mu$ and $g(z) = g_0 (R_p / (R_p + z))^2$.</li>
        <li><strong>Potential temperature ($\\theta$):</strong>
          <p>$$\\theta(z) = T(z) \\left(\\frac{P_0}{P(z)}\\right)^{R_{spec}/C_p}$$</p></li>
        <li><strong>Brunt-V&auml;is&auml;l&auml; frequency ($N^2$):</strong>
          <p>$$N^2(z) = \\frac{g(z)}{T(z)}\\left(\\frac{dT}{dz} + \\Gamma_d\\right), \\quad \\Gamma_d = g/c_p(T)$$</p>
          Negative $N^2$ marks convectively unstable layers. For Venus, Mars, Titan and Pluto $c_p$ depends on temperature (JANAF ideal-gas values of the main gases weighted by composition): about 740 J/(kg K) on Mars at 200 K, 850 to 1140 J/(kg K) from 300 to 735 K on Venus.</li>
        <li><strong>Gravity-wave potential energy:</strong>
          <p>$$E_p(z) = \\frac{1}{2}\\left(\\frac{g}{N}\\right)^2 \\overline{\\left(\\frac{T'}{\\overline{T}}\\right)^2}$$</p></li>
        <li><strong>Radio occultation (Abel inversion):</strong>
          <p>$$\\mu(r) - 1 = \\frac{1}{\\pi} \\int_r^{r_{top}} \\frac{\\alpha(a)}{\\sqrt{a^2 - r^2}}\\,da$$</p></li>
        <li><strong>Vertical total electron content:</strong>
          <p>$$\\text{VTEC} = 10^{-7} \\int N_e(z)\\,dz \\quad [\\text{TECU}]$$</p></li>
      </ul>
      <p>The <strong>Variables</strong> panel lists every variable with its formula, reference and DOI. VEDA does not alter archived values; check derived profiles against the official PDS labels and calibration documents before publishing.</p>
    </section>
  `;
  const search = container.querySelector('#help-search');
  search.addEventListener('input', () => {
    const q = search.value.trim().toLowerCase();
    container.querySelectorAll('[data-help]').forEach(sec => {
      sec.style.display = !q || sec.textContent.toLowerCase().includes(q) ? '' : 'none';
    });
  });
  renderMath(container);
  return container;
}

const escHtml = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function missionName(id) {
  const m = (vedaState.missions || []).find(x => x.id === id);
  return m ? m.name : id.toUpperCase();
}

/** "Mission: payload (level); ..." for every connected archive data set. */
async function fillDatasetSummary(box) {
  if (!box) return;
  try {
    const { datasets = [] } = await api.archiveDatasets();
    const byMission = new Map();
    datasets.forEach(d => byMission.set(d.mission_id, [...(byMission.get(d.mission_id) || []), d]));
    box.innerHTML = [...byMission].map(([m, ds]) =>
      `<strong>${escHtml(missionName(m))}</strong>: ${[...new Set(ds.map(d => `${d.instrument} (${d.level})`))].map(escHtml).join('; ')}`
    ).join('<br>') || 'No archive data set is connected.';
  } catch (err) {
    box.textContent = `Could not list the data sets: ${err.message}`;
  }
}

/** Table of connected data sets with archive, citation and DOI. */
async function fillDatasetTable(box) {
  if (!box) return;
  try {
    const { datasets = [] } = await api.archiveDatasets();
    box.innerHTML = `
      <table class="data-table">
        <thead><tr><th>Mission</th><th>Data set</th><th>Archive</th><th>Cite</th></tr></thead>
        <tbody>${datasets.map(d => `
          <tr>
            <td>${escHtml(missionName(d.mission_id))}</td>
            <td>${escHtml(d.title)}<br><code>${escHtml(d.id)}</code></td>
            <td>${d.base_url ? `<a href="${escHtml(d.base_url)}" target="_blank" rel="noopener">${escHtml(d.archive)}</a>` : escHtml(d.archive)}${d.portal_only ? '<br><span class="badge">account needed</span>' : ''}</td>
            <td>${escHtml(d.citation || 'See the data set documentation')}${d.doi ? `<br><a href="https://doi.org/${escHtml(d.doi)}" target="_blank" rel="noopener">doi:${escHtml(d.doi)}</a>` : ''}</td>
          </tr>`).join('')}
        </tbody>
      </table>`;
  } catch (err) {
    box.textContent = `Could not list the data sets: ${err.message}`;
  }
}

function escAttr(s) {
  return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

function buildLine() {
  const b = state.meta && state.meta.build;
  const parts = b && b.build ? [`Build ${b.build}`, b.date, b.commit && `commit ${b.commit}`].filter(Boolean)
                             : ['Running from source'];
  return `<p class="hint">${escAttr(parts.join(' · '))} &middot; <a href="#" id="about-check-update">Check for updates</a></p>`;
}

function aboutBody() {
  const version = appVersion();
  const paths = (state.meta && state.meta.paths) || {};
  const container = el('div', { class: 'stack about-body' });
  container.innerHTML = `
    <div class="about-hero">
      <img src="img/veda_logo.png" alt="" width="56" height="56" />
      <div>
        <h2>VEDA ${version ? `<span class="badge">v${escAttr(appBuildLabel())}</span>` : ''}</h2>
        ${buildLine()}
        <p>Visualization, Exploration, and Data Analysis: search the official planetary archives by body, mission, payload and date, then plot, derive, compare and export the real spacecraft observations, with SPICE observation geometry.</p>
        <p><a href="${REPO_URL}" target="_blank" rel="noopener">Source code &amp; releases</a> &middot;
           <a href="${REPO_URL}/issues" target="_blank" rel="noopener">Report a problem</a> &middot;
           <a href="https://jovian-explorer.github.io/" target="_blank" rel="noopener">Author's website</a></p>
      </div>
    </div>

    <h3>Author</h3>
    <p><strong>Keshav Aggarwal</strong>, Student visitor at the Space Physics Laboratory (SPL), Vikram Sarabhai Space Centre (VSSC), ISRO, Thiruvananthapuram, India. Formerly Prime Minister's Research Fellow, DAASE, IIT Indore. Research: planetary radio occultation, planetary atmospheres and ionospheres, solar wind and coronal plasma.</p>

    <h3>Connected archive data</h3>
    <p class="about-missions" id="about-datasets">Loading&hellip;</p>

    <h3>How to cite</h3>
    <p>Cite the data set and the instrument team's reference publication (listed in <strong>Data &amp; Licenses</strong>), the archive, and VEDA:</p>
    <pre class="about-bibtex">${vedaBibtex()}</pre>
    <button type="button" class="ghost small" id="btn-copy-bibtex">Copy citation</button>

    <h3>License and terms</h3>
    <p>VEDA is free software under the MIT License and comes with no warranty. The data belong to the mission teams and archives (NASA PDS, ESA PSA, JAXA DARTS, ISRO ISSDC; ephemerides from NASA NAIF); VEDA only downloads and reads them, and your use of them is governed by each archive's terms. Check results against the product documentation before you publish. VEDA sends nothing about you anywhere: it contacts only the archives you search, and only when downloads are allowed in Settings. See <code>TERMS.md</code>, <code>DATA_POLICY.md</code> and <code>THIRD_PARTY_LICENSES.md</code> in the repository.</p>
    <p class="hint">Bundled libraries: Plotly.js, KaTeX (MIT); FastAPI, Pydantic, SpiceyPy (MIT); Uvicorn, NumPy, SciPy, Astropy, PyWebView (BSD-3-Clause); Requests (Apache-2.0); Matplotlib (PSF-based); Pillow (MIT-CMU); NAIF CSPICE (public, see NAIF rules).</p>
    <h3>This installation</h3>
    <dl class="about-paths">
      <dt>Data folder</dt><dd><code>${paths.data_root || 'unknown'}</code></dd>
      <dt>Settings file</dt><dd><code>${paths.settings_file || 'unknown'}</code></dd>
      <dt>Logs</dt><dd><code>${paths.logs || 'unknown'}</code></dd>
    </dl>
  `;
  fillDatasetSummary(container.querySelector('#about-datasets'));
  container.querySelector('#btn-copy-bibtex').addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(vedaBibtex());
      toast('Citation copied', 'good');
    } catch (_) {
      toast('Could not copy; select the text and copy it manually', 'bad');
    }
  });
  container.querySelector('#about-check-update')?.addEventListener('click', (e) => {
    e.preventDefault();
    checkForUpdate({ force: true, quiet: false });
  });
  return container;
}

function variablesCatalogBody() {
  const container = el('div', { class: 'stack' });
  const vars = (state.meta && state.meta.variables) || [];

  let cardsHtml = '';
  vars.forEach(v => {
    const formulaHtml = v.formula ? `<div class="guide-formula-box" style="margin: 6px 0; padding: 6px 10px; background: rgba(0,0,0,0.18); border: 1px solid var(--border-color); border-radius: 4px;">$$${v.formula}$$</div>` : '';
    const doiLink = v.doi ? `<a href="https://doi.org/${v.doi}" target="_blank" rel="noopener" class="link" style="color: var(--accent);">DOI: ${v.doi} ↗</a>` : '';
    const archiveHtml = v.archive ? `<span class="badge" style="font-size: calc(10px * var(--font-scale, 1.0)); padding: 2px 6px; background: rgba(0, 229, 255, 0.12); color: var(--focal);">${v.archive}</span>` : '';
    const refHtml = v.reference ? `<p style="font-size: calc(11px * var(--font-scale, 1.0)); color: var(--text-secondary); margin: 4px 0;"><strong>Reference:</strong> ${v.reference} ${doiLink}</p>` : '';
    const catBadge = v.category ? `<span class="badge" style="font-size: calc(10px * var(--font-scale, 1.0)); padding: 2px 6px; text-transform: uppercase;">${v.category}</span>` : '';

    cardsHtml += `
      <div class="card" style="margin-bottom: 10px; padding: 12px; background: rgba(0,0,0,0.18); border: 1px solid var(--border-color); border-radius: 6px;">
        <div style="display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 6px;">
          <div>
            <strong style="font-size: calc(14px * var(--font-scale, 1.0)); color: var(--focal);">${v.label || v.id}</strong>
            <code style="margin-left: 6px; font-size: calc(11px * var(--font-scale, 1.0)); background: rgba(0,0,0,0.3); padding: 2px 4px; border-radius: 3px;">${v.id}</code>
            ${v.units && v.units !== '-' ? `<span style="margin-left: 6px; font-size: calc(11px * var(--font-scale, 1.0)); color: var(--text-secondary);">[${v.units}]</span>` : ''}
          </div>
          <div style="display: flex; gap: 6px;">${catBadge} ${archiveHtml}</div>
        </div>
        <p style="font-size: calc(12px * var(--font-scale, 1.0)); margin: 6px 0; color: var(--text-primary);">${v.description || ''}</p>
        ${formulaHtml}
        ${refHtml}
      </div>
    `;
  });

  container.innerHTML = `
    <h2>Planetary Science Variables & Algorithm Catalog</h2>
    <p class="hint" style="margin-bottom: 12px;">
      Exhaustive physical formulas, thermodynamic definitions, peer-reviewed citations, DOIs, and space agency archive sources for planetary atmospheric and ionospheric analysis:
    </p>
    <div style="margin-top: 12px;">
      ${cardsHtml}
    </div>
  `;
  renderMath(container);
  return container;
}

function dataPolicyBody() {
  const container = el('div', { class: 'stack policy-body' });
  const portals = (state.meta && state.meta.data_portals) || [];
  const licenses = (state.meta && state.meta.licenses) || {};
  const stmt = (state.meta && state.meta.data_availability) ||
    `The spacecraft observations analysed in this study are publicly available from the NASA Planetary Data System (PDS) Atmospheres Node (https://pds-atmospheres.nmsu.edu/), the ESA Planetary Science Archive (PSA) (https://archives.esac.esa.int/psa/) and the JAXA Data Archives and Transmission System (DARTS) (https://data.darts.isas.jaxa.jp/). Archived values were read, unit-converted and compared with VEDA version ${appVersion()} (${REPO_URL}).`;
  const licenseKey = { nasa_pds_atm: 'nasa_pds', pds_opus: 'nasa_pds', esa_psa: 'esa_psa', jaxa_darts: 'jaxa_darts', research_repositories: 'cc_by_4', isro_issdc: 'isro_issdc', naif_spice: 'naif_spice' };

  const portalsHtml = portals.map(p => {
    const lic = licenses[licenseKey[p.id]];
    const missions = (p.missions || []).map(missionName).join(', ');
    return `
      <div class="policy-card">
        <div class="policy-card-head">
          <a href="${escHtml(p.url)}" target="_blank" rel="noopener"><strong>${escHtml(p.name)}</strong></a>
          <span class="badge">${escHtml(p.agency)}</span>
          ${p.login ? '<span class="badge">account needed</span>' : ''}
        </div>
        <p>${escHtml(p.description)}</p>
        ${missions ? `<p class="hint"><strong>Read by VEDA:</strong> ${escHtml(missions)}</p>` : ''}
        ${lic ? `<p class="hint"><strong>Terms:</strong> ${escHtml(lic.terms)} <a href="${escHtml(lic.url)}" target="_blank" rel="noopener">Details</a></p>` : ''}
      </div>`;
  }).join('');

  container.innerHTML = `
    <p>VEDA does not own, host or modify any of the data it shows. It downloads products from the official archives below to a cache on your computer and reads them there. Each archive's own terms apply to the data; VEDA's MIT License applies only to the software.</p>

    <h3>Archives</h3>
    ${portalsHtml}

    <h3>Data sets and what to cite</h3>
    <p class="hint">Cite the data set (with its DOI where the archive gives one) and the instrument team's reference publication. The list below comes from VEDA's catalogue, so it always matches what this version can search.</p>
    <div id="policy-datasets" class="policy-table">Loading&hellip;</div>

    <h3>Data availability statement</h3>
    <p class="hint">A starting point for your paper; remove archives you did not use and add the data set DOIs.</p>
    <blockquote class="policy-quote" id="policy-statement">${escHtml(stmt)}</blockquote>
    <button type="button" class="ghost small" id="btn-copy-statement">Copy statement</button>

    <h3>Citing VEDA</h3>
    <pre class="about-bibtex">${vedaBibtex()}</pre>

    <h3>Terms of use (summary)</h3>
    <ul>
      <li>VEDA is provided as is, without warranty. Check derived values against the product labels and the instrument team's documentation before you publish them.</li>
      <li>Archived files are never altered. Unit conversions and derived quantities are computed in memory; the downloaded files stay exactly as the archive published them.</li>
      <li>Download what you need: VEDA fetches products one at a time, backs off when an archive is busy, and keeps them in a local cache so the archives are not asked twice.</li>
      <li>VEDA has no accounts, no analytics and no telemetry. It contacts only the archives you search, and only while <em>Allow downloads</em> is on in Settings. Archive passwords are never seen by VEDA: you sign in on the archive's own website.</li>
      <li>VEDA is not affiliated with or endorsed by NASA, ESA, JAXA or ISRO.</li>
    </ul>
    <p class="hint">Full texts: <a href="${REPO_URL}/blob/main/TERMS.md" target="_blank" rel="noopener">TERMS.md</a> &middot; <a href="${REPO_URL}/blob/main/DATA_POLICY.md" target="_blank" rel="noopener">DATA_POLICY.md</a> &middot; <a href="${REPO_URL}/blob/main/LICENSE" target="_blank" rel="noopener">LICENSE</a> &middot; <a href="${REPO_URL}/blob/main/THIRD_PARTY_LICENSES.md" target="_blank" rel="noopener">THIRD_PARTY_LICENSES.md</a></p>

    <h3>Software license</h3>
    <p>VEDA: MIT License, Copyright (c) 2026 Keshav Aggarwal. Third-party components: Plotly.js, KaTeX, FastAPI, Pydantic, SpiceyPy (MIT); Uvicorn, NumPy, SciPy, Astropy, PyWebView (BSD-3-Clause); Requests (Apache-2.0); Matplotlib (PSF-based); Pillow (MIT-CMU); NAIF CSPICE (public).</p>
  `;
  fillDatasetTable(container.querySelector('#policy-datasets'));
  container.querySelector('#btn-copy-statement').addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(stmt);
      toast('Statement copied', 'good');
    } catch (_) {
      toast('Could not copy; select the text and copy it manually', 'bad');
    }
  });
  return container;
}

async function boot() {
  // Wire chrome and event listeners immediately
  wireChrome();
  installPlotJanitor();

  try {
    state.meta = await api.meta();
    if (state.meta && state.meta.app) {
      $('#version-tag').textContent = `v${appBuildLabel()}`;
      document.querySelectorAll('.veda-version').forEach(n => { n.textContent = state.meta.app.version; });
      document.title = `${state.meta.app.title} ${state.meta.app.version}`;
    }
    if (state.meta && state.meta.settings) {
      applySettings(state.meta.settings);
    }
  } catch (err) {
    console.warn('Could not reach backend /api/meta:', err);
    banner(`Could not reach the backend: ${err.message}`, 'bad');
  }

  await initVeda();
  renderMath(document.body);
  setTimeout(() => checkForUpdate(), 4000);   // after start-up, not competing with it
}

boot();
