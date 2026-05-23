#!/usr/bin/env python3
"""
restore_eggiswil.py — Restore haus-eggiwil panoramas from backup source images.

Copies the 185 per-position JPEGs from data/eggiswil_backup/images/ into
data/panoramas/haus-eggiwil/ and generates metadata.json with LV95 coordinates
normalised to local (relative to the cesium tileset centre).

Usage:
    python3 scripts/restore_eggiswil.py
"""

import csv
import json
import shutil
import os

SRC_IMAGES  = 'data/eggiswil_backup/images'
DST_DIR     = 'data/panoramas/haus-eggiwil'
CSV_PATH    = 'data/eggiswil_backup/image_poses.csv'

os.makedirs(DST_DIR, exist_ok=True)

panoramas = []
missing = []

with open(CSV_PATH, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        fname = row['file']
        src   = os.path.join(SRC_IMAGES, fname)
        if not os.path.exists(src):
            missing.append(fname)
            continue
        dst = os.path.join(DST_DIR, fname)
        shutil.copy2(src, dst)
        # Positions in absolute LV95 (EPSG:2056) — Cesium's lv95ModelMatrix
        # applies the origin shift internally, so absolute coords are required.
        panoramas.append({
            "id":          row['name'].strip().replace(' ', '_'),
            "label":       row['name'].strip(),
            "path":        f"/data/panoramas/haus-eggiwil/{fname}",
            "x":           round(float(row['x']), 4),
            "y":           round(float(row['y']), 4),
            "z":           round(float(row['z']), 4),
            "northOffset": round(float(row['rotZ_deg']), 2)
        })

metadata = {
    "name":      "Haus Eggiwil",
    "source":    "lidar",
    "crs":       "EPSG:2056",
    "scanCount": len(panoramas),
    "panoramas": panoramas
}

meta_path = os.path.join(DST_DIR, 'metadata.json')
with open(meta_path, 'w') as f:
    json.dump(metadata, f, indent=2)

print(f"Copied  : {len(panoramas)} panoramas → {DST_DIR}/")
print(f"Metadata: {meta_path}")
if missing:
    print(f"Missing : {len(missing)} files not found in backup")
    for m in missing:
        print(f"  {m}")
