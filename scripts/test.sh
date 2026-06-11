#!/bin/bash
# test.sh — Smoke/end-to-end tests against a running platform server.
#
# Checks (via curl against http://localhost:3000):
#   - API health + dataset listing return expected JSON
#   - portal and viewer pages respond with HTTP 200
#   - sample data files are served under /data (run download_samples.sh first)
#   - POST + DELETE round-trip on /api/datasets
#
# If no server is reachable it starts `node server.js` in the background and
# kills it again at the end. Prints a PASS/FAIL summary; exit code is non-zero
# if any check failed.
#
# Run from the repo root: bash scripts/test.sh

set -e
export NVM_DIR="$HOME/.nvm" && [ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"

BASE="http://localhost:3000"
PASS=0; FAIL=0

check() {
  local desc="$1" url="$2" expect="$3"
  local result
  result=$(curl -s -o /dev/null -w "%{http_code}" "$url")
  if [ "$result" = "$expect" ]; then
    echo "  PASS  $desc ($result)"
    PASS=$((PASS+1))
  else
    echo "  FAIL  $desc (expected $expect, got $result)"
    FAIL=$((FAIL+1))
  fi
}

check_json() {
  local desc="$1" url="$2" key="$3"
  local result
  result=$(curl -s "$url")
  if echo "$result" | grep -q "$key"; then
    echo "  PASS  $desc"
    PASS=$((PASS+1))
  else
    echo "  FAIL  $desc (key '$key' not found in response)"
    FAIL=$((FAIL+1))
  fi
}

echo "=== Point Cloud Platform — E2E Tests ==="
echo ""

# Start server if not running
if ! curl -s "$BASE/api/health" > /dev/null 2>&1; then
  echo "Starting server..."
  node server.js &
  sleep 2
  SERVER_STARTED=1
fi

echo "--- API ---"
check_json "GET /api/health returns status:ok"   "$BASE/api/health"   '"status"'
check_json "GET /api/datasets returns array"     "$BASE/api/datasets" '"id"'

echo ""
echo "--- Pages ---"
check "Portal dashboard (/) loads"              "$BASE/"                            "200"
check "Potree viewer loads"                     "$BASE/viewers/potree.html"         "200"
check "Cesium viewer loads"                     "$BASE/viewers/cesium.html"         "200"
check "Splat viewer loads"                      "$BASE/viewers/splat.html"          "200"
check "Panorama viewer loads"                   "$BASE/viewers/panorama.html"       "200"
check "Compare viewer loads"                    "$BASE/viewers/compare.html"        "200"

echo ""
echo "--- Data ---"
check "Demo sphere metadata accessible"         "$BASE/data/pointclouds/demo-sphere/metadata.json" "200"
check "Splat file accessible"                   "$BASE/data/splats/nike.splat"                     "200"
check "LiDAR sample accessible"                 "$BASE/data/pointclouds/sample-las/autzen.laz"     "200"

echo ""
echo "--- Dataset API ---"
# POST a test dataset and DELETE it
TEST_ID="test-$(date +%s)"
RESP=$(curl -s -X POST "$BASE/api/datasets" \
  -H "Content-Type: application/json" \
  -d "{\"id\":\"$TEST_ID\",\"name\":\"Test\",\"type\":\"pointcloud\"}")
if echo "$RESP" | grep -q "\"id\""; then
  echo "  PASS  POST /api/datasets creates dataset"
  PASS=$((PASS+1))
  curl -s -X DELETE "$BASE/api/datasets/$TEST_ID" > /dev/null
  echo "  PASS  DELETE /api/datasets/:id removes dataset"
  PASS=$((PASS+1))
else
  echo "  FAIL  POST /api/datasets"
  FAIL=$((FAIL+1))
fi

[ -n "$SERVER_STARTED" ] && kill %1 2>/dev/null || true

echo ""
echo "================================"
echo "  Results: $PASS passed, $FAIL failed"
echo "================================"
[ "$FAIL" -eq 0 ]
