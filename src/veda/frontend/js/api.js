// Thin wrapper over the local JSON API, plus the shared client-side state.

async function call(path, {method = 'GET', body = null} = {}) {
  const opts = {method, headers: {}};
  if (body !== null) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(path, opts);
  } catch (err) {
    throw new Error(`Cannot reach the backend (${err.message}). ` +
                    `Is the application still running?`);
  }
  const text = await res.text();
  let data = null;
  if (text) {
    try { data = JSON.parse(text); } catch { data = {raw: text}; }
  }
  if (!res.ok) {
    const detail = data && (data.detail || data.error);
    throw new Error(typeof detail === 'string' ? detail
                    : `${res.status} ${res.statusText}`);
  }
  return data;
}

export const api = {
  health:        ()          => call('/api/health'),
  meta:          ()          => call('/api/meta'),
  saveSettings:  (patch)     => call('/api/settings', {method: 'POST', body: patch}),
  resetSettings: ()          => call('/api/settings/reset', {method: 'POST'}),

  archiveDay:    (date, streams) =>
      call(`/api/archive/day?date=${date}` + (streams ? `&streams=${streams}` : '')),
  archiveLatest: (stream, level, product) =>
      call(`/api/archive/latest?stream=${stream}&level=${level}` +
           (product ? `&product=${product}` : '')),

  download:      (req)       => call('/api/download', {method: 'POST', body: req}),
  jobs:          (activeOnly = false) => call(`/api/jobs?active_only=${activeOnly}`),
  cancelJob:     (id)        => call(`/api/jobs/${id}/cancel`, {method: 'POST'}),
  reindex:       ()          => call('/api/jobs/reindex', {method: 'POST'}),
  loadSamples:   ()          => call('/api/local/load-samples', {method: 'POST'}),

  localSummary:  ()          => call('/api/local/summary'),
  datasets:      ()          => call('/api/local/datasets'),
  deleteDataset: (key)       => call(`/api/local/datasets/${key}`, {method: 'DELETE'}),
  facets:        ()          => call('/api/local/facets'),
  coverage:      (products)  =>
      call('/api/local/coverage' + (products ? `?products=${products}` : '')),

  search:        (req)       => call('/api/profiles/search', {method: 'POST', body: req}),
  profile:       (gid)       => call(`/api/profiles/${gid}`),
  profileData:   (gid, vars, maxPoints = 1200) =>
      call(`/api/profiles/${gid}/data?max_points=${maxPoints}` +
           (vars ? `&vars=${vars}` : '')),
  plotProfiles:  (req)       => call('/api/plot/profiles', {method: 'POST', body: req}),
  composite:     (req)       => call('/api/composite', {method: 'POST', body: req}),
  diagTable:     (req)       => call('/api/diagnostics/table', {method: 'POST', body: req}),

  exportData:    (req)       => call('/api/export/data', {method: 'POST', body: req}),
  exportFigure:  (req)       => call('/api/export/figure', {method: 'POST', body: req}),
  exports:       ()          => call('/api/exports'),
  deleteExport:  (name)      => call(`/api/exports/${name}`, {method: 'DELETE'}),
  revealFolder:  (which)     => call(`/api/reveal-folder?which=${which}`),

  // VEDA Multi-Mission & Planetary Science Endpoints
  vedaInfo:        ()           => call('/api/veda/info'),
  vedaBodies:      ()           => call('/api/veda/bodies'),
  vedaBodyDetails: (id)         => call(`/api/veda/bodies/${id}`),
  vedaMissions:    ()           => call('/api/veda/missions'),
  vedaMissionDetails: (id)      => call(`/api/veda/missions/${id}`),
  vedaExploreBody: (id, missions) =>
      call(`/api/veda/explore/body/${id}` + (missions ? `?missions=${missions}` : '')),
  vedaExploreMission: (id, bodyId, instrumentId) => {
    const q = [];
    if (bodyId) q.push(`body_id=${encodeURIComponent(bodyId)}`);
    if (instrumentId) q.push(`instrument_id=${encodeURIComponent(instrumentId)}`);
    return call(`/api/veda/explore/mission/${id}` + (q.length ? `?${q.join('&')}` : ''));
  },
  vedaCompareBody: (bodyId, req) =>
      call(`/api/veda/compare/body/${bodyId}`, {method: 'POST', body: req}),
  vedaProfile: (missionId, obsId, decimate = 600) =>
      call(`/api/veda/profile/${missionId}/${encodeURIComponent(obsId)}?decimate_max=${decimate}`),
  vedaImageMeta: (missionId, obsId) =>
      call(`/api/veda/image/${missionId}/${encodeURIComponent(obsId)}`),
  vedaImageRenderUrl: (missionId, obsId, stretch = 'zscale', cmap = 'inferno') =>
      `/api/veda/image/${missionId}/${encodeURIComponent(obsId)}/render?stretch=${stretch}&colormap=${cmap}`,
  vedaImageTransect: (missionId, obsId, req) =>
      call(`/api/veda/image/${missionId}/${encodeURIComponent(obsId)}/transect`, {method: 'POST', body: req}),
  vedaImageHistogram: (missionId, obsId, bins = 100) =>
      call(`/api/veda/image/${missionId}/${encodeURIComponent(obsId)}/histogram?bins=${bins}`),
  vedaExportProfileCsvUrl: (missionId, obsId) =>
      `/api/veda/export/profile/${missionId}/${encodeURIComponent(obsId)}/csv`,
  vedaExportProfileJsonUrl: (missionId, obsId) =>
      `/api/veda/export/profile/${missionId}/${encodeURIComponent(obsId)}/json`,
  // Real archive data sets (see veda/archives)
  archiveDatasets: (missionId) =>
      call(`/api/veda/archive/datasets${missionId ? `?mission_id=${encodeURIComponent(missionId)}` : ''}`),
  archiveIndex: (datasetId, force = false) =>
      call(`/api/veda/archive/datasets/${encodeURIComponent(datasetId)}/index${force ? '?force=true' : ''}`, {method: 'POST'}),
  archiveSearch: (params) => {
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v === undefined || v === null || v === '') continue;
      if (Array.isArray(v)) v.forEach(x => q.append(k, x)); else q.append(k, v);
    }
    return call(`/api/veda/archive/search?${q.toString()}`);
  },
  archiveFetch: (items) => call('/api/veda/archive/fetch', {method: 'POST', body: {items}}),
  archiveJob: (jobId) => call(`/api/veda/archive/jobs/${encodeURIComponent(jobId)}`),
  vedaPublicationFigureUrl: (bodyId, variable = 'temperature_k', missions, dpi = 300, fmt = 'png') => {
    const q = [`body_id=${encodeURIComponent(bodyId)}`, `variable=${encodeURIComponent(variable)}`, `dpi=${dpi}`, `fmt=${fmt}`];
    if (missions) q.push(`missions=${encodeURIComponent(missions)}`);
    return `/api/veda/figure/publication?${q.join('&')}`;
  },
  vedaParseFile: (req) =>
      call('/api/veda/parse-file', {method: 'POST', body: req}),
  vedaVariables: () =>
      call('/api/veda/variables'),
  vedaVariable: (id) =>
      call(`/api/veda/variables/${encodeURIComponent(id)}`),
  vedaDataAvailability: () =>
      call('/api/veda/data-availability'),
  vedaLicenses: () =>
      call('/api/veda/licenses'),
  vedaPortals: () =>
      call('/api/veda/portals'),
};

// --------------------------------------------------------------------------
// shared state
// --------------------------------------------------------------------------

export const state = {
  meta: null,             // /api/meta payload
  results: [],            // current search page
  total: 0,
  offset: 0,
  pageSize: 100,
  selected: new Map(),    // granule_id -> row
  lastSearch: null,       // the SearchRequest that produced `results`
  curious: true,
};

export function selectRow(row) { state.selected.set(row.id, row); }
export function deselectRow(id) { state.selected.delete(id); }
export function isSelected(id) { return state.selected.has(id); }
export function selectedIds() { return [...state.selected.keys()]; }

/** The selection if there is one, otherwise the active search. */
export function selectionRequest(selectedOnly) {
  const ids = selectedIds();
  if (selectedOnly) return {granule_ids: ids};
  if (ids.length) return {granule_ids: ids};
  return {search: state.lastSearch || {good_only: true, limit: 2000}};
}

export function vocabInfo(name) {
  const v = state.meta && state.meta.vocabulary[name];
  return v || {name, label: name, units: '', plain: '', role: 'field'};
}

export function axisTitle(name, units) {
  const v = vocabInfo(name);
  const u = units === undefined || units === null ? v.units : units;
  return u && u !== '-' ? `${v.label} [${u}]` : v.label;
}
