/**
 * VEDA — Visualization, Exploration, and Data Analysis
 * Main Application Shell and Orchestrator
 */
import { api, state } from './api.js';
import { $, $$, el, banner, toast, drawer } from './ui.js';
import { initVeda } from './veda_app.js';

function wireChrome() {
  const btnBody = $('#btn-mode-body');
  const btnMission = $('#btn-mode-mission');
  const vBody = $('#veda-view-body');
  const vMission = $('#veda-view-mission');

  if (btnBody && btnMission) {
    btnBody.addEventListener('click', () => {
      btnBody.classList.add('active');
      btnMission.classList.remove('active');
      if (vBody) vBody.style.display = 'block';
      if (vMission) vMission.style.display = 'none';
      window.dispatchEvent(new Event('resize'));
    });

    btnMission.addEventListener('click', () => {
      btnMission.classList.add('active');
      btnBody.classList.remove('active');
      if (vBody) vBody.style.display = 'none';
      if (vMission) vMission.style.display = 'block';
      window.dispatchEvent(new Event('resize'));
    });
  }

  $('#btn-settings').addEventListener('click', () => drawer('Settings', settingsBody()));
  $('#btn-about').addEventListener('click', () => drawer('About VEDA', aboutBody()));
  $('#btn-help').addEventListener('click', () => drawer('Planetary Science Guide', helpBody()));
  $('#drawer-close').addEventListener('click', () => $('#drawer').classList.add('hidden'));

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') $('#drawer').classList.add('hidden');
  });

  if (state.meta && state.meta.settings) {
    applySettings(state.meta.settings);
  }
}

function applySettings(settings) {
  if (settings.ui_theme) {
    document.documentElement.dataset.theme = settings.ui_theme;
  }
  if (settings.ui_font_size) {
    document.documentElement.style.setProperty('--ui-font-size', `${settings.ui_font_size}px`);
  }
}

function settingsBody() {
  const container = el('div', { class: 'stack' });
  const curSettings = (state.meta && state.meta.settings) || {};

  const form = el('form', {
    onsubmit: async (e) => {
      e.preventDefault();
      const patch = {
        ui_theme: $('#s-theme').value,
        ui_font_size: parseInt($('#s-font').value, 10),
        ui_mode: $('#s-mode').value,
        plot_theme: $('#s-plot-theme').value,
        plot_dpi: parseInt($('#s-plot-dpi').value, 10),
        units_temperature: $('#s-units-temp').value,
      };
      try {
        const updated = await api.saveSettings(patch);
        if (state.meta) state.meta.settings = updated;
        applySettings(updated);
        toast('Settings saved');
      } catch (err) {
        toast('Error saving settings: ' + err, 'bad');
      }
    }
  });

  form.append(
    el('label', {}, 'Interface Theme ',
      el('select', { id: 's-theme' },
        el('option', { value: 'dark', selected: curSettings.ui_theme !== 'light' }, 'Dark / Deep Space'),
        el('option', { value: 'light', selected: curSettings.ui_theme === 'light' }, 'Light / Day')
      )
    ),
    el('label', {}, 'Font Size (px) ',
      el('input', { type: 'number', id: 's-font', value: curSettings.ui_font_size || 14, min: 10, max: 24 })
    ),
    el('label', {}, 'Interface Mode ',
      el('select', { id: 's-mode' },
        el('option', { value: 'research', selected: curSettings.ui_mode !== 'educational' }, 'Research (Scientific Workstation)'),
        el('option', { value: 'educational', selected: curSettings.ui_mode === 'educational' }, 'Educational (Extended Guidance)')
      )
    ),
    el('hr'),
    el('h3', {}, 'Visualization Defaults'),
    el('label', {}, 'Plot Theme ',
      el('select', { id: 's-plot-theme' },
        el('option', { value: 'dark', selected: curSettings.plot_theme !== 'light' }, 'Deep Space (Dark)'),
        el('option', { value: 'light', selected: curSettings.plot_theme === 'light' }, 'Publication Clean (Light)')
      )
    ),
    el('label', {}, 'Publication Plot DPI ',
      el('input', { type: 'number', id: 's-plot-dpi', value: curSettings.plot_dpi || 300, min: 72, max: 1200, step: 50 })
    ),
    el('label', {}, 'Temperature Units ',
      el('select', { id: 's-units-temp' },
        el('option', { value: 'K', selected: curSettings.units_temperature !== 'C' }, 'Kelvin (K)'),
        el('option', { value: 'C', selected: curSettings.units_temperature === 'C' }, 'Celsius (°C)')
      )
    ),
    el('hr'),
    el('button', { class: 'primary', type: 'submit' }, 'Save Settings')
  );

  container.append(form);
  return container;
}

function helpBody() {
  const container = el('div', { class: 'stack' });
  container.innerHTML = `
    <h3>VEDA Planetary Science Handbook</h3>
    <h4>1. Exploration Modes</h4>
    <p><strong>🪐 By Celestial Body:</strong> Select any non-Earth target in our Solar System (Venus, Mars, Jupiter, Saturn, Titan, Pluto, Mercury, Moon, Ceres, Vesta, Comet 67P) to discover and simultaneously compare observations from all spacecraft that investigated it.</p>
    <p><strong>🛰️ By Planetary Mission:</strong> Delve into specific orbiter and flyby encounter data products across 15 premier robotic missions (Akatsuki, Cassini, New Horizons, Juno, MAVEN, BepiColombo, Venus Express, Galileo, MESSENGER, Magellan, Pioneer Venus, MRO, LRO, Dawn, Rosetta).</p>
    
    <h4>2. Physical Diagnostics</h4>
    <ul>
      <li><strong>Brunt-Väisälä Static Stability ($N^2$):</strong> Computed as $N^2 = \frac{g}{T}\left(\frac{dT}{dz} + \Gamma_d\right)$ where dry adiabatic lapse rate $\Gamma_d = g / C_p$. Negative values identify dynamically unstable convective regions.</li>
      <li><strong>Gravity Wave Potential Energy ($E_p$):</strong> Evaluated via vertical background-detrending and $E_p = \frac{1}{2}\left(\frac{g}{N}\right)^2 \overline{\left(\frac{T'}{\overline{T}}\right)^2}$, identifying atmospheric wave breaking and momentum deposition.</li>
      <li><strong>1D Photometric Transects:</strong> Real-time cross-section profile slicing on calibrated scientific FITS images.</li>
    </ul>

    <h4>3. Remote Archives</h4>
    <p>Direct live search and streaming acquisition from NASA Planetary Data System (PDS), ESA Planetary Science Archive (PSA), and JAXA DARTS.</p>
  `;
  return container;
}

function aboutBody() {
  return el('div', {},
    el('h2', {}, 'VEDA — Visualization, Exploration, and Data Analysis'),
    el('p', {}, 'VEDA is an advanced, multi-mission planetary science data laboratory built for discovering, downloading, processing, analyzing, visualizing, and comparing scientific observations from robotic planetary spacecraft across the Solar System.'),
    el('h3', {}, 'Primary Missions Supported'),
    el('ul', {},
      el('li', {}, 'Akatsuki (VCO) — Venus Climate Orbiter (JAXA)'),
      el('li', {}, 'Venus Express (VEX) — Atmospheric Orbiter (ESA)'),
      el('li', {}, 'Magellan — Radar & Radio Science Orbiter (NASA)'),
      el('li', {}, 'Pioneer Venus Orbiter (PVO) — Long-term In-situ Sounder (NASA)'),
      el('li', {}, 'BepiColombo — Mercury Planetary & Magnetospheric Orbiters (ESA / JAXA)'),
      el('li', {}, 'MESSENGER — Mercury Surface & Exosphere Orbiter (NASA)'),
      el('li', {}, 'MAVEN — Mars Atmospheric & Volatile Evolution Orbiter (NASA)'),
      el('li', {}, 'Mars Reconnaissance Orbiter (MRO) — Reconnaissance & Climate Sounder (NASA)'),
      el('li', {}, 'Juno — Polar Jovian Orbiter (NASA)'),
      el('li', {}, 'Galileo — Jovian System Orbiter & Probe (NASA)'),
      el('li', {}, 'Cassini-Huygens — Saturn, Ring System & Titan Orbiter (NASA / ESA)'),
      el('li', {}, 'New Horizons — Pluto System & Kuiper Belt Encounter (NASA)'),
      el('li', {}, 'Lunar Reconnaissance Orbiter (LRO) — High-Res Lunar Orbiter (NASA)'),
      el('li', {}, 'Dawn — Vesta & Ceres Protoplanet Orbiter (NASA)'),
      el('li', {}, 'Rosetta — Comet 67P/Churyumov–Gerasimenko Rendezvous & Orbiter (ESA)'),
    ),
    el('h3', {}, 'Scientific Analysis Engine'),
    el('p', {}, 'Features authoritative celestial body parameters, adiabatic lapse rates, Brunt-Väisälä buoyancy frequency squared ($N^2$), gravity wave potential energy ($E_p$), interactive FITS raster visualization with live 1D photometric line transects, and publication-ready 300-DPI figure generation.'),
    el('hr'),
    el('h3', {}, 'Author Information'),
    el('p', {}, 'Developed by Keshav Aggarwal, Ph.D. Scholar at the Department of Astronomy, Astrophysics and Space Engineering (DAASE), IIT Indore, working under Prof. Abhirup Datta.'),
    el('p', {}, 'Research Focus: Planetary Radio Occultation, Space Physics, and Multi-Mission Data Systems.'),
    el('p', {}, el('a', { href: 'https://jovian-explorer.github.io/', target: '_blank' }, 'Visit Researcher Website'))
  );
}

async function boot() {
  try {
    state.meta = await api.meta();
  } catch (err) {
    banner(`Could not reach the backend: ${err.message}`, 'bad');
    return;
  }
  if (state.meta && state.meta.app) {
    $('#version-tag').textContent = `v${state.meta.app.version}`;
    document.title = `${state.meta.app.title} ${state.meta.app.version}`;
  }

  wireChrome();
  await initVeda();
}

boot();
