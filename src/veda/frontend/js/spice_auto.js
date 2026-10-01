/**
 * Automatic SPICE kernel downloads.
 *
 * When a mission is opened its generic and body kernels are fetched in the
 * background; when an observation is opened, the spacecraft ephemeris for its
 * date follows.  Nothing is downloaded when Settings > Observation geometry >
 * automatic downloads is off, or when the files exceed the size limit set there
 * (the Geometry panel then asks first).  Kernels are kept and reused.
 */
import { api, state } from './api.js';
import { toast } from './ui.js';

const inFlight = new Map();          // key -> promise

function enabled() {
  const s = state.meta && state.meta.settings;
  return !s || (s.spice_auto_download !== false && s.network_enabled !== false);
}

async function waitJob(jobId) {
  for (;;) {
    await new Promise(r => setTimeout(r, 1500));
    const j = await api.archiveJob(jobId);
    if (j.status !== 'running') return j;
  }
}

/** Generic and body kernels for a mission (silent unless it fails). */
export function prefetchMission(missionId, bodyId) {
  if (!enabled() || !missionId) return null;
  const key = `m|${missionId}|${bodyId || ''}`;
  if (inFlight.has(key)) return inFlight.get(key);
  const p = (async () => {
    try {
      const r = await api.spicePrefetch(missionId, bodyId);
      if (r.job_id) await waitJob(r.job_id);
    } catch (_) { /* geometry will ask again when it is opened */ }
  })();
  inFlight.set(key, p);
  return p;
}

/** Spacecraft SPK (and anything else missing) for an opened observation. */
export function prefetchObservation(p) {
  if (!enabled() || !p || !p.dataset_id) return null;
  const key = `o|${p.dataset_id}|${p.product_id}`;
  if (inFlight.has(key)) return inFlight.get(key);
  const job = (async () => {
    try {
      const k = await api.geometryKernels(p.dataset_id, p.product_id);
      if (!k.missing.length || !k.auto) return k;
      toast(`Downloading SPICE kernels for the geometry (${k.missing_mb} MB, kept for later)`);
      const { job_id } = await api.geometryPrepare(p.dataset_id, p.product_id);
      const j = await waitJob(job_id);
      if (j.status !== 'completed') toast(`SPICE kernels: ${j.message || 'download failed'}`, 'bad');
      return j;
    } catch (_) {
      return null;          // no SPICE for this mission, or no time: nothing to prefetch
    } finally {
      setTimeout(() => inFlight.delete(key), 60000);
    }
  })();
  inFlight.set(key, job);
  return job;
}

/** The pending download for this observation, if any (the Geometry panel waits for it). */
export function pendingFor(p) {
  return p ? inFlight.get(`o|${p.dataset_id}|${p.product_id}`) : null;
}
