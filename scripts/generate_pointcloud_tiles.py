#!/usr/bin/env python3
"""
generate_pointcloud_tiles.py — Out-of-core LOD 3D Tiles pipeline (massive clouds).

Unlike process.py — which writes a single .pnts tile containing *every* input
point and has no level-of-detail — this script wraps py3dtiles to build a
streaming 3D Tiles octree. Each zoom level loads only the tiles it needs, so
very large point clouds (tens to hundreds of millions of points) can be served
and rendered progressively in the existing Cesium viewer.

Pipeline position
  Alternative to process.py for point-cloud inputs too large for a single tile.
  Output lands in <data-dir>/cesium/<id>/tileset.json and is registered in
  datasets.json as type "cesium" — identical wiring to process.py's output, so
  the portal and cesium.html pick it up with no viewer changes.

Coordinates
  No reprojection is performed: the tileset keeps the input coordinates (e.g.
  Swiss LV95 / EPSG:2056), matching how the current cesium point-cloud datasets
  are stored. The viewer's LV95-anchor logic positions it.

Requires
  py3dtiles            (pip install py3dtiles)
  laspy[lazrs]         (only for .laz inputs; plain .las needs nothing extra)

Usage
  python3 scripts/generate_pointcloud_tiles.py INPUT.las --id ID --name "NAME" [opts]

Options
  --id ID            Dataset id/slug (default: slugified input filename stem)
  --name NAME        Human-readable dataset name (default: the id)
  --data-dir DIR     Data root (default: $DATA_DIR or /workspace/data)
  --jobs N           Parallel py3dtiles workers (default: all CPUs)
  --srs-in EPSG      Numeric EPSG of the input, recorded as the dataset CRS
                     (default: 2056 / Swiss LV95). No reprojection is done.
  --no-rgb           Drop colour (smaller, faster).
  --no-register      Skip writing the entry into datasets.json.
  --overwrite        Delete and recreate the output dir if it exists.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys

DATA_DIR = os.environ.get('DATA_DIR', '/workspace/data')


def slugify(text):
    """Lowercase, hyphenated slug (mirrors process.py's slugify)."""
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[\s_]+', '-', text)


def las_point_count(path):
    """Return the point count from a LAS/LAZ header without reading the body."""
    try:
        import laspy
        with laspy.open(path) as f:
            return int(f.header.point_count)
    except Exception:
        return None


def register_dataset(data_dir, entry):
    """Insert/replace ``entry`` in <data-dir>/datasets.json (a flat JSON list)."""
    reg_path = os.path.join(data_dir, 'datasets.json')
    try:
        with open(reg_path) as f:
            datasets = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        datasets = []
    datasets = [d for d in datasets if d.get('id') != entry['id']]
    datasets.append(entry)
    with open(reg_path, 'w') as f:
        json.dump(datasets, f, indent=2)
    print(f"  registered '{entry['id']}' in {reg_path} ({len(datasets)} datasets)")


def main():
    p = argparse.ArgumentParser(description='Build LOD 3D Tiles from a large point cloud.')
    p.add_argument('input', help='Input point cloud (.las/.laz/.xyz/.ply)')
    p.add_argument('--id', help='Dataset id/slug (default: input filename stem)')
    p.add_argument('--name', help='Human-readable name (default: the id)')
    p.add_argument('--data-dir', default=DATA_DIR, help=f'Data root (default: {DATA_DIR})')
    p.add_argument('--jobs', type=int, default=None, help='Parallel workers (default: all CPUs)')
    p.add_argument('--cache-size', type=int, default=None,
                   help='py3dtiles in-RAM cache in MB (lower = less memory, more '
                        'disk I/O; default: available memory / 10)')
    p.add_argument('--srs-in', type=int, default=2056,
                   help='Numeric EPSG of input, stored as CRS (default: 2056)')
    p.add_argument('--no-rgb', action='store_true', help='Drop colour attributes')
    p.add_argument('--no-register', action='store_true', help='Skip datasets.json registration')
    p.add_argument('--overwrite', action='store_true', help='Overwrite existing output dir')
    args = p.parse_args()

    input_path = os.path.abspath(args.input)
    if not os.path.exists(input_path):
        sys.exit(f"ERROR: input not found: {input_path}")

    name = args.name or os.path.splitext(os.path.basename(input_path))[0]
    ds_id = args.id or slugify(os.path.splitext(os.path.basename(input_path))[0])
    data_dir = os.path.abspath(args.data_dir)
    out_dir = os.path.join(data_dir, 'cesium', ds_id)

    if os.path.exists(out_dir):
        if not args.overwrite:
            sys.exit(f"ERROR: {out_dir} exists (use --overwrite)")
        shutil.rmtree(out_dir)
    os.makedirs(os.path.dirname(out_dir), exist_ok=True)

    n_points = las_point_count(input_path)
    print(f"[tiles] {os.path.basename(input_path)} → {out_dir}")
    if n_points:
        print(f"  input points: {n_points:,}")

    # ── Build the LOD octree with py3dtiles ──────────────────────────────────
    cmd = ['py3dtiles', 'convert', input_path, '--out', out_dir, '--overwrite']
    if args.jobs:
        cmd += ['--jobs', str(args.jobs)]
    if args.cache_size:
        cmd += ['--cache_size', str(args.cache_size)]
    if args.no_rgb:
        cmd += ['--no-rgb']
    print('  $ ' + ' '.join(cmd))
    start = datetime.datetime.now()
    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit(f"ERROR: py3dtiles convert failed (exit {result.returncode})")
    elapsed = (datetime.datetime.now() - start).total_seconds()

    ts_path = os.path.join(out_dir, 'tileset.json')
    if not os.path.exists(ts_path):
        sys.exit(f"ERROR: no tileset.json produced at {ts_path}")

    n_tiles = sum(1 for _, _, files in os.walk(out_dir)
                  for fn in files if fn.endswith('.pnts'))
    out_size = sum(os.path.getsize(os.path.join(dp, fn))
                   for dp, _, files in os.walk(out_dir) for fn in files)
    print(f"  done in {elapsed:.1f}s — {n_tiles} .pnts tiles, "
          f"{out_size / 1e6:.1f} MB output")

    # ── Register so the portal/viewer can see it ─────────────────────────────
    entry = {
        'id': ds_id,
        'name': name,
        'type': 'cesium',
        'source': 'lidar',
        'path': f'/data/cesium/{ds_id}/tileset.json',
        'description': f'LOD 3D Tiles from {os.path.basename(input_path)} (py3dtiles)',
        'createdAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'crs': f'EPSG:{args.srs_in}',
        'hasColor': not args.no_rgb,
        'pointCount': n_points,
        'processedBy': 'generate_pointcloud_tiles.py (py3dtiles)',
    }
    meta_path = os.path.join(out_dir, 'metadata.json')
    with open(meta_path, 'w') as f:
        json.dump(entry, f, indent=2)
    print(f"  wrote {meta_path}")

    if not args.no_register:
        register_dataset(data_dir, entry)

    print(f"\nDone. {ds_id} → {entry['path']}")


if __name__ == '__main__':
    main()
