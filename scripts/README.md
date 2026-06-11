# Processing pipeline

Python scripts that turn raw capture data (point clouds, E57 scans, Blender
models, Gaussian splats) into web-ready datasets under `data/`, registered in
`data/datasets.json` and served by `server.js` to the Cesium / Potree /
panorama viewers. Run everything from the repo root — several scripts use
relative paths.

## Input data types

| Input                                            | Handled by              |
|--------------------------------------------------|-------------------------|
| Point clouds: `.las .laz .e57 .xyz .txt .pts .ptx .pcd .ply` | `process.py` |
| Meshes: `.obj .glb .gltf .stl` and mesh `.ply`   | `process.py`            |
| Gaussian splats: `.splat`, 3DGS `.ply`           | `process.py` (+ `convert_splat.py`) |
| Blender Gesamtmodell (`Gesamtsmodell_V3.blend`)  | `export_blender_glb.py` chain |
| E57 panorama scans                               | `extract_e57.py` or `process.py --extract-panoramas` |

## Pipeline 1 — capture data → viewer (`process.py`)

```
raw file ──▶ process.py ──▶ data/cesium/<id>/tileset.json   (point clouds & meshes, .pnts/GLB)
                       ├──▶ data/splats/<id>.splat          (3DGS PLY / .splat)
                       ├──▶ data/panoramas/<id>/...         (E57 with --extract-panoramas)
                       └──▶ upserts entry in data/datasets.json
```

- Auto-detects the input format (PLY headers are sniffed to tell 3DGS splats,
  meshes, and plain clouds apart) and LV95 (EPSG:2056) coordinates.
- `--helmert params.json` applies a local→LV95 similarity transform before
  writing output. The params come from **`helmert.py`**, which `server.js`
  invokes via `POST /api/helmert` (Horn/Kabsch SVD fit on user-picked point
  pairs; returns `{R, s, t, residuals, rms}` on stdout).
- `--batch` processes a whole directory, optionally with a per-file JSON config.

**`convert_splat.py`** (optional post-step): converts a `.splat` file into a
3D Tiles directory (`splat.glb` + `tileset.json`) using the
`KHR_gaussian_splatting` + SPZ-compression glTF extensions, so splats can be
loaded as a tileset in CesiumJS 1.135+.

**`extract_e57.py`** (standalone): extracts equirectangular preview panoramas
and scan positions from an E57 file into `<output_dir>/` without doing any
3D Tiles conversion; the resulting dataset is registered manually via curl.

## Pipeline 2 — Blender Gesamtmodell → 3D Tiles

Run in order:

1. **`export_blender_glb.py`** — runs *inside* Blender
   (`blender --background model.blend --python scripts/export_blender_glb.py [-- --building NNN --phase N --skip-terrain]`).
   Exports one GLB per leaf/Bauphase collection under `Häuser` plus
   `terrain.glb`, and writes `data/blender/export/manifest.json` (file list,
   world-space bounding boxes, parent grouping, focused-run flags).
2. **`generate_3dtiles.py`** — reads the manifest, builds gltfpack LOD chains
   (LOD0/1/2, REPLACE refinement), computes the LV95→ECEF root transform
   (LN02 orthometric heights, calibrated 2.2° yaw), and writes
   `data/cesium/gesamtmodell/tileset.json` plus per-group and per-phase
   tilesets. Upserts all of them into `data/datasets.json`; focused
   (`--building`/`--phase`) exports preserve entries not in the manifest.
3. **`backfill_building_phase.py`** — idempotent post-pass over
   `data/datasets.json` that derives `building`, `buildingName`, `phase`,
   `phaseLabel`, and `isGroupMaster` from group/name conventions, plus a few
   hand-maintained mappings.

## Utilities

- **`restore_eggiswil.py`** — one-off recovery: copies the backed-up
  haus-eggiwil panorama JPEGs from `data/eggiswil_backup/` and regenerates
  `data/panoramas/haus-eggiwil/metadata.json` (absolute LV95 positions).

Other files in this directory (`export_cidoc_crm.py`, `download_samples.sh`,
`generate_demo_pointcloud.js`, `regen_northoffset.pl`, `test.sh`) are not part
of the core conversion pipeline above.
