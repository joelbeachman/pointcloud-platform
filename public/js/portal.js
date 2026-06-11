/**
 * portal.js — logic for the portal landing page (public/index.html).
 *
 * Renders the dataset catalogue as one card per house/building ("Häuser"),
 * plus a flat list for datasets without a building ("Andere Datensätze").
 * Each card/row links to the appropriate viewer page with ?id= / ?building=.
 *
 * Server endpoints used (see server.js):
 *   GET    /api/datasets      load the full dataset registry on page load
 *   POST   /api/datasets      register a new dataset via the "add" modal form
 *   DELETE /api/datasets/:id  remove a dataset (Remove button on a row)
 *
 * Rendering is plain template strings into #datasets-list; the search box
 * (#search-input) filters the in-memory list client-side and re-renders.
 */

let allDatasets = [];   // full registry from GET /api/datasets
let searchQuery = '';   // current contents of the search box (raw)

// Maps dataset.type → viewer page(s) offered for it in the flat dataset rows.
const VIEWER_MAP = {
  cesium:        [
    { label: 'Cesium',       url: '/viewers/cesium.html' },
    { label: 'Potree-Next',  url: '/viewers/potreenext.html' },
  ],
  'cesium-splat':[{ label: 'Cesium',      url: '/viewers/cesium.html' }],
  splat:         [{ label: 'Splat',       url: '/viewers/splat.html' }],
  panorama:      [{ label: 'Cesium',      url: '/viewers/cesium.html' }],
  potree:        [
    { label: 'Potree 1.8',  url: '/viewers/potree18.html' },
    { label: 'Potree-Next', url: '/viewers/potreenext.html' },
  ],
  document:      [{ label: 'Öffnen',      url: '/viewers/pdf.html' }],
  video:         [{ label: 'Abspielen',   url: '/viewers/video.html' }],
};

// Badge icon (HTML entity) per dataset type.
const ICONS = {
  pointcloud: '&#9632;', cesium: '&#9679;', splat: '&#10022;',
  panorama: '&#9900;', e57: '&#11036;', potree: '&#8857;',
  document: '&#128196;', video: '&#127916;',
};

// Badge background colour class (portal.css) per dataset type.
const BADGE_CLASS = {
  pointcloud: 'badge-pointcloud', cesium: 'badge-cesium', splat: 'badge-splat',
  panorama: 'badge-panorama', e57: 'badge-e57', potree: 'badge-potree',
  document: 'badge-document', video: 'badge-video',
};

// Escape user-supplied strings before interpolating into innerHTML templates.
function escHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// Group datasets by building; everything without a building goes into "Andere".
function groupByBuilding(datasets) {
  const houses = new Map();   // buildingId -> { id, name, datasets: [] }
  const orphans = [];
  for (const d of datasets) {
    if (d.building) {
      if (!houses.has(d.building)) {
        houses.set(d.building, { id: d.building, name: null, datasets: [] });
      }
      const h = houses.get(d.building);
      h.datasets.push(d);
      if (!h.name && d.buildingName) h.name = d.buildingName;
    } else {
      orphans.push(d);
    }
  }
  // Sort houses numerically.
  return {
    houses: Array.from(houses.values()).sort((a, b) => {
      const ai = parseInt(a.id, 10), bi = parseInt(b.id, 10);
      return ai - bi;
    }),
    orphans,
  };
}

function matchesSearch(d, q) {
  if (!q) return true;
  return [d.name, d.source, d.description, d.building, d.buildingName, d.group]
    .filter(Boolean).some(s => String(s).toLowerCase().includes(q));
}

function houseMatchesSearch(house, q) {
  if (!q) return true;
  if (String(house.id).includes(q)) return true;
  if (house.name && house.name.toLowerCase().includes(q)) return true;
  return house.datasets.some(d => matchesSearch(d, q));
}

// One-line German summary of a house's datasets, e.g. "2× Punktwolke · 1× Dokument".
function summarize(datasets) {
  const counts = { pointcloud: 0, model: 0, document: 0, video: 0, other: 0 };
  for (const d of datasets) {
    if (d.type === 'document') counts.document++;
    else if (d.type === 'video') counts.video++;
    else if (d.source === 'lidar' || d.source === 'photogrammetry') counts.pointcloud++;
    else if (d.source === 'model') counts.model++;
    else counts.other++;
  }
  const parts = [];
  if (counts.pointcloud) parts.push(`${counts.pointcloud}× Punktwolke`);
  if (counts.model)      parts.push(`${counts.model}× 3D-Modell`);
  if (counts.document)   parts.push(`${counts.document}× Dokument`);
  if (counts.video)      parts.push(`${counts.video}× Video`);
  if (counts.other)      parts.push(`${counts.other}× Sonstige`);
  return parts.join(' · ');
}

function renderHouseCard(house) {
  const title = house.name ? `${house.id} — ${escHtml(house.name)}` : `Gebäude ${house.id}`;
  const meta  = summarize(house.datasets);
  const cesiumTarget = `/viewers/cesium.html?building=${encodeURIComponent(house.id)}`;

  // Secondary buttons: which other viewers does this house have data for?
  const potree = house.datasets.find(d => d.type === 'potree');
  const doc    = house.datasets.find(d => d.type === 'document');
  const vid    = house.datasets.find(d => d.type === 'video');

  const secondary = [
    potree ? `<a href="/viewers/potreenext.html?id=${encodeURIComponent(potree.id)}" title="Punktwolke in Potree öffnen">Potree</a>` : '',
    doc    ? `<a href="/viewers/pdf.html?id=${encodeURIComponent(doc.id)}" title="PDF anzeigen">PDF</a>` : '',
    vid    ? `<a href="/viewers/video.html?id=${encodeURIComponent(vid.id)}" title="Video abspielen">Video</a>` : '',
  ].filter(Boolean).join('');

  return `
    <div class="house-card" data-bldg="${house.id}">
      <div class="house-num">${house.id}</div>
      <div class="house-body">
        <div class="house-title">${title}</div>
        <div class="house-meta">${meta || '—'}</div>
      </div>
      <div class="house-actions">
        <a href="${cesiumTarget}" class="btn-primary">Im 3D-Viewer öffnen</a>
        ${secondary ? `<div class="house-secondary">${secondary}</div>` : ''}
      </div>
    </div>`;
}

function renderDatasetRow(d) {
  const viewers = VIEWER_MAP[d.type];
  const openBtn = viewers
    ? viewers.map(v => `<a href="${v.url}?id=${encodeURIComponent(d.id)}">${escHtml(v.label)}</a>`).join('')
    : `<span style="color:#484f58;font-size:0.8rem">No viewer</span>`;
  return `
    <div class="dataset-row" data-id="${d.id}">
      <div class="dataset-badge ${BADGE_CLASS[d.type] || 'badge-cesium'}">
        <span>${ICONS[d.type] || '&#9679;'}</span>
      </div>
      <div class="dataset-info">
        <div class="dataset-name">${escHtml(d.name)}</div>
        <div class="dataset-meta">
          ${escHtml(d.type)} &middot; ${escHtml(d.source || 'unknown source')}
          ${d.description ? ' &middot; ' + escHtml(d.description) : ''}
        </div>
      </div>
      <div class="dataset-actions">
        ${openBtn}
        <button class="btn-del" onclick="deleteDataset('${d.id}')">Remove</button>
      </div>
    </div>`;
}

// Re-render the whole list (houses + ungrouped) applying the current search query.
function render() {
  const container = document.getElementById('datasets-list');
  const q = (searchQuery || '').toLowerCase().trim();
  const { houses, orphans } = groupByBuilding(allDatasets);

  const visibleHouses  = houses.filter(h => houseMatchesSearch(h, q));
  const visibleOrphans = orphans.filter(d => matchesSearch(d, q));

  if (!visibleHouses.length && !visibleOrphans.length) {
    container.innerHTML = `<div class="empty-state"><h3>Nichts gefunden</h3><p>Versuche einen anderen Suchbegriff.</p></div>`;
    return;
  }

  let html = '';
  if (visibleHouses.length) {
    html += `<div class="section-title">Häuser <span class="section-count">${visibleHouses.length}</span></div>`;
    html += `<div class="house-grid">${visibleHouses.map(renderHouseCard).join('')}</div>`;
  }
  if (visibleOrphans.length) {
    html += `<div class="section-title" style="margin-top:1.5rem">Andere Datensätze <span class="section-count">${visibleOrphans.length}</span></div>`;
    html += `<div class="orphan-list">${visibleOrphans.map(renderDatasetRow).join('')}</div>`;
  }
  container.innerHTML = html;
}

// Fetch the registry from GET /api/datasets and render it.
async function loadDatasets() {
  const container = document.getElementById('datasets-list');
  try {
    const res = await fetch('/api/datasets');
    allDatasets = await res.json();
    if (!allDatasets.length) {
      container.innerHTML = `<div class="empty-state"><h3>Keine Datensätze</h3><p>Füge einen hinzu, um loszulegen.</p></div>`;
      return;
    }
    render();
  } catch (e) {
    container.innerHTML = `<div class="loading">Error loading datasets: ${e.message}</div>`;
  }
}

// Remove a dataset via DELETE /api/datasets/:id, then reload the list.
// Must stay a global function: dataset rows reference it via inline onclick.
async function deleteDataset(id) {
  if (!confirm('Datensatz entfernen?')) return;
  await fetch(`/api/datasets/${id}`, { method: 'DELETE' });
  loadDatasets();
}

// Wire up UI events: live search, and the "add dataset" modal
// (open/cancel/backdrop-click/submit → POST /api/datasets).
document.addEventListener('DOMContentLoaded', () => {
  const searchEl = document.getElementById('search-input');
  if (searchEl) searchEl.addEventListener('input', e => { searchQuery = e.target.value; render(); });

  document.getElementById('btn-add')?.addEventListener('click', () =>
    document.getElementById('modal').classList.remove('hidden'));
  document.getElementById('btn-cancel')?.addEventListener('click', () =>
    document.getElementById('modal').classList.add('hidden'));
  document.getElementById('modal')?.addEventListener('click', e => {
    if (e.target === e.currentTarget) e.currentTarget.classList.add('hidden');
  });
  document.getElementById('add-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const payload = Object.fromEntries(fd.entries());
    await fetch('/api/datasets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    document.getElementById('modal').classList.add('hidden');
    e.target.reset();
    loadDatasets();
  });
});

loadDatasets();
