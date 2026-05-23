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

## 2026-05-23 — Panorama Viewer: Spatial Hotspots + Orientation Fix

### Completed
- **Spatial navigation hotspots** (`public/viewers/panorama.html`)
  - Camera-icon hotspots (same orange SVG as Potree markers) pointing toward nearby scan positions
  - Icons scaled by distance (56 px at 0.5 m → 24 px at ≥6.25 m), hard cutoff at 10 m horizontal
  - Compass heading preserved on jump: `compass = getYaw() + northOffset_src`, `initYaw = compass - northOffset_dst`
  - Removed 6-marker hard limit; filter is now purely distance-based (≤10 m)
  - Navigation opens in same tab (not new tab) from Potree camera markers
- **Quaternion-derived `northOffset`** — fixed systematic orientation errors
  - Root cause: Leica scanner stores Euler ZYX angles; near |rotation|≈180° two Euler decompositions
    give the same physical orientation but different `rotZ_deg` values (differ by 180°)
  - Fix: compute `northOffset = atan2(1−2(qy²+qz²), 2(qx·qy+qw·qz))` directly from quaternion
    columns of `image_poses.csv` — unique regardless of gimbal-lock variant
  - Regenerated all 185 `northOffset` values in `data/panoramas/haus-eggiwil/metadata.json`
  - Added `scripts/regen_northoffset.pl` — documents and automates the regeneration
- **Hotspot anchor fix** — icons were anchored at bottom-right instead of center
  - Pannellum already centers hotspot divs via `offsetWidth/2`; our additional
    `margin-left: -s/2; margin-top: -s/2` was doubling the offset
  - Removed negative margins from both CSS class and `createTooltipFunc` inline style

---

## 2026-05-23 — Panorama Overlay in Cesium Viewer

### Completed
- **In-page panorama overlay** (`public/viewers/cesium.html`)
  - Clicking a camera marker opens the panorama as an overlay covering only `#cesiumContainer`
    (`top:100px; bottom:0; left:220px; right:220px`); both sidebars remain fully visible
  - Overlay bar shows scan label, LV95 coordinates, and a close button; Escape also closes
  - Full spatial navigation hotspots (same logic as standalone panorama.html)
  - Prev/next scan navigation within the dataset
  - Compass heading preserved when jumping between scans
- **Measurement integration**: when a measurement tool is active, clicking inside the panorama
  casts a ray into the Cesium scene (`pickFromRay`) and feeds the hit point to the existing
  measurement tools (Distance, Horizontal, Vertical, Area, Coords)
  - Ray construction: `bearing = clickYaw + northOffset` → ENU vector →
    ECEF via `Cesium.Transforms.eastNorthUpToFixedFrame` at scan's ECEF position
  - Click yaw/pitch derived from Pannellum's current view using perspective projection formula
  - Right-click in panorama finishes area or cancels current measurement, matching Cesium canvas behavior
  - Blue "Click in panorama to place measurement point" hint shown when a tool is active
- Pannellum CSS/JS loaded in `<head>`; hover tooltip suppressed while overlay is open

---

## Pending / Planned

### High priority
- [ ] Verify panorama images are equirectangular — scanner perspective JPEGs may need conversion before Pannellum can display them correctly
- [ ] Update `scripts/restore_eggiswil.py` to use quaternion-derived `northOffset` formula (currently stores `rotZ_deg` directly)
- [ ] Restore documentation folder contents (thesis assets, compiled PDF, figures)
- [ ] Tag v0.1.0 once haus-eggiwil is verified end-to-end

### Medium priority
- [ ] COPC streaming support — convert LAS files to COPC for Potree streaming (better for large Ballenberg datasets)
- [ ] Metadata schema — define minimum field set per dataset (capture method, date, scanner model, CRS, point density, processing status) aligned with CIDOC-CRM
- [ ] Semantic annotations layer — clickable regions in Cesium/Potree viewer linked to documentation records
- [ ] Mobile optimization audit — test viewers on mobile; Potree-Next to be monitored as WebGPU successor

### Low priority / future
- [ ] Multi-building support — extend `datasets.json` schema for building-level grouping (toward Ballenberg archive)
- [ ] Potree-Next integration — monitor WebGPU support, plan migration path from Potree 1.8
- [ ] CIDOC-CRM metadata export — dataset-level metadata serializable to CIDOC-CRM/CRMdig
