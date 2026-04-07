// Search + filter state
let allDatasets = [];
let filterType = 'all';
let searchQuery = '';

function applyFilter() {
  let filtered = allDatasets;
  if (filterType !== 'all') filtered = filtered.filter(d => d.type === filterType);
  if (searchQuery) {
    const q = searchQuery.toLowerCase();
    filtered = filtered.filter(d =>
      (d.name || '').toLowerCase().includes(q) ||
      (d.source || '').toLowerCase().includes(q) ||
      (d.description || '').toLowerCase().includes(q)
    );
  }
  renderDatasets(filtered);
}

document.addEventListener('DOMContentLoaded', () => {
  // Search bar
  const searchEl = document.getElementById('search-input');
  if (searchEl) searchEl.addEventListener('input', e => { searchQuery = e.target.value; applyFilter(); });
  // Filter buttons
  document.querySelectorAll('[data-filter]').forEach(btn => {
    btn.addEventListener('click', () => {
      filterType = btn.dataset.filter;
      document.querySelectorAll('[data-filter]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      applyFilter();
    });
  });
});

const VIEWER_MAP = {
  pointcloud: '/viewers/potree.html',
  e57: '/viewers/potree.html',
  cesium: '/viewers/cesium.html',
  splat: '/viewers/splat.html',
  panorama: '/viewers/panorama.html',
};

const ICONS = {
  pointcloud: '&#9632;',
  cesium: '&#9679;',
  splat: '&#10022;',
  panorama: '&#9900;',
  e57: '&#11036;',
};

const BADGE_CLASS = {
  pointcloud: 'badge-pointcloud',
  cesium: 'badge-cesium',
  splat: 'badge-splat',
  panorama: 'badge-panorama',
  e57: 'badge-e57',
};

function renderDatasets(datasets) {
  const container = document.getElementById('datasets-list');
  if (datasets.length === 0) {
    container.innerHTML = `<div class="empty-state"><h3>No datasets found</h3><p>Try a different filter or <a href="#" onclick="document.getElementById('btn-add').click();return false;">add a dataset</a>.</p></div>`;
    return;
  }
  container.innerHTML = datasets.map(d => `
      <div class="dataset-row" data-id="${d.id}">
        <div class="dataset-badge ${BADGE_CLASS[d.type] || 'badge-pointcloud'}">
          <span>${ICONS[d.type] || '&#9632;'}</span>
        </div>
        <div class="dataset-info">
          <div class="dataset-name">${escHtml(d.name)}</div>
          <div class="dataset-meta">
            ${escHtml(d.type)} &middot; ${escHtml(d.source || 'unknown source')}
            ${d.description ? ' &middot; ' + escHtml(d.description) : ''}
          </div>
        </div>
        <div class="dataset-actions">
          <a href="${VIEWER_MAP[d.type] || '/viewers/potree.html'}?id=${d.id}">Open</a>
          <button class="btn-del" onclick="deleteDataset('${d.id}')">Remove</button>
        </div>
      </div>
    `).join('');
}

async function loadDatasets() {
  const container = document.getElementById('datasets-list');
  try {
    const res = await fetch('/api/datasets');
    allDatasets = await res.json();
    if (allDatasets.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <h3>No datasets yet</h3>
          <p>Add a dataset to start visualizing point clouds.</p>
        </div>`;
      return;
    }
    applyFilter();
  } catch (e) {
    container.innerHTML = `<div class="loading">Error loading datasets: ${e.message}</div>`;
  }
}

async function deleteDataset(id) {
  if (!confirm('Remove this dataset?')) return;
  await fetch(`/api/datasets/${id}`, { method: 'DELETE' });
  loadDatasets();
}

function escHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// Modal
document.getElementById('btn-add').addEventListener('click', () => {
  document.getElementById('modal').classList.remove('hidden');
});
document.getElementById('btn-cancel').addEventListener('click', () => {
  document.getElementById('modal').classList.add('hidden');
});
document.getElementById('modal').addEventListener('click', e => {
  if (e.target === e.currentTarget) e.currentTarget.classList.add('hidden');
});

document.getElementById('add-form').addEventListener('submit', async (e) => {
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

loadDatasets();
