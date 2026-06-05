#!/usr/bin/env python3
"""Backfill derived fields on datasets.json so the demo is fully reproducible.

Run order:
    1. python3 scripts/generate_3dtiles.py     (wipes & re-writes gesamtmodell_* entries)
    2. python3 scripts/backfill_building_phase.py   (re-applies all derived fields)

Idempotent. Authoritative for: building, buildingName, phase, phaseLabel, isGroupMaster.
Also patches a few hand-known mappings (point clouds → building, mislabeled 752 exports).
"""

import json
import re
from pathlib import Path

DATASETS = Path(__file__).resolve().parent.parent / "data" / "datasets.json"

# Group prefixes that ARE collections of buildings (not a single building).
# For these, the leaf `name` is itself the building number.
COLLECTION_GROUPS = {"Mit_Nummer", "Ohne_Nummer"}

# Groups that are neither a single building nor a building collection.
META_GROUPS = {"Tragwerk", "Gesamtmodell", "Eingang NW"}

# Datasets whose `building` cannot be derived from group/name (point clouds, docs, videos
# that the export script doesn't know about). Maps dataset id → building number.
EXPLICIT_BUILDINGS = {
    "haus-eggiwil":        "351",
    "haus-eggiwil-potree": "351",
    # PDF + video entries already carry `building` in datasets.json — listed here for clarity.
    "doc-351-bauernhaus-eggiwil": "351",
    "doc-752-stallscheune-meggen": "752",
    "vid-351-drone-yk0sxdykx9w":   "351",
}

# Human-readable names per building number.
BUILDING_NAMES = {
    "351": "Bauernhaus Eggiwil",
    "752": "Stallscheune Meggen",
}

# Manual relabels for known-broken Blender exports.
# Each entry: dataset id → {field: value, ...} to overwrite after the derived pass.
# After fixing the underlying export, delete the entry from this dict.
#
# (Empty now: the 752 export was fixed by the parent-disambiguating
# export_blender_glb.py change. Add new entries here as needed.)
MANUAL_RELABELS = {}


def building_from_group(group: str) -> str | None:
    if not group:
        return None
    if group in META_GROUPS or group in COLLECTION_GROUPS:
        return None
    m = re.search(r"(?:^|_)(\d{3})$", group)
    if m:
        return m.group(1)
    if re.fullmatch(r"\d{3}", group):
        return group
    return None


def is_group_master(name: str) -> bool:
    return "alle Phasen" in (name or "")


def main():
    with DATASETS.open() as f:
        datasets = json.load(f)

    changed = 0
    for ds in datasets:
        original = dict(ds)
        group = ds.get("group")
        name  = ds.get("name", "")

        # --- 1. Derived `building` ---------------------------------------
        if ds["id"] in EXPLICIT_BUILDINGS:
            ds["building"] = EXPLICIT_BUILDINGS[ds["id"]]
        elif group in COLLECTION_GROUPS:
            if re.fullmatch(r"\d{3,4}[a-z]?", name):
                ds["building"] = name
            else:
                ds["building"] = None
                ds["isCollectionMaster"] = True
        else:
            ds["building"] = building_from_group(group)

        # --- 2. Derived phase / master flags -----------------------------
        if is_group_master(name):
            ds["isGroupMaster"] = True
            ds["phase"] = 0
            ds["phaseLabel"] = "Alle Phasen"
        elif ds.get("building"):
            m = re.search(r"(\d+)\.\s*Bauphase", name)
            if m:
                ds["phase"] = int(m.group(1))
                ds["phaseLabel"] = f"{m.group(1)}. Bauphase"
            elif name and not re.fullmatch(r"\d{3,4}[a-z]?", name):
                ds["phase"] = None
                ds["phaseLabel"] = name

        # --- 3. Propagate buildingName ----------------------------------
        b = ds.get("building")
        if b and b in BUILDING_NAMES:
            ds["buildingName"] = BUILDING_NAMES[b]

        # --- 4. Manual relabels for known-broken exports ----------------
        if ds["id"] in MANUAL_RELABELS:
            ds.update(MANUAL_RELABELS[ds["id"]])

        if ds != original:
            changed += 1

    with DATASETS.open("w") as f:
        json.dump(datasets, f, indent=2, ensure_ascii=False)

    print(f"Updated {changed} of {len(datasets)} datasets")
    buildings = sorted({d["building"] for d in datasets if d.get("building")})
    print(f"Buildings detected: {len(buildings)}")
    masters = [d["name"] for d in datasets if d.get("isGroupMaster")]
    print(f"Group masters: {len(masters)}")
    named = [d for d in datasets if d.get("buildingName")]
    print(f"Datasets with buildingName: {len(named)}")


if __name__ == "__main__":
    main()
