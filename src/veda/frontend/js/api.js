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
    const err = new Error(typeof detail === 'string' ? detail
                          : (detail && detail.message) || `${res.status} ${res.statusText}`);
    err.status = res.status;
    if (detail && typeof detail === 'object') err.detail = detail;
    throw err;
  }
  return data;
}

const productBase = (ds, pid) => `/api/veda/product/${encodeURIComponent(ds)}/${encodeURIComponent(pid)}`;

/** URL query from an object; arrays repeat the key, empty values are left out. */
function query(params = {}) {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '' || v === false) continue;
    if (Array.isArray(v)) v.forEach(x => q.append(k, x)); else q.append(k, v);
  }
  return q.toString();
}

export const api = {
  health:        ()          => call('/api/health'),
  meta:          ()          => call('/api/meta'),
  saveSettings:  (patch)     => call('/api/settings', {method: 'POST', body: patch}),
  resetSettings: ()          => call('/api/settings/reset', {method: 'POST'}),
  updateCheck:   (force)     => call(`/api/update${force ? '?force=true' : ''}`),

  revealFolder:  (which)     => call(`/api/reveal-folder?which=${which}`, {method: 'POST'}),

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
  vedaHarmonicFit: (req) =>
      call('/api/veda/analysis/harmonic-fit', {method: 'POST', body: req}),
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
  archiveDatasets: (missionId, bodyId) => {
    const q = new URLSearchParams();
    if (missionId) q.append('mission_id', missionId);
    if (bodyId) q.append('body_id', bodyId);
    return call(`/api/veda/archive/datasets${q.toString() ? `?${q}` : ''}`);
  },
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
  // Any product, any payload: structure, table series, images, cubes (see product_routes.py)
  productStructure: (ds, pid, confirmLarge = false) =>
    call(`${productBase(ds, pid)}/structure${confirmLarge ? '?confirm_large=true' : ''}`),
  productTable: (ds, pid, params) => call(`${productBase(ds, pid)}/table?${query(params)}`),
  productImageUrl: (ds, pid, params) => `${productBase(ds, pid)}/image.png?${query(params)}`,
  productImageStats: (ds, pid, params) => call(`${productBase(ds, pid)}/image/stats?${query(params)}`),
  productTransect: (ds, pid, params) => call(`${productBase(ds, pid)}/image/transect?${query(params)}`),
  productSpectrum: (ds, pid, params) => call(`${productBase(ds, pid)}/cube/spectrum?${query(params)}`),
  productRows: (ds, pid, params) => call(`${productBase(ds, pid)}/rows?${query(params)}`),
  productText: (ds, pid, params) => call(`${productBase(ds, pid)}/text?${query(params)}`),
  productProgress: (ds, pid) => call(`${productBase(ds, pid)}/progress`),
  archiveJob: (jobId) => call(`/api/veda/archive/jobs/${encodeURIComponent(jobId)}`),
  archiveLive: (req) => call('/api/veda/archive/live', {method: 'POST', body: req}),
  geometryKernels: (ds, pid) => call(`/api/veda/geometry/${encodeURIComponent(ds)}/${encodeURIComponent(pid)}/kernels`),
  geometryPrepare: (ds, pid) => call(`/api/veda/geometry/${encodeURIComponent(ds)}/${encodeURIComponent(pid)}/prepare`, {method: 'POST'}),
  spicePrefetch: (missionId, bodyId) => call('/api/veda/geometry/prefetch', {method: 'POST', body: {mission_id: missionId, body_id: bodyId || null}}),
  vedaPublicationFigureUrl: (bodyId, variable = 'temperature_k', missions, dpi = 300, fmt = 'png') => {
    const q = [`body_id=${encodeURIComponent(bodyId)}`, `variable=${encodeURIComponent(variable)}`, `dpi=${dpi}`, `fmt=${fmt}`];
    if (missions) q.push(`missions=${encodeURIComponent(missions)}`);
    return `/api/veda/figure/publication?${q.join('&')}`;
  },
  vedaPreviewUpload: (req) => call('/api/veda/upload/preview', {method: 'POST', body: req}),
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
  meta: null,             // /api/meta payload (settings, paths, version, registry data)
};
