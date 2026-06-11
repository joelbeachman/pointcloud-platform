# Optimization & Maintainability Plan

Goal: make the codebase understandable and maintainable for a new developer —
cleanup for readability, conservative dead-code removal, and documentation
(docstrings, header comments, per-area READMEs). **No behavior changes**: logic,
CLI flags, file paths, and I/O must remain identical.

Working branch: `optimization/cleanup` (never commit to `main`).
Executor: Fable 5 subagents, orchestrated per batch.
Budget constraint: this window + the next 5h window only.

## Rules for every batch
- Preserve behavior exactly. Readability, comments, docs, dead-code removal only.
- Only touch files listed in your batch. Never touch `public/libs/**` (vendored).
- Add module/file header explaining purpose + how it fits the pipeline.
- Add docstrings/comments where intent is non-obvious. Don't over-comment trivia.
- Keep diffs reviewable; avoid gratuitous reformatting churn.

## Batches

### Batch A — Python pipeline  — STATUS: in progress (this window)
Files: scripts/process.py, scripts/generate_3dtiles.py, scripts/export_blender_glb.py,
scripts/convert_splat.py, scripts/extract_e57.py, scripts/backfill_building_phase.py,
scripts/helmert.py, scripts/restore_eggiswil.py
Deliverable: clean + document each; add scripts/README.md describing the pipeline
(inputs → stages → outputs) and how the scripts chain together.

### Batch B — Server + frontend glue — STATUS: in progress (this window)
Files: server.js, scripts/generate_demo_pointcloud.js, public/js/portal.js,
public/css/portal.css, scripts/download_samples.sh, scripts/test.sh,
scripts/regen_northoffset.pl
Deliverable: clean + document; document server.js routes/endpoints and how the
portal front-end talks to it.

### Batch C — Main Cesium viewer — STATUS: pending (next window)
Files: public/viewers/cesium.html
Deliverable: section the large file with clear comment banners, document the
data-loading flow (datasets, camera, building navigation), remove dead code.

### Batch D — Other viewers — STATUS: pending (next window)
Files: public/viewers/{potree18,potreenext,panorama,mobile,splat,compare,pdf,video}.html,
public/index.html
Deliverable: clean + document each viewer's purpose and inputs; add
public/viewers/README.md cataloguing the viewers and when each is used.

## Resume instructions (for the next-window agent)
1. `git checkout optimization/cleanup && git pull` (or fetch the branch).
2. Read this file; do the first batch whose STATUS is `pending`.
3. Use Fable 5 subagents for the editing work.
4. Commit per batch with message `cleanup(<batch>): <summary>`; update STATUS here.
5. When all batches done, open/update a PR from `optimization/cleanup` into `main`.
6. Stop after the next window's budget — do not exceed the 2-window limit.
