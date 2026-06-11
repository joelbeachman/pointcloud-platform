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
        data/cesium/gesamtmodell/tileset_<group>[_<phase>].json (per group/phase)

The tilesets are registered in datasets.json automatically.

Pipeline position (run from the repo root — all paths are relative):
  export_blender_glb.py (in Blender)  →  this script  →  backfill_building_phase.py
The output tilesets are served by server.js and loaded in the Cesium viewer.
"""

import json
import math
import os
import subprocess
import sys
from collections import defaultdict

# ── config ────────────────────────────────────────────────────────────────────
MANIFEST_PATH = 'data/blender/export/manifest.json'
OUTPUT_DIR    = 'data/cesium/gesamtmodell'
DATASETS_JSON = 'data/datasets.json'

# LV95 (EPSG:2056) origin in Blender local space = [0, 0, 0]
LV95_ORIGIN = (2648466.518, 1177343.008, 570.290)  # (E, N, H_orthometric)

# Vertical datum: LN02 orthometric (the Swiss vertical datum), matching the
# swisstopo terrain provider's reference frame (https://3d.geo.admin.ch/
# ch.swisstopo.terrain.3d/v1/). Keeping GEOID_UNDULATION = 0 means our building
# tilesets use the same reference as the terrain, so they sit ON terrain instead
# of floating ~47.5 m above it.
#
# History: this used to be 47.5 m (orthometric → WGS84 ellipsoidal). That was
# correct for a Cesium-on-bare-ellipsoid setup but wrong once swisstopo terrain
# (also orthometric in practice) was introduced. See documentation/PIPELINE.md.
# If you wire a different terrain source that is genuinely in WGS84 ellipsoidal
# heights, set this back to ~47.5 m for Switzerland (varies 45–50 m by location).
GEOID_UNDULATION = 0.0
HEIGHT_OFFSET    = 0.0   # metres fine-tune vertical placement (zero with swisstopo terrain)

# Documented yaw of the Blender model relative to geographic North.
MODEL_YAW_DEG = 2.2   # empirically calibrated; positive = CCW from East when viewed from above

# gltfpack simplification ratios per LOD level
# LOD0 = full quality, LOD1 = 30%, LOD2 = 5%
LODS = [
    ('lod0', None),
    ('lod1', 0.30),
    ('lod2', 0.05),
]

# Absolute geometricError values (metres) per LOD level.
# CesiumJS shows a tile (instead of refining to children) when
#   geometricError * screenHeight / (2 * tan(halfFOV) * distance) <= maxSSE (default 16)
# → tile shown at distance >= geometricError * ~58 m  (1080p, 60°FOV)
# LOD0=0 → always shown when reached; LOD1=1 → shown ≥58 m; LOD2=5 → shown ≥290 m
LOD_GE_ABSOLUTE = [0.0, 1.0, 5.0]  # indexed same as LODS: lod0, lod1, lod2

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
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        print('  [gltfpack] not found — copying source GLB as-is (install gltfpack for LOD simplification)')
        return False
    if result.returncode != 0:
        print(f'  [gltfpack error] {result.stderr.strip()}')
        # Retry without -tc in case basisu encoding fails for this file
        cmd_notc = [x for x in cmd if x != '-tc']
        try:
            result = subprocess.run(cmd_notc, capture_output=True, text=True)
        except FileNotFoundError:
            return False
        if result.returncode != 0:
            print(f'  [gltfpack error no-tc] {result.stderr.strip()}')
            return False
    return True


def box_bounding_volume(bbox_min, bbox_max):
    """
    Build a 3D Tiles 'box' bounding volume from a local-space AABB.
    Format: [cx, cy, cz,  hx,0,0,  0,hy,0,  0,0,hz]

    Tile bounding volumes are in the TILE's local coordinate system — the same
    Z-up ENU space that the root transform maps FROM (Blender world space).
    CesiumJS applies its Y-up→Z-up glTF correction internally to the model
    geometry only; bounding volumes must NOT be converted to Y-up.
    Using Y-up here places bounding sphere centres hundreds of metres below
    the model (North ↔ Up axes swapped).
    """
    cx = (bbox_min[0] + bbox_max[0]) / 2
    cy = (bbox_min[1] + bbox_max[1]) / 2
    cz = (bbox_min[2] + bbox_max[2]) / 2
    hx = (bbox_max[0] - bbox_min[0]) / 2
    hy = (bbox_max[1] - bbox_min[1]) / 2
    hz = (bbox_max[2] - bbox_min[2]) / 2

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
    """Build all tileset.json files + LOD GLBs from the Blender export manifest.

    Returns (main_tileset_path, group_paths) where group_paths is a list of
    (parent_name, leaf_name_or_None, tileset_path) consumed by register_datasets.
    """
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
    # group_tiles: parent_name (None = standalone) → list of (tile, bldg)
    group_tiles  = defaultdict(list)
    import shutil

    for bldg in buildings:
        name     = bldg['name']
        src_glb  = os.path.join(export_base, bldg['file'])
        size     = bldg.get('size', 20.0)
        parent   = bldg.get('parent')  # None for standalone buildings

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
                shutil.copy(src_glb, dst_glb_abs)

            lod_idx = [l[0] for l in LODS].index(lod_suffix)
            ge      = LOD_GE_ABSOLUTE[lod_idx]
            lod_entries.append((dst_glb_name, ge))

        tile = make_building_tile(bldg, lod_entries)
        group_tiles[parent].append((tile, bldg))
        print(f'  ✓ {name}  (parent={parent!r}, {size:.0f}m, {bldg.get("vertex_count", 0):,} verts)')

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

    # ── helper: build a sub-tileset root node from a list of (tile, bldg) ────
    # Returns (node, (bbox_min, bbox_max), size) — caller uses bbox for root tile.
    def make_group_root(tile_bldg_list, fallback_bmin, fallback_bmax):
        if not tile_bldg_list:
            return None, None, 0
        gb_mins = [b['bbox_min'] for _, b in tile_bldg_list if b.get('bbox_min')]
        gb_maxs = [b['bbox_max'] for _, b in tile_bldg_list if b.get('bbox_max')]
        if gb_mins:
            gb_min = [min(x[i] for x in gb_mins) for i in range(3)]
            gb_max = [max(x[i] for x in gb_maxs) for i in range(3)]
        else:
            gb_min, gb_max = fallback_bmin, fallback_bmax
        gb_size = max(gb_max[i] - gb_min[i] for i in range(3))
        node = {
            'boundingVolume': {'box': box_bounding_volume(gb_min, gb_max)},
            'geometricError': gb_size * 10,
            'refine': 'ADD',
            'children': [t for t, _ in tile_bldg_list],
        }
        return node, (gb_min, gb_max), gb_size

    # ── compute global bbox (all buildings + terrain) ────────────────────────
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

    # ── helper: write one tileset.json ───────────────────────────────────────
    # tile_bbox: (bbox_min, bbox_max) for the root tile's bounding volume.
    # Use the group's own bbox (not the global one) so CesiumJS flies to the
    # correct location when this tileset is loaded as a standalone layer.
    def write_tileset(filename, buildings_node, terrain_node, label, tile_bbox=None):
        root_children = []
        if terrain_node:
            root_children.append(terrain_node)
        if buildings_node:
            root_children.append(buildings_node)

        bv_min = tile_bbox[0] if tile_bbox else root_bmin
        bv_max = tile_bbox[1] if tile_bbox else root_bmax
        bv_size = max(bv_max[i] - bv_min[i] for i in range(3))

        ts = {
            'asset': {
                'version': '1.0',
                'extras': {
                    'generatedBy': 'generate_3dtiles.py',
                    'lv95Origin': list(lv95_origin),
                    'crs': 'EPSG:2056',
                    'label': label,
                }
            },
            'geometricError': bv_size * 10,
            'root': {
                'transform': root_transform,
                'boundingVolume': {'box': box_bounding_volume(bv_min, bv_max)},
                'geometricError': bv_size * 5,
                'refine': 'ADD',
                'children': root_children,
            }
        }
        path = os.path.join(output_dir, filename)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(ts, f, indent=2)
        return path

    # ── main tileset: standalone buildings (parent=None) + terrain ───────────
    standalone = group_tiles.pop(None, [])
    main_path = os.path.join(output_dir, 'tileset.json')
    # A focused export (--building / --phase) only knows about a slice of the
    # model. Rewriting tileset.json from that slice would drop every other
    # building from the Gesamtmodell view. Preserve the existing main tileset
    # in that case.
    if manifest.get('focused') and os.path.exists(main_path):
        print(f'\n[main] skipping tileset.json rewrite — focused run '
              f'(building={manifest.get("building_filter")!r}, '
              f'phase={manifest.get("phase_filter")!r}). Existing main preserved.')
    else:
        standalone_root, standalone_bbox, _ = make_group_root(standalone, root_bmin, root_bmax)
        main_path = write_tileset('tileset.json', standalone_root, terrain_tile,
                                  'Gesamtmodell Eggiwil', tile_bbox=None)
        print(f'\nWrote {main_path}  ({len(standalone)} standalone buildings, '
              f'terrain={terrain_tile is not None})')

    # ── per-group tilesets: one file per parent collection ───────────────────
    group_paths = []  # [(parent_name, leaf_name_or_None, tileset_path), ...]
    for parent_name, tile_bldg_list in sorted(group_tiles.items()):
        safe_parent = parent_name.replace('/', '_').replace(' ', '_').replace('\\', '_')
        filename    = f'tileset_{safe_parent}.json'
        group_root, group_bbox, _ = make_group_root(tile_bldg_list, root_bmin, root_bmax)
        path = write_tileset(filename, group_root, None, parent_name, tile_bbox=group_bbox)
        group_paths.append((parent_name, None, path))
        print(f'Wrote {path}  ({len(tile_bldg_list)} buildings in "{parent_name}")')

        # ── per-leaf tilesets for multi-building groups ─────────────────────
        # Generates one tileset per individual building so phases can be
        # toggled independently in the viewer (e.g. Bauphase 1 vs 2 of 851).
        if len(tile_bldg_list) > 1:
            for tile, bldg in tile_bldg_list:
                leaf_name = bldg['name']
                safe_leaf = leaf_name.replace('/', '_').replace(' ', '_').replace('\\', '_')
                leaf_filename = f'tileset_{safe_parent}_{safe_leaf}.json'
                # Wrap the single REPLACE-chain tile in an ADD root
                bmin = bldg.get('bbox_min', root_bmin)
                bmax = bldg.get('bbox_max', root_bmax)
                leaf_size = max(bmax[i] - bmin[i] for i in range(3))
                leaf_root = {
                    'boundingVolume': {'box': box_bounding_volume(bmin, bmax)},
                    'geometricError': leaf_size * 10,
                    'refine': 'ADD',
                    'children': [tile],
                }
                path_leaf = write_tileset(
                    leaf_filename, leaf_root, None,
                    f'{parent_name} — {leaf_name}',
                    tile_bbox=(bmin, bmax),
                )
                group_paths.append((parent_name, leaf_name, path_leaf))
            print(f'  + {len(tile_bldg_list)} individual phase tilesets for "{parent_name}"')

    return main_path, group_paths


def _to_web_path(fs_path):
    """Convert a local filesystem path to a web-root-relative path."""
    p = fs_path.replace('\\', '/')
    idx = p.find('/data/cesium')
    if idx >= 0:
        return p[idx:]
    return '/' + p.lstrip('/')


def register_datasets(main_path, group_paths, datasets_path):
    """
    Merge gesamtmodell entries into datasets.json.

    Behavior:
    - Build the new entries from the current manifest (main + groups + leaves).
    - Replace any existing entry whose id matches a new id (upsert).
    - PRESERVE every other gesamtmodell_* entry (so a focused per-building
      re-export doesn't wipe entries for buildings that aren't in this manifest).
    - Warn about preserved entries whose tileset.json file no longer exists.

    group_paths entries: (parent_name, leaf_name_or_None, tileset_path)
      leaf_name=None → group tileset (all phases together)
      leaf_name=str  → individual phase tileset
    """
    import datetime
    with open(datasets_path, encoding='utf-8') as f:
        datasets = json.load(f)

    now = datetime.datetime.utcnow().isoformat() + 'Z'

    def safe(s):
        return s.replace('/', '_').replace(' ', '_').replace('\\', '_').replace('+', '_')

    # ── Build new entries ─────────────────────────────────────────────────────
    new_entries = []
    new_entries.append({
        'id':          DATASET_ID,
        'name':        DATASET_NAME,
        'type':        'cesium',
        'source':      'model',
        'path':        _to_web_path(main_path),
        'description': 'Gesamtmodell Eggiwil — all standalone buildings and terrain.',
        'crs':         'EPSG:2056',
        'group':       'Gesamtmodell',
        'createdAt':   now,
    })

    for parent_name, leaf_name, ts_path in group_paths:
        if leaf_name is None:
            ds_id   = f'{DATASET_ID}_{safe(parent_name)}'
            ds_name = f'{parent_name} (alle Phasen)'
            desc    = f'Alle Phasen von {parent_name}.'
        else:
            ds_id   = f'{DATASET_ID}_{safe(parent_name)}_{safe(leaf_name)}'
            ds_name = leaf_name
            desc    = f'{leaf_name} — Phase von {parent_name}.'

        new_entries.append({
            'id':          ds_id,
            'name':        ds_name,
            'type':        'cesium',
            'source':      'model',
            'path':        _to_web_path(ts_path),
            'description': desc,
            'crs':         'EPSG:2056',
            'group':       parent_name,
            'createdAt':   now,
        })

    # ── Merge: keep old entries except where a new id replaces them ───────────
    new_ids = {e['id'] for e in new_entries}

    preserved      = []   # old gesamtmodell entries kept (not in new manifest)
    overridden     = []   # old gesamtmodell entries replaced by a new one
    stale_warnings = []   # preserved entries whose tileset file is gone

    # Resolve the project root once so we can sanity-check paths on disk.
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(datasets_path)))

    final = []
    for d in datasets:
        did = d.get('id', '')
        if not did.startswith(DATASET_ID):
            # Non-gesamtmodell entry (PDFs, video, point clouds, samples) — keep as-is.
            final.append(d)
            continue
        if did in new_ids:
            # Replaced by a new entry below; drop the old.
            overridden.append(did)
            continue
        # Preserve this old gesamtmodell entry — but warn if the tileset is gone.
        ts_path = d.get('path', '')
        if ts_path.startswith('/'):
            fs_path = os.path.join(project_root, ts_path.lstrip('/'))
        else:
            fs_path = ts_path
        if not os.path.exists(fs_path):
            stale_warnings.append((did, ts_path))
        preserved.append(d)
        final.append(d)

    # Append new entries (those that override are dropped above; the new versions
    # take their place; brand-new ids land here too).
    final.extend(new_entries)

    # Dedupe by id (defensive — should already be unique).
    seen, deduped = set(), []
    for d in final:
        if d['id'] in seen:
            continue
        seen.add(d['id']); deduped.append(d)

    with open(datasets_path, 'w', encoding='utf-8') as f:
        json.dump(deduped, f, indent=2, ensure_ascii=False)

    n_groups = sum(1 for _, l, _ in group_paths if l is None)
    n_leaves = sum(1 for _, l, _ in group_paths if l is not None)
    print(f'Registered 1 main + {n_groups} group + {n_leaves} individual tilesets')
    print(f'  → {len(new_entries)} new/upserted entries')
    print(f'  → {len(overridden)} old entries replaced')
    print(f'  → {len(preserved)} preserved gesamtmodell entries (other buildings, not in this run)')
    if stale_warnings:
        print(f'  !! {len(stale_warnings)} preserved entries point at MISSING tileset files:')
        for did, p in stale_warnings[:8]:
            print(f'       {did}  →  {p}')
        if len(stale_warnings) > 8:
            print(f'       ... and {len(stale_warnings) - 8} more')
        print(f'     Run a full export (no --building filter) to rebuild these,')
        print(f'     or delete the orphaned entries manually.')
    print(f'  Total entries in {datasets_path}: {len(deduped)}')


# ── entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    if not os.path.exists(MANIFEST_PATH):
        print(f'ERROR: manifest not found at {MANIFEST_PATH}')
        print('Run export_blender_glb.py in Blender first to generate it.')
        sys.exit(1)

    main_path, group_paths = generate(MANIFEST_PATH, OUTPUT_DIR, LV95_ORIGIN)
    register_datasets(main_path, group_paths, DATASETS_JSON)
    print('\nDone. Load the datasets in cesium.html to verify placement.')
