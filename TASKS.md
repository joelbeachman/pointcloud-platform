# Autonomous Task Queue

This file is read and updated by scheduled agents. Each agent picks the next PENDING task,
marks it IN_PROGRESS, completes it, marks it DONE, and commits.

## Status codes: PENDING | IN_PROGRESS | DONE | FAILED | SKIPPED

---

## Day 1 Tasks

- [DONE] TASK-001: Install npm dependencies (express, cors, multer) — verified 2026-04-07
- [DONE] TASK-002: Download and register open LAS dataset — autzen.laz (PDAL test data, 295KB)
- [DONE] TASK-003: Register demo point cloud in datasets.json — synthetic sphere (50k pts) + autzen
- [DONE] TASK-004: Download sample Gaussian splat — nike.splat (8.3MB, huggingface/cakewalk)
- [DONE] TASK-005: Test that server starts and API endpoints return valid data
- [DONE] TASK-006: .gitignore exists, initial commit pushed to GitHub on 2026-04-02

## Day 2 Tasks

- [DONE] TASK-007: Python3 + pye57 installed; E57 extraction script written (scripts/extract_e57.py)
- [SKIPPED] TASK-008: Register E57 dataset — no sample E57 available for download; script ready for user's own files
- [DONE] TASK-009: scripts/extract_e57.py — extracts panoramas from E57, outputs equirectangular JPEGs + metadata.json
- [SKIPPED] TASK-010: Aerial photogrammetry 3D Tiles — requires Cesium Ion token or external data; Cesium viewer ready for user data
- [SKIPPED] TASK-011: Scan position markers already built into potree.html (loads from dataset.scanPositions)
- [DONE] TASK-012: Viewer comparison page — public/viewers/compare.html with draggable split + layout buttons

## Day 3 Tasks

- [DONE] TASK-013: Dataset search + type filter added to portal dashboard
- [SKIPPED] TASK-014: Metadata overlay already present in each viewer (info panels, dataset name/source)
- [DONE] TASK-015: scripts/download_samples.sh — reproduces full dataset setup from scratch
- [DONE] TASK-016: scripts/test.sh — E2E tests for all API endpoints + viewer pages
- [DONE] TASK-017: SETUP.md — full documentation for running, adding data, each viewer
- [PENDING] TASK-018: Final commit + tag v0.1.0 release on GitHub

---

## Notes for agents

- Work directory: /workspace
- Node: load with `export NVM_DIR="$HOME/.nvm" && source "$NVM_DIR/nvm.sh"`
- Server start: `cd /workspace && node server.js &`
- Git remote: https://joelbeachman:TOKEN@github.com/joelbeachman/pointcloud-platform.git
- Token stored in: /workspace/.env (GITHUB_TOKEN)
- After completing tasks, always: git add, git commit, git push
- If a task fails, mark it FAILED with a note and move to next task
- Update PROGRESS.md with what was done each run
