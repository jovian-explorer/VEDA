/**
 * Body-wide search: every connected archive data set for one planet or moon,
 * filtered by date range. Results can be downloaded, opened or compared.
 */
import { api } from './api.js';
import { toast, esc } from './ui.js';

const PAGE = 300;
const st = { bodyId: null, results: [], total: 0, selected: new Map(), onOpen: null, onCompare: null, token: 0, notes: [] };
const $ = (id) => document.getElementById(id);
const keyOf = (p) => `${p.dataset_id}|${p.product_id}`;

export function setupBodySearch({ onOpen, onCompare }) {
  st.onOpen = onOpen;
  st.onCompare = onCompare;
  // (the search sits below the comparison: one click from the top of the page)
  $('veda-jump-search')?.addEventListener('click', () => {
    $('veda-body-search')?.scrollIntoView({ behavior: 'smooth' });
    $('bs-start')?.focus({ preventScroll: true });
  });
  $('bs-form')?.addEventListener('submit', (e) => { e.preventDefault(); run(true); });
  $('bs-kind')?.addEventListener('change', () => run(true));
  $('bs-more')?.addEventListener('click', () => run(false));
  $('bs-select-all')?.addEventListener('change', (e) => {
    st.results.forEach(p => (e.target.checked ? st.selected.set(keyOf(p), p) : st.selected.delete(keyOf(p))));
    rows();
  });
  $('bs-download')?.addEventListener('click', download);
  $('bs-compare')?.addEventListener('click', () => {
    const items = [...st.selected.values()].filter(p => p.kind === 'profile');
    if (!items.length) return toast('Select one or more profiles to compare', 'bad');
    st.onCompare?.(items);
  });
}

export async function showBodySearch(bodyId, bodyName) {
  if (st.bodyId !== bodyId) { st.selected.clear(); st.results = []; st.total = 0; }
  st.bodyId = bodyId;
  if ($('bs-body-name')) $('bs-body-name').textContent = bodyName || bodyId;
  try {
    const ds = (await api.archiveDatasets(null, bodyId)).datasets || [];
    const real = ds.filter(d => !d.portal_only);
    st.liveCount = real.filter(d => d.live).length;
    const missions = [...new Set(real.map(d => d.mission_id))];
    // the years with observations: from each data set's dates (open-ended: still growing)
    const now = String(new Date().getFullYear());
    const years = real.flatMap(d => (d.coverage || []).length ? [d.coverage[0].slice(0, 4), d.coverage[1].slice(0, 4) || now]
      : d.indexed_volumes && d.first_time ? [d.first_time.slice(0, 4), d.last_time.slice(0, 4)] : []).sort();
    $('bs-coverage').textContent = real.length
      ? `${real.length} data set${real.length > 1 ? 's' : ''} from ${missions.length} mission${missions.length > 1 ? 's' : ''}` +
        (st.liveCount ? ` (${st.liveCount} searched live on the archive servers when you give dates)` : '') +
        (years.length ? `; observations from ${years[0]} to ${years[years.length - 1]}` : '')
      : 'No archive data set is connected for this body yet.';
    $('bs-form').hidden = !real.length;
    if (!st.results.length) $('bs-results').innerHTML = real.length
      ? '<tr><td colspan="8" class="empty-state">Choose a date range (or leave it empty for everything) and press Search all missions.</td></tr>'
      : '<tr><td colspan="8" class="empty-state">Nothing to search yet for this body.</td></tr>';
  } catch (err) {
    $('bs-coverage').textContent = `Could not list data sets: ${err.message}`;
  }
}

async function poll(jobId, label, keepLabel = false, keepBar = false) {
  progress(true, 0, label);
  for (;;) {
    await new Promise(r => setTimeout(r, 700));
    const j = await api.archiveJob(jobId);
    progress(true, j.total ? Math.round(100 * j.done / j.total) : 5,
      keepLabel ? `${label}${j.message ? ` (${j.message})` : ''}` : (j.message || label));
    if (j.status === 'running') continue;
    if (!keepBar) progress(false);
    if (j.status !== 'completed') toast(j.message || `${label} failed`, 'bad');
    return j;
  }
}

async function ensureIndexed(start, end, onRead) {
  // (a data set whose observations all lie outside the dates is not read)
  const outside = ([first, last] = []) => (first && end && end < first) || (last && start && start > last);
  let ds = ((await api.archiveDatasets(null, st.bodyId)).datasets || []).filter(d =>
    !d.portal_only && !d.indexed_volumes && !d.live && d.auto_index !== false && !outside(d.coverage));
  if (!ds.length) return;
  // (with the authors of a research data set: several NOMAD sets share one instrument name)
  const who = d => (/\(([^()]*[A-Za-z][^()]* \d{4})\)$/.exec(d.title || '') || [])[1];
  const name = d => `${d.instrument.toUpperCase().startsWith(d.mission_id.toUpperCase()) ? '' : `${d.mission_id.toUpperCase()} `}${d.instrument}${who(d) ? `, ${who(d)}` : ''}`;
  // an archive server that does not answer now would cost minutes per data set in
  // timeouts and retries: its data sets are skipped this time (one short check per server)
  progress(true, 0, 'Checking that the archive servers answer');
  try {
    const down = (await api.archiveReachable(ds.map(d => d.id))).down || [];
    const skip = new Set(down.flatMap(h => h.dataset_ids));
    st.notes.push(...down.map(h => `${h.archive} did not answer; ${h.dataset_ids.length} data set${h.dataset_ids.length > 1 ? 's' : ''} skipped (${
      ds.filter(d => h.dataset_ids.includes(d.id)).map(name).join(', ')}): try again later`));
    ds = ds.filter(d => !skip.has(d.id));
  } catch (err) {
    if (err.status === 503) { st.notes.push(err.message); return; }   // network switched off
  }
  // the first search on a computer reads each data set's archive catalogue once (minutes
  // for the large ones), three at a time; later searches use the local copy
  // never two at once from one archive server (a busy server refuses: JAXA, the PDS nodes)
  const host = d => { try { return new URL(d.url).host; } catch (e) { return d.archive; } };
  const queue = [...ds], running = new Set(), busy = new Set(), failed = [];
  let done = 0;
  const show = () => progress(true, Math.round(100 * done / ds.length),
    `First search on this computer: reading the archive catalogues, ${done} of ${ds.length} done`
    + (running.size ? ` (now ${[...running].join(', ')})` : '') + '; results appear below as each is read, and later searches are instant');
  async function worker() {
    while (queue.length) {
      const k = queue.findIndex(x => !busy.has(host(x)));
      if (k < 0) { await new Promise(r => setTimeout(r, 500)); continue; }
      const d = queue.splice(k, 1)[0];
      busy.add(host(d)); running.add(name(d)); show();
      try {
        const { job_id } = await api.archiveIndex(d.id);
        for (;;) {
          await new Promise(r => setTimeout(r, 700));
          const j = await api.archiveJob(job_id);
          if (j.status === 'running') continue;
          if (j.status !== 'completed') failed.push(name(d));
          break;
        }
      } catch (err) {
        failed.push(name(d));
      }
      busy.delete(host(d)); running.delete(name(d)); done += 1; show();
      onRead();
    }
  }
  if (ds.length) await Promise.all([worker(), worker(), worker()]);
  if (failed.length) st.notes.push(`The archive did not answer for ${failed.join(', ')}: their observations are left out; search again later`);
}

async function run(reset) {
  if (!st.bodyId) return;
  const start = $('bs-start').value, end = $('bs-end').value;
  if (start && end && end < start) return toast('The end date is before the start date', 'bad');
  const token = ++st.token;
  const query = () => api.archiveSearch({
    body_id: st.bodyId, start, end, kind: $('bs-kind').value,
    limit: PAGE, offset: reset ? 0 : st.results.length,
  });
  const show = (res) => {
    st.results = reset ? res.products : st.results.concat(res.products);
    st.total = res.total;
    st.undated = res.undated || 0;
    rows();
  };
  // while the first search reads the catalogues, what is already read is listed (one
  // listing at a time; one more after the last catalogue that finished meanwhile)
  let listing = null, again = false;
  const partial = () => {
    if (listing) { again = true; return; }
    listing = query().then(res => { if (token === st.token && res.products.length) show(res); })
      .catch(() => {}).finally(() => { listing = null; if (again) { again = false; partial(); } });
  };
  try {
    if (reset) {
      st.notes = [];
      await ensureIndexed(start, end, partial);
    }
    if (reset && start && end && st.liveCount) {
      const key = `${st.bodyId}|${start}|${end}`;
      if (key !== st.liveKey) {
        st.liveKey = key;
        const { job_id } = await api.archiveLive({ start, end, body_id: st.bodyId });
        const j = await poll(job_id, 'Searching the archive servers', false, true);
        if (j.status === 'completed' && j.message) toast(j.message, j.result?.truncated?.length ? '' : 'good');
      }
    }
    if (token !== st.token) return;
    if (reset) progress(true, 100, 'Listing the observations');
    while (listing) await listing;
    const res = await query();
    if (token !== st.token) return;
    show(res);
    if (reset && st.notes.length) toast(st.notes.join('. '), 'bad');
  } catch (err) {
    $('bs-results').innerHTML = `<tr><td colspan="8" class="empty-state">Search failed: ${esc(err.message)}</td></tr>`;
  } finally {
    if (token === st.token) progress(false);
  }
}

function rows() {
  const body = $('bs-results');
  if (!st.results.length) {
    body.innerHTML = '<tr><td colspan="8" class="empty-state">No observations in this date range. Widen the range or clear it.</td></tr>';
  } else {
    body.innerHTML = st.results.map((p, i) => `
      <tr class="${st.selected.has(keyOf(p)) ? 'selected' : ''}">
        <td class="arch-col-check"><input type="checkbox" data-sel="${i}" ${st.selected.has(keyOf(p)) ? 'checked' : ''} aria-label="Select ${esc(p.product_id)}" /></td>
        <td><strong>${esc((p.mission_id || '').toUpperCase())}</strong></td>
        <td class="nowrap">${esc((p.start_time || '').replace('T', ' ').slice(0, 19)) || '-'}</td>
        <td><code>${esc(p.product_id)}</code></td>
        <td>${esc(p.product_type)}</td>
        <td>${esc(`${p.instrument || ''} ${p.level || ''}`)}</td>
        <td>${p.downloaded ? '<span class="badge badge-ok">Downloaded</span>' : '<span class="badge">In archive</span>'}</td>
        <td><button type="button" class="ghost small" data-open="${i}">${p.kind === 'profile' ? 'Open' : 'View'}</button></td>
      </tr>`).join('');
    body.querySelectorAll('input[data-sel]').forEach(cb => cb.addEventListener('change', () => {
      const p = st.results[+cb.dataset.sel];
      cb.checked ? st.selected.set(keyOf(p), p) : st.selected.delete(keyOf(p));
      cb.closest('tr').classList.toggle('selected', cb.checked);
      buttons();
    }));
    body.querySelectorAll('button[data-open]').forEach(b => b.addEventListener('click', () => st.onOpen?.(st.results[+b.dataset.open])));
  }
  const missions = new Set(st.results.map(p => p.mission_id));
  const noDates = !($('bs-start').value && $('bs-end').value);
  $('bs-count').textContent = (st.total ? `${st.results.length.toLocaleString()} of ${st.total.toLocaleString()} from ${missions.size} mission${missions.size > 1 ? 's' : ''}` : '') +
    (noDates && st.liveCount ? `${st.total ? ' · ' : ''}Give From and To dates to include the ${st.liveCount} live data sets` : '') +
    (st.notes.length ? ` · ${st.notes.join(' · ')}` : '') +
    (st.undated ? ` · ${st.undated.toLocaleString()} product${st.undated > 1 ? 's' : ''} without a time in the archive index ${st.undated > 1 ? 'are' : 'is'} not listed for dates; clear the dates to see ${st.undated > 1 ? 'them' : 'it'}` : '');
  $('bs-more').hidden = st.results.length >= st.total;
  buttons();
}

function buttons() {
  const n = st.selected.size;
  $('bs-download').disabled = !n;
  $('bs-download').textContent = n ? `Download selected (${n})` : 'Download selected';
  $('bs-compare').disabled = ![...st.selected.values()].some(p => p.kind === 'profile');
}

async function download() {
  const items = [...st.selected.values()].filter(p => !p.downloaded);
  if (!items.length) return toast('The selected products are already downloaded', 'good');
  try {
    const { job_id } = await api.archiveFetch(items.map(p => ({ dataset_id: p.dataset_id, product_id: p.product_id })));
    const j = await poll(job_id, `Downloading ${items.length} products`);
    const ok = new Set((j.result && j.result.fetched) || []);
    st.results.forEach(p => { if (ok.has(p.product_id)) p.downloaded = true; });
    rows();
  } catch (err) {
    toast(`Download failed: ${err.message}`, 'bad');
  }
}

function progress(on, pct = 0, text = '') {
  const box = $('bs-progress');
  box.hidden = !on;
  if (on) { $('bs-progress-fill').style.width = `${pct}%`; $('bs-progress-text').textContent = text; }
}
