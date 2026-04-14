FROM node:20-slim

# ── Python processing pipeline ────────────────────────────────────────────────
# Required for scripts/process.py (point cloud / mesh / splat → 3D Tiles)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-dev \
    gcc g++ \
    && rm -rf /var/lib/apt/lists/*

# laspy[lazrs]  — LAS / LAZ point clouds
# pye57         — E57 laser scans
# plyfile       — PLY point clouds and 3DGS PLY
# trimesh[easy] — OBJ / STL / GLB mesh loading + GLB export
# numpy         — array processing (shared across all pipeline scripts)
RUN pip3 install --break-system-packages \
    numpy \
    "laspy[lazrs]" \
    pye57 \
    plyfile \
    "trimesh[easy]"

WORKDIR /app

# Install dependencies first (layer-cached until package.json changes)
COPY package*.json ./
RUN npm ci --production

# Copy app code (not data — that comes from a volume at runtime)
COPY server.js ./
COPY public ./public
COPY scripts ./scripts

EXPOSE 3000

CMD ["node", "server.js"]
