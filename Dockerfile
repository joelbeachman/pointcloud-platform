FROM node:20-alpine

# ── Python processing pipeline ────────────────────────────────────────────────
# Required for scripts/process.py (point cloud / mesh / splat → 3D Tiles)
# laspy      — LAS point clouds (no LAZ; lazrs needs Rust to compile)
# plyfile    — PLY point clouds and 3DGS PLY
# trimesh    — OBJ / STL / GLB mesh loading + GLB export
# numpy      — array processing
# pye57 (E57) and lazrs (LAZ) are excluded — both require native compilation.
# Install manually inside the container if needed:
#   apk add gcc g++ musl-dev rust cargo python3-dev && pip3 install lazrs pye57
RUN apk add --no-cache python3 py3-pip && \
    pip3 install --break-system-packages \
        numpy \
        laspy \
        plyfile \
        trimesh

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
