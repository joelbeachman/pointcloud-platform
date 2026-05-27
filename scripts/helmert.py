#!/usr/bin/env python3
"""
3D Helmert transformation (Horn/Kabsch SVD approach).
Reads JSON from stdin: {src, dst_lv95, useScale}
  src      – list of [x, y, z] in local model space
  dst_lv95 – list of [E, N, H] in LV95 (target frame)
  useScale – bool; if true computes 7-param (scale), otherwise 6-param (rigid)
Writes JSON to stdout: {R, s, t, residuals, rms, verification}
  R    – 3×3 rotation matrix as list of rows R[row][col]
  s    – scale factor (1.0 when useScale is false)
  t    – translation [t0, t1, t2] in LV95
  residuals – per-point residual in metres
  rms  – root-mean-square residual
  verification – per-point debug dict {target, computed, delta}
"""
import sys, json
import numpy as np

def solve(src, dst, use_scale):
    src = np.array(src, dtype=float)   # N×3  local space
    dst = np.array(dst, dtype=float)   # N×3  LV95
    n   = len(src)

    # Centroids
    p_bar = src.mean(axis=0)
    q_bar = dst.mean(axis=0)

    # Mean-centred points
    pc = src - p_bar
    qc = dst - q_bar

    # Cross-covariance  H = pc^T · qc   (3×3)
    H = pc.T @ qc

    # SVD:  H = U · diag(S) · Vt
    U, S, Vt = np.linalg.svd(H)
    V = Vt.T

    # Reflection correction (ensures det(R) = +1)
    d = np.linalg.det(V @ U.T)
    D = np.diag([1.0, 1.0, float(np.sign(d)) if d != 0 else 1.0])

    # Rotation matrix
    R = V @ D @ U.T          # 3×3, row-major: R[row, col]

    # Scale (7-param) or rigid (6-param)
    src_var = float(np.sum(pc ** 2))
    if use_scale and src_var > 0:
        s = float(np.sum(S) / src_var)
    else:
        s = 1.0

    # Translation:  dst = s·R·src + t  =>  t = q_bar - s·R·p_bar
    t = q_bar - s * (R @ p_bar)

    # Per-point residuals
    residuals = []
    for i in range(n):
        diff = dst[i] - (s * (R @ src[i]) + t)
        residuals.append(float(np.linalg.norm(diff)))

    rms = float(np.sqrt(np.mean(np.array(residuals) ** 2)))

    # Verification (debug info)
    verification = []
    for i in range(n):
        computed = s * (R @ src[i]) + t
        verification.append({
            'target':   dst[i].tolist(),
            'computed': computed.tolist(),
            'delta':    (computed - dst[i]).tolist(),
        })

    return {
        'R':            R.tolist(),
        's':            s,
        't':            t.tolist(),
        'residuals':    residuals,
        'rms':          rms,
        'verification': verification,
    }

if __name__ == '__main__':
    try:
        data     = json.loads(sys.stdin.read())
        src      = data['src']
        dst      = data['dst_lv95']
        use_scale = bool(data.get('useScale', False))

        if len(src) < 3 or len(src) != len(dst):
            raise ValueError(f'Need at least 3 matching pairs, got src={len(src)} dst={len(dst)}')

        result = solve(src, dst, use_scale)
        print(json.dumps(result))

    except Exception as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        sys.exit(1)
