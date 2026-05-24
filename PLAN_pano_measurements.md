# Plan: Measurement Tools in the Standalone Panorama Viewer

> **Status:** Planning  
> **Scope:** `public/viewers/panorama.html` (standalone viewer)  
> **Note on the DouglasTecnologia plugin:** It is MIT-licensed but entirely
> embedded in MapStore2's Redux/React plugin system and cannot be extracted.
> Its core idea — spherical geometry between clicked panorama points — is
> reproduced here from scratch without that dependency.

---

## Context and Goals

The Cesium overlay already has panorama measurement working: a click in the
Pannellum div casts a ray into the loaded 3D Tiles via `pickFromRay`, and the
result is fed to the existing measurement tools. That approach requires an
active Cesium scene and a loaded tileset.

The **standalone panorama viewer** (`panorama.html`) does not have a Cesium
scene, but it does have something equally powerful: every scan position is
stored as an absolute LV95 coordinate `(x, y, z)` with a calibrated
`northOffset`. This means every click in the panorama corresponds to a known
ray in 3D world space, originating from a precisely surveyed point.

Three distinct measurement methods are achievable without a 3D model, in
order of increasing complexity and accuracy:

| # | Method | What you need | Accuracy |
|---|--------|---------------|----------|
| A | **Angular** — great-circle angle between two click directions | Single panorama | No real-world distance |
| B | **Floor-plane intersection** — ray × horizontal plane at assumed height | Single panorama + scan z | Good for horizontal layout |
| C | **Two-view triangulation** — mark same point in two panoramas | Two panoramas | Highest; no model needed |

All three produce measurements in metres (LV95 space) or degrees and are
displayed in the same right-side panel used by the Cesium viewer.

---

## Phase 1 — Toolbar UI + Angular Distance (quick win)

### 1.1 Add measurement toolbar to `panorama.html`

Add a right-side panel (matching the Cesium viewer's style) with four tool
buttons and a measurements list:

```
[ ∠ Angle ]   [ ↔ Horizontal ]   [ ↕ Vertical ]   [ ✕ Clear ]
────────────────────────────────────────────────
Measurements
  · 12.4 m  Horizontal (floor plane)
  · 34.7°   Angular
```

The toolbar sits in a `#right-panel` div (`position: absolute; right: 0;
top: 100px; bottom: 0; width: 220px`) mirroring Cesium's sidebar CSS. The
viewer div shrinks to `right: 220px` when the panel is open.

### 1.2 Pannellum click → yaw/pitch

Attach a `mousedown` listener to the Pannellum container. Convert the click
pixel to (yaw, pitch) using the same perspective-projection formula already
used in the Cesium overlay:

```javascript
const tanH2 = Math.tan(pannellumViewer.getHfov() * Math.PI / 360);
const half  = rect.width / 2;
const yaw   = pannellumViewer.getYaw()   + Math.atan(dx * tanH2 / half) * 180 / Math.PI;
const pitch = pannellumViewer.getPitch() - Math.atan(dy * tanH2 / half) * 180 / Math.PI;
```

### 1.3 Angular tool

Compute the great-circle angle between two clicked directions on the unit
sphere. This answers "what is the angular separation between two features
visible from this scan position?" — useful for estimating apparent size or
confirming a compass bearing.

```javascript
function angularDistance(yaw1, pitch1, yaw2, pitch2) {
  // Convert to unit vectors on the sphere
  const toRad = d => d * Math.PI / 180;
  const v1 = sphereDir(toRad(yaw1), toRad(pitch1));
  const v2 = sphereDir(toRad(yaw2), toRad(pitch2));
  const dot = v1[0]*v2[0] + v1[1]*v2[1] + v1[2]*v2[2];
  return Math.acos(Math.max(-1, Math.min(1, dot))) * 180 / Math.PI;
}

function sphereDir(yawRad, pitchRad) {
  // ENU convention: north = Y, east = X, up = Z
  const bearing = yawRad + (currentNorthOffset * Math.PI / 180);
  return [
    Math.sin(bearing) * Math.cos(pitchRad),  // east
    Math.cos(bearing) * Math.cos(pitchRad),  // north
    Math.sin(pitchRad)                        // up
  ];
}
```

Display: `34.7° angular` in the measurements panel.

---

## Phase 2 — Floor-Plane Intersection (single panorama, real distances)

This is the most immediately useful method for an open-air museum: the user
clicks on two points that are approximately at the same height (e.g. two
corners of a building at ground level), and the viewer returns the horizontal
distance between them in metres.

### 2.1 Ray construction

For each click (yaw, pitch), construct a ray in LV95 space:

```javascript
function clickRayLV95(yaw, pitch, scan) {
  const compass  = (yaw + scan.northOffset) * Math.PI / 180;
  const pitchRad = pitch * Math.PI / 180;
  // Direction in LV95 (east = +x, north = +y, up = +z)
  const dir = {
    x: Math.sin(compass) * Math.cos(pitchRad),
    y: Math.cos(compass) * Math.cos(pitchRad),
    z: Math.sin(pitchRad),
  };
  // Origin = scan position in LV95
  return { origin: { x: scan.x, y: scan.y, z: scan.z }, dir };
}
```

### 2.2 Plane intersection

Intersect the ray with a horizontal plane at `z = planeZ`. The plane height
defaults to the scan's own z (ground level at the scanner), but the user can
adjust it with a small numeric input (±5 m range, 0.1 m steps).

```javascript
function rayPlaneZ(ray, planeZ) {
  const t = (planeZ - ray.origin.z) / ray.dir.z;
  if (t <= 0) return null;  // plane behind or at scanner
  return {
    x: ray.origin.x + t * ray.dir.x,
    y: ray.origin.y + t * ray.dir.y,
    z: planeZ,
  };
}
```

### 2.3 Measurements from floor intersections

**Horizontal distance** between two floor-plane intersection points:
```
d = sqrt((x2-x1)² + (y2-y1)²)  [metres, LV95]
```

**Vertical distance** when two points are clicked with *different* assumed
plane heights (user changes the height slider between clicks).

**Area** — polygon of ≥3 floor-plane points, shoelace formula in LV95.

### 2.4 Measurement markers in the panorama

Draw markers at the clicked hotspot positions in Pannellum (using Pannellum's
`addHotSpot` API after load, or by re-creating the viewer with extra hotspots
in the `hotSpots` array). Each point gets a numbered dot SVG; connecting lines
are drawn in a `<canvas>` overlay that is sized and positioned to match the
Pannellum viewport, updated each animation frame using `getYaw/getPitch/getHfov`
to project the LV95 point back to screen coordinates.

---

## Phase 3 — Two-View Triangulation (highest accuracy, no model)

When two scan positions look at the same real-world point, we can recover its
3D LV95 coordinates by finding the closest approach of the two rays.

### 3.1 When to trigger

Add a **"Mark in this view"** button that appears in the toolbar when a
measurement is "awaiting a second view" — after the user has clicked a point
in scan A and wants to refine it by clicking the same point in scan B.

The UI flow:
1. User activates Triangulate tool, clicks point P in scan A → ray_A stored,
   P marked with a yellow hotspot.
2. User navigates to scan B (hotspot or prev/next). The yellow "awaiting"
   marker is preserved across navigations.
3. User clicks same real-world point in scan B → ray_B constructed.
4. Nearest-point between ray_A and ray_B gives the 3D LV95 position.
5. The measurement is committed with a residual (distance between the two
   rays at closest approach) shown as a quality indicator.

### 3.2 Ray–ray nearest point

```javascript
function nearestPointBetweenRays(o1, d1, o2, d2) {
  // Solves: minimize |o1 + t*d1 - (o2 + s*d2)|²
  const w  = { x: o1.x-o2.x, y: o1.y-o2.y, z: o1.z-o2.z };
  const a  = dot(d1, d1), b = dot(d1, d2), c = dot(d2, d2);
  const d  = dot(d1, w),  e = dot(d2, w);
  const D  = a*c - b*b;
  if (Math.abs(D) < 1e-8) return null;  // rays parallel
  const t  = (b*e - c*d) / D;
  const s  = (a*e - b*d) / D;
  const p1 = { x: o1.x+t*d1.x, y: o1.y+t*d1.y, z: o1.z+t*d1.z };
  const p2 = { x: o2.x+s*d2.x, y: o2.y+s*d2.y, z: o2.z+s*d2.z };
  const residual = Math.sqrt((p1.x-p2.x)**2 + (p1.y-p2.y)**2 + (p1.z-p2.z)**2);
  const mid = { x:(p1.x+p2.x)/2, y:(p1.y+p2.y)/2, z:(p1.z+p2.z)/2 };
  return { point: mid, residual };
}
```

A residual under ~0.3 m is good; over 1 m suggests the user clicked different
features. The residual is shown in the measurement panel entry.

Once the 3D LV95 point is known, all measurement types (distance between two
triangulated points, height difference, area of a polygon of triangulated
points) follow from simple LV95 arithmetic — the same formulas used in the
Cesium viewer.

---

## Phase 4 (Optional) — Server-side Point Cloud Ray-Cast

For datasets where a 3D Tiles tileset is available (haus-eggiwil), add a
server endpoint:

```
POST /api/datasets/:id/raycast
Body: { x, y, z, dx, dy, dz }   (ray origin + direction in LV95)
Returns: { hit: { x, y, z } } or { hit: null }
```

The server uses a pre-built spatial index (numpy KDTree or similar) of the
point cloud to find the nearest point along the ray. The panorama viewer can
call this endpoint to get precise intersection with the actual scanned
geometry instead of a floor-plane approximation.

This is the same thing the Cesium overlay achieves via `pickFromRay`, but
available to the standalone viewer without Cesium loaded. It requires a
server-side Python dependency (numpy, scipy) and an indexed cache per dataset.

---

## Implementation Order

```
Phase 1  (1–2 h)  Toolbar UI + Angular tool
Phase 2  (2–3 h)  Floor-plane tool — Horizontal, Vertical, Area + canvas overlay markers
Phase 3  (3–4 h)  Two-view triangulation + cross-scan workflow
Phase 4  (4–6 h)  Server-side raycast endpoint (optional, after Phase 3 verified)
```

## Files to Change

| File | Change |
|------|--------|
| `public/viewers/panorama.html` | Add right panel, tool buttons, measurement state, all three measurement engines, canvas overlay for markers |
| `server.js` | Phase 4 only: `POST /api/datasets/:id/raycast` |
| `scripts/process.py` | Phase 4 only: build + cache KDTree index on dataset registration |
| `PROGRESS.md` | Update after each phase |

## What the DouglasTecnologia Plugin Contributes

The plugin is MIT but cannot be used directly (MapStore2/Redux coupling).
Its conceptual contribution to this plan:
- Confirms that spherical-geometry measurements in Pannellum are a solved problem
- The "cross-image calibration" concept maps directly to Phase 3 triangulation
- Export to JSON/CSV is worth adding after Phase 2 (trivial given the LV95 coordinates we already have)
