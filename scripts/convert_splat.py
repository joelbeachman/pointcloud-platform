#!/usr/bin/env python3
"""Convert a .splat file to a CesiumJS-compatible 3D Tiles directory.

Produces a GLB tile using the KHR_gaussian_splatting glTF extension
plus a tileset.json wrapper loadable by CesiumJS 1.115+.

Usage:
    python3 scripts/convert_splat.py <input.splat> <output_dir>
"""
import sys, os, json, struct, math
import numpy as np

STRIDE = 32  # bytes per splat


def load_splat(path):
    raw = np.frombuffer(open(path, 'rb').read(), dtype=np.uint8)
    n   = len(raw) // STRIDE
    raw = raw[: n * STRIDE].reshape(n, STRIDE)

    # Positions: bytes 0-11, three float32
    positions = raw[:, 0:12].view(np.float32).reshape(n, 3).copy()

    # Scales: bytes 12-23, stored as ln(scale) → exponentiate
    log_scales = raw[:, 12:24].view(np.float32).reshape(n, 3).copy()
    scales     = np.exp(log_scales).astype(np.float32)

    # Colors: bytes 24-27, RGBA uint8
    colors = raw[:, 24:28].copy()

    # Rotations: bytes 28-31, packed uint8 WXYZ → normalised float XYZW (glTF)
    rb   = raw[:, 28:32].astype(np.float64)
    rf   = (rb - 128.0) / 128.0
    nrm  = np.linalg.norm(rf, axis=1, keepdims=True)
    nrm  = np.where(nrm < 1e-10, 1.0, nrm)
    rf  /= nrm
    # Reorder W,X,Y,Z → X,Y,Z,W
    rotations = np.column_stack([rf[:, 1], rf[:, 2], rf[:, 3], rf[:, 0]]).astype(np.float32)

    print(f"Loaded {n:,} splats from {os.path.basename(path)}")
    return positions, scales, colors, rotations


def pack_buffer(*arrays):
    """Pack arrays into one aligned byte buffer.
    Returns (bytes, list of (byteOffset, byteLength) tuples)."""
    parts, offsets, lengths = [], [], []
    off = 0
    for a in arrays:
        b   = a.flatten().tobytes()
        pad = (4 - len(b) % 4) % 4
        offsets.append(off)
        lengths.append(len(b))
        parts.append(b + b'\x00' * pad)
        off += len(b) + pad
    return b''.join(parts), list(zip(offsets, lengths))


def build_glb(positions, scales, colors, rotations):
    n = len(positions)
    buf, ols = pack_buffer(positions, scales, rotations, colors)
    pos_o, sc_o, rot_o, col_o = ols

    pmin = positions.min(axis=0).tolist()
    pmax = positions.max(axis=0).tolist()

    gltf = {
        "asset": {"version": "2.0", "generator": "convert_splat.py"},
        "extensionsUsed":     ["KHR_gaussian_splatting"],
        "extensionsRequired": ["KHR_gaussian_splatting"],
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{
            "primitives": [{
                "mode": 0,
                "attributes": {},
                "extensions": {
                    "KHR_gaussian_splatting": {
                        "attributes": {
                            "POSITION": 0,
                            "SCALE":    1,
                            "ROTATION": 2,
                            "COLOR_0":  3,
                        }
                    }
                }
            }]
        }],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": n, "type": "VEC3",
             "min": pmin, "max": pmax},
            {"bufferView": 1, "componentType": 5126, "count": n, "type": "VEC3"},
            {"bufferView": 2, "componentType": 5126, "count": n, "type": "VEC4"},
            {"bufferView": 3, "componentType": 5121, "normalized": True,
             "count": n, "type": "VEC4"},
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": pos_o[0], "byteLength": pos_o[1]},
            {"buffer": 0, "byteOffset": sc_o[0],  "byteLength": sc_o[1]},
            {"buffer": 0, "byteOffset": rot_o[0], "byteLength": rot_o[1]},
            {"buffer": 0, "byteOffset": col_o[0], "byteLength": col_o[1]},
        ],
        "buffers": [{"byteLength": len(buf)}],
    }

    json_bytes = json.dumps(gltf, separators=(',', ':')).encode()
    json_pad   = (4 - len(json_bytes) % 4) % 4
    json_chunk = json_bytes + b' ' * json_pad

    c0     = struct.pack('<II', len(json_chunk), 0x4E4F534A) + json_chunk
    c1     = struct.pack('<II', len(buf),        0x004E4942) + buf
    total  = 12 + len(c0) + len(c1)
    header = struct.pack('<III', 0x46546C67, 2, total)
    return header + c0 + c1


def build_tileset(positions):
    ctr    = positions.mean(axis=0)
    radius = float(np.linalg.norm(positions - ctr, axis=1).max()) * 1.05
    return {
        "asset": {"version": "1.1"},
        "geometricError": radius * 2,
        "root": {
            "geometricError": radius * 2,
            "refine": "ADD",
            "boundingVolume": {
                "sphere": [float(ctr[0]), float(ctr[1]), float(ctr[2]), radius]
            },
            "content": {"uri": "splat.glb"},
        },
    }


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 convert_splat.py <input.splat> <output_dir>")
        sys.exit(1)

    in_path, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)

    positions, scales, colors, rotations = load_splat(in_path)

    print("Building GLB…")
    glb     = build_glb(positions, scales, colors, rotations)
    glb_path = os.path.join(out_dir, 'splat.glb')
    open(glb_path, 'wb').write(glb)
    print(f"  → {glb_path}  ({len(glb):,} bytes)")

    ts      = build_tileset(positions)
    ts_path = os.path.join(out_dir, 'tileset.json')
    json.dump(ts, open(ts_path, 'w'), indent=2)
    print(f"  → {ts_path}")
    print("Done.")


if __name__ == '__main__':
    main()
