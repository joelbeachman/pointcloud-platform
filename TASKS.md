# Autonomous Task Queue

This file is read and updated by scheduled agents. Each agent picks the next PENDING task,
marks it IN_PROGRESS, completes it, marks it DONE, and commits.

## Status codes: PENDING | IN_PROGRESS | DONE | FAILED | SKIPPED

---

## Day 1 Tasks

- [PENDING] TASK-001: Install npm dependencies (express, cors, multer)
- [PENDING] TASK-002: Download and register open LAS dataset (USGS 3DEP small tile, ~20MB)
- [PENDING] TASK-003: Install PotreeConverter or use pre-converted sample — register in datasets.json
- [PENDING] TASK-004: Download sample Gaussian splat (.splat) from open repository
- [PENDING] TASK-005: Test that server starts and all 4 viewer pages load without JS errors
- [PENDING] TASK-006: Add .gitignore and make first commit + push to GitHub

## Day 2 Tasks

- [PENDING] TASK-007: Download open E57 sample file, extract panoramic images using Python (pye57)
- [PENDING] TASK-008: Register E57 dataset with extracted panoramas in datasets.json
- [PENDING] TASK-009: Set up Python script scripts/extract_e57.py for E57 panorama extraction
- [PENDING] TASK-010: Add aerial photogrammetry demo dataset (convert to 3D Tiles or use Cesium Ion sample)
- [PENDING] TASK-011: Implement scan position markers in Potree viewer (link to panoramas)
- [PENDING] TASK-012: Add viewer comparison page (side-by-side Potree + Cesium)

## Day 3 Tasks

- [PENDING] TASK-013: Add dataset type filtering and search to the portal dashboard
- [PENDING] TASK-014: Add metadata overlay to each viewer (dataset info panel)
- [PENDING] TASK-015: Write scripts/download_samples.sh to reproduce full dataset setup
- [PENDING] TASK-016: Add basic end-to-end test (fetch /api/health, /api/datasets, check viewer pages return 200)
- [PENDING] TASK-017: Write SETUP.md — how to run the platform, add data, use each viewer
- [PENDING] TASK-018: Final cleanup, tag v0.1.0 release on GitHub

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
