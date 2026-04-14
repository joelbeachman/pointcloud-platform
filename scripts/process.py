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

Usage
  python3 scripts/process.py <input_file> [options]

Options
  --name NAME      Human-readable dataset name (default: filename stem)
  --id   ID        Dataset ID slug (default: auto-derived from name)
  --data-dir DIR   Data directory root (default: DATA_DIR env or /workspace/data)
  --no-register    Skip auto-registration in datasets.json
"""

import sys, os, json, struct, shutil, re, argparse, datetime
import numpy as np

# ── Defaults ─────────────────────────────────────────────────────────────────
DATA_DIR = os.environ.get('DATA_DIR', '/workspace/data')


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


# ── Slug helpers ──────────────────────────────────────────────────────────────

def slugify(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


# ── 3D Tiles: .pnts writer ────────────────────────────────────────────────────

def write_pnts(xyz, rgb, out_path):
    """Write a 3D Tiles 1.0 .pnts file (single tile, with optional RGB).

    xyz : (N, 3) float32   world-space positions
    rgb : (N, 3) uint8     per-point colours, or None
    """
    n   = len(xyz)
    ctr = xyz.mean(axis=0)
    pos = (xyz - ctr).astype(np.float32)

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
    laspy = _require('laspy', 'laspy[lazrs]')
    las   = laspy.read(path)
    xyz   = np.vstack([las.x, las.y, las.z]).T.astype(np.float32)
    rgb   = None
    if hasattr(las, 'red'):
        # LAS stores colour as 16-bit — scale to 8-bit
        scale = 257.0 if np.asarray(las.red).max() > 255 else 1.0
        rgb = np.column_stack([
            (np.asarray(las.red)   / scale).astype(np.uint8),
            (np.asarray(las.green) / scale).astype(np.uint8),
            (np.asarray(las.blue)  / scale).astype(np.uint8),
        ])
    print(f"    {len(xyz):,} points from {os.path.basename(path)}")
    return xyz, rgb


def read_e57(path):
    try:
        import pye57
    except ImportError:
        sys.exit("ERROR: pye57 not installed.  Run: pip3 install pye57")
    e57   = pye57.E57(path)
    xyzs, rgbs = [], []
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
        if 'colorRed' in data:
            rgbs.append(np.column_stack([
                np.clip(data['colorRed'],   0, 255).astype(np.uint8),
                np.clip(data['colorGreen'], 0, 255).astype(np.uint8),
                np.clip(data['colorBlue'],  0, 255).astype(np.uint8),
            ]))
    xyz = np.vstack(xyzs)
    rgb = np.vstack(rgbs) if rgbs else None
    print(f"    {len(xyz):,} points from {e57.scan_count} scan(s)")
    return xyz, rgb


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
    return xyz, rgb


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
    return xyz, rgb


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
    return xyz, rgb


def read_ply_cloud(path):
    plyfile = _require('plyfile', 'plyfile')
    PlyData = plyfile.PlyData
    ply = PlyData.read(path)
    v   = ply['vertex']
    xyz = np.column_stack([
        np.array(v['x']), np.array(v['y']), np.array(v['z'])
    ]).astype(np.float32)
    rgb = None
    if 'red' in v.data.dtype.names:
        rgb = np.column_stack([
            np.array(v['red']).astype(np.uint8),
            np.array(v['green']).astype(np.uint8),
            np.array(v['blue']).astype(np.uint8),
        ])
    print(f"    {len(xyz):,} points from {os.path.basename(path)}")
    return xyz, rgb


# ── Processor: point cloud → 3D Tiles ────────────────────────────────────────

def process_pointcloud(input_path, out_dir, name, ds_id, data_dir, register):
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
    xyz, rgb = reader(input_path)

    pnts_dir  = os.path.join(out_dir, '0')
    pnts_path = os.path.join(pnts_dir, 'r.pnts')
    center    = write_pnts(xyz, rgb, pnts_path)
    radius    = float(np.linalg.norm(xyz - center, axis=1).max()) * 1.05

    ts_path = os.path.join(out_dir, 'tileset.json')
    write_tileset(center, radius, '0/r.pnts', ts_path)

    rel_path = f'/data/cesium/{ds_id}/tileset.json'
    dataset  = _make_dataset(ds_id, name, 'cesium', 'lidar', rel_path, input_path)
    if register:
        register_dataset(data_dir, dataset)
    return dataset


# ── Processor: mesh → GLB tileset ────────────────────────────────────────────

def process_mesh(input_path, out_dir, name, ds_id, data_dir, register):
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

    print(f"    {len(mesh.vertices):,} vertices, {len(mesh.faces):,} faces")

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

    rel_path = f'/data/cesium/{ds_id}/tileset.json'
    dataset  = _make_dataset(ds_id, name, 'cesium', 'photogrammetry', rel_path, input_path)
    if register:
        register_dataset(data_dir, dataset)
    return dataset


# ── Processor: .splat copy ────────────────────────────────────────────────────

def process_splat(input_path, data_dir, name, ds_id, register):
    print(f"[splat] {os.path.basename(input_path)}")
    out_dir  = os.path.join(data_dir, 'splats')
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f'{ds_id}.splat')
    shutil.copy2(input_path, out_path)
    print(f"    copied to {out_path}")

    rel_path = f'/data/splats/{ds_id}.splat'
    dataset  = _make_dataset(ds_id, name, 'splat', 'photogrammetry', rel_path, input_path)
    if register:
        register_dataset(data_dir, dataset)
    return dataset


# ── Processor: 3DGS PLY → .splat ─────────────────────────────────────────────

_C0 = 0.28209479177387814   # SH degree-0 DC coefficient (normalization constant)

def process_3dgs_ply(input_path, data_dir, name, ds_id, register):
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

    rel_path = f'/data/splats/{ds_id}.splat'
    dataset  = _make_dataset(ds_id, name, 'splat', 'photogrammetry', rel_path, input_path)
    if register:
        register_dataset(data_dir, dataset)
    return dataset


# ── Dataset helpers ───────────────────────────────────────────────────────────

def _make_dataset(ds_id, name, ds_type, source, path, input_path):
    return {
        "id":          ds_id,
        "name":        name,
        "type":        ds_type,
        "source":      source,
        "path":        path,
        "description": f"Converted from {os.path.basename(input_path)}",
        "createdAt":   datetime.datetime.utcnow().isoformat() + 'Z',
    }


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
    p.add_argument('input',       help='Input file to process')
    p.add_argument('--name',      help='Dataset name (default: filename stem)')
    p.add_argument('--id',        help='Dataset ID slug (default: derived from name)')
    p.add_argument('--data-dir',  default=DATA_DIR,
                   help=f'Data directory root (default: {DATA_DIR})')
    p.add_argument('--no-register', action='store_true',
                   help='Skip registration in datasets.json')
    args = p.parse_args()

    input_path = os.path.abspath(args.input)
    if not os.path.exists(input_path):
        sys.exit(f"ERROR: file not found: {input_path}")

    name      = args.name or os.path.splitext(os.path.basename(input_path))[0]
    ds_id     = args.id   or slugify(name)
    data_dir  = os.path.abspath(args.data_dir)
    register  = not args.no_register

    fmt = detect_format(input_path)
    print(f"format: {fmt}")

    if fmt == 'pointcloud':
        out_dir = os.path.join(data_dir, 'cesium', ds_id)
        os.makedirs(out_dir, exist_ok=True)
        ds = process_pointcloud(input_path, out_dir, name, ds_id, data_dir, register)

    elif fmt == 'mesh':
        out_dir = os.path.join(data_dir, 'cesium', ds_id)
        os.makedirs(out_dir, exist_ok=True)
        ds = process_mesh(input_path, out_dir, name, ds_id, data_dir, register)

    elif fmt == 'splat':
        ds = process_splat(input_path, data_dir, name, ds_id, register)

    elif fmt == 'splat_ply':
        ds = process_3dgs_ply(input_path, data_dir, name, ds_id, register)

    else:
        sys.exit(f"ERROR: unhandled format: {fmt}")

    print(f"\nDone.  {ds['id']} → {ds['path']}")
    if not register:
        print("\nRegister manually:")
        print(f"  curl -X POST http://localhost:3000/api/datasets \\")
        print(f"    -H 'Content-Type: application/json' \\")
        print(f"    -d '{json.dumps(ds)}'")


if __name__ == '__main__':
    main()
