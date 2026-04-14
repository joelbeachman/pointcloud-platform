# Point Cloud Platform — Setup Guide

A multi-viewer platform for managing and exploring 3D spatial data:
LiDAR scans, photogrammetry meshes, Gaussian splats, and panoramic images.

## Quick Start

```bash
# 1. Install Node dependencies (first time only)
npm install

# 2. Install Python processing libraries (first time only)
pip3 install numpy "laspy[lazrs]" pye57 plyfile "trimesh[easy]"

# 3. Download sample datasets (first time only)
bash scripts/download_samples.sh

# 4. Start the server
node server.js

# 5. Open in browser
# http://localhost:3000
```

## Docker

```bash
# Build and start (Python processing libraries included in image)
docker compose up --build

# With a custom data directory on the host
DATA_DIR=/Volumes/MyDrive/pointcloud-data docker compose up
```

The container mounts your data directory at `/data` — datasets.json and all
asset subdirectories (pointclouds/, splats/, cesium/, panoramas/) live there.

---

## Processing Pipeline — `scripts/process.py`

The universal converter ingests any common spatial data format and produces
output registered in the platform automatically.

### Supported formats

| Input | Detection | Output | Viewer |
|---|---|---|---|
| `.las` `.laz` | extension | 3D Tiles pnts | Cesium |
| `.e57` | extension | 3D Tiles pnts | Cesium |
| `.xyz` `.txt` `.pts` | extension | 3D Tiles pnts | Cesium |
| `.ptx` (Leica) | extension | 3D Tiles pnts | Cesium |
| `.pcd` (ASCII) | extension | 3D Tiles pnts | Cesium |
| `.ply` (point cloud) | PLY header | 3D Tiles pnts | Cesium |
| `.obj` `.stl` `.glb` `.gltf` | extension | 3D Tiles GLB | Cesium |
| `.ply` (mesh — has faces) | PLY header | 3D Tiles GLB | Cesium |
| `.splat` | extension | copied to splats/ | Splat viewer |
| `.ply` (3DGS — has `f_dc_0`) | PLY header | converted to .splat | Splat viewer |

### Usage

```bash
# Basic — auto-detects format, converts, registers in datasets.json
python3 scripts/process.py /path/to/scan.laz

# With a custom name
python3 scripts/process.py /path/to/model.obj --name "Site Facade"

# Custom ID and data directory
python3 scripts/process.py input.e57 --name "Building Scan" --id "building-2026" \
  --data-dir /mnt/data

# Dry run — print curl command instead of registering
python3 scripts/process.py input.splat --no-register

# DATA_DIR env var (matches what the server uses inside Docker)
DATA_DIR=/data python3 scripts/process.py /data/uploads/scan.las --name "New Scan"
```

Output for point clouds goes to `<data-dir>/cesium/<id>/tileset.json`.
Output for meshes goes to `<data-dir>/cesium/<id>/mesh.glb` + `tileset.json`.
Output for splats goes to `<data-dir>/splats/<id>.splat`.

### Notes

- Point clouds are written as a single 3D Tiles 1.0 `.pnts` tile with `RTC_CENTER`
  (relative-to-center positions). Colour is preserved when present in the source.
- Meshes are loaded by trimesh and exported as GLB. Multi-mesh scenes are
  flattened into a single mesh before export.
- 3DGS PLY files are detected by the presence of `f_dc_0` in the PLY header.
  SH DC coefficients are converted to RGB; opacity is converted via sigmoid.
- For E57 files, all scans are concatenated into one tile. To also extract
  panoramic images from an E57, use `scripts/extract_e57.py` instead.

---

## Viewers

| Viewer | URL | Best for |
|--------|-----|----------|
| **Portal** | `http://localhost:3000` | Dataset management dashboard |
| **Potree** | `/viewers/potree.html` | Large LiDAR scans, octree streaming |
| **Cesium** | `/viewers/cesium.html` | Multi-layer 3D Tiles, globe, measurements |
| **Gaussian Splat** | `/viewers/splat.html` | Photo-realistic splat renders |
| **Panorama** | `/viewers/panorama.html` | 360° images linked to scan positions |
| **Compare** | `/viewers/compare.html` | Side-by-side viewer comparison |

### Cesium viewer features

The Cesium viewer is a joint multi-layer viewer:

- **Left sidebar — Layers**: add datasets as layers (one or more simultaneously),
  toggle visibility, fly to, remove. Supports `cesium` (3D Tiles) and `splat`
  (Gaussian splat overlay) dataset types.
- **Left sidebar — Measurements**: Distance, Horizontal distance, Vertical
  distance, Area tools. Click to place points, double-click to finish.
- **Right sidebar**: running list of completed measurements with labels,
  distances/areas, and delete buttons.
- **Gaussian splat layers**: rendered via a transparent Three.js canvas overlaid
  on the Cesium canvas. Camera is synced every frame via ECEF→ENU transform so
  the splat stays registered with the globe.

---

## Adding Data Manually

### Point cloud / mesh / splat — use the pipeline

```bash
python3 scripts/process.py input.laz --name "My LiDAR Scan"
python3 scripts/process.py model.obj  --name "Photogrammetry Mesh"
python3 scripts/process.py scene.splat --name "Gaussian Splat"
```

### E57 with panoramic images

```bash
# Extracts panoramas + writes metadata.json, prints curl command to register
python3 scripts/extract_e57.py my_scan.e57 data/panoramas/my-scan "My Site"
```

### Cesium 3D Tiles (pre-tiled)

```bash
curl -X POST http://localhost:3000/api/datasets \
  -H "Content-Type: application/json" \
  -d '{"name":"Aerial Survey","type":"cesium","source":"aerial","path":"/data/cesium/my-survey/tileset.json"}'
```

### Convert .splat to 3D Tiles GLB

If you need a `.splat` file in native CesiumJS 3D Tiles format
(for environments where the JS overlay approach is not suitable):

```bash
python3 scripts/convert_splat.py input.splat data/cesium/my-splat/
# Produces splat.glb + tileset.json
# Register as type "cesium-splat" (requires CesiumJS 1.130+ with KHR_gaussian_splatting)
```

---

## Running Tests

```bash
bash scripts/test.sh
```

---

## Project Structure

```
/workspace/
├── server.js                    # Express backend — REST API + static serving
├── package.json
├── Dockerfile                   # node:20-slim + Python processing libraries
├── docker-compose.yml           # mounts DATA_DIR volume, port 3000
├── public/
│   ├── index.html               # Portal dashboard
│   ├── css/portal.css
│   ├── js/portal.js
│   └── viewers/
│       ├── potree.html          # Potree point cloud viewer
│       ├── cesium.html          # Multi-layer Cesium viewer + measurements
│       ├── splat.html           # Gaussian splat viewer (trackball controls)
│       ├── panorama.html        # 360° panorama viewer
│       └── compare.html         # Side-by-side viewer comparison
├── data/
│   ├── datasets.json            # Dataset registry
│   ├── pointclouds/             # Potree-format or raw point cloud files
│   ├── splats/                  # .splat files
│   ├── panoramas/               # Equirectangular images + metadata.json
│   └── cesium/                  # 3D Tiles tilesets (tileset.json + tiles)
└── scripts/
    ├── process.py               # Universal converter — any format → 3D Tiles / splat
    ├── convert_splat.py         # .splat → 3D Tiles GLB (KHR_gaussian_splatting)
    ├── extract_e57.py           # E57 → panorama JPEGs + metadata.json
    ├── generate_demo_pointcloud.js
    ├── download_samples.sh      # Download all open sample datasets
    └── test.sh                  # E2E API + viewer tests
```

## Supported Dataset Types in datasets.json

| `type` field | Viewer | Description |
|---|---|---|
| `pointcloud` | Potree | Potree octree format (`metadata.json`) |
| `e57` | Potree / Panorama | Raw XYZ + linked panoramic images |
| `splat` | Splat / Cesium | `.splat` binary (32 bytes/Gaussian) |
| `cesium` | Cesium | 3D Tiles tileset (`tileset.json`) |
| `cesium-splat` | Cesium | 3D Tiles GLB with KHR_gaussian_splatting |
