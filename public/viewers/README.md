# Viewer Catalogue

Each file in this directory is a standalone HTML viewer (inline JS, no build
step) for one data type. They share the dataset registry served by the backend
(`GET /api/datasets`, `GET /api/datasets/:id`) and most are reachable from the
portal landing page (`/public/index.html` + `/public/js/portal.js`, which maps
each `dataset.type` to a viewer URL). All 3D viewers work in LV95 (EPSG:2056)
world coordinates unless noted otherwise.

## cesium.html

The platform's primary viewer (documented separately). A full CesiumJS globe
with swisstopo terrain and Zeitreise historical imagery, multi-layer 3D-Tiles
loading (point clouds, GLB building models, Gaussian splats), building-centric
navigation, construction-phase (Bauphasen) switching, the historical-position
editor and an embedded panorama overlay. Accepts `?id=<datasetId>` to open one
dataset or `?building=<houseId>` to bulk-load every cesium-compatible dataset
of a building. portal.js routes dataset types `cesium`, `cesium-splat` and
`panorama` here, and every house card's main "open" action targets it.

## potree18.html

Potree 1.8 (WebGL) point-cloud viewer with the stock Potree sidebar (EDL,
measurement, clipping). Platform extensions: a datasets panel for loading
additional `potree` clouds or draping `cesium` GLB tilesets into the scene via
Three.js/GLTFLoader, scan-position markers that open a Pannellum panorama
overlay, and panorama measurement tools (point/distance/horizontal/area) that
raycast the point cloud and bridge results into native `Potree.Measure`
objects. Accepts `?id=<datasetId>` (defaults to the Haus Eggiwil cloud); the
dataset's `panoramasPath` supplies scan positions. portal.js offers it for
type `potree` datasets; also linked in every viewer's header nav.

## potreenext.html

Experimental Potree "next" (WebGPU) viewer by TU Wien — requires Chrome 113+
or another WebGPU browser, otherwise it shows an error with a fallback link to
potree18.html. Loads `potree` clouds via `PotreeLoader` and `cesium` 3D-Tiles
via `TDTilesLoader` (re-projected ECEF → LV95 with proj4). Includes the same
datasets panel, panorama overlay, and pano measurement tools as potree18.html,
bridged into the viewer's native measure objects. Accepts `?id=<datasetId>`
(type decides the loader) and `?splat=<url>` to additionally load a 3DGS PLY.
portal.js offers it for types `potree` and `cesium` (building "Potree" links
point here).

## panorama.html

Standalone equirectangular panorama viewer built on Pannellum 2.5.6. Shows a
dataset's 360° scan images with spatial navigation hotspots to neighbouring
scans (computed from LV95 scan positions + `northOffset`), prev/next
navigation, and floor-plane measurement tools (horizontal distance, angle,
polygon area) drawn on a canvas overlay. Accepts `?id=<datasetId>` and
`?pos=<panoramaId>` for the starting scan; the dropdown lists datasets of type
`panorama`/`e57` or with a `panoramas` array. Not linked from portal.js
(panorama datasets route to cesium.html's embedded overlay) — kept as the
direct/standalone way to inspect panoramas.

## mobile.html

Minimal mobile/kiosk Cesium viewer — model-only (GLB 3D Tiles), no point
clouds or tools, big touch controls, mobile-sized tile cache. A splash menu
(no query param) offers three demos selected with `?demo=`: `eggiwil` (Haus
Eggiwil at Ballenberg vs. its 1684 original site, with a swisstopo Zeitreise
map/orthophoto year slider), `phases` (Stallscheune Meggen's two construction
phases), and `tragwerk` (timber structure coloured by load zone). Dataset ids
are hardcoded against the registry. Intended to be opened directly on a
phone/tablet (e.g. via QR code); not linked from the portal.

## splat.html

Gaussian-splat viewer using the GaussianSplats3D UMD build with Three.js r149
and custom quaternion trackball controls (free rotation, no gimbal lock).
The dropdown lists datasets of type `splat`; the selected dataset's `path`
(.splat / .ksplat / 3DGS .ply) is streamed into the scene. Accepts
`?id=<datasetId>` to auto-load. portal.js routes type `splat` here; also in
the header nav.

## compare.html

Side-by-side comparison shell: two iframes hosting any of Cesium, Splat,
Potree 1.8 or Potree-Next, with a draggable divider, horizontal/vertical split
and single-pane fullscreen modes. Takes no query params — each embedded viewer
handles its own dataset selection. Linked from the portal header nav.

## pdf.html

PDF document viewer: a toolbar (dataset name, building, source, description)
above an iframe that uses the browser's native PDF rendering, plus an
"open in new tab" link. Requires `?id=<datasetId>`; the dataset's `path` must
be a PDF. portal.js routes type `document` here.

## video.html

Video viewer: plays a dataset either as a YouTube embed (when the dataset has
a `youtubeId`, honouring optional `start`/`end` clip seconds) or as a plain
HTML5 `<video>` from the dataset's `path`. Requires `?id=<datasetId>`.
portal.js routes type `video` here.
