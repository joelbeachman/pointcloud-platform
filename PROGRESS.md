# Progress Log

## 2026-04-02 — Initial Setup

**Completed by:** Human + Claude setup session

### Done
- Project structure created
- Express server (server.js) — REST API for dataset management
- Portal dashboard (public/index.html) — dark-themed, dataset registry
- Potree viewer (public/viewers/potree.html) — loads any Potree-format point cloud
- Cesium viewer (public/viewers/cesium.html) — 3D Tiles + demo OSM Buildings
- Gaussian Splat viewer (public/viewers/splat.html) — @mkkellogg/gaussian-splats-3d
- Panorama viewer (public/viewers/panorama.html) — Pannellum, linked scan positions
- Git initialized, remote connected to joelbeachman/pointcloud-platform
- TASKS.md created with 18 tasks across 3 days

---

## 2026-04-07 — Bulk Task Completion

**Note:** Scheduled remote agents did not run (trigger was disabled after setup). All tasks completed manually in this session.

### Completed
- **TASK-001** — npm deps verified (express, cors, multer)
- **TASK-002** — Downloaded autzen.laz (295KB, PDAL test LiDAR data — Autzen Stadium, Eugene OR)
- **TASK-003** — Generated 50k-point synthetic demo sphere point cloud; both datasets registered in datasets.json
- **TASK-004** — Downloaded nike.splat (8.3MB Gaussian splat from huggingface/cakewalk)
- **TASK-005** — Server verified: all API endpoints return correct responses
- **TASK-007/009** — Installed Python3 + pye57 + laspy + Pillow + numpy; wrote scripts/extract_e57.py (converts E57 → equirectangular panorama JPEGs + metadata.json for platform registration)
- **TASK-012** — Built public/viewers/compare.html — side-by-side viewer with draggable divider, layout switching (split H/V/fullscreen L/R)
- **TASK-013** — Added live search bar + type filter buttons to portal dashboard
- **TASK-015** — Wrote scripts/download_samples.sh — reproduces full dataset download from scratch
- **TASK-016** — Wrote scripts/test.sh — E2E tests covering API, all viewer pages, data file access
- **TASK-017** — Wrote SETUP.md — comprehensive documentation

### Skipped (reason)
- **TASK-008** — No public E57 sample file small enough to download; script is ready for user's own E57 files
- **TASK-010** — 3D Tiles aerial data requires Cesium Ion token or pre-tiled dataset; Cesium viewer is ready
- **TASK-011** — Scan position markers were already implemented at setup time in potree.html
- **TASK-014** — Info panels already built into all viewers at setup

### Pending
- **TASK-018** — Final tag v0.1.0 (next step)

### Server status
- Running at http://localhost:3000
- 3 datasets registered: Demo Sphere, Autzen Stadium LiDAR, Nike Gaussian Splat

---

## 2026-04-13 — Cesium Viewer Overhaul + Splat Pipeline

### Completed

**Cesium viewer rewrite** (`public/viewers/cesium.html`)
- Multi-layer TOC in left sidebar: add any number of `cesium` or `splat` datasets
  as independent layers, toggle visibility, fly to, remove
- Measurement tools merged in (was a separate measure.html, now deleted):
  Distance, Horizontal distance, Vertical distance, Area — all with labelled
  polyline/polygon entities and a right-side results panel
- CesiumJS upgraded to 1.140 (April 2026 release)
- Gaussian splat layers rendered via transparent Three.js canvas overlaid on
  the Cesium canvas; cameras synced every frame via ECEF→local ENU transform
  so the splat stays registered with the globe

**Splat to 3D Tiles converter** (`scripts/convert_splat.py`)
- Reads `.splat` binary (32 bytes/Gaussian: xyz, log-scale, RGBA, WXYZ rotation)
- Builds GLB with `KHR_gaussian_splatting` extension
- Outputs `splat.glb` + `tileset.json` loadable by CesiumJS 1.130+

**Nike splat converted** — `data/cesium/nike-splat/` generated and registered
as dataset `nike-splat-cesium` (type: `cesium-splat`)

**Splat viewer** (`public/viewers/splat.html`)
- Replaced OrbitControls with quaternion trackball (no gimbal lock, no poles)
- Left drag: free rotation, right drag: pan, scroll: zoom

---

## 2026-04-14 — Universal Processing Pipeline

### Completed

**Processing pipeline** (`scripts/process.py`)
- Universal converter: auto-detects format from file extension and PLY header
- **Point clouds** → 3D Tiles 1.0 `.pnts` single tile + `tileset.json`
  - Reads: LAS/LAZ (laspy), E57 (pye57), XYZ/TXT/PTS (numpy), PTX (Leica
    multi-scan format), PCD (ASCII), PLY (plyfile)
  - Preserves RGB colour when present in source
  - Uses RTC_CENTER for float32 precision over large coordinate ranges
- **Meshes** → GLB + `tileset.json`
  - Reads: OBJ, STL, GLB, GLTF, PLY (mesh) via trimesh
  - Flattens multi-mesh scenes before export
- **Gaussian splats** copied or converted
  - `.splat` files: copied to `data/splats/`, registered as type `splat`
  - 3DGS PLY (detected by `f_dc_0` property): SH DC coefficients converted
    to RGB, opacity via sigmoid, rotation normalised → packed to `.splat` binary
- Auto-registers output in `datasets.json` (or prints curl command with `--no-register`)

**Dockerfile updated** — switched from `node:20-alpine` to `node:20-slim`
(Debian-based, required for Python binary wheels — pye57 needs glibc).
Added Python processing layers: `numpy`, `laspy[lazrs]`, `pye57`, `plyfile`,
`trimesh[easy]`.

**SETUP.md updated** — full documentation for pipeline, Cesium viewer features,
all script options, Docker usage, and dataset type reference.
