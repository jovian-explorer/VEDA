/**
 * VEDA: Visualization, Exploration, and Data Analysis
 * Dedicated Planetary Science Laboratory Workstation Controller
 */
import { api } from './api.js';
import { renderMath, toast } from './ui.js';

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
  lastComparisonData: null,
  bodySubtab: 'soundings', // 'soundings' | 'map'
  planetaryMapProjection: '2d', // '2d' | '3d'
  currentBodyObservations: [],
  // Mission Mode State
  activeMissionId: 'new_horizons',
  activeMission: null,
  missionFilter: 'all', // 'all' | 'orbiter' | 'flyby' | 'other'
  missionObservations: [],
  selectedObservation: null,
  currentProfileData: null,
  currentImageData: null,
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
  potential_temperature: { label: 'Potential Temp (θ)', units: 'K', axis: 'Potential Temperature θ (K)', color: '#81c784' },
  buoyancy_freq_sq: { label: 'Brunt-Väisälä (N²)', units: 'rad²/s²', axis: 'Buoyancy Freq Squared N² (rad²/s²)', color: '#ffb300' },
  density: { label: 'Mass Density (ρ)', units: 'kg/m³', axis: 'Mass Density ρ (kg/m³)', logScale: true, color: '#4db6ac' },
  scale_height: { label: 'Scale Height (H)', units: 'km', axis: 'Scale Height H (km)', color: '#90caf9' },
  electron_density_cm3: { label: 'Electron Density (Ne)', units: 'cm⁻³', axis: 'Electron Density Ne (cm⁻³)', logScale: true, color: '#f06292' },
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

/**
 * Initialize VEDA UI and event handlers
 */
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

  // Setup DOM Event Listeners
  setupModeSwitching();
  setupBodyModeControls();
  setupMissionModeControls();
  setupWorkflowGuideInteractions();

  // Render Initial View
  renderCelestialBodiesGrid();
  renderMissionsCatalog();
  await loadAndRenderCelestialBody(vedaState.activeBodyId);
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
  } else if (mode === 'mission') {
    if (!vedaState.activeMission) {
      loadAndRenderMission(vedaState.activeMissionId);
    }
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
        <div class="body-card-sub">${(b.supported_missions || []).length} missions &bull; ${b.surface_gravity.toFixed(2)} m/s²</div>
      </div>
    `;
    card.addEventListener('click', async () => {
      document.querySelectorAll('.body-selector-card').forEach(el => el.classList.remove('active'));
      card.classList.add('active');
      await loadAndRenderCelestialBody(b.id);
    });
    grid.appendChild(card);
  });
}

export async function loadAndRenderCelestialBody(bodyId) {
  vedaState.activeBodyId = bodyId;
  const bodyDetails = await api.vedaBodyDetails(bodyId);
  vedaState.activeBody = bodyDetails;

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
        <div class="phys-badge"><strong>Gravity g₀:</strong> ${bodyDetails.surface_gravity} m/s²</div>
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
      const encBadge = m.encounter_type === 'flyby' ? '<span class="badge badge-flyby">Flyby</span>' : '<span class="badge badge-orbiter">Orbiter</span>';
      label.innerHTML = `
        <input type="checkbox" value="${m.id}" ${isChecked ? 'checked' : ''}>
        <span class="checkbox-box"></span>
        <span class="mission-name-span">${m.name}</span>
        ${encBadge}
        <span class="mission-instruments-hint">${(m.instruments || []).slice(0, 3).join(', ')}</span>
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

function setupBodyModeControls() {
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

  const btnExportCsv = document.getElementById('veda-btn-export-comparison-csv');
  if (btnExportCsv) {
    btnExportCsv.addEventListener('click', async () => {
      try {
        const mids = Array.from(vedaState.selectedMissionIdsForBody);
        const res = await fetch(`/api/veda/export/compare/${vedaState.activeBodyId}/csv`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            missions: mids,
            variable: vedaState.selectedCompareVariable,
          }),
        });
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `veda_comparison_${vedaState.activeBodyId}_${vedaState.selectedCompareVariable}.csv`;
        a.click();
      } catch (e) {
        alert(`Export failed: ${e.message}`);
      }
    });
  }

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

  // Publication Figure Generator (DPI 300)
  const btnPubFig = document.getElementById('veda-btn-download-publication-fig');
  if (btnPubFig) {
    btnPubFig.addEventListener('click', () => {
      const mids = Array.from(vedaState.selectedMissionIdsForBody).join(',');
      const url = api.vedaPublicationFigureUrl(vedaState.activeBodyId, vedaState.selectedCompareVariable, mids, 300, 'png');
      const a = document.createElement('a');
      a.href = url;
      a.download = `veda_publication_${vedaState.activeBodyId}_${vedaState.selectedCompareVariable}.png`;
      a.target = '_blank';
      a.click();
    });
  }

  // Subtab Switching (Soundings vs Planetary Map)
  const btnSubtabSoundings = document.getElementById('btn-subtab-soundings');
  const btnSubtabMap = document.getElementById('btn-subtab-map');
  const soundingsPanel = document.getElementById('veda-subtab-soundings-panel');
  const mapPanel = document.getElementById('veda-subtab-map-panel');

  if (btnSubtabSoundings && btnSubtabMap) {
    btnSubtabSoundings.addEventListener('click', () => {
      vedaState.bodySubtab = 'soundings';
      btnSubtabSoundings.classList.add('active');
      btnSubtabMap.classList.remove('active');
      if (soundingsPanel) soundingsPanel.style.display = 'flex';
      if (mapPanel) mapPanel.style.display = 'none';
      renderComparisonPlot();
    });

    btnSubtabMap.addEventListener('click', () => {
      vedaState.bodySubtab = 'map';
      btnSubtabMap.classList.add('active');
      btnSubtabSoundings.classList.remove('active');
      if (soundingsPanel) soundingsPanel.style.display = 'none';
      if (mapPanel) mapPanel.style.display = 'flex';
      renderPlanetaryMap(vedaState.planetaryMapProjection || '2d');
    });
  }

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

async function updateComparison() {
  const mids = Array.from(vedaState.selectedMissionIdsForBody);
  const statusEl = document.getElementById('veda-comparison-status');
  if (statusEl) statusEl.textContent = 'Computing multi-mission composite thermodynamics...';

  try {
    const [compData, exploreData] = await Promise.all([
      api.vedaCompareBody(vedaState.activeBodyId, {
        missions: mids,
        variable: vedaState.selectedCompareVariable,
      }),
      api.vedaExploreBody(vedaState.activeBodyId, mids.join(',')),
    ]);

    vedaState.lastComparisonData = compData;
    vedaState.currentBodyObservations = exploreData.observations || [];

    if (vedaState.bodySubtab === 'map') {
      renderPlanetaryMap(vedaState.planetaryMapProjection || '2d');
    } else {
      renderComparisonPlot();
    }
    renderComparisonTable();

    if (statusEl) {
      statusEl.textContent = `Aggregated ${compData.profile_count} soundings across ${mids.length} missions.`;
    }
  } catch (err) {
    console.error('Failed to compute comparison:', err);
    if (statusEl) statusEl.textContent = `Comparison error: ${err.message}`;
  }
}

function renderComparisonPlot() {
  const plotDiv = document.getElementById('veda-comparison-plot');
  if (!plotDiv || !window.Plotly) return;

  const data = vedaState.lastComparisonData;
  if (!data || !data.grid_km || data.grid_km.length === 0) {
    plotDiv.innerHTML = '<div class="empty-state">No profile observations selected or available for this body.</div>';
    return;
  }

  const varCfg = VARIABLE_CONFIGS[vedaState.selectedCompareVariable] || {
    label: vedaState.selectedCompareVariable,
    units: '',
    axis: vedaState.selectedCompareVariable,
  };

  const traces = [];
  const zGrid = data.grid_km;

  // 1. Shaded +/- 1 sigma confidence envelope
  if (data.composite_plus_1sigma && data.composite_minus_1sigma && data.composite_plus_1sigma.some(v => v !== null)) {
    traces.push({
      x: data.composite_minus_1sigma,
      y: zGrid,
      type: 'scatter',
      mode: 'lines',
      line: { width: 0, color: 'transparent' },
      name: '-1σ Lower Bound',
      showlegend: false,
      hoverinfo: 'skip',
    });
    traces.push({
      x: data.composite_plus_1sigma,
      y: zGrid,
      type: 'scatter',
      mode: 'lines',
      fill: 'tonexty',
      fillcolor: 'rgba(255, 255, 255, 0.12)',
      line: { width: 0, color: 'transparent' },
      name: '±1σ Multi-Mission Spread',
      showlegend: true,
      hoverinfo: 'skip',
    });
  }

  // 2. Individual mission traces
  (data.profiles || []).forEach(p => {
    if (p.interpolated_series && p.interpolated_series.some(v => v !== null)) {
      const mColor = MISSION_COLORS[p.mission_id.toLowerCase()] || '#80deea';
      traces.push({
        x: p.interpolated_series,
        y: zGrid,
        type: 'scatter',
        mode: 'lines',
        line: { color: mColor, width: 1.8, dash: 'dot' },
        name: `${p.mission_id.toUpperCase()} (${p.instrument})`,
        hovertemplate: `<b>${p.mission_id.toUpperCase()}</b><br>Alt: %{y:.1f} km<br>${varCfg.label}: %{x:.2f} ${varCfg.units}<extra></extra>`,
      });
    }
  });

  // 3. Thick composite mean trace
  if (data.composite_mean && data.composite_mean.some(v => v !== null)) {
    traces.push({
      x: data.composite_mean,
      y: zGrid,
      type: 'scatter',
      mode: 'lines',
      line: { color: '#ffffff', width: 3.5 },
      name: 'Composite Mean μ(z)',
      hovertemplate: `<b>Composite Mean</b><br>Alt: %{y:.1f} km<br>${varCfg.label}: %{x:.2f} ${varCfg.units}<extra></extra>`,
    });
  }

  const layout = {
    title: {
      text: `${data.body_name.toUpperCase()} &bull; Multi-Mission Cross-Comparison (${varCfg.label})`,
      font: { color: '#e0e0e0', size: 15 },
    },
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'rgba(25, 30, 36, 0.6)',
    font: { color: '#b0bec5', family: 'Segoe UI, sans-serif' },
    xaxis: {
      title: varCfg.axis,
      gridcolor: '#2a3441',
      zerolinecolor: '#37474f',
      type: varCfg.logScale ? 'log' : 'linear',
    },
    yaxis: {
      title: 'Altitude Above Reference Surface (km)',
      gridcolor: '#2a3441',
      zerolinecolor: '#37474f',
    },
    legend: {
      orientation: 'h',
      x: 0,
      y: 1.12,
      font: { size: 11 },
    },
    margin: { l: 65, r: 25, t: 70, b: 55 },
    hovermode: 'closest',
  };

  const config = { responsive: true, displayModeBar: true };
  window.Plotly.newPlot(plotDiv, traces, layout, config);
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

    window.Plotly.newPlot(mapDiv, traces, layout, { responsive: true });

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

    window.Plotly.newPlot(mapDiv, traces, layout, { responsive: true });
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
  const filteredMissions = vedaState.missions.filter(m => {
    if (filter === 'all') return true;
    if (filter === 'orbiter') return m.mission_type === 'orbiter';
    if (filter === 'flyby') return m.mission_type === 'flyby';
    if (filter === 'other') return m.mission_type !== 'orbiter' && m.mission_type !== 'flyby';
    return true;
  });

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

  // Populate Instruments Selector
  const instSelect = document.getElementById('veda-instrument-select');
  if (instSelect) {
    instSelect.innerHTML = '<option value="">-- All Instruments --</option>' +
      (mission.instruments || []).map(inst => `
        <option value="${inst.id}">${inst.name} (${inst.type})</option>
      `).join('');
    instSelect.onchange = () => loadMissionObservations();
  }

  await loadMissionObservations();
}

async function loadMissionObservations() {
  const instSelect = document.getElementById('veda-instrument-select');
  const instId = instSelect ? instSelect.value : null;

  try {
    const res = await api.vedaExploreMission(vedaState.activeMissionId, null, instId);
    vedaState.missionObservations = res.observations || [];
    renderObservationsTable();

    // Auto-select first observation if available
    if (vedaState.missionObservations.length > 0) {
      await inspectObservation(vedaState.missionObservations[0]);
    } else {
      const viewer = document.getElementById('veda-observation-viewer');
      if (viewer) viewer.innerHTML = '<div class="empty-state">No observations recorded for this filter.</div>';
    }
  } catch (err) {
    console.error('Failed to load observations:', err);
  }
}

function renderObservationsTable() {
  const tbody = document.getElementById('veda-observations-table-body');
  if (!tbody) return;

  if (vedaState.missionObservations.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" class="text-muted">No observations found.</td></tr>';
    return;
  }

  tbody.innerHTML = vedaState.missionObservations.map((obs, idx) => `
    <tr class="obs-row ${idx === 0 ? 'selected' : ''}" data-obs-id="${obs.observation_id}">
      <td><strong>${obs.observation_id}</strong></td>
      <td>${obs.instrument}</td>
      <td>${obs.body_id.toUpperCase()}</td>
      <td>${obs.time_utc ? obs.time_utc.split('T')[0] : '-'}</td>
      <td><button class="small ghost btn-inspect-obs">Inspect</button></td>
    </tr>
  `).join('');

  tbody.querySelectorAll('tr').forEach((row, i) => {
    row.addEventListener('click', async () => {
      tbody.querySelectorAll('tr').forEach(r => r.classList.remove('selected'));
      row.classList.add('selected');
      await inspectObservation(vedaState.missionObservations[i]);
    });
  });
}

export async function inspectObservation(obs) {
  vedaState.selectedObservation = obs;
  const isImage = obs.instrument === 'LORRI' || obs.instrument === 'UVI' || obs.instrument === 'LIR' || obs.instrument === 'JunoCam' || obs.instrument === 'ISS';

  if (isImage) {
    await inspectImageObservation(obs);
  } else {
    await inspectProfileObservation(obs);
  }
}

async function inspectProfileObservation(obs) {
  const viewer = document.getElementById('veda-observation-viewer');
  if (!viewer) return;

  try {
    const prof = (obs.altitude_km && obs.n_points != null)
      ? obs
      : await api.vedaProfile(obs.mission_id, obs.observation_id);
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
      'temperature_c',
      'scale_height',
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
          ${prof.provenance ? `<div class="diag-chip"><strong>Archive:</strong> ${prof.provenance.archive_source}</div>` : ''}
          ${prof.filename ? `<div class="diag-chip"><strong>File:</strong> ${prof.filename}</div>` : ''}
        </div>

        <div class="profile-variable-selector-row">
          <label>Plot Variable:
            <select id="veda-profile-var-select">
              ${optionsHtml}
            </select>
          </label>
        </div>

        <div id="veda-single-profile-plot" style="height: 480px; margin-top: 10px;"></div>
      </div>
    `;

    const varSelect = document.getElementById('veda-profile-var-select');
    if (varSelect) {
      varSelect.value = bestVar;
      varSelect.onchange = () => renderSingleProfilePlot(prof, varSelect.value);
    }

    const btnLocalExport = document.getElementById('btn-export-local-profile-csv');
    if (btnLocalExport) {
      btnLocalExport.addEventListener('click', () => exportLocalProfileCsv(prof));
    }

    renderSingleProfilePlot(prof, bestVar);
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
    '# Software: VEDA (Keshav Aggarwal, SPL, VSSC, ISRO 2026)',
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

function renderSingleProfilePlot(prof, varKey) {
  const plotDiv = document.getElementById('veda-single-profile-plot');
  if (!plotDiv || !window.Plotly) return;

  const z = prof.altitude_km || [];
  let series = null;

  if (varKey === 'temperature_k') series = prof.temperature_k;
  else if (varKey === 'temperature_c') series = prof.temperature_c;
  else if (varKey === 'pressure_hpa') series = prof.pressure_hpa;
  else if (varKey === 'electron_density_cm3') series = prof.electron_density_cm3;
  else if (prof.derived && prof.derived[varKey]) series = prof.derived[varKey];

  if (!series || series.length === 0) {
    plotDiv.innerHTML = '<div class="empty-state">Variable not present in this observation profile.</div>';
    return;
  }

  const varCfg = VARIABLE_CONFIGS[varKey] || { label: varKey, units: '', axis: varKey, color: '#ff7043' };

  const trace = {
    x: series,
    y: z,
    type: 'scatter',
    mode: 'lines+markers',
    marker: { size: 3.5, color: varCfg.color },
    line: { color: varCfg.color, width: 2.2 },
    name: varCfg.label,
    hovertemplate: `Alt: %{y:.1f} km<br>${varCfg.label}: %{x:.2f} ${varCfg.units}<extra></extra>`,
  };

  const layout = {
    title: {
      text: `${(prof.mission_id || 'LOCAL').toUpperCase()} &bull; ${prof.observation_id} (${varCfg.label})`,
      font: { color: '#e0e0e0', size: 14 },
    },
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'rgba(25, 30, 36, 0.6)',
    font: { color: '#b0bec5' },
    xaxis: {
      title: varCfg.axis,
      gridcolor: '#2a3441',
      type: varCfg.logScale ? 'log' : 'linear',
    },
    yaxis: {
      title: 'Altitude Above Surface (km)',
      gridcolor: '#2a3441',
    },
    margin: { l: 65, r: 25, t: 50, b: 50 },
  };

  window.Plotly.newPlot(plotDiv, [trace], layout, { responsive: true });
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
  window.addEventListener('resize', resizeOverlay);

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
      if (!isDragging) return;
      isDragging = false;
      const coords = getImgCoords(e);
      vedaState.transectCoords.x1 = coords.imgX;
      vedaState.transectCoords.y1 = coords.imgY;
      drawTransectLine(vedaState.transectCoords.x0, vedaState.transectCoords.y0, vedaState.transectCoords.x1, vedaState.transectCoords.y1);
      loadTransect(obs.mission_id, obs.observation_id, vedaState.transectCoords.x0, vedaState.transectCoords.y0, vedaState.transectCoords.x1, vedaState.transectCoords.y1);
    });
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
    const layout = {
      title: { text: `Line Slice (${x0},${y0}) &rarr; (${x1},${y1})`, font: { size: 12, color: '#e0e0e0' } },
      paper_bgcolor: 'transparent',
      plot_bgcolor: 'rgba(25, 30, 36, 0.6)',
      font: { color: '#b0bec5', size: 10 },
      xaxis: { title: 'Distance Along Slice (px)', gridcolor: '#2a3441' },
      yaxis: { title: 'Intensity', gridcolor: '#2a3441' },
      margin: { l: 45, r: 15, t: 30, b: 35 },
    };
    window.Plotly.newPlot(plotDiv, [trace], layout, { responsive: true, displayModeBar: false });
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
    const layout = {
      title: { text: 'Pixel Intensity Histogram', font: { size: 12, color: '#e0e0e0' } },
      paper_bgcolor: 'transparent',
      plot_bgcolor: 'rgba(25, 30, 36, 0.6)',
      font: { color: '#b0bec5', size: 10 },
      xaxis: { title: 'Pixel Value', gridcolor: '#2a3441' },
      yaxis: { title: 'Count', gridcolor: '#2a3441' },
      margin: { l: 45, r: 15, t: 30, b: 35 },
    };
    window.Plotly.newPlot(plotDiv, [trace], layout, { responsive: true, displayModeBar: false });
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

  // Remote Archive Downloader Controls
  const btnToggle = document.getElementById('btn-toggle-archive-search');
  const btnClose = document.getElementById('btn-close-archive-search');
  const panel = document.getElementById('veda-archive-search-panel');
  const btnQuery = document.getElementById('btn-execute-archive-search');
  const resultsContainer = document.getElementById('archive-results-container');

  if (btnToggle && panel) {
    btnToggle.addEventListener('click', () => {
      panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
      if (panel.style.display === 'block') {
        executeArchiveQuery();
      }
    });
  }

  if (btnClose && panel) {
    btnClose.addEventListener('click', () => {
      panel.style.display = 'none';
    });
  }

  if (btnQuery) {
    btnQuery.addEventListener('click', () => {
      executeArchiveQuery();
    });
  }

  async function executeArchiveQuery() {
    if (!resultsContainer) return;
    resultsContainer.innerHTML = '<div class="hint">Querying authentic international archives (NASA PDS, ESA PSA, JAXA DARTS)...</div>';

    const agency = document.getElementById('archive-agency-select')?.value || 'all';
    const queryTerm = (document.getElementById('archive-search-input')?.value || '').trim().toLowerCase();

    try {
      const resp = await api.vedaArchiveDiscover(vedaState.activeMissionId, vedaState.activeBodyId);
      let products = resp.products || [];

      if (agency !== 'all') {
        products = products.filter(p => p.archive.toLowerCase().includes(agency));
      }
      if (queryTerm) {
        products = products.filter(p =>
          (p.filename || '').toLowerCase().includes(queryTerm) ||
          (p.product_id || '').toLowerCase().includes(queryTerm) ||
          (p.instrument || '').toLowerCase().includes(queryTerm) ||
          (p.target || '').toLowerCase().includes(queryTerm)
        );
      }

      if (products.length === 0) {
        resultsContainer.innerHTML = '<div class="hint">No matching archive products found. Try a different search term or agency.</div>';
        return;
      }

      resultsContainer.innerHTML = `
        <table class="data-table" style="width: 100%; border-collapse: collapse; font-size: 12px;">
          <thead>
            <tr style="border-bottom: 1px solid var(--line); text-align: left;">
              <th style="padding: 6px 8px;">Archive / Agency</th>
              <th style="padding: 6px 8px;">Product / Granule</th>
              <th style="padding: 6px 8px;">Instrument</th>
              <th style="padding: 6px 8px;">Format</th>
              <th style="padding: 6px 8px;">Size</th>
              <th style="padding: 6px 8px;">Action</th>
            </tr>
          </thead>
          <tbody>
            ${products.map((p, idx) => {
              const agencyClass = p.archive.toLowerCase().includes('nasa') ? 'nasa' :
                                  (p.archive.toLowerCase().includes('esa') ? 'esa' : 'jaxa');
              const taskId = `dl-${Date.now()}-${idx}`;
              return `
                <tr id="archive-row-${idx}">
                  <td style="padding: 6px 8px;"><span class="archive-badge ${agencyClass}">${p.archive}</span></td>
                  <td style="padding: 6px 8px;"><code>${p.filename || p.product_id}</code></td>
                  <td style="padding: 6px 8px;">${p.instrument}</td>
                  <td style="padding: 6px 8px;">${p.format}</td>
                  <td style="padding: 6px 8px;">${(p.size_bytes / 1024 / 1024).toFixed(1)} MB</td>
                  <td style="padding: 6px 8px;">
                    <button class="primary small btn-start-dl"
                      data-task-id="${taskId}"
                      data-url="${p.download_url}"
                      data-filename="${p.filename}"
                      data-mission="${vedaState.activeMissionId}"
                      data-body="${p.target || vedaState.activeBodyId}"
                      data-instrument="${p.instrument}">
                      ⬇️ Download
                    </button>
                    <div id="prog-${taskId}" class="progress-wrap hidden" style="margin-top: 4px; width: 120px;">
                      <div class="progress-bar"><div class="progress-fill" id="bar-${taskId}" style="width: 0%;"></div></div>
                    </div>
                  </td>
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      `;

      // Connect download buttons
      resultsContainer.querySelectorAll('.btn-start-dl').forEach(btn => {
        btn.addEventListener('click', async () => {
          const tid = btn.dataset.taskId;
          btn.disabled = true;
          btn.textContent = 'Downloading...';
          const progWrap = document.getElementById(`prog-${tid}`);
          const bar = document.getElementById(`bar-${tid}`);
          if (progWrap) progWrap.classList.remove('hidden');

          try {
            await api.vedaArchiveDownload({
              task_id: tid,
              mission_id: btn.dataset.mission,
              body_id: btn.dataset.body,
              instrument: btn.dataset.instrument,
              remote_url: btn.dataset.url,
              filename: btn.dataset.filename,
            });

            // Poll task status
            const interval = setInterval(async () => {
              try {
                const st = await api.vedaArchiveTaskStatus(tid);
                if (bar) bar.style.width = `${st.progress_pct}%`;

                if (st.status === 'completed') {
                  clearInterval(interval);
                  btn.textContent = '✓ Downloaded';
                  btn.classList.remove('primary');
                  btn.classList.add('ghost');
                  // Refresh mission observations
                  await loadAndRenderMission(vedaState.activeMissionId);
                } else if (st.status === 'failed') {
                  clearInterval(interval);
                  btn.textContent = 'Failed';
                  alert(`Download failed: ${st.error}`);
                }
              } catch (pollErr) {
                clearInterval(interval);
              }
            }, 600);

          } catch (dlErr) {
            btn.textContent = 'Error';
            alert(`Download error: ${dlErr.message}`);
          }
        });
      });

    } catch (err) {
      resultsContainer.innerHTML = `<div class="hint text-danger">Archive search error: ${err.message}</div>`;
    }
  }
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

export async function handleUploadedFile(file) {
  if (!file) return;
  toast(`Parsing ${file.name}...`);
  try {
    const isBinary = /\.(fits?|fit|png|jpe?g)$/i.test(file.name);
    let fileContent;
    if (isBinary) {
      fileContent = await readFileAsBase64(file);
    } else {
      fileContent = await readFileAsText(file);
    }

    const payload = {
      filename: file.name,
      file_content: fileContent,
      body_id: vedaState.activeBodyId || 'venus'
    };

    const res = await api.vedaParseFile(payload);

    if (res.status === 'ok' || res.observation_id || res.n_points) {
      toast(`Successfully parsed ${file.name} (${res.n_points || 0} levels)`, 'good');
      switchMode('mission');
      await inspectProfileObservation(res);
      const viewer = document.getElementById('veda-observation-viewer');
      if (viewer) viewer.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else {
      toast(`Could not parse file: ${res.detail || 'Unknown format'}`, 'bad');
    }
  } catch (err) {
    console.error('File load error:', err);
    toast(`Failed to load file: ${err.message}`, 'bad');
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
      if (e.target.files && e.target.files[0]) {
        handleUploadedFile(e.target.files[0]);
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
      dropZone.classList.remove('drag-active');
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
        handleUploadedFile(e.dataTransfer.files[0]);
      }
    });
  }

  // Guide Action Buttons
  document.querySelectorAll('[data-guide-action]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const action = btn.dataset.guideAction;
      switch (action) {
        case 'browse-missions':
          switchMode('mission');
          break;
        case 'trigger-file-input':
          if (fileInput) fileInput.click();
          break;
        case 'load-sample-chandrayaan2':
          switchMode('mission');
          await loadAndRenderMission('chandrayaan2');
          await inspectProfileObservation({
            mission_id: 'chandrayaan2',
            observation_id: 'ch2_dfrs_lunar_iono_sample',
            instrument: 'DFRS'
          });
          break;
        case 'load-sample-venus':
          switchMode('mission');
          await loadAndRenderMission('vex');
          await inspectProfileObservation({
            mission_id: 'vex',
            observation_id: 'vex_vera_orbit_0045_profile',
            instrument: 'VeRa'
          });
          break;
        case 'load-sample-menca':
          switchMode('mission');
          await loadAndRenderMission('mom');
          await inspectProfileObservation({
            mission_id: 'mom',
            observation_id: 'mom_menca_mars_exosphere_sample',
            instrument: 'MENCA'
          });
          break;
        case 'inspect-active-profile':
          switchMode('mission');
          if (vedaState.missionObservations && vedaState.missionObservations.length > 0) {
            const firstProf = vedaState.missionObservations.find(o => o.data_type === 'profile') || vedaState.missionObservations[0];
            await inspectProfileObservation(firstProf);
          }
          break;
        case 'help-drawer': {
          const btnHelp = document.getElementById('btn-help');
          if (btnHelp) btnHelp.click();
          break;
        }
        case 'compare-venus': {
          switchMode('body');
          await loadAndRenderCelestialBody('venus');
          const checkboxes = document.querySelectorAll('#veda-missions-checkboxes input[type="checkbox"]');
          vedaState.selectedMissionIdsForBody.clear();
          checkboxes.forEach(cb => {
            if (cb.value === 'akatsuki' || cb.value === 'vex') {
              cb.checked = true;
              vedaState.selectedMissionIdsForBody.add(cb.value);
            } else {
              cb.checked = false;
            }
          });
          updateComparison();
          break;
        }
        case 'compare-mars': {
          switchMode('body');
          await loadAndRenderCelestialBody('mars');
          const checkboxes = document.querySelectorAll('#veda-missions-checkboxes input[type="checkbox"]');
          vedaState.selectedMissionIdsForBody.clear();
          checkboxes.forEach(cb => {
            if (cb.value === 'mom' || cb.value === 'maven') {
              cb.checked = true;
              vedaState.selectedMissionIdsForBody.add(cb.value);
            } else {
              cb.checked = false;
            }
          });
          updateComparison();
          break;
        }
        case 'load-fits-pluto':
          switchMode('mission');
          await loadAndRenderMission('new_horizons');
          await inspectImageObservation({
            mission_id: 'new_horizons',
            observation_id: 'nh_lorri_pluto_approach',
            instrument: 'LORRI'
          });
          break;
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
        default:
          console.warn('Unknown guide action:', action);
      }
    });
  });
}
