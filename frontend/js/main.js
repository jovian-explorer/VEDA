/**
 * VEDA: Visualization, Exploration, and Data Analysis
 * Main Application Shell and Orchestrator
 */
import { api, state } from './api.js';
import { $, $$, el, banner, toast, drawer, closeDrawer } from './ui.js';
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
    btnHelp.addEventListener('click', () => drawer('Planetary Science Guide', helpBody()));
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
    
    <h4>2. Physical Diagnostics and Equations</h4>
    <ul>
      <li>
        <strong>Hydrostatic Balance and Ideal Gas State:</strong>
        <p>$$\\frac{dP}{dz} = -\\rho(z) g(z), \\quad P(z) = \\rho(z) R_{spec} T(z)$$</p>
        where specific gas constant $R_{spec} = R_{univ} / \\mu$ and altitude-dependent gravity is $g(z) = g_0 (R_p / (R_p + z))^2$.
      </li>
      <li>
        <strong>Poisson Potential Temperature ($\\theta$):</strong>
        <p>$$\\theta(z) = T(z) \\left(\\frac{P_0}{P(z)}\\right)^{\\frac{R_{spec}}{C_p}}$$</p>
        where $P_0$ is the target reference pressure level and $C_p$ is isobaric heat capacity.
      </li>
      <li>
        <strong>Brunt-Vaisala Static Stability Frequency ($N^2$):</strong>
        <p>$$N^2(z) = \\frac{g(z)}{T(z)}\\left(\\frac{dT}{dz} + \\Gamma_d\\right) = \\frac{g(z)}{\\theta(z)}\\frac{d\\theta}{dz}$$</p>
        where dry adiabatic lapse rate $\\Gamma_d = g(z) / C_p$. Negative $N^2$ values identify dynamically unstable convective regions, whereas positive values represent buoyant oscillatory stability.
      </li>
      <li>
        <strong>Gravity Wave Potential Energy ($E_p$):</strong>
        <p>$$E_p(z) = \\frac{1}{2}\\left(\\frac{g(z)}{N(z)}\\right)^2 \\overline{\\left(\\frac{T'(z)}{\\overline{T}(z)}\\right)^2}$$</p>
        evaluated via vertical background-detrending to quantify atmospheric gravity wave breaking and momentum deposition.
      </li>
      <li>
        <strong>Radio Occultation Abel Inversion:</strong>
        <p>$$\\mu(r) - 1 = \\frac{1}{\\pi} \\int_r^{r_{top}} \\frac{\\alpha(a)}{\\sqrt{a^2 - r^2}}\\,da$$</p>
        retrieving neutral atmospheric refractive index $\\mu(r)$ and ionospheric electron density $N_e(r)$ from spacecraft radio Doppler shifts.
      </li>
      <li>
        <strong>1D Photometric Line Transects:</strong>
        <p>Real-time cross-section slicing across calibrated scientific FITS images $(x_0, y_0) \\to (x_1, y_1)$ with dynamic percentile and ZScale stretch algorithms.</p>
      </li>
    </ul>

    <h4>3. Remote Archives</h4>
    <p>Direct live search and streaming acquisition from NASA Planetary Data System (PDS), ESA Planetary Science Archive (PSA), and JAXA DARTS.</p>
  `;
  return container;
}

function aboutBody() {
  return el('div', {},
    el('h2', {}, 'VEDA: Visualization, Exploration, and Data Analysis'),
    el('p', {}, 'VEDA is an advanced, multi-mission planetary science data laboratory built for discovering, downloading, processing, analyzing, visualizing, and comparing scientific observations from robotic planetary spacecraft across the Solar System.'),
    el('h3', {}, 'Primary Missions Supported'),
    el('ul', {},
      el('li', {}, 'Akatsuki (VCO) - Venus Climate Orbiter (JAXA)'),
      el('li', {}, 'Venus Express (VEX) - Atmospheric Orbiter (ESA)'),
      el('li', {}, 'Magellan - Radar & Radio Science Orbiter (NASA)'),
      el('li', {}, 'Pioneer Venus Orbiter (PVO) - Long-term In-situ Sounder (NASA)'),
      el('li', {}, 'BepiColombo - Mercury Planetary & Magnetospheric Orbiters (ESA / JAXA)'),
      el('li', {}, 'MESSENGER - Mercury Surface & Exosphere Orbiter (NASA)'),
      el('li', {}, 'MAVEN - Mars Atmospheric & Volatile Evolution Orbiter (NASA)'),
      el('li', {}, 'Mars Reconnaissance Orbiter (MRO) - Reconnaissance & Climate Sounder (NASA)'),
      el('li', {}, 'Juno - Polar Jovian Orbiter (NASA)'),
      el('li', {}, 'Galileo - Jovian System Orbiter & Probe (NASA)'),
      el('li', {}, 'Cassini-Huygens - Saturn, Ring System & Titan Orbiter (NASA / ESA)'),
      el('li', {}, 'New Horizons - Pluto System & Kuiper Belt Encounter (NASA)'),
      el('li', {}, 'Lunar Reconnaissance Orbiter (LRO) - High-Res Lunar Orbiter (NASA)'),
      el('li', {}, 'Dawn - Vesta & Ceres Protoplanet Orbiter (NASA)'),
      el('li', {}, 'Rosetta - Comet 67P/Churyumov-Gerasimenko Rendezvous & Orbiter (ESA)'),
    ),
    el('h3', {}, 'Scientific Analysis Engine'),
    el('p', {}, 'Features authoritative celestial body parameters, adiabatic lapse rates, Brunt-Vaisala buoyancy frequency squared ($N^2$), gravity wave potential energy ($E_p$), interactive FITS raster visualization with live 1D photometric line transects, and publication-ready 300-DPI figure generation.'),
    el('hr'),
    el('h3', {}, 'Lead Researcher & Developer'),
    el('p', {}, el('strong', {}, 'Keshav Aggarwal')),
    el('p', {}, 'Research Associate, Space Physics Laboratory (SPL), Vikram Sarabhai Space Centre (VSSC), Indian Space Research Organisation (ISRO), Thiruvananthapuram, Kerala, India.'),
    el('p', {}, 'Former Prime Minister\'s Research Fellow (PMRF Scholar), Department of Astronomy, Astrophysics and Space Engineering (DAASE), Indian Institute of Technology (IIT) Indore.'),
    el('p', {}, 'Research Specialization: Planetary Radio Occultation, Space Physics, Solar Wind Velocity and Turbulence, Coronal Electron Density, and Planetary Atmospheric/Ionospheric Structure.'),
    el('p', {}, el('a', { href: 'https://jovian-explorer.github.io/', target: '_blank', rel: 'noopener' }, '🌐 Visit Researcher Website ↗'))
  );
}

async function boot() {
  // Wire chrome and event listeners immediately
  wireChrome();

  try {
    state.meta = await api.meta();
    if (state.meta && state.meta.app) {
      $('#version-tag').textContent = `v${state.meta.app.version}`;
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
}

boot();
