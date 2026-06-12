# Processing pipeline

Python scripts that turn raw capture data (point clouds, E57 scans, Blender
models, Gaussian splats) into web-ready datasets under `data/`, registered in
`data/datasets.json` and served by `server.js` to the Cesium / Potree /
panorama viewers. Run everything from the repo root — several scripts use
relative paths.

## Input data types

| Input                                            | Handled by              |
|--------------------------------------------------|-------------------------|
| Point clouds: `.las .laz .e57 .xyz .txt .pts .ptx .pcd .ply` | `process.py` (single tile) · `generate_pointcloud_tiles.py` (LOD, large clouds) |
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
- `--max-points N` randomly downsamples a point cloud to at most N points before
  writing (deterministic via `--seed`; default: keep every point). NOTE:
  `process.py` writes a **single `.pnts` tile with no level-of-detail**, so the
  result must still fit in a browser — for very large clouds use Pipeline 3.

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

## Pipeline 3 — massive point clouds → LOD 3D Tiles (`generate_pointcloud_tiles.py`)

`process.py` writes a point cloud as a **single `.pnts` tile** containing every
point, with no level-of-detail — fine up to ~10–20M points, but the browser
loads the whole thing at once. For larger clouds, `generate_pointcloud_tiles.py`
wraps **py3dtiles** to build a streaming **3D Tiles octree**: each zoom level
loads only the tiles it needs, so tens-to-hundreds of millions of points render
progressively in the same Cesium viewer.

```
big.las ──▶ generate_pointcloud_tiles.py ──▶ data/cesium/<id>/tileset.json  (+ N .pnts LOD tiles)
                                          └──▶ upserts entry in data/datasets.json
```

```
python3 scripts/generate_pointcloud_tiles.py INPUT.las --id ID --name "NAME" \
        [--jobs N] [--cache-size MB] [--srs-in 2056] [--no-rgb] [--overwrite]
```

- Keeps input coordinates (no reprojection), like `process.py`, and registers a
  `type: cesium` dataset — the portal and `cesium.html` pick it up unchanged.
- Requires `py3dtiles` (`pip install py3dtiles`); `.laz` inputs also need
  `laspy[lazrs]`.
- **Memory**: py3dtiles peak RAM scales with `--jobs` and `--cache-size`. On
  small hosts lower both (e.g. `--jobs 4 --cache-size 256`). Full-res conversion
  of very large clouds (100M+) can exceed a small machine's RAM — if so,
  decimate first and tile the reduced cloud.

Example — the "massive" Eggiwil set on a 7.7 GB host: the 251M-point source LAS
OOMs at full resolution, so it was streamed-decimated to ~31M points (every 8th)
and tiled with `--jobs 4 --cache-size 256`, yielding a 4,588-tile LOD octree
(~460 MB, registered as `haus-eggiwil-massive`) that streams smoothly. The
Cesium viewer's **Punktgröße** slider (below Zeitreise) adjusts the rendered
point size.

## Utilities

- **`restore_eggiswil.py`** — one-off recovery: copies the backed-up
  haus-eggiwil panorama JPEGs from `data/eggiswil_backup/` and regenerates
  `data/panoramas/haus-eggiwil/metadata.json` (absolute LV95 positions).

Other files in this directory (`export_cidoc_crm.py`, `download_samples.sh`,
`generate_demo_pointcloud.js`, `regen_northoffset.pl`, `test.sh`) are not part
of the core conversion pipeline above.
