#!/usr/bin/env python3
"""
extract_e57.py — Extract panoramic images and scan positions from E57 files.

Usage:
    python3 scripts/extract_e57.py <input.e57> <output_dir> [dataset_name]

Output:
    <output_dir>/panoramas/scan_<N>.jpg  — equirectangular panoramic images
    <output_dir>/metadata.json           — scan positions + panorama paths for platform

Example:
    python3 scripts/extract_e57.py my_scan.e57 data/panoramas/site1 "Site 1"
    # Then register in the platform:
    curl -X POST http://localhost:3000/api/datasets -H 'Content-Type: application/json' \
      -d '{"name":"Site 1","type":"e57","source":"lidar","path":"/data/panoramas/site1/metadata.json"}'
"""

import sys
import os
import json
import math

try:
    import pye57
except ImportError:
    print("ERROR: pye57 not installed. Run: pip3 install pye57 --break-system-packages")
    sys.exit(1)

try:
    from PIL import Image
    import numpy as np
except ImportError:
    print("ERROR: Pillow/numpy not installed. Run: pip3 install Pillow numpy --break-system-packages")
    sys.exit(1)


def spherical_to_equirectangular(points_xyz, width=4096, height=2048):
    """Convert a set of XYZ points (relative to scanner) into an equirectangular image."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    count = np.zeros((height, width), dtype=np.int32)

    x, y, z = points_xyz[:, 0], points_xyz[:, 1], points_xyz[:, 2]
    r = np.sqrt(x**2 + y**2 + z**2)
    r = np.where(r == 0, 1e-9, r)

    # Azimuth: -pi to pi -> pixel x
    azimuth = np.arctan2(y, x)
    # Elevation: -pi/2 to pi/2 -> pixel y
    elevation = np.arcsin(np.clip(z / r, -1, 1))

    px = ((azimuth + math.pi) / (2 * math.pi) * width).astype(int)
    py = ((math.pi/2 - elevation) / math.pi * height).astype(int)

    px = np.clip(px, 0, width - 1)
    py = np.clip(py, 0, height - 1)

    # Color by intensity or distance
    intensity = np.clip(r / r.max() * 255, 0, 255).astype(np.uint8)
    img[py, px, 0] = intensity  # R
    img[py, px, 1] = (intensity * 0.8).astype(np.uint8)  # G
    img[py, px, 2] = (intensity * 0.6).astype(np.uint8)  # B
    count[py, px] += 1

    return img


def extract_e57(input_path, output_dir, dataset_name=None):
    if not os.path.exists(input_path):
        print(f"ERROR: File not found: {input_path}")
        sys.exit(1)

    os.makedirs(output_dir + '/panoramas', exist_ok=True)
    dataset_name = dataset_name or os.path.splitext(os.path.basename(input_path))[0]

    print(f"Opening: {input_path}")
    e57 = pye57.E57(input_path)
    scan_count = e57.scan_count
    print(f"Scans found: {scan_count}")

    scan_positions = []

    for i in range(scan_count):
        print(f"  Processing scan {i+1}/{scan_count}...")
        try:
            # Read scan data
            data = e57.read_scan(i, intensity=True, colors=True, row_column=True, transform=False)

            # Get scanner position from header
            header = e57.get_header(i)
            pose = header.get('pose', {})
            translation = pose.get('translation', {})
            tx = translation.get('x', 0.0)
            ty = translation.get('y', 0.0)
            tz = translation.get('z', 0.0)

            # Get cartesian points
            if 'cartesianX' in data:
                x = data['cartesianX']
                y = data['cartesianY']
                z = data['cartesianZ']
            elif 'sphericalRange' in data:
                r = data['sphericalRange']
                az = data['sphericalAzimuth']
                el = data['sphericalElevation']
                x = r * np.cos(el) * np.cos(az)
                y = r * np.cos(el) * np.sin(az)
                z = r * np.sin(el)
            else:
                print(f"    No point data found in scan {i}, skipping")
                continue

            points = np.column_stack([x, y, z])

            # Generate equirectangular panorama
            out_img_path = f"{output_dir}/panoramas/scan_{i:03d}.jpg"
            img_array = spherical_to_equirectangular(points, width=2048, height=1024)
            img = Image.fromarray(img_array)
            img.save(out_img_path, 'JPEG', quality=85)
            print(f"    Saved panorama: {out_img_path} ({len(points)} points)")

            scan_positions.append({
                "id": f"scan_{i:03d}",
                "label": f"Scan {i+1}",
                "path": f"/data/{os.path.relpath(out_img_path, '/workspace/data')}",
                "x": float(tx),
                "y": float(ty),
                "z": float(tz),
                "northOffset": 0
            })

        except Exception as e:
            print(f"    Warning: scan {i} failed — {e}")
            continue

    # Write metadata
    metadata = {
        "name": dataset_name,
        "source": input_path,
        "scanCount": len(scan_positions),
        "panoramas": scan_positions
    }
    meta_path = output_dir + '/metadata.json'
    with open(meta_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"\nDone: {len(scan_positions)} scans extracted")
    print(f"Metadata: {meta_path}")
    print(f"\nRegister this dataset with:")
    print(f'  curl -X POST http://localhost:3000/api/datasets \\')
    print(f'    -H "Content-Type: application/json" \\')
    print(f'    -d \'{{"name":"{dataset_name}","type":"e57","source":"lidar","path":"/data/{os.path.relpath(meta_path, "/workspace/data")}","panoramas":{json.dumps(scan_positions)}}}\'')

    return scan_positions


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    input_path = sys.argv[1]
    output_dir = sys.argv[2]
    dataset_name = sys.argv[3] if len(sys.argv) > 3 else None

    extract_e57(input_path, output_dir, dataset_name)
