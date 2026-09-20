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
    
    <h4>1. Exploration Paradigms</h4>
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
        <strong>Vertical Total Electron Content (VTEC):</strong>
        <p>$$\\text{VTEC} = 10^{-7} \\int N_e(z)\\,dz \\quad [\\text{TECU}]$$</p>
        integrating vertical electron density to quantify ionospheric plasma content.
      </li>
      <li>
        <strong>1D Photometric Line Transects:</strong>
        <p>Real-time cross-section slicing across calibrated scientific FITS images $(x_0, y_0) \\to (x_1, y_1)$ with dynamic percentile and ZScale stretch algorithms.</p>
      </li>
    </ul>

    <h4>3. Remote Planetary Data Archives</h4>
    <p>Direct live search and streaming acquisition from NASA Planetary Data System (PDS), ESA Planetary Science Archive (PSA), and JAXA DARTS. Downloads feature chunked transfer, progress tracking, and SHA-256 cryptographic verification.</p>

    <h4>4. Data Provenance and Scientific Validation</h4>
    <p>Researchers utilizing VEDA for publication must verify derived profiles against official PDS3/PDS4 labels and calibration documentation. VEDA performs deterministic mathematical operations and does not alter underlying archived data points.</p>
  `;
  return container;
}

function aboutBody() {
  const container = el('div', { class: 'stack' });
  container.innerHTML = `
    <h2>VEDA: Visualization, Exploration, and Data Analysis</h2>
    <p>VEDA is an open multi-mission planetary science computational platform built for discovering, downloading, processing, analyzing, visualizing, and comparing scientific observations from robotic planetary spacecraft across the Solar System.</p>

    <h3>Primary Missions Supported</h3>
    <ul>
      <li><strong>Akatsuki (VCO)</strong>: Venus Climate Orbiter (JAXA)</li>
      <li><strong>Venus Express (VEX)</strong>: Atmospheric Orbiter (ESA)</li>
      <li><strong>Magellan</strong>: Radar and Radio Science Orbiter (NASA)</li>
      <li><strong>Pioneer Venus Orbiter (PVO)</strong>: Long-term In-situ Sounder (NASA)</li>
      <li><strong>BepiColombo</strong>: Mercury Planetary and Magnetospheric Orbiters (ESA / JAXA)</li>
      <li><strong>MESSENGER</strong>: Mercury Surface and Exosphere Orbiter (NASA)</li>
      <li><strong>MAVEN</strong>: Mars Atmospheric and Volatile Evolution Orbiter (NASA)</li>
      <li><strong>Mars Reconnaissance Orbiter (MRO)</strong>: Climate Sounder and Reconnaissance (NASA)</li>
      <li><strong>Juno</strong>: Polar Jovian Orbiter (NASA)</li>
      <li><strong>Galileo</strong>: Jovian System Orbiter and Probe (NASA)</li>
      <li><strong>Cassini-Huygens</strong>: Saturn, Ring System, and Titan Orbiter (NASA / ESA)</li>
      <li><strong>New Horizons</strong>: Pluto System and Kuiper Belt Encounter (NASA)</li>
      <li><strong>Lunar Reconnaissance Orbiter (LRO)</strong>: High-Resolution Lunar Orbiter (NASA)</li>
      <li><strong>Dawn</strong>: Vesta and Ceres Protoplanet Orbiter (NASA)</li>
      <li><strong>Rosetta</strong>: Comet 67P/Churyumov-Gerasimenko Rendezvous and Lander (ESA)</li>
    </ul>

    <hr/>

    <h3>Third-Party Planetary Data Policy and Archives</h3>
    <p>VEDA ingests and visualizes public planetary science data from international space agency archives. VEDA does not claim ownership of underlying raw or calibrated telemetry.</p>
    <ul>
      <li><strong>NASA Planetary Data System (PDS):</strong> Public domain datasets provided by NASA SMD (Atmospheres, PPI, Geosciences, Small Bodies, and Imaging nodes).</li>
      <li><strong>ESA Planetary Science Archive (PSA):</strong> Open-access research data provided by ESA ESAC. Publications must include standard ESA PSA acknowledgments.</li>
      <li><strong>JAXA DARTS / ISAS:</strong> Open-access scientific data provided by JAXA. Publications must credit JAXA and the Akatsuki / mission teams.</li>
      <li><strong>ISRO ISSDC:</strong> Planetary datasets provided under ISRO science data terms.</li>
    </ul>

    <h4>Mandatory Dual-Attribution for Academic Publications</h4>
    <p>When publishing scientific research that uses data, figures, or analyses produced with VEDA, researchers are required to cite both:</p>
    <ol>
      <li>The primary space agency dataset, instrument PI team, and archive DOI.</li>
      <li>The VEDA software platform.</li>
    </ol>

    <p><strong>BibTeX Citation for VEDA:</strong></p>
    <pre style="background: rgba(0,0,0,0.4); padding: 10px; border-radius: 6px; font-size: 11px; overflow-x: auto;">
@software{Aggarwal_VEDA_2026,
  author    = {Keshav Aggarwal},
  title     = {{VEDA: Visualization, Exploration, and Data Analysis - A Multi-Mission Planetary Science Data Laboratory}},
  year      = {2026},
  publisher = {Space Physics Laboratory (SPL), Vikram Sarabhai Space Centre (VSSC), ISRO},
  version   = {1.0.0},
  url       = {https://jovian-explorer.github.io/},
  address   = {Thiruvananthapuram, Kerala, India}
}</pre>

    <hr/>

    <h3>Software License and Open-Source Attributions</h3>
    <p><strong>License:</strong> VEDA is open-source software released under the <strong>MIT License</strong>. Copyright (c) 2026 Keshav Aggarwal, Space Physics Laboratory (SPL), Vikram Sarabhai Space Centre (VSSC), ISRO.</p>
    <p><strong>Third-Party Libraries:</strong> VEDA utilizes and bundles permissive open-source libraries: KaTeX (MIT), Plotly.js (MIT), Three.js (MIT), FastAPI (MIT), Pydantic (MIT), Uvicorn (BSD-3-Clause), NumPy (BSD-3-Clause), SciPy (BSD-3-Clause), Astropy (BSD-3-Clause), Matplotlib (PSF), and PyWebView (BSD-3-Clause). Full license notices are available in the repository documentation.</p>

    <hr/>

    <h3>Lead Researcher and Developer</h3>
    <p><strong>Keshav Aggarwal</strong></p>
    <p>Research Associate, Space Physics Laboratory (SPL), Vikram Sarabhai Space Centre (VSSC), Indian Space Research Organisation (ISRO), Thiruvananthapuram, Kerala, India.</p>
    <p>Former Prime Minister's Research Fellow (PMRF Scholar), Department of Astronomy, Astrophysics and Space Engineering (DAASE), Indian Institute of Technology (IIT) Indore.</p>
    <p>Research Specialization: Planetary Radio Occultation, Space Physics, Solar Wind Velocity and Turbulence, Coronal Electron Density, and Planetary Atmospheric and Ionospheric Structure.</p>
    <p><a href="https://jovian-explorer.github.io/" target="_blank" rel="noopener">🌐 Visit Researcher Website ↗</a></p>
  `;
  return container;
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
