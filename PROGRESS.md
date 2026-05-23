# Progress Log

> **Rule:** Update this file whenever a task is planned or completed. It is the single source of truth for what has been done and what is next.

---

## Data Safety Guidelines

`.gitignore` blocks **binary file extensions** (`.pnts`, `.splat`, `.ply`, `.glb`, `.jpg`, `.laz`, etc.)
across `data/`, not entire directories. This means all small config files (`.json`, `.csv`, `.tex`,
`.bib`) inside `data/` **are tracked by git** — a `git reset --hard` restores tilesets, metadata,
and panorama position tables. Only the binary payload needs to come from external storage.

**To prevent data loss:**
- Keep large binary data on external storage; mount via `DATA_DIR` (Docker) or symlink
- `data/eggiswil_backup/` and `data/splats/colmap_only_flight3/` are fully gitignored — external only
- Never run `git clean -fd` without a dry run (`git clean -nfd`) first
- `data/datasets.json` is the dataset registry; always commit it after registering a new dataset

**Recovery after a hard reset:**
All `.json`/`.csv` config files survive (tracked). Re-copy binaries from external storage, then:
- `scripts/restore_eggiswil.py` — re-copies panorama JPEGs + regenerates `metadata.json` from `eggiswil_backup/`

---

## 2026-04-02 — Initial Setup

### Completed
- Project structure created
- Express server (`server.js`) — REST API for dataset management
- Portal dashboard (`public/index.html`) — dark-themed, dataset registry with search + type filters
- Potree viewer (`public/viewers/potree.html`) — loads any Potree-format point cloud
- Cesium viewer (`public/viewers/cesium.html`) — 3D Tiles + OSM Buildings
- Gaussian Splat viewer (`public/viewers/splat.html`) — @mkkellogg/gaussian-splats-3d
- Panorama viewer (`public/viewers/panorama.html`) — Pannellum, linked scan positions
- Compare viewer (`public/viewers/compare.html`) — side-by-side with draggable divider
- Git initialized, remote connected to joelbeachman/pointcloud-platform

---

## 2026-04-07 — Bulk Task Completion

### Completed
- npm deps verified (express, cors, multer)
- Downloaded autzen.laz (295KB PDAL test LiDAR — Autzen Stadium, Eugene OR)
- Generated 50k-point synthetic demo sphere point cloud; both registered in `datasets.json`
- Downloaded nike.splat (8.3MB Gaussian splat from huggingface/cakewalk)
- Server verified: all API endpoints return correct responses
- Installed Python3 + pye57 + laspy + Pillow + numpy
- Wrote `scripts/extract_e57.py` — E57 → equirectangular panoramas + metadata.json
- Wrote `scripts/download_samples.sh` — reproducible dataset download from scratch
- Wrote `scripts/test.sh` — E2E tests covering API, all viewer pages, data file access
- Wrote `SETUP.md` — comprehensive documentation

### Skipped
- No public E57 sample small enough to download; `extract_e57.py` is ready for real files
- 3D Tiles aerial data requires Cesium Ion token; Cesium viewer is ready
- Scan position markers already implemented at setup in `potree.html`
- Info panels already built into all viewers at setup

---

## 2026-04-13 — Cesium Viewer Overhaul + Splat Pipeline

### Completed
- **Cesium viewer rewrite** (`public/viewers/cesium.html`)
  - Multi-layer TOC: add any number of `cesium` or `splat` datasets as layers
  - Measurement tools merged in (was separate `measure.html`, now deleted): Distance,
    Horizontal distance, Vertical distance, Area — labelled polyline/polygon entities
  - CesiumJS upgraded to 1.140
  - Gaussian splat layers via transparent Three.js canvas overlaid on Cesium canvas;
    cameras synced every frame via ECEF→local ENU transform
- **Splat → 3D Tiles converter** (`scripts/convert_splat.py`)
  - Reads `.splat` binary (32 bytes/Gaussian: xyz, log-scale, RGBA, WXYZ rotation)
  - Builds GLB with `KHR_gaussian_splatting` extension + `tileset.json`
- Nike splat converted → `data/cesium/nike-splat/`, registered as `nike-splat-cesium`
- **Splat viewer** (`public/viewers/splat.html`) — replaced OrbitControls with quaternion
  trackball (no gimbal lock, no poles)

---

## 2026-04-14 — Universal Processing Pipeline

### Completed
- **Processing pipeline** (`scripts/process.py`) — universal converter, auto-detects format
  - Point clouds → 3D Tiles 1.0 `.pnts` single tile + `tileset.json`
    - Reads: LAS/LAZ, E57, XYZ/TXT/PTS, PTX, PCD, PLY (point cloud)
    - Preserves RGB colour; uses RTC_CENTER for float32 precision
  - Meshes → GLB + `tileset.json` — reads OBJ, STL, GLB, GLTF, PLY (mesh)
  - Gaussian splats: `.splat` copied; 3DGS PLY converted (SH DC → RGB, sigmoid opacity)
  - Auto-registers output in `datasets.json`
- **Dockerfile** updated — `node:20-slim` (glibc required for Python wheels)
- **SETUP.md** updated — full pipeline, Cesium features, Docker, dataset type reference

---

## 2026-05-15 — Haus Eggiwil Dataset Processing

### Completed
- LAS file `351_Haus-Eggiwil.las` processed → `data/cesium/haus-eggiwil/` (72MB, 5,023,669 pts)
- `image_poses.csv` generated with 185 scan positions in LV95 (EPSG:2056)

### Lost in revert (recovered 2026-05-23)
- Processed panoramic JPEGs for `data/panoramas/haus-eggiwil/` — wiped by git operation
- Original `documentation/` folder contents — wiped by git reset

---

## 2026-05-23 — Data Recovery + Safety Hardening

### Completed
- Restored 185 panoramic JPEGs to `data/panoramas/haus-eggiwil/` from `data/eggiswil_backup/images/`
- Generated `data/panoramas/haus-eggiwil/metadata.json` — LV95 coords normalized to local,
  `northOffset` from `rotZ_deg`, 185 scan positions
- Registered `haus-eggiwil` in `datasets.json` (cesium 3D Tiles + panoramas path)
- Added `data/eggiswil_backup/` to `.gitignore`
- Wrote `scripts/restore_eggiswil.py` — documents and automates panorama recovery
- Added data safety guidelines to this file (top section)

---

## Pending / Planned

### High priority
- [ ] Verify panorama viewer loads haus-eggiwil correctly (check image format compatibility with Pannellum — images are per-position perspective JPEGs from scanner, may need equirectangular conversion)
- [ ] Restore documentation folder contents (thesis assets, compiled PDF, figures)
- [ ] Commit current state (datasets.json update, .gitignore, restore script)

### Medium priority
- [ ] COPC streaming support — convert LAS files to COPC for Potree streaming (better for large Ballenberg datasets)
- [ ] Metadata schema — define minimum field set per dataset (capture method, date, scanner model, CRS, point density, processing status) aligned with CIDOC-CRM
- [ ] Semantic annotations layer — clickable regions in Cesium/Potree viewer linked to documentation records
- [ ] Mobile optimization audit — test viewers on mobile; Potree-Next to be monitored as WebGPU successor
- [ ] Tag v0.1.0 once haus-eggiwil dataset is verified end-to-end

### Low priority / future
- [ ] Multi-building support — extend `datasets.json` schema for building-level grouping (toward Ballenberg archive)
- [ ] Potree-Next integration — monitor WebGPU support, plan migration path from Potree 1.8
- [ ] CIDOC-CRM metadata export — dataset-level metadata serializable to CIDOC-CRM/CRMdig
