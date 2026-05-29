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

- [ ] Load all Tragwerk element layers → confirm per-element colors appear
- [ ] Confirm legend shows bottom-left
- [ ] **Improve realism of load colors** (see below)
- [ ] Screenshot / screen-record for presentation

### Realistic load coloring (optional improvement)
Reihe 00–05 are bays of a roof truss. Realistic load distribution:
- Ridge elements (Kehlbälken) carry bending → highest stress → red
- Outer bays (Reihe_00, Reihe_05) carry more of the total roof load → orange
- Middle bays (Reihe_02, Reihe_03) share load with neighbours → yellow/green
- Inner tie beams → lower stress → blue
- [ ] Update `TRAGWERK_COLORS` in `cesium.html` with revised color mapping
- [ ] Re-test in viewer

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

## Open questions to address at meeting

- What does "Datensätze" mean to them? Clarify scope (includes per-building models, photogrammetric meshes, etc.)
- How to integrate videos, text, other images — Potree alone won't cover these
- Do they have real structural load data from an engineer for UC3?
