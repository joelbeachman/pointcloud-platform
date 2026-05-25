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

## 2026-05-23 — Panorama Viewer: Measurement Tools

### Completed
- **Measurement panel** (`public/viewers/panorama.html`)
  - Right-side panel (220 px, matches Cesium sidebar style) with tool buttons and results list
  - **Horizontal distance** — 2 clicks; ray–floor-plane intersection at configurable z-offset; result in metres
  - **Angular distance** — 2 clicks; great-circle angle between click directions on unit sphere; result in degrees
  - **Area** — n-click floor-plane polygon; shoelace formula; result in m² or ha
- **Canvas overlay** (`<canvas id="measure-canvas">`) redraws committed measurement markers each rAF frame
  - Committed points stored in LV95 → reprojected via `lv95ToYawPitch` each frame; visible from any scan position
  - In-progress points tracked by (yaw, pitch) relative to current scan; cleared on navigation
- **`#measure-capture`** transparent intercept overlay — `pointer-events: all` only when a tool is active; blocks Pannellum pan so measurement clicks register correctly
- Floor Z offset input (±0.1 m step) adjusts assumed measurement plane height
- Keyboard: Escape cancels in-progress; Backspace removes last area point; right-click finishes area or cancels

---

## 2026-05-23 — Measurement Markers in Cesium Panorama Overlay

### Completed
- **Removed standalone panorama viewer tab** from all nav bars (portal, potree, cesium, splat,
  compare) and from the portal viewer-card grid; panorama functionality lives exclusively in
  the Cesium overlay
  - Potree scan-position click now opens `cesium.html?id=...` instead of `panorama.html`
  - `portal.js` routes `panorama` dataset type to `cesium.html`
  - Compare viewer picker no longer lists panorama as an option
- **Removed nike splat datasets** (`nike-splat`, `nike-splat-cesium`) from `datasets.json`
- **Measurement markers in panorama overlay** (`public/viewers/cesium.html`)
  - `<canvas id="pano-canvas">` overlaid on `#pano-div` (z-index 5, pointer-events none)
  - `yawPitchToPanoCanvas` — perspective projection with full `isFinite` / hfov guards
    to survive WebGL context loss or invalid viewer state
  - `ecefToPanoYawPitch(ecef)` — inverse projection: ECEF → ENU at scan → compass bearing
    → Pannellum yaw/pitch; uses `layer.tileset.modelMatrix` (LV95→ECEF) already set by
    `addLayer`
  - `drawPanoCanvas` rAF loop reads directly from `curPts` (in-progress) and
    `measurements[].pts` (committed) every frame — markers appear whether the panorama was
    open or closed when measurements were placed
  - `commit()` now stores `pts: [...curPts]` so committed measurements project correctly
  - `doCoords()` now stores `pts: [ecef]` so coordinate-inspection points also appear
  - `panoFloorPick` fallback for panorama-click measurements when 3D raycast misses
    point cloud geometry
  - Canvas resized on overlay open and window resize; rAF loop stops when overlay closes

---

## 2026-05-24 — Measurement Refinements + Potree Removal + Scan Station Toggle

### Completed
- **Measurement display cleanup** (`public/viewers/cesium.html`)
  - Removed all text labels from Cesium 3D scene and panorama canvas
  - Measurements show only geometry (points, lines, polygons) + a sequential number label
  - Sequential number (`m.num`) shown in panel # column, 3D scene, and panorama canvas
  - Coords tool: dot only in scene, full coordinates in panel only
  - Area polygons close in panorama canvas; number floats above line midpoint / at area centroid
- **Potree viewer removed** — Cesium is now the sole point cloud viewer
  - Deleted `public/viewers/potree.html`
  - Removed Point Cloud nav from all pages; compare viewer defaults to Cesium vs Cesium
  - Portal simplified: only cesium / cesium-splat / splat types in Add Dataset modal
- **Scan station visibility toggle** (`public/viewers/cesium.html`)
  - Checkbox in left panel (between Layers and Measurement Tools) toggles all scan position billboards
  - Also hides/shows Pannellum navigation hotspots in the panorama overlay
  - Toggling while panorama is open reloads the current scan at the same yaw immediately

---

## 2026-05-24 — Clip Box Feature

### Completed
- **Clip Box** (`public/viewers/cesium.html`)
  - "Clip Box" tool button in left panel (below measurement tools, gold colour `#e3b341`)
  - Floating panel (top-left of viewer canvas) with X/Y/Z min/max number inputs (offsets in metres from bounding-sphere centre)
  - **Seed** button: reads first loaded tileset's bounding sphere, seeds all 6 inputs to ±radius so the box wraps the full dataset
  - **Inside** mode (default): `ClippingPlaneCollection` with `unionClippingRegions: true` — clips everything outside the box, shows only the interior window
  - **Outside** mode: flipped plane normals with `unionClippingRegions: false` — clips the box interior, shows everything outside it
  - **Apply** button: builds and applies 6 `Cesium.ClippingPlane` objects (via `ClippingPlaneCollection.modelMatrix = getRefMatrix()`) to all loaded tilesets
  - **Remove** button: disables planes, removes wireframe (panel stays open for re-adjustment)
  - Yellow **wireframe box** (12 polyline edges) updates live as values are typed, disappears when clip box is toggled off
  - Escape key closes the clip box panel and removes clip planes/wireframe
  - New layers loaded while clip box is active automatically get the current clip planes applied
  - Fixed pre-existing bug: duplicate `loadDatasets()` boot call removed (was calling twice, adding default layer twice)

---

## 2026-05-24 — Clip Box Clipping Fixed

### Root cause (commit 7f1a8c0)
Three bugs found by reading the Cesium 1.140 source directly:

1. **ClippingPlane clips the NEGATIVE side** (`dot(n,p)+d < 0`), not the positive side.
   The API says "renders the half-space on the outside of each plane", where "outside" means
   the negative half-space. All 6 planes had their normals reversed.

2. **Missing `planes.modelMatrix`** on the `ClippingPlaneCollection`.
   Cesium's bounding-volume intersection test uses `clippingPlanesOriginMatrix × planes.modelMatrix`
   as the effective matrix to transform planes into world space for testing against the ECEF
   bounding sphere. Without a `modelMatrix`, the test was comparing ECEF sphere coordinates
   against LV95-scale plane distances → degenerate result every time → all-or-nothing behaviour.

3. **Plane distances in LV95 absolute** (millions of metres) instead of ENU-relative.
   Precision edge cases could cause problems; more importantly, the whole coordinate-space
   analysis was wrong because of bugs 1+2.

### Fix
- `planes.modelMatrix = Cesium.Matrix4.fromTranslation(cbOriginLV95)` — shifts planes from
  ENU-relative into LV95 absolute. Effective bounding-volume matrix becomes `enu_at_centroid`,
  so the ECEF sphere is tested against ENU-relative planes in metres. ✓
- Shader: `test_pos = (E−E0, N−N0, H−H0)` (ENU-relative metres). ✓
- Planes rewritten with correct inward/outward normals and distances in metres from centroid.

---

## 2026-05-24–25 — Clip Box UX Fixes + Mode/Wireframe Redesign

### Completed
- **"Untoggle to activate" bug fixed** (`cbApplyEditor`)
  - Root cause: `cbApplyEditor` only called `applyActiveClipBox()` when `cb.enabled` was already
    true. New boxes start `enabled: false`, so Apply had no effect on first use.
  - Fix: Apply always sets `cb.enabled = true` (disabling other boxes first), then always calls
    `applyActiveClipBox()`.
- **Clipping decoupled from wireframe visibility** (`showWireframe` flag)
  - Added `cb.showWireframe` (default `true`) to each clip box object.
  - `cbBuildWireframe` returns early when `showWireframe === false`; clipping planes are driven
    solely by `cb.enabled` — wireframe state has no effect on clipping.
- **Mode button redesign** (`cb.inside` is now `true | false | null`)
  - **Inside** — `cb.inside = true`; clips outside the box, shows interior
  - **Outside** — `cb.inside = false`; clips inside the box, shows exterior
  - **None** — `cb.inside = null`; no clipping planes applied, wireframe still visible (box is a
    visual reference only). `applyActiveClipBox` returns early when `inside === null`.
- **"Show box" toggle** — independent button in editor panel; hides/shows wireframe without
  touching clipping state. Works in all three modes.
- **Two-way wireframe sync** between editor panel and clip box list
  - List checkbox now controls `cb.showWireframe` (wireframe visibility), not `cb.enabled`.
    Dot opacity still reflects `cb.enabled` (clipping active) as a separate indicator.
  - New `cbToggleWireframe(id, show)` function drives both: sets the flag, builds/clears wireframe,
    updates the editor "Show box" button if that box is open in the editor.
  - "Show box" button calls `renderClipBoxList()` after toggling to keep the list checkbox in sync.
- List mode badge updated: ▣ Inside, □ Outside, ○ None.

---

## 2026-05-25 — Clip Box Interactive Gizmo Handles

### Completed
- **7 drag handles per clip box** (`public/viewers/cesium.html`)
  - Shown only when the editor panel is open; removed on close
  - **6 face handles** (colored by axis: red=±East, green=±North, blue=±Up) placed at face centres
    — drag moves that face along its axis only; opposite face stays fixed; minimum box size 0.5 m
  - **1 gold centre handle** — drag translates the entire box freely in 3D
  - Handles use `CallbackProperty` positions → follow the box live during drag without manual update
- **Drag math**: screen-aligned plane through the handle at mousedown; `rayPlane` intersection on
  every mousemove; ENU delta projected onto constraint axis for face handles; full ENU delta for centre
- **Camera lock**: `screenSpaceCameraController` all axes disabled during drag, restored on mouseup
- **Live feedback**: wireframe, clipping planes, and editor input fields all update every mousemove
- **Hover UX**: cursor → `grab`; gold tooltip label shows handle purpose ("Resize +North", "Move box", etc.)
  Cursor → `grabbing` during drag. Handle clicks are suppressed from measurement / panorama logic.
- **`cbEnuMatrix` cache**: ENU→ECEF matrix computed once in `initClipOrigin()`, shared by new
  `cbEnuToEcef` / `cbEcefToEnu` helpers — avoids recomputing per-frame for each handle

---

## 2026-05-25 — Panorama Area Fill

### Completed
- **Transparent polygon fill for area measurements** (`public/viewers/cesium.html`)
  - Committed area polygons now render a `#a371f7` fill at ~20% opacity in the panorama canvas
  - In-progress area previews (≥3 points) show the same fill at ~13% opacity to distinguish
    from finished measurements while still clicking
  - Fill is drawn first (bottom layer), outline and vertex dots drawn on top — correct z-order
  - Non-area tools (distance, horizontal, vertical, coords) unchanged

---

## 2026-05-25 — Panorama Measurement Bug Fixes

### Completed
- **Panorama canvas projection precision fix** (`public/viewers/cesium.html`)
  - Old click handler used decoupled `atan(dx/f)` / `atan(dy/f)` — independent formulas that
    are only exact at the image center; off-center clicks mapped to a slightly wrong yaw/pitch
    due to missing cross-coupling between horizontal and vertical angles
  - Fix: replaced with the exact inverse of the perspective projection: unproject canvas pixel
    into a camera-space ray `(dx/f, -dy/f, 1)`, rotate to world space using the same camera
    axes as `yawPitchToPanoCanvas`, then extract `yaw = atan2(wx, wz)` and
    `pitch = atan2(wy, sqrt(wx²+wz²))`. Clicks now round-trip exactly at any position.
- **Panorama cursor override** (`public/viewers/cesium.html`)
  - Pannellum sets `cursor: grab` inline on its inner canvas, overriding CSS class rules.
  - Fix: added `!important` and `*` child selector — `body.measuring #pano-div *` — so
    crosshair takes effect during active measurement for precise click placement.
- **Area polygon anchor preservation when vertices leave the viewport**
  - Phase 1: `projectEcefPts` now keeps off-canvas-but-in-front vertices (`vis=false`)
    instead of filtering them. Area paths include all vertices; canvas clips rendering at
    boundary. Vertex dots suppressed for off-canvas points.
  - Phase 2: `yawPitchToPanoCanvas` no longer returns `null` for `dotFwd ≤ 0` (point >90°
    from camera direction). Instead clamps `dotFwd` to `0.05`, projecting behind-camera
    vertices far off-canvas in the correct lateral direction. Canvas clipping cuts the
    fill/outline at the canvas edge — polygon shape stays intact when a corner pans off-screen.

---

## 2026-05-25 — Multiple Clip Boxes + Box Rotation + Boolean Clipping

### Completed
- **Multiple simultaneous clip boxes** (`public/viewers/cesium.html`)
  - Any number of clip boxes can be active at once; each has an independent enabled toggle
  - Scrollable clip box list in left panel; gold dot = clipping active, faded = disabled
  - `applyClipBoxes()` combines all enabled boxes into a single `ClippingPlaneCollection`
    per tileset — efficient tile-level culling
- **Box rotation handles** — three draggable rotation rings (X=red, Y=green, Z=blue)
  - Each ring is a 40-segment circle on the corresponding face plane, radius = 1.35× face diagonal
  - Drag angle computed from projected box center on screen; delta applied to `cb.rotX/Y/Z`
  - `cbRotMatrix(cb)` builds Rz·Ry·Rx row-major 3×3; plane normals rotated via matrix columns
  - Rotation angle inputs (X°, Y°, Z°) in editor panel; rings and wireframe update live
- **Boolean inside+outside clipping** (`applyClipBoxes`, `cbBuildMixedShader`)
  - Pure inside-only or outside-only: fast `ClippingPlaneCollection` path (unchanged)
  - Mixed mode (any inside box + any outside box active simultaneously): switches to
    `Cesium.CustomShader` for per-fragment GLSL boolean evaluation
  - Shader transforms `positionMC → eye-space (czm_modelView) → ENU (u_eyeToEnu uniform)`
    to avoid float32 ECEF precision errors (~0.5 m) — computation stays in camera-relative
    space where values are small
  - `u_eyeToEnu = ecefToEnu × invView` updated every frame via `scene.preRender` listener
  - Switching back to pure mode or disabling all boxes removes the shader and listener
    (`cbClearCustomShader`)

---

## 2026-05-25 — Elevation Profile (Höhenprofil)

### Completed
- **Elevation Profile tool** (`public/viewers/cesium.html`, `server.js`)
  - New "Profile" tool button in the left panel (orange, chart icon), below the existing measurement tools
  - **Drawing**: click to add waypoints on the 3D scene (same pick logic as measurement tools);
    orange dashed polyline with dots shows the drawn line; right-click (≥2 pts) computes the profile
  - Profile line waypoints are converted from ECEF → tileset-local space
    (`Matrix4.inverseTransformation(tileset.modelMatrix)`) before sending to the server, so the
    comparison with .pnts binary positions works regardless of which coordinate system the dataset uses
  - **Server endpoint** `POST /api/profile` (`server.js`)
    - Accepts `{datasetId, line, halfWidth, maxPoints, stride}` (line in tileset-local space)
    - Walks the tileset tree (`tileset.json`), accumulates per-tile `transform` matrices
    - Streams each `.pnts` file in 262K-point blocks; parses `POINTS_LENGTH`, `RTC_CENTER`,
      `POSITION` and `RGB` from the feature table; applies cumulative tile transforms
    - Filters points within `halfWidth` meters of the profile polyline (perpendicular distance)
    - Projects surviving points to `(d, z)` — distance along the line and elevation
    - Returns up to 150K points as `[{d, z, r?, g?, b?}]` sorted by `d`
  - **Profile panel** — floating panel at the bottom of the viewer (between the two sidebars)
    - Width input (m) and layer selector in the header; Esc or ✕ to close
    - 2D scatter plot on a `<canvas>` with axis labels (elevation vs. distance)
    - Points drawn via `ImageData` as 2×2px dots — efficient for 150K points
    - Coloured by original RGB if available, otherwise viridis-like elevation gradient
    - Hover tooltip showing `d` and `z` at cursor position

---

## 2026-05-25 — Potree Viewers: Scan Markers + Clickable Panorama Overlay

### Completed
- **Potree 1.8 viewer** (`public/viewers/potree18.html`) — new file, replacing the deleted `potree.html`
  - Loads Haus Eggiwil point cloud from `data/potree/haus-eggiwil/metadata.json`
  - Fetches `data/panoramas/haus-eggiwil/metadata.json`; creates 185 orange debug spheres via
    `Potree.Utils.debugSphere(viewer.scene.scene, {x,y,z}, 0.3, 0xf0883e)` at **full LV95 world coords**
    (no bounding-box subtraction — `viewer.scene.scene` uses LV95 world space, matching the camera)
  - Canvas click handler: projects each sphere via `THREE.Vector3.project(camera)` → NDC → screen px;
    20 px pick radius; drag guard (>5 px movement discards click)
  - Pannellum equirectangular overlay (same CSS/HTML/JS structure as Cesium viewer): scan label,
    LV95 coordinate bar, prev/next scan navigation, close button
- **Potree-Next viewer** (`public/viewers/potreenext.html`) — new file
  - 185 `Mesh` spheres (`geometries.sphere`, `NormalMaterial`) placed at LV95 scan positions;
    `PhongMaterial` avoided — its `render()` calls deprecated `renderer.getGpuBuffers()` which
    throws unconditionally, killing the `requestAnimationFrame` loop (FPS drops to 0)
  - Canvas click handler: builds `viewProj = cam.proj × cam.view`; projects each marker via
    `new Vector4(x,y,z,1).applyMatrix4(viewProj)` → clip space → NDC → screen px; same 20 px threshold
  - Same Pannellum panorama overlay as Potree 1.8

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
