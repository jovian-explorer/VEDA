import {api, state} from './api.js';
import {$, $$, el, banner, toast, drawer} from './ui.js';
import {initGetTab, initExploreTab, refreshLocal, refreshFacets,
        runSearch} from './tabs_data.js';
import {initProfileTab, initCompositeTab, initExportTab} from './tabs_science.js';
import {initVeda} from './veda_app.js';

function showTab(name) {
  $$('.tab').forEach((t) => t.classList.toggle('active', t.dataset.tab === name));
  $$('.panel').forEach((p) => p.classList.toggle('active', p.id === `tab-${name}`));
  // Plotly needs a resize once its container becomes visible.
  window.dispatchEvent(new Event('resize'));
}

function wireChrome() {
  $$('.tab').forEach((t) =>
      t.addEventListener('click', () => showTab(t.dataset.tab)));
  document.addEventListener('goto-profile', () => showTab('profile'));

  const btnBody = $('#btn-mode-body');
  const btnMission = $('#btn-mode-mission');
  const btnEarth = $('#btn-mode-earth');
  const vBody = $('#veda-view-body');
  const vMission = $('#veda-view-mission');
  const vEarth = $('#veda-view-earth');

  if (btnEarth) {
    btnEarth.addEventListener('click', () => {
      [btnBody, btnMission, btnEarth].forEach(b => b && b.classList.remove('active'));
      btnEarth.classList.add('active');
      if (vBody) vBody.style.display = 'none';
      if (vMission) vMission.style.display = 'none';
      if (vEarth) vEarth.style.display = 'block';
      window.dispatchEvent(new Event('resize'));
    });
  }
  if (btnBody) {
    btnBody.addEventListener('click', () => {
      if (btnEarth) btnEarth.classList.remove('active');
      if (vEarth) vEarth.style.display = 'none';
      window.dispatchEvent(new Event('resize'));
    });
  }
  if (btnMission) {
    btnMission.addEventListener('click', () => {
      if (btnEarth) btnEarth.classList.remove('active');
      if (vEarth) vEarth.style.display = 'none';
      window.dispatchEvent(new Event('resize'));
    });
  }

  $('#btn-settings').addEventListener('click', () => drawer('Settings', settingsBody()));
  $('#btn-about').addEventListener('click', () => drawer('About', aboutBody()));
  $('#btn-help').addEventListener('click', () => drawer('Help', helpBody()));
  $('#drawer-close').addEventListener('click', () =>
      $('#drawer').classList.add('hidden'));
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') $('#drawer').classList.add('hidden');
  });

  applySettings(state.meta.settings);
}

function applySettings(settings) {
  if (settings.ui_theme) {
    document.documentElement.dataset.theme = settings.ui_theme;
  }
  if (settings.ui_font_size) {
    document.documentElement.style.setProperty('--ui-font-size', `${settings.ui_font_size}px`);
  }
  if (settings.ui_mode) {
    document.body.classList.toggle('no-curious', settings.ui_mode === 'research');
  } else if (settings.explain_mode !== undefined) {
    document.body.classList.toggle('no-curious', !settings.explain_mode);
  }
}

function settingsBody() {
  const container = el('div', {class: 'stack'});
  
  const form = el('form', {onsubmit: async (e) => {
    e.preventDefault();
    const patch = {
      ui_theme: $('#s-theme').value,
      ui_font_size: parseInt($('#s-font').value, 10),
      ui_mode: $('#s-mode').value,
      plot_theme: $('#s-plot-theme').value,
      plot_dpi: parseInt($('#s-plot-dpi').value, 10),
      units_temperature: $('#s-units-temp').value,
      qc_require_good: $('#s-qc').checked,
      default_stream: $('#s-stream').value
    };
    try {
      const updated = await api.saveSettings(patch);
      state.meta.settings = updated;
      applySettings(updated);
      toast('Settings saved');
    } catch (err) {
      toast('Error saving settings: ' + err, 'bad');
    }
  }});

  form.append(
    el('label', {}, 'Interface Theme ',
      el('select', {id: 's-theme'},
        el('option', {value: 'light', selected: state.meta.settings.ui_theme === 'light'}, 'Light / Day'),
        el('option', {value: 'dark', selected: state.meta.settings.ui_theme === 'dark'}, 'Dark / Night')
      )
    ),
    el('label', {}, 'Font Size (px) ',
      el('input', {type: 'number', id: 's-font', value: state.meta.settings.ui_font_size || 14, min: 10, max: 24})
    ),
    el('label', {}, 'Interface Mode ',
      el('select', {id: 's-mode'},
        el('option', {value: 'educational', selected: state.meta.settings.ui_mode !== 'research'}, 'Educational (More explanations)'),
        el('option', {value: 'research', selected: state.meta.settings.ui_mode === 'research'}, 'Research (Compact interface)')
      )
    ),
    el('hr'),
    el('h3', {}, 'Plot Appearance'),
    el('label', {}, 'Plot Theme ',
      el('select', {id: 's-plot-theme'},
        el('option', {value: 'light', selected: state.meta.settings.plot_theme === 'light'}, 'Light'),
        el('option', {value: 'dark', selected: state.meta.settings.plot_theme === 'dark'}, 'Dark')
      )
    ),
    el('label', {}, 'Plot DPI (Export) ',
      el('input', {type: 'number', id: 's-plot-dpi', value: state.meta.settings.plot_dpi || 300, min: 72, max: 1200, step: 10})
    ),
    el('hr'),
    el('h3', {}, 'Science Defaults'),
    el('label', {}, 'Default Stream ',
      el('select', {id: 's-stream'},
        el('option', {value: 'nrt', selected: state.meta.settings.default_stream === 'nrt'}, 'Near Real-Time (nrt)'),
        el('option', {value: 'postcal', selected: state.meta.settings.default_stream === 'postcal'}, 'Post-Processed (postcal)')
      )
    ),
    el('label', {}, 'Temperature Units ',
      el('select', {id: 's-units-temp'},
        el('option', {value: 'C', selected: state.meta.settings.units_temperature === 'C'}, 'Celsius (°C)'),
        el('option', {value: 'K', selected: state.meta.settings.units_temperature === 'K'}, 'Kelvin (K)')
      )
    ),
    el('label', {class: 'check'},
      el('input', {type: 'checkbox', id: 's-qc', checked: state.meta.settings.qc_require_good}),
      ' Require Good QC by default'
    ),
    el('hr'),
    el('button', {class: 'primary', type: 'submit'}, 'Save Settings')
  );

  container.append(form);
  return container;
}

function helpBody() {
  const container = el('div', {class: 'stack'});
  container.innerHTML = '<p>Loading guidebook...</p>';
  fetch('/help.html')
    .then(r => r.text())
    .then(html => {
      container.innerHTML = html;
    })
    .catch(err => {
      container.innerHTML = `<p class="error">Failed to load help: ${err}</p>`;
    });
  return container;
}

function aboutBody() {
  return el('div', {},
    el('h2', {}, 'About COSMIC-2 Explorer'),
    el('h3', {}, '1. About COSMIC-2'),
    el('p', {}, 'The Constellation Observing System for Meteorology, Ionosphere, and Climate (COSMIC-2) is a six-satellite constellation providing high-resolution radio occultation profiles of Earth\'s atmosphere, especially over the tropics and subtropics.'),
    el('h3', {}, '2. About COSMIC-2 Data'),
    el('p', {}, 'COSMIC-2 GNSS Radio Occultation data provides critical vertical profiles of temperature, pressure, water vapor, and electron density. These soundings are uniquely capable of penetrating thick cloud cover with high vertical resolution.'),
    el('h3', {}, '3. About COSMIC-2 Explorer'),
    el('p', {}, 'COSMIC-2 Explorer is an interactive desktop software tool that simplifies the downloading, processing, and visualization of COSMIC-2 soundings.'),
    el('h3', {}, '4. Purpose and Intended Use'),
    el('p', {}, 'The purpose of this software is to bridge the gap between complex NetCDF/HDF archive data and intuitive, rigorous visualization, making atmospheric profiles accessible without writing custom parsers.'),
    el('h3', {}, '5. Scientific Use Cases'),
    el('p', {}, 'Researchers use this tool to discover planetary boundary layer heights, analyze gravity wave potential energy, inspect topside ionosphere anomalies, and compute exact data provenance for reproducibility.'),
    el('h3', {}, '6. Educational Use Cases'),
    el('p', {}, 'Undergraduate and graduate students can utilize the Educational mode to interactively understand the differences between dry/wet refractivity, trace signal propagation, and learn the physics behind atmospheric profiles.'),
    el('h3', {}, '7. Development Information'),
    el('p', {}, 'Developed as an extensible Python backend with a reactive JavaScript frontend. It is packaged via PyInstaller to run natively without requiring a Python environment.'),
    el('hr'),
    el('h3', {}, '8. Author Information'),
    el('p', {}, 'Keshav Aggarwal is a Ph.D. student at the Department of Astronomy, Astrophysics and Space Engineering (DAASE), IIT Indore, working under Prof. Abhirup Datta.'),
    el('p', {}, 'Research interests include solar/planetary radio occultation and related space/atmospheric science.'),
    el('p', {}, el('a', {href: 'https://jovian-explorer.github.io/', target: '_blank'}, 'Visit Author Website'))
  );
}

async function boot() {
  try {
    state.meta = await api.meta();
  } catch (err) {
    banner(`Could not reach the backend: ${err.message}`, 'bad');
    return;
  }
  $('#version-tag').textContent = `v${state.meta.app.version}`;
  document.title = `${state.meta.app.title} ${state.meta.app.version}`;

  wireChrome();
  await initVeda();
  initGetTab();
  initExploreTab();
  initProfileTab();
  initCompositeTab();
  initExportTab();

  await refreshFacets();
  const summary = await api.localSummary().catch(() => null);
  if (summary && summary.n_granules) {
    await runSearch().catch(() => {});
  } else {
    banner('No profiles on this computer yet. Pick a date and fetch some on the ' +
           '"Get data" tab, or load the bundled examples to try things out.');
  }
  if (summary && summary.cache_quota_bytes &&
      summary.cache_bytes_on_disk > 0.9 * summary.cache_quota_bytes) {
    banner('The local cache is nearly at its quota. Delete a dataset or raise ' +
           'the quota before downloading more.', 'bad');
  }
}

boot();
