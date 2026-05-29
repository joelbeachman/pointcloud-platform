#!/usr/bin/env python3
"""
Generate a 3D Tiles tileset from exported Blender GLBs.

Prerequisites:
  pip install pyproj  (or: pip install pyproj --break-system-packages)
  apt install gltfpack  (or download from meshoptimizer releases)

Usage:
  python3 scripts/generate_3dtiles.py

Reads:  data/blender/export/manifest.json
Writes: data/cesium/gesamtmodell/tileset.json  (+ LOD GLBs next to it)

The tileset is registered in datasets.json automatically.
"""

import json
import math
import os
import subprocess
import sys

# ── config ────────────────────────────────────────────────────────────────────
MANIFEST_PATH = 'data/blender/export/manifest.json'
OUTPUT_DIR    = 'data/cesium/gesamtmodell'
DATASETS_JSON = 'data/datasets.json'

# LV95 (EPSG:2056) origin in Blender local space = [0, 0, 0]
LV95_ORIGIN = (2648466.518, 1177343.008, 570.290)  # (E, N, H_orthometric)

# Geoid undulation at this location (EGM2008 / Swiss LHN95→ellipsoidal correction).
# Switzerland: N ≈ 47–48 m.  Ellipsoidal H = orthometric H + N.
# pyproj only has the Swiss geoid grid if proj-data-ch is installed, so we apply
# the correction manually here.  Tune if the model still appears too high/low.
GEOID_UNDULATION = 47.5  # metres (LHN95 → WGS84 ellipsoid)
HEIGHT_OFFSET    = 1.5   # metres fine-tune vertical placement (empirically calibrated)

# Documented yaw of the Blender model relative to geographic North.
MODEL_YAW_DEG = 2.2   # empirically calibrated; positive = CCW from East when viewed from above

# gltfpack simplification ratios per LOD level
# LOD0 = full quality, LOD1 = 30%, LOD2 = 5%
LODS = [
    ('lod0', None),
    ('lod1', 0.30),
    ('lod2', 0.05),
]

# geometricError multipliers (bbox_size * factor)
LOD_GE_FACTORS = [0, 1.0, 5.0]  # LOD0 never coarser than LOD1, LOD2 shown far away

DATASET_ID   = 'gesamtmodell'
DATASET_NAME = 'Gesamtmodell Eggiwil (3D Tiles)'
# ──────────────────────────────────────────────────────────────────────────────


def compute_transform(lv95_E, lv95_N, lv95_H,
                      geoid_undulation=0.0, yaw_deg=0.0):
    """
    Compute the 4×4 column-major transform matrix (local → ECEF).

    CesiumJS internally applies a Y-up→Z-up correction (+90° around X) to all
    glTF content before applying the tile transform.  After that correction the
    tile's local frame is simply East-North-Up (Z-up), so this matrix is the
    standard eastNorthUpToFixedFrame, optionally pre-multiplied by a yaw
    rotation around the Up axis.

    geoid_undulation: metres to add to lv95_H to convert LHN95 orthometric
                      height to WGS84 ellipsoidal height (≈ 47.5 m for CH).
    yaw_deg:          clockwise rotation of the model around Up, in degrees.
                      Positive = model's +X has rotated clockwise from East.
    """
    from pyproj import Transformer

    ellipsoidal_H = lv95_H + geoid_undulation

    # LV95 → WGS84 geographic (for ENU frame unit vectors)
    t_geo = Transformer.from_crs("EPSG:2056", "EPSG:4326", always_xy=True)
    lon_deg, lat_deg, _ = t_geo.transform(lv95_E, lv95_N, ellipsoidal_H)

    # LV95 → ECEF (translation) using corrected ellipsoidal height
    t_ecef = Transformer.from_crs("EPSG:2056", "EPSG:4978", always_xy=True)
    ox, oy, oz = t_ecef.transform(lv95_E, lv95_N, ellipsoidal_H)

    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)

    # ENU unit vectors in ECEF
    east  = (-math.sin(lon),
              math.cos(lon),
              0.0)
    north = (-math.sin(lat) * math.cos(lon),
             -math.sin(lat) * math.sin(lon),
              math.cos(lat))
    up    = ( math.cos(lat) * math.cos(lon),
              math.cos(lat) * math.sin(lon),
              math.sin(lat))

    # eastNorthUpToFixedFrame base matrix
    # col 0 → East, col 1 → North, col 2 → Up, col 3 → translation
    m = [
        east[0],  east[1],  east[2],  0.0,
        north[0], north[1], north[2], 0.0,
        up[0],    up[1],    up[2],    0.0,
        ox,       oy,       oz,       1.0,
    ]

    if yaw_deg == 0.0:
        return m

    # Pre-multiply by Rz(yaw) in local ENU space:
    #   new_col0 = cos(yaw)*m_col0 + sin(yaw)*m_col1
    #   new_col1 = -sin(yaw)*m_col0 + cos(yaw)*m_col1
    #   new_col2, new_col3 unchanged
    # Column-major: col i occupies indices [i*4 .. i*4+3].
    θ  = math.radians(yaw_deg)
    c, s = math.cos(θ), math.sin(θ)

    def col(i):
        b = i * 4
        return [m[b], m[b+1], m[b+2], m[b+3]]

    c0, c1 = col(0), col(1)
    new_c0 = [ c*c0[r] + s*c1[r] for r in range(4)]
    new_c1 = [-s*c0[r] + c*c1[r] for r in range(4)]

    return [
        new_c0[0], new_c0[1], new_c0[2], new_c0[3],
        new_c1[0], new_c1[1], new_c1[2], new_c1[3],
        m[8],  m[9],  m[10], m[11],
        m[12], m[13], m[14], m[15],
    ]


def run_gltfpack(src_glb, dst_glb, simplify_ratio=None):
    """Run gltfpack to optimize/simplify a GLB. Returns True on success."""
    cmd = ['gltfpack', '-i', src_glb, '-o', dst_glb, '-kn', '-tc']  # -kn keeps names, -tc = KTX2
    if simplify_ratio is not None:
        cmd += ['-si', str(simplify_ratio)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f'  [gltfpack error] {result.stderr.strip()}')
        # Retry without -tc in case basisu encoding fails for this file
        cmd_notc = [x for x in cmd if x != '-tc']
        result = subprocess.run(cmd_notc, capture_output=True, text=True)
        if result.returncode != 0:
            print(f'  [gltfpack error no-tc] {result.stderr.strip()}')
            return False
    return True


def box_bounding_volume(bbox_min, bbox_max):
    """
    Build a 3D Tiles 'box' bounding volume from a local-space AABB.
    Format: [cx, cy, cz,  hx,0,0,  0,hy,0,  0,0,hz]
    Note: Blender Z-up is exported as glTF Y-up, so swap Y↔Z for glTF frame.
      Blender: (x, y, z) → glTF: (x, z, -y)
    """
    # Blender bbox → glTF Y-up bbox
    bx_min, by_min, bz_min = bbox_min
    bx_max, by_max, bz_max = bbox_max

    # glTF X = Blender X (East)
    # glTF Y = Blender Z (Up)
    # glTF Z = -Blender Y (-North)
    gtlf_x_min, gtlf_x_max = bx_min, bx_max
    gtlf_y_min, gtlf_y_max = bz_min, bz_max
    gtlf_z_min, gtlf_z_max = -by_max, -by_min  # negate + swap

    cx = (gtlf_x_min + gtlf_x_max) / 2
    cy = (gtlf_y_min + gtlf_y_max) / 2
    cz = (gtlf_z_min + gtlf_z_max) / 2
    hx = (gtlf_x_max - gtlf_x_min) / 2
    hy = (gtlf_y_max - gtlf_y_min) / 2
    hz = (gtlf_z_max - gtlf_z_min) / 2

    return [cx, cy, cz,  hx, 0, 0,  0, hy, 0,  0, 0, hz]


def make_building_tile(building, lod_files):
    """
    Build a 3D Tiles tile node for one building with LOD levels (REPLACE refinement).
    lod_files: [(uri, geometricError), ...] ordered fine→coarse (LOD0 first, LOD2 last).

    Correct 3D Tiles REPLACE hierarchy:
      outermost tile  → LOD2 (coarse, high GE, shown when far)
        child tile    → LOD1 (medium, medium GE)
          leaf tile   → LOD0 (full quality, GE=0, shown when close)

    We build inside-out: start from LOD0 (leaf), wrap with LOD1, then LOD2 (root).
    """
    bmin = building['bbox_min']
    bmax = building['bbox_max']
    bv   = {'box': box_bounding_volume(bmin, bmax)}

    current = None
    for glb_rel, ge in lod_files:          # fine → coarse: LOD0, LOD1, LOD2
        tile = {
            'boundingVolume': bv,
            'geometricError': round(ge, 2),
            'refine': 'REPLACE',
            'content': {'uri': glb_rel},
        }
        if current is not None:
            tile['children'] = [current]   # finer level becomes child of coarser
        current = tile
    return current


def generate(manifest_path, output_dir, lv95_origin):
    with open(manifest_path, encoding='utf-8') as f:
        manifest = json.load(f)

    buildings = manifest.get('buildings', [])
    terrain   = manifest.get('terrain')

    if not buildings and not terrain:
        print('ERROR: manifest has no buildings and no terrain — nothing to do.')
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)
    export_base = os.path.dirname(manifest_path)  # data/blender/export

    # ── compute root transform ──────────────────────────────────────────────
    print('Computing LV95 → ECEF transform...')
    root_transform = compute_transform(*lv95_origin,
                                       geoid_undulation=GEOID_UNDULATION + HEIGHT_OFFSET,
                                       yaw_deg=MODEL_YAW_DEG)
    print(f'  ECEF origin: ({root_transform[12]:.0f}, {root_transform[13]:.0f}, {root_transform[14]:.0f})')
    print(f'  geoid correction: +{GEOID_UNDULATION} m  height offset: +{HEIGHT_OFFSET} m  yaw: {MODEL_YAW_DEG}°')

    # ── process buildings ───────────────────────────────────────────────────
    building_tiles = []

    for bldg in buildings:
        name     = bldg['name']
        src_glb  = os.path.join(export_base, bldg['file'])
        size     = bldg.get('size', 20.0)

        if not os.path.exists(src_glb):
            print(f'  [skip] GLB not found: {src_glb}')
            continue

        safe = name.replace('/', '_').replace(' ', '_').replace('\\', '_')
        lod_entries = []

        for lod_suffix, ratio in LODS:
            dst_glb_name = f'buildings/{safe}_{lod_suffix}.glb'
            dst_glb_abs  = os.path.join(output_dir, dst_glb_name)
            os.makedirs(os.path.dirname(dst_glb_abs), exist_ok=True)

            ok = run_gltfpack(src_glb, dst_glb_abs, simplify_ratio=ratio)
            if not ok:
                # Fallback: copy the source file
                import shutil
                shutil.copy(src_glb, dst_glb_abs)

            lod_idx = [l[0] for l in LODS].index(lod_suffix)
            ge      = size * LOD_GE_FACTORS[lod_idx]
            lod_entries.append((dst_glb_name, ge))

        tile = make_building_tile(bldg, lod_entries)
        building_tiles.append(tile)
        print(f'  ✓ {name} ({size:.0f}m, {bldg.get("vertex_count", 0):,} verts)')

    # ── process terrain ─────────────────────────────────────────────────────
    terrain_tile = None
    if terrain:
        src_terrain = os.path.join(export_base, terrain['file'])
        if os.path.exists(src_terrain):
            dst_terrain_name = 'terrain_lod1.glb'
            dst_terrain_abs  = os.path.join(output_dir, dst_terrain_name)
            print(f'\nProcessing terrain...')
            ok = run_gltfpack(src_terrain, dst_terrain_abs, simplify_ratio=0.05)
            if not ok:
                import shutil
                shutil.copy(src_terrain, dst_terrain_abs)

            bmin = terrain['bbox_min']
            bmax = terrain['bbox_max']
            terrain_tile = {
                'boundingVolume': {'box': box_bounding_volume(bmin, bmax)},
                'geometricError': 0,
                'refine': 'REPLACE',
                'content': {'uri': dst_terrain_name},
            }
            print(f'  ✓ terrain ({dst_terrain_name})')

    # ── assemble root boundingVolume ─────────────────────────────────────────
    # Union of all buildings + terrain bboxes
    all_bmin = [b['bbox_min'] for b in buildings if b.get('bbox_min')]
    all_bmax = [b['bbox_max'] for b in buildings if b.get('bbox_max')]
    if terrain and terrain.get('bbox_min'):
        all_bmin.append(terrain['bbox_min'])
        all_bmax.append(terrain['bbox_max'])

    if all_bmin:
        root_bmin = [min(b[i] for b in all_bmin) for i in range(3)]
        root_bmax = [max(b[i] for b in all_bmax) for i in range(3)]
    else:
        root_bmin = [0, 0, 0]
        root_bmax = [1600, 700, 150]

    root_size = max(root_bmax[i] - root_bmin[i] for i in range(3))

    # ── assemble buildings sub-tileset ───────────────────────────────────────
    buildings_root = None
    if building_tiles:
        # Compute union bbox for buildings
        b_bmin = [b['bbox_min'] for b in buildings if b.get('bbox_min')]
        b_bmax = [b['bbox_max'] for b in buildings if b.get('bbox_max')]
        if b_bmin:
            bb_min = [min(b[i] for b in b_bmin) for i in range(3)]
            bb_max = [max(b[i] for b in b_bmax) for i in range(3)]
        else:
            bb_min, bb_max = root_bmin, root_bmax

        buildings_root = {
            'boundingVolume': {'box': box_bounding_volume(bb_min, bb_max)},
            'geometricError': root_size * 10,
            'refine': 'ADD',
            'children': building_tiles,
        }

    # ── root tile ────────────────────────────────────────────────────────────
    root_children = []
    if terrain_tile:
        root_children.append(terrain_tile)
    if buildings_root:
        root_children.append(buildings_root)

    tileset = {
        'asset': {
            'version': '1.0',
            'extras': {
                'generatedBy': 'generate_3dtiles.py',
                'lv95Origin': list(lv95_origin),
                'crs': 'EPSG:2056',
            }
        },
        'geometricError': root_size * 10,
        'root': {
            'transform': root_transform,
            'boundingVolume': {'box': box_bounding_volume(root_bmin, root_bmax)},
            'geometricError': root_size * 5,
            'refine': 'ADD',
            'children': root_children,
        }
    }

    # ── write tileset.json ────────────────────────────────────────────────────
    tileset_path = os.path.join(output_dir, 'tileset.json')
    with open(tileset_path, 'w', encoding='utf-8') as f:
        json.dump(tileset, f, indent=2)

    print(f'\nWrote {tileset_path}')
    print(f'  {len(building_tiles)} building tiles')
    print(f'  terrain: {"yes" if terrain_tile else "no"}')

    return tileset_path


def register_dataset(tileset_path, datasets_path):
    """Add or update the gesamtmodell entry in datasets.json."""
    with open(datasets_path, encoding='utf-8') as f:
        datasets = json.load(f)

    # Remove existing entry if present
    datasets = [d for d in datasets if d.get('id') != DATASET_ID]

    # Normalize path for the datasets.json (relative to public root)
    web_path = '/' + tileset_path.replace('\\', '/').lstrip('/')
    if 'data/cesium' in web_path:
        web_path = web_path[web_path.index('/data/cesium'):]

    datasets.append({
        'id':          DATASET_ID,
        'name':        DATASET_NAME,
        'type':        'cesium',
        'source':      'model',
        'path':        web_path,
        'description': 'Gesamtmodell Eggiwil — BIM/CAD model with per-building structure in LV95 (EPSG:2056).',
        'crs':         'EPSG:2056',
        'createdAt':   __import__('datetime').datetime.utcnow().isoformat() + 'Z',
    })

    with open(datasets_path, 'w', encoding='utf-8') as f:
        json.dump(datasets, f, indent=2)

    print(f'Registered dataset "{DATASET_ID}" in {datasets_path}')


# ── entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    if not os.path.exists(MANIFEST_PATH):
        print(f'ERROR: manifest not found at {MANIFEST_PATH}')
        print('Run export_blender_glb.py in Blender first to generate it.')
        sys.exit(1)

    tileset_path = generate(MANIFEST_PATH, OUTPUT_DIR, LV95_ORIGIN)
    register_dataset(tileset_path, DATASETS_JSON)
    print('\nDone. Load the dataset in cesium.html to verify placement.')
