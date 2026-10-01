/**
 * VEDA: Visualization, Exploration, and Data Analysis
 * Main Application Shell and Orchestrator
 */
import { api, state } from './api.js';
import { $, $$, el, banner, toast, drawer, closeDrawer, renderMath, updatePlotlyFonts, rethemePlots } from './ui.js';
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

  const btnDataPolicy = $('#btn-veda-data-policy');
  if (btnDataPolicy) {
    btnDataPolicy.addEventListener('click', () => drawer('Planetary Data Portals, Availability & Licenses', dataPolicyBody()));
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

function vedaBibtex() {
  return `@software{Aggarwal_VEDA_${new Date().getFullYear()},
  author    = {Keshav Aggarwal},
  title     = {{VEDA: Visualization, Exploration, and Data Analysis - A Multi-Mission Planetary Science Data Laboratory}},
  year      = {${new Date().getFullYear()}},
  publisher = {Space Physics Laboratory (SPL), Vikram Sarabhai Space Centre (VSSC), ISRO},
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
      field('Download timeout (seconds)',
        el('input', { type: 'number', id: 's-timeout', value: s.network_timeout_s || 30, min: 5, max: 300, required: true }),
        'How long to wait for a slow archive before giving up.')),
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
      <h3>Quick start</h3>
      <ol>
        <li>Pick a planet, moon or comet under <strong>By Celestial Body</strong>.</li>
        <li>Tick the missions to compare and choose a variable (temperature, pressure, density...).</li>
        <li>Read the composite profile and the &plusmn;1&sigma; spread; open any row of the table with <strong>Deep Dive</strong>.</li>
        <li>Export the comparison as CSV, a PNG snapshot, or a publication figure.</li>
      </ol>
    </section>

    <section data-help>
      <h3>Exploring by mission</h3>
      <p><strong>By Planetary Mission</strong> lists each spacecraft's observations. Open one to plot a profile or to view an image with stretch, colour map, histogram and line-transect tools. <strong>Remote Archives</strong> searches the official catalogue for that mission and downloads files into the cache.</p>
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
          <p>$$N^2(z) = \\frac{g(z)}{T(z)}\\left(\\frac{dT}{dz} + \\Gamma_d\\right), \\quad \\Gamma_d = g/C_p$$</p>
          Negative $N^2$ marks convectively unstable layers.</li>
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

function aboutBody() {
  const version = appVersion();
  const paths = (state.meta && state.meta.paths) || {};
  const container = el('div', { class: 'stack about-body' });
  container.innerHTML = `
    <div class="about-hero">
      <img src="img/veda_logo.png" alt="" width="56" height="56" />
      <div>
        <h2>VEDA ${version ? `<span class="badge">v${version}</span>` : ''}</h2>
        <p>Visualization, Exploration, and Data Analysis: a multi-mission planetary science laboratory for discovering, processing, comparing and plotting spacecraft observations across the Solar System.</p>
        <p><a href="${REPO_URL}" target="_blank" rel="noopener">Source code &amp; releases</a> &middot;
           <a href="${REPO_URL}/issues" target="_blank" rel="noopener">Report a problem</a> &middot;
           <a href="https://jovian-explorer.github.io/" target="_blank" rel="noopener">Author's website</a></p>
      </div>
    </div>

    <h3>Author</h3>
    <p><strong>Keshav Aggarwal</strong>, Research Associate, Space Physics Laboratory (SPL), Vikram Sarabhai Space Centre (VSSC), ISRO, Thiruvananthapuram, India. Formerly Prime Minister's Research Fellow, DAASE, IIT Indore.</p>

    <h3>Missions</h3>
    <p class="about-missions">${(vedaState.missions || []).map(m => m.name).join(' &middot; ') || 'Akatsuki, Venus Express, Magellan, Pioneer Venus, BepiColombo, MESSENGER, MAVEN, MRO, Juno, Galileo, Cassini-Huygens, New Horizons, LRO, Dawn, Rosetta, Mars Orbiter Mission, Chandrayaan-2'}</p>

    <h3>How to cite</h3>
    <p>Cite both the mission dataset (instrument team and archive DOI) and VEDA:</p>
    <pre class="about-bibtex">${vedaBibtex()}</pre>
    <button type="button" class="ghost small" id="btn-copy-bibtex">Copy citation</button>

    <h3>Data &amp; license</h3>
    <p>VEDA reads public data from NASA PDS, ESA PSA, JAXA DARTS and ISRO ISSDC and does not claim ownership of it; see <strong>Data &amp; Licenses</strong> for each archive's terms. VEDA itself is released under the MIT License. Bundled libraries: KaTeX, Plotly.js, Three.js (MIT); FastAPI, Pydantic (MIT); Uvicorn, NumPy, SciPy, Astropy, PyWebView (BSD-3-Clause); Matplotlib (PSF).</p>

    <h3>This installation</h3>
    <dl class="about-paths">
      <dt>Data folder</dt><dd><code>${paths.data_root || 'unknown'}</code></dd>
      <dt>Settings file</dt><dd><code>${paths.settings_file || 'unknown'}</code></dd>
      <dt>Logs</dt><dd><code>${paths.logs || 'unknown'}</code></dd>
    </dl>
  `;
  container.querySelector('#btn-copy-bibtex').addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(vedaBibtex());
      toast('Citation copied', 'good');
    } catch (_) {
      toast('Could not copy; select the text and copy it manually', 'bad');
    }
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
  const container = el('div', { class: 'stack' });
  const portals = (state.meta && state.meta.data_portals) || [];
  const stmt = (state.meta && state.meta.data_availability) ||
    'The planetary spacecraft observations and radio occultation profiles analyzed in this study were retrieved from international planetary data archives: NASA Planetary Data System (PDS) Atmospheres Node (https://pds-atmospheres.nmsu.edu/), European Space Agency (ESA) Planetary Science Archive (PSA) (https://archives.esac.esa.int/psa/), JAXA Data Archives and Transmission System (DARTS) (https://data.darts.isas.jaxa.jp/), and ISRO Indian Space Science Data Centre (ISSDC / PRADAN) (https://pradan.issdc.gov.in/). Cross-mission calibration, thermodynamic profiling, and comparative analysis were conducted using VEDA (Version ' + appVersion() + '), available open-source at ' + REPO_URL + '.';

  let portalsHtml = '';
  portals.forEach(p => {
    const missions = p.missions ? `<p style="font-size: calc(10px * var(--font-scale, 1.0)); color: var(--text-secondary); margin-top: 4px;"><strong>Supported Missions:</strong> ${p.missions.join(', ')}</p>` : '';
    portalsHtml += `
      <div class="card" style="margin-bottom: 8px; padding: 10px; background: rgba(0,0,0,0.18); border: 1px solid var(--border-color); border-radius: 6px;">
        <div style="display: flex; justify-content: space-between; align-items: baseline;">
          <strong style="font-size: calc(13px * var(--font-scale, 1.0)); color: var(--focal);">${p.name}</strong>
          <span class="badge" style="font-size: calc(10px * var(--font-scale, 1.0));">${p.agency}</span>
        </div>
        <p style="font-size: calc(11px * var(--font-scale, 1.0)); margin: 4px 0; color: var(--text-primary);">${p.description}</p>
        ${missions}
        <div style="margin-top: 6px;">
          <a href="${p.url}" target="_blank" rel="noopener" class="link" style="font-size: calc(11px * var(--font-scale, 1.0)); color: var(--focal);">Official Archive Portal ↗</a>
        </div>
      </div>
    `;
  });

  container.innerHTML = `
    <h2>Authoritative Planetary Data Portals, Availability & Licenses</h2>

    <h3>1. Planetary Data Availability Statement</h3>
    <p style="font-size: calc(12px * var(--font-scale, 1.0)); color: var(--text-secondary);">
      Authors utilizing VEDA for academic peer-reviewed publications are requested to include the following Data Availability Statement:
    </p>
    <blockquote style="background: rgba(0,0,0,0.2); border-left: 4px solid var(--focal); margin: 8px 0; padding: 10px 14px; font-size: calc(12px * var(--font-scale, 1.0)); color: var(--text-secondary); line-height: 1.5;">
      "${stmt}"
    </blockquote>

    <h3 style="margin-top: 16px;">2. Authoritative Planetary Science Data Portals</h3>
    <p style="font-size: calc(12px * var(--font-scale, 1.0)); color: var(--text-secondary); margin-bottom: 8px;">
      Primary international public space agency portals hosting the underlying raw and calibrated science data:
    </p>
    <div style="margin-top: 8px;">
      ${portalsHtml}
    </div>

    <h3 style="margin-top: 16px;">3. Mandatory Dual-Attribution Citations</h3>
    <p style="font-size: calc(12px * var(--font-scale, 1.0)); color: var(--text-secondary); margin-bottom: 8px;">
      In accordance with open science practices, academic publications must cite both the primary spacecraft instrument dataset (via DOI) and the VEDA computational platform:
    </p>
    <pre class="about-bibtex">${vedaBibtex()}</pre>

    <h3 style="margin-top: 16px;">4. Software & Open-Source Licenses</h3>
    <p style="font-size: calc(12px * var(--font-scale, 1.0)); color: var(--text-secondary);">
      VEDA is distributed under the permissive <strong>MIT License</strong>. Copyright (c) 2026 Keshav Aggarwal, Space Physics Laboratory (SPL), Vikram Sarabhai Space Centre (VSSC), ISRO.
    </p>
    <p style="font-size: calc(11px * var(--font-scale, 1.0)); color: var(--text-secondary); margin-top: 6px;">
      Third-party dependencies utilized in VEDA include KaTeX (MIT), Plotly.js (MIT), Three.js (MIT), FastAPI (MIT), Pydantic (MIT), Uvicorn (BSD-3-Clause), NumPy (BSD-3-Clause), SciPy (BSD-3-Clause), Astropy (BSD-3-Clause), Matplotlib (PSF), and PyWebView (BSD-3-Clause).
    </p>

    <h3 style="margin-top: 16px;">5. Lead Researcher and Principal Architect</h3>
    <div class="card" style="padding: 12px; background: rgba(0,0,0,0.18); border: 1px solid var(--border-color); border-radius: 6px;">
      <strong style="font-size: calc(14px * var(--font-scale, 1.0)); color: var(--focal);">Keshav Aggarwal</strong>
      <p style="font-size: calc(12px * var(--font-scale, 1.0)); margin: 4px 0; color: var(--text-secondary);">
        Research Associate, Space Physics Laboratory (SPL), Vikram Sarabhai Space Centre (VSSC), Indian Space Research Organisation (ISRO), Thiruvananthapuram, Kerala, India.
      </p>
      <p style="font-size: calc(11px * var(--font-scale, 1.0)); color: var(--text-secondary); margin-top: 2px;">
        Former Prime Minister's Research Fellow (PMRF Scholar), Department of Astronomy, Astrophysics and Space Engineering (DAASE), Indian Institute of Technology (IIT) Indore.
      </p>
      <p style="font-size: calc(11px * var(--font-scale, 1.0)); color: var(--text-secondary); margin-top: 2px;">
        Research Specialization: Planetary Radio Occultation, Space Physics, Solar Wind Velocity and Turbulence, Coronal Electron Density, and Planetary Atmospheric and Ionospheric Structure.
      </p>
      <div style="margin-top: 6px;">
        <a href="https://jovian-explorer.github.io/" target="_blank" rel="noopener" class="link" style="font-size: calc(11px * var(--font-scale, 1.0)); color: var(--focal);">🌐 Researcher Website ↗</a>
      </div>
    </div>
  `;
  renderMath(container);
  return container;
}

async function boot() {
  // Wire chrome and event listeners immediately
  wireChrome();

  try {
    state.meta = await api.meta();
    if (state.meta && state.meta.app) {
      $('#version-tag').textContent = `v${state.meta.app.version}`;
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
}

boot();
