#!/bin/bash
# download_samples.sh — Download all open sample datasets for the platform
# Run from /workspace: bash scripts/download_samples.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$SCRIPT_DIR/../data"

echo "=== Point Cloud Platform — Sample Dataset Setup ==="

# Gaussian Splat
echo ""
echo "[1/3] Downloading Gaussian Splat sample (nike.splat)..."
mkdir -p "$DATA_DIR/splats"
if [ ! -f "$DATA_DIR/splats/nike.splat" ]; then
  curl -L "https://huggingface.co/cakewalk/splat-data/resolve/main/nike.splat" \
    -o "$DATA_DIR/splats/nike.splat"
  echo "  -> $DATA_DIR/splats/nike.splat ($(du -sh "$DATA_DIR/splats/nike.splat" | cut -f1))"
else
  echo "  -> already exists, skipping"
fi

# LiDAR sample (Autzen, PDAL test data)
echo ""
echo "[2/3] Downloading LiDAR sample (autzen.laz)..."
mkdir -p "$DATA_DIR/pointclouds/sample-las"
if [ ! -f "$DATA_DIR/pointclouds/sample-las/autzen.laz" ]; then
  curl -L "https://github.com/PDAL/data/raw/master/autzen/autzen.laz" \
    -o "$DATA_DIR/pointclouds/sample-las/autzen.laz"
  echo "  -> autzen.laz ($(du -sh "$DATA_DIR/pointclouds/sample-las/autzen.laz" | cut -f1))"
else
  echo "  -> already exists, skipping"
fi

# Synthetic demo sphere (generated locally)
echo ""
echo "[3/3] Generating synthetic demo point cloud..."
mkdir -p "$DATA_DIR/pointclouds/demo-sphere"
if [ ! -f "$DATA_DIR/pointclouds/demo-sphere/metadata.json" ]; then
  export NVM_DIR="$HOME/.nvm"
  [ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"
  node "$SCRIPT_DIR/generate_demo_pointcloud.js"
else
  echo "  -> already exists, skipping"
fi

echo ""
echo "=== All samples ready. ==="
echo "Start the server: node server.js"
echo "Then open: http://localhost:3000"
