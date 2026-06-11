# Minimal Mobile Viewer — Plan & Spike Notes

Date: 2026-06-11 · Status: all three demos built in `public/viewers/mobile.html`
— splash routes to `?demo=eggiwil | phases | tragwerk`.

1. **Eggiwil** (`?demo=eggiwil`): model-only building 351; toggle Ballenberg ↔
   Originalstandort (verified: 24.7 km move, correct LV95). Anchored to the point
   cloud's LV95 centroid (read from its tileset.json, no 72 MB load) so it matches
   the desktop position. swisstopo Zeitreise: Karte/Luftbild switch + year slider,
   a green band marking the timeframe the building was/is at the shown location,
   old-site default = relocation year 1988. Imagery re-requested once the terrain
   tile queue drains (full-LOD on arrival without a slider touch).
2. **Phases** (`?demo=phases`): Stallscheune Meggen (752); switch 1. ↔ 2. Bauphase.
3. **Tragwerk** (`?demo=tragwerk`): per-element load colours (CustomShader).
   Still the heavy one (175 MB, fake LOD ladder — see F-A/F-B) and the mobile-GPU
   shader risk; fine on WiFi, needs the re-export for a cellular kiosk.

All verified headlessly (syntax, asset paths, endpoints). Still needs a
real-device render pass (touch, terrain, the CustomShader path).

## Goal
A stripped, touch-first Cesium viewer for two kiosk demos, **model-only** (no
point cloud, no tools):
1. **Eggiwil — Standort**: toggle building 351's model between its
   Originalstandort (1684) and Ballenberg, over swisstopo terrain.
2. **Tragwerk — Lastverteilung**: the 7 roof elements coloured by load zone via
   the runtime CustomShader.

## Decision taken: model-only is the default
Confirmed (see "How hard" discussion):
- Drops the 72 MB single-tile `.pnts`; uses the 351 **model** tileset instead.
- The historical toggle still works with no point cloud:
  `propagateHistoricalLV95()` copies `historicalLV95` from `haus-eggiwil` onto
  the model entry (it walks the full catalog, not loaded layers), and
  `buildHistoricalModelMatrix` Case B falls back to the model's own
  `boundingSphere.center` when no cloud anchor exists — self-consistent.
- Whole viewer is GLB-only → every asset has (nominal) LOD + tuned cache.
- Trade-off: clean untextured massing model vs. the dense colour scan.

## Spike: what was built
`public/viewers/mobile.html` (~340 lines, self-contained):
- Same `/cesium-proxy/Cesium.js` boot; swisstopo terrain verbatim.
- Coordinate/matrix helpers copied verbatim from `cesium.html`
  (`lv95ToWgs84`, `isLv95`, `lv95ModelMatrix`, `getHistoricalAnchorEcef`,
  `buildHistoricalModelMatrix`) — **candidates for extraction into a shared
  `/js/lv95.js`** that both viewers import (kills the duplication the thesis
  flags).
- Mobile cache: **256 MB / 64 MB** (desktop uses 4 GB / 2 GB → would OOM mobile
  Safari). `requestRenderMode` on for battery; `resolutionScale` capped on
  hi-DPI.
- Routes: `?demo=eggiwil`, `?demo=tragwerk`, else a 2-button splash.
- Verified server-side: serves 200, `/api/datasets` carries the historical
  field, all 8 tileset paths + GLB content resolve over HTTP.

### To test on a phone
`http://<host>:3000/viewers/mobile.html` → pick a demo (or QR to
`...?demo=eggiwil` / `?demo=tragwerk`).

## ⚠ Findings from the spike (act before the demo)

### F-A — The served LOD ladder is FAKE (blocks Tragwerk on mobile)
All three LODs of every building are **md5-identical copies**, e.g.
`2025_351_lod{0,1,2}.glb` = same hash, 427,278 verts each;
`Kehlbälken_lod{0,1,2}.glb` = 25.0 MB each. Root cause:
`generate_3dtiles.py:271` falls back to `shutil.copy` when `gltfpack` returns
non-zero, and the served tiles were generated that way (likely the `-tc`
KTX2/basisu path failed; gltfpack is installed now). Consequences:
- **No cheap coarse level anywhere.** `skipLevelOfDetail` is moot.
- Eggiwil model demo = a hard **16 MB** download (OK on WiFi/4G).
- Tragwerk demo = **7 × 25 MB = 175 MB**, no lighter option → too heavy for a
  cellular kiosk; risks mobile memory pressure.

### F-B — Re-export alone won't fix the weight; textures dominate
Tested live: `gltfpack -si 0.05` on Kehlbälken only gets **25 → 17 MB** (and
optimise-only ≈ 17.5 MB). So geometry is ~⅓ of the file; the rest is the 2
embedded uncompressed images per element. A real mobile re-export needs
**KTX2 texture compression (`-tc`) + vertex quantization**, which must be made
to actually succeed (the current export silently fell back to copies). This is
the main pipeline task to make Tragwerk mobile-viable.

### F-C — This contradicts the thesis (new review item)
`chapter_implementation.tex` (LOD0/LOD1/LOD2 = 100/30/5%) and
`chapter_evaluation.tex` ("LOD artefacts at LOD2, 5% simplification") describe
an export that the served data does not contain — identical to the M-1
north-offset pattern: pipeline true in principle, served artifacts don't
reflect it. Add to `review_3.txt`.

## Remaining risks (unchanged from original plan)
1. **CustomShader on mobile GPUs** — the spike wires it exactly as desktop;
   still needs a real-device check (thesis's own flagged risk).
2. Coordinate-math drift → solved by the `/js/lv95.js` extraction.

## Next steps (recommended order)
1. Load the spike on one iOS + one Android phone. Verify: (a) Eggiwil toggle +
   terrain, (b) Tragwerk colours render (CustomShader path). Retires risk #1.
2. If Tragwerk is too heavy / crashes: re-export the Tragwerk elements with
   working `-tc` + quantization (F-B), confirm real size drop, re-test.
3. Decide standalone vs. shared-helpers; if keeping `mobile.html`, extract
   `/js/lv95.js` and import from both viewers.
4. Add the F-C discrepancy to `review_3.txt`.
