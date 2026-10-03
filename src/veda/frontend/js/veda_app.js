/**
 * VEDA: Visualization, Exploration, and Data Analysis
 * Dedicated Planetary Science Laboratory Workstation Controller
 */
import { api, state } from './api.js';
import { renderMath, toast, cleanPlotlyMath, themedLayout, plotColors, drawer, closeDrawer } from './ui.js';
import { setupArchiveBrowser, showMissionArchive } from './archive_browser.js';
import { showGeometry } from './geometry.js';
import { setupBodySearch, showBodySearch } from './body_search.js';
import { showProductViewer } from './product_viewer.js';
import { prefetchMission, prefetchObservation } from './spice_auto.js';
import { recordProduct, recordFeature } from './citations.js';
import { style as plotStyle, styleTrace, styleLayout, sigmaBand, orient, paletteColor, plotStyleBody, exportFigure } from './plot_style.js';

/** Surface gravity with three significant figures (comet 67P: 1.6e-4, not 0.00). */
const fmtGravity = (g) => (g == null || !isFinite(g) ? 'N/A'
  : Math.abs(g) >= 0.01 ? Number(g).toFixed(2) : Number(g).toExponential(1));
const escHtml = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

let imageViewerListeners = null;   // AbortController for the open image's window listeners

// VEDA Global State
export const vedaState = {
  mode: 'body', // 'body' | 'mission'
  bodies: [],
  missions: [],
  // Celestial Body Mode State
  activeBodyId: 'venus',
  activeBody: null,
  selectedMissionIdsForBody: new Set(['akatsuki', 'vex']),
  selectedCompareVariable: 'temperature_k',
  compareFilter: null,   // dates and geometry limits for the comparison (null: downloaded profiles)
  compareGroupBy: '',    // climatology bins: latitude | lst | sza | year | month | month_of_year | mission
  compareGroupWidth: '',
  compareAltitudeStep: '',
  compareVertical: 'altitude',   // altitude | pressure (grid uniform in log p)
  compareShowAs: 'values',  // values | deviation
  lastComparisonData: null,
  bodySubtab: 'soundings', // 'soundings' | 'map'
  planetaryMapProjection: '2d', // '2d' | '3d'
  currentBodyObservations: [],
  // Mission Mode State
  activeMissionId: 'new_horizons',
  activeMission: null,
  missionFilter: 'all', // 'all' | 'orbiter' | 'flyby' | 'other'
  missionObservations: [],
  comparisonProducts: null,  // [{mission_id, observation_id}] picked in the archive browser
  selectedObservation: null,
  currentProfileData: null,
  currentImageData: null,
  // Units State for Quick Unit Switcher
  unitsTemperature: 'K', // 'K' | 'C'
  unitsPressure: 'hPa',  // 'bar' | 'hPa' | 'Pa'
  plotDpi: 300,          // publication figure DPI (from Settings)
  // FITS image controls
  imageStretch: 'zscale',
  imageColormap: 'inferno',
  transectCoords: { x0: 50, y0: 50, x1: 200, y1: 200 },
};

// Variable Display Configs
const VARIABLE_CONFIGS = {
  temperature_k: { label: 'Temperature', units: 'K', axis: 'Temperature (K)', color: '#ff7043' },
  temperature_c: { label: 'Temperature', units: '°C', axis: 'Temperature (°C)', color: '#ffb74d' },
  pressure_hpa: { label: 'Atmospheric Pressure', units: 'hPa', axis: 'Pressure (hPa)', logScale: true, color: '#4fc3f7' },
  lapse_rate: { label: 'Lapse Rate (-dT/dz)', units: 'K/km', axis: 'Lapse Rate (K/km)', color: '#ba68c8' },
  dry_adiabatic_lapse_rate: { label: 'Dry Adiabatic Lapse Rate (g/cp)', units: 'K/km', axis: 'Dry Adiabatic Lapse Rate (K/km)', color: '#4db6ac' },
  potential_temperature: { label: 'Potential Temp (θ)', units: 'K', axis: 'Potential Temperature θ (K)', color: '#81c784' },
  buoyancy_freq_sq: { label: 'Brunt-Väisälä (N²)', units: 'rad²/s²', axis: 'Buoyancy Freq Squared N² (rad²/s²)', color: '#ffb300' },
  density: { label: 'Mass Density (ρ)', units: 'kg/m³', axis: 'Mass Density ρ (kg/m³)', logScale: true, color: '#4db6ac' },
  scale_height: { label: 'Scale Height (H)', units: 'km', axis: 'Scale Height H (km)', color: '#90caf9' },
  electron_density_cm3: { label: 'Electron Density (Ne)', units: 'cm⁻³', axis: 'Electron Density Ne (cm⁻³)', logScale: true, color: '#f06292' },
  h2so4_ppm: { label: 'H₂SO₄ vapour (ppm)', units: 'ppm', axis: 'H₂SO₄ vapour volume mixing ratio (ppm)', color: '#eab308' },
  absorptivity_db_km: { label: 'Microwave absorptivity', units: 'dB/km', axis: 'Absorptivity (dB/km)', color: '#f97316' },
  density_measured: { label: 'Mass density (archive)', units: 'kg/m³', axis: 'Mass density ρ (kg/m³)', logScale: true, color: '#14b8a6' },
  number_density_m3: { label: 'Number density (archive)', units: 'm⁻³', axis: 'Number density (m⁻³)', logScale: true, color: '#22d3ee' },
  refractivity: { label: 'Radio Refractivity (N)', units: 'N-units', axis: 'Refractivity N', color: '#a1887f' },
};

// Mission Distinct Color Palette for Comparative Charts
const MISSION_COLORS = {
  akatsuki: '#ff5252',
  vex: '#448aff',
  magellan: '#e040fb',
  pvo: '#ffd740',
  bepicolombo: '#69f0ae',
  messenger: '#ffab40',
  maven: '#ff5252',
  mro: '#40c4ff',
  juno: '#ff6e40',
  galileo: '#7c4dff',
  cassini: '#00e5ff',
  new_horizons: '#ffd740',
  lro: '#b0bec5',
  dawn: '#00b0ff',
  rosetta: '#1de9b6',
  mom: '#ff3d00',
  chandrayaan2: '#00e676',
  user_imported: '#00e5ff',
};

export function getMissionColor(missionId) {
  const m = (missionId || '').toLowerCase();
  if (MISSION_COLORS[m]) return MISSION_COLORS[m];
  const fallback = ['#ff5252', '#448aff', '#00e676', '#ffb300', '#ba68c8', '#00e5ff', '#ff3d00', '#69f0ae'];
  let hash = 0;
  for (let i = 0; i < m.length; i++) hash = (hash << 5) - hash + m.charCodeAt(i);
  return fallback[Math.abs(hash) % fallback.length];
}

// Planetary Icons & Badges
const BODY_EMOJIS = {
  venus: '🟡',
  mars: '🔴',
  earth: '🌍',
  jupiter: '🪐',
  saturn: '🪐',
  titan: '🟠',
  pluto: '❄️',
  mercury: '⚪',
  moon: '🌙',
  ceres: '⚪',
  vesta: '☄️',
  comet_67p: '☄️',
};

// Planetary Body Physical Constants Quick-Card Catalog
export const BODY_PHYSICAL_CONSTANTS = {
  venus: {
    name: 'Venus',
    category: 'Terrestrial Planet',
    gravity: '8.87 m/s²',
    scale_height: '15.9 km',
    pressure_bar: '92.0 bar (92,000 hPa)',
    composition: '96.5% CO2, 3.5% N2, 0.015% SO2',
    mean_temp_k: '737 K (464 °C)',
    solar_dist_au: '0.723 AU (108.2 million km)',
    notes: 'Superrotating thick CO2 atmosphere, runaway greenhouse effect'
  },
  mars: {
    name: 'Mars',
    category: 'Terrestrial Planet',
    gravity: '3.72 m/s²',
    scale_height: '11.1 km',
    pressure_bar: '0.0061 bar (6.1 hPa)',
    composition: '95.3% CO2, 2.6% N2, 1.9% Ar',
    mean_temp_k: '214 K (-59 °C)',
    solar_dist_au: '1.524 AU (227.9 million km)',
    notes: 'Rarefied CO2 atmosphere with seasonal polar caps and dust storms'
  },
  earth: {
    name: 'Earth',
    category: 'Terrestrial Planet',
    gravity: '9.81 m/s²',
    scale_height: '8.5 km',
    pressure_bar: '1.013 bar (1013.25 hPa)',
    composition: '78.1% N2, 20.9% O2, 0.93% Ar',
    mean_temp_k: '288 K (15 °C)',
    solar_dist_au: '1.000 AU (149.6 million km)',
    notes: 'Nitrogen-oxygen atmosphere supporting liquid hydrosphere and biosphere'
  },
  jupiter: {
    name: 'Jupiter',
    category: 'Gas Giant',
    gravity: '24.79 m/s²',
    scale_height: '23.9 km (1 bar, 165 K)',
    pressure_bar: '1.000 bar (1 bar ref level)',
    composition: '86.2% H2, 13.6% He, 0.2% CH4',
    mean_temp_k: '165 K (-108 °C at 1 bar)',
    solar_dist_au: '5.204 AU (778.5 million km)',
    notes: 'Massive hydrogen-helium envelope with ammonia ice clouds and Great Red Spot'
  },
  saturn: {
    name: 'Saturn',
    category: 'Gas Giant',
    gravity: '10.44 m/s²',
    scale_height: '46.4 km (1 bar, 134 K)',
    pressure_bar: '1.000 bar (1 bar ref level)',
    composition: '88.55% H2, 11% He, 0.45% CH4',
    mean_temp_k: '134 K (-139 °C at 1 bar)',
    solar_dist_au: '9.582 AU (1.433 billion km)',
    notes: 'Hydrogen-helium atmosphere with equatorial jets and northern polar hexagon'
  },
  titan: {
    name: 'Titan',
    category: 'Planetary Moon',
    gravity: '1.352 m/s²',
    scale_height: '20.0 km (near surface), ~40 km aloft',
    pressure_bar: '1.467 bar (1467 hPa)',
    composition: '95.0% N2, 4.9% CH4, 0.1% H2',
    mean_temp_k: '94 K (-179 °C)',
    solar_dist_au: '9.582 AU (Saturn orbit, 1.433 billion km)',
    notes: 'Dense nitrogen atmosphere with photochemical tholin haze and liquid methane hydrologic cycle'
  },
  pluto: {
    name: 'Pluto',
    category: 'Dwarf Planet',
    gravity: '0.62 m/s²',
    scale_height: '50.0 km',
    pressure_bar: '1.15e-5 bar (1.15 Pa / 0.0115 hPa)',
    composition: '99.0% N2, 0.5% CH4, 0.1% CO',
    mean_temp_k: '37 K (-236 °C)',
    solar_dist_au: '39.48 AU (5.906 billion km)',
    notes: 'Tenuous nitrogen atmosphere with steep temperature inversion and blue haze'
  },
  mercury: {
    name: 'Mercury',
    category: 'Terrestrial Planet',
    gravity: '3.70 m/s²',
    scale_height: 'Exosphere (Surface-boundary)',
    pressure_bar: '~1e-15 bar (Surface exosphere)',
    composition: '42% O, 29% Na, 22% H, 6% He',
    mean_temp_k: '440 K (167 °C mean; diurnal 100 to 700 K)',
    solar_dist_au: '0.387 AU (57.9 million km)',
    notes: 'Sputtered surface-boundary exosphere with dipolar magnetic field'
  },
  moon: {
    name: 'Moon',
    category: 'Planetary Moon',
    gravity: '1.62 m/s²',
    scale_height: 'Exosphere (Surface-boundary)',
    pressure_bar: '~1e-14 bar (Surface exosphere)',
    composition: '40% He, 40% Ne, 20% Ar',
    mean_temp_k: '220 K (-53 °C mean; diurnal 100 to 390 K)',
    solar_dist_au: '1.000 AU (Earth orbit, 149.6 million km)',
    notes: 'Ultra-tenuous exosphere with permanently shadowed polar volatile deposits'
  },
  ceres: {
    name: 'Ceres',
    category: 'Dwarf Planet',
    gravity: '0.28 m/s²',
    scale_height: 'Transient exosphere',
    pressure_bar: '~1e-13 bar (Transient)',
    composition: 'Transient H2O vapor',
    mean_temp_k: '168 K (-105 °C)',
    solar_dist_au: '2.767 AU (413.9 million km)',
    notes: 'Water-rich dwarf planet with carbonate deposits and transient water outgassing'
  },
  vesta: {
    name: 'Vesta',
    category: 'Protoplanet / Asteroid',
    gravity: '0.25 m/s²',
    scale_height: 'None (Airless body)',
    pressure_bar: '0 bar (Negligible vacuum)',
    composition: 'None (Airless basaltic crust)',
    mean_temp_k: '160 K (-113 °C)',
    solar_dist_au: '2.362 AU (353.4 million km)',
    notes: 'Differentiated basaltic protoplanet with metallic iron core and impact basins'
  },
  comet_67p: {
    name: 'Comet 67P/C-G',
    category: 'Comet',
    gravity: '0.0001 m/s²',
    scale_height: 'Coma expansion (~100 km)',
    pressure_bar: '~1e-11 bar (Inner coma)',
    composition: '70% H2O, 15% CO, 10% CO2',
    mean_temp_k: '200 K (-73 °C mean)',
    solar_dist_au: '3.46 AU (Perihelion: 1.24 AU, Aphelion: 5.68 AU)',
    notes: 'Bi-lobed nucleus with active gas sublimation jets and dust coma'
  }
};

export function renderPlanetaryBodyQuickCard(bodyId, bodyDetails) {
  const card = document.getElementById('veda-body-quick-card');
  if (!card) return;

  const bKey = (bodyId || '').toLowerCase();
  const c = BODY_PHYSICAL_CONSTANTS[bKey] || {
    name: bodyDetails?.name || bodyId,
    category: (bodyDetails?.category || 'Celestial Body').replace('_', ' '),
    gravity: bodyDetails?.surface_gravity ? `${fmtGravity(bodyDetails.surface_gravity)} m/s²` : 'N/A',
    scale_height: 'N/A',
    pressure_bar: bodyDetails?.reference_pressure_hpa ? `${(bodyDetails.reference_pressure_hpa / 1000).toFixed(4)} bar` : 'N/A',
    composition: Object.entries(bodyDetails?.atmospheric_composition || {}).map(([g, pct]) => `${g}: ${pct}%`).join(', ') || 'Trace',
    mean_temp_k: 'N/A',
    solar_dist_au: 'N/A',
    notes: bodyDetails?.description || ''
  };

  const emoji = BODY_EMOJIS[bKey] || '🪐';
  const name = bodyDetails?.name || c.name;

  card.innerHTML = `
    <div class="quick-card-head">
      <div class="quick-card-title">
        <span style="font-size: calc(22px * var(--font-scale, 1.0));">${emoji}</span>
        <h3>Planetary Body Physical Constants Quick-Card: ${name}</h3>
      </div>
      <span class="quick-card-badge">${c.category}</span>
    </div>
    <div class="quick-card-grid">
      <div class="quick-card-tile">
        <div class="tile-head">
          <span class="tile-icon">⚖️</span>
          <span class="tile-label">Surface gravity g (m/s²)</span>
        </div>
        <div class="tile-value">${c.gravity}</div>
        <div class="tile-sub">Reference surface acceleration</div>
      </div>
      <div class="quick-card-tile">
        <div class="tile-head">
          <span class="tile-icon">📏</span>
          <span class="tile-label">Atmospheric scale height H (km)</span>
        </div>
        <div class="tile-value">${c.scale_height}</div>
        <div class="tile-sub">Pressure e-folding vertical scale</div>
      </div>
      <div class="quick-card-tile">
        <div class="tile-head">
          <span class="tile-icon">⏲️</span>
          <span class="tile-label">Surface pressure P₀ (bar)</span>
        </div>
        <div class="tile-value">${c.pressure_bar}</div>
        <div class="tile-sub">Baseline hydrostatic pressure</div>
      </div>
      <div class="quick-card-tile">
        <div class="tile-head">
          <span class="tile-icon">🧪</span>
          <span class="tile-label">Dominant atmospheric composition</span>
        </div>
        <div class="tile-value" style="font-size: calc(13px * var(--font-scale, 1.0));">${c.composition}</div>
        <div class="tile-sub">Major atmospheric constituents</div>
      </div>
      <div class="quick-card-tile">
        <div class="tile-head">
          <span class="tile-icon">🌡️</span>
          <span class="tile-label">Mean surface temperature T_surf (K)</span>
        </div>
        <div class="tile-value">${c.mean_temp_k}</div>
        <div class="tile-sub">Planetary surface thermal state</div>
      </div>
      <div class="quick-card-tile">
        <div class="tile-head">
          <span class="tile-icon">☀️</span>
          <span class="tile-label">Solar distance (AU)</span>
        </div>
        <div class="tile-value">${c.solar_dist_au}</div>
        <div class="tile-sub">Semi-major orbital distance</div>
      </div>
    </div>
  `;
}

/**
 * Initialize VEDA UI and event handlers
 */
// Apply the saved Settings.  On first load they also choose the starting body
// and mission; later saves only change units and figure defaults.
export function applyUserPreferences(settings, { initial = false } = {}) {
  if (!settings) return;
  if (settings.units_temperature) vedaState.unitsTemperature = settings.units_temperature;
  if (settings.units_pressure) vedaState.unitsPressure = settings.units_pressure;
  if (settings.plot_dpi) vedaState.plotDpi = settings.plot_dpi;
  if (initial) {
    if (settings.default_body) vedaState.activeBodyId = settings.default_body;
    if (settings.default_mission) vedaState.activeMissionId = settings.default_mission;
    vedaState.selectedCompareVariable = vedaState.unitsTemperature === 'C' ? 'temperature_c' : 'temperature_k';
  }
  syncUnitButtons();
  const pub = document.getElementById('veda-btn-download-publication-fig');
  if (pub) {
    pub.textContent = `🏛️ Publication Figure (${vedaState.plotDpi} DPI)`;
    pub.title = `Download a publication-quality figure at ${vedaState.plotDpi} DPI (change in Settings)`;
  }
  if (!initial && vedaState.mode === 'body') renderActiveSubtab();
}

function syncUnitButtons() {
  const on = (id, active) => document.getElementById(id)?.classList.toggle('active', active);
  on('btn-comp-unit-k', vedaState.unitsTemperature === 'K');
  on('btn-comp-unit-c', vedaState.unitsTemperature === 'C');
  on('btn-comp-unit-hpa', vedaState.unitsPressure === 'hPa');
  on('btn-comp-unit-bar', vedaState.unitsPressure === 'bar');
  on('btn-comp-unit-pa', vedaState.unitsPressure === 'Pa');
  const varSelect = document.getElementById('veda-compare-variable-select');
  if (varSelect && varSelect.querySelector(`option[value="${vedaState.selectedCompareVariable}"]`)) {
    varSelect.value = vedaState.selectedCompareVariable;
  }
}

export async function initVeda() {
  const container = document.getElementById('veda-container');
  if (!container) return;

  // Load platform metadata
  try {
    const [bodiesData, missionsData] = await Promise.all([
      api.vedaBodies(),
      api.vedaMissions(),
    ]);
    vedaState.bodies = bodiesData;
    vedaState.missions = missionsData;
  } catch (err) {
    console.error('Failed to load VEDA initial registry:', err);
    return;
  }

  applyUserPreferences(state.meta && state.meta.settings, { initial: true });

  // Setup DOM Event Listeners
  setupModeSwitching();
  setupBodyModeControls();
  setupMissionModeControls();
  setupArchiveBrowser({ onOpen: openArchiveProduct, onCompare: compareSelectedProducts });
  setupBodySearch({
    onOpen: async (p) => {
      switchMode('mission');
      await loadAndRenderMission(p.mission_id);
      await openArchiveProduct(p);
      document.getElementById('veda-observation-viewer')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    },
    onCompare: compareSelectedProducts,
  });
  setupWorkflowGuideInteractions();
  setupGlobalDragAndDrop();

  // Render Initial View
  renderCelestialBodiesGrid();
  renderMissionsCatalog();
  await loadAndRenderCelestialBody(vedaState.activeBodyId);
  renderMath(document.body);
}

/**
 * Mode Switching: By Celestial Body vs By Mission vs Workflow Guide
 */
export function switchMode(mode) {
  vedaState.mode = mode;
  const btnBodyMode = document.getElementById('btn-mode-body');
  const btnMissionMode = document.getElementById('btn-mode-mission');
  const btnGuideMode = document.getElementById('btn-mode-guide');
  const viewBody = document.getElementById('veda-view-body');
  const viewMission = document.getElementById('veda-view-mission');
  const viewGuide = document.getElementById('veda-view-guide');

  if (btnBodyMode) btnBodyMode.classList.toggle('active', mode === 'body');
  if (btnMissionMode) btnMissionMode.classList.toggle('active', mode === 'mission');
  if (btnGuideMode) btnGuideMode.classList.toggle('active', mode === 'guide');

  if (viewBody) viewBody.style.display = (mode === 'body') ? 'block' : 'none';
  if (viewMission) viewMission.style.display = (mode === 'mission') ? 'block' : 'none';
  if (viewGuide) viewGuide.style.display = (mode === 'guide') ? 'block' : 'none';

  if (mode === 'body') {
    renderComparisonPlot();
    if (viewBody) renderMath(viewBody);
  } else if (mode === 'mission') {
    if (!vedaState.activeMission) {
      loadAndRenderMission(vedaState.activeMissionId);
    }
    if (viewMission) renderMath(viewMission);
  } else if (mode === 'guide') {
    if (viewGuide) renderMath(viewGuide);
  }

  setTimeout(() => {
    window.dispatchEvent(new Event('resize'));
    resizeAllPlots();
  }, 60);
}

export function resizeAllPlots() {
  if (!window.Plotly) return;
  const plotIds = [
    'veda-comparison-plot',
    'veda-single-profile-plot',
    'veda-transect-plot',
    'veda-histogram-plot',
    'veda-planetary-map'
  ];
  plotIds.forEach(id => {
    const el = document.getElementById(id);
    if (el && el.offsetParent !== null && typeof window.Plotly.Plots.resize === 'function') {
      try { window.Plotly.Plots.resize(el); } catch (e) {}
    }
  });
}

function setupModeSwitching() {
  const btnBodyMode = document.getElementById('btn-mode-body');
  const btnMissionMode = document.getElementById('btn-mode-mission');
  const btnGuideMode = document.getElementById('btn-mode-guide');

  if (btnBodyMode) btnBodyMode.addEventListener('click', () => switchMode('body'));
  if (btnMissionMode) btnMissionMode.addEventListener('click', () => switchMode('mission'));
  if (btnGuideMode) btnGuideMode.addEventListener('click', () => switchMode('guide'));
}

// ==========================================================================
// 1. CELESTIAL BODY EXPLORATION MODE
// ==========================================================================

function renderCelestialBodiesGrid() {
  const grid = document.getElementById('veda-bodies-grid');
  if (!grid) return;
  grid.innerHTML = '';

  vedaState.bodies.forEach(b => {
    const card = document.createElement('button');
    card.className = `body-selector-card ${b.id === vedaState.activeBodyId ? 'active' : ''}`;
    card.dataset.bodyId = b.id;
    const emoji = BODY_EMOJIS[b.id] || '🪐';
    card.innerHTML = `
      <div class="body-emoji">${emoji}</div>
      <div class="body-card-content">
        <div class="body-card-name">${b.name}</div>
        <div class="body-card-sub">${(b.supported_missions || []).length} mission${(b.supported_missions || []).length === 1 ? '' : 's'} &bull; ${fmtGravity(b.surface_gravity)} m/s²</div>
      </div>
    `;
    card.addEventListener('click', async () => {
      document.querySelectorAll('.body-selector-card').forEach(el => el.classList.remove('active'));
      card.classList.add('active');
      if (b.id !== vedaState.activeBodyId) vedaState.comparisonProducts = null;  // picks belong to one body
      await loadAndRenderCelestialBody(b.id);
    });
    grid.appendChild(card);
  });
}

export async function loadAndRenderCelestialBody(bodyId) {
  vedaState.activeBodyId = bodyId;
  const bodyDetails = await api.vedaBodyDetails(bodyId);
  vedaState.activeBody = bodyDetails;

  // Render Planetary Body Physical Constants Quick-Card
  renderPlanetaryBodyQuickCard(bodyId, bodyDetails);
  showBodySearch(bodyId, bodyDetails.name);

  // Update Body Physics Banner
  const banner = document.getElementById('veda-body-banner');
  if (banner) {
    const compStr = Object.entries(bodyDetails.atmospheric_composition || {})
      .map(([gas, pct]) => `${gas}: ${pct}%`).join(', ') || 'Trace exosphere';
    banner.innerHTML = `
      <div class="body-banner-head">
        <h2>${BODY_EMOJIS[bodyId] || '🪐'} ${bodyDetails.name}</h2>
        <span class="badge category-badge">${bodyDetails.category.replace('_', ' ').toUpperCase()}</span>
        <div class="body-banner-links" style="display:inline-flex; gap:8px; margin-left:auto; flex-wrap:wrap;">
          ${bodyDetails.mission_page_url ? `<a href="${bodyDetails.mission_page_url}" target="_blank" rel="noopener" class="badge" style="text-decoration:none; background:#1e3a5f; color:#90caf9;">🌐 Exploration Overview ↗</a>` : ''}
          ${bodyDetails.data_page_url ? `<a href="${bodyDetails.data_page_url}" target="_blank" rel="noopener" class="badge" style="text-decoration:none; background:#2e4c36; color:#a5d6a7;">🗄️ Planetary Data Archive ↗</a>` : ''}
        </div>
      </div>
      <p class="body-desc" style="line-height:1.6; margin:8px 0 12px 0;">${bodyDetails.description}</p>
      <div class="physics-metrics-row">
        <div class="phys-badge"><strong>Radius:</strong> ${bodyDetails.radius_km.toLocaleString()} km</div>
        <div class="phys-badge"><strong>Gravity g₀:</strong> ${fmtGravity(bodyDetails.surface_gravity)} m/s²</div>
        <div class="phys-badge"><strong>Gas Const R:</strong> ${bodyDetails.gas_constant_r} J/(kg K)</div>
        <div class="phys-badge"><strong>Ref Pressure:</strong> ${bodyDetails.reference_pressure_hpa >= 1 ? bodyDetails.reference_pressure_hpa.toLocaleString() + ' hPa' : bodyDetails.reference_pressure_hpa + ' hPa'}</div>
        <div class="phys-badge"><strong>Atmosphere:</strong> ${compStr}</div>
      </div>
    `;
  }

  // Populate Mission Checkboxes
  const missionCheckboxes = document.getElementById('veda-missions-checkboxes');
  if (missionCheckboxes) {
    missionCheckboxes.innerHTML = '';
    const missions = bodyDetails.missions || [];
    // Reset or keep compatible selection
    const defaultMids = missions.slice(0, 2).map(m => m.id);
    vedaState.selectedMissionIdsForBody = new Set(defaultMids);

    missions.forEach(m => {
      const label = document.createElement('label');
      label.className = 'mission-checkbox-label';
      const isChecked = vedaState.selectedMissionIdsForBody.has(m.id);
      const kind = m.encounter_type === 'flyby' ? 'Flyby'
        : ['lander', 'rover', 'probe'].includes(m.mission_type) ? m.mission_type[0].toUpperCase() + m.mission_type.slice(1) : 'Orbiter';
      const encBadge = `<span class="badge ${kind === 'Flyby' ? 'badge-flyby' : 'badge-orbiter'}">${kind}</span>`;
      label.innerHTML = `
        <input type="checkbox" value="${m.id}" ${isChecked ? 'checked' : ''}>
        <span class="checkbox-box"></span>
        <span class="mission-name-span">${m.name}</span>
        ${encBadge}
        <span class="mission-instruments-hint" title="${(m.instruments || []).join(', ')}">${(m.instruments || []).slice(0, 3).join(', ')}</span>
      `;
      const input = label.querySelector('input');
      input.addEventListener('change', () => {
        if (input.checked) {
          vedaState.selectedMissionIdsForBody.add(m.id);
        } else {
          vedaState.selectedMissionIdsForBody.delete(m.id);
        }
        updateComparison();
      });
      missionCheckboxes.appendChild(label);
    });
  }

  await updateComparison();
}

// ------------------------------------------------------------------ which profiles to compare

/** The comparison request behind the plot on screen (exports use the same). */
function currentComparisonRequest() {
  return {
    observations: vedaState.comparisonProducts || undefined,
    missions: Array.from(vedaState.selectedMissionIdsForBody),
    variable: vedaState.selectedCompareVariable,
    filter: vedaState.comparisonProducts ? undefined : (vedaState.compareFilter || undefined),
    group_by: vedaState.compareGroupBy || undefined,
    group_width: Number(vedaState.compareGroupWidth) || 0,
    altitude_step_km: Number(vedaState.compareAltitudeStep) || undefined,
    vertical: vedaState.compareVertical === 'pressure' ? 'pressure' : undefined,
  };
}

// Variables averaged in log space (their deviations are shown in percent)
const LOG_COMPARE_VARIABLES = new Set(['pressure_hpa', 'density', 'density_measured', 'number_density_m3', 'electron_density_cm3']);

/**
 * The comparison as it is drawn: values, or each profile's deviation from the mean
 * (its group's mean when grouped; percent for log-averaged variables), with the group
 * means as deviations from the overall mean.
 */
function comparisonView(data) {
  const groups = (data.groups || []).filter(g => !g.ungrouped && g.mean && g.mean.length);
  if (vedaState.compareShowAs !== 'deviation') return { data, groups, deviation: false };
  const logVar = LOG_COMPARE_VARIABLES.has(vedaState.selectedCompareVariable);
  const overall = data.composite_mean || [];
  const groupOf = {};
  groups.forEach((g, gi) => g.observation_ids.forEach(id => { groupOf[id] = gi; }));
  const dev = (series, ref) => (series || []).map((v, k) => (v == null || ref[k] == null || (logVar && !ref[k])
    ? null : (logVar ? 100 * (v / ref[k] - 1) : v - ref[k])));
  const zero = overall.map(v => (v == null ? null : 0));
  return {
    deviation: true, logVar,
    data: {
      ...data,
      composite_mean: zero,
      composite_plus_1sigma: dev(data.composite_plus_1sigma, overall),
      composite_minus_1sigma: dev(data.composite_minus_1sigma, overall),
      profiles: (data.profiles || []).map(p => ({ ...p, interpolated_series:
        dev(p.interpolated_series, groupOf[p.observation_id] != null ? groups[groupOf[p.observation_id]].mean : overall) })),
    },
    groups: groups.map(g => ({ ...g, mean: dev(g.mean, overall), plus_1sigma: dev(g.plus_1sigma, overall),
                               minus_1sigma: dev(g.minus_1sigma, overall) })),
  };
}

function readCompareFilter() {
  const num = (id) => { const v = document.getElementById(id)?.value; return v === '' || v == null ? null : Number(v); };
  const f = {
    start: document.getElementById('cf-start')?.value || null,
    end: document.getElementById('cf-end')?.value || null,
    lat_min: num('cf-lat-min'), lat_max: num('cf-lat-max'),
    lst_min: num('cf-lst-min'), lst_max: num('cf-lst-max'),
    sza_min: num('cf-sza-min'), sza_max: num('cf-sza-max'),
    ls_min: num('cf-ls-min'), ls_max: num('cf-ls-max'),
    per_mission: num('cf-per-mission') || 10,
    download: !!document.getElementById('cf-download')?.checked,
  };
  if (f.start && f.end && f.start > f.end) throw new Error('The start date is after the end date');
  for (const [a, b, what] of [['lat_min', 'lat_max', 'latitude'], ['sza_min', 'sza_max', 'solar zenith angle']]) {
    if (f[a] != null && f[b] != null && f[a] > f[b]) throw new Error(`The ${what} range is reversed`);
  }
  return f;
}

function renderSelectionReport(sel) {
  const el = document.getElementById('cf-report');
  if (!el) return;
  if (!sel || vedaState.comparisonProducts) { el.textContent = ''; return; }
  const name = (mid) => (vedaState.missions.find(m => m.id === mid) || {}).name || mid.toUpperCase();
  el.innerHTML = Object.entries(sel).map(([mid, r]) => {
    const out = Object.entries(r.left_out || {}).map(([why, n]) => `${n} ${escHtml(why)}`);
    if (r.failed) out.push(`${r.failed} unreadable`);
    const parts = [`<strong>${escHtml(name(mid))}</strong>: ${r.kept} kept`,
      r.note ? escHtml(r.note) : `${r.in_date_range} in the date range, ${r.tried} read`];
    if (out.length) parts.push(`left out: ${out.join(', ')}`);
    if (r.not_indexed?.length) parts.push(`not indexed yet: open the mission's archive data to index ${r.not_indexed.map(escHtml).join(', ')}`);
    return `<div>${parts.join('; ')}</div>`;
  }).join('') + (vedaState.compareFilter ? '' : '<div>Showing downloaded profiles only. Set dates or ranges and press Apply to search the whole archive.</div>');
}

// The comparison choices (which profiles, grouping, grid, vertical, view) are kept on this
// computer and filled in again the next time VEDA opens.  A remembered filter only fills
// the fields: nothing is searched or downloaded until Apply is pressed.
const COMPARE_FORM_KEY = 'veda.compare.form';
const COMPARE_OPTIONS = [
  ['veda-compare-group-by', 'compareGroupBy'], ['veda-compare-group-width', 'compareGroupWidth'],
  ['veda-compare-altitude-step', 'compareAltitudeStep'], ['veda-compare-vertical', 'compareVertical'],
  ['veda-compare-show-as', 'compareShowAs'],
];

function saveCompareForm() {
  const saved = {};
  document.querySelectorAll('#veda-compare-filter input').forEach(i => {
    if (i.id) saved[i.id] = i.type === 'checkbox' ? i.checked : i.value;
  });
  COMPARE_OPTIONS.forEach(([id]) => { const el = document.getElementById(id); if (el) saved[id] = el.value; });
  try { localStorage.setItem(COMPARE_FORM_KEY, JSON.stringify(saved)); } catch (_) { /* storage blocked */ }
}

function restoreCompareForm() {
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem(COMPARE_FORM_KEY) || 'null'); } catch (_) { saved = null; }
  if (!saved || typeof saved !== 'object') return;
  document.querySelectorAll('#veda-compare-filter input').forEach(i => {
    if (!(i.id in saved)) return;
    if (i.type === 'checkbox') i.checked = !!saved[i.id];
    else i.value = String(saved[i.id] ?? '');
  });
  COMPARE_OPTIONS.forEach(([id, key]) => {
    const el = document.getElementById(id);
    if (!el || !(id in saved)) return;
    el.value = String(saved[id] ?? '');
    if (el.tagName === 'SELECT' && el.value !== String(saved[id] ?? '')) return;   // option no longer offered
    if (id === 'veda-compare-altitude-step') {
      const v = el.value === '' ? '' : Number(el.value);
      if (v !== '' && !(v >= 0.01 && v <= 100)) { el.value = ''; return; }
      vedaState[key] = v;
    } else {
      vedaState[key] = el.value;
    }
  });
}

function setupCompareFilter() {
  const form = document.getElementById('veda-compare-filter');
  if (!form) return;
  restoreCompareForm();
  form.addEventListener('change', saveCompareForm);
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    try {
      vedaState.compareFilter = readCompareFilter();
    } catch (err) {
      return toast(err.message, 'bad');
    }
    vedaState.comparisonProducts = null;          // a filter replaces a hand-picked selection
    recordFeature('comparison');
    updateComparison();
  });
  document.getElementById('cf-clear')?.addEventListener('click', () => {
    form.querySelectorAll('input[type="date"], input[type="number"]').forEach(i => { i.value = i.id === 'cf-per-mission' ? '10' : ''; });
    saveCompareForm();
    vedaState.compareFilter = null;
    updateComparison();
  });
}

function setupBodyModeControls() {
  setupCompareFilter();
  const groupSel = document.getElementById('veda-compare-group-by');
  const groupWidth = document.getElementById('veda-compare-group-width');
  const showAs = document.getElementById('veda-compare-show-as');
  groupSel?.addEventListener('change', () => { vedaState.compareGroupBy = groupSel.value; updateComparison(); });
  groupWidth?.addEventListener('change', () => { vedaState.compareGroupWidth = groupWidth.value; if (vedaState.compareGroupBy) updateComparison(); });
  const vertSel = document.getElementById('veda-compare-vertical');
  vertSel?.addEventListener('change', () => { vedaState.compareVertical = vertSel.value; updateComparison(); });
  const altStep = document.getElementById('veda-compare-altitude-step');
  altStep?.addEventListener('change', () => {
    const v = altStep.value === '' ? '' : Number(altStep.value);
    if (v !== '' && !(v >= 0.01 && v <= 100)) { altStep.value = vedaState.compareAltitudeStep; return toast('Grid step must be between 0.01 and 100 km', 'bad'); }
    vedaState.compareAltitudeStep = v;
    updateComparison();
  });
  showAs?.addEventListener('change', () => { vedaState.compareShowAs = showAs.value; renderComparisonPlot(); });
  COMPARE_OPTIONS.forEach(([id]) => document.getElementById(id)?.addEventListener('change', saveCompareForm));
  const varSelect = document.getElementById('veda-compare-variable-select');
  if (varSelect) {
    varSelect.innerHTML = Object.entries(VARIABLE_CONFIGS).map(([key, cfg]) => `
      <option value="${key}">${cfg.label} (${cfg.units})</option>
    `).join('');
    varSelect.value = vedaState.selectedCompareVariable;
    varSelect.addEventListener('change', () => {
      vedaState.selectedCompareVariable = varSelect.value;
      updateComparison();
    });
  }

  // Quick Unit Switcher in Body Comparative Mode
  const btnCompK = document.getElementById('btn-comp-unit-k');
  const btnCompC = document.getElementById('btn-comp-unit-c');
  const btnCompBar = document.getElementById('btn-comp-unit-bar');
  const btnCompHpa = document.getElementById('btn-comp-unit-hpa');
  const btnCompPa = document.getElementById('btn-comp-unit-pa');

  if (btnCompK && btnCompC) {
    btnCompK.addEventListener('click', () => {
      vedaState.unitsTemperature = 'K';
      btnCompK.classList.add('active');
      btnCompC.classList.remove('active');
      if (varSelect) {
        varSelect.value = 'temperature_k';
        vedaState.selectedCompareVariable = 'temperature_k';
        updateComparison();
      }
    });
    btnCompC.addEventListener('click', () => {
      vedaState.unitsTemperature = 'C';
      btnCompC.classList.add('active');
      btnCompK.classList.remove('active');
      if (varSelect) {
        varSelect.value = 'temperature_c';
        vedaState.selectedCompareVariable = 'temperature_c';
        updateComparison();
      }
    });
  }

  if (btnCompBar && btnCompHpa && btnCompPa) {
    const pBtns = [btnCompBar, btnCompHpa, btnCompPa];
    pBtns.forEach(b => {
      b.addEventListener('click', () => {
        pBtns.forEach(x => x.classList.remove('active'));
        b.classList.add('active');
        if (b.id === 'btn-comp-unit-bar') vedaState.unitsPressure = 'bar';
        else if (b.id === 'btn-comp-unit-pa') vedaState.unitsPressure = 'Pa';
        else vedaState.unitsPressure = 'hPa';
        if (varSelect) {
          varSelect.value = 'pressure_hpa';
          vedaState.selectedCompareVariable = 'pressure_hpa';
          updateComparison();
        }
      });
    });
  }

  const colorBy = document.getElementById('veda-compare-color-by');
  if (colorBy) colorBy.addEventListener('change', () => { vedaState.compareColorBy = colorBy.value; renderComparisonPlot(); });
  document.getElementById('veda-compare-show-mean')?.addEventListener('change', (e) => { vedaState.compareShowMean = e.target.checked; renderComparisonPlot(); });
  document.getElementById('veda-compare-show-spread')?.addEventListener('change', (e) => { vedaState.compareShowSpread = e.target.checked; renderComparisonPlot(); });
  document.getElementById('veda-btn-plot-style')?.addEventListener('click', openPlotStyle);
  document.getElementById('veda-btn-export-figure')?.addEventListener('click', () =>
    exportFigure(document.getElementById('veda-comparison-plot'), `veda_comparison_${vedaState.activeBodyId}_${vedaState.selectedCompareVariable}`));

  // Exports of the comparison on screen (same profiles, filters and grouping)
  const exportComparison = async (button, path, filename) => {
    const old = button.textContent;
    button.disabled = true;
    button.textContent = 'Exporting...';
    try {
      const res = await fetch(`/api/veda/export/compare/${vedaState.activeBodyId}/${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(currentComparisonRequest()),
      });
      if (!res.ok) {
        let detail = `${res.status} ${res.statusText}`;
        try { detail = (await res.json()).detail || detail; } catch (_) {}
        throw new Error(detail);
      }
      const url = window.URL.createObjectURL(await res.blob());
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      setTimeout(() => window.URL.revokeObjectURL(url), 10000);
    } catch (e) {
      toast(`Export failed: ${e.message}`, 'bad');
    } finally {
      button.disabled = false;
      button.textContent = old;
    }
  };
  const btnExportCsv = document.getElementById('veda-btn-export-comparison-csv');
  btnExportCsv?.addEventListener('click', () => exportComparison(btnExportCsv, 'csv',
    `veda_comparison_${vedaState.activeBodyId}_${vedaState.selectedCompareVariable}.csv`));
  const btnExportProfiles = document.getElementById('veda-btn-export-profiles-csv');
  btnExportProfiles?.addEventListener('click', () => exportComparison(btnExportProfiles, 'profiles',
    `veda_profiles_${vedaState.activeBodyId}.csv`));

  const btnOpen = document.getElementById('veda-btn-open-comparison');
  const openFile = document.getElementById('veda-open-comparison-file');
  btnOpen?.addEventListener('click', () => openFile?.click());
  openFile?.addEventListener('change', async () => {
    const f = openFile.files && openFile.files[0];
    openFile.value = '';
    if (f) await openComparisonRecipe(await f.text());
  });

  const btnDownloadPng = document.getElementById('veda-btn-download-comparison-png');
  if (btnDownloadPng) {
    btnDownloadPng.addEventListener('click', () => {
      const plotDiv = document.getElementById('veda-comparison-plot');
      if (plotDiv && window.Plotly) {
        window.Plotly.downloadImage(plotDiv, {
          format: 'png',
          width: 1200,
          height: 800,
          filename: `veda_${vedaState.activeBodyId}_${vedaState.selectedCompareVariable}`,
        });
      }
    });
  }

  // Publication figure at the DPI chosen in Settings.  Fetched first so a
  // failure shows a message instead of a raw JSON error page.
  const btnPubFig = document.getElementById('veda-btn-download-publication-fig');
  if (btnPubFig) {
    btnPubFig.addEventListener('click', async () => {
      recordFeature('publication_figure');
      btnPubFig.disabled = true;
      toast(`Rendering publication figure at ${vedaState.plotDpi} DPI...`);
      try {
        // The same profiles as the plot: hand-picked ones, or the same filter
        const res = await fetch(`/api/veda/figure/publication?body_id=${encodeURIComponent(vedaState.activeBodyId)}`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ...currentComparisonRequest(), dpi: vedaState.plotDpi, fmt: 'png' }),
        });
        if (!res.ok) {
          let detail = `${res.status} ${res.statusText}`;
          try { detail = (await res.json()).detail || detail; } catch (_) {}
          throw new Error(detail);
        }
        const blobUrl = URL.createObjectURL(await res.blob());
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = `veda_publication_${vedaState.activeBodyId}_${vedaState.selectedCompareVariable}_${vedaState.plotDpi}dpi.png`;
        a.click();
        setTimeout(() => URL.revokeObjectURL(blobUrl), 10000);
        toast('Publication figure saved', 'good');
      } catch (err) {
        toast(`Could not create the figure: ${err.message}`, 'bad');
      } finally {
        btnPubFig.disabled = false;
      }
    });
  }

  // Subtabs: profiles, altitude cut, map
  const SUBTABS = ['soundings', 'cut', 'map'];
  const showSubtab = (name) => {
    vedaState.bodySubtab = name;
    SUBTABS.forEach(t => {
      document.getElementById(`btn-subtab-${t}`)?.classList.toggle('active', t === name);
      const panel = document.getElementById(`veda-subtab-${t}-panel`);
      if (panel) panel.style.display = t === name ? 'flex' : 'none';
    });
    renderActiveSubtab();
  };
  SUBTABS.forEach(t => document.getElementById(`btn-subtab-${t}`)?.addEventListener('click', () => showSubtab(t)));
  ['veda-cut-x', 'veda-cut-color', 'veda-cut-y'].forEach(id => document.getElementById(id)?.addEventListener('change', renderAltitudeCut));
  document.getElementById('veda-cut-altitude')?.addEventListener('change', (e) => {
    vedaState.cutAltitude = e.target.value === '' ? null : Number(e.target.value);
    renderAltitudeCut();
  });
  document.getElementById('veda-cut-top')?.addEventListener('change', (e) => {
    vedaState.cutTop = e.target.value === '' ? null : Number(e.target.value);
    renderAltitudeCut();
  });

  // Map Projection Toggles (2D Equirectangular vs 3D Globe)
  const btnMap2d = document.getElementById('btn-map-proj-2d');
  const btnMap3d = document.getElementById('btn-map-proj-3d');
  if (btnMap2d && btnMap3d) {
    btnMap2d.addEventListener('click', () => {
      vedaState.planetaryMapProjection = '2d';
      btnMap2d.classList.add('active');
      btnMap3d.classList.remove('active');
      renderPlanetaryMap('2d');
    });
    btnMap3d.addEventListener('click', () => {
      vedaState.planetaryMapProjection = '3d';
      btnMap3d.classList.add('active');
      btnMap2d.classList.remove('active');
      renderPlanetaryMap('3d');
    });
  }
}

// Products picked in the archive browser; when set, they replace the
// automatic one-profile-per-mission selection in the body comparison.
async function compareSelectedProducts(products) {
  recordFeature('comparison');
  (products || []).forEach(recordProduct);
  const bodies = new Set(products.map(p => (p.target || '').toLowerCase()).filter(Boolean));
  if (bodies.size > 1) return toast('Pick profiles of a single body to compare them', 'bad');
  const body = [...bodies][0] || (vedaState.activeMission && vedaState.activeMission.primary_targets[0]);
  vedaState.comparisonProducts = products.map(p => ({ mission_id: p.mission_id, observation_id: p.product_id }));
  // Pick a variable the selection actually contains.
  const isIono = (p) => /ionosphere|electron/i.test(p.product_type || '');
  if (products.every(isIono)) vedaState.selectedCompareVariable = 'electron_density_cm3';
  else if (!products.some(isIono) && vedaState.selectedCompareVariable === 'electron_density_cm3') {
    vedaState.selectedCompareVariable = vedaState.unitsTemperature === 'C' ? 'temperature_c' : 'temperature_k';
  }
  syncUnitButtons();
  switchMode('body');
  await loadAndRenderCelestialBody(body);
  toast(`Comparing ${products.length} selected profile${products.length > 1 ? 's' : ''} on ${body}`, 'good');
}

/** Redo a comparison from the "# recipe:" line of a Comparison CSV exported by VEDA. */
async function openComparisonRecipe(csvText) {
  const line = (csvText || '').split(/\r?\n/, 40).find(l => l.startsWith('# recipe: '));
  let r = null;
  try { r = line ? JSON.parse(line.slice(10)) : null; } catch (_) { r = null; }
  if (!r || r.veda_recipe !== 1 || !r.body_id || !Array.isArray(r.observations) || !r.observations.length) {
    return toast('This file is not a Comparison CSV exported by VEDA (no recipe line)', 'bad');
  }
  vedaState.comparisonProducts = r.observations.map(o => ({ mission_id: String(o.mission_id), observation_id: String(o.observation_id) }));
  vedaState.selectedCompareVariable = r.variable || 'temperature_k';
  vedaState.compareGroupBy = r.group_by || '';
  vedaState.compareGroupWidth = r.group_width ? String(r.group_width) : '';
  vedaState.compareAltitudeStep = r.altitude_step_km || '';
  vedaState.compareVertical = r.vertical === 'pressure' ? 'pressure' : 'altitude';
  const setVal = (id, v) => { const el = document.getElementById(id); if (el) el.value = v; };
  setVal('veda-compare-variable-select', vedaState.selectedCompareVariable);
  setVal('veda-compare-group-by', vedaState.compareGroupBy);
  setVal('veda-compare-group-width', vedaState.compareGroupWidth);
  setVal('veda-compare-altitude-step', vedaState.compareAltitudeStep);
  setVal('veda-compare-vertical', vedaState.compareVertical);
  syncUnitButtons();
  switchMode('body');
  await loadAndRenderCelestialBody(r.body_id);
  toast(`Comparison of ${r.observations.length} profiles reopened`
        + (r.veda_version ? ` (exported by VEDA ${String(r.veda_version)})` : ''), 'good');
}

function renderComparisonSelectionNote() {
  const el = document.getElementById('veda-comparison-status');
  const n = (vedaState.comparisonProducts || []).length;
  let chip = document.getElementById('veda-selection-chip');
  if (!n) { chip?.remove(); return; }
  if (!chip && el) {
    chip = document.createElement('div');
    chip.id = 'veda-selection-chip';
    chip.className = 'selection-chip';
    el.insertAdjacentElement('beforebegin', chip);
  }
  if (chip) {
    chip.innerHTML = `Comparing ${n} hand-picked profile${n > 1 ? 's' : ''} <button type="button" class="ghost small">Use all missions instead</button>`;
    chip.querySelector('button').onclick = () => { vedaState.comparisonProducts = null; updateComparison(); };
  }
}

async function updateComparison() {
  renderComparisonSelectionNote();
  const mids = Array.from(vedaState.selectedMissionIdsForBody);
  const statusEl = document.getElementById('veda-comparison-status');
  if (statusEl) statusEl.textContent = vedaState.compareFilter && !vedaState.comparisonProducts
    ? 'Finding, downloading and reading the matching profiles (the first time this can take a minute)...'
    : 'Computing multi-mission composite thermodynamics...';

  try {
    const [compData, exploreData] = await Promise.all([
      api.vedaCompareBody(vedaState.activeBodyId, currentComparisonRequest()),
      api.vedaExploreBody(vedaState.activeBodyId, mids.join(',')),
    ]);

    vedaState.lastComparisonData = compData;
    renderSelectionReport(compData.selection);
    vedaState.currentBodyObservations = exploreData.observations || [];

    renderActiveSubtab();
    renderComparisonTable();

    if (statusEl) {
      const nMissions = new Set((compData.profiles || []).map(p => p.mission_id)).size;
      statusEl.textContent = `Aggregated ${compData.profile_count} sounding${compData.profile_count === 1 ? "" : "s"} from ${nMissions} mission${nMissions === 1 ? "" : "s"}${compData.averaging ? `; ${compData.averaging}; the spread is shown where at least two profiles overlap` : ""}.${compData.vertical_reference_warning ? ` Note: ${compData.vertical_reference_warning}` : ""}`;
    }
  } catch (err) {
    console.error('Failed to compute comparison:', err);
    if (statusEl) statusEl.textContent = `Comparison error: ${err.message}`;
  }
}

function renderActiveSubtab() {
  if (vedaState.bodySubtab === 'map') renderPlanetaryMap(vedaState.planetaryMapProjection || '2d');
  else if (vedaState.bodySubtab === 'cut') renderAltitudeCut();
  else renderComparisonPlot();
}

/**
 * Altitude cut: the compared variable at one level of the common grid, one point per
 * profile, against time, latitude, local time, zenith angle or longitude.  Shows
 * seasonal and latitudinal structure at a fixed height.  The default level is the one
 * covered by most profiles.
 */
function renderAltitudeCut() {
  const plotDiv = document.getElementById('veda-cut-plot');
  const status = document.getElementById('veda-cut-status');
  if (!plotDiv || !window.Plotly) return;
  const data = vedaState.lastComparisonData;
  if (data && data.vertical === 'pressure') {
    if (plotDiv.data) Plotly.purge(plotDiv);
    plotDiv.innerHTML = '<div class="empty-state">The altitude cut works on altitude levels. Set Vertical to Altitude to use it.</div>';
    if (status) status.textContent = '';
    return;
  }
  const grid = (data && data.grid_km) || [];
  const profiles = (data && data.profiles) || [];
  if (!grid.length || !profiles.length) {
    if (plotDiv.data) Plotly.purge(plotDiv);
    plotDiv.innerHTML = '<div class="empty-state">No profiles to cut. Compare some profiles first.</div>';
    if (status) status.textContent = '';
    return;
  }
  const counts = data.profiles_per_level || grid.map((_, k) => profiles.filter(p => p.interpolated_series[k] != null).length);
  const nearest = (z) => grid.reduce((best, g, i) => (Math.abs(g - z) < Math.abs(grid[best] - z) ? i : best), 0);
  let k;
  if (vedaState.cutAltitude == null || !isFinite(vedaState.cutAltitude)) {
    k = counts.indexOf(Math.max(...counts));
  } else {
    k = nearest(vedaState.cutAltitude);
  }

  // What each point is: the variable at one level, a statistic over a layer, or a
  // quantity computed from the whole profile (tropopause, electron density peak ...).
  const diagLabels = data.diagnostic_labels || {};
  const ySel = document.getElementById('veda-cut-y');
  const diagGroup = document.getElementById('veda-cut-diag-group');
  const diagKeys = Object.keys(diagLabels).join(',');
  if (diagGroup && diagGroup.dataset.keys !== diagKeys) {
    diagGroup.innerHTML = '';
    Object.entries(diagLabels).forEach(([key, [label, unit]]) =>
      diagGroup.appendChild(new Option(unit ? `${label} (${unit})` : label, `diag:${key}`)));
    diagGroup.dataset.keys = diagKeys;
    diagGroup.label = diagKeys ? 'From each whole profile' : 'From each whole profile (none for these profiles)';
  }
  let yKey = (ySel && ySel.value) || 'value';
  if (yKey.startsWith('diag:') && !diagLabels[yKey.slice(5)]) {
    yKey = 'value';
    if (ySel) ySel.value = 'value';
  }
  const isLayer = yKey.startsWith('layer_');
  const isDiag = yKey.startsWith('diag:');
  const isAlt = yKey.endsWith('_alt');
  let kTop = k;
  if (isLayer) {
    kTop = (vedaState.cutTop == null || !isFinite(vedaState.cutTop)) ? nearest(grid[k] + 10) : nearest(vedaState.cutTop);
    if (kTop === k) kTop = k + 1 < grid.length ? k + 1 : Math.max(0, k - 1);
  }
  const kLo = Math.min(k, kTop), kHi = Math.max(k, kTop);
  const altInput = document.getElementById('veda-cut-altitude');
  if (altInput && document.activeElement !== altInput) altInput.value = grid[k];
  const topInput = document.getElementById('veda-cut-top');
  if (topInput && document.activeElement !== topInput) topInput.value = grid[kTop];
  const altLabel = document.getElementById('veda-cut-altitude-label');
  if (altLabel) {
    altLabel.style.display = isDiag ? 'none' : '';
    altLabel.firstChild.textContent = isLayer ? 'From (km) ' : 'Altitude (km) ';
  }
  const topLabel = document.getElementById('veda-cut-top-label');
  if (topLabel) topLabel.style.display = isLayer ? '' : 'none';
  const logMean = /geometric/.test(data.averaging || '');
  const yOf = (p) => {
    if (isDiag) {
      const v = (p.diagnostics || {})[yKey.slice(5)];
      return v != null && isFinite(v) ? v : null;
    }
    const s = p.interpolated_series;
    if (!isLayer) return s[k];
    // only profiles covering the whole layer: otherwise their extreme may lie outside their data
    let best = null, bestK = -1, sum = 0;
    for (let i = kLo; i <= kHi; i++) {
      const v = s[i];
      if (v == null) return null;
      sum += logMean ? Math.log(v) : v;
      if (best == null || (yKey.startsWith('layer_max') ? v > best : v < best)) { best = v; bestK = i; }
    }
    if (yKey === 'layer_mean') return logMean ? Math.exp(sum / (kHi - kLo + 1)) : sum / (kHi - kLo + 1);
    return isAlt ? grid[bestK] : best;
  };

  const xKey = document.getElementById('veda-cut-x')?.value || 'time';
  const colorKey = document.getElementById('veda-cut-color')?.value || 'mission';
  const cfg = VARIABLE_CONFIGS[vedaState.selectedCompareVariable] || { axis: vedaState.selectedCompareVariable, units: '' };
  const pUnit = vedaState.selectedCompareVariable === 'pressure_hpa' ? vedaState.unitsPressure : 'hPa';
  const pScale = { bar: 1e-3, Pa: 100 }[pUnit] || 1;
  const varLabel = cleanPlotlyMath(cfg.label || cfg.axis);
  const diag = isDiag ? diagLabels[yKey.slice(5)] : null;
  const yScale = isDiag || isAlt ? 1 : pScale;
  const yTitle = diag ? (diag[1] ? `${diag[0]} (${diag[1]})` : diag[0])
    : isAlt ? 'Altitude (km)' : (pScale === 1 ? cleanPlotlyMath(cfg.axis) : `Pressure (${pUnit})`);
  const layerText = `${grid[kLo]} to ${grid[kHi]} km`;
  const what = diag ? diag[0]
    : isLayer ? `${{ layer_min: 'Minimum', layer_max: 'Maximum', layer_mean: 'Mean',
                     layer_min_alt: 'Altitude of the minimum', layer_max_alt: 'Altitude of the maximum' }[yKey]} of ${varLabel}, ${layerText}`
    : `${varLabel} at ${grid[k]} km`;
  const yUnitText = diag ? (diag[1] ? ` ${diag[1]}` : '') : isAlt ? ' km' : isLayer ? ` (${layerText})` : ` at ${grid[k]} km`;
  const dayOfYear = (t) => {
    const d = new Date(t.length <= 10 ? `${t}T00:00:00Z` : (/[zZ]|[+-]\d\d:?\d\d$/.test(t) ? t : `${t}Z`));
    return isNaN(d) ? null : (d - Date.UTC(d.getUTCFullYear(), 0, 1)) / 86400000 + 1;
  };
  const xOf = (p) => {
    if (xKey === 'time') return p.time_utc ? p.time_utc.replace(/Z$/, '') : null;
    if (xKey === 'season') return p.time_utc ? dayOfYear(p.time_utc) : null;
    return p[xKey] != null && isFinite(p[xKey]) ? p[xKey] : null;
  };
  const groupOf = {};
  (data.groups || []).filter(g => !g.ungrouped).forEach((g, gi) => g.observation_ids.forEach(id => { groupOf[id] = { gi, label: g.label }; }));

  const withY = profiles.map(p => ({ p, x: xOf(p), y: yOf(p) })).filter(o => o.y != null);
  const pts = withY.filter(o => o.x != null);
  const missing = withY.length - pts.length;
  const atEdge = isAlt ? withY.filter(o => o.y === grid[kLo] || o.y === grid[kHi]).length : 0;
  const traces = [];
  const hover = o => `<b>${escHtml((o.p.mission_label || o.p.mission_id).toUpperCase())}</b> ${escHtml(o.p.observation_id)}<br>`
    + `${escHtml(o.p.time_utc || '')}<br>lat ${o.p.latitude != null ? o.p.latitude.toFixed(1) : '?'}°`
    + `, LST ${o.p.lst != null ? o.p.lst.toFixed(1) + ' h' : '?'}, SZA ${o.p.sza != null ? o.p.sza.toFixed(0) + '°' : '?'}`
    + (o.p.ls != null ? `, Ls ${o.p.ls.toFixed(1)}°` : '')
    + `<br>${(o.y * yScale).toPrecision(5)}${yUnitText}`;
  const addTrace = (name, list, marker) => traces.push({
    type: 'scatter', mode: 'markers', name, x: list.map(o => o.x), y: list.map(o => o.y * yScale),
    text: list.map(hover), hovertemplate: '%{text}<extra></extra>',
    marker: { size: 8, line: { width: 0.5, color: 'rgba(0,0,0,0.4)' }, ...marker } });
  if (colorKey === 'latitude' || colorKey === 'lst') {
    const vals = pts.map(o => o.p[colorKey]);
    addTrace(colorKey === 'lst' ? 'Local time' : 'Latitude', pts, {
      color: vals.map(v => (v == null ? NaN : v)), colorscale: colorKey === 'lst' ? 'Portland' : 'RdBu', showscale: true,
      colorbar: { title: { text: colorKey === 'lst' ? 'LST (h)' : 'Latitude (°)' }, thickness: 12, len: 0.7 } });
  } else {
    const keyOf = colorKey === 'group'
      ? (o => (groupOf[o.p.observation_id] ? groupOf[o.p.observation_id].label : 'Not grouped'))
      : (o => (o.p.mission_label || o.p.mission_id).toUpperCase());
    const order = (key) => {
      if (colorKey !== 'group') return 0;
      const g = (data.groups || []).findIndex(x => x.label === key);
      return g < 0 ? Infinity : g;                      // groups in their own order, ungrouped last
    };
    const keys = [...new Set(pts.map(keyOf))].sort((a, b) => order(a) - order(b));
    keys.forEach((key, i) => {
      const list = pts.filter(o => keyOf(o) === key);
      const color = colorKey === 'group'
        ? (groupOf[list[0].p.observation_id] ? paletteColor(groupOf[list[0].p.observation_id].gi + 1) : '#94a3b8')
        : (MISSION_COLORS[key.toLowerCase()] || paletteColor(i));
      addTrace(`${key} (n = ${list.length})`, list, { color });
    });
  }
  const xTitles = { time: 'Time (UTC)', latitude: 'Latitude (°)', lst: 'Local solar time (h)', sza: 'Solar zenith angle (°)',
                    ls: 'Solar longitude Ls (°)', longitude: 'Longitude (°)', season: 'Day of year' };
  const layout = {
    title: { text: `${what} (${pts.length} profile${pts.length === 1 ? '' : 's'})` },
    hovermode: 'closest',
    margin: { l: 75, r: 25, t: 56, b: 60 },
    xaxis: { title: { text: xTitles[xKey] }, type: xKey === 'time' ? 'date' : 'linear',
             ...(xKey === 'lst' ? { range: [0, 24], dtick: 3 } : {}), ...(xKey === 'latitude' ? { range: [-90, 90], dtick: 30 } : {}),
             ...(xKey === 'ls' ? { range: [0, 360], dtick: 30 } : {}) },
    yaxis: { title: { text: yTitle },
             type: (diag ? ['cm^-3', 'J/kg'].includes(diag[1]) : !isAlt && cfg.logScale) ? 'log' : 'linear' },
    legend: { orientation: 'h', y: -0.18 },
  };
  Plotly.newPlot(plotDiv, traces, themedLayout(layout), { responsive: true, displayModeBar: true });
  if (status) {
    status.textContent = (isDiag ? `${withY.length} of ${profiles.length} profiles have this quantity`
      : isLayer ? `${withY.length} of ${profiles.length} profiles cover ${layerText}`
        + (isAlt && atEdge ? ` (${atEdge} with the ${yKey.startsWith('layer_max') ? 'maximum' : 'minimum'} at an edge of the layer: none inside it)` : '')
      : `${counts[k]} of ${profiles.length} profiles reach ${grid[k]} km`)
      + (missing > 0 ? `; ${missing} without ${xTitles[xKey].toLowerCase()} not shown` : '')
      + '. Click a point to open the profile.';
  }
  plotDiv.removeAllListeners?.('plotly_click');
  plotDiv.on?.('plotly_click', (ev) => {
    const pt = ev.points && ev.points[0];
    if (!pt) return;
    const o = pts.find(q => hover(q) === pt.text);
    if (o) document.querySelector(`#veda-comparison-table-body tr[data-obs-id="${CSS.escape(o.p.observation_id)}"] .btn-dive-deep`)?.click();
  });
}

function renderComparisonPlot() {
  const plotDiv = document.getElementById('veda-comparison-plot');
  if (!plotDiv || !window.Plotly) return;

  const raw = vedaState.lastComparisonData;
  const baseCfg = VARIABLE_CONFIGS[vedaState.selectedCompareVariable] || {
    label: vedaState.selectedCompareVariable,
    units: '',
    axis: vedaState.selectedCompareVariable,
  };
  // Pressure arrives in hPa; the quick unit switcher can show it in bar or Pa.
  const pUnit = vedaState.selectedCompareVariable === 'pressure_hpa' ? vedaState.unitsPressure : 'hPa';
  const pScale = { bar: 1e-3, Pa: 100 }[pUnit] || 1;
  const varCfg = pScale === 1 ? baseCfg : { ...baseCfg, units: pUnit, axis: `Pressure (${pUnit})` };
  const rawGrid = raw ? (raw.vertical === 'pressure' ? raw.grid_hpa : raw.grid_km) || [] : [];
  if (!raw || rawGrid.length === 0 || !raw.profile_count) {
    if (plotDiv.data) Plotly.purge(plotDiv);
    // varCfg.label is one of the app's own VARIABLE_CONFIGS labels (sub/sup markup).
    plotDiv.innerHTML = `<div class="empty-state">${
      !raw || !rawGrid.length
        ? 'No profile observations are selected or available for this body. Pick missions above to compare.'
        : `None of the selected observations contain ${cleanPlotlyMath(varCfg.label)}. ` +
          'Choose another variable or add missions that measure it.'
    }</div>`;
    return;
  }

  const sc = a => (pScale === 1 || !Array.isArray(a)) ? a : a.map(v => (v === null ? v : v * pScale));
  const scaled = pScale === 1 ? raw : {
    ...raw,
    composite_mean: sc(raw.composite_mean),
    composite_plus_1sigma: sc(raw.composite_plus_1sigma),
    composite_minus_1sigma: sc(raw.composite_minus_1sigma),
    profiles: (raw.profiles || []).map(pr => ({ ...pr, interpolated_series: sc(pr.interpolated_series) })),
    groups: (raw.groups || []).map(g => ({ ...g, mean: sc(g.mean), plus_1sigma: sc(g.plus_1sigma), minus_1sigma: sc(g.minus_1sigma) })),
  };
  const view = comparisonView(scaled);
  const data = view.data;
  const groupColor = (gi) => paletteColor(gi + 1);
  const groupIndex = {};
  view.groups.forEach((g, gi) => g.observation_ids.forEach(id => { groupIndex[id] = gi; }));

  const traces = [];
  const byPressure = data.vertical === 'pressure';
  const zGrid = byPressure ? data.grid_hpa : data.grid_km;
  const ink = plotColors().ink;

  // Colour each profile by mission (default), by observation date or by
  // tangent-point latitude (continuous scale with a colour bar).
  const profs = (data.profiles || []).filter(p => p.interpolated_series && p.interpolated_series.some(v => v !== null));
  const colorBy = vedaState.compareColorBy || 'mission';
  const numericKey = colorBy === 'time' ? (p => (p.time_utc ? Date.parse(p.time_utc) : null))
    : colorBy === 'latitude' ? (p => p.latitude) : null;
  const vals = numericKey ? profs.map(numericKey).filter(v => v != null && !Number.isNaN(v)) : [];
  const lo = vals.length ? Math.min(...vals) : 0, hi = vals.length ? Math.max(...vals) : 1;
  const VIRIDIS = ['#440154', '#482878', '#3e4989', '#31688e', '#26828e', '#1f9e89', '#35b779', '#6ece58', '#b5de2b', '#fde725'];
  const scaleColor = (v) => VIRIDIS[Math.min(VIRIDIS.length - 1, Math.max(0, Math.round((hi > lo ? (v - lo) / (hi - lo) : 0.5) * (VIRIDIS.length - 1))))];

  // 1. Composite +/- 1 sigma spread
  if (vedaState.compareShowSpread !== false && data.composite_plus_1sigma && data.composite_plus_1sigma.some(v => v !== null)) {
    const lower = { ...orient(data.composite_minus_1sigma, zGrid), type: 'scatter', mode: 'lines',
      line: { width: 0, color: 'transparent' }, showlegend: false, hoverinfo: 'skip' };
    const upper = { ...orient(data.composite_plus_1sigma, zGrid), type: 'scatter', mode: 'lines',
      fill: plotStyle.swapAxes ? 'tonexty' : 'tonextx', fillcolor: 'rgba(56, 189, 248, 0.18)',
      line: { width: 0, color: 'transparent' }, name: '±1σ spread', hoverinfo: 'skip' };
    traces.push(lower, upper);
  }

  // 2. Individual profiles
  profs.forEach((p, i) => {
    const when = (p.time_utc || '').replace('T', ' ').slice(0, 16);
    let color;
    if (numericKey) {
      const v = numericKey(p);
      color = v == null || Number.isNaN(v) ? '#888888' : scaleColor(v);
    } else if (view.groups.length && groupIndex[p.observation_id] != null) {
      color = groupColor(groupIndex[p.observation_id]);      // grouped: profiles take their group's colour
    } else {
      color = plotStyle.palette === 'veda' ? (MISSION_COLORS[(p.mission_label || p.mission_id).toLowerCase()] || paletteColor(i)) : paletteColor(i);
    }
    const who = (p.mission_label || p.mission_id).toUpperCase() + (p.mission_id === 'user_imported' ? ' (your file)' : '');
    const t = { ...orient(p.interpolated_series, zGrid), type: 'scatter',
      name: `${who} ${when || p.observation_id}`,
      hovertemplate: `<b>${who}</b> ${when}<br>${p.observation_id}<br>Lat ${p.latitude != null ? p.latitude.toFixed(1) : '?'}°<br>%{x:.4g}, %{y:.4g}<extra></extra>` };
    const styled = styleTrace(t, i, { color });
    if (view.groups.length) { styled.opacity = 0.3; styled.showlegend = false; }   // grouped: the group means stand out
    traces.push(styled);
  });

  // 2b. Group composites (climatology bins): thick lines with their own spread
  view.groups.forEach((g, gi) => {
    const c = groupColor(gi);
    if (vedaState.compareShowSpread !== false && g.plus_1sigma.some(v => v != null)) {
      traces.push({ ...orient(g.minus_1sigma, zGrid), type: 'scatter', mode: 'lines', line: { width: 0, color: 'transparent' },
        showlegend: false, hoverinfo: 'skip', legendgroup: `g${gi}` });
      traces.push({ ...orient(g.plus_1sigma, zGrid), type: 'scatter', mode: 'lines', fill: plotStyle.swapAxes ? 'tonexty' : 'tonextx',
        fillcolor: c.startsWith('#') && c.length === 7 ? `${c}26` : 'rgba(128,128,128,0.15)', line: { width: 0, color: 'transparent' },
        showlegend: false, hoverinfo: 'skip', legendgroup: `g${gi}` });
    }
    traces.push({ ...orient(g.mean, zGrid), type: 'scatter', mode: 'lines', legendgroup: `g${gi}`,
      line: { color: c, width: plotStyle.lineWidth + 2.5 }, name: `${g.label} (n = ${g.n})`,
      hovertemplate: `<b>${escHtml(g.label)}</b> (n = ${g.n})<br>%{x:.4g}, %{y:.4g}<extra></extra>` });
  });

  // 3. Composite mean
  if (vedaState.compareShowMean !== false && data.composite_mean && data.composite_mean.some(v => v !== null)) {
    traces.push({ ...orient(data.composite_mean, zGrid), type: 'scatter', mode: 'lines',
      line: { color: plotStyle.template === 'journal' ? '#000000' : ink, width: plotStyle.lineWidth + 1.5 },
      name: 'Composite mean', hovertemplate: `<b>Composite mean</b><br>%{x:.4g}, %{y:.4g}<extra></extra>` });
  }

  // Colour bar for the continuous colourings
  if (numericKey && vals.length) {
    const fmt = colorBy === 'time' ? (v => new Date(v).toISOString().slice(0, 10)) : (v => `${v.toFixed(0)}°`);
    traces.push({ x: [null], y: [null], type: 'scatter', mode: 'markers', hoverinfo: 'skip', showlegend: false,
      marker: { color: [lo, hi], cmin: lo, cmax: hi, colorscale: 'Viridis', showscale: true,
        colorbar: { title: { text: colorBy === 'time' ? 'Date' : 'Latitude' }, tickvals: [lo, (lo + hi) / 2, hi],
          ticktext: [fmt(lo), fmt((lo + hi) / 2), fmt(hi)], len: 0.6, thickness: 12 } } });
  }

  // The vertical axis is the comparison grid's coordinate: altitude, or pressure (log, top at top).
  const savedVertical = plotStyle.vertical;
  plotStyle.vertical = byPressure ? 'pressure' : 'altitude';
  const layout = styleLayout({
    title: { text: cleanPlotlyMath(`${(data.body_name || data.body_id || '').toUpperCase()} • ${data.profile_count} profile${data.profile_count === 1 ? '' : 's'} (${varCfg.label})`) },
    hovermode: 'closest',
    margin: { l: 70, r: 25, t: 56, b: 60 },
  }, { xLog: !!varCfg.logScale && !view.deviation,
       varTitle: view.deviation
         ? `Deviation from the ${view.groups.length ? 'group' : 'composite'} mean (${view.logVar ? '%' : cleanPlotlyMath(varCfg.units || '')})`
         : cleanPlotlyMath(varCfg.axis),
       coordTitle: byPressure ? 'Pressure (hPa)' : 'Altitude above reference radius (km)' });
  plotStyle.vertical = savedVertical;

  window.Plotly.newPlot(plotDiv, traces, themedLayout(layout), { responsive: true, displayModeBar: true });
}

function renderComparisonTable() {
  const tbody = document.getElementById('veda-comparison-table-body');
  if (!tbody) return;
  const data = vedaState.lastComparisonData;
  if (!data || !data.profiles || data.profiles.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-muted">No observations selected.</td></tr>';
    return;
  }

  tbody.innerHTML = data.profiles.map(p => `
    <tr data-obs-id="${p.observation_id}" style="cursor: pointer;" title="Click to view details or highlight on planetary map">
      <td><strong>${p.mission_id.toUpperCase()}</strong></td>
      <td><code>${p.observation_id}</code></td>
      <td>${p.instrument}</td>
      <td>${p.time_utc ? p.time_utc.split('T')[0] : 'N/A'}</td>
      <td>${p.latitude != null ? p.latitude.toFixed(1) + '°' : '-'} / ${p.longitude != null ? p.longitude.toFixed(1) + '°' : '-'}</td>
      <td>${p.z_range_km ? `${p.z_range_km[0]} to ${p.z_range_km[1]} km` : '-'}</td>
      <td><button class="ghost small btn-dive-deep" data-mission="${p.mission_id}" data-obs="${p.observation_id}" title="Jump to Mission mode for detailed profile and provenance">🔍 Deep Dive</button></td>
    </tr>
  `).join('');

  // Row click to highlight & deep dive
  tbody.querySelectorAll('tr').forEach(tr => {
    tr.addEventListener('click', (e) => {
      if (e.target.classList.contains('btn-dive-deep')) {
        const mid = e.target.dataset.mission;
        const obsId = e.target.dataset.obs;
        // Switch to Mission Mode
        const btnMission = document.getElementById('btn-mode-mission');
        if (btnMission) {
          btnMission.click();
          loadAndRenderMission(mid).then(() => {
            inspectProfileObservation({ mission_id: mid, observation_id: obsId, instrument: '' });
          });
        }
        return;
      }
      tbody.querySelectorAll('tr').forEach(r => r.classList.remove('selected'));
      tr.classList.add('selected');
    });
  });
}

/**
 * Render 2D Cylindrical or 3D Orthographic Planetary Coordinates Map
 */
export function renderPlanetaryMap(projection = '2d') {
  const mapDiv = document.getElementById('veda-planetary-map');
  if (!mapDiv || !window.Plotly) return;

  const body = vedaState.activeBody || { name: vedaState.activeBodyId };
  const observations = vedaState.currentBodyObservations || [];
  const selectedMids = vedaState.selectedMissionIdsForBody || new Set();

  // Filter observations by selected missions
  const activeObs = observations.filter(o => selectedMids.has(o.mission_id.toLowerCase()));

  const statusEl = document.getElementById('veda-map-status');
  if (statusEl) {
    statusEl.textContent = `${body.name || 'Planetary'} Observation Footprints & Ground Tracks (${activeObs.length} points)`;
  }

  if (activeObs.length === 0) {
    mapDiv.innerHTML = `<div class="empty-state">No observation footprints available for selected missions on ${body.name || 'this body'}.</div>`;
    return;
  }

  // Group by mission
  const byMission = {};
  activeObs.forEach(obs => {
    const mid = obs.mission_id.toLowerCase();
    if (!byMission[mid]) byMission[mid] = [];
    byMission[mid].push(obs);
  });

  if (projection === '2d') {
    // 2D Cylindrical / Equirectangular Projection
    const traces = [];

    // Reference Latitude Bands (Equator & Parallels)
    traces.push({
      x: [-180, 180],
      y: [0, 0],
      type: 'scatter',
      mode: 'lines',
      line: { color: 'rgba(56, 189, 248, 0.4)', width: 1.5, dash: 'dash' },
      name: 'Equator (0°)',
      hoverinfo: 'none',
      showlegend: false,
    });
    traces.push({
      x: [-180, 180],
      y: [30, 30],
      type: 'scatter',
      mode: 'lines',
      line: { color: 'rgba(148, 163, 184, 0.25)', width: 1, dash: 'dot' },
      name: '+30° N Parallel',
      hoverinfo: 'none',
      showlegend: false,
    });
    traces.push({
      x: [-180, 180],
      y: [-30, -30],
      type: 'scatter',
      mode: 'lines',
      line: { color: 'rgba(148, 163, 184, 0.25)', width: 1, dash: 'dot' },
      name: '-30° S Parallel',
      hoverinfo: 'none',
      showlegend: false,
    });

    // Mission Footprint Traces
    Object.entries(byMission).forEach(([mid, obsList]) => {
      const color = MISSION_COLORS[mid] || '#38bdf8';
      const lons = obsList.map(o => o.longitude != null ? (o.longitude > 180 ? o.longitude - 360 : o.longitude) : 0);
      const lats = obsList.map(o => o.latitude != null ? o.latitude : 0);
      const customdata = obsList.map(o => [
        o.observation_id,
        o.instrument,
        o.product,
        o.time_utc || 'N/A',
        o.latitude != null ? o.latitude.toFixed(2) : '-',
        o.longitude != null ? o.longitude.toFixed(2) : '-'
      ]);

      traces.push({
        x: lons,
        y: lats,
        customdata: customdata,
        type: 'scatter',
        mode: 'markers',
        marker: {
          size: 11,
          color: color,
          symbol: 'circle',
          line: { width: 1.8, color: '#ffffff' },
        },
        name: `${mid.toUpperCase()} (${obsList.length})`,
        hovertemplate: `<b>${mid.toUpperCase()}</b><br>ID: %{customdata[0]}<br>Inst: %{customdata[1]}<br>Coords: %{customdata[4]}° Lat, %{customdata[5]}° Lon<br>UTC: %{customdata[3]}<extra></extra>`,
      });
    });

    const layout = {
      title: {
        text: `${(body.name || '').toUpperCase()} &bull; Spatial Distribution of Observations`,
        font: { color: '#e0e0e0', size: 14 },
      },
      paper_bgcolor: 'transparent',
      plot_bgcolor: 'rgba(15, 23, 42, 0.8)',
      font: { color: '#b0bec5', family: 'Segoe UI, sans-serif' },
      xaxis: {
        title: 'Planetary Longitude (deg)',
        range: [-180, 180],
        dtick: 30,
        gridcolor: 'rgba(51, 65, 85, 0.4)',
        zerolinecolor: 'rgba(56, 189, 248, 0.4)',
      },
      yaxis: {
        title: 'Planetary Latitude (deg)',
        range: [-90, 90],
        dtick: 30,
        gridcolor: 'rgba(51, 65, 85, 0.4)',
        zerolinecolor: 'rgba(56, 189, 248, 0.4)',
      },
      legend: {
        orientation: 'h',
        x: 0,
        y: 1.12,
        font: { size: 11 },
      },
      margin: { l: 55, r: 20, t: 65, b: 45 },
      hovermode: 'closest',
    };

    window.Plotly.newPlot(mapDiv, traces, themedLayout(layout), { responsive: true });

  } else {
    // 3D Orthographic Globe Projection
    const traces = [];

    // Sphere Wireframe Parallels
    for (let latDeg = -60; latDeg <= 60; latDeg += 30) {
      const latRad = (latDeg * Math.PI) / 180;
      const r = Math.cos(latRad);
      const z = Math.sin(latRad);
      const px = [], py = [], pz = [];
      for (let lonDeg = 0; lonDeg <= 360; lonDeg += 10) {
        const lonRad = (lonDeg * Math.PI) / 180;
        px.push(r * Math.cos(lonRad));
        py.push(r * Math.sin(lonRad));
        pz.push(z);
      }
      traces.push({
        x: px, y: py, z: pz,
        type: 'scatter3d',
        mode: 'lines',
        line: { color: latDeg === 0 ? 'rgba(56, 189, 248, 0.6)' : 'rgba(148, 163, 184, 0.25)', width: latDeg === 0 ? 3 : 1.5 },
        hoverinfo: 'none',
        showlegend: false,
      });
    }

    // Sphere Wireframe Meridians
    for (let lonDeg = 0; lonDeg < 360; lonDeg += 45) {
      const lonRad = (lonDeg * Math.PI) / 180;
      const px = [], py = [], pz = [];
      for (let latDeg = -90; latDeg <= 90; latDeg += 10) {
        const latRad = (latDeg * Math.PI) / 180;
        px.push(Math.cos(latRad) * Math.cos(lonRad));
        py.push(Math.cos(latRad) * Math.sin(lonRad));
        pz.push(Math.sin(latRad));
      }
      traces.push({
        x: px, y: py, z: pz,
        type: 'scatter3d',
        mode: 'lines',
        line: { color: 'rgba(148, 163, 184, 0.2)', width: 1.5 },
        hoverinfo: 'none',
        showlegend: false,
      });
    }

    // Plot observation markers on 3D globe surface
    Object.entries(byMission).forEach(([mid, obsList]) => {
      const color = MISSION_COLORS[mid] || '#38bdf8';
      const R = 1.03; // slightly elevated above surface
      const px = [], py = [], pz = [];
      const customdata = [];

      obsList.forEach(o => {
        const latRad = ((o.latitude || 0) * Math.PI) / 180;
        const lonRad = ((o.longitude || 0) * Math.PI) / 180;
        px.push(R * Math.cos(latRad) * Math.cos(lonRad));
        py.push(R * Math.cos(latRad) * Math.sin(lonRad));
        pz.push(R * Math.sin(latRad));
        customdata.push([
          o.observation_id,
          o.instrument,
          o.product,
          o.time_utc || 'N/A',
          o.latitude != null ? o.latitude.toFixed(2) : '-',
          o.longitude != null ? o.longitude.toFixed(2) : '-'
        ]);
      });

      traces.push({
        x: px, y: py, z: pz,
        customdata: customdata,
        type: 'scatter3d',
        mode: 'markers',
        marker: {
          size: 6,
          color: color,
          symbol: 'circle',
          line: { width: 1.5, color: '#ffffff' }
        },
        name: `${mid.toUpperCase()} (${obsList.length})`,
        hovertemplate: `<b>${mid.toUpperCase()}</b><br>ID: %{customdata[0]}<br>Inst: %{customdata[1]}<br>Coords: %{customdata[4]}° Lat, %{customdata[5]}° Lon<extra></extra>`,
      });
    });

    const layout = {
      title: {
        text: `${(body.name || '').toUpperCase()} &bull; 3D Planetary Coordinates Globe`,
        font: { color: '#e0e0e0', size: 14 },
      },
      paper_bgcolor: 'transparent',
      font: { color: '#b0bec5', family: 'Segoe UI, sans-serif' },
      scene: {
        xaxis: { title: '', showgrid: false, zeroline: false, showticklabels: false },
        yaxis: { title: '', showgrid: false, zeroline: false, showticklabels: false },
        zaxis: { title: '', showgrid: false, zeroline: false, showticklabels: false },
        camera: { eye: { x: 1.4, y: 1.4, z: 0.8 } },
        aspectratio: { x: 1, y: 1, z: 1 },
      },
      legend: {
        orientation: 'h',
        x: 0,
        y: 1.08,
        font: { size: 11 },
      },
      margin: { l: 0, r: 0, t: 50, b: 0 },
    };

    window.Plotly.newPlot(mapDiv, traces, themedLayout(layout), { responsive: true });
  }

  // Handle marker clicks to highlight in table
  mapDiv.on('plotly_click', (eventData) => {
    if (!eventData || !eventData.points || !eventData.points[0]) return;
    const pt = eventData.points[0];
    const obsId = pt.customdata ? pt.customdata[0] : null;
    if (!obsId) return;

    // Highlight row in comparison table
    const row = document.querySelector(`tr[data-obs-id="${obsId}"]`);
    if (row) {
      document.querySelectorAll('#veda-comparison-table-body tr').forEach(r => r.classList.remove('selected'));
      row.classList.add('selected');
      row.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  });
}

// ==========================================================================
// 2. MISSION EXPLORATION MODE (DEEP DIVE)
// ==========================================================================

function renderMissionsCatalog() {
  const container = document.getElementById('veda-missions-list');
  if (!container) return;
  container.innerHTML = '';

  const filter = vedaState.missionFilter;
  const target = document.getElementById('mission-filter-target')?.value || '';
  const text = (document.getElementById('mission-filter-text')?.value || '').trim().toLowerCase();
  const inCategory = (m, f) => f === 'all' || (f === 'orbiter' ? m.mission_type === 'orbiter'
    : f === 'flyby' ? m.mission_type === 'flyby' : m.mission_type !== 'orbiter' && m.mission_type !== 'flyby');
  const matches = (m) => (!target || (m.primary_targets || []).includes(target) || Object.keys(m.target_encounters || {}).includes(target))
    && (!text || `${m.name} ${m.id} ${m.agency} ${(m.instruments || []).map(i => i.name || i).join(' ')}`.toLowerCase().includes(text));
  const filteredMissions = vedaState.missions.filter(m => inCategory(m, filter) && matches(m));
  // live counts on the category buttons (for the chosen target and search)
  document.querySelectorAll('.mission-filter-btn').forEach(b => {
    const base = b.dataset.label || (b.dataset.label = b.textContent.replace(/\s*\(\d+\)$/, ''));
    b.textContent = `${base} (${vedaState.missions.filter(m => inCategory(m, b.dataset.filter) && matches(m)).length})`;
  });
  if (!filteredMissions.length) container.innerHTML = '<div class="empty-state">No mission matches these filters.</div>';

  filteredMissions.forEach(m => {
    const card = document.createElement('div');
    card.className = `mission-card ${m.id === vedaState.activeMissionId ? 'active' : ''}`;
    card.dataset.missionId = m.id;
    const typeBadge = m.mission_type === 'flyby'
      ? '<span class="badge badge-flyby">Flyby</span>'
      : m.mission_type === 'orbiter'
      ? '<span class="badge badge-orbiter">Orbiter</span>'
      : `<span class="badge badge-constellation">${m.mission_type}</span>`;

    card.innerHTML = `
      <div class="mission-card-top">
        <strong>${m.name}</strong>
        ${typeBadge}
      </div>
      <div class="mission-card-agency">${m.agency} &bull; Launched ${m.launch_date.split('-')[0]}</div>
      <div class="mission-card-targets">Targets: ${(m.primary_targets || []).map(t => t.toUpperCase()).join(', ')}</div>
    `;
    card.addEventListener('click', () => {
      document.querySelectorAll('.mission-card').forEach(el => el.classList.remove('active'));
      card.classList.add('active');
      loadAndRenderMission(m.id);
    });
    container.appendChild(card);
  });
}

export async function loadAndRenderMission(missionId) {
  vedaState.activeMissionId = missionId;
  const mission = await api.vedaMissionDetails(missionId);
  vedaState.activeMission = mission;
  // SPICE: generic and body kernels for this mission, in the background (Settings can turn this off)
  prefetchMission(missionId, (mission.primary_targets || [])[0]);

  // Render Mission Header
  const headEl = document.getElementById('veda-mission-header');
  if (headEl) {
    const typeTag = mission.mission_type === 'flyby'
      ? '<span class="badge badge-flyby">Flyby</span>'
      : '<span class="badge badge-orbiter">Orbiter</span>';
    headEl.innerHTML = `
      <div class="mission-header-top">
        <h2>${mission.name}</h2>
        ${typeTag}
        <span class="badge badge-agency">${mission.agency}</span>
        <span class="badge status-badge status-${mission.mission_status}">${mission.mission_status.toUpperCase()}</span>
        <div class="mission-header-links" style="display:inline-flex; gap:8px; margin-left:auto; flex-wrap:wrap;">
          ${mission.mission_page_url ? `<a href="${mission.mission_page_url}" target="_blank" rel="noopener" class="badge" style="text-decoration:none; background:#1e3a5f; color:#90caf9;">🌐 Official Mission Page ↗</a>` : ''}
          ${(mission.data_page_url || mission.archive_url) ? `<a href="${mission.data_page_url || mission.archive_url}" target="_blank" rel="noopener" class="badge" style="text-decoration:none; background:#2e4c36; color:#a5d6a7;">🗄️ Authoritative Data Archive ↗</a>` : ''}
        </div>
      </div>
      <p class="mission-header-desc" style="line-height:1.6; margin:8px 0 12px 0;">${mission.description}</p>
      <div class="mission-meta-chips">
        <span><strong>Launch:</strong> ${mission.launch_date}</span>
        <span><strong>Archive Node:</strong> <a href="${mission.data_page_url || mission.archive_url}" target="_blank" rel="noopener">${mission.authoritative_archive} ↗</a></span>
        <span><strong>Citation:</strong> <em>${mission.citation}</em></span>
      </div>
    `;
  }

  // Indexing a mission's archive can take seconds; do not hold up whatever opened the mission.
  showMissionArchive(missionId);
}

export async function inspectObservation(obs) {
  vedaState.selectedObservation = obs;
  const isImage = obs.data_type === 'image' || ['LORRI', 'UVI', 'LIR', 'JunoCam', 'ISS'].includes(obs.instrument);

  if (isImage) {
    await inspectImageObservation(obs);
  } else {
    await inspectProfileObservation(obs);
  }
}

/** Open an archive product: profiles in the profile viewer, everything else in the product viewer. */
async function openArchiveProduct(p) {
  prefetchObservation(p);            // spacecraft ephemeris for this date, if automatic downloads are on
  recordProduct(p);                  // for the Cite panel
  if (p.kind === 'profile') {
    recordFeature('derived');
    return inspectProfileObservation({
      mission_id: p.mission_id, observation_id: p.product_id, dataset_id: p.dataset_id,
      instrument: p.instrument, data_type: 'profile', time_utc: p.start_time,
    });
  }
  const viewer = document.getElementById('veda-observation-viewer');
  if (viewer) await showProductViewer(viewer, p);
}

async function inspectProfileObservation(obs) {
  const viewer = document.getElementById('veda-observation-viewer');
  if (!viewer) return;

  try {
    const prof = (obs.altitude_km && (obs.n_points != null || obs.altitude_km.length > 0))
      ? obs
      : (obs.data ? obs.data : await api.vedaProfile(obs.mission_id, obs.observation_id));
    vedaState.currentProfileData = prof;

    // Detect available variables with valid numerical data
    const candidateVars = [
      'temperature_k',
      'electron_density_cm3',
      'pressure_hpa',
      'density',
      'potential_temperature',
      'buoyancy_freq_sq',
      'lapse_rate',
      'dry_adiabatic_lapse_rate',
      'temperature_c',
      'scale_height',
      'h2so4_ppm',
      'absorptivity_db_km',
      'density_measured',
      'number_density_m3',
    ];

    const hasValidData = (k) => {
      let arr = null;
      if (k === 'temperature_k') arr = prof.temperature_k;
      else if (k === 'temperature_c') arr = prof.temperature_c;
      else if (k === 'pressure_hpa') arr = prof.pressure_hpa;
      else if (k === 'electron_density_cm3') arr = prof.electron_density_cm3;
      else if (prof.derived && prof.derived[k]) arr = prof.derived[k];
      return Array.isArray(arr) && arr.length > 0 && arr.some(v => v != null && !isNaN(v));
    };

    let bestVar = candidateVars.find(k => hasValidData(k)) || 'temperature_k';

    const optionsHtml = candidateVars.map(k => {
      const available = hasValidData(k);
      const cfg = VARIABLE_CONFIGS[k] || { label: k, units: '' };
      const selected = (k === bestVar) ? ' selected' : '';
      const disabled = !available ? ' disabled' : '';
      const statusText = available ? '' : ' (not in profile)';
      return `<option value="${k}"${selected}${disabled}>${cfg.label}${statusText}</option>`;
    }).join('');

    const missionTag = (prof.mission_id || 'LOCAL').toUpperCase();
    const bodyTag = (prof.body_id || 'PLANET').toUpperCase();
    const instTag = prof.instrument || 'Sounder';
    const timeTag = prof.time_utc || 'N/A';
    const latStr = prof.latitude != null ? `${prof.latitude.toFixed(2)}°` : 'N/A';
    const lonStr = prof.longitude != null ? `${prof.longitude.toFixed(2)}°` : 'N/A';

    viewer.innerHTML = `
      <div class="profile-viewer-wrap">
        <div class="viewer-toolbar">
          <div class="viewer-title">
            <h3>Observation: <code>${prof.observation_id}</code> &bull; ${instTag} (${bodyTag})</h3>
          </div>
          <div class="toolbar-actions">
            <button type="button" class="btn small ghost" id="btn-plot-style" title="Lines, colours, uncertainty, axes, fonts, journal templates">🎨 Plot style</button>
            <button type="button" class="btn small ghost" id="btn-export-figure" title="Download the plot at journal column width (set in Plot style)">🖼️ Export figure</button>
            <button type="button" class="btn small ghost" id="btn-geometry" title="Orbit, view from Earth, tangent-point map and solar angles (SPICE)">🛰️ Geometry</button>
            ${prof.dataset_id || obs.dataset_id ? '<button type="button" class="btn small ghost" id="btn-all-fields" title="Plot any column of the product against any other">🔬 All fields</button>' : ''}
            ${prof.mission_id ? `
              <a class="btn small primary" href="${api.vedaExportProfileCsvUrl(prof.mission_id, prof.observation_id)}" download>📥 Export CSV</a>
              <a class="btn small ghost" href="${api.vedaExportProfileJsonUrl(prof.mission_id, prof.observation_id)}" download>Structured JSON</a>
            ` : `
              <button class="btn small primary" id="btn-export-local-profile-csv">📥 Export CSV</button>
            `}
          </div>
        </div>

        <div class="diagnostics-bar">
          <div class="diag-chip"><strong>Sounding Points:</strong> ${prof.n_points || 0}</div>
          <div class="diag-chip"><strong>Time UTC:</strong> ${timeTag}</div>
          <div class="diag-chip"><strong>Lat/Lon:</strong> ${latStr}, ${lonStr}</div>
          ${prof.provenance ? `<div class="diag-chip"><strong>Archive:</strong> ${escHtml(prof.provenance.archive_source)}</div>` : ''}
          ${prof.filename ? `<div class="diag-chip"><strong>File:</strong> ${escHtml(prof.filename)}</div>` : ''}
          ${prof.altitude_reference ? `<div class="diag-chip" title="Altitude is measured from ${escHtml(prof.altitude_reference)}"><strong>Altitude from:</strong> ${escHtml(prof.altitude_reference.replace(/ \(.*\)$/, ''))}</div>` : ''}
          ${trackChips(prof)}
        </div>

        <div class="profile-variable-selector-row">
          <label>Plot Variable:
            <select id="veda-profile-var-select">
              ${optionsHtml}
            </select>
          </label>
          <div class="panel-picker" role="group" aria-label="Side-by-side panels">
            <span class="hint">Side-by-side panels:</span>
            ${candidateVars.filter(k => k !== 'temperature_c' && hasValidData(k)).map(k => `
              <label class="inline"><input type="checkbox" data-panel="${k}" ${(vedaState.profilePanels || []).includes(k) ? 'checked' : ''} /> ${(VARIABLE_CONFIGS[k] || { label: k }).label}</label>`).join('')}
          </div>
        </div>

        <!-- Quick Unit Switcher in Profile View -->
        <div class="quick-unit-switcher-card">
          <span class="switcher-label">⚡ Quick Unit Switcher:</span>
          <div class="unit-switcher-group">
            <span class="unit-type-tag">Temperature:</span>
            <div class="pill-group" id="unit-toggle-temp">
              <button type="button" class="unit-pill ${vedaState.unitsTemperature === 'K' ? 'active' : ''}" data-temp-unit="K">Kelvin (K)</button>
              <button type="button" class="unit-pill ${vedaState.unitsTemperature === 'C' ? 'active' : ''}" data-temp-unit="C">Celsius (°C)</button>
            </div>
          </div>
          <div class="unit-switcher-group">
            <span class="unit-type-tag">Pressure:</span>
            <div class="pill-group" id="unit-toggle-pres">
              <button type="button" class="unit-pill ${vedaState.unitsPressure === 'bar' ? 'active' : ''}" data-pres-unit="bar">bar</button>
              <button type="button" class="unit-pill ${vedaState.unitsPressure === 'hPa' ? 'active' : ''}" data-pres-unit="hPa">hPa</button>
              <button type="button" class="unit-pill ${vedaState.unitsPressure === 'Pa' ? 'active' : ''}" data-pres-unit="Pa">Pa</button>
            </div>
          </div>
        </div>

        <div id="veda-single-profile-plot" style="height: 480px; margin-top: 10px;"></div>
        <div id="veda-geometry-box" class="geo-box" hidden></div>
      </div>
    `;

    const varSelect = document.getElementById('veda-profile-var-select');
    if (varSelect) {
      varSelect.value = bestVar;
      varSelect.onchange = () => renderSingleProfilePlot(prof, varSelect.value);
    }

    // Connect Quick Unit Switcher buttons
    const tempPills = viewer.querySelectorAll('#unit-toggle-temp .unit-pill');
    tempPills.forEach(pill => {
      pill.addEventListener('click', () => {
        const u = pill.dataset.tempUnit;
        vedaState.unitsTemperature = u;
        tempPills.forEach(p => p.classList.toggle('active', p.dataset.tempUnit === u));
        let curVar = varSelect ? varSelect.value : bestVar;
        if (curVar === 'temperature_k' || curVar === 'temperature_c' || !hasValidData(curVar)) {
          curVar = u === 'K' ? 'temperature_k' : 'temperature_c';
          if (varSelect) varSelect.value = curVar;
        }
        renderSingleProfilePlot(prof, curVar);
      });
    });

    const presPills = viewer.querySelectorAll('#unit-toggle-pres .unit-pill');
    presPills.forEach(pill => {
      pill.addEventListener('click', () => {
        const u = pill.dataset.presUnit;
        vedaState.unitsPressure = u;
        presPills.forEach(p => p.classList.toggle('active', p.dataset.presUnit === u));
        let curVar = varSelect ? varSelect.value : bestVar;
        if (curVar !== 'pressure_hpa') {
          curVar = 'pressure_hpa';
          if (varSelect) varSelect.value = curVar;
        }
        renderSingleProfilePlot(prof, curVar);
      });
    });

    viewer.querySelectorAll('input[data-panel]').forEach(cb => cb.addEventListener('change', () => {
      vedaState.profilePanels = [...viewer.querySelectorAll('input[data-panel]:checked')].map(x => x.dataset.panel);
      renderSingleProfilePlot(prof, varSelect ? varSelect.value : bestVar);
    }));
    document.getElementById('btn-plot-style')?.addEventListener('click', openPlotStyle);
    document.getElementById('btn-all-fields')?.addEventListener('click', () =>
      showProductViewer(viewer, { dataset_id: prof.dataset_id || obs.dataset_id, product_id: prof.observation_id,
                                  mission_id: prof.mission_id, start_time: prof.time_utc }));
    document.getElementById('btn-geometry')?.addEventListener('click', () => {
      const box = document.getElementById('veda-geometry-box');
      box.hidden = !box.hidden;
      if (!box.hidden) {
        showGeometry(box, { dataset_id: prof.dataset_id || obs.dataset_id, product_id: prof.observation_id });
        box.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
    document.getElementById('btn-export-figure')?.addEventListener('click', () =>
      exportFigure(document.getElementById('veda-single-profile-plot'), `veda_${prof.mission_id || 'profile'}_${prof.observation_id}`));

    const btnLocalExport = document.getElementById('btn-export-local-profile-csv');
    if (btnLocalExport) {
      btnLocalExport.addEventListener('click', () => exportLocalProfileCsv(prof));
    }

    renderSingleProfilePlot(prof, bestVar);
    renderMath(viewer);
  } catch (err) {
    viewer.innerHTML = `<div class="error-box">Failed to load profile: ${err.message}</div>`;
  }
}

function exportLocalProfileCsv(prof) {
  if (!prof) return;
  const z = prof.altitude_km || [];
  const n = z.length;
  if (!n) {
    alert('No data points in profile to export.');
    return;
  }
  const lines = [
    '# VEDA Profile Export',
    `# Observation ID: ${prof.observation_id || 'imported_profile'}`,
    `# Mission: ${prof.mission_id || 'User Imported'}`,
    `# Target Body: ${prof.body_id || 'Unknown'}`,
    `# Instrument: ${prof.instrument || 'Unknown'}`,
    `# Sounding Points: ${n}`,
    '# Software: VEDA (Keshav Aggarwal, 2026), https://github.com/jovian-explorer/VEDA',
    'altitude_km,temperature_k,pressure_hpa,electron_density_cm3,potential_temp_k,lapse_rate_k_per_km,buoyancy_freq_sq'
  ];
  const t = prof.temperature_k || [];
  const p = prof.pressure_hpa || [];
  const ne = prof.electron_density_cm3 || [];
  const pt = (prof.derived && prof.derived.potential_temperature) || [];
  const lr = (prof.derived && prof.derived.lapse_rate) || [];
  const n2 = (prof.derived && prof.derived.buoyancy_freq_sq) || [];

  for (let i = 0; i < n; i++) {
    const alt = z[i] != null ? z[i] : '';
    const temp = t[i] != null ? t[i] : '';
    const pres = p[i] != null ? p[i] : '';
    const ed = ne[i] != null ? ne[i] : '';
    const pot = pt[i] != null ? pt[i] : '';
    const lrate = lr[i] != null ? lr[i] : '';
    const bfq = n2[i] != null ? n2[i] : '';
    lines.push(`${alt},${temp},${pres},${ed},${pot},${lrate},${bfq}`);
  }

  const csvBlob = new Blob([lines.join('\\r\\n')], { type: 'text/csv;charset=utf-8;' });
  const downloadUrl = URL.createObjectURL(csvBlob);
  const a = document.createElement('a');
  a.href = downloadUrl;
  a.download = `${prof.observation_id || 'veda_profile'}_profile.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(downloadUrl);
}

// Values (with 1-sigma when the product has it) for one variable, in the
// units chosen in the quick unit switcher.
function profileSeries(prof, varKey) {
  const cfg = VARIABLE_CONFIGS[varKey] || { label: varKey, units: '', axis: varKey };
  const unc = prof.uncertainty || {};
  let values = null, sigma = null, label = cfg.label, units = cfg.units, axis = cfg.axis, log = !!cfg.logScale;
  if (varKey === 'temperature_k' || varKey === 'temperature_c') {
    const c = vedaState.unitsTemperature === 'C';
    const k = prof.temperature_k || (prof.temperature_c ? prof.temperature_c.map(t => (t != null ? t + 273.15 : null)) : null);
    values = k ? (c ? k.map(t => (t != null ? t - 273.15 : null)) : k) : null;
    sigma = unc.temperature_k || unc.temperature_c || null;
    label = c ? 'Temperature (°C)' : 'Temperature (K)'; units = c ? '°C' : 'K';
    axis = c ? 'Temperature T (°C)' : 'Temperature T (K)'; log = false;
  } else if (varKey === 'pressure_hpa') {
    const f = { bar: 1e-3, Pa: 100 }[vedaState.unitsPressure] || 1;
    const u = { bar: 'bar', Pa: 'Pa' }[vedaState.unitsPressure] || 'hPa';
    values = prof.pressure_hpa ? prof.pressure_hpa.map(p => (p != null ? p * f : null)) : null;
    sigma = unc.pressure_hpa ? unc.pressure_hpa.map(s => (s != null ? s * f : null)) : null;
    label = `Pressure (${u})`; units = u; axis = `Pressure P (${u})`; log = true;
  } else if (varKey === 'electron_density_cm3') {
    values = prof.electron_density_cm3;
    sigma = unc.electron_density_cm3 || null;
  } else if (prof.derived && prof.derived[varKey]) {
    values = prof.derived[varKey];
  }
  const ok = Array.isArray(values) && values.some(v => v != null && !Number.isNaN(v));
  return ok ? { values, sigma, label, units, axis, log, color: cfg.color } : null;
}

function verticalCoordinate(prof) {
  const usePressure = plotStyle.vertical === 'pressure' && Array.isArray(prof.pressure_hpa)
    && prof.pressure_hpa.some(p => p != null && p > 0);
  return usePressure
    ? { coord: prof.pressure_hpa, title: 'Pressure (hPa)', isPressure: true }
    : { coord: prof.altitude_km || [], title: 'Altitude above reference radius (km)', isPressure: false };
}

function trackChips(prof) {
  const t = prof.track || {};
  const rng = (a, d = 1) => {
    const v = (a || []).filter(x => x != null);
    return v.length ? `${Math.min(...v).toFixed(d)} to ${Math.max(...v).toFixed(d)}` : null;
  };
  const chips = [];
  if (rng(t.latitude)) chips.push(`<div class="diag-chip"><strong>Tangent lat:</strong> ${rng(t.latitude)}°</div>`);
  if (rng(t.sza)) chips.push(`<div class="diag-chip"><strong>SZA:</strong> ${rng(t.sza)}°</div>`);
  if (rng(t.lst)) chips.push(`<div class="diag-chip"><strong>Local time:</strong> ${rng(t.lst, 2)} h</div>`);
  const g = prof.geometry || {};
  const how = g.computed ? 'Computed by VEDA from the time and position (no archive value)' : 'From the archive';
  if (!rng(t.lst) && g.lst != null) chips.push(`<div class="diag-chip" title="${how}"><strong>Local time:</strong> ${g.lst.toFixed(2)} h${g.computed ? '*' : ''}</div>`);
  if (!rng(t.sza) && g.sza != null) chips.push(`<div class="diag-chip" title="${how}"><strong>SZA:</strong> ${g.sza.toFixed(1)}°${g.computed ? '*' : ''}</div>`);
  if (g.ls != null) chips.push(`<div class="diag-chip" title="Mars solar longitude: 0 northern spring equinox, 90 summer solstice, 180 autumn, 270 winter"><strong>Ls:</strong> ${g.ls.toFixed(1)}°</div>`);
  if (g.computed && (rng(t.lst) || rng(t.sza))) chips.push(`<div class="diag-chip" title="${how}"><strong>Geometry:</strong> computed*</div>`);
  if (g.label_time) {
    const lt = g.light_time_s ? `; the one-way light time (${(g.light_time_s / 60).toFixed(1)} min) was subtracted` : '';
    chips.push(`<div class="diag-chip" title="The time shown is the measurement at the planet (lowest level), from the archive's per-sample or spacecraft times${lt}. The label or file name gives ${escHtml(g.label_time)}, a ground-station or pass time."><strong>Label time:</strong> ${escHtml(g.label_time)}</div>`);
  }
  return chips.join('');
}

// Plot style drawer: redraws whatever profile/comparison plot is open.
function openPlotStyle() {
  const redraw = (reopen) => {
    const prof = vedaState.currentProfileData;
    const sel = document.getElementById('veda-profile-var-select');
    if (prof && document.getElementById('veda-single-profile-plot')) renderSingleProfilePlot(prof, sel ? sel.value : 'temperature_k');
    if (vedaState.mode === 'body') renderActiveSubtab();
    if (reopen === true) openPlotStyle();
  };
  const target = () => (vedaState.mode === 'body'
    ? { gd: document.getElementById('veda-comparison-plot'), name: `veda_comparison_${vedaState.activeBodyId}` }
    : { gd: document.getElementById('veda-single-profile-plot'), name: 'veda_profile' });
  drawer('Plot style', plotStyleBody(redraw, target));
}

function renderSingleProfilePlot(prof, varKey) {
  const keys = (vedaState.profilePanels && vedaState.profilePanels.length > 1) ? vedaState.profilePanels : [varKey];
  renderProfilePanels(prof, keys);
}

function renderProfilePanels(prof, varKeys) {
  const plotDiv = document.getElementById('veda-single-profile-plot');
  if (!plotDiv || !window.Plotly) return;
  const series = varKeys.map(k => ({ key: k, s: profileSeries(prof, k) })).filter(x => x.s);
  if (!series.length) {
    plotDiv.innerHTML = '<div class="empty-state">This product does not contain the selected variable.</div>';
    return;
  }
  const { coord, title: coordTitle } = verticalCoordinate(prof);
  const n = series.length;
  const gap = n > 1 ? 0.04 : 0;
  const traces = [];
  let layout = {
    title: { text: cleanPlotlyMath(`${(prof.mission_id || 'LOCAL').toUpperCase()} • ${prof.observation_id}${prof.time_utc ? ' • ' + prof.time_utc.replace('T', ' ').slice(0, 19) : ''}`) },
    hovermode: 'closest',
    margin: { l: 70, r: 25, t: 50, b: 60 },
  };
  series.forEach(({ key, s }, i) => {
    const color = n > 1 ? paletteColor(i) : (plotStyle.palette === 'veda' ? (s.color || paletteColor(0)) : paletteColor(0));
    const axisSuffix = i === 0 ? '' : String(i + 1);
    const xa = `x${axisSuffix}`;
    const band = sigmaBand(s.values, coord, s.sigma, color, s.label).map(t => ({ ...t, xaxis: xa, yaxis: 'y' }));
    traces.push(...band);
    const t = { ...orient(s.values, coord), type: 'scatter', name: s.label, xaxis: xa, yaxis: 'y',
      hovertemplate: `%{y:.4g}<br>${s.label}: %{x:.4g}<extra></extra>` };
    traces.push(styleTrace(t, i, { color, sigma: s.sigma }));
    if (i === 0) {
      layout = styleLayout(layout, { xLog: s.log, varTitle: cleanPlotlyMath(s.axis), coordTitle });
    } else {
      const base = plotStyle.swapAxes ? layout.yaxis : layout.xaxis;
      layout[`xaxis${axisSuffix}`] = { ...base, title: { ...base.title, text: cleanPlotlyMath(s.axis) },
        type: plotStyle.xScale === 'auto' ? (s.log ? 'log' : 'linear') : plotStyle.xScale, anchor: 'y', autorange: true, range: undefined };
    }
  });
  if (n > 1 && !plotStyle.swapAxes) {
    const w = (1 - gap * (n - 1)) / n;
    series.forEach((_, i) => {
      const ax = i === 0 ? 'xaxis' : `xaxis${i + 1}`;
      layout[ax] = { ...layout[ax], domain: [i * (w + gap), i * (w + gap) + w] };
    });
  }
  window.Plotly.newPlot(plotDiv, traces, themedLayout(layout), { responsive: true });
}

async function inspectImageObservation(obs) {
  const viewer = document.getElementById('veda-observation-viewer');
  if (!viewer) return;

  try {
    const imgMeta = await api.vedaImageMeta(obs.mission_id, obs.observation_id);
    vedaState.currentImageData = imgMeta;

    viewer.innerHTML = `
    <div class="image-viewer-wrap">
      <div class="viewer-toolbar">
        <h3>Camera Observation: <code>${obs.observation_id}</code> (${obs.instrument})</h3>
        <div class="image-controls-row">
          <label>Stretch:
            <select id="veda-stretch-select">
              <option value="zscale" selected>ZScale (Astronomical)</option>
              <option value="percentile">Percentile (0.5% - 99.5%)</option>
              <option value="linear">Linear</option>
              <option value="log">Logarithmic</option>
              <option value="sqrt">Square Root</option>
              <option value="asinh">Asinh</option>
              <option value="histeq">Histogram Equalized</option>
            </select>
          </label>
          <label>Palette:
            <select id="veda-colormap-select">
              <option value="inferno" selected>Inferno</option>
              <option value="viridis">Viridis</option>
              <option value="plasma">Plasma</option>
              <option value="gray">Grayscale</option>
              <option value="magma">Magma</option>
              <option value="twilight">Twilight</option>
            </select>
          </label>
        </div>
      </div>

      <div class="image-display-grid">
        <div class="image-frame-container">
          <div class="fits-interactive-wrap" id="fits-canvas-wrap">
            <img id="veda-rendered-img" src="${api.vedaImageRenderUrl(obs.mission_id, obs.observation_id, vedaState.imageStretch, vedaState.imageColormap)}" alt="Scientific observation" />
            <canvas class="fits-canvas-overlay" id="fits-drawing-canvas"></canvas>
          </div>
          <div class="pixel-inspector-badge" id="fits-pixel-inspector">
            <span>Cursor:</span> <strong id="fits-cursor-coords">X: - | Y: -</strong>
            <span style="margin-left: auto; color: #64748b;">Click & drag on image to slice transect</span>
          </div>
          <div class="image-meta-strip">
            <span>Filter: ${imgMeta.filter_name || 'Clear'}</span>
            <span>Target Dist: ${imgMeta.target_distance_km ? imgMeta.target_distance_km.toLocaleString() + ' km' : '-'}</span>
            <span>Phase Angle: ${imgMeta.solar_phase_angle_deg ? imgMeta.solar_phase_angle_deg.toFixed(1) + '°' : '-'}</span>
          </div>
        </div>

        <div class="transect-panel">
          <h4>1D Photometric Line Transect</h4>
          <p class="hint">Extract calibrated cross-section intensity along line slice (x₀, y₀) &rarr; (x₁, y₁).</p>
          <div class="row" style="gap: 6px;">
            <button class="small ghost" id="btn-transect-horiz">Equatorial Slice</button>
            <button class="small ghost" id="btn-transect-vert">Meridional Slice</button>
            <button class="small ghost" id="btn-transect-diag">Diagonal Slice</button>
          </div>
          <div id="veda-transect-plot" style="height: 240px; margin-top: 8px;"></div>
          <div id="veda-histogram-plot" style="height: 180px; margin-top: 8px;"></div>
        </div>
      </div>
    </div>
  `;

  // Stretch & colormap change handlers
  const stretchSelect = document.getElementById('veda-stretch-select');
  const cmapSelect = document.getElementById('veda-colormap-select');
  const imgEl = document.getElementById('veda-rendered-img');
  const canvasWrap = document.getElementById('fits-canvas-wrap');
  const overlayCanvas = document.getElementById('fits-drawing-canvas');
  const cursorCoordsEl = document.getElementById('fits-cursor-coords');

  const updateImage = () => {
    vedaState.imageStretch = stretchSelect.value;
    vedaState.imageColormap = cmapSelect.value;
    imgEl.src = api.vedaImageRenderUrl(obs.mission_id, obs.observation_id, vedaState.imageStretch, vedaState.imageColormap);
  };

  if (stretchSelect) stretchSelect.onchange = updateImage;
  if (cmapSelect) cmapSelect.onchange = updateImage;

  // Window-level listeners belong to the image on screen; drop the previous
  // image's ones (they used to pile up with every image opened).
  imageViewerListeners?.abort();
  imageViewerListeners = new AbortController();
  const winOpts = { signal: imageViewerListeners.signal };

  // Interactive Drag-to-Slice Line Transect
  let isDragging = false;
  let startX = 0, startY = 0;

  function resizeOverlay() {
    if (!overlayCanvas || !imgEl) return;
    overlayCanvas.width = imgEl.clientWidth;
    overlayCanvas.height = imgEl.clientHeight;
  }

  function getImgCoords(e) {
    const rect = imgEl.getBoundingClientRect();
    const clientX = Math.max(0, Math.min(rect.width, e.clientX - rect.left));
    const clientY = Math.max(0, Math.min(rect.height, e.clientY - rect.top));
    const origW = imgMeta.shape ? imgMeta.shape[1] : (imgEl.naturalWidth || 512);
    const origH = imgMeta.shape ? imgMeta.shape[0] : (imgEl.naturalHeight || 512);
    const scaleX = origW / rect.width;
    const scaleY = origH / rect.height;
    return {
      canvasX: clientX,
      canvasY: clientY,
      imgX: Math.round(clientX * scaleX),
      imgY: Math.round(clientY * scaleY),
    };
  }

  function drawTransectLine(ix0, iy0, ix1, iy1) {
    if (!overlayCanvas || !imgEl) return;
    const ctx = overlayCanvas.getContext('2d');
    ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
    const rect = imgEl.getBoundingClientRect();
    if (!rect.width || !rect.height) return;

    const origW = imgMeta.shape ? imgMeta.shape[1] : (imgEl.naturalWidth || 512);
    const origH = imgMeta.shape ? imgMeta.shape[0] : (imgEl.naturalHeight || 512);
    const scaleX = rect.width / origW;
    const scaleY = rect.height / origH;

    const cx0 = ix0 * scaleX;
    const cy0 = iy0 * scaleY;
    const cx1 = ix1 * scaleX;
    const cy1 = iy1 * scaleY;

    // Line
    ctx.strokeStyle = '#ffff00';
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.moveTo(cx0, cy0);
    ctx.lineTo(cx1, cy1);
    ctx.stroke();

    // Start handle
    ctx.fillStyle = '#ff1744';
    ctx.beginPath();
    ctx.arc(cx0, cy0, 4.5, 0, Math.PI * 2);
    ctx.fill();

    // End handle
    ctx.fillStyle = '#00e5ff';
    ctx.beginPath();
    ctx.arc(cx1, cy1, 4.5, 0, Math.PI * 2);
    ctx.fill();
  }

  imgEl.onload = () => {
    resizeOverlay();
    drawTransectLine(vedaState.transectCoords.x0, vedaState.transectCoords.y0, vedaState.transectCoords.x1, vedaState.transectCoords.y1);
  };
  window.addEventListener('resize', resizeOverlay, winOpts);

  if (canvasWrap) {
    canvasWrap.addEventListener('mousemove', (e) => {
      const coords = getImgCoords(e);
      if (cursorCoordsEl) {
        cursorCoordsEl.textContent = `X: ${coords.imgX} | Y: ${coords.imgY}`;
      }
      if (isDragging && overlayCanvas) {
        const ctx = overlayCanvas.getContext('2d');
        ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
        ctx.strokeStyle = '#ffff00';
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.moveTo(startX, startY);
        ctx.lineTo(coords.canvasX, coords.canvasY);
        ctx.stroke();
      }
    });

    canvasWrap.addEventListener('mousedown', (e) => {
      isDragging = true;
      const coords = getImgCoords(e);
      startX = coords.canvasX;
      startY = coords.canvasY;
      vedaState.transectCoords.x0 = coords.imgX;
      vedaState.transectCoords.y0 = coords.imgY;
    });

    window.addEventListener('mouseup', (e) => {
      if (!isDragging || !imgEl.isConnected) return;
      isDragging = false;
      const coords = getImgCoords(e);
      vedaState.transectCoords.x1 = coords.imgX;
      vedaState.transectCoords.y1 = coords.imgY;
      drawTransectLine(vedaState.transectCoords.x0, vedaState.transectCoords.y0, vedaState.transectCoords.x1, vedaState.transectCoords.y1);
      loadTransect(obs.mission_id, obs.observation_id, vedaState.transectCoords.x0, vedaState.transectCoords.y0, vedaState.transectCoords.x1, vedaState.transectCoords.y1);
    }, winOpts);
  }

  // Preset transect buttons
  const origW = imgMeta.shape ? imgMeta.shape[1] : 512;
  const origH = imgMeta.shape ? imgMeta.shape[0] : 512;

  document.getElementById('btn-transect-horiz')?.addEventListener('click', () => {
    const midY = Math.round(origH / 2);
    vedaState.transectCoords = { x0: 10, y0: midY, x1: origW - 10, y1: midY };
    drawTransectLine(10, midY, origW - 10, midY);
    loadTransect(obs.mission_id, obs.observation_id, 10, midY, origW - 10, midY);
  });
  document.getElementById('btn-transect-vert')?.addEventListener('click', () => {
    const midX = Math.round(origW / 2);
    vedaState.transectCoords = { x0: midX, y0: 10, x1: midX, y1: origH - 10 };
    drawTransectLine(midX, 10, midX, origH - 10);
    loadTransect(obs.mission_id, obs.observation_id, midX, 10, midX, origH - 10);
  });
  document.getElementById('btn-transect-diag')?.addEventListener('click', () => {
    vedaState.transectCoords = { x0: 20, y0: 20, x1: origW - 20, y1: origH - 20 };
    drawTransectLine(20, 20, origW - 20, origH - 20);
    loadTransect(obs.mission_id, obs.observation_id, 20, 20, origW - 20, origH - 20);
  });

  // Initial load of transect & histogram
  const initMidY = Math.round(origH / 2);
  vedaState.transectCoords = { x0: 10, y0: initMidY, x1: origW - 10, y1: initMidY };
    await Promise.all([
      loadTransect(obs.mission_id, obs.observation_id, 10, initMidY, origW - 10, initMidY),
      loadImageHistogram(obs.mission_id, obs.observation_id),
    ]);
  } catch (err) {
    viewer.innerHTML = `<div class="error-box">Failed to load camera observation: ${err.message}</div>`;
  }
}

async function loadTransect(missionId, obsId, x0, y0, x1, y1) {
  const plotDiv = document.getElementById('veda-transect-plot');
  if (!plotDiv || !window.Plotly) return;

  try {
    const data = await api.vedaImageTransect(missionId, obsId, { x0, y0, x1, y1, num_samples: 120 });
    const trace = {
      x: data.distances_pixels,
      y: data.intensities,
      type: 'scatter',
      mode: 'lines',
      line: { color: '#00e5ff', width: 2.2 },
      name: 'Photometric Intensity',
    };
    const fontScale = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--font-scale') || '1.0');
    const layout = {
      title: { text: cleanPlotlyMath(`Line Slice (${x0},${y0}) &rarr; (${x1},${y1})`), font: { size: Math.round(12 * fontScale), color: '#ffffff' } },
      paper_bgcolor: 'transparent',
      plot_bgcolor: 'rgba(25, 30, 36, 0.6)',
      font: { color: '#b0bec5', size: Math.round(10.5 * fontScale) },
      xaxis: { title: { text: 'Distance Along Slice (px)', font: { size: Math.round(11 * fontScale) } }, gridcolor: '#2a3441' },
      yaxis: { title: { text: 'Intensity', font: { size: Math.round(11 * fontScale) } }, gridcolor: '#2a3441' },
      margin: { l: 45, r: 15, t: 30, b: 35 },
    };
    window.Plotly.newPlot(plotDiv, [trace], themedLayout(layout), { responsive: true, displayModeBar: false });
  } catch (err) {
    plotDiv.innerHTML = `<div class="text-muted" style="padding: 10px;">Transect: ${err.message}</div>`;
  }
}

async function loadImageHistogram(missionId, obsId) {
  const plotDiv = document.getElementById('veda-histogram-plot');
  if (!plotDiv || !window.Plotly) return;

  try {
    const data = await api.vedaImageHistogram(missionId, obsId, 60);
    if (!data.counts || data.counts.length === 0) return;

    const trace = {
      x: data.bins,
      y: data.counts,
      type: 'bar',
      marker: { color: '#ff8a65' },
      name: 'Pixel Counts',
    };
    const fontScale = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--font-scale') || '1.0');
    const layout = {
      title: { text: cleanPlotlyMath('Pixel Intensity Histogram'), font: { size: Math.round(12 * fontScale), color: '#ffffff' } },
      paper_bgcolor: 'transparent',
      plot_bgcolor: 'rgba(25, 30, 36, 0.6)',
      font: { color: '#b0bec5', size: Math.round(10.5 * fontScale) },
      xaxis: { title: { text: 'Pixel Value', font: { size: Math.round(11 * fontScale) } }, gridcolor: '#2a3441' },
      yaxis: { title: { text: 'Count', font: { size: Math.round(11 * fontScale) } }, gridcolor: '#2a3441' },
      margin: { l: 45, r: 15, t: 30, b: 35 },
    };
    window.Plotly.newPlot(plotDiv, [trace], themedLayout(layout), { responsive: true, displayModeBar: false });
  } catch (err) {
    plotDiv.innerHTML = `<div class="text-muted" style="padding: 10px;">Histogram: ${err.message}</div>`;
  }
}

function setupMissionModeControls() {
  const filterBtns = document.querySelectorAll('.mission-filter-btn');
  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      vedaState.missionFilter = btn.dataset.filter;
      renderMissionsCatalog();
    });
  });
  const targetSel = document.getElementById('mission-filter-target');
  if (targetSel) {
    const targets = [...new Set(vedaState.missions.flatMap(m => [...(m.primary_targets || []), ...Object.keys(m.target_encounters || {})]))].sort();
    targetSel.innerHTML = '<option value="">All bodies</option>' + targets.map(t => `<option value="${escHtml(t)}">${escHtml(t[0].toUpperCase() + t.slice(1))}</option>`).join('');
    targetSel.addEventListener('change', renderMissionsCatalog);
  }
  let searchTimer = 0;
  document.getElementById('mission-filter-text')?.addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(renderMissionsCatalog, 150);
  });

}

// ==========================================================================
// 3. WORKFLOW GUIDE & UNIVERSAL FILE INGESTION
// ==========================================================================

function readFileAsText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error || new Error('Failed to read file as text'));
    reader.readAsText(file);
  });
}

function readFileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error || new Error('Failed to read file as base64'));
    reader.readAsDataURL(file);
  });
}

// Keep in sync with SUPPORTED_UPLOAD_SUFFIXES in api/routes.py.
const UPLOAD_EXTENSIONS = ['tab', 'lbl', 'xml', 'csv', 'txt', 'dat', 'asc', 'fit', 'fits', 'fts', 'jpg', 'jpeg', 'png'];
const MAX_COMPANIONS = 8;

function fileExt(file) {
  const parts = file.name.split('.');
  return parts.length > 1 ? parts.pop().toLowerCase() : '';
}

function readUploadContent(file) {
  return /\.(fits?|fts|png|jpe?g)$/i.test(file.name) ? readFileAsBase64(file) : readFileAsText(file);
}

// Entry point for the file picker and drag-and-drop.  A PDS3 label is sent
// together with the other selected files (its .tab table); anything else is
// loaded one file at a time.
export async function handleUploadedFiles(fileList) {
  const files = Array.from(fileList || []);
  if (!files.length) return;
  const unsupported = files.filter(f => !UPLOAD_EXTENSIONS.includes(fileExt(f)));
  if (unsupported.length) {
    toast(`Unsupported format: ${unsupported.map(f => f.name).join(', ')}. ` +
          `Supported: ${UPLOAD_EXTENSIONS.map(e => '.' + e).join(', ')}`, 'bad');
  }
  const usable = files.filter(f => UPLOAD_EXTENSIONS.includes(fileExt(f)));
  if (!usable.length) return;
  // A PDS3 (.lbl) or PDS4 (.xml) label is sent with its data table.
  const label = usable.find(f => fileExt(f) === 'lbl' || fileExt(f) === 'xml');
  if (label) return openLoadDialog(label, usable.filter(f => f !== label).slice(0, MAX_COMPANIONS));
  const images = usable.filter(f => /\.(fits?|fts|png|jpe?g)$/i.test(f.name));
  for (const f of images) await handleUploadedFile(f);
  const tables = usable.filter(f => !images.includes(f));
  if (tables.length) return openLoadDialog(tables[0], [], tables.slice(1));
}

// ------------------------------------------------------------------ load dialog

const ROLE_LABELS = {
  '': 'Not used', altitude: 'Altitude', radius: 'Radius (from the centre)', temperature: 'Temperature',
  temperature_sigma: 'Temperature 1σ', pressure: 'Pressure', pressure_sigma: 'Pressure 1σ',
  electron_density: 'Electron density', electron_density_sigma: 'Electron density 1σ',
  number_density: 'Number density', latitude: 'Latitude', longitude: 'Longitude', lst: 'Local solar time', sza: 'Solar zenith angle',
};

/**
 * Load a table: preview its columns, say what each one is (role and unit) and what
 * the file is (body, mission, instrument, time), then read it.  ``queue`` holds more
 * tables picked together, loaded one after another with the same choices offered.
 */
async function openLoadDialog(file, companions = [], queue = []) {
  let content, comps, pv;
  try {
    content = await readUploadContent(file);
    comps = await Promise.all(companions.map(async c => ({ filename: c.name, file_content: await readUploadContent(c) })));
    pv = await api.vedaPreviewUpload({ filename: file.name, file_content: content, companion_files: comps });
  } catch (err) {
    toast(err.message, 'bad');
    if (queue.length) return openLoadDialog(queue[0], [], queue.slice(1));
    return;
  }
  const sug = pv.suggested || {};
  const prev = vedaState.lastLoadChoice || {};
  const bodyId = sug.body_id || prev.body_id || vedaState.activeBodyId || 'venus';
  const box = document.createElement('form');
  box.className = 'stack settings-form load-dialog';
  const bodyOpts = (vedaState.bodies || []).map(b => `<option value="${escHtml(b.id)}" ${b.id === bodyId ? 'selected' : ''}>${escHtml(b.name)}</option>`).join('');
  const roleOpts = (sel) => Object.entries(ROLE_LABELS).filter(([k]) => k === '' || pv.role_units[k])
    .map(([k, v]) => `<option value="${k}" ${k === sel ? 'selected' : ''}>${escHtml(v)}</option>`).join('');
  const unitOpts = (role, sel) => (pv.role_units[role] || []).map(u => `<option ${u === sel ? 'selected' : ''}>${escHtml(u)}</option>`).join('');
  const labelNote = Object.entries(pv.label || {}).map(([k, v]) => `${escHtml(k)} = ${escHtml(v)}`).join(' · ');
  box.innerHTML = `
    <p class="hint">${escHtml(file.name)}${companions.length ? ` with ${companions.map(c => escHtml(c.name)).join(', ')}` : ''}${queue.length ? ` (${queue.length} more file${queue.length > 1 ? 's' : ''} after this)` : ''}.
      Say what the file is and what each column holds; choices are kept for the next file.</p>
    ${labelNote ? `<p class="hint">From the label: ${labelNote}</p>` : ''}
    <fieldset><legend>What it is</legend>
      <label class="settings-field"><span class="settings-label">Body</span><select name="body">${bodyOpts}</select></label>
      <label class="settings-field"><span class="settings-label">Mission</span><select name="mission"></select></label>
      <label class="settings-field ld-other-mission" hidden><span class="settings-label">Mission name</span><input name="mission_other" placeholder="e.g. Venera 15" /></label>
      <label class="settings-field"><span class="settings-label">Instrument</span><select name="instrument"></select></label>
      <label class="settings-field ld-other-inst" hidden><span class="settings-label">Instrument name</span><input name="instrument_other" placeholder="e.g. radio occultation" /></label>
      <label class="settings-field"><span class="settings-label">Observation time (UTC)</span><input name="time" type="datetime-local" step="1" />
        <span class="hint">Used to place the profile in date searches and comparisons; leave empty if unknown.</span></label>
    </fieldset>
    <fieldset><legend>Columns</legend>
      <div class="ld-cols"><table class="data-table"><thead><tr><th>Column</th><th>Unit in file</th><th>First values</th><th>Range</th><th>Is</th><th>Unit</th></tr></thead>
      <tbody>${pv.columns.map((c, i) => {
        const s = (pv.suggested_roles || {})[c.name] || (prev.roles || {})[c.name] || {};
        return `<tr data-col="${i}"><td><code>${escHtml(c.name)}</code>${c.description ? `<br><span class="hint">${escHtml(c.description)}</span>` : ''}</td>
          <td>${escHtml(c.unit || '')}</td><td class="hint">${c.first.map(v => (v == null ? '-' : v)).join(', ')}</td>
          <td class="hint">${c.min == null ? '' : `${c.min} to ${c.max}`}</td>
          <td><select class="ld-role">${roleOpts(s.role || '')}</select></td>
          <td><select class="ld-unit">${unitOpts(s.role || '', s.unit)}</select></td></tr>`;
      }).join('')}</tbody></table></div>
      <p class="hint">Altitude is measured above the body's reference radius; a radius column is converted to that. Choose at least the vertical coordinate and one measured quantity.</p>
    </fieldset>
    <div class="settings-actions"><button type="submit" class="primary">Load</button>
      ${queue.length ? '<button type="button" class="ghost ld-skip">Skip this file</button>' : ''}</div>
    <div class="hint ld-msg" aria-live="polite"></div>`;
  const q = (s) => box.querySelector(s);
  const fillMissions = () => {
    const b = q('[name=body]').value;
    const ms = (vedaState.missions || []).filter(m => (m.primary_targets || []).includes(b) || Object.keys(m.target_encounters || {}).includes(b));
    const want = sug.mission_id || prev.source_mission || '';
    q('[name=mission]').innerHTML = '<option value="">Not specified</option>' +
      ms.map(m => `<option value="${escHtml(m.id)}" ${m.id === want ? 'selected' : ''}>${escHtml(m.name)}</option>`).join('') +
      '<option value="__other__">Other (not in VEDA)</option>';
    fillInstruments();
  };
  const fillInstruments = () => {
    const m = (vedaState.missions || []).find(x => x.id === q('[name=mission]').value);
    const insts = (m && m.instruments) || [];
    const want = (sug.instrument || prev.instrument || '').toUpperCase();
    const pick = insts.find(i => i.id.toUpperCase() === want || i.name.toUpperCase().includes(want) && want);
    q('[name=instrument]').innerHTML = '<option value="">Not specified</option>' +
      insts.map(i => `<option value="${escHtml(i.id)}" ${pick && pick.id === i.id ? 'selected' : ''}>${escHtml(i.id)}: ${escHtml(i.name)}</option>`).join('') +
      '<option value="__other__">Other</option>';
    q('.ld-other-mission').hidden = q('[name=mission]').value !== '__other__';
    q('.ld-other-inst').hidden = q('[name=instrument]').value !== '__other__';
  };
  q('[name=body]').addEventListener('change', fillMissions);
  q('[name=mission]').addEventListener('change', fillInstruments);
  q('[name=instrument]').addEventListener('change', () => { q('.ld-other-inst').hidden = q('[name=instrument]').value !== '__other__'; });
  fillMissions();
  const t = String(sug.time_utc || '').replace(' ', 'T').replace(/Z$/, '');
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(t)) q('[name=time]').value = t.slice(0, 19);
  box.querySelectorAll('tr[data-col]').forEach(tr => {
    tr.querySelector('.ld-role').addEventListener('change', (e) => {
      const role = e.target.value;
      tr.querySelector('.ld-unit').innerHTML = unitOpts(role, (pv.role_units[role] || [])[0]);
    });
  });
  q('.ld-skip')?.addEventListener('click', () => openLoadDialog(queue[0], [], queue.slice(1)));
  box.addEventListener('submit', async (e) => {
    e.preventDefault();
    const roles = {};
    box.querySelectorAll('tr[data-col]').forEach(tr => {
      const role = tr.querySelector('.ld-role').value;
      if (role) roles[pv.columns[+tr.dataset.col].name] = { role, unit: tr.querySelector('.ld-unit').value || null };
    });
    const used = Object.values(roles).map(r => r.role);
    const dup = used.find((r, i) => used.indexOf(r) !== i);
    const msg = q('.ld-msg');
    if (dup) { msg.textContent = `Two columns are marked as ${ROLE_LABELS[dup]}; choose one.`; return; }
    if (!used.includes('altitude') && !used.includes('radius')) { msg.textContent = 'Mark the column that holds altitude or radius.'; return; }
    const mission = q('[name=mission]').value === '__other__' ? q('[name=mission_other]').value.trim() : q('[name=mission]').value;
    const instSel = q('[name=instrument]').value;
    const instrument = instSel === '__other__' ? q('[name=instrument_other]').value.trim() : instSel;
    const time = q('[name=time]').value;
    vedaState.lastLoadChoice = { body_id: q('[name=body]').value, source_mission: mission, instrument, roles };
    msg.textContent = 'Reading...';
    try {
      const res = await api.vedaParseFile({
        filename: file.name, file_content: content, companion_files: comps, body_id: q('[name=body]').value,
        source_mission: mission || null, instrument: instrument || null, time_utc: time ? `${time}${time.length === 16 ? ':00' : ''}` : null, roles,
      });
      const profData = res.data || res;
      toast(`Loaded ${file.name} (${profData.n_points || 0} levels)`, 'good');
      closeDrawer();
      switchMode('mission');
      await inspectProfileObservation(profData);
      document.getElementById('veda-observation-viewer')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      if (queue.length) openLoadDialog(queue[0], [], queue.slice(1));
    } catch (err) {
      msg.textContent = err.message;
    }
  });
  drawer(`Load ${file.name}`, box);
}

export async function handleUploadedFile(file, companions = []) {
  if (!file) return;
  toast(`Parsing ${file.name}...`);
  try {
    const payload = {
      filename: file.name,
      file_content: await readUploadContent(file),
      body_id: vedaState.activeBodyId || 'venus',
      companion_files: await Promise.all(companions.map(async c => ({
        filename: c.name,
        file_content: await readUploadContent(c),
      }))),
    };

    const res = await api.vedaParseFile(payload);

    if (res.type === 'image') {
      toast(`Successfully parsed image ${file.name}`, 'good');
      switchMode('mission');
      await inspectImageObservation(res);
      const viewer = document.getElementById('veda-observation-viewer');
      if (viewer) viewer.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else if (res.type === 'profile' || res.data) {
      const profData = res.data || res;
      const nPts = profData.n_points || (profData.altitude_km ? profData.altitude_km.length : 0);
      toast(`Successfully parsed ${file.name} (${nPts} levels)`, 'good');
      switchMode('mission');
      await inspectProfileObservation(profData);
      const viewer = document.getElementById('veda-observation-viewer');
      if (viewer) viewer.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else {
      toast(`Could not parse file: ${res.detail || 'Unknown format'}`, 'bad');
    }
  } catch (err) {
    console.error('File load error:', err);
    // Server messages already name the file and say what to do next.
    toast(err.message, 'bad');
  }
}

export function setupWorkflowGuideInteractions() {
  const fileInput = document.getElementById('veda-file-input');
  const btnLoadFile = document.getElementById('btn-load-file');
  if (btnLoadFile && fileInput) {
    btnLoadFile.addEventListener('click', () => fileInput.click());
  }
  if (fileInput) {
    fileInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files.length) {
        handleUploadedFiles(e.target.files);
        fileInput.value = '';
      }
    });
  }

  // Drag and Drop Zone in Guide
  const dropZone = document.getElementById('guide-drag-drop-zone');
  if (dropZone && fileInput) {
    dropZone.addEventListener('click', () => fileInput.click());
    dropZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropZone.classList.add('drag-active');
    });
    dropZone.addEventListener('dragleave', () => {
      dropZone.classList.remove('drag-active');
    });
    dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      e.stopPropagation();  // the window-level drop handler would load the files again
      dropZone.classList.remove('drag-active');
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
        handleUploadedFiles(e.dataTransfer.files);
      }
    });
  }

  // Guide Action Buttons
  document.querySelectorAll('[data-guide-action]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const action = btn.dataset.guideAction;
      switch (action) {
        // Interactive Demonstration Profiles
        case 'demo-akatsuki':
          switchMode('mission');
          await loadAndRenderMission('akatsuki');
          await inspectProfileObservation({
            mission_id: 'akatsuki',
            observation_id: 'rs_20160303_223100_udsc64_l4_ae_v10',
            instrument: 'RS'
          });
          toast('Loaded Akatsuki Venus Radio Occultation Sounding (VCO)', 'good');
          {
            const viewer = document.getElementById('veda-observation-viewer');
            if (viewer) viewer.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }
          break;
        case 'mode-body':
          switchMode('body');
          break;
        case 'mode-mission':
        case 'browse-missions':
          switchMode('mission');
          break;
        case 'open-archive': {
          switchMode('mission');
          document.getElementById('veda-archive-browser')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
          break;
        }
        case 'trigger-file-input':
        case 'click-file-input':
          if (fileInput) fileInput.click();
          break;
        case 'load-sample-akatsuki':
          switchMode('mission');
          await loadAndRenderMission('akatsuki');
          await inspectProfileObservation({
            mission_id: 'akatsuki',
            observation_id: 'rs_20160303_223100_udsc64_l4_ae_v10',
            instrument: 'RS'
          });
          toast('Loaded Akatsuki Venus Radio Occultation Sounding (VCO)', 'good');
          break;
        case 'demo-mex':
        case 'demo-mex-ion': {
          const ion = action === 'demo-mex-ion';
          switchMode('mission');
          await loadAndRenderMission('mex');
          await inspectProfileObservation({
            mission_id: 'mex', instrument: 'MaRS (Radio Science)', data_type: 'profile',
            observation_id: ion ? 'M32ICL2L04_IIX_040931105_60' : 'M32ICL2L04_AIX_040931105_60',
          });
          break;
        }
        case 'archive-akatsuki':
        case 'archive-mex': {
          switchMode('mission');
          await loadAndRenderMission(action === 'archive-mex' ? 'mex' : 'akatsuki');
          document.getElementById('veda-archive-browser')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
          toast('Pick a date range and product type, tick profiles, then Download or Compare selected', 'good');
          break;
        }
        case 'inspect-active-profile': {
          switchMode('mission');
          const res = await api.vedaExploreMission(vedaState.activeMissionId);
          const first = (res.observations || []).find(o => o.data_type === 'profile');
          if (first) await inspectProfileObservation(first);
          else toast('No downloaded profiles for this mission yet; use the archive table to download some', 'bad');
          break;
        }
        case 'help-drawer': {
          const btnHelp = document.getElementById('btn-help');
          if (btnHelp) btnHelp.click();
          break;
        }
        case 'load-fits-akatsuki':
          switchMode('mission');
          await loadAndRenderMission('akatsuki');
          await inspectImageObservation({
            mission_id: 'akatsuki',
            observation_id: 'uvi_20181105_080112_283_geo_v10',
            instrument: 'UVI'
          });
          break;
        case 'about-drawer': {
          const btnAbout = document.getElementById('btn-about');
          if (btnAbout) btnAbout.click();
          break;
        }
        case 'vars-drawer': {
          const btnVars = document.getElementById('btn-veda-vars');
          if (btnVars) btnVars.click();
          break;
        }
        case 'data-policy-drawer': {
          const btnDataPolicy = document.getElementById('btn-veda-data-policy');
          if (btnDataPolicy) btnDataPolicy.click();
          break;
        }
        default:
          console.warn('Unknown guide action:', action);
      }
    });
  });
}

export function setupGlobalDragAndDrop() {
  const overlay = document.getElementById('veda-drag-drop-overlay');
  let dragCounter = 0;

  window.addEventListener('dragenter', (e) => {
    e.preventDefault();
    dragCounter++;
    if (overlay && dragCounter > 0) {
      overlay.classList.remove('hidden');
      overlay.setAttribute('aria-hidden', 'false');
    }
  });

  window.addEventListener('dragover', (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
  });

  window.addEventListener('dragleave', (e) => {
    e.preventDefault();
    dragCounter = Math.max(0, dragCounter - 1);
    if (overlay && dragCounter === 0) {
      overlay.classList.add('hidden');
      overlay.setAttribute('aria-hidden', 'true');
    }
  });

  window.addEventListener('drop', (e) => {
    e.preventDefault();
    dragCounter = 0;
    if (overlay) {
      overlay.classList.add('hidden');
      overlay.setAttribute('aria-hidden', 'true');
    }

    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleUploadedFiles(e.dataTransfer.files);
    }
  });
}
