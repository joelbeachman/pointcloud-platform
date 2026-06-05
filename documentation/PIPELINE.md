# Pipeline & Architecture — Technical Overview

A walkthrough of the codebase, the data pipeline, the libraries involved, and a proposed long-term workflow that addresses the archival problem we have with the 4.9 GB Blender file.

---

## 1. Big picture

At its core, the platform is **one Express server + a dataset catalog + a set of browser viewers**. Everything else (Blender export, point-cloud conversion, splat conversion) is a one-shot preprocessing step that produces files in `data/` and registers them in `data/datasets.json`. The viewer chooses how to render based on the dataset `type`.

```
┌────────────────────────────────────────────────────────────────────┐
│                       Raw sources                                  │
│ Blender (.blend) · LiDAR (.e57/.las) · Photogrammetry (.ply/.glb)  │
│              · Drone video · PDFs · Panoramas                      │
└─────────────────────────┬──────────────────────────────────────────┘
                          │  (preprocessing — Python + Blender)
                          ▼
┌────────────────────────────────────────────────────────────────────┐
│                    data/  (served directory)                       │
│  cesium/  (3D Tiles, GLBs)  potree/ (octrees)  splats/             │
│  panoramas/ (JPEGs + metadata)  PDFs/  videos/                     │
│                                                                    │
│              datasets.json  ←  catalog of everything               │
└─────────────────────────┬──────────────────────────────────────────┘
                          │  (Express HTTP API + static file server)
                          ▼
┌────────────────────────────────────────────────────────────────────┐
│                    Browser viewers (per `type`)                    │
│  Cesium · Potree 1.8 · Potree-Next (WebGPU) · Gaussian Splat       │
│  Pannellum (panorama overlay) · PDF iframe · YouTube/<video>       │
└────────────────────────────────────────────────────────────────────┘
```

---

## 2. Codebase layout

```
your-project/
├─ server.js                  Express server (~590 LOC)
├─ package.json               Node dependencies
├─ data/                      Everything served and processed (NOT in git for binaries)
│  ├─ datasets.json           THE catalog (155 entries today)
│  ├─ blender/                Source .blend + exported GLBs (12 GB)
│  ├─ cesium/                 3D Tiles tilesets (17 GB)
│  ├─ potree/                 Potree octrees (257 MB)
│  ├─ splats/                 Gaussian splats (3 GB)
│  ├─ panoramas/              Equirectangular JPEGs + metadata (775 MB)
│  ├─ pointclouds/            Raw + sample point clouds (115 MB)
│  └─ PDFs/                   Document attachments (9 MB)
├─ public/                    Static frontend
│  ├─ index.html              Portal landing page
│  ├─ css/portal.css
│  ├─ js/portal.js            Portal logic (one card per house)
│  ├─ libs/                   Vendored JS libs (potree, three, splats)
│  └─ viewers/                One HTML page per viewer type
│     ├─ cesium.html          (4341 LOC) — the main viewer
│     ├─ potree18.html        Potree 1.8 (WebGL)
│     ├─ potreenext.html      Potree-Next (WebGPU, experimental)
│     ├─ splat.html           Gaussian splat viewer
│     ├─ panorama.html        Standalone panorama viewer
│     ├─ pdf.html             PDF iframe viewer
│     ├─ video.html           Video / YouTube viewer
│     └─ compare.html         Side-by-side compare
├─ scripts/                   Python + JS processing tools
└─ documentation/             This folder
```

### Backend — `server.js` (Node.js + Express)

| Concern | What it does |
|---|---|
| Static file serving | `/data/*` and `/*` (the `public/` tree) |
| REST API | `GET /api/datasets`, `GET /api/datasets/:id`, `POST /api/datasets`, `DELETE /api/datasets/:id`, `GET /api/health`, `GET /api/metadata/schema` |
| Metadata validation | Validates incoming dataset entries against a schema (required fields, enum types, date formats) |
| Cesium proxy | `/cesium-proxy/Cesium.js` — downloads Cesium from CDN, patches a few `slice()` calls, caches in memory. Lets us avoid bundling Cesium ourselves. |
| Panorama resolution | If a dataset has `panoramasPath`, it inlines the contents into the API response so viewers don't need a second fetch |

**Dependencies**: `express`, `cors`, `multer` (uploads), `serve-static`. Zero JS framework — vanilla HTML/JS on the front end.

### Frontend — viewers

Each viewer is a standalone HTML page that reads `?id=<dataset-id>` (or `?building=NNN`) from the URL, fetches `/api/datasets/:id`, and decides how to render. They share nothing beyond `portal.css` — by design, so each can be vendored independently.

| Viewer | Renderer | Libraries |
|---|---|---|
| `cesium.html` | Cesium 1.140 | Cesium (from CDN via proxy), Pannellum 2.5.6 (panorama overlay), swisstopo WMTS tiles for Zeitreise |
| `potree18.html` | Potree 1.8 | Vendored in `public/libs/potree18/` (Potree + Three.js) |
| `potreenext.html` | Potree-Next (TU Wien) | Vendored: WebGPU radix-sort, BinaryHeap, laz-perf, proj4js, tween, json5 |
| `splat.html` | Mark Kellogg's `gaussian-splats-3d` | Three.js + UMD splat lib |
| `panorama.html` | Pannellum | Loaded from jsdelivr CDN |
| `pdf.html` | Browser-native PDF (iframe) | Just an `<iframe>` |
| `video.html` | HTML5 `<video>` or YouTube `<iframe>` | None |

### `data/datasets.json` — the catalog

A single JSON array, ~155 entries today. Each entry has:

```json
{
  "id":            "doc-351-bauernhaus-eggiwil",
  "name":          "Bauernhaus Eggiwil BE — Dokumentation",
  "type":          "document",            // cesium · potree · splat · e57 · panorama · document · video
  "source":        "report",              // lidar · photogrammetry · model · report · youtube · ...
  "path":          "/data/PDFs/351_Bauernhaus Eggiwil BE-low.pdf",
  "building":      "351",                 // links datasets to a house
  "buildingName":  "Bauernhaus Eggiwil",  // displayed name
  "phase":         1,                     // for Bauphasen
  "isGroupMaster": true,                  // for "alle Phasen" entries
  "createdAt":     "2026-05-31T16:17:00.000Z"
}
```

**This is the glue.** The portal groups by `building`, the Cesium viewer's layer panel groups phases by `building`, the docs panel filters by `building`, the Add-Layer modal groups by `building` first. Every UI grouping reads from this catalog.

---

## 3. The pipeline — five tracks

Each source data type goes through a different pipeline before reaching the catalog. They all converge on `datasets.json`.

### Track A — Hand-modeled buildings (the Blender pipeline)

This is the heaviest pipeline and the one with the most pain points.

```
data/blender/Gesamtsmodell_V3.blend  (4.9 GB)
            │
            │  scripts/export_blender_glb.py   (run inside Blender headless)
            │  Libraries: bpy (Blender's Python API)
            │
            ▼
data/blender/export/
   ├─ manifest.json         (one entry per leaf collection)
   ├─ terrain.glb
   └─ buildings/
       ├─ 851.glb           (per leaf collection)
       ├─ 1._Bauphase_851.glb
       ├─ 2._Bauphase_851.glb
       └─ ...                (6.4 GB total)
            │
            │  scripts/generate_3dtiles.py
            │  Libraries: pyproj (LV95 ↔ ECEF), gltfpack (LOD simplification)
            │
            ▼
data/cesium/gesamtmodell/
   ├─ tileset.json          (main: standalone buildings + terrain)
   ├─ tileset_<group>.json  (one per parent collection — "alle Phasen")
   ├─ tileset_<group>_<leaf>.json   (one per leaf collection — individual Bauphase)
   ├─ buildings/*_lod0.glb  (full quality)
   ├─ buildings/*_lod1.glb  (30 % simplified)
   └─ buildings/*_lod2.glb  (5 % simplified)
                            (17 GB total)
            │
            │  scripts/backfill_building_phase.py
            │  Re-derives building/phase/isGroupMaster/buildingName
            │  from group names + a hand-curated dict
            │
            ▼
data/datasets.json  ←  ~120 gesamtmodell_* entries registered
```

**Key facts about this track:**

- Blender export runs headless (`blender --background ... --python ...`) so it can be scripted.
- `LOW_MEMORY_MODE` purges packed images before export — without it, the 4.9 GB Blender file OOMs on a normal machine.
- `export_apply=False` skips modifier evaluation (avoids OOM from Boolean modifiers).
- LV95→ECEF transform: Blender models are authored in Swiss LV95 grid coordinates centered at `(2648466.518, 1177343.008, 570.29)`. The 3D Tiles transform converts this to ECEF (Earth-Centered, Earth-Fixed) so Cesium can place them on the globe. Includes a 47.5 m geoid undulation correction (LHN95 → WGS84 ellipsoid) and a 2.2° model yaw.
- LOD: each building is rendered at three levels of detail. `gltfpack` (from meshoptimizer) does the mesh simplification.

### Track B — LiDAR point clouds (E57 / LAS / LAZ)

```
data/laserscans/<scan>.e57   (raw TLS output, gigabytes)
            │
            │  scripts/process.py
            │  Libraries: laspy (LAS/LAZ), pye57 (E57), plyfile (PLY),
            │             numpy, PIL (panorama extraction)
            │
            ▼
data/cesium/<id>/tileset.json      (3D Tiles, point cloud variant)
data/panoramas/<id>/                (per-scan-position equirectangular JPEGs)
   ├─ metadata.json                  (scan positions in LV95 + yaw)
   └─ scan_001.jpg, scan_002.jpg, ...
            │
            │  process.py auto-registers in datasets.json
            ▼
data/datasets.json  ←  type="cesium" + panoramasPath set
```

**Example**: the Eggiwil scan (`haus-eggiwil`) is 5,023,669 points in LV95 with 185 linked panorama positions. The Cesium viewer drops a marker at each panorama position; clicking opens Pannellum as a full-screen overlay.

### Track C — Gaussian splats

```
.splat file  (or 3D Gaussian Splat .ply with f_dc_0 / scale_0 / rot_0 props)
            │
            │  scripts/convert_splat.py
            │  Libraries: numpy
            │  Output: glTF with KHR_gaussian_splatting + SPZ compression
            │
            ▼
data/cesium/<id>/tileset.json   (loadable by Cesium 1.135+)
data/splats/<id>.splat          (also kept raw for the standalone splat viewer)
            │
            ▼
data/datasets.json  ←  type="cesium-splat" OR type="splat"
```

### Track D — Documents, videos, panoramas (lightweight)

- **PDFs**: drop in `data/PDFs/`, add an entry with `type: "document"` to `datasets.json`. The viewer is a plain `<iframe>`.
- **Videos**: either drop an `.mp4` in `data/videos/` (use HTML5 `<video>`) or set `youtubeId` + `start` + `end` to embed a YouTube clip. The drone footage for building 351 uses the YouTube path.
- **Standalone panoramas** (e.g. `demo-panoramas`): JPEGs + `metadata.json` directly under `data/panoramas/<id>/`. No conversion needed.

These are the cheapest to add — no processing, just a `datasets.json` entry.

### Track E — Photogrammetry / Gaussian splat capture

```
Photos / drone video
            │
            │  COLMAP (Structure-from-Motion — outside this repo)
            │  → sparse + dense reconstruction
            │
            │  Gaussian Splatting training (3DGS / Postshot / etc.)
            │
            ▼
.splat / .ply  →  back into Track C
```

This track happens entirely outside the platform. The platform just consumes the trained splat.

---

## 4. The Blender file problem

The single biggest fragility in the pipeline today is `Gesamtsmodell_V3.blend`:

- **4.9 GB**, a single binary file
- Cannot be meaningfully diffed or merged — only the latest version matters
- Causes OOM on most laptops during export → `LOW_MEMORY_MODE` strips textures
- All ~70 buildings + terrain + Tragwerk live in one file → bus factor of 1
- Naming conventions inside Blender directly determine output file names → "1. Bauphase" (generic name) collides with other buildings' "1. Bauphase" because the export script uses only the collection name. Building 851 works because its collections are named "1. Bauphase 851"; building 752 broke because its collection is named just "1. Bauphase" under parent "2025_752"
- The current export silently drops a leaf collection if all its objects are eye-icon-hidden in the outliner (fixed in tonight's edit; warnings now bubble up into `manifest.json["errors"]`)
- Re-running the export takes 20+ minutes on a workstation

**Today's mitigations** (already in the repo):

- The Blender file lives in `data/blender/` and is gitignored. External storage / Git-LFS expected.
- `backfill_building_phase.py` reapplies all derived dataset fields, so wiping `gesamtmodell_*` entries and re-running is safe.
- `MANUAL_RELABELS` in `backfill_building_phase.py` covers the broken 752 export — delete entries from that dict once the underlying export is fixed.
- `scripts/export_blender_glb.py` now warns instead of silently skipping empty leaf collections.

---

## 5. Proposed workflow — sustainable + archivable

The current "everything in one giant .blend" model doesn't scale and isn't archivable. Here's a workflow that addresses both.

### 5.1 Source of truth: separate raw / processed / served

```
archive/                        ← long-term storage (NAS / cold object storage)
├─ raw/
│  ├─ laserscans/               .e57 / .las raw scans (immutable, per-campaign folders)
│  ├─ photogrammetry/           image sets per flight
│  ├─ documents/                PDF originals
│  └─ video/                    drone footage masters
├─ source-models/
│  ├─ buildings/                ONE .blend file per building (not one mega-file!)
│  │  ├─ 351_Bauernhaus_Eggiwil/
│  │  │  ├─ source.blend        (~200 MB, per building)
│  │  │  ├─ phases/             Pre-baked GLBs per Bauphase
│  │  │  └─ README.md           Provenance + author + dates
│  │  └─ ...
│  └─ terrain/
│     └─ Gesamtmodell.blend     Only the layout + LOD-low buildings + terrain
└─ processed/                   reproducible, can always be regenerated
   ├─ tilesets/                 3D Tiles output (per dataset)
   ├─ octrees/                  Potree output (per scan)
   └─ derived-manifests/        manifests, audits, indexes
```

**Why split the .blend file?** Three reasons:
1. Bus factor and memory both go from "all-or-nothing" to "per building"
2. Per-building .blend files are 50–200 MB each — small enough to commit to Git LFS without pain
3. Changes to one building don't lock or risk the others

If splitting is too disruptive mid-project, an interim measure: keep the mega-.blend, but use Blender's "library overrides" to author per-building .blend files that link into the master. The exports come from the per-building files, not the master.

### 5.2 Naming convention (enforced by export script)

Per-collection GLB names should always carry the building number:

```
data/blender/export/buildings/
   <building>_<phase>.glb        e.g. 351_alle_Phasen.glb
   <building>_<phase>_<part>.glb  e.g. 351_2._Bauphase.glb
```

The `export_blender_glb.py` script should auto-prefix the building number when the collection name doesn't already contain it (preventing the 752 collision). Suggested rule: if `parent_name` matches `(?:^|_)(\d{3,4})$`, append `_<building>` to the GLB name when the collection name doesn't already include that number.

### 5.3 Dataset registry: file-based, not one giant JSON

`datasets.json` works for 155 entries; at 500+ it becomes a merge-conflict magnet. Migration path:

```
data/datasets/
   <id>.json                    one file per dataset
   _index.json                  generated by a script — what's currently in datasets.json
```

The server reads everything in `data/datasets/*.json` at startup. Editing one dataset doesn't touch any other. Per-building diffs in PRs become trivial to review.

### 5.4 Provenance per dataset

Every dataset should have:
- `source` (lidar / photogrammetry / model / document / video)
- `captureDate` (ISO 8601)
- `captureMethod` (TLS / UAV / CloseRange / Photogrammetry / StructureFromMotion / handBuiltModel)
- `operator` (who captured/created it)
- `sourceArchive` (pointer back into `archive/raw/`)
- `processingSteps` (which scripts were run — for reproducibility)

These fields are already half-defined in `server.js`'s metadata schema. Enforce them at write time.

### 5.5 Archival contract

Archive a snapshot of the platform as **three artifacts**:
1. The `archive/raw/` and `archive/source-models/` trees (immutable inputs)
2. A pinned commit of the repo (scripts + viewers + server)
3. The generated `datasets.json` (or `_index.json`)

If you also need a "ready-to-browse" snapshot for non-technical viewers, additionally archive `archive/processed/` — but it should always be reproducible from #1 + #2.

For long-term storage:
- **Hot tier** (active development): local SSD or NAS, full `data/` tree
- **Warm tier** (last presentation snapshot): object storage with metadata
- **Cold tier** (research archive): tar+bzip2, checksummed, with a `MANIFEST.txt` listing every file's sha256 + provenance line

### 5.6 The CI / "build the demo" pipeline

A single command should rebuild everything from raw:

```
make demo                     # (or scripts/build_all.sh)
  ↓
  for each per-building .blend → export GLBs
  python scripts/generate_3dtiles.py
  python scripts/backfill_building_phase.py
  python scripts/process.py --batch data/laserscans/
  npm install && node server.js
```

Today this would take hours; that's fine, it runs offline. The key is reproducibility — anyone with the archive can rebuild the demo from scratch.

---

## 6. Quick-reference: where every library is used

| Library | Where | Why |
|---|---|---|
| **bpy** (Blender Python) | `export_blender_glb.py` | Drives Blender headless to export per-collection GLBs |
| **pyproj** | `generate_3dtiles.py` | LV95 (EPSG:2056) ↔ WGS84 ↔ ECEF coordinate conversion |
| **gltfpack** (meshoptimizer) | `generate_3dtiles.py` | LOD simplification of building GLBs |
| **laspy** | `process.py` | Read LAS / LAZ point clouds |
| **pye57** | `process.py`, `extract_e57.py` | Read E57 scans + embedded panoramas |
| **plyfile** | `process.py` | Read PLY (both point cloud and mesh variants) |
| **trimesh** | `process.py` | Read OBJ / STL / GLB meshes |
| **PIL (Pillow)** | `process.py`, `extract_e57.py` | Convert E57 panorama strips → equirectangular JPEGs |
| **numpy** | almost every Python script | Array math, point sampling, SVD (Helmert) |
| **Cesium 1.140** | `cesium.html` | 3D globe, 3D Tiles, Gaussian splat extension, terrain |
| **Pannellum 2.5.6** | `cesium.html`, `panorama.html` | Equirectangular panorama overlay |
| **Potree 1.8** | `potree18.html` | Octree-streamed point clouds (WebGL) |
| **Potree-Next** | `potreenext.html` | WebGPU point cloud renderer (TU Wien) |
| **Three.js** | `splat.html`, `potree18.html` | Scene graph + camera for splats and Potree |
| **gaussian-splats-3d** | `splat.html` | Mark Kellogg's splat renderer |
| **Express 4** | `server.js` | HTTP server + REST API |
| **swisstopo WMTS** | `cesium.html` Zeitreise | Historical aerial imagery + maps overlay |

External binaries / tools (not Python or JS libraries):
- **Blender 5.x** (headless mode) — runs `export_blender_glb.py`
- **gltfpack** — must be on `PATH` for LOD simplification
- **PotreeConverter** (for converting raw LiDAR to Potree octrees, run manually)
- **COLMAP** (for photogrammetry — outside the repo)
- **Gaussian Splatting trainer** (Postshot or similar — outside the repo)

---

## 7. End-of-doc: the smallest possible "I want to add a new building" runbook

1. Drop the LiDAR scan in `data/laserscans/<building>/scan.e57`.
2. `python3 scripts/process.py data/laserscans/<building>/scan.e57 --building-id NNN --capture-method TLS --has-color` → tileset + panoramas + dataset entry.
3. Open Blender, model the building (or open the per-building .blend), name collections `1._Bauphase_NNN`, `2._Bauphase_NNN`, ….
4. Run `blender --background <building>.blend --python scripts/export_blender_glb.py`.
5. `python3 scripts/generate_3dtiles.py && python3 scripts/backfill_building_phase.py`.
6. Drop the PDF in `data/PDFs/NNN_<name>.pdf` and add a `type: "document"` entry to `datasets.json` (or a per-building file once 5.3 lands).
7. Add the building number → name mapping in `BUILDING_NAMES` in `backfill_building_phase.py`, re-run backfill.
8. Reload the portal — the new house card appears with all its data linked.

That's the contract. If any step requires more than what's here, it's a bug or a missing convention.
