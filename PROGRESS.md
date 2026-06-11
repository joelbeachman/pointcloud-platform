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
- **Potree v1 viewer removed** — the original `public/viewers/potree.html` was deleted as part of this cleanup.
  - Note (2026-06-07): Potree was later reintroduced in two replacement viewers
    `potree18.html` (Potree 1.8, WebGL) and `potreenext.html` (Potree-Next, WebGPU
    experimental), both vendored under `public/libs/`. The Add Dataset modal now
    supports `potree` and the Compare viewer offers Cesium vs Potree side-by-side.
  - Compare viewer defaults to Cesium vs Cesium for the symmetric case; Cesium vs Potree
    is one click away.
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

## 2026-05-25 — Potree Viewers: Measurement Bridge + Raycast Picking + UI Layout

### Completed
- **Measurement bridge to Potree native systems** (both Potree viewers)
  - `bridgeToPotreeNext(tool, pts)`: creates a `DistanceMeasure`, adds markers via `addMarker(new Vector3(...))`,
    pushes to `potree.measure.measures[]`, opens the measurements tab by clicking sidebar section button [2]
  - `bridgeToPotree18(tool, pts)`: creates `Potree.Measure` with `showDistances`/`showArea`/`closed` flags,
    calls `viewer.scene.addMeasurement(m)`; opens measurements panel via `$('#menu_measurements').next().slideDown()`
  - Panorama measurements committed via right-click → saved in Potree's own measurement panel
  - "Clear" button calls `viewer.scene.removeMeasurement` / removes from `potree.measure.measures[]`
- **Point cloud raycast picking** (both Potree viewers)
  - `raycastPotreeNext(origin, dir)`: walks loaded octree nodes, AABB prune, 0.008 rad cone test,
    positions from `node.geometry.buffer` as Float32 at offset 0, relative to `pc.position` (LV95_min)
  - `raycastPointCloud18(origin, dir)`: iterates `pc.visibleNodes`, reads
    `node.geometryNode.geometry.attributes.position.array` (node-local Float32), translates via
    `node.sceneNode.matrixWorld.elements[12,13,14]` (world translation = LV95_node_min)
  - Floor-plane fallback retained: used only when raycast returns null
  - `panoFloorPick` bug fixed: `pitchRad >= 0` guard replaced with `Math.abs(dirZ) < 0.02`
    (was blocking all measurements looking slightly downward)
- **Panorama replaces render area only** (sidebar stays visible)
  - Potree-Next: `#pano-overlay` moved into canvas span (second grid column) in `installSidebar().then()`
    callback; `position: absolute; inset: 0; z-index: 200` fills only the render column
  - Potree 1.8: `#pano-overlay` placed inside `#potree_render_area` in HTML; render area has
    `left: 350px` transition so panorama follows the sidebar automatically
  - `#pano-measure-capture`: `position: absolute; inset: 0; z-index: 6; pointer-events: none`;
    activated via `body.pano-measuring` class; intercepts canvas clicks before Pannellum
- **Potree measurement button interception** (both viewers)
  - Capture-phase `document.addEventListener('click', handler, true)` with `stopImmediatePropagation()`
  - Potree-Next: matches `.potree_sidebar_button[title]` — Distance→distance, Height→horizontal, Circle→area
  - Potree 1.8: matches `img.button-icon` by `src` pattern — `/distance.svg`, `/height.svg`, `/area.svg`,
    `/circle.svg`
  - `installPanoInterceptor()` / `uninstallPanoInterceptor()` called on open/close
  - Tools not available in panorama mode (angle, azimuth, volume) grayed out on open, restored on close
- **Potree viewers added to navigation** (`public/index.html`, nav bars in all viewer pages)
  - Potree 1.8 and Potree-Next appear in the portal dashboard and nav menus
  - Compare viewer dropdown now includes both Potree viewers as options

---

## 2026-05-25 — Potree Measurement Tool Fixes + Toolbar Integration

### Completed
- **Point measurement tool** (both viewers)
  - Potree-Next: imports `PointMeasure`; single click commits immediately; bridged via `PointMeasure`
    (not `DistanceMeasure`); `'Point'` added to sidebar interceptor toolMap
  - Potree 1.8: `doPoint()` added; `bridgeToPotree18` sets `showCoordinates = true` for point;
    `/point\.svg/` pattern added to button interceptor
  - `MTC` color map extended with `point: { hex: '#f0883e' }` in both viewers
- **Measurements tab toggling closed on commit** (Potree-Next)
  - Root cause: `bridgeToPotreeNext` always called `btn.click()` on the section button, which
    toggled the tab closed if it was already open
  - Fix: check `sidebar.elSectionContent.querySelector('#measurements_panel')` before clicking —
    only open if measurements panel is not already visible
- **Panorama measure bar cleanup** (both viewers)
  - Distance/Horiz./Area tool-select buttons hidden on panorama open (`display: none`)
  - Potree sidebar/toolbar is now the sole tool-selection interface; Floor offset + Clear remain
  - Buttons restored to visible on panorama close
- **Potree 1.8 button interception not firing** (bug fix)
  - Root cause: graying code set `img.parentElement.style.pointerEvents = 'none'` on `li#tools`,
    which disabled pointer events for ALL children including the non-grayed buttons
  - Fix: removed the parent pointer-events assignment; grayed buttons retain `pointer-events: none`
    on the `img` itself, which is sufficient to block their click handlers
- **Potree-Next toolbar buttons** (`#potree_toolbar`)
  - A second set of measurement buttons (`input.potree_toolbar_button`) exists in the viewer toolbar
    alongside the sidebar, with titles "Point Measure", "Distance Measure", "Circle Measure"
  - Extended `installPanoInterceptor` to also match `.potree_toolbar_button` with the additional
    title mappings; both sidebar and toolbar buttons now activate panorama tools when pano is open

---

## 2026-05-28 — Blender Model Integration Pipeline (Gesamtmodell)

### Completed
- **Full scene audit** (`data/blender/scene_audit.json`) — 4 collections, 22.8M total vertices:
  - `Häuser` (716K verts): all building meshes, sub-collections `Mit_Nummer` / `Ohne_Nummer`, local bbox [64–1547, 29–640, 2–145] m
  - `Terrain` (921K verts): DTM terrain tiles (DTM3–DTM21), vegetation (L/M/S_Tree_Buche/Fichte/Tanne), ground surfaces — sub-collections `Abschnitte / Wege / Bodentypen`, `Wald`
  - `Terrain_Substitute` (10.2M verts): `PG_Dronenflug`, `swisstopo_V0.1`, `dtm_swissalti_2` — high-res reference meshes, excluded from web tiles
  - `Misc` (10.9M verts): imported point clouds (`- Cloud` suffix) — already in platform as separate datasets, excluded
- **Installed server-side tools**: `pyproj 3.7.2`, `gltfpack 0.20`
- **`scripts/export_blender_glb.py`** — Blender Python script (run headless or in Scripting tab):
  - Recursively traverses sub-collections of `Häuser`; each **leaf collection** → one GLB (preserves building hierarchy)
  - Exports `Terrain` collection as a single combined `terrain.glb`
  - Computes per-building bbox + vertex count; writes `data/blender/export/manifest.json`
- **`scripts/generate_3dtiles.py`** — server-side pipeline (no Blender required):
  - Reads `manifest.json`; for each building GLB runs `gltfpack` at 3 LOD levels: LOD0 (full), LOD1 (−70%), LOD2 (−95%)
  - Computes correct LV95→ECEF transform via `pyproj` at origin (E=2648466.518, N=1177343.008, H=570.290)
  - glTF Y-up axis convention respected: column mapping East→X, Up→Y, −North→Z
  - Generates `data/cesium/gesamtmodell/tileset.json` with REPLACE refinement LOD hierarchy per building
  - Auto-registers `gesamtmodell` dataset in `data/datasets.json`

### How to run
1. On a machine with Blender (3.x or 4.x):
   ```
   blender --background data/blender/Gesamtsmodell_V3.blend \
           --python scripts/export_blender_glb.py
   ```
2. Copy `data/blender/export/` to the server
3. On the server:
   ```
   python3 scripts/generate_3dtiles.py
   ```
4. Load `gesamtmodell` dataset in the Cesium viewer

### Executed on server (2026-05-28)
- Blender 4.0.2 installed from apt (arm64, headless)
- OOM on first attempt: 4.9GB .blend file + export_apply modifier evaluation exceeded 7.7GB RAM
- Fix: purge all packed images from Blender memory before export; use export_apply=False (skips Boolean modifier evaluation) and export_materials='PLACEHOLDER' (material colours only, no textures)
- Result: 132 buildings exported, terrain.glb (142MB → 60MB after gltfpack −95% decimation), tileset.json generated
- Post-processed all 397 GLBs to remove zero-scale nodes (hidden Blender objects exported as singular matrices, crashing CesiumJS matrix inversion)
- Terrain GLB had no materials after gltfpack stripped them; injected a `doubleSided: true` default material so terrain is visible from above

### Geo-registration calibration (2026-05-28)
The tileset root transform in `data/cesium/gesamtmodell/tileset.json` was iteratively calibrated
against visible reference features. Final values baked into `scripts/generate_3dtiles.py`:

| Parameter | Value | Reason |
|---|---|---|
| LV95 origin | E=2648466.518, N=1177343.008 | Blender scene origin in LV95 |
| Orthometric height | H=570.290 m | Blender Z=0 plane in LHN95 |
| Geoid undulation | +47.5 m | LHN95 → WGS84 ellipsoidal height (Switzerland) |
| Height fine-tune | +1.5 m | Empirical vertical alignment |
| Effective ellipsoidal H | 619.29 m | H + geoid + fine-tune |
| Yaw | +2.2° | CCW rotation of model around local Up (empirically calibrated) |
| ECEF origin | (4,335,367, 614,920, 4,622,876) | After all corrections |

**Key lessons:**
- `compute_transform` must use `eastNorthUpToFixedFrame` column order (East/North/Up), **not** Y-up column order (East/Up/−North). CesiumJS applies an internal Y-up→Z-up correction to glTF content *before* applying the tile transform, so the transform maps from a Z-up ENU frame.
- pyproj EPSG:2056 (2D) treats the passed Z as ellipsoidal height — Swiss geoid grid (CHGeo2004hn) is not installed, so the `~47.5 m` LHN95→WGS84 correction is applied manually.

**Measurement fix:**
- `getRefMatrix()` in `cesium.html` previously returned `ts.modelMatrix` (IDENTITY for gesamtmodell, since it is positioned by its own `tileset.json` transform). Measurements were therefore in raw ECEF space.
- Fixed: when `modelMatrix === IDENTITY`, build `eastNorthUpToFixedFrame(boundingSphere.center)` as the measurement frame → horizontal = geographic horizontal, vertical = LV95 Up.

### Pending
- [ ] Tune `geometricError` per building based on actual sizes (currently size × 0/1/5)
- [ ] Add full textures by re-exporting `1._Bauphase` (detailed farmhouse) and `V2` (109K verts) with higher fidelity

---

## 2026-05-31 → 2026-06-05 — Multi-datatype integration + Blender pipeline hardening + Wissam-Präsentation

### Completed — Building-centric navigation

- Backfilled `building`, `phase`, `phaseLabel`, `isGroupMaster`, `buildingName` on every dataset via new `scripts/backfill_building_phase.py`. Currently 159 datasets across 94 indexed buildings, 17 group masters, 12 entries with `buildingName`.
- Portal landing page restructured (`public/js/portal.js`, `public/index.html`): one card per house grouped by `building`, type-filter buttons removed in favor of search-only navigation, "Andere Datensätze" section below for non-building entries.
- Cesium viewer (`public/viewers/cesium.html`): layer list now clusters layers by `building` under collapsible group headers with master checkbox (checked / indeterminate / unchecked tri-state), visible-count badge, fly-to per group.
- Cesium "Add Layer" modal regrouped by building first (label `"NNN — buildingName"`), falls back to `ds.group`, then "Andere"; a per-group "Ganzes Gebäude laden" button bulk-loads via the same logic as `?building=NNN`.
- New URL parameter `?building=NNN` on the Cesium viewer: loads ALL cesium-compatible datasets for that house at once, point cloud (source=lidar/photogrammetry) auto-on, models/phases off, falls back to the "alle Phasen" master if no point cloud. `activeBuildingPinned` keeps the docs panel locked to the chosen building.
- Default Cesium landing (no URL params) now opens the Gesamtmodell instead of "first compatible dataset."

### Completed — Documents, videos, and the "Dokumente & Medien" sidebar

- Added new dataset types `document` and `video` in `datasets.json` schema, portal `VIEWER_MAP` / `ICONS` / `BADGE_CLASS`, and `public/css/portal.css`.
- New standalone viewers: `public/viewers/pdf.html` (iframe wrapper) and `public/viewers/video.html` (HTML5 `<video>` OR YouTube `<iframe>` based on `youtubeId`).
- New "Dokumente & Medien" section in the Cesium right sidebar that filters to the active building. PDFs open as a slide-out overlay (left of the right sidebar, ~45% of viewport); point cloud stays interactive in the remaining viewport.
- Video Picture-in-Picture (`#video-pip`) supports both `<video>` (mp4) and `<iframe>` (YouTube) via a generic `#video-pip-stage` container that swaps content based on `ds.youtubeId`.
- Registered three new datasets:
  - `doc-351-bauernhaus-eggiwil` — Bauhistorische Dokumentation für Geb. 351
  - `doc-752-stallscheune-meggen` — Bauhistorische Dokumentation für Geb. 752
  - `vid-351-drone-yk0sxdykx9w` — Drohnenflug-Ausschnitt (YouTube embed, start=95 end=119)
- Linked `haus-eggiwil` and `haus-eggiwil-potree` point clouds to building 351 via the backfill script's `EXPLICIT_BUILDINGS` dict.

### Completed — Blender export hardening (`scripts/export_blender_glb.py`)

- Added CLI flags via the `--` separator: `--building NNN`, `--phase N`, `--skip-terrain`. Filter is applied recursively, so it works even when buildings are nested under category collections (`Häuser → Mit_Nummer → 2025_752`).
- Auto-disambiguation of GLB filenames: when a leaf collection's name doesn't already contain the parent's building number, the GLB filename gets that number appended. So a generic collection literally named `1. Bauphase` under parent `2025_752` writes to `1._Bauphase_752.glb` instead of stomping on other buildings' `1._Bauphase.glb`.
- Phase-container detection: when a non-leaf collection's name matches `N. Bauphase`, its descendants are merged into one GLB instead of being exported as separate child GLBs. Fixes the case where a Bauphase is structured as a parent of WIP sub-collections (e.g. 752's `2. Bauphase` holding `test` + `new`).
- Removed the eye-icon hide filter (`obj.hide_get()`). Only the explicit render-disable flag (`obj.hide_viewport`) still excludes objects, so artists' temporary outliner toggles no longer silently drop collections from the export.
- Loud warnings on empty leaf collections: when a leaf has mesh verts in source but zero objects pass the export filter, a `[WARNING]` is printed and bubbled up into `manifest["errors"]` (and printed at the end). No more silent skips.
- Manifest now carries `focused: bool`, `building_filter`, `phase_filter`, `terrain_exported` so downstream tools know whether they're looking at a full or partial export.

### Completed — 3D Tiles generation hardening (`scripts/generate_3dtiles.py`)

- **Merge mode instead of wipe.** `register_datasets()` now upserts: keeps every existing `gesamtmodell_*` entry not in the current manifest, replaces matching IDs, warns about preserved entries pointing at missing tileset files on disk. A focused per-building re-export no longer drops the other buildings.
- **Main tileset preserved on focused runs.** When `manifest["focused"]` is set and `tileset.json` already exists, the main is left untouched. Per-building tilesets still get written. The Gesamtmodell view is only rewritten on a full export (no filter flags).

### Completed — Backfill script (`scripts/backfill_building_phase.py`)

- New file: authoritative source for derived dataset fields. Runs after `generate_3dtiles.py` and is fully idempotent.
- `EXPLICIT_BUILDINGS` dict: pinpoint dataset IDs to building numbers when the regex-from-group derivation can't reach them (point clouds, documents, videos without a `group` field).
- `BUILDING_NAMES` dict: building-number → friendly name lookup (currently 351 → "Bauernhaus Eggiwil", 752 → "Stallscheune Meggen"); propagated as `buildingName` to every dataset matching that building.
- `MANUAL_RELABELS` dict: per-id field overrides for hand-fixing known-broken Blender exports. Now empty since the 752 export was fixed at source; the block is documented as the place to add future workarounds.

### Completed — Documentation for the supervisor meeting

- `documentation/PIPELINE.md` (new): codebase + pipeline architecture, library inventory, archival-workflow proposal addressing the 4.9 GB monolith Blender file.
- `documentation/PIPELINE_BITES.md` (new): 35+ self-contained, slide-sized explanation snippets organized A–I, plus a P section with concrete step-by-step pipelines (Blender, LiDAR, documents/video, browser-side house-loading sequence).
- `documentation/PRESENTATION_MONDAY.md` (new): structured German-language presentation outline answering Wissam's email — 4-part schema *(Anwendung → Daten → Pipeline → Demo)* for each of UC1–UC4, with each use case explicitly tagged to research questions RQ1–RQ5 from `pointclouds.tex`. Closing matrix maps each RQ to evidence + remaining gaps.

### Bug fixes

- **Building 752 — both phases looked alike.** Root cause: Blender file had `2. Bauphase` structured as a parent of WIP sub-collections `test` + `new`. The export descended into them and emitted `test.glb` + `new.glb`. Fixed by adding the phase-container detection in `export_blender_glb.py`.
- **Building 752 — Bauphase 1 collided across buildings.** Root cause: generic collection name `1. Bauphase` under parent `2025_752` wrote to `1._Bauphase.glb`, overwriting any other building's identically-named phase. Fixed by the parent-disambiguation rule in `export_blender_glb.py`.
- **Focused export wiped all other buildings.** Ran `blender ... --building 752`, then `generate_3dtiles.py` — the latter's old wipe-and-reregister logic removed every non-752 `gesamtmodell_*` entry from `datasets.json`. Recovered by parsing `extras.label` from each remaining `tileset_*.json` on disk (the label encodes parent/leaf identity as `"<parent> — <leaf>"`); reconstructed 146 gesamtmodell entries. Fixed for future runs by making `register_datasets()` a merge.
- **Focused export emptied the main tileset.** `tileset.json` was overwritten with only the 3 buildings from the focused manifest, leaving `root.children: []`. Recovered via `git checkout HEAD -- data/cesium/gesamtmodell/tileset.json`. Prevented in future runs by the `manifest["focused"]` gate.
- **The MANUAL_RELABELS block became stale.** After a clean 752 re-export the relabeled IDs no longer existed; the relabels would have silently no-op'd but were misleading. Block cleared.

### Recovery & forensic notes

- `data/datasets.json`'s `gesamtmodell_*` entries are NOT committed in git in any meaningful version — they're a derived artifact of `generate_3dtiles.py`. The non-gesamtmodell entries (point clouds, PDFs, video, samples) ARE preserved across runs.
- 146 tileset `.json` files (config) ARE tracked. GLBs and binary payload are gitignored. Hence the recovery path works: tilesets + their `extras.label` survive a generate run, even if `datasets.json` is wiped.
- Main `tileset.json` IS tracked → `git checkout HEAD` is a one-line recovery.
- The "what survives a focused export wipe" decision tree is now codified in `documentation/PIPELINE.md` § 5.

### Lessons

- The Blender file structure (collection naming, hierarchy depth) directly determines the dataset IDs in the platform. Generic collection names (`1. Bauphase` without a building suffix) create silent collisions. The right fix is at the source (rename in Blender), but the export script now also defensively disambiguates.
- A wipe-and-rewrite registration step is fine for one-shot setups but lethal for focused iterations. Merge-or-die: any tool that writes to a shared registry should merge by ID, not replace by prefix.
- The `extras.label` field in a tileset.json is a quietly load-bearing piece of metadata — it's what made post-wipe reconstruction possible. Document this contract.
- "What goes into git" deserves a one-pager. Today's split (tracked: scripts + config + small JSON; gitignored: binary payload + the .blend) survived multiple incidents — that lesson should not be in someone's head.

### Pending

- [ ] Migrate `Gesamtsmodell_V3.blend` from monolith (4.9 GB) to per-building `.blend` files (~200 MB each). Proposed structure in `documentation/PIPELINE.md` § 5.1.
- [ ] Migrate `data/datasets.json` to `data/datasets/<id>.json` once entry count climbs past ~500. Proposed in `documentation/PIPELINE.md` § 5.3.
- [ ] Real FEM data for UC3 — currently using plausibility colors; CustomShader pipeline is ready to ingest numeric values.
- [ ] User-group validation of the platform (Konservator / Forscher / Besucher personas) — required for definitive answers to RQ2 + RQ5.
- [ ] Re-export the Gesamtmodell with the hardened `export_blender_glb.py` so that every building benefits from the parent-disambiguation rule and the phase-container collapse.

---

## 2026-06-05 — Swisstopo terrain + vertical-datum migration + historical-position editor

### Completed — Swisstopo quantized-mesh terrain

- Integrated the swisstopo terrain provider `https://3d.geo.admin.ch/ch.swisstopo.terrain.3d/v1/` via `CesiumTerrainProvider.fromUrl()` with `requestVertexNormals: true` (vertex normals for lighting). Free, no token, Apache-2.0-compatible — matches the project's "no Ion" stance.
- Added a **Terrain** checkbox to the Zeitreise section in the left sidebar. Independent of the Luftbilder / Karten toggles; turning any of the three on makes the globe visible, all three off hides it (preserves the minimalist single-tile-set default).
- Removed the **Höhen-Offset** slider and its supporting machinery (`groundElevationWgs84()`, `getManualOffset()`, the raised-`Cesium.Globe(raised_ellipsoid)` rewrite per toggle). Real terrain replaces all of it.
- Set `viewer.scene.globe.baseColor = '#3d4a3a'` (muted moss-green) and `showGroundAtmosphere = false` so the "terrain alone, no imagery" view shows a neutral landscape instead of the default blue ocean tint.

### Completed — Vertical-datum migration (LN02 orthometric everywhere)

Discovered that swisstopo's terrain serves heights in LN02 orthometric (the Swiss vertical datum), NOT WGS84 ellipsoidal as the Cesium quantized-mesh spec assumes. Our project up to this point had buildings + point clouds in WGS84 ellipsoidal via a +47.5 m geoid correction; this caused a ~47 m float of buildings above terrain.

The fix was applied in three places to bring the whole project onto LN02 orthometric:

- **`scripts/generate_3dtiles.py`**: `GEOID_UNDULATION = 0.0`, `HEIGHT_OFFSET = 0.0`. The previous +47.5 m + 1.5 m was correct for Cesium-on-bare-ellipsoid but wrong with a real terrain provider.
- **All 146 tileset.json files in `data/cesium/gesamtmodell/`**: back-patched `root.transform` with the new GEOID=0 / HEIGHT=0 transform. ECEF origin shifted from `(4335367, 614920, 4622876)` to `(4335334, 614916, 4622840)` — exactly the geoid+fine-tune offset removed.
- **`public/viewers/cesium.html`** — `lv95ToWgs84` / `wgs84ToLv95`: dropped the geoid-undulation term in the height calculation. Heights now pass through unchanged (LN02 orthometric in, LN02 orthometric out). This fixed the point-cloud float (`haus-eggiwil`) which positions itself at runtime via `lv95ModelMatrix()` — that path didn't go through the tileset transform.

The round-trip invariant on `lv95ToWgs84 ↔ wgs84ToLv95` still holds. Helmert, historic placement, panoramas, and the Tragwerk sub-tilesets all share the same convention now — internally consistent.

Intermediate step (since reverted): briefly used a runtime height-shift monkey-patch on the terrain provider (`requestTileGeometry` wrap, `_minimumHeight`/`_maximumHeight` += 47.5). Worked but coupled to Cesium internals; replaced with the data-side fix as the proper solution.

### Completed — Historical-position editor

Added a floating "Historische Position bearbeiten" panel that pops up when a layer with `historicalLV95` is toggled into historic mode:

- Three fields: **E**, **N** (metres, integer), **Yaw** (degrees, fractional). Each row has ±1, ±5, ±10 / ±1, ±5 nudge buttons. Direct numeric input works too.
- **Arrow keys** when panel is focused but not in an input: ←→ nudge E ±1 m, ↑↓ nudge N ±1 m, Shift+←/→ rotate Yaw ±1°.
- Live preview: every change rebuilds `historicalModelMatrix` via the same `buildHistoricalModelMatrix(ds, ts)` used at load time; what you see while nudging is what gets persisted.
- **Speichern** → `PATCH /api/datasets/:id` with the new `historicalLV95`. Button feedback briefly flips to `✓ N gespeichert` (or `✗ N fehlgeschlagen`).
- **Zurücksetzen** restores values from when the panel was opened (or from the last save).

### Completed — Building-aware historical position

The first version of the editor only operated on the one dataset that had `historicalLV95` set (point cloud). Extended so the field is conceptually a *building* property:

- `propagateHistoricalLV95()` runs after `allDatasets` is loaded. For every building, finds any dataset that has `historicalLV95`, and shares that object **by reference** with every sibling of the same building. A mutation on one updates all in memory; on disk each entry still stores its own copy.
- `toggleHistoricalPosition()` now toggles every member of the building (`historicalGroupFor(layer)`). One click of ⌂ on the point cloud moves the cloud + all model phases together to the historical site.
- `histApplyFromInputs()` rebuilds matrices for every group member at every nudge.
- `histSaveEditor()` PATCHes every dataset that shares the building, fires concurrent requests via `Promise.all`, reports the count in the button feedback.

### Bug fix — Cloud↔model alignment at the historical position

Buildings + cloud aligned perfectly at Ballenberg but drifted apart by several metres at the historical site. Root cause: `buildHistoricalModelMatrix` was pinning each layer's *own* center to `P_hist`:

- Case A (point cloud): pinned the vertex centroid (`_lv95Center`) to `P_hist`.
- Case B (model with embedded root.transform): pinned the bounding-sphere center (`boundingSphere.center`) to `P_hist`.

Those two "centers" are at slightly different physical positions inside the same building (the cloud centroid skews toward scan-dense areas; the model's bbox center is the geometric middle). At Ballenberg the misalignment was invisible because each representation was at its own correct LV95 position. Moving both centers to the same `P_hist` left the geometry around them offset by (model_center − cloud_center).

**Fix**: added `getHistoricalAnchorEcef(ds)` which returns the ECEF position derived from the point cloud's `_lv95Center` for the building. Every Case B layer now translates by `P_hist − ECEF(anchor)` — the same delta. The relative offset between cloud and models at FLM is preserved exactly at the historical site. Case A is unchanged (it IS the anchor).

Also rebuilds matrices for the whole group at `toggleHistoricalPosition` so layers that loaded before the point cloud's `_lv95Center` was available get their matrix recomputed with the correct anchor.

### Lessons

- The Cesium quantized-mesh spec says heights should be ellipsoidal; in practice, national terrain providers often use the local vertical datum (LN02 here). Always verify the height datum of any terrain source against your geometry before trusting alignment.
- A "raised ellipsoid" hack to drape flat imagery on tile-content geometry was a clever workaround when no terrain provider was wired up. As soon as a real provider was added, the hack stopped having any purpose and became actively misleading. Lesson: workarounds that depend on an absent feature should be ripped out as soon as the feature is added.
- When two representations of the same building have different "natural centers" (vertex centroid vs bounding-box center), the only way they stay aligned through any rigid transformation is to share a single anchor. Per-layer centers diverge whenever the transformation isn't the identity.
- For interactive editing of building-level metadata (`historicalLV95`), in-memory sharing by reference + per-entry persistence on disk is a clean compromise — every dataset is self-contained on disk but the runtime edit experience is "edit once, applies everywhere."

### Pending

- [ ] Migrate `historicalLV95` to a separate per-building registry (e.g. `data/buildings/<id>.json`) so the schema reflects the semantics. Today the field is duplicated across every dataset of the same building.
- [ ] Add a "Originalstandort initialisieren" affordance for buildings that don't yet have `historicalLV95` — currently you can only edit positions for buildings whose data was hand-authored with the field.
- [ ] Save-versioning: today PATCH overwrites. Optionally append every save to a `data/datasets.history.jsonl` for rollback.
- [ ] Capture a screenshot of the demo for the upcoming Wissam presentation (terrain + Originalstandort with PDF/video panel — strongest single visual).

---

## 2026-06-05 — Panorama view-direction persistence

### Completed

When opening a panorama from a scan marker, the panorama now initializes facing the same direction the user was looking in the 3D scene — no more disorienting "where am I pointing?" moment.

- `openPanoramaOverlay()` captures `viewer.camera.heading` and `viewer.camera.pitch` before invoking Pannellum.
- Conversion: `initYaw = toDegrees(camera.heading) − scan.northOffset`. Pitch maps 1:1 (both conventions are 0 = horizon, positive = up).
- `loadPanoScan()` gained an `initPitch` parameter, clamped to `[−85°, 85°]` to stay inside Pannellum's valid range (Cesium can report values outside that when the camera is near-vertical).
- Hotspot scan-navigation (clicking the "go to next scan" arrows in 3D space) propagates compass bearing **and** pitch so the user keeps facing the same direction across scan stations.
- Prev/Next buttons in the panorama bar now do the same — extracted into a small `nextPanoScan(delta)` helper.
- Toggling "Show scan positions" while a panorama is open also preserves pitch on re-render.

### Lessons

- Cesium `camera.heading` and Pannellum `yaw` share the same convention (0 = N, positive = E), and `camera.pitch` matches Pannellum `pitch` (0 = horizon, positive = up). The only adapter needed is the per-scan `northOffset` to translate between compass bearing and the panorama's local frame.
- Cesium occasionally reports `camera.pitch` slightly outside ±π/2 when the camera is tilted past vertical. Clamping the converted value to ±85° avoids edge-case Pannellum errors without visibly affecting the typical case.

---

## 2026-06-11 — Minimal mobile viewer (`public/viewers/mobile.html`)

### Completed

A stripped, touch-first Cesium viewer covering the three demo use cases on a
phone, with no measurement/clip/profile/Helmert tooling. Splash routes to
`?demo=eggiwil | phases | tragwerk`. Model-only and (for Eggiwil/phases)
GLB-only, so the heaviest asset is a 16 MB model tileset instead of the 72 MB
point cloud.

- **Eggiwil — Standort** (`?demo=eggiwil`): building 351 model toggled between
  Ballenberg and its Originalstandort (24.7 km, yaw 170°). The historical
  placement is anchored to the **point cloud's LV95 centroid** (2648855,
  1177528, 649), read from the cloud's `tileset.json` — *not* its 72 MB payload
  — so the position matches the desktop viewer exactly. Falling back to the
  model's own bbox centre (the first attempt) put the building in the wrong
  spot at the old site.
- **swisstopo Zeitreise on mobile**: a Karte/Luftbild switch + year slider
  (ports the WMTS endpoints and year tables from `cesium.html`), a green band
  under the slider marking the timeframe the building was/is at the shown
  location (original site → relocation 1988; Ballenberg 1988 → present), and
  position-aware defaults (old site → 1988, Ballenberg → most recent). Imagery
  crossfades (add-on-top, retire-old-late) so reloads never flash grey.
- **Phases** (`?demo=phases`): Stallscheune Meggen (752), switch
  1. ↔ 2. Bauphase via tileset `show`.
- **Tragwerk** (`?demo=tragwerk`): per-element load colours via the runtime
  `CustomShader` (ported from `cesium.html`).

### Lessons

- **The served LOD ladder is decorative.** Every building's `_lod0/1/2.glb` are
  byte-identical copies (`generate_3dtiles.py` fell back to `shutil.copy`
  because gltfpack's `-tc` path failed at export). So there is no cheap coarse
  level: the model is a hard 16 MB and Tragwerk is a hard ~175 MB (7×25 MB).
  This also contradicts the thesis's 100/30/5 % LOD claim — logged in
  `documentation/review_3.txt` / `MOBILE_VIEWER_PLAN.md`. gltfpack `-si 0.05`
  only gets Tragwerk 25→17 MB (textures dominate); a real mobile re-export
  needs working KTX2 (`-tc`) + quantization.
- **Draped imagery is only as sharp as the terrain tiles loaded so far.** A
  fly's `complete` callback is unreliable on mobile (a screen touch cancels the
  fly and suppresses it). The robust trigger is re-requesting imagery once the
  terrain **tile queue drains** (`globe.tilesLoaded` / `tileLoadProgressEvent`)
  after `camera.moveEnd` — the same settled state a manual slider touch hits.
- **Two representations of one building need a shared anchor.** Confirmed again:
  the historical coordinate was authored against the point-cloud centroid, so
  any model-only placement must reuse that centroid, not its own centre.
- Mobile cache must be tiny (256 MB / 64 MB; desktop's 4 GB / 2 GB OOMs mobile
  Safari). Coordinate/matrix helpers were copied verbatim from `cesium.html` —
  candidates for extraction into a shared `/js/lv95.js`.

### Pending

- [ ] Real-device pass (iOS + Android): touch nav, terrain, and especially the
  Tragwerk `CustomShader` path on mobile GPUs.
- [ ] Tragwerk mobile weight: re-export the 7 elements with working KTX2 + mesh
  quantization, confirm the size drop, re-test on cellular.
- [ ] Extract the shared LV95/matrix helpers into `/js/lv95.js`, import from
  both `cesium.html` and `mobile.html`.

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
