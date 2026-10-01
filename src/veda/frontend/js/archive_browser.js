/**
 * Archive browser: search a mission's real archive data sets by payload, date
 * range, product type and text; download products; open or compare them.
 */
import { api } from './api.js';
import { toast } from './ui.js';

const PAGE = 200;

const st = {
  missionId: null,
  datasets: [],
  selectedDatasets: new Set(),
  results: [],
  total: 0,
  selected: new Map(),          // key -> product
  onOpen: null,
  onCompare: null,
  busy: false,
  gen: 0,                       // bumps on every mission switch; stale loads stop
};

const $ = (id) => document.getElementById(id);
const keyOf = (p) => `${p.dataset_id}|${p.product_id}`;
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

export function setupArchiveBrowser({ onOpen, onCompare }) {
  st.onOpen = onOpen;
  st.onCompare = onCompare;
  $('arch-filters')?.addEventListener('submit', (e) => { e.preventDefault(); runSearch(true); });
  ['arch-ptype', 'arch-profiles-only', 'arch-local-only', 'arch-order'].forEach(id =>
    $(id)?.addEventListener('change', () => runSearch(true)));
  $('arch-more')?.addEventListener('click', () => runSearch(false));
  $('arch-select-all')?.addEventListener('change', (e) => {
    st.results.forEach(p => e.target.checked ? st.selected.set(keyOf(p), p) : st.selected.delete(keyOf(p)));
    renderRows();
  });
  $('arch-download')?.addEventListener('click', downloadSelected);
  $('arch-compare')?.addEventListener('click', () => {
    const items = [...st.selected.values()].filter(p => p.kind === 'profile');
    if (!items.length) return toast('Select one or more profiles to compare', 'bad');
    st.onCompare?.(items);
  });
}

export async function showMissionArchive(missionId) {
  const gen = ++st.gen;
  const stale = () => gen !== st.gen;
  st.missionId = missionId;
  st.selected.clear();
  st.results = [];
  const box = $('arch-datasets');
  if (!box) return;
  box.innerHTML = '<div class="hint">Loading data sets...</div>';
  try {
    const res = await api.archiveDatasets(missionId);
    if (stale()) return;
    st.datasets = res.datasets || [];
  } catch (err) {
    box.innerHTML = `<div class="hint text-danger">Could not load data sets: ${esc(err.message)}</div>`;
    return;
  }
  st.selectedDatasets = new Set(st.datasets.filter(d => !d.portal_only).map(d => d.id));
  renderDatasets();
  if (!st.datasets.length) {
    renderEmpty('No archive data set is connected for this mission yet. Load your own files with Load File, or see the mission archive link above.');
    return;
  }
  if (st.datasets.every(d => d.portal_only)) {
    renderEmpty('This archive works through its own website. Sign in above, download the products, then use Import downloaded files.');
    return;
  }
  // Index data sets whose archive index has never been read (bundled samples
  // alone do not count), then search. Index files are small.
  for (const d of st.datasets.filter(x => !x.indexed_volumes && !x.portal_only)) {
    await indexDataset(d.id, false, true, gen);
    if (stale()) return;
  }
  await runSearch(true);
}

function coverage(d) {
  if (!d.indexed_volumes) return d.indexed_products ? `${d.indexed_products} bundled sample(s); archive not indexed yet` : 'Not indexed yet';
  const y0 = (d.first_time || '').slice(0, 10), y1 = (d.last_time || '').slice(0, 10);
  return `${d.indexed_products.toLocaleString()} products, ${y0} to ${y1}`;
}

function renderDatasets() {
  const box = $('arch-datasets');
  if (!st.datasets.length) {
    box.innerHTML = '<div class="hint">No data sets for this mission yet.</div>';
    return;
  }
  box.innerHTML = st.datasets.map(d => d.portal_only ? `
    <div class="arch-ds arch-portal">
      <span></span>
      <span class="arch-ds-main">
        <strong>${esc(d.instrument)}</strong> <span class="badge badge-warn">account needed</span>
        <span class="arch-ds-title">${esc(d.title)}</span>
        <span class="arch-ds-meta">${esc(d.portal_help)}</span>
      </span>
      <span class="arch-portal-actions">
        <a class="btn small primary" href="${esc(d.login_url)}" target="_blank" rel="noopener">Sign in to ${esc(d.archive)}</a>
        <button type="button" class="ghost small" data-import="1">Import downloaded files</button>
      </span>
    </div>` : `
    <label class="arch-ds" title="${esc(d.title)}">
      <input type="checkbox" data-ds="${esc(d.id)}" ${st.selectedDatasets.has(d.id) ? 'checked' : ''} />
      <span class="arch-ds-main">
        <strong>${esc(d.instrument)}</strong> <span class="badge">${esc(d.level)}</span>
        <span class="arch-ds-title">${esc(d.title)}</span>
        <span class="arch-ds-meta">${esc(d.archive)} &middot; <code>${esc(d.id)}</code> &middot; <span data-cov="${esc(d.id)}">${esc(coverage(d))}</span>
          ${d.needs_login ? ' &middot; <span class="badge badge-warn">account needed</span>' : ''}</span>
      </span>
      <button type="button" class="ghost small" data-index="${esc(d.id)}" title="Re-read the archive's index files">Update index</button>
    </label>`).join('');
  box.querySelectorAll('input[data-ds]').forEach(cb => cb.addEventListener('change', () => {
    cb.checked ? st.selectedDatasets.add(cb.dataset.ds) : st.selectedDatasets.delete(cb.dataset.ds);
    runSearch(true);
  }));
  box.querySelectorAll('button[data-import]').forEach(b => b.addEventListener('click', () =>
    document.getElementById('veda-file-input')?.click()));
  box.querySelectorAll('button[data-index]').forEach(b => b.addEventListener('click', async (e) => {
    e.preventDefault();
    await indexDataset(b.dataset.index, true);
    await runSearch(true);
  }));
  // Show the overall coverage as a hint; the date fields stay unrestricted.
  const span = st.datasets.filter(d => d.indexed_volumes && d.first_time);
  if (span.length) {
    const lo = span.map(d => d.first_time.slice(0, 10)).sort()[0];
    const hi = span.map(d => d.last_time.slice(0, 10)).sort().slice(-1)[0];
    $('arch-summary').textContent = `Archive coverage ${lo} to ${hi}`;
  }
}

async function pollJob(jobId, label) {
  showProgress(true, 0, label);
  for (;;) {
    await new Promise(r => setTimeout(r, 600));
    const job = await api.archiveJob(jobId);
    const pct = job.total ? Math.round(100 * job.done / job.total) : 0;
    showProgress(true, pct, job.message || label);
    if (job.status === 'running') continue;
    showProgress(false);
    if (job.status === 'login_required') {
      toast(job.message, 'bad');
      if (job.login_url) window.open(job.login_url, '_blank', 'noopener');
    } else if (job.status === 'failed') {
      toast(job.message || 'The archive request failed', 'bad');
    }
    (job.errors || []).slice(0, 3).forEach(e => toast(e, 'bad'));
    return job;
  }
}

async function indexDataset(datasetId, force, quiet = false, gen = st.gen) {
  try {
    const { job_id } = await api.archiveIndex(datasetId, force);
    const job = await pollJob(job_id, `Indexing ${datasetId}`);
    if (job.status === 'completed' && !quiet) toast(job.message, 'good');
    if (gen !== st.gen) return;            // the user moved to another mission
    const res = await api.archiveDatasets(st.missionId);
    if (gen !== st.gen) return;
    st.datasets = res.datasets || st.datasets;
    renderDatasets();
  } catch (err) {
    toast(`Could not index ${datasetId}: ${err.message}`, 'bad');
  }
}

async function runSearch(reset) {
  if (!st.missionId) return;
  const gen = st.gen;
  const token = (st.searchToken = (st.searchToken || 0) + 1);
  const ids = [...st.selectedDatasets];
  if (!ids.length) { st.results = []; st.total = 0; renderEmpty('Tick at least one data set above.'); return; }
  const start = $('arch-start')?.value, end = $('arch-end')?.value;
  if (start && end && end < start) return toast('The end date is before the start date', 'bad');
  st.busy = true;
  try {
    const res = await api.archiveSearch({
      dataset_id: ids, start, end,
      kind: $('arch-profiles-only')?.checked ? 'profile' : '',
      product_type: $('arch-ptype')?.value,
      q: $('arch-text')?.value.trim(),
      downloaded_only: $('arch-local-only')?.checked ? 'true' : '',
      newest_first: $('arch-order')?.value === 'desc' ? 'true' : '',
      limit: PAGE, offset: reset ? 0 : st.results.length,
    });
    if (gen !== st.gen || token !== st.searchToken) return;   // superseded
    st.results = reset ? res.products : st.results.concat(res.products);
    st.total = res.total;
    fillTypes(res.product_types || {});
    renderRows();
  } catch (err) {
    renderEmpty(`Search failed: ${err.message}`);
  } finally {
    st.busy = false;
  }
}

function fillTypes(types) {
  const sel = $('arch-ptype');
  if (!sel) return;
  const cur = sel.value;
  sel.innerHTML = '<option value="">All types</option>' + Object.entries(types)
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([t, n]) => `<option value="${esc(t)}" ${t === cur ? 'selected' : ''}>${esc(t)} (${n})</option>`).join('');
}

function renderEmpty(msg) {
  const body = $('arch-results-body');
  if (body) body.innerHTML = `<tr><td colspan="8" class="empty-state">${esc(msg)}</td></tr>`;
  $('arch-count').textContent = '';
  $('arch-more').hidden = true;
  updateButtons();
}

function renderRows() {
  const body = $('arch-results-body');
  if (!body) return;
  if (!st.results.length) {
    renderEmpty('No products match these filters. Widen the date range or clear the search.');
    return;
  }
  body.innerHTML = st.results.map((p, i) => {
    const ds = st.datasets.find(d => d.id === p.dataset_id);
    return `<tr data-i="${i}" class="${st.selected.has(keyOf(p)) ? 'selected' : ''}">
      <td class="arch-col-check"><input type="checkbox" data-sel="${i}" ${st.selected.has(keyOf(p)) ? 'checked' : ''} aria-label="Select ${esc(p.product_id)}" /></td>
      <td class="nowrap">${esc((p.start_time || '').replace('T', ' ').slice(0, 19)) || '-'}</td>
      <td><code>${esc(p.product_id)}</code></td>
      <td>${esc(p.product_type)}</td>
      <td>${esc(p.orbit || '')}</td>
      <td>${esc(ds ? `${ds.instrument} ${ds.level}` : p.dataset_id)}</td>
      <td>${p.downloaded ? '<span class="badge badge-ok">Downloaded</span>' : '<span class="badge">In archive</span>'}</td>
      <td>${p.kind === 'profile' ? `<button type="button" class="ghost small" data-open="${i}">Open</button>` : ''}
          <a class="small" href="${esc(p.url)}" target="_blank" rel="noopener" title="Open the archive file">Label</a></td>
    </tr>`;
  }).join('');
  body.querySelectorAll('input[data-sel]').forEach(cb => cb.addEventListener('change', () => {
    const p = st.results[+cb.dataset.sel];
    cb.checked ? st.selected.set(keyOf(p), p) : st.selected.delete(keyOf(p));
    cb.closest('tr').classList.toggle('selected', cb.checked);
    updateButtons();
  }));
  body.querySelectorAll('button[data-open]').forEach(b => b.addEventListener('click', () => openProduct(st.results[+b.dataset.open])));
  $('arch-count').textContent = `${st.results.length.toLocaleString()} of ${st.total.toLocaleString()} products`;
  $('arch-more').hidden = st.results.length >= st.total;
  updateButtons();
}

function updateButtons() {
  const n = st.selected.size;
  const dl = $('arch-download'), cmp = $('arch-compare');
  if (dl) { dl.disabled = !n; dl.textContent = n ? `Download selected (${n})` : 'Download selected'; }
  if (cmp) cmp.disabled = ![...st.selected.values()].some(p => p.kind === 'profile');
  const all = $('arch-select-all');
  if (all) all.checked = st.results.length > 0 && st.results.every(p => st.selected.has(keyOf(p)));
}

async function openProduct(p) {
  if (!p.downloaded) toast(`Downloading ${p.product_id}...`);
  await st.onOpen?.(p);
  if (!p.downloaded) { p.downloaded = true; renderRows(); }
}

async function downloadSelected() {
  const items = [...st.selected.values()].filter(p => !p.downloaded);
  if (!items.length) return toast('The selected products are already downloaded', 'good');
  try {
    const { job_id } = await api.archiveFetch(items.map(p => ({ dataset_id: p.dataset_id, product_id: p.product_id })));
    const job = await pollJob(job_id, `Downloading ${items.length} products`);
    const ok = new Set((job.result && job.result.fetched) || []);
    st.results.forEach(p => { if (ok.has(p.product_id)) p.downloaded = true; });
    renderRows();
    if (ok.size) toast(`Downloaded ${ok.size} of ${items.length} products`, ok.size === items.length ? 'good' : 'bad');
  } catch (err) {
    toast(`Download failed: ${err.message}`, 'bad');
  }
}

function showProgress(on, pct = 0, text = '') {
  const box = $('arch-progress');
  if (!box) return;
  box.hidden = !on;
  if (on) {
    $('arch-progress-fill').style.width = `${pct}%`;
    $('arch-progress-text').textContent = text;
  }
}
