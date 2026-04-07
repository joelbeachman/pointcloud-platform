# Point Cloud Platform — Setup Guide

A multi-viewer platform for managing and exploring point clouds from multiple sources:
LiDAR scans, photogrammetry, aerial surveys, Gaussian splats, and panoramic images from E57 files.

## Quick Start

```bash
# 1. Load Node.js
export NVM_DIR="$HOME/.nvm" && source "$NVM_DIR/nvm.sh"

# 2. Install dependencies (first time only)
npm install

# 3. Download sample datasets (first time only)
bash scripts/download_samples.sh

# 4. Start the server
node server.js

# 5. Open in browser
# http://localhost:3000
```

## Viewers

| Viewer | URL | Best for |
|--------|-----|----------|
| **Portal** | `http://localhost:3000` | Dataset management dashboard |
| **Potree** | `/viewers/potree.html` | Large LiDAR scans, octree streaming |
| **Cesium** | `/viewers/cesium.html` | Georeferenced data, globe context, aerial |
| **Gaussian Splat** | `/viewers/splat.html` | Photo-realistic splat renders |
| **Panorama** | `/viewers/panorama.html` | 360° images linked to scan positions |
| **Compare** | `/viewers/compare.html` | Side-by-side viewer comparison |

## Adding Your Own Data

### Point Cloud (LAS/LAZ → Potree format)

1. Convert your LAS/LAZ file to Potree format using [PotreeConverter](https://github.com/potree/PotreeConverter):
   ```bash
   PotreeConverter input.las -o data/pointclouds/my-scan/
   ```
2. Register it in the platform:
   ```bash
   curl -X POST http://localhost:3000/api/datasets \
     -H "Content-Type: application/json" \
     -d '{"name":"My Scan","type":"pointcloud","source":"lidar","path":"/data/pointclouds/my-scan/metadata.json"}'
   ```

### E57 File with Panoramic Images

```bash
# Extract panoramas from E57
python3 scripts/extract_e57.py my_scan.e57 data/panoramas/my-scan "My Site"

# The script prints a curl command to register the dataset automatically
```

### Gaussian Splat (.splat / .ply)

Place your `.splat` file in `data/splats/`, then register:
```bash
curl -X POST http://localhost:3000/api/datasets \
  -H "Content-Type: application/json" \
  -d '{"name":"My Scene","type":"splat","source":"photogrammetry","path":"/data/splats/my-scene.splat"}'
```

### Cesium 3D Tiles

Point the path to a `tileset.json` (local or hosted):
```bash
curl -X POST http://localhost:3000/api/datasets \
  -H "Content-Type: application/json" \
  -d '{"name":"Aerial Survey","type":"cesium","source":"aerial","path":"/data/cesium/my-survey/tileset.json"}'
```

## Supported Data Types

| Format | Type | Notes |
|--------|------|-------|
| LAS / LAZ | Point cloud | Must be converted to Potree octree format first |
| Potree octree | Point cloud | `metadata.json` in output dir |
| E57 | Point cloud + panoramas | Use `scripts/extract_e57.py` |
| .splat | Gaussian splat | Direct file loading |
| 3D Tiles | Cesium | `tileset.json` |
| Equirectangular JPEG/PNG | Panorama | 360° images |

## Running Tests

```bash
bash scripts/test.sh
```

## Project Structure

```
/workspace/
├── server.js              # Express backend — REST API + static serving
├── package.json
├── public/
│   ├── index.html         # Portal dashboard
│   ├── css/portal.css
│   ├── js/portal.js
│   └── viewers/
│       ├── potree.html    # Potree point cloud viewer
│       ├── cesium.html    # Cesium globe viewer
│       ├── splat.html     # Gaussian splat viewer
│       ├── panorama.html  # 360° panorama viewer
│       └── compare.html   # Side-by-side viewer comparison
├── data/
│   ├── datasets.json      # Dataset registry
│   ├── pointclouds/       # Potree-format or LAS/LAZ files
│   ├── splats/            # .splat files
│   ├── panoramas/         # Equirectangular images + metadata
│   └── cesium/            # 3D Tiles tilesets
└── scripts/
    ├── extract_e57.py         # E57 → panoramas + metadata
    ├── generate_demo_pointcloud.js  # Generate synthetic demo data
    ├── download_samples.sh    # Download all open sample datasets
    └── test.sh                # E2E tests
```
