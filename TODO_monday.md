# Monday Demo — Task List

## 0 · Pipeline (you, ~15 min)
- [ ] `git pull && python3 scripts/generate_3dtiles.py`  
      (generates per-leaf tilesets + corrected bounding volumes)
- [ ] Copy `data/cesium/gesamtmodell/` to server
- [ ] Reload viewer — verify buildings appear at correct height and fly-to works

---

## UC1 · Two building phases of building 851

- [ ] Open "Add Layer" → section `2025_851` → load `1. Bauphase 851` → confirm camera flies to building
- [ ] Load `2. Bauphase 851` alongside → toggle visibility → confirm no z-fighting
- [ ] Load `851 (alle Phasen)` → confirm all 7 phases visible together
- [ ] Screenshot / screen-record for presentation

---

## UC2 · Building in previous environment

- [ ] Load `Mit_Nummer (alle Phasen)` → confirms village context visible
- [ ] Load `1. Bauphase 851` → building appears within village at its Phase 1 state
- [ ] Fly to building 851 from outside to show it in context
- [ ] Screenshot / screen-record for presentation

---

## UC3 · Load distribution (Tragwerk)

- [x] Per-element colors working (CustomShader approach, Cesium 1.140)
- [x] Legend shows bottom-left
- [x] Realistic color mapping: Kehlbälken=red, outer bays=orange, transitional=yellow, middle=green
- [ ] Screenshot / screen-record for presentation

⚠ Known: Reihe GLBs include full building context (Blender export issue) — accepted for Monday

---

## Presentation prep (you)

- [ ] Slide 1: Platform overview — what it is, who it's for
- [ ] Slide 2: UC1 — Bauphase comparison  
      Data: Blender Bauphase collections  
      Pipeline: Blender → GLB export → 3D Tiles → CesiumJS  
      Demo: toggle Phase 1 ↔ Phase 7 of building 851  
- [ ] Slide 3: UC2 — Building in previous environment  
      Data: same model, village context layer  
      Pipeline: same + layer toggle  
      Demo: Phase 1 of building 851 within village  
- [ ] Slide 4: UC3 — Load distribution  
      Data: Tragwerk collection from Blender  
      Pipeline: Blender → per-element GLBs → color-coded tiles  
      Demo: load the Tragwerk layers, show legend  
- [ ] Slide 5: Open questions / next steps (other data types: video, text, images)

---

## Known issues — Blender export

- **Gebäude 752**: both exported tilesets were mislabeled as "alle Phasen". `tileset_2025_752.json` (refs `1._Bauphase.glb`) is a single phase; `tileset_752.json` (refs `2022_752.glb`) is the combined state. Relabeled in the dataset registry as **1. Bauphase 752** and **2. Bauphase 752** respectively (no master) so the demo can toggle between them. The underlying Blender export needs a re-run with proper per-building Bauphase collections; if the visual order is reversed at the demo, swap `phase` 1↔2 on the two entries in `datasets.json`.
- **Gebäude 851**: also has two masters (`851 (alle Phasen)` + `2025_851 (alle Phasen)`). Less broken than 752 since both contain valid geometry, but the duplication is noisy. Worth cleaning up post-demo.

## Open questions to address at meeting

- What does "Datensätze" mean to them? Clarify scope (includes per-building models, photogrammetric meshes, etc.)
- ~~How to integrate videos, text, other images — Potree alone won't cover these~~ → UC4 demo
- Do they have real structural load data from an engineer for UC3?

---

## UC4 · Dokumente & Medien pro Gebäude (NEW)

- [x] Backfill `building`/`phase`/`isGroupMaster` on `datasets.json` (94 buildings, 16 group masters)
- [x] Add `document` type + PDF entry for Gebäude 351 (`Bauernhaus Eggiwil BE`)
- [x] `/viewers/pdf.html` standalone document viewer
- [x] **Dokumente & Medien** section in Cesium right sidebar — contextual to currently active building
- [x] Slide-out PDF overlay — opens left of the right sidebar, 3D viewer stays interactive
- [x] Video PIP (player wired; no source yet — drop an mp4 in `data/videos/` to demo)
- [x] Layer list groups phases by building (collapsible, master checkbox, indeterminate state)

## Navigation — one entry per house

- [x] Eggiwil LiDAR (`haus-eggiwil` + potree variant) linked to building 351
- [x] `buildingName: "Bauernhaus Eggiwil"` propagated to all building-351 datasets
- [x] Portal renders one card per house, sorted by number; "Andere Datensätze" section below
- [x] House card → `/viewers/cesium.html?building=NNN` loads ALL datasets for that house at once
  - Point cloud (source=lidar/photogrammetry) auto-toggled ON
  - All other layers loaded but toggled OFF
  - Fallback: if no point cloud, the "alle Phasen" master is toggled ON
- [x] Default Cesium landing (no URL params) → Gesamtmodell
- [x] `activeBuilding` pinned when chosen via URL → docs panel stays on the right building even when toggling layers

**Demo flow:**
1. Open portal — house cards, "351 — Bauernhaus Eggiwil" prominent
2. Click "Im 3D-Viewer öffnen" on 351 → 4 cesium layers loaded under one group header, only the point cloud visible, camera flies in, PDF appears in the right sidebar
3. Toggle individual Bauphasen on/off against the point cloud — compare model vs. scan
4. Click the PDF → it slides out next to the still-interactive 3D scene

