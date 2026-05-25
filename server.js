const express = require('express');
const cors = require('cors');
const path = require('path');
const fs = require('fs');
const { execFile } = require('child_process');

const app = express();
const PORT = process.env.PORT || 3000;

// DATA_DIR can be overridden via environment variable so the container
// can mount asset storage from any host path without rebuilding the image.
const DATA_DIR = process.env.DATA_DIR || path.join(__dirname, 'data');

// ── Metadata Schema Validation ─────────────────────────────────────────────────────

// Core required fields
const CORE_METADATA_FIELDS = [
  'id', 'name', 'type', 'path', 'createdAt'
];

// Optional Ballenberg-specific fields
const BALLENBERG_FIELDS = [
  'buildingId', 'captureDate', 'captureMethod', 'crs'
];

// Valid enum values
const VALID_TYPES = ['cesium', 'cesium-splat', 'potree', 'splat', 'e57', 'pointcloud'];
const VALID_CAPTURE_METHODS = ['TLS', 'UAV', 'CloseRange', 'Photogrammetry', 'StructureFromMotion'];

/**
 * Validate dataset metadata against the schema.
 * Returns { valid: boolean, errors: string[] }
 */
function validateMetadata(dataset) {
  const errors = [];

  // Check required core fields
  for (const field of CORE_METADATA_FIELDS) {
    if (dataset[field] === undefined || dataset[field] === null || dataset[field] === '') {
      errors.push(`Missing required field: ${field}`);
    }
  }

  // Validate type enum
  if (dataset.type && !VALID_TYPES.includes(dataset.type)) {
    errors.push(`Invalid type: ${dataset.type}. Must be one of: ${VALID_TYPES.join(', ')}`);
  }

  // Validate captureMethod enum
  if (dataset.captureMethod && !VALID_CAPTURE_METHODS.includes(dataset.captureMethod)) {
    errors.push(`Invalid captureMethod: ${dataset.captureMethod}. Must be one of: ${VALID_CAPTURE_METHODS.join(', ')}`);
  }

  // Validate date formats
  if (dataset.createdAt && !isValidDateTime(dataset.createdAt)) {
    errors.push(`Invalid createdAt format: ${dataset.createdAt}. Expected ISO8601 format.`);
  }
  if (dataset.captureDate && !isValidDate(dataset.captureDate)) {
    errors.push(`Invalid captureDate format: ${dataset.captureDate}. Expected YYYY-MM-DD format.`);
  }

  // Validate numeric fields
  const numericFields = ['pointDensity', 'accuracy', 'fileSize', 'pointCount', 'scanPositions'];
  for (const field of numericFields) {
    if (dataset[field] !== undefined && dataset[field] !== null && typeof dataset[field] !== 'number') {
      errors.push(`Field ${field} must be a number, got ${typeof dataset[field]}`);
    }
  }

  // Validate boolean fields
  const booleanFields = ['hasColor', 'hasIntensity', 'hasNormals', 'hasClassification'];
  for (const field of booleanFields) {
    if (dataset[field] !== undefined && dataset[field] !== null && typeof dataset[field] !== 'boolean') {
      errors.push(`Field ${field} must be a boolean, got ${typeof dataset[field]}`);
    }
  }

  return {
    valid: errors.length === 0,
    errors
  };
}

function isValidDateTime(str) {
  return !isNaN(Date.parse(str));
}

function isValidDate(str) {
  return /^\d{4}-\d{2}-\d{2}$/.test(str);
}

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// Serve data directory (point clouds, splats, panoramas)
app.use('/data', express.static(DATA_DIR));

// Resolve panoramasPath → inline panoramas array so all viewers get a consistent shape.
function resolvePanoramas(dataset) {
  if (dataset.panoramas || !dataset.panoramasPath) return dataset;
  try {
    const metaFile = path.join(DATA_DIR, dataset.panoramasPath.replace(/^\/data\//, ''));
    const meta = JSON.parse(fs.readFileSync(metaFile, 'utf8'));
    return { ...dataset, panoramas: meta.panoramas || [] };
  } catch (e) {
    return dataset;
  }
}

// API: list all datasets
app.get('/api/datasets', (req, res) => {
  const dbPath = path.join(DATA_DIR, 'datasets.json');
  if (!fs.existsSync(dbPath)) return res.json([]);
  const datasets = JSON.parse(fs.readFileSync(dbPath, 'utf8'));
  res.json(datasets.map(resolvePanoramas));
});

// API: get single dataset
app.get('/api/datasets/:id', (req, res) => {
  const dbPath = path.join(DATA_DIR, 'datasets.json');
  if (!fs.existsSync(dbPath)) return res.status(404).json({ error: 'Not found' });
  const datasets = JSON.parse(fs.readFileSync(dbPath, 'utf8'));
  const dataset = datasets.find(d => d.id === req.params.id);
  if (!dataset) return res.status(404).json({ error: 'Not found' });
  res.json(resolvePanoramas(dataset));
});

// API: register a dataset
app.post('/api/datasets', (req, res) => {
  const dbPath = path.join(DATA_DIR, 'datasets.json');
  const datasets = fs.existsSync(dbPath)
    ? JSON.parse(fs.readFileSync(dbPath, 'utf8'))
    : [];

  // Merge request body with defaults
  const dataset = {
    ...req.body,
    id: req.body.id || Date.now().toString(),
    createdAt: req.body.createdAt || new Date().toISOString(),
    source: req.body.source || 'unknown',
    description: req.body.description || ''
  };

  // Validate metadata
  const validation = validateMetadata(dataset);
  if (!validation.valid) {
    return res.status(400).json({ error: 'Validation failed', errors: validation.errors });
  }

  datasets.push(dataset);
  fs.writeFileSync(dbPath, JSON.stringify(datasets, null, 2));
  res.json(dataset);
});

// API: delete a dataset
app.delete('/api/datasets/:id', (req, res) => {
  const dbPath = path.join(DATA_DIR, 'datasets.json');
  if (!fs.existsSync(dbPath)) return res.status(404).json({ error: 'Not found' });
  let datasets = JSON.parse(fs.readFileSync(dbPath, 'utf8'));
  datasets = datasets.filter(d => d.id !== req.params.id);
  fs.writeFileSync(dbPath, JSON.stringify(datasets, null, 2));
  res.json({ ok: true });
});

// API: update (patch) a dataset
app.patch('/api/datasets/:id', (req, res) => {
  const dbPath = path.join(DATA_DIR, 'datasets.json');
  if (!fs.existsSync(dbPath)) return res.status(404).json({ error: 'Not found' });
  let datasets = JSON.parse(fs.readFileSync(dbPath, 'utf8'));
  const idx = datasets.findIndex(d => d.id === req.params.id);
  if (idx < 0) return res.status(404).json({ error: 'Not found' });

  // Merge request body
  const updated = { ...datasets[idx], ...req.body };

  // Remove keys explicitly set to null (e.g. clearing modelMatrix)
  for (const [k, v] of Object.entries(updated)) {
    if (v === null) delete updated[k];
  }

  // Validate metadata
  const validation = validateMetadata(updated);
  if (!validation.valid) {
    return res.status(400).json({ error: 'Validation failed', errors: validation.errors });
  }

  datasets[idx] = updated;
  fs.writeFileSync(dbPath, JSON.stringify(datasets, null, 2));
  res.json(updated);
});

// API: compute Helmert transformation (Python/numpy)
app.post('/api/helmert', (req, res) => {
  const input = JSON.stringify(req.body);
  const script = path.join(__dirname, 'scripts', 'helmert.py');
  const child = execFile('python3', [script], { maxBuffer: 10 * 1024 * 1024 }, (err, stdout, stderr) => {
    if (err) {
      console.error('[helmert] error:', err.message, stderr);
      return res.status(500).json({ error: err.message, stderr });
    }
    try {
      res.json(JSON.parse(stdout));
    } catch (e) {
      console.error('[helmert] JSON parse error:', e.message, stdout.slice(0, 500));
      res.status(500).json({ error: 'Invalid JSON from helmert.py' });
    }
  });
  child.stdin.write(input);
  child.stdin.end();
});

// ── Elevation profile endpoint ────────────────────────────────────────────────
// POST /api/profile
// Body: { datasetId, line:[{x,y,z},...], halfWidth, maxPoints, stride }
// line is in the tileset's LOCAL space — the client applies inverse(modelMatrix)
// before sending so the server can directly compare against .pnts positions.
// Returns [{d, z, r?, g?, b?}] sorted by d (distance along the profile line).
app.post('/api/profile', (req, res) => {
  const { datasetId, line, halfWidth = 2, maxPoints = 150000, stride = 1 } = req.body || {};
  if (!datasetId || !Array.isArray(line) || line.length < 2) {
    return res.status(400).json({ error: 'datasetId and line (≥2 points) required' });
  }

  const dbPath = path.join(DATA_DIR, 'datasets.json');
  let datasets;
  try { datasets = JSON.parse(fs.readFileSync(dbPath, 'utf8')); }
  catch (e) { return res.status(500).json({ error: 'cannot read datasets.json' }); }

  const ds = datasets.find(d => d.id === datasetId);
  if (!ds) return res.status(404).json({ error: 'dataset not found' });

  const tilesetRelPath = ds.path.replace(/^\/data\//, '');
  const tilesetPath    = path.join(DATA_DIR, tilesetRelPath);
  const tilesetDir     = path.dirname(tilesetPath);

  let tileset;
  try { tileset = JSON.parse(fs.readFileSync(tilesetPath, 'utf8')); }
  catch (e) { return res.status(500).json({ error: 'cannot read tileset: ' + e.message }); }

  // ── Build profile segments (XY only — Z is the elevation we display) ─────
  const segs = [];
  let cumDist = 0;
  for (let i = 0; i < line.length - 1; i++) {
    const p1 = line[i], p2 = line[i + 1];
    const dx = p2.x - p1.x, dy = p2.y - p1.y;
    const len = Math.sqrt(dx * dx + dy * dy);
    segs.push({ x1: p1.x, y1: p1.y, dx, dy, len, dStart: cumDist });
    cumDist += len;
  }

  // Project (px, py) onto the polyline; return { dist, d } or null if polyline has zero length.
  function projectXY(px, py) {
    let bestDist = Infinity, bestD = 0;
    for (const s of segs) {
      if (s.len < 1e-10) continue;
      let t = ((px - s.x1) * s.dx + (py - s.y1) * s.dy) / (s.len * s.len);
      t = t < 0 ? 0 : t > 1 ? 1 : t;
      const cx = s.x1 + t * s.dx, cy = s.y1 + t * s.dy;
      const dist = Math.sqrt((px - cx) ** 2 + (py - cy) ** 2);
      if (dist < bestDist) { bestDist = dist; bestD = s.dStart + t * s.len; }
    }
    return { dist: bestDist, d: bestD };
  }

  // ── 4×4 column-major matrix helpers ──────────────────────────────────────
  const ID4 = [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1];
  function m4mul(A, B) {
    const R = new Float64Array(16);
    for (let r = 0; r < 4; r++)
      for (let c = 0; c < 4; c++)
        for (let k = 0; k < 4; k++) R[c * 4 + r] += A[k * 4 + r] * B[c * 4 + k];
    return Array.from(R);
  }
  function m4pt(M, x, y, z) {
    return [
      M[0]*x + M[4]*y + M[8]*z + M[12],
      M[1]*x + M[5]*y + M[9]*z + M[13],
      M[2]*x + M[6]*y + M[10]*z + M[14],
    ];
  }
  function isIdentity(M) { return M.every((v, i) => v === ID4[i]); }

  // ── Walk tileset tree, collect .pnts tiles with cumulative transforms ─────
  const tiles = [];
  function collectTiles(node, baseDir, parentTx) {
    const tx = node.transform ? m4mul(parentTx, node.transform) : parentTx;
    if (node.content?.uri?.endsWith('.pnts')) {
      const fp = path.join(baseDir, node.content.uri);
      if (fs.existsSync(fp)) tiles.push({ fp, tx });
    }
    for (const child of (node.children || [])) collectTiles(child, baseDir, tx);
  }
  collectTiles(tileset.root, tilesetDir, ID4.slice());

  if (tiles.length === 0) return res.status(404).json({ error: 'no .pnts tiles found' });

  // ── Parse each tile ───────────────────────────────────────────────────────
  const results = [];
  const hw = Number(halfWidth);
  const maxPts = Math.min(Number(maxPoints) || 150000, 500000);
  const eff_stride = Math.max(1, Math.round(Number(stride) || 1));
  const BLOCK = 262144; // points per I/O block (~3 MB for positions)

  for (const tile of tiles) {
    if (results.length >= maxPts) break;

    let fd;
    try { fd = fs.openSync(tile.fp, 'r'); }
    catch (e) { continue; }

    try {
      const hdr = Buffer.alloc(28);
      if (fs.readSync(fd, hdr, 0, 28, 0) < 28) continue;
      if (hdr.slice(0, 4).toString('ascii') !== 'pnts') continue;

      const ftJSONLen = hdr.readUInt32LE(12);
      const ftJSONBuf = Buffer.alloc(ftJSONLen);
      if (fs.readSync(fd, ftJSONBuf, 0, ftJSONLen, 28) < ftJSONLen) continue;
      const ft = JSON.parse(ftJSONBuf.toString('utf8'));

      const nPts    = ft.POINTS_LENGTH;
      const rtc     = ft.RTC_CENTER || [0, 0, 0];
      const posOff  = ft.POSITION?.byteOffset ?? 0;
      const rgbOff  = ft.RGB?.byteOffset ?? null;
      const hasRGB  = rgbOff !== null;
      const binStart = 28 + ftJSONLen;
      const hasTx   = !isIdentity(tile.tx);
      const tx      = tile.tx;

      const posBuf = Buffer.alloc(BLOCK * 12);
      const rgbBuf = hasRGB ? Buffer.alloc(BLOCK * 3) : null;

      for (let blk = 0; blk < nPts && results.length < maxPts; blk += BLOCK) {
        const cnt = Math.min(BLOCK, nPts - blk);
        if (fs.readSync(fd, posBuf, 0, cnt * 12, binStart + posOff + blk * 12) < cnt * 12) break;
        if (hasRGB && rgbBuf) fs.readSync(fd, rgbBuf, 0, cnt * 3, binStart + rgbOff + blk * 3);

        for (let i = 0; i < cnt && results.length < maxPts; i += eff_stride) {
          const o = i * 12;
          let px = rtc[0] + posBuf.readFloatLE(o);
          let py = rtc[1] + posBuf.readFloatLE(o + 4);
          let pz = rtc[2] + posBuf.readFloatLE(o + 8);
          if (hasTx) { [px, py, pz] = m4pt(tx, px, py, pz); }

          const proj = projectXY(px, py);
          if (proj.dist <= hw) {
            const pt = { d: proj.d, z: pz };
            if (hasRGB && rgbBuf) {
              const ri = i * 3;
              pt.r = rgbBuf[ri]; pt.g = rgbBuf[ri + 1]; pt.b = rgbBuf[ri + 2];
            }
            results.push(pt);
          }
        }
      }
    } finally {
      fs.closeSync(fd);
    }
  }

  results.sort((a, b) => a.d - b.d);
  res.json(results);
});

// Health check
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', time: new Date().toISOString() });
});

// API: validate dataset metadata without saving
app.post('/api/datasets/validate', (req, res) => {
  const validation = validateMetadata(req.body);
  if (validation.valid) {
    res.json({ valid: true });
  } else {
    res.status(400).json({ valid: false, errors: validation.errors });
  }
});

// API: get metadata schema
app.get('/api/metadata/schema', (req, res) => {
  res.json({
    coreFields: CORE_METADATA_FIELDS,
    validTypes: VALID_TYPES,
    validCaptureMethods: VALID_CAPTURE_METHODS,
    optionalFields: [
      'scannerModel', 'flightAltitude', 'groundDistance', 'scanPositions',
      'operator', 'campaignId', 'pointDensity', 'pointCount', 'accuracy',
      'resolution', 'hasColor', 'hasIntensity', 'hasNormals', 'hasClassification',
      'sourcePath', 'sourceFormat', 'processedBy', 'processingDate', 'processingNotes',
      'modelMatrix', 'helmertLV95', 'description', 'fileSize', 'coverage',
      'tags', 'constructionPhase', 'region', 'era', 'buildingType', 'catalogNumber',
      'panoramas'
    ]
  });
});

// ── Cesium CDN proxy ─────────────────────────────────────────────────────────
// Routes Cesium.js and all Workers through our server so we can patch the
// files before they run in the browser / worker threads.
//
// Root cause of "t.value.slice is not a function":
//   Workers/decodeSpz.js calls @spz-loader/core WASM which returns an
//   Emscripten vector (not a Float32Array) for gcloudData.positions/rotations/
//   scales when the SPZ binary is unrecognised.  The worker then does
//   `gcloudData.positions.slice()` (or equivalent), which throws because
//   Emscripten vectors don't have .slice().
// ─────────────────────────────────────────────────────────────────────────────

const CESIUM_CDN_BASE = 'https://cesium.com/downloads/cesiumjs/releases/1.140/Build/Cesium';

// Safe typed-array helper injected at the top of patched JS files.
// Works in both window (main thread) and self (worker) contexts.
// _gsplatTA: for positions/rotations/scales → always returns Float32Array.
// _safeSlice: generic safe .slice() — returns same type or plain Array copy.
const SAFE_TA_HELPER =
  'var _gsplatTA=function(v){' +
    'if(!v)return new Float32Array(0);' +
    'if(v instanceof Float32Array)return v.slice();' +
    'if(ArrayBuffer.isView(v))return new Float32Array(v.buffer,v.byteOffset,v.byteLength>>>2);' +
    'var n=(typeof v.size==="function")?v.size():(v.length>>>0);' +
    'var a=new Float32Array(n);' +
    'for(var i=0;i<n;i++)a[i]=(typeof v.get==="function")?v.get(i):(v[i]||0);' +
    'return a;' +
  '};' +
  'var _safeSlice=function(v){' +
    'if(!v||typeof v!=="object")return void 0;' +
    'if(typeof v.slice==="function")return v.slice(0);' +
    'if(typeof v.length==="number")return Array.prototype.slice.call(v);' +
    'return void 0;' +
  '};';

// ── Patch helpers ─────────────────────────────────────────────────────────────

function diagScan(label, code) {
  console.log(`[cesium-proxy] --- DIAG ${label} (${(code.length/1024).toFixed(0)} KB) ---`);
  const p = (re) => (code.match(re)||[]).length;
  console.log(`  value.slice()       : ${p(/\.value\.slice\(\)/g)}`);
  console.log(`  value.slice(0)      : ${p(/\.value\.slice\(0\)/g)}`);
  console.log(`  typedArray.slice()  : ${p(/\.typedArray\.slice\(\)/g)}`);
  console.log(`  .slice() total      : ${p(/\.slice\(\)/g)}`);
  console.log(`  .slice(0) total     : ${p(/\.slice\(0\)/g)}`);
  console.log(`  getAttributeBySem…  : ${p(/getAttributeBySemantic/g)}`);
  console.log(`  KHR_gaussian        : ${p(/KHR_gaussian/g)}`);
  console.log(`  GaussianSplat       : ${p(/GaussianSplat/g)}`);
  console.log(`  processSpz          : ${p(/processSpz/g)}`);
  console.log(`  decompress          : ${p(/decompress/g)}`);
  console.log(`  gcloudData          : ${p(/gcloudData/g)}`);
  console.log(`  positions           : ${p(/positions/g)}`);
  // Print up to 3 contexts around .slice() calls
  const hits = [...code.matchAll(/[\w$]+\.[\w$]+\.slice\(\)/g)].slice(0, 3);
  hits.forEach(m => {
    const ctx = code.slice(Math.max(0, m.index-80), m.index + m[0].length + 30);
    console.log(`  ctx: …${ctx}…`);
  });
  console.log(`[cesium-proxy] --- END DIAG ${label} ---`);
}

function patchJs(label, code) {
  let count = 0;
  let out = code;

  // All patches are applied cumulatively (not cascading).

  // 1. getAttributeBySemantic(...).typedArray.slice()
  out = out.replace(
    /([\w.]*getAttributeBySemantic\([^)]+\))\.typedArray\.slice\(\)/g,
    (_, c) => { count++; return `_gsplatTA(${c}.typedArray)`; },
  );

  // 2. Any .typedArray.slice() or .typedArray.slice(0)
  out = out.replace(
    /\b(\w+(?:\.\w+)*)\.typedArray\.slice\(0?\)/g,
    (_, c) => { count++; return `_gsplatTA(${c}.typedArray)`; },
  );

  // 3. VertexArray addAttribute pattern: t.value.slice(0)
  //    Original: value:r?t.value.slice(0):void 0
  //    The .value here is a constant attribute array, not a typed array.
  //    Use _safeSlice which preserves type and handles non-arrays gracefully.
  out = out.replace(
    /\b(\w+)\.value\.slice\(0\)/g,
    (_, c) => { count++; return `_safeSlice(${c}.value)`; },
  );

  // 4. Any remaining .value.slice() (no args)
  out = out.replace(
    /\b(\w+(?:\.\w+)*)\.value\.slice\(\)/g,
    (_, c) => { count++; return `_safeSlice(${c}.value)`; },
  );

  console.log(`[cesium-proxy] ${label}: patched ${count} slice() call(s)`);
  return SAFE_TA_HELPER + '\n' + out;
}

// ── Cesium.js proxy ───────────────────────────────────────────────────────────

let _cesiumPromise = null;

app.get('/cesium-proxy/Cesium.js', (_req, res) => {
  if (!_cesiumPromise) {
    const cdnUrl = `${CESIUM_CDN_BASE}/Cesium.js`;
    console.log('[cesium-proxy] Fetching Cesium.js from CDN…');
    _cesiumPromise = fetch(cdnUrl)
      .then(r => { if (!r.ok) throw new Error(`CDN ${r.status}`); return r.text(); })
      .then(text => {
        console.log(`[cesium-proxy] Downloaded ${(text.length/1024/1024).toFixed(1)} MB`);
        diagScan('Cesium.js', text);
        return patchJs('Cesium.js', text);
      })
      .catch(err => { _cesiumPromise = null; throw err; });
  }

  _cesiumPromise
    .then(text => {
      res.setHeader('Content-Type', 'application/javascript; charset=utf-8');
      res.setHeader('Cache-Control', 'public, max-age=3600');
      res.send(text);
    })
    .catch(err => {
      console.error('[cesium-proxy] Cesium.js error:', err.message);
      res.redirect(`${CESIUM_CDN_BASE}/Cesium.js`);
    });
});

// ── Worker proxy ──────────────────────────────────────────────────────────────
// All workers are fetched from CDN and served through here.
// decodeSpz.js gets the same safe-slice patch as Cesium.js.

const _workerCache = new Map();

app.get('/cesium-proxy/Workers/:worker', (req, res) => {
  const workerName = req.params.worker;
  if (!_workerCache.has(workerName)) {
    const cdnUrl = `${CESIUM_CDN_BASE}/Workers/${workerName}`;
    console.log(`[worker-proxy] Fetching ${workerName} from CDN…`);
    const p = fetch(cdnUrl)
      .then(r => { if (!r.ok) throw new Error(`CDN ${r.status}`); return r.text(); })
      .then(text => {
        console.log(`[worker-proxy] Downloaded ${workerName} (${(text.length/1024).toFixed(0)} KB)`);
        if (workerName === 'decodeSpz.js') {
          diagScan('decodeSpz.js', text);
          return patchJs('decodeSpz.js', text);
        }
        return text;
      })
      .catch(err => { _workerCache.delete(workerName); throw err; });
    _workerCache.set(workerName, p);
  }

  _workerCache.get(workerName)
    .then(text => {
      res.setHeader('Content-Type', 'application/javascript; charset=utf-8');
      res.setHeader('Cache-Control', 'public, max-age=3600');
      res.send(text);
    })
    .catch(err => {
      console.error(`[worker-proxy] ${workerName} error:`, err.message);
      res.redirect(`${CESIUM_CDN_BASE}/Workers/${workerName}`);
    });
});

// ── Generic Cesium CDN pass-through (Assets, ThirdParty, etc.) ────────────────

app.get('/cesium-proxy/*', (req, res) => {
  const subPath = req.params[0];
  res.redirect(`${CESIUM_CDN_BASE}/${subPath}`);
});

// ── Debug: inspect patched Cesium.js at a given line ──────────────────────────
app.get('/cesium-proxy/debug/:line', async (req, res) => {
  if (!_cesiumPromise) return res.status(503).send('Cesium.js not loaded yet');
  try {
    const text = await _cesiumPromise;
    const line = parseInt(req.params.line, 10);
    const lines = text.split('\n');
    const start = Math.max(0, line - 6);
    const end = Math.min(lines.length, line + 5);
    const snippet = lines.slice(start, end).map((l, i) => {
      const ln = start + i + 1;
      const marker = ln === line ? '>>>' : '   ';
      return `${marker} ${ln}: ${l.slice(0, 300)}`;
    }).join('\n');
    res.type('text/plain').send(snippet);
  } catch (e) { res.status(500).send(e.message); }
});

app.listen(PORT, () => {
  console.log(`Point Cloud Platform running at http://localhost:${PORT}`);
});
