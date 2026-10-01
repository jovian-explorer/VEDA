/**
 * Body-wide search: every connected archive data set for one planet or moon,
 * filtered by date range. Results can be downloaded, opened or compared.
 */
import { api } from './api.js';
import { toast } from './ui.js';

const PAGE = 300;
const st = { bodyId: null, results: [], total: 0, selected: new Map(), onOpen: null, onCompare: null, token: 0 };
const $ = (id) => document.getElementById(id);
const keyOf = (p) => `${p.dataset_id}|${p.product_id}`;
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

export function setupBodySearch({ onOpen, onCompare }) {
  st.onOpen = onOpen;
  st.onCompare = onCompare;
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
    const missions = [...new Set(real.map(d => d.mission_id))];
    const span = real.filter(d => d.indexed_volumes && d.first_time);
    $('bs-coverage').textContent = real.length
      ? `${real.length} data set${real.length > 1 ? 's' : ''} from ${missions.length} mission${missions.length > 1 ? 's' : ''}` +
        (span.length ? `; indexed coverage ${span.map(d => d.first_time.slice(0, 4)).sort()[0]} to ${span.map(d => d.last_time.slice(0, 4)).sort().slice(-1)[0]}` : '')
      : 'No archive data set is connected for this body yet.';
    $('bs-form').hidden = !real.length;
    if (!st.results.length) $('bs-results').innerHTML = real.length
      ? '<tr><td colspan="8" class="empty-state">Choose a date range (or leave it empty for everything) and press Search all missions.</td></tr>'
      : '<tr><td colspan="8" class="empty-state">Nothing to search yet for this body.</td></tr>';
  } catch (err) {
    $('bs-coverage').textContent = `Could not list data sets: ${err.message}`;
  }
}

async function poll(jobId, label) {
  progress(true, 0, label);
  for (;;) {
    await new Promise(r => setTimeout(r, 700));
    const j = await api.archiveJob(jobId);
    progress(true, j.total ? Math.round(100 * j.done / j.total) : 5, j.message || label);
    if (j.status === 'running') continue;
    progress(false);
    if (j.status !== 'completed') toast(j.message || `${label} failed`, 'bad');
    return j;
  }
}

async function ensureIndexed() {
  const ds = ((await api.archiveDatasets(null, st.bodyId)).datasets || []).filter(d => !d.portal_only && !d.indexed_volumes);
  for (const d of ds) {
    const { job_id } = await api.archiveIndex(d.id);
    await poll(job_id, `Indexing ${d.mission_id.toUpperCase()} ${d.instrument} (${d.level})`);
  }
}

async function run(reset) {
  if (!st.bodyId) return;
  const start = $('bs-start').value, end = $('bs-end').value;
  if (start && end && end < start) return toast('The end date is before the start date', 'bad');
  const token = ++st.token;
  try {
    if (reset) await ensureIndexed();
    const res = await api.archiveSearch({
      body_id: st.bodyId, start, end, kind: $('bs-kind').value,
      limit: PAGE, offset: reset ? 0 : st.results.length,
    });
    if (token !== st.token) return;
    st.results = reset ? res.products : st.results.concat(res.products);
    st.total = res.total;
    rows();
  } catch (err) {
    $('bs-results').innerHTML = `<tr><td colspan="8" class="empty-state">Search failed: ${esc(err.message)}</td></tr>`;
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
  $('bs-count').textContent = st.total ? `${st.results.length.toLocaleString()} of ${st.total.toLocaleString()} from ${missions.size} mission${missions.size > 1 ? 's' : ''}` : '';
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
