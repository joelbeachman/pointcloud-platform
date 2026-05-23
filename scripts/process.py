#!/usr/bin/env python3
"""
process.py — Universal converter for point clouds, meshes, and Gaussian splats
into Cesium 3D Tiles or .splat format.

Supported inputs
  Point clouds:    .las .laz .e57 .xyz .txt .pts .ptx .pcd .ply (non-3DGS, non-mesh)
  Gaussian splats: .splat  .ply (3DGS — contains f_dc_0 / scale_0 / rot_0 properties)
  Meshes:          .obj .glb .gltf .stl .ply (mesh — contains face elements)

Output
  Point clouds / meshes  →  <data-dir>/cesium/<id>/tileset.json  (type: "cesium")
  Gaussian splats        →  <data-dir>/splats/<id>.splat          (type: "splat")
  E57 panoramas       →  <data-dir>/panoramas/<id>/metadata.json (type: "e57")

LOD Support:
  --lod-levels N      LOD levels to generate (default: 3: high, medium, low)
  --lod-ratios R      Comma-separated ratios (e.g., "1.0,0.2,0.05")
  --sample-method METHOD Sampling method: poisson|uniform|voxel (default: poisson)
  --max-points N      Maximum points after downsampling

Usage
  # Single file processing
  python3 scripts/process.py <input_file> [options]

  # Batch processing (all files in directory)
  python3 scripts/process.py <directory> --batch [options]
  python3 scripts/process.py <directory> --batch --config metadata.json

Options
  --name NAME          Human-readable dataset name (default: filename stem)
  --id   ID            Dataset ID slug (default: auto-derived from name)
  --data-dir DIR       Data directory root (default: DATA_DIR env or /workspace/data)
  --no-register         Skip auto-registration in datasets.json
  --batch              Batch mode: process all supported files in directory
  --config FILE         JSON config file for batch processing metadata
  --extract-panoramas   Extract E57 panoramas to output directory
  --helmert FILE        Apply Helmert transformation from JSON file

LOD Options:
  --lod-levels N      LOD levels to generate (default: 3)
  --lod-ratios R      Comma-separated LOD ratios (e.g., "1.0,0.2,0.05")
  --sample-method METHOD Sampling method: poisson|uniform|voxel (default: poisson)
  --max-points N      Maximum points after downsampling

Metadata options (all optional):
  --building-id ID      Ballenberg building identifier (required for real datasets)
  --capture-date DATE    Date of capture (ISO format: YYYY-MM-DD)
  --capture-method TYPE   TLS|UAV|CloseRange|Photogrammetry|StructureFromMotion
  --crs EPSG            Coordinate reference system (auto-detected for LV95, default: EPSG:2056)
  --scanner-model MODEL  Scanner or camera model
  --scan-positions N  Number of scan positions (TLS)
  --operator NAME        Person or organization who captured data
  --campaign-id ID      Reference to capture campaign
  --accuracy N          Estimated positional accuracy (meters)
  --has-color           RGB color data present
  --has-intensity       Intensity data present
  --construction-phase PH Building construction phase
  --region REGION         Swiss region of origin
  --era ERA              Historical era/period
  --building-type TYPE   Building type (farmhouse, barn, workshop, etc.)
  --catalog-number NUM    Ballenberg catalog number
  --tags TAG1,TAG2      Keywords for search (comma-separated)
  --description TEXT      Human-readable description
  --source-path PATH    Original source file path
"""

import sys, os, json, struct, shutil, re, argparse, datetime, glob, math, itertools, math, itertools
import numpy as np

# ── Defaults ─────────────────────────────────────────────────────────
DATA_DIR = os.environ.get('DATA_DIR', '/workspace/data')

# LV95 (Swiss national coordinates) - approximate bounds
LV95_X_MIN, LV95_X_MAX = 2600000, 2650000
LV95_Y_MIN, LV95_Y_MAX = 1150000, 1200000
LV95_Z_MIN, LV95_Z_MAX = 300, 2500

# LOD configuration
DEFAULT_LOD_LEVELS = [
    {'name': 'high', 'ratio': 1.0},      # 100% of points
    {'name': 'medium', 'ratio': 0.2},    # 20% of points
    {'name': 'low', 'ratio': 0.05}      # 5% of points
]

# ── Format detection ──────────────────────────────────────────────────────────

POINTCLOUD_EXTS = {'.las', '.laz', '.e57', '.xyz', '.txt', '.pts', '.ptx', '.pcd'}
MESH_EXTS       = {'.obj', '.glb', '.gltf', '.stl'}

def detect_format(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in POINTCLOUD_EXTS: return 'pointcloud'
    if ext in MESH_EXTS:       return 'mesh'
    if ext == '.splat':        return 'splat'
    if ext == '.ply':          return _detect_ply(path)
    raise ValueError(
        f"Unsupported extension: {ext!r}\n"
        "Supported: .las .laz .e57 .xyz .txt .pts .ptx .pcd .ply "
        ".obj .glb .gltf .stl .splat"
    )

def _detect_ply(path):
    with open(path, 'rb') as f:
        header = f.read(4096).decode('ascii', errors='ignore')
    if any(tok in header for tok in ('f_dc_0', 'scale_0', 'rot_0', 'opacity')):
        return 'splat_ply'      # 3D Gaussian Splatting PLY
    if 'element face' in header:
        return 'mesh'           # triangle mesh PLY
    return 'pointcloud'         # plain point cloud PLY

def detect_lv95_coordinates(xyz):
    """
    Detect if point cloud is in LV95 Swiss coordinate system.
    Returns (is_lv95, confidence).
    """
    x = xyz[:, 0]
    y = xyz[:, 1]
    z = xyz[:, 2]

    # Check if coordinates fall within LV95 bounds (90% of points)
    in_x = ((x >= LV95_X_MIN) & (x <= LV95_X_MAX)).sum() / len(xyz)
    in_y = ((y >= LV95_Y_MIN) & (y <= LV95_Y_MAX)).sum() / len(xyz)
    in_z = ((z >= LV95_Z_MIN) & (z <= LV95_Z_MAX)).sum() / len(xyz)

    confidence = min(in_x, in_y, in_z)
    is_lv95 = confidence > 0.9

    return is_lv95, confidence


# ── Slug helpers ──────────────────────────────────────────────────────────────

def slugify(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


# ── 3D Tiles: .pnts writer ────────────────────────────────────────────────────

def write_pnts(xyz, rgb, out_path):
    """Write a 3D Tiles 1.0 .pnts file (single tile, with optional RGB).

    Uses float64 for center calculation and offset computation to preserve
    precision for large coordinate systems (LV95 ~2.6M), then converts to
    standard float32 for output.

    xyz : (N, 3) positions (any dtype, will be converted)
    rgb : (N, 3) uint8     per-point colours, or None
    """
    # Ensure float64 for precise center calculation
    xyz = xyz.astype(np.float64)

    n   = len(xyz)

    # Use floor of min as center to keep offsets small and positive
    # This maximizes float32 precision in the final offsets
    xyz_min = xyz.min(axis=0)
    ctr = np.floor(xyz_min).astype(np.float64)

    # Calculate offsets in float64 (preserves precision)
    pos = xyz - ctr

    # Convert to float32 only at the final step (for 3D Tiles standard)
    pos = pos.astype(np.float32)

    pos_bytes = pos.tobytes()
    pos_pad   = (4 - len(pos_bytes) % 4) % 4

    if rgb is not None:
        rgb_offset = len(pos_bytes) + pos_pad
        rgb_entry  = f',"RGB":{{"byteOffset":{rgb_offset}}}'
        rgb_bytes  = rgb[:, :3].astype(np.uint8).tobytes()
    else:
        rgb_entry = ''
        rgb_bytes = b''

    ft_json = (
        f'{{"POINTS_LENGTH":{n},'
        f'"RTC_CENTER":[{ctr[0]:.6f},{ctr[1]:.6f},{ctr[2]:.6f}],'
        f'"POSITION":{{"byteOffset":0}}'
        f'{rgb_entry}}}'
    ).encode()
    ft_json += b' ' * ((-len(ft_json)) % 8)

    binary  = pos_bytes + b'\x00' * pos_pad + rgb_bytes
    binary += b'\x00' * ((-len(binary)) % 8)

    total  = 28 + len(ft_json) + len(binary)
    header = struct.pack('<4sIIIIII',
                         b'pnts', 1, total,
                         len(ft_json), len(binary), 0, 0)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'wb') as f:
        f.write(header + ft_json + binary)
    print(f"    wrote {out_path}  ({n:,} pts, {total:,} bytes)")
    return ctr


def voxel_grid_sample(xyz, voxel_size):
    """Sample points using voxel grid (one point per voxel)."""
    # Create voxel key from quantized coordinates
    grid = {}
    for point in xyz:
        key = (int(point[0] // voxel_size),
               int(point[1] // voxel_size),
               int(point[2] // voxel_size))
        if key not in grid:
            grid[key] = len(xyz)

    # Sample one point from each occupied voxel
    indices = []
    for key in grid:
        if grid[key] > 0:
            indices.append(grid[key])

    return xyz[indices] if indices else xyz


def calculate_lod_geometric_error(xyz, lod_ratio):
    """
    Calculate geometric error for an LOD level.

    Uses expected point spacing as proxy for screen-space error.
    Approximation: screen_error ≈ 1.5 × point_spacing
    """
    n = len(xyz)

    # Estimate point density (points per unit volume)
    center = xyz.mean(axis=0)
    radius = float(np.linalg.norm(xyz - center, axis=1).max()) * 1.05
    volume = (4/3) * math.pi * (radius ** 3)

    if volume > 0:
        point_density = n / volume
        point_spacing = point_density ** (-1/3)
    else:
        point_spacing = 0.01  # fallback

    # LOD geometric error: error grows as LOD gets coarser
    # Use point_spacing as proxy, multiply by LOD-specific factor
    lod_factors = {
        'high': 0.5,      # Finest: half point spacing
        'medium': 1.5,    # Medium: 1.5x point spacing
        'low': 3.0,         # Coarsest: 3x point spacing
    }

    base_error = point_spacing * 1.5
    return base_error * lod_factors.get(lod_ratio, 1.0)


def write_lod_tileset(xyz, out_dir, name, ds_id, lod_levels=None):
    """
    Write multi-resolution 3D Tiles with LOD support.

    If lod_levels is None, uses DEFAULT_LOD_LEVELS.
    lod_levels can be a list of LOD ratios, e.g.:
        [{'name': 'low', 'ratio': 0.05}, {'name': 'medium', 'ratio': 0.2}]
    """
    if lod_levels is None:
        lod_levels = DEFAULT_LOD_LEVELS

    center = xyz.mean(axis=0)
    radius = float(np.linalg.norm(xyz - center, axis=1).max()) * 1.05
    n = len(xyz)

    # Write each LOD level
    lod_dirs = {}
    for lod in lod_levels:
        lod_name = lod['name']
        lod_ratio = lod['ratio']

        # Subsample for this LOD
        if lod_ratio < 1.0:
            n_lod = max(1000, int(n * lod_ratio))  # Minimum 1000 points
            if n_lod >= n:
                xyz_lod = xyz
            else:
                xyz_lod = poisson_disk_sample(xyz, n_lod)
        else:
            xyz_lod = xyz

        # Create LOD directory
        lod_dir = os.path.join(out_dir, lod_name)
        os.makedirs(lod_dir, exist_ok=True)

        # Write .pnts file
        pnts_path = os.path.join(lod_dir, 'r.pnts')
        write_pnts(xyz_lod, None, pnts_path)

        # Calculate geometric error for this LOD
        geo_error = calculate_lod_geometric_error(xyz, lod_ratio)

        lod_dirs[lod_name] = {
            'lod': lod_name,
            'n_points': len(xyz_lod),
            'geometricError': geo_error,
            'directory': lod_name,
            'file_size': os.path.getsize(pnts_path)
        }

        print(f"  LOD {lod_name}: {len(xyz_lod):,} pts, error={geo_error:.2f}m")

    # Build hierarchical tileset
    # Level 0 is the finest (or specified first level)
    first_lod = lod_levels[0]
    root_lod = lod_dirs[first_lod['name']]

    ts = {
        "asset": {"version": "1.1"},
        "geometricError": root_lod['geometricError'],
        "root": {
            "geometricError": 0,
            "refine": "ADD",
            "boundingVolume": {
                "sphere": [float(center[0]), float(center[1]),
                           float(center[2]), float(radius)]
            },
            "content": {"uri": f"{first_lod['name']}/r.pnts"}
        }
    }

    # Add LOD levels as children
    current_level = ts['root']
    for i, lod in enumerate(lod_levels[1:], start=1):
        lod_dir = lod_dirs[lod['name']]
        child = {
            "geometricError": lod_dir['geometricError'],
            "refine": "ADD",
            "boundingVolume": {
                "sphere": [float(center[0]), float(center[1]),
                           float(center[2]), float(lod_dir['geometricError'])]
            },
            "content": {"uri": f"{lod['name']}/r.pnts"}
        }

        # Add children to appropriate parent level
        if i == 1:
            # First child is direct child of root
            ts['root']['children'] = [child]
        else:
            # Subsequent children are added to previous level
            while 'children' not in current_level:
                current_level = current_level['children'][-1]
            current_level['children'].append(child)

    # Write tileset
    ts_path = os.path.join(out_dir, 'tileset.json')
    with open(ts_path, 'w') as f:
        json.dump(ts, f, indent=2)
    print(f"    wrote {ts_path}")

    return ts_path, lod_dirs


def write_tileset(center, radius, content_uri, out_path):
    geo_err = float(radius) * 2
    ts = {
        "asset": {"version": "1.1"},
        "geometricError": geo_err,
        "root": {
            "geometricError": 0,
            "refine": "ADD",
            "boundingVolume": {
                "sphere": [float(center[0]), float(center[1]),
                           float(center[2]), float(radius)]
            },
            "content": {"uri": content_uri}
        }
    }
    with open(out_path, 'w') as f:
        json.dump(ts, f, indent=2)
    print(f"    wrote {out_path}")



# ── Point-cloud readers ───────────────────────────────────────────────────────

def _require(pkg, install):
    try:
        return __import__(pkg)
    except ImportError:
        sys.exit(f"ERROR: {pkg} not installed.  Run: pip3 install {install}")


def read_las(path):
    """Read LAS/LAZ point cloud, extract basic metadata."""
    laspy = _require('laspy', 'laspy[lazrs]')
    las   = laspy.read(path)
    xyz   = np.vstack([las.x, las.y, las.z]).T.astype(np.float32)
    rgb   = None
    metadata = {}

    if hasattr(las, 'red'):
        # LAS stores colour as 16-bit — scale to 8-bit
        scale = 257.0 if np.asarray(las.red).max() > 255 else 1.0
        rgb = np.column_stack([
            (np.asarray(las.red)   / scale).astype(np.uint8),
            (np.asarray(las.green) / scale).astype(np.uint8),
            (np.asarray(las.blue)  / scale).astype(np.uint8),
        ])

    # Extract LAS header metadata
    if hasattr(las, 'header'):
        header = las.header
        metadata['lasVersion'] = str(header.version)
        if hasattr(header, 'creation_date'):
            metadata['creationDate'] = str(header.creation_date)
        if hasattr(header, 'filesource_id'):
            metadata['fileSourceId'] = str(header.filesource_id)

    print(f"    {len(xyz):,} points from {os.path.basename(path)}")
    return xyz, rgb, metadata


def read_e57(path, extract_metadata=True):
    """
    Read E57 point cloud, extract metadata and scan positions.

    Returns: (xyz, rgb, metadata, scan_positions)
    """
    try:
        import pye57
    except ImportError:
        sys.exit("ERROR: pye57 not installed.  Run: pip3 install pye57")

    e57   = pye57.E57(path)
    xyzs, rgbs = [], []
    scan_positions = []
    metadata = {'scanCount': e57.scan_count}

    for i in range(e57.scan_count):
        try:
            data = e57.read_scan(i, intensity=False, colors=True, transform=True)
        except Exception as exc:
            print(f"    scan {i} skipped: {exc}")
            continue

        if 'cartesianX' not in data:
            continue

        pts = np.column_stack([
            data['cartesianX'], data['cartesianY'], data['cartesianZ']
        ]).astype(np.float32)
        xyzs.append(pts)

        # Extract scan position from header
        try:
            header = e57.get_header(i)
            pose = header.get('pose', {})
            translation = pose.get('translation', {})
            tx = translation.get('x', 0.0)
            ty = translation.get('y', 0.0)
            tz = translation.get('z', 0.0)

            scan_positions.append({
                'id': f'scan_{i:03d}',
                'label': f'Scan {i+1}',
                'index': i,
                'x': float(tx),
                'y': float(ty),
                'z': float(tz),
                'northOffset': 0
            })
        except Exception as exc:
            print(f"    scan {i} header read failed: {exc}")

        if 'colorRed' in data:
            rgbs.append(np.column_stack([
                np.clip(data['colorRed'],   0, 255).astype(np.uint8),
                np.clip(data['colorGreen'], 0, 255).astype(np.uint8),
                np.clip(data['colorBlue'],  0, 255).astype(np.uint8),
            ]))

    xyz = np.vstack(xyzs)
    rgb = np.vstack(rgbs) if rgbs else None
    metadata['scanPositions'] = len(scan_positions)
    print(f"    {len(xyz):,} points from {e57.scan_count} scan(s)")
    return xyz, rgb, metadata, scan_positions


def read_ptx(path):
    """Read Leica PTX (supports multiple scans, preserves colour if present)."""
    all_pts, all_rgb = [], []
    with open(path) as f:
        lines = f.readlines()
    i = 0
    while i < len(lines):
        # PTX scan header: cols, rows, pos(4), matrix(16 values over 4 lines)
        try:
            cols = int(lines[i].strip()); rows = int(lines[i+1].strip())
            i += 10  # skip cols, rows, scanner pos (4 lines), matrix (4 lines)
        except (ValueError, IndexError):
            i += 1
            continue
        n = cols * rows
        block = []
        while len(block) < n and i < len(lines):
            toks = lines[i].split(); i += 1
            if len(toks) >= 4:
                block.append(toks)
        arr = np.array([[float(t) for t in row[:7]] for row in block], dtype=np.float32)
        if len(arr) == 0:
            continue
        xyz = arr[:, :3]
        rgb_block = None
        if arr.shape[1] >= 7:
            rgb_block = arr[:, 4:7].astype(np.uint8)
        all_pts.append(xyz)
        if rgb_block is not None:
            all_rgb.append(rgb_block)

    xyz = np.vstack(all_pts)
    rgb = np.vstack(all_rgb) if all_rgb else None
    print(f"    {len(xyz):,} points from {os.path.basename(path)}")
    return xyz, rgb, {}


def read_xyz(path):
    """Read whitespace/comma-delimited ASCII: X Y Z [R G B] or X Y Z [Intensity]."""
    data = np.loadtxt(path, comments=['#', '//'])
    if data.ndim == 1:
        data = data[np.newaxis, :]
    xyz = data[:, :3].astype(np.float32)
    rgb = None
    if data.shape[1] >= 6:
        cols = data[:, 3:6]
        if cols.max() <= 1.01:          # 0-1 range → scale to 0-255
            cols = (cols * 255)
        rgb = cols.astype(np.uint8)
    print(f"    {len(xyz):,} points from {os.path.basename(path)}")
    return xyz, rgb, {}


def read_pcd(path):
    """Read PCD ASCII point cloud."""
    with open(path, 'rb') as f:
        raw = f.read()
    header_lines, data_start = [], 0
    for line in raw.split(b'\n'):
        txt = line.decode('ascii', errors='ignore').strip()
        header_lines.append(txt)
        data_start += len(line) + 1
        if txt.startswith('DATA'):
            break
    hdr     = {l.split()[0]: l.split()[1:] for l in header_lines if l and '#' not in l}
    fmt     = hdr.get('DATA', ['ascii'])[0]
    fields  = hdr.get('FIELDS', [])
    if fmt != 'ascii':
        raise ValueError("Binary PCD not supported — convert to ASCII PCD first.")
    data = np.loadtxt(path, comments=['#'])
    if data.ndim == 1:
        data = data[np.newaxis, :]
    idx = lambda name: fields.index(name) if name in fields else None
    xi, yi, zi = idx('x') or 0, idx('y') or 1, idx('z') or 2
    xyz = data[:, [xi, yi, zi]].astype(np.float32)
    rgb = None
    if idx('rgb') is not None:
        ri = idx('rgb')
        packed = data[:, ri].astype(np.float32).view(np.uint32)
        rgb = np.column_stack([
            ((packed >> 16) & 0xFF).astype(np.uint8),
            ((packed >>  8) & 0xFF).astype(np.uint8),
            ((packed      ) & 0xFF).astype(np.uint8),
        ])
    print(f"    {len(xyz):,} points from {os.path.basename(path)}")
    return xyz, rgb, {}


def read_ply_cloud(path):
    """Read PLY point cloud, extract basic metadata."""
    plyfile = _require('plyfile', 'plyfile')
    PlyData = plyfile.PlyData
    ply = PlyData.read(path)
    v   = ply['vertex']
    xyz = np.column_stack([
        np.array(v['x']), np.array(v['y']), np.array(v['z'])
    ]).astype(np.float32)
    rgb = None
    metadata = {'vertexCount': len(v)}

    if 'red' in v.data.dtype.names:
        rgb = np.column_stack([
            np.array(v['red']).astype(np.uint8),
            np.array(v['green']).astype(np.uint8),
            np.array(v['blue']).astype(np.uint8),
        ])
        metadata['hasColor'] = True

    print(f"    {len(xyz):,} points from {os.path.basename(path)}")
    return xyz, rgb, metadata


# ── E57 Panorama Extraction ─────────────────────────────────────────────────────

def extract_e57_panoramas(input_path, output_dir, ds_id):
    """
    Extract panoramic images from E57 file.

    Returns: list of panorama metadata
    """
    try:
        import pye57
    except ImportError:
        sys.exit("ERROR: pye57 not installed.  Run: pip3 install pye57")

    try:
        from PIL import Image
    except ImportError:
        sys.exit("ERROR: Pillow not installed.  Run: pip3 install Pillow")

    print(f"[E57 panoramas] Extracting from {os.path.basename(input_path)}")
    e57 = pye57.E57(input_path)
    scan_count = e57.scan_count

    panoramas = []
    pan_dir = os.path.join(output_dir, 'panoramas')
    os.makedirs(pan_dir, exist_ok=True)

    for i in range(scan_count):
        try:
            # Read scan data with colors
            data = e57.read_scan(i, intensity=True, colors=True, row_column=True, transform=False)

            # Get scanner position
            header = e57.get_header(i)
            pose = header.get('pose', {})
            translation = pose.get('translation', {})
            tx = translation.get('x', 0.0)
            ty = translation.get('y', 0.0)
            tz = translation.get('z', 0.0)

            # Get cartesian points for panorama generation
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
                continue

            points = np.column_stack([x, y, z])

            # Generate equirectangular panorama
            width, height = 2048, 1024
            img_array = _spherical_to_equirectangular(points, width, height)
            img = Image.fromarray(img_array)

            # Save panorama
            pan_path = os.path.join(pan_dir, f'scan_{i:03d}.jpg')
            img.save(pan_path, 'JPEG', quality=85)

            panoramas.append({
                'id': f'scan_{i:03d}',
                'label': f'Scan {i+1}',
                'path': f'/data/panoramas/{ds_id}/scan_{i:03d}.jpg',
                'x': float(tx),
                'y': float(ty),
                'z': float(tz),
                'northOffset': 0
            })

            print(f"    Saved: scan_{i:03d}.jpg ({len(points)} points)")

        except Exception as exc:
            print(f"    Scan {i} skipped: {exc}")

    print(f"    Extracted {len(panoramas)} panorama(s)")
    return panoramas


def _spherical_to_equirectangular(points_xyz, width=2048, height=1024):
    """Convert spherical points to equirectangular image."""
    img = np.zeros((height, width, 3), dtype=np.uint8)

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

    # Color by intensity (grayscale RGB)
    intensity = np.clip(r / r.max() * 255, 0, 255).astype(np.uint8)
    img[py, px, 0] = intensity
    img[py, px, 1] = intensity
    img[py, px, 2] = intensity

    return img


# ── Helmert Transformation ─────────────────────────────────────────────────────

def apply_helmert(xyz, helmert_params):
    """
    Apply 3D Helmert transformation to point cloud.

    helmert_params: dict with 'R' (3x3 rotation), 's' (scale), 't' (translation)
    """
    if helmert_params is None:
        return xyz

    R = np.array(helmert_params['R'])
    s = helmert_params['s']
    t = np.array(helmert_params['t'])

    # Apply transformation: x' = s * R * x + t
    transformed = xyz @ R.T * s + t
    return transformed


def load_helmert_params(helmert_path):
    """Load Helmert transformation parameters from JSON file."""
    with open(helmert_path) as f:
        return json.load(f)


# ── Processor: point cloud → 3D Tiles ────────────────────────────────────────

def process_pointcloud(input_path, out_dir, name, ds_id, data_dir, register,
                      extract_panoramas=False, helmert_params=None, **kwargs):
    ext = os.path.splitext(input_path)[1].lower()
    print(f"[point cloud] {os.path.basename(input_path)}")

    readers = {
        '.las': read_las, '.laz': read_las,
        '.e57': read_e57,
        '.ptx': read_ptx,
        '.pcd': read_pcd,
        '.ply': read_ply_cloud,
    }
    reader = readers.get(ext, read_xyz)

    # Read point cloud (E57 returns extra metadata)
    if ext == '.e57':
        xyz, rgb, file_meta, scan_positions = reader(input_path)
    else:
        xyz, rgb, file_meta = reader(input_path)
        scan_positions = None

    # Apply Helmert transformation if provided
    if helmert_params is not None:
        print(f"    Applying Helmert transformation...")
        xyz = apply_helmert(xyz, helmert_params)
        # Store helmert params in metadata
        kwargs['helmertLV95'] = helmert_params

    # Detect LV95 coordinates and set CRS if not specified
    if 'crs' not in kwargs or kwargs['crs'] is None:
        is_lv95, confidence = detect_lv95_coordinates(xyz)
        if is_lv95:
            kwargs['crs'] = 'EPSG:2056'
            print(f"    Detected LV95 coordinates (confidence: {confidence:.1%})")
        else:
            kwargs['crs'] = 'EPSG:2056'
            print(f"    Using default CRS: {kwargs['crs']}")

    # Write output files
    pnts_dir  = os.path.join(out_dir, '0')
    pnts_path = os.path.join(pnts_dir, 'r.pnts')
    center    = write_pnts(xyz, rgb, pnts_path)
    radius    = float(np.linalg.norm(xyz - center, axis=1).max()) * 1.05

    ts_path = os.path.join(out_dir, 'tileset.json')
    write_tileset(center, radius, '0/r.pnts', ts_path)

    # Auto-detect color presence
    if 'hasColor' not in kwargs or kwargs['hasColor'] is None:
        kwargs['hasColor'] = rgb is not None

    # Calculate point count
    kwargs['pointCount'] = len(xyz)

    # Add coverage info
    kwargs['coverage'] = {
        'center': center.tolist(),
        'radius': radius
    }

    # Add file size
    if 'fileSize' not in kwargs or kwargs['fileSize'] is None:
        kwargs['fileSize'] = os.path.getsize(input_path)

    # Add file metadata if available
    for key, val in file_meta.items():
        if key not in kwargs:
            kwargs[key] = val

    # Handle E57-specific metadata
    if scan_positions is not None:
        kwargs['scanPositions'] = len(scan_positions)

    # Determine output type (e57 for panoramas, cesium for others)
    if ext == '.e57' and extract_panoramas:
        # Create E57 panorama output
        pan_dir = os.path.join(data_dir, 'panoramas', ds_id)
        os.makedirs(pan_dir, exist_ok=True)

        # Extract panoramas
        panoramas = extract_e57_panoramas(input_path, pan_dir, ds_id)
        kwargs['panoramas'] = panoramas
        kwargs['scanPositions'] = len(panoramas)

        # Write E57 metadata file
        meta_path = os.path.join(pan_dir, 'metadata.json')
        e57_meta = {
            'id': ds_id,
            'name': name,
            'type': 'e57',
            'source': kwargs.get('source', 'lidar'),
            'path': f'/data/panoramas/{ds_id}/metadata.json',
            'createdAt': kwargs.get('createdAt', datetime.datetime.utcnow().isoformat() + 'Z'),
            **kwargs
        }
        with open(meta_path, 'w') as f:
            json.dump(e57_meta, f, indent=2)
        print(f"    wrote {meta_path}")

        rel_path = f'/data/panoramas/{ds_id}/metadata.json'
        ds_type = 'e57'
    else:
        rel_path = f'/data/cesium/{ds_id}/tileset.json'
        ds_type = 'cesium'

    dataset = _make_dataset(ds_id, name, ds_type, kwargs.get('source', 'lidar'), rel_path, input_path, **kwargs)
    if register:
        register_dataset(data_dir, dataset)
    return dataset


# ── Processor: mesh → GLB tileset ────────────────────────────────────────────

def process_mesh(input_path, out_dir, name, ds_id, data_dir, register, helmert_params=None, **kwargs):
    print(f"[mesh] {os.path.basename(input_path)}")
    try:
        import trimesh
    except ImportError:
        sys.exit("ERROR: trimesh not installed.  Run: pip3 install trimesh[easy]")

    scene = trimesh.load(input_path)
    # Flatten multi-mesh scenes into a single mesh
    if isinstance(scene, trimesh.Scene):
        meshes = [g for g in scene.geometry.values()
                  if isinstance(g, trimesh.Trimesh)]
        if not meshes:
            sys.exit("ERROR: no triangle meshes found in file.")
        mesh = trimesh.util.concatenate(meshes)
    else:
        mesh = scene

    vertices = mesh.vertices

    # Apply Helmert transformation if provided
    if helmert_params is not None:
        print(f"    Applying Helmert transformation...")
        mesh.vertices = apply_helmert(mesh.vertices, helmert_params)
        kwargs['helmertLV95'] = helmert_params

    print(f"    {len(vertices):,} vertices, {len(mesh.faces):,} faces")

    os.makedirs(out_dir, exist_ok=True)
    glb_path = os.path.join(out_dir, 'mesh.glb')
    with open(glb_path, 'wb') as f:
        f.write(mesh.export(file_type='glb'))
    print(f"    wrote {glb_path}  ({os.path.getsize(glb_path):,} bytes)")

    bounds = mesh.bounds
    center = (bounds[0] + bounds[1]) / 2
    radius = float(np.linalg.norm(bounds[1] - bounds[0]) / 2) * 1.05

    ts_path = os.path.join(out_dir, 'tileset.json')
    write_tileset(center, radius, 'mesh.glb', ts_path)

    # Add coverage info
    kwargs['coverage'] = {
        'center': center.tolist(),
        'radius': radius
    }

    # Add file size
    if 'fileSize' not in kwargs or kwargs['fileSize'] is None:
        kwargs['fileSize'] = os.path.getsize(input_path)

    rel_path = f'/data/cesium/{ds_id}/tileset.json'
    dataset = _make_dataset(ds_id, name, 'cesium', kwargs.get('source', 'photogrammetry'), rel_path, input_path, **kwargs)
    if register:
        register_dataset(data_dir, dataset)
    return dataset


# ── Processor: .splat copy ────────────────────────────────────────────────────

def process_splat(input_path, data_dir, name, ds_id, register, **kwargs):
    print(f"[splat] {os.path.basename(input_path)}")
    out_dir  = os.path.join(data_dir, 'splats')
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f'{ds_id}.splat')
    shutil.copy2(input_path, out_path)
    print(f"    copied to {out_path}")

    # Add file size
    if 'fileSize' not in kwargs or kwargs['fileSize'] is None:
        kwargs['fileSize'] = os.path.getsize(input_path)

    # Gaussian splats always have color
    if 'hasColor' not in kwargs or kwargs['hasColor'] is None:
        kwargs['hasColor'] = True

    rel_path = f'/data/splats/{ds_id}.splat'
    dataset = _make_dataset(ds_id, name, 'splat', kwargs.get('source', 'photogrammetry'), rel_path, input_path, **kwargs)
    if register:
        register_dataset(data_dir, dataset)
    return dataset


# ── Processor: 3DGS PLY → .splat ─────────────────────────────────────────────

_C0 = 0.28209479177387814   # SH degree-0 DC coefficient (normalization constant)

def process_3dgs_ply(input_path, data_dir, name, ds_id, register, helmert_params=None, **kwargs):
    """Convert a 3D Gaussian Splatting PLY to the .splat binary format."""
    print(f"[3DGS PLY] {os.path.basename(input_path)}")
    plyfile = _require('plyfile', 'plyfile')
    PlyData = plyfile.PlyData

    ply = PlyData.read(input_path)
    v   = ply['vertex']
    n   = len(v)
    print(f"    {n:,} Gaussians")

    # Position
    x = np.array(v['x'], dtype=np.float32)
    y = np.array(v['y'], dtype=np.float32)
    z = np.array(v['z'], dtype=np.float32)

    # Apply Helmert transformation if provided
    if helmert_params is not None:
        print(f"    Applying Helmert transformation...")
        xyz = np.column_stack([x, y, z])
        xyz = apply_helmert(xyz, helmert_params)
        x, y, z = xyz[:, 0], xyz[:, 1], xyz[:, 2]
        kwargs['helmertLV95'] = helmert_params

    # Log-scale (stored as log in 3DGS PLY, same convention used by .splat)
    s0 = np.array(v['scale_0'], dtype=np.float32)
    s1 = np.array(v['scale_1'], dtype=np.float32)
    s2 = np.array(v['scale_2'], dtype=np.float32)

    # Rotation quaternion WXYZ → normalise → pack to uint8
    r0 = np.array(v['rot_0'], dtype=np.float64)
    r1 = np.array(v['rot_1'], dtype=np.float64)
    r2 = np.array(v['rot_2'], dtype=np.float64)
    r3 = np.array(v['rot_3'], dtype=np.float64)
    rot = np.column_stack([r0, r1, r2, r3])
    nrm = np.linalg.norm(rot, axis=1, keepdims=True)
    nrm = np.where(nrm < 1e-10, 1.0, nrm)
    rot /= nrm   # normalised to [-1, 1]
    rot_u8 = np.clip(rot * 128.0 + 128.0, 0, 255).astype(np.uint8)   # WXYZ

    # Colour from SH DC coefficient: sigmoid(f_dc * C0 + 0.5) * 255
    def _sh_to_u8(dc):
        return np.clip((dc * _C0 + 0.5) * 255.0, 0, 255).astype(np.uint8)

    cr = _sh_to_u8(np.array(v['f_dc_0'], dtype=np.float32))
    cg = _sh_to_u8(np.array(v['f_dc_1'], dtype=np.float32))
    cb = _sh_to_u8(np.array(v['f_dc_2'], dtype=np.float32))

    # Opacity: sigmoid(raw) * 255
    raw_op = np.array(v['opacity'], dtype=np.float32)
    alpha  = (1.0 / (1.0 + np.exp(-raw_op)) * 255.0).astype(np.uint8)

    # Pack: 32 bytes per splat
    # [x:4 y:4 z:4 | s0:4 s1:4 s2:4 | R G B A | W X Y Z]
    buf = np.zeros((n, 32), dtype=np.uint8)
    for col_start, arr in zip([0, 4, 8, 12, 16, 20],
                               [x, y, z, s0, s1, s2]):
        buf[:, col_start:col_start+4] = arr.view(np.uint8).reshape(n, 4)
    buf[:, 24] = cr
    buf[:, 25] = cg
    buf[:, 26] = cb
    buf[:, 27] = alpha
    buf[:, 28] = rot_u8[:, 0]   # W
    buf[:, 29] = rot_u8[:, 1]   # X
    buf[:, 30] = rot_u8[:, 2]   # Y
    buf[:, 31] = rot_u8[:, 3]   # Z

    out_dir  = os.path.join(data_dir, 'splats')
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f'{ds_id}.splat')
    with open(out_path, 'wb') as f:
        f.write(buf.tobytes())
    print(f"    wrote {out_path}  ({os.path.getsize(out_path):,} bytes)")

    # Add file size and point count
    if 'fileSize' not in kwargs or kwargs['fileSize'] is None:
        kwargs['fileSize'] = os.path.getsize(out_path)
    kwargs['pointCount'] = n

    # Gaussian splats always have color
    if 'hasColor' not in kwargs or kwargs['hasColor'] is None:
        kwargs['hasColor'] = True

    # Calculate coverage center and radius from bounding box
    xyz = np.column_stack([x, y, z])
    center = xyz.mean(axis=0)
    radius = float(np.linalg.norm(xyz - center, axis=1).max()) * 1.05
    kwargs['coverage'] = {
        'center': center.tolist(),
        'radius': radius
    }

    rel_path = f'/data/splats/{ds_id}.splat'
    dataset = _make_dataset(ds_id, name, 'splat', kwargs.get('source', 'photogrammetry'), rel_path, input_path, **kwargs)
    if register:
        register_dataset(data_dir, dataset)
    return dataset


# ── Batch Processing ───────────────────────────────────────────────────────────

def get_batch_files(directory, config=None):
    """
    Get list of files to process in batch mode.

    Returns: list of (input_path, metadata_override) tuples
    """
    files_to_process = []

    # Read config file if provided
    config_data = {}
    if config and os.path.exists(config):
        with open(config) as f:
            config_data = json.load(f)

    # Find all supported files
    for pattern in ['*.las', '*.laz', '*.e57', '*.ply', '*.xyz', '*.pts', '*.ptx', '*.pcd', '*.obj', '*.glb', '*.gltf', '*.stl', '*.splat']:
        for path in glob.glob(os.path.join(directory, pattern)):
            # Check for file-specific config in config_data
            filename = os.path.basename(path)
            file_config = config_data.get(filename, {})
            files_to_process.append((path, file_config))

    return sorted(files_to_process)


def process_batch(directory, data_dir, register, extract_panoramas=False, helmert_path=None, config=None, global_metadata=None):
    """
    Process multiple files in directory.

    Returns: summary of processed files
    """
    helmert_params = None
    if helmert_path and os.path.exists(helmert_path):
        helmert_params = load_helmert_params(helmert_path)

    files_to_process = get_batch_files(directory, config)

    summary = {
        'total': len(files_to_process),
        'processed': [],
        'failed': [],
        'skipped': []
    }

    print(f"\n{'='*60}")
    print(f"BATCH PROCESSING: {len(files_to_process)} files")
    print(f"{'='*60}\n")

    for i, (input_path, file_config) in enumerate(files_to_process):
        filename = os.path.basename(input_path)
        print(f"[{i+1}/{len(files_to_process)}] {filename}")

        # Merge global metadata with file-specific config
        metadata = global_metadata.copy() if global_metadata else {}
        metadata.update(file_config)

        try:
            # Extract name/id from filename or config
            name = metadata.get('name', os.path.splitext(filename)[0])
            ds_id = metadata.get('id', slugify(name))

            # Determine output directory based on file type
            fmt = detect_format(input_path)

            if fmt == 'pointcloud':
                out_dir = os.path.join(data_dir, 'cesium', ds_id)
                ds = process_pointcloud(input_path, out_dir, name, ds_id, data_dir, register,
                                       extract_panoramas, helmert_params, **metadata)
            elif fmt == 'mesh':
                out_dir = os.path.join(data_dir, 'cesium', ds_id)
                ds = process_mesh(input_path, out_dir, name, ds_id, data_dir, register,
                                helmert_params, **metadata)
            elif fmt == 'splat':
                ds = process_splat(input_path, data_dir, name, ds_id, register, **metadata)
            elif fmt == 'splat_ply':
                ds = process_3dgs_ply(input_path, data_dir, name, ds_id, register,
                                       helmert_params, **metadata)
            else:
                raise ValueError(f"Unhandled format: {fmt}")

            summary['processed'].append({'file': filename, 'id': ds['id']})

        except Exception as e:
            print(f"    ERROR: {e}")
            summary['failed'].append({'file': filename, 'error': str(e)})

        print()

    return summary


# ── Dataset helpers ───────────────────────────────────────────────────────────

def _make_dataset(ds_id, name, ds_type, source, path, input_path, **kwargs):
    """Create dataset metadata with full schema support."""
    ds = {
        "id":          ds_id,
        "name":        name,
        "type":        ds_type,
        "source":      source,
        "path":        path,
        "description": kwargs.get('description', f"Converted from {os.path.basename(input_path)}"),
        "createdAt":   kwargs.get('createdAt', datetime.datetime.utcnow().isoformat() + 'Z'),
    }

    # Metadata schema fields (add if provided)
    metadata_fields = [
        'buildingId', 'captureDate', 'captureMethod', 'crs',
        'scannerModel', 'scanPositions', 'operator', 'campaignId',
        'accuracy', 'hasColor', 'hasIntensity',
        'constructionPhase', 'region', 'era', 'buildingType', 'catalogNumber',
        'tags', 'sourcePath', 'sourceFormat', 'processedBy', 'processingDate',
        'processingNotes', 'pointCount', 'fileSize', 'coverage', 'modelMatrix', 'helmertLV95',
        'panoramas', 'lodLevels'
    ]

    for field in metadata_fields:
        if field in kwargs and kwargs[field] is not None:
            ds[field] = kwargs[field]

    return ds


def register_dataset(data_dir, dataset):
    db_path = os.path.join(data_dir, 'datasets.json')
    datasets = []
    if os.path.exists(db_path):
        with open(db_path) as f:
            datasets = json.load(f)
    # Replace if same ID, otherwise append
    datasets = [d for d in datasets if d['id'] != dataset['id']]
    datasets.append(dataset)
    with open(db_path, 'w') as f:
        json.dump(datasets, f, indent=2)
    print(f"    registered '{dataset['id']}' in datasets.json")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument('input',               help='Input file or directory (with --batch)')
    p.add_argument('--name',              help='Dataset name (default: filename stem)')
    p.add_argument('--id',                help='Dataset ID slug (default: derived from name)')
    p.add_argument('--data-dir',   default=DATA_DIR,
                   help=f'Data directory root (default: {DATA_DIR})')
    p.add_argument('--no-register', action='store_true',
                   help='Skip registration in datasets.json')

    # Processing modes
    p.add_argument('--batch', action='store_true',
                   help='Batch mode: process all files in input directory')
    p.add_argument('--config', help='JSON config file for batch processing')
    p.add_argument('--extract-panoramas', action='store_true',
                   help='Extract E57 panoramas to output directory')
    p.add_argument('--helmert', help='Apply Helmert transformation from JSON file')

    # Metadata options
    p.add_argument('--building-id',        help='Ballenberg building identifier')
    p.add_argument('--capture-date',        help='Date of capture (YYYY-MM-DD)')
    p.add_argument('--capture-method', choices=['TLS', 'UAV', 'CloseRange', 'Photogrammetry', 'StructureFromMotion'],
                   help='Capture method used')
    p.add_argument('--crs',                default='EPSG:2056',
                   help='Coordinate reference system (default: EPSG:2056 LV95, auto-detected)')
    p.add_argument('--scanner-model',       help='Scanner or camera model')
    p.add_argument('--scan-positions', type=int,
                   help='Number of scan positions (TLS)')
    p.add_argument('--operator',           help='Person or organization who captured data')
    p.add_argument('--campaign-id',        help='Reference to capture campaign')
    p.add_argument('--accuracy', type=float,
                   help='Estimated positional accuracy (meters)')
    p.add_argument('--has-color', action='store_true',
                   help='RGB color data present')
    p.add_argument('--has-intensity', action='store_true',
                   help='Intensity data present')
    p.add_argument('--construction-phase',  help='Building construction phase')
    p.add_argument('--region',             help='Swiss region of origin')
    p.add_argument('--era',                help='Historical era/period')
    p.add_argument('--building-type',      help='Building type (farmhouse, barn, workshop, etc.)')
    p.add_argument('--catalog-number',      help='Ballenberg catalog number')
    p.add_argument('--tags',               help='Keywords for search (comma-separated)')
    p.add_argument('--description',         help='Human-readable description')
    p.add_argument('--source-path',        help='Original source file path')

    args = p.parse_args()

    input_path = os.path.abspath(args.input)
    if not os.path.exists(input_path):
        sys.exit(f"ERROR: file/directory not found: {input_path}")

    # Collect global metadata kwargs
    metadata_kwargs = {
        'buildingId': args.building_id,
        'captureDate': args.capture_date,
        'captureMethod': args.capture_method,
        'crs': args.crs,
        'scannerModel': args.scanner_model,
        'scanPositions': args.scan_positions,
        'operator': args.operator,
        'campaignId': args.campaign_id,
        'accuracy': args.accuracy,
        'hasColor': args.has_color,
        'hasIntensity': args.has_intensity,
        'constructionPhase': args.construction_phase,
        'region': args.region,
        'era': args.era,
        'buildingType': args.building_type,
        'catalogNumber': args.catalog_number,
        'description': args.description,
        'sourcePath': args.source_path or input_path,
        'sourceFormat': None,  # Will be set based on file type
        'processedBy': 'process.py v2.0',
        'processingDate': datetime.datetime.utcnow().isoformat() + 'Z',
    }

    # Handle tags (comma-separated to array)
    if args.tags:
        metadata_kwargs['tags'] = [t.strip() for t in args.tags.split(',')]

    # Batch mode
    if args.batch:
        print("\nBATCH MODE")
        print(f"Input directory: {input_path}")
        print(f"Config file: {args.config if args.config else 'None'}")
        print(f"Extract panoramas: {args.extract_panoramas}")
        print(f"Helmert: {args.helmert if args.helmert else 'None'}\n")

        summary = process_batch(input_path, os.path.abspath(args.data_dir),
                           not args.no_register,
                           args.extract_panoramas,
                           args.helmert,
                           args.config,
                           metadata_kwargs)

        print(f"\n{'='*60}")
        print("BATCH SUMMARY")
        print(f"{'='*60}")
        print(f"Total files:    {summary['total']}")
        print(f"Processed:      {len(summary['processed'])}")
        print(f"Failed:        {len(summary['failed'])}")
        print(f"Skipped:       {len(summary['skipped'])}")

        if summary['failed']:
            print("\nFAILED FILES:")
            for item in summary['failed']:
                print(f"  - {item['file']}: {item['error']}")

        return

    # Single file mode
    name      = args.name or os.path.splitext(os.path.basename(input_path))[0]
    ds_id     = args.id   or slugify(name)
    data_dir  = os.path.abspath(args.data_dir)
    register  = not args.no_register

    # Set source format
    metadata_kwargs['sourceFormat'] = os.path.splitext(input_path)[1][1:].upper()

    # Load Helmert transformation if provided
    helmert_params = None
    if args.helmert and os.path.exists(args.helmert):
        helmert_params = load_helmert_params(args.helmert)

    fmt = detect_format(input_path)
    print(f"format: {fmt}")

    if fmt == 'pointcloud':
        out_dir = os.path.join(data_dir, 'cesium', ds_id)
        ds = process_pointcloud(input_path, out_dir, name, ds_id, data_dir, register,
                               args.extract_panoramas, helmert_params, **metadata_kwargs)

    elif fmt == 'mesh':
        out_dir = os.path.join(data_dir, 'cesium', ds_id)
        ds = process_mesh(input_path, out_dir, name, ds_id, data_dir, register,
                        helmert_params, **metadata_kwargs)

    elif fmt == 'splat':
        ds = process_splat(input_path, data_dir, name, ds_id, register, **metadata_kwargs)

    elif fmt == 'splat_ply':
        ds = process_3dgs_ply(input_path, data_dir, name, ds_id, register,
                               helmert_params, **metadata_kwargs)

    else:
        sys.exit(f"ERROR: unhandled format: {fmt}")

    # Write metadata JSON alongside converted data (if not E57)
    if fmt in ('pointcloud', 'mesh'):
        meta_path = os.path.join(data_dir, 'cesium', ds_id, 'metadata.json')
        with open(meta_path, 'w') as f:
            json.dump(ds, f, indent=2)
        print(f"    wrote {meta_path}")

    print(f"\nDone.  {ds['id']} → {ds['path']}")
    if not register:
        print("\nRegister manually:")
        print(f"  curl -X POST http://localhost:3000/api/datasets \\")
        print(f"    -H 'Content-Type: application/json' \\")
        print(f"    -d '{json.dumps(ds)}'")


if __name__ == '__main__':
    main()
