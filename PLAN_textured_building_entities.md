# Plan: Textured Per-Building Entities with Navigable Layer Browser

**Goal:** Re-export the Gesamtmodell with real textures, and give each building a
navigable entity in the Cesium viewer sidebar — fly-to, phase switching, sub-part
grouping — without rewriting the core viewer architecture.

---

## Current State (reference)

| What | Where |
|---|---|
| 132 GLBs (no textures) | `data/blender/export/buildings/<name>.glb` |
| LOD 0/1/2 GLBs (no textures) | `data/cesium/gesamtmodell/buildings/<name>_lod{0,1,2}.glb` |
| Terrain | `data/cesium/gesamtmodell/terrain_lod1.glb` |
| Tileset | `data/cesium/gesamtmodell/tileset.json` |
| Export script | `scripts/export_blender_glb.py` |
| Tiles script | `scripts/generate_3dtiles.py` |

### Known building groupings (from manifest.json analysis)

- **Mit_Nummer** (~94 leaf collections): numbered buildings, e.g. `111`, `311`, `1311`
- **Ohne_Nummer** (11 leaf collections): named outbuildings, e.g. `141_Ost_Nebenhaus`
- **511 sub-parts** (8 collections): `Reihe_00`–`Reihe_05`, `Kehlbälken`, `OG_Wohnbereich`, `Heuboden`, `Treppengeländer`, `Übergang` — all belong to building 511
- **Multi-phase buildings** (same numeric ID, different year prefix or Bauphase suffix):
  - 351: `2022_351`, `2025_351`
  - 751: `2022_751`, `2025_751`
  - 821: `2022_821`, `2025_821`
  - 851: `2022_851`, `1._Bauphase_851` … `7._Bauphase_851`

---

## Phase 1 — Textured Blender Export

### Problem
`export_blender_glb.py` currently:
1. Purges ALL images from `bpy.data.images` to free ~3 GB RAM before export
2. Uses `export_materials='PLACEHOLDER'` (colours only, no textures)

### Memory budget

**Run on a machine with ample RAM (16 GB+) — no memory workarounds needed.**

On the server (7.7 GB container) we had to purge all textures to fit within budget.
On a capable workstation the .blend loads fully, all textures stay resident, and we
can export at full resolution without any downscaling or purging.

### Changes to `scripts/export_blender_glb.py`

**A. Remove the image purge block entirely**

Delete (or comment out) the section that currently reads:
```python
print('[setup] Purging image data to free RAM...')
for img in list(bpy.data.images):
    bpy.data.images.remove(img, do_unlink=True)
bpy.ops.outliner.orphans_purge(...)
```

All packed images stay in memory so the exporter can embed them.

**B. Change export call to full texture export**

```python
# was: export_materials='PLACEHOLDER'
try:
    bpy.ops.export_scene.gltf(**kwargs, export_materials='EXPORT',
                               export_image_format='JPEG', export_jpeg_quality=85)
except TypeError:
    bpy.ops.export_scene.gltf(**kwargs)
```

- `export_image_format='JPEG'` + quality 85 gives good quality at reasonable file sizes.
- If you want lossless (larger files), use `export_image_format='PNG'` instead.
- `export_jpeg_quality` may not exist in older Blender versions — the try/except handles that.
- The glTF exporter automatically includes only textures referenced by the exported
  objects' materials, so each building GLB contains only its own textures.

**C. Per-export orphan purge stays** (already in place — frees mesh data, not images)

### Expected output sizes
- Per-building GLB with full-res JPEG textures: ~2–50 MB each
- Total `data/blender/export/buildings/`: estimate 500 MB – 2 GB depending on texture density
- After gltfpack LOD generation + KTX2 compression: roughly 30–50% of source size

### Test run recommendation
Before the full run, test on one texture-heavy building (e.g. `1._Bauphase`) by
adding an early exit after the first successful export, and verify the GLB contains
embedded textures (check file size > ~5 MB and open in a glTF viewer).

---

## Phase 2 — Compressed 3D Tiles Generation

### Changes to `scripts/generate_3dtiles.py`

**A. Add KTX2 texture compression to gltfpack**

```python
def run_gltfpack(src_glb, dst_glb, simplify_ratio=None):
    cmd = ['gltfpack', '-i', src_glb, '-o', dst_glb, '-kn']
    if simplify_ratio is not None:
        cmd += ['-si', str(simplify_ratio)]
    # KTX2/ETC1S texture compression — ~8× smaller than JPEG in GLB
    # Only works if gltfpack was built with basisu support
    cmd += ['-tc']
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # Fallback: retry without -tc (basisu may not be available)
        cmd_notc = [x for x in cmd if x != '-tc']
        result = subprocess.run(cmd_notc, capture_output=True, text=True)
        if result.returncode != 0:
            print(f'  [gltfpack error] {result.stderr.strip()}')
            return False
    return True
```

**B. Register `extensionsUsed` for KTX2** — handled automatically by gltfpack; no manual JSON edits needed.

---

## Phase 3 — Building Index JSON

### New script: `scripts/generate_building_index.py`

Reads `manifest.json` and produces `data/cesium/gesamtmodell/buildings_index.json`.

#### Output schema

```jsonc
{
  "groups": [
    {
      "id": "mit_nummer",
      "label": "Mit Nummer",
      "buildings": [
        {
          "name": "111",
          "label": "Gebäude 111",
          "file": "buildings/111.glb",
          "bbox_min": [...],
          "bbox_max": [...],
          "center": [...],
          "size": 18.5,
          "vertex_count": 4200
        },
        ...
      ]
    },
    {
      "id": "ohne_nummer",
      "label": "Ohne Nummer",
      "buildings": [...]
    },
    {
      "id": "phases",
      "label": "Bauphasen",
      "subgroups": [
        {
          "id": "851",
          "label": "Gebäude 851 — Bauphasen",
          "phases": [
            { "name": "2022_851", "label": "Stand 2022", ... },
            { "name": "1._Bauphase_851", "label": "1. Bauphase", ... },
            ...
          ]
        }
      ]
    },
    {
      "id": "511_parts",
      "label": "Gebäude 511 — Teile",
      "buildings": [
        { "name": "Reihe_00", "label": "Reihe 00", ... },
        ...
      ]
    }
  ]
}
```

#### Grouping logic

```python
PHASE_PATTERNS = [
    (r'^(\d{4})_(\d+)$',          lambda m: ('phase', m.group(2), m.group(1))),  # 2022_351
    (r'^(\d+)\. Bauphase (\d+)$', lambda m: ('bauphase', m.group(2), m.group(1)+'._Bauphase')),
    (r'^1\._Bauphase$',           lambda m: ('standalone', None, '1._Bauphase')),
]

BUILDING_511_PARTS = {'Übergang','Reihe_00','Reihe_01','Reihe_02','Reihe_03',
                      'Reihe_04','Reihe_05','Kehlbälken','Treppengeländer',
                      'OG_Wohnbereich','Heuboden'}

OHNE_NUMMER_PATTERNS = [r'^\d+_\w+$']  # 141_Ost_Nebenhaus, 311_West_Nebenhaus, etc.
```

#### Auto-generation hook

Add to `generate_3dtiles.py` at the end (after `register_dataset`):

```python
import subprocess
subprocess.run(['python3', 'scripts/generate_building_index.py'], check=False)
```

---

## Phase 4 — Building Browser UI in `cesium.html`

### Design

The layers panel gains a collapsible **building browser** that appears under any
loaded gesamtmodell layer. It mirrors the Blender collection hierarchy.

```
▼ Gesamtmodell Eggiwil                [👁] [✕]
  ▼ Mit Nummer  (94)
      111  Gebäude 111           [→] 
      131  Gebäude 131           [→]
      ...
  ▼ Ohne Nummer  (11)
      141_Ost_Nebenhaus          [→]
      ...
  ▼ Bauphasen
    ▼ Gebäude 851
        2022_851  Stand 2022     [→] [●]
        1. Bauphase              [→] [●]
        2. Bauphase              [→] [●]
        ...
  ▼ Gebäude 511 — Teile
      Reihe_00                   [→]
      ...
```

Buttons per building:
- `[→]` — fly to bounding box (`viewer.camera.flyToBoundingSphere`)
- `[●]` — for phase buildings only: toggle which phase is highlighted (visual indicator only;
  actual phase switching = separate layer load, see Phase 5)

### Implementation

**A. Data loading**

```javascript
let buildingIndex = null;

async function loadBuildingIndex(dsId) {
  // Only for gesamtmodell
  if (dsId !== 'gesamtmodell') return;
  const resp = await fetch('/data/cesium/gesamtmodell/buildings_index.json');
  buildingIndex = await resp.json();
  renderBuildingBrowser();
}
```

Call `loadBuildingIndex(ds.id)` at the end of `addLayer()` when the tileset loads.

**B. Bounding box fly-to**

Convert bbox (Blender local space) to ECEF using the tileset's root transform:

```javascript
function flyToBuilding(b) {
  // b.center is in Blender local Z-up space: [East, North, Up] offsets
  // Convert to ECEF via the tile root transform (same as getRefMatrix but for position)
  const localPos = new Cesium.Cartesian3(b.center[0], b.center[1], b.center[2]);
  const ecefPos  = localToEcef(localPos);
  const radius   = b.size / 2 + 20;
  viewer.camera.flyToBoundingSphere(new Cesium.BoundingSphere(ecefPos, radius), {
    duration: 1.2,
    offset: new Cesium.HeadingPitchRange(0, Cesium.Math.toRadians(-30), radius * 3),
  });
}
```

Note: `localToEcef` uses `getRefMatrix()` which for gesamtmodell returns
`eastNorthUpToFixedFrame(boundingSphere.center)`. This is the geographic ENU frame,
NOT the model's yawed frame. The building centers in the manifest are in Blender
local Z-up space (East, North, Up) which matches the ENU measurement frame.

Actually — **this needs care**: the manifest `center` values are Blender-space (no yaw applied).
The tileset root transform includes a 2.2° yaw. The fly-to should use the actual ECEF
position of the building, which means applying the FULL tileset root transform (with yaw),
not just the ENU frame.

**Correct fly-to approach**: load the tileset root transform from `tileset.json` once at startup
and use it directly for building-center → ECEF mapping.

```javascript
let gesamtmodellTransform = null;  // Cesium.Matrix4, loaded from tileset.json

async function loadGesamtmodellTransform() {
  const resp = await fetch('/data/cesium/gesamtmodell/tileset.json');
  const ts   = await resp.json();
  const t    = ts.root.transform;
  if (t) gesamtmodellTransform = Cesium.Matrix4.fromArray(t);
}

function buildingCenterToEcef(center) {
  // center = [East, North, Up] in Blender local Z-up after Y-up correction
  // tileset root transform maps this to ECEF
  if (!gesamtmodellTransform) return null;
  // CesiumJS applies Y-up→Z-up correction internally, so local frame is already Z-up:
  //   local X = East = center[0]
  //   local Y = North = center[1]
  //   local Z = Up = center[2]
  return Cesium.Matrix4.multiplyByPoint(
    gesamtmodellTransform,
    new Cesium.Cartesian3(center[0], center[1], center[2]),
    new Cesium.Cartesian3()
  );
}
```

**C. HTML structure** (insert into the layer list item for gesamtmodell)

```html
<div class="building-browser" id="bb-${layer.id}">
  <!-- generated by renderBuildingBrowser() -->
</div>
```

CSS: collapsible groups, compact rows, same dark-theme as the rest of the panel.

---

## Phase 5 — Phase Switching (Optional — next session)

For multi-phase buildings (351, 751, 821, 851), it should be possible to show only
one phase at a time.

**Approach**: load the per-building LOD0 GLB as a separate inline tileset, with a
minimal single-tile `tileset.json` generated client-side.

```javascript
async function loadBuildingAsSeparateLayer(building) {
  const glbUrl = `/data/cesium/gesamtmodell/${building.file
    .replace('buildings/', 'buildings/').replace('.glb', '_lod0.glb')}`;
  const tilesetJson = {
    asset: { version: '1.0' },
    geometricError: 100,
    root: {
      transform: Array.from(gesamtmodellTransform),  // same as parent
      boundingVolume: { box: boxBoundingVolume(building.bbox_min, building.bbox_max) },
      geometricError: 0,
      refine: 'REPLACE',
      content: { uri: glbUrl }
    }
  };
  // Serve inline via Blob URL
  const blob = new Blob([JSON.stringify(tilesetJson)], { type: 'application/json' });
  const url  = URL.createObjectURL(blob);
  const ts   = await Cesium.Cesium3DTileset.fromUrl(url);
  viewer.scene.primitives.add(ts);
  // ... register as a layer, add remove button
}
```

This avoids any server-side changes and works with the existing GLB files.

---

## Execution Order

```
Session N (this plan written)  ✓

Session N+1:
  □ Phase 1: update export_blender_glb.py (texture downscale + EXPORT materials)
  □ Run Blender export on server (test with 1._Bauphase first, then full run)
  □ Phase 2: update generate_3dtiles.py (-tc flag + fallback)
  □ Run generate_3dtiles.py → new textured tileset

Session N+2:
  □ Phase 3: write generate_building_index.py
  □ Run it → buildings_index.json
  □ Phase 4A: loadBuildingIndex() + loadGesamtmodellTransform() in cesium.html
  □ Phase 4B: flyToBuilding() helper
  □ Phase 4C: renderBuildingBrowser() UI with collapsible groups

Session N+3:
  □ Phase 5: phase switching via inline per-building tilesets
  □ Styling polish: highlight selected building bbox in the 3D scene
  □ Update PROGRESS.md, commit
```

---

## Open Questions (resolve before Session N+1)

1. **Which textures exist?** Run a quick Blender audit script to list all images, their
   sizes, and which collections use them. Helps estimate post-downscale RAM budget.
   ```
   blender --background data/blender/Gesamtsmodell_V3.blend \
           --python scripts/audit_textures.py
   ```

2. **gltfpack basisu support?** Check: `gltfpack --help | grep '\-tc'`. If absent,
   skip `-tc` and rely on JPEG compression from Blender export.

3. **Manifest center vs. transform**: confirm that `manifest.json` `center` values
   are in raw Blender local space (no Y-up, no yaw applied) before trusting
   `buildingCenterToEcef()`.

4. **Building 511 grouping**: the 8 sub-parts (`Reihe_*`, `Kehlbälken`, etc.) are
   separate GLBs in the tileset. Decide whether they should appear as one "511" entry
   (fly-to the union bbox) or individually.
```
