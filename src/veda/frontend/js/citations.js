/**
 * "What to cite": VEDA remembers (on this computer only) which data sets you
 * opened and which features you used, and the Cite panel lists exactly the
 * references those need: data sets and instrument papers, archive
 * acknowledgements, SPICE when you used geometry, the libraries behind derived
 * quantities and figures, and VEDA itself, with BibTeX and a data
 * availability statement to copy.
 */
import { el, toast } from './ui.js';

const KEY = 'veda_usage_v1';
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function load() {
  try {
    const u = JSON.parse(localStorage.getItem(KEY) || '{}');
    return { datasets: u.datasets || {}, features: u.features || {}, volumes: u.volumes || {} };
  } catch (_) {
    return { datasets: {}, features: {}, volumes: {} };
  }
}

function save(u) {
  try { localStorage.setItem(KEY, JSON.stringify(u)); } catch (_) { /* private mode: keep in memory only */ }
}

let usage = load();

/** A product was opened: remember its VEDA data set and archive data set id. */
export function recordProduct(p) {
  if (!p || !p.dataset_id) return;
  usage.datasets[p.dataset_id] = new Date().toISOString();
  if (p.volume) {
    const v = new Set(usage.volumes[p.dataset_id] || []);
    v.add(p.volume);
    usage.volumes[p.dataset_id] = [...v].slice(-40);
  }
  save(usage);
}

/** A feature was used: geometry, derived, comparison, image, publication_figure, figure_export. */
export function recordFeature(name) {
  usage.features[name] = new Date().toISOString();
  save(usage);
}

function copy(text, what) {
  navigator.clipboard.writeText(text).then(() => toast(`${what} copied`, 'good'),
    () => toast('Could not copy; select the text and copy it manually', 'bad'));
}

/** Body of the Cite drawer. */
export function citeBody() {
  const box = el('div', { class: 'stack cite-body' });
  const n = Object.keys(usage.datasets).length;
  box.innerHTML = `<p class="hint">Loading the references for ${n} data set${n === 1 ? '' : 's'}&hellip;</p>`;
  fetch('/api/veda/citations', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ datasets: Object.keys(usage.datasets), features: Object.keys(usage.features), volumes: usage.volumes }),
  }).then(r => r.json()).then(r => render(box, r)).catch(err => {
    box.innerHTML = `<p class="hint text-danger">Could not build the reference list: ${esc(err.message)}</p>`;
  });
  return box;
}

function render(box, r) {
  const item = (t, doi) => `<li>${esc(t).replace(/(https:\/\/doi\.org\/\S+)/, '<a href="$1" target="_blank" rel="noopener">$1</a>')}</li>`;
  const data = r.data.length ? r.data.map(d => `
      <div class="cite-ds">
        <strong>${esc(d.mission)} ${esc(d.instrument)}</strong> <span class="hint">${esc(d.archive)}</span>
        <p>${esc(d.data_citation)}</p>
        ${d.archive_ids.length ? `<p class="hint">Archive data sets and volumes you used (cite these identifiers): ${d.archive_ids.map(esc).join(', ')}</p>` : ''}
        ${d.papers.length ? `<ul>${d.papers.map(p => item(p.text)).join('')}</ul>` : ''}
      </div>`).join('')
    : '<p class="hint">You have not opened any archive product yet. Open products and this list fills in by itself.</p>';
  box.innerHTML = `
    <p>Everything below follows from what you opened and used in VEDA on this computer
      (${r.data.length} data set${r.data.length === 1 ? '' : 's'}${r.missions.length ? ` from ${r.missions.length} mission${r.missions.length === 1 ? '' : 's'}` : ''}).
      Cite the data, the instrument papers, the tools, and VEDA.</p>
    <div class="cite-actions">
      <button type="button" class="primary small" data-copy="bib">Copy all BibTeX (${r.n_references})</button>
      <button type="button" class="ghost small" data-copy="text">Copy as text</button>
      <button type="button" class="ghost small" data-copy="stmt">Copy data availability statement</button>
      <button type="button" class="ghost small" data-clear>Start a new list</button>
    </div>
    <h3>Data and instrument papers</h3>
    ${data}
    ${r.acknowledgements.length ? `<h3>Acknowledgements</h3><ul>${r.acknowledgements.map(a => `<li><strong>${esc(a.archive)}:</strong> ${esc(a.text)}</li>`).join('')}</ul>` : ''}
    ${r.features.map(f => `<h3>${esc(f.title)}</h3><ul>${f.items.map(i => item(i.text)).join('')}</ul>`).join('')}
    <h3>VEDA</h3>
    <ul><li>${esc(r.veda.text)}</li></ul>
    <h3>Data availability statement</h3>
    <blockquote class="policy-quote">${esc(r.statement)}</blockquote>
    <details><summary>BibTeX</summary><pre class="about-bibtex">${esc(r.bibtex)}</pre></details>
    <p class="hint">References were checked against Crossref; entries without a DOI say so. Your list is stored only in this browser.</p>`;
  const asText = () => [
    ...r.data.flatMap(d => [d.data_citation, ...(d.archive_ids.length ? [`Archive data sets: ${d.archive_ids.join(', ')}`] : []), ...d.papers.map(p => p.text)]),
    ...r.acknowledgements.map(a => a.text), ...r.features.flatMap(f => f.items.map(i => i.text)), r.veda.text,
  ].join('\n');
  box.querySelector('[data-copy="bib"]').addEventListener('click', () => copy(r.bibtex, 'BibTeX'));
  box.querySelector('[data-copy="text"]').addEventListener('click', () => copy(asText(), 'References'));
  box.querySelector('[data-copy="stmt"]').addEventListener('click', () => copy(r.statement, 'Statement'));
  box.querySelector('[data-clear]').addEventListener('click', () => {
    usage = { datasets: {}, features: {}, volumes: {} };
    save(usage);
    box.replaceWith(citeBody());
  });
}
