#!/usr/bin/env python3
"""Convert a .splat file to a CesiumJS-compatible 3D Tiles directory.

Produces a GLB tile using the KHR_gaussian_splatting glTF extension with
SPZ compression (KHR_gaussian_splatting_compression_spz_2) loadable by
CesiumJS 1.135+.

Usage:
    python3 scripts/convert_splat.py <input.splat> <output_dir>

Pipeline position: optional post-step after process.py has produced a .splat
(from a 3DGS PLY) in data/splats/. Writes <output_dir>/splat.glb and
<output_dir>/tileset.json; the result is loaded as a 3D Tiles layer in the
Cesium viewer instead of the antimatter15-style splat renderer.
"""
import sys, os, json, struct, math, gzip
import numpy as np

STRIDE = 32  # bytes per splat: 3×f32 pos | 3×f32 log-scale | RGBA u8 | WXYZ quat u8
SH_C0  = 0.28209479177387814  # 1 / (2*sqrt(pi)) — SH degree-0 basis constant
# SPZ stores colours as quantized SH DC coefficients scaled by 0.15 — this must
# match the constant in the SPZ reference codec (and Cesium's SPZ decoder),
# otherwise colours come out washed out or oversaturated.
COLOR_SCALE = 0.15


def load_splat(path):
    """Parse a .splat file into (positions, log_scales, rgba_colors, rotations_wxyz)."""
    raw = np.frombuffer(open(path, 'rb').read(), dtype=np.uint8)
    n   = len(raw) // STRIDE
    raw = raw[: n * STRIDE].reshape(n, STRIDE)

    # Positions: bytes 0-11, three float32
    positions = raw[:, 0:12].view(np.float32).reshape(n, 3).copy()

    # Log-scales: bytes 12-23, stored as ln(scale) — keep as log for SPZ encoder
    log_scales = raw[:, 12:24].view(np.float32).reshape(n, 3).copy()

    # Colors: bytes 24-27, RGBA uint8
    colors = raw[:, 24:28].copy()

    # Rotations: bytes 28-31, packed uint8 WXYZ → normalised float
    rb  = raw[:, 28:32].astype(np.float64)
    rf  = (rb - 128.0) / 128.0
    nrm = np.linalg.norm(rf, axis=1, keepdims=True)
    nrm = np.where(nrm < 1e-10, 1.0, nrm)
    rf /= nrm
    # Keep in WXYZ order (native .splat order)
    rotations_wxyz = rf.astype(np.float32)

    print(f"Loaded {n:,} splats from {os.path.basename(path)}")
    return positions, log_scales, colors, rotations_wxyz


def encode_spz(positions, log_scales, colors, rotations_wxyz):
    """Encode Gaussian splat data to SPZ binary format (then gzip-compressed).

    SPZ v2 format:
      Header (16 bytes): magic, version, numPoints, shDegree, fractionalBits, flags, reserved
      Data (gzip-compressed): positions | alphas | colors | scales | rotations
    """
    n = len(positions)

    # Choose fractionalBits so max abs position fits in 24-bit signed int
    max_abs = float(np.abs(positions).max()) if n > 0 else 1.0
    if max_abs < 1e-6:
        max_abs = 1.0
    max_fb = max(0, int(math.floor(23 - math.log2(max_abs))))
    fractional_bits = min(12, max_fb)
    scale_factor    = 1 << fractional_bits

    # ── Header ───────────────────────────────────────────────────────────────
    MAGIC   = 0x5053474e  # "NGSP" LE
    VERSION = 2
    header  = struct.pack('<IIIBBB B',
        MAGIC, VERSION, n,
        0,               # shDegree = 0 (no SH, DC colours only)
        fractional_bits,
        0,               # flags
        0,               # reserved
    )

    # ── Positions (3 bytes × 3 components per splat, signed 24-bit LE) ───────
    fixed = np.round(positions * scale_factor).astype(np.int32)
    fixed = np.clip(fixed, -0x800000, 0x7FFFFF)
    # To unsigned 24-bit: negative values need two's complement
    fixed_u = np.where(fixed < 0, fixed + 0x1000000, fixed).astype(np.uint32)
    # Pack 3 bytes LE per value: shape (n, 3, 3)
    b0 = (fixed_u        & 0xFF).astype(np.uint8)
    b1 = ((fixed_u >> 8) & 0xFF).astype(np.uint8)
    b2 = ((fixed_u >> 16) & 0xFF).astype(np.uint8)
    pos_bytes = np.stack([b0, b1, b2], axis=2).reshape(n * 9)
    pos_data  = pos_bytes.tobytes()

    # ── Alphas (1 byte per splat, direct copy from .splat RGBA[3]) ───────────
    # .splat stores sigmoid(opacity_logit)*255, SPZ stores the same value.
    alpha_data = colors[:, 3].tobytes()

    # ── Colors: visible uint8 → SH DC coefficient → SPZ byte ─────────────────
    # visible = f_dc * SH_C0 + 0.5  →  f_dc = (visible/255 - 0.5) / SH_C0
    # spz_byte = round(f_dc * COLOR_SCALE * 255 + 0.5 * 255)
    rgb   = colors[:, :3].astype(np.float32) / 255.0
    f_dc  = (rgb - 0.5) / SH_C0
    c_enc = np.clip(np.round(f_dc * COLOR_SCALE * 255.0 + 127.5), 0, 255).astype(np.uint8)
    color_data = c_enc.tobytes()

    # ── Scales (1 byte × 3 per splat, log-encoded) ────────────────────────────
    # packed = clamp(round((log_scale + 10.0) * 16.0), 0, 255)
    s_enc = np.clip(np.round((log_scales + 10.0) * 16.0), 0, 255).astype(np.uint8)
    scale_data = s_enc.tobytes()

    # ── Rotations v2 (3 bytes × 3 xyz components per splat) ───────────────────
    # Canonical form: ensure w >= 0 (negate all components if w < 0)
    W    = rotations_wxyz[:, 0]
    sign = np.where(W < 0, -1.0, 1.0).astype(np.float32)
    rots = (rotations_wxyz.T * sign).T  # shape (n,4)
    xyz  = rots[:, 1:4]                 # take X, Y, Z; W is implicit
    # Encode: byte = round((xyz + 1.0) * 127.5) → maps [-1,1] to [0,255]
    r_enc = np.clip(np.round((xyz + 1.0) * 127.5), 0, 255).astype(np.uint8)
    rot_data = r_enc.tobytes()

    # ── Concatenate raw, then gzip ────────────────────────────────────────────
    raw = header + pos_data + alpha_data + color_data + scale_data + rot_data
    return gzip.compress(raw, compresslevel=6)


def build_glb(spz_bytes, n):
    """Wrap SPZ bytes in a GLB with KHR_gaussian_splatting_compression_spz_2."""
    n_spz = len(spz_bytes)
    pad   = (4 - n_spz % 4) % 4
    bin_chunk_data = spz_bytes + b'\x00' * pad

    gltf = {
        "asset": {"version": "2.0", "generator": "convert_splat.py (SPZ)"},
        "extensionsUsed":     ["KHR_gaussian_splatting",
                               "KHR_gaussian_splatting_compression_spz_2"],
        "extensionsRequired": ["KHR_gaussian_splatting",
                               "KHR_gaussian_splatting_compression_spz_2"],
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{
            "primitives": [{
                "mode": 0,
                "attributes": {
                    "POSITION":                        0,
                    "KHR_gaussian_splatting:SCALE":    1,
                    "KHR_gaussian_splatting:ROTATION": 2,
                    "COLOR_0":                         3,
                },
                "extensions": {
                    "KHR_gaussian_splatting": {
                        "extensions": {
                            "KHR_gaussian_splatting_compression_spz_2": {}
                        }
                    }
                }
            }]
        }],
        # All accessors point at bufferView 0 (the SPZ blob).
        # Cesium reads accessor.count for the point budget; types match
        # what processSpz() expects per semantic.
        "accessors": [
            {"bufferView": 0, "byteOffset": 0, "componentType": 5126, "count": n, "type": "VEC3"},   # POSITION
            {"bufferView": 0, "byteOffset": 0, "componentType": 5126, "count": n, "type": "VEC3"},   # SCALE
            {"bufferView": 0, "byteOffset": 0, "componentType": 5126, "count": n, "type": "VEC4"},   # ROTATION
            {"bufferView": 0, "byteOffset": 0, "componentType": 5121, "count": n, "type": "VEC4", "normalized": True},  # COLOR_0
        ],
        # Buffer view 0 = the SPZ gzip data (Cesium hardcodes bufferViewId=0)
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": n_spz},
        ],
        "buffers": [{"byteLength": n_spz}],
    }

    json_bytes = json.dumps(gltf, separators=(',', ':')).encode()
    json_pad   = (4 - len(json_bytes) % 4) % 4
    json_chunk = json_bytes + b' ' * json_pad

    c0    = struct.pack('<II', len(json_chunk), 0x4E4F534A) + json_chunk
    c1    = struct.pack('<II', len(bin_chunk_data), 0x004E4942) + bin_chunk_data
    total = 12 + len(c0) + len(c1)
    hdr   = struct.pack('<III', 0x46546C67, 2, total)
    return hdr + c0 + c1


def build_tileset(positions):
    """Build a single-tile tileset.json declaring the gaussian-splatting extensions."""
    ctr    = positions.mean(axis=0)
    radius = float(np.linalg.norm(positions - ctr, axis=1).max()) * 1.05
    return {
        "asset": {"version": "1.1"},
        "extensionsUsed": ["3DTILES_content_gltf"],
        "extensions": {
            "3DTILES_content_gltf": {
                "extensionsUsed": [
                    "KHR_gaussian_splatting",
                    "KHR_gaussian_splatting_compression_spz_2",
                ],
                "extensionsRequired": [
                    "KHR_gaussian_splatting",
                    "KHR_gaussian_splatting_compression_spz_2",
                ],
            },
        },
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

    positions, log_scales, colors, rotations_wxyz = load_splat(in_path)

    print("Encoding SPZ…")
    spz_bytes = encode_spz(positions, log_scales, colors, rotations_wxyz)
    print(f"  SPZ payload: {len(spz_bytes):,} bytes (gzip-compressed)")

    print("Building GLB…")
    glb      = build_glb(spz_bytes, len(positions))
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
