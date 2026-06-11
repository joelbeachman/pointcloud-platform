#!/usr/bin/env python3
"""
Blender export script — Gesamtsmodell_V3.blend → per-building GLBs.

Run headless:
  blender --background /path/to/Gesamtsmodell_V3.blend --python export_blender_glb.py

Or paste into Blender's Scripting tab and run (set OUTPUT_DIR first).

Output: data/blender/export/
  manifest.json            ← tile list for generate_3dtiles.py
  buildings/<name>.glb     ← one GLB per leaf collection in Häuser
  terrain.glb              ← all Terrain collection objects combined

Pipeline position: first stage of the Gesamtmodell chain. Follow up with
  python3 scripts/generate_3dtiles.py          (GLBs → georeferenced 3D Tiles)
  python3 scripts/backfill_building_phase.py   (derive building/phase fields)
"""

import bpy
import json
import os
import re
import sys

# ── config ────────────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__ if '__file__' in dir() else sys.argv[0]))
OUTPUT_DIR  = os.path.normpath(os.path.join(SCRIPT_DIR, '..', 'data', 'blender', 'export'))

EXPORT_COLLECTIONS  = ['Häuser']   # per-building GLBs from these
TERRAIN_COLLECTIONS = ['Terrain']  # combined terrain GLB from these
SKIP_COLLECTIONS    = ['Terrain_Substitute', 'Misc']  # too heavy / point clouds

# ── CLI args (parsed after the `--` separator that Blender passes through) ───
# Usage:
#   blender --background file.blend --python scripts/export_blender_glb.py -- --building 752
#
# --building NNN    Only export top-level child collections under EXPORT_COLLECTIONS
#                   whose name contains NNN. Other buildings are skipped entirely
#                   (no risk of GLB filenames colliding with them).
# --phase N         Only export leaf/phase-container collections named "N. Bauphase".
#                   Other collections (other Bauphasen, placeholders like "2022_752")
#                   are skipped. Combine with --building for "phase 1 of building 752".
# --skip-terrain    Don't re-export terrain.glb (saves time on focused runs).
def _parse_cli():
    if '--' not in sys.argv:
        return {}
    argv = sys.argv[sys.argv.index('--') + 1:]
    out = {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--building' and i + 1 < len(argv):
            out['building'] = argv[i + 1]; i += 2
        elif a == '--phase' and i + 1 < len(argv):
            out['phase'] = argv[i + 1]; i += 2
        elif a == '--skip-terrain':
            out['skip_terrain'] = True; i += 1
        else:
            print(f'[cli] unknown arg ignored: {a!r}'); i += 1
    return out

CLI = _parse_cli()
BUILDING_FILTER = CLI.get('building')   # e.g. "752", or None for all buildings
PHASE_FILTER    = CLI.get('phase')      # e.g. "1", or None for all phases
SKIP_TERRAIN    = CLI.get('skip_terrain', False)
if BUILDING_FILTER:
    print(f'[cli] --building active: only exporting buildings matching {BUILDING_FILTER!r}')
if PHASE_FILTER:
    print(f'[cli] --phase active: only exporting Bauphase {PHASE_FILTER!r} collections')
if SKIP_TERRAIN:
    print(f'[cli] --skip-terrain: skipping terrain.glb')

# Set to True when running on a machine with limited RAM (≤ 8 GB).
# Purges all packed textures before export so materials will have no textures.
# Set to False (default) on a workstation with ample RAM to export full textures.
LOW_MEMORY_MODE = False

os.makedirs(os.path.join(OUTPUT_DIR, 'buildings'), exist_ok=True)
# ──────────────────────────────────────────────────────────────────────────────

# Ensure the glTF exporter addon is active (required in some Blender setups)
try:
    bpy.ops.preferences.addon_enable(module='io_scene_gltf2')
except Exception:
    pass  # already enabled or unavailable

if LOW_MEMORY_MODE:
    # Purge all packed images to free RAM. Textures will not appear in exported GLBs.
    print('[setup] LOW_MEMORY_MODE: purging image data...')
    for img in list(bpy.data.images):
        bpy.data.images.remove(img, do_unlink=True)
    bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=False, do_recursive=True)
    print('[setup] Images purged. Proceeding to export without textures.')
else:
    print('[setup] Full-memory mode: textures will be embedded in exported GLBs.')

from mathutils import Vector


def world_bbox(obj):
    """Return (bbox_min, bbox_max) in world space for obj and all mesh descendants."""
    pts = []
    stack = [obj]
    while stack:
        o = stack.pop()
        if o.type == 'MESH':
            for corner in o.bound_box:
                pts.append(o.matrix_world @ Vector(corner))
        stack.extend(o.children)
    if not pts:
        return None, None
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    zs = [p.z for p in pts]
    return [min(xs), min(ys), min(zs)], [max(xs), max(ys), max(zs)]


def vertex_count(obj):
    """Total vertex count for obj and all mesh descendants."""
    total = 0
    stack = [obj]
    while stack:
        o = stack.pop()
        if o.type == 'MESH' and o.data:
            total += len(o.data.vertices)
        stack.extend(o.children)
    return total


def deselect_all():
    bpy.ops.object.select_all(action='DESELECT')


# Object name prefixes/substrings to exclude from building exports.
# DGM = Digitales Geländemodell (terrain mesh embedded in some building collections).
EXCLUDE_NAME_PREFIXES = ('DGM',)

def select_objects(objects):
    """Select a list of objects; set the first as active.

    Skips:
    - Zero-scale objects (hidden in Blender; export as singular matrices that
      crash CesiumJS when inverting the model matrix).
    - Render-disabled objects (hide_viewport=True 🖥 monitor icon — explicitly
      excluded from renders / dependency graph).
    - Objects whose names start with EXCLUDE_NAME_PREFIXES (e.g. DGM terrain
      meshes that are embedded inside building collections by mistake).

    Does NOT skip eye-icon-hidden objects (hide_get()) — that flag is purely a
    viewport convenience the artist uses while modeling, and silently dropping
    such collections caused 752 to lose its 2. Bauphase export.
    """
    deselect_all()
    active = None
    for obj in objects:
        if obj.type in ('MESH', 'EMPTY', 'CURVE', 'SURFACE'):
            # Skip zero-scale
            s = obj.scale
            if s.x == 0 or s.y == 0 or s.z == 0:
                continue
            # Skip render-disabled (monitor icon) — these are intentionally excluded.
            if obj.hide_viewport:
                continue
            # Skip excluded name prefixes (DGM terrain meshes, etc.)
            if any(obj.name.startswith(p) for p in EXCLUDE_NAME_PREFIXES):
                continue
            obj.select_set(True)
            if active is None:
                active = obj
    if active:
        bpy.context.view_layer.objects.active = active
    return active is not None


def export_glb(filepath, objects):
    """Export a list of objects to a GLB file."""
    if not select_objects(objects):
        print(f'  [skip] no exportable objects for {os.path.basename(filepath)}')
        return False
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    # Common kwargs for all Blender versions.
    # export_apply=False: skip modifier evaluation (avoids OOM from Boolean modifiers).
    # The base mesh geometry is exported as-is; Boolean cuts are a visual detail
    # not needed for spatial/measurement use in the platform.
    kwargs = dict(
        filepath=filepath,
        use_selection=True,
        export_format='GLB',
        export_apply=False,
    )
    if LOW_MEMORY_MODE:
        # No textures available (purged at startup) — export colours only.
        try:
            bpy.ops.export_scene.gltf(**kwargs, export_materials='PLACEHOLDER')
        except TypeError:
            bpy.ops.export_scene.gltf(**kwargs)
    else:
        # Full export with textures.  Try progressively simpler calls so that
        # unknown/renamed parameters in newer Blender versions don't break the export.
        exported = False
        for attempt_kwargs in [
            # 1. JPEG at quality 85 — best size/quality (Blender ≤ 4.x param name)
            dict(export_materials='EXPORT', export_image_format='JPEG', export_jpeg_quality=85),
            # 2. Without quality setting (param may not exist in Blender 5.x)
            dict(export_materials='EXPORT', export_image_format='JPEG'),
            # 3. Without image format override — let Blender choose (PNG default)
            dict(export_materials='EXPORT'),
            # 4. Last resort: colours only (no textures)
            dict(export_materials='PLACEHOLDER'),
        ]:
            try:
                bpy.ops.export_scene.gltf(**kwargs, **attempt_kwargs)
                exported = True
                used = list(attempt_kwargs.keys())
                print(f'  [export] succeeded with {used}')
                break
            except (TypeError, RuntimeError) as e:
                print(f'  [export] attempt {attempt_kwargs} failed: {e!r}, trying next...')
        if not exported:
            bpy.ops.export_scene.gltf(**kwargs)  # bare fallback

    return os.path.exists(filepath)


def all_objects_in_collection(col):
    """Return all objects directly in col (not recursive into child collections)."""
    return list(col.objects)


def all_objects_recursive(col):
    """Return all objects in col and all descendant collections."""
    objs = list(col.objects)
    for child in col.children:
        objs.extend(all_objects_recursive(child))
    return objs


def is_leaf_collection(col):
    """A leaf collection has no child collections (objects only)."""
    return len(col.children) == 0


# Match collection names like "1. Bauphase", "2. Bauphase 752", "10. Bauphase".
_PHASE_NAME_RE = re.compile(r'^\s*(\d+)\.\s*Bauphase\b', re.IGNORECASE)

def phase_number_of(col_name):
    """Return the Bauphase number from a collection name, or None if it's not a phase."""
    m = _PHASE_NAME_RE.match(col_name)
    return m.group(1) if m else None

def passes_phase_filter(col):
    """When --phase N is active, only collections named 'N. Bauphase' pass."""
    if not PHASE_FILTER:
        return True
    n = phase_number_of(col.name)
    return n == PHASE_FILTER

def is_phase_container(col):
    """A non-leaf collection that semantically represents one Bauphase.

    When the artist organizes a phase as a parent collection holding several
    sub-collections (e.g. work-in-progress drafts named "test" / "new"),
    we treat the parent as a single export rather than recursing — otherwise
    we end up with anonymous "test.glb" / "new.glb" files instead of a clean
    "N._Bauphase_<building>.glb".
    """
    return not is_leaf_collection(col) and _PHASE_NAME_RE.match(col.name) is not None


def export_collection_recursive(col, manifest_buildings, rel_path_prefix='buildings', parent_name=None):
    """
    Recursively export leaf collections as individual GLBs.
    Leaf = a collection with no child collections.
    Exception: a non-leaf collection whose name matches "N. Bauphase" is treated
    as a single export (its sub-collection geometry is merged into one GLB).
    parent_name: immediate parent collection name (used to group Bauphase variants
                 of the same building into separate tilesets in generate_3dtiles.py).
    """
    # When --phase N is active, skip leaves/phase-containers that aren't the matching Bauphase.
    # (We still recurse through non-leaf non-phase collections to find matching phases below.)
    if (is_leaf_collection(col) or is_phase_container(col)) and not passes_phase_filter(col):
        print(f'  [phase-filter] skipping {col.name!r} (does not match --phase {PHASE_FILTER})')
        return

    if is_leaf_collection(col) or is_phase_container(col):
        # Export this collection as one GLB.
        # Disambiguate the filename by appending the parent's building number
        # when the collection name doesn't already contain it. This prevents
        # generic-named collections like "1. Bauphase" from overwriting each
        # other across different buildings.
        safe_name = col.name.replace('/', '_').replace(' ', '_').replace('\\', '_')
        if parent_name:
            m = re.search(r'(\d{3,4}[a-z]?)$', parent_name)
            bldg_num = m.group(1) if m else None
            if bldg_num and bldg_num not in safe_name:
                safe_name = f'{safe_name}_{bldg_num}'
        glb_rel   = f'{rel_path_prefix}/{safe_name}.glb'
        glb_abs   = os.path.join(OUTPUT_DIR, glb_rel)

        objects   = all_objects_recursive(col)
        mesh_objs = [o for o in objects if o.type == 'MESH']
        if not mesh_objs:
            print(f'  [skip] no meshes in {col.name}')
            return

        # Bounding box from root objects (no parent in this collection)
        root_objs = [o for o in mesh_objs if o.parent is None or o.parent not in objects]
        bmin_all, bmax_all = [], []
        for o in (root_objs or mesh_objs):
            bmin, bmax = world_bbox(o)
            if bmin:
                bmin_all.append(bmin)
                bmax_all.append(bmax)

        if not bmin_all:
            print(f'  [skip] empty bbox for {col.name}')
            return

        bbox_min = [min(b[i] for b in bmin_all) for i in range(3)]
        bbox_max = [max(b[i] for b in bmax_all) for i in range(3)]
        center   = [(bbox_min[i] + bbox_max[i]) / 2 for i in range(3)]
        size     = max(bbox_max[i] - bbox_min[i] for i in range(3))
        vcount   = sum(vertex_count(o) for o in mesh_objs)

        print(f'  → exporting "{col.name}"  (parent={parent_name!r}, {vcount:,} verts, size={size:.1f}m)')
        success = export_glb(glb_abs, objects)
        # Free orphaned data blocks between exports to reclaim memory
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=False, do_recursive=True)
        if success:
            manifest_buildings.append({
                'name':       col.name,
                'collection': col.name,
                'parent':     parent_name,   # None for standalone buildings
                'file':       glb_rel,
                'bbox_min':   bbox_min,
                'bbox_max':   bbox_max,
                'center':     center,
                'size':       round(size, 3),
                'vertex_count': vcount,
            })
        else:
            msg = (f'export skipped/failed for leaf collection {col.name!r} '
                   f'(parent={parent_name!r}) — {vcount} mesh verts in source, '
                   f'but no objects passed the export filter '
                   f'(check hide_viewport / DGM prefix / zero-scale).')
            print(f'  [WARNING] {msg}')
            # Bubble it up so it lands in manifest["errors"] and is visible after the run.
            global _PENDING_WARNINGS
            try:
                _PENDING_WARNINGS.append(msg)
            except NameError:
                _PENDING_WARNINGS = [msg]
    else:
        # Recurse into child collections; this collection becomes the parent for its children
        print(f'  [{col.name}] → {len(col.children)} sub-collections')
        for child in col.children:
            export_collection_recursive(child, manifest_buildings, rel_path_prefix,
                                        parent_name=col.name)


# ── main ──────────────────────────────────────────────────────────────────────

manifest = {
    'buildings': [],
    'terrain': None,
    'errors': [],
    # Mark focused runs so generate_3dtiles.py knows not to rebuild the main
    # tileset.json (which would drop all the buildings not included in this run).
    'focused':           bool(BUILDING_FILTER or PHASE_FILTER),
    'building_filter':   BUILDING_FILTER,
    'phase_filter':      PHASE_FILTER,
    'terrain_exported':  not (SKIP_TERRAIN or BUILDING_FILTER),
}

# 1. Export buildings (per leaf-collection)
print('\n=== Exporting buildings ===')
for col_name in EXPORT_COLLECTIONS:
    if col_name not in bpy.data.collections:
        msg = f'Collection "{col_name}" not found'
        print(f'WARNING: {msg}')
        manifest['errors'].append(msg)
        continue
    col = bpy.data.collections[col_name]
    print(f'\n[{col_name}]  sub-collections: {[c.name for c in col.children]}')
    children = list(col.children) if col.children else [col]

    if BUILDING_FILTER:
        # The Häuser tree may be organised by category first ("Mit_Nummer",
        # "Ohne_Nummer", ...) and only then by building. Find every collection
        # (anywhere in the descent) whose name contains the filter, but stop
        # the search once a match is found on a branch — we want the building
        # collection, not deeper phase sub-collections.
        def find_matching(c, path_parents):
            if BUILDING_FILTER in c.name:
                return [(c, path_parents)]
            hits = []
            for ch in c.children:
                hits.extend(find_matching(ch, path_parents + [c.name]))
            return hits

        matches = []
        for ch in children:
            matches.extend(find_matching(ch, []))

        if not matches:
            msg = (f'--building {BUILDING_FILTER!r}: no collection found anywhere '
                   f'under "{col_name}". Top-level children were: '
                   f'{[c.name for c in children]}')
            print(f'  [WARNING] {msg}')
            manifest['errors'].append(msg)
            continue
        print(f'  [filter] matched {len(matches)} collection(s):')
        for c, parents in matches:
            chain = ' → '.join(parents + [c.name]) if parents else c.name
            print(f'           {chain}')
        # Export from each match, preserving the in-Blender parent name so phase
        # children get the right parent in the manifest.
        for c, parents in matches:
            initial_parent = parents[-1] if parents else None
            export_collection_recursive(c, manifest['buildings'], parent_name=initial_parent)
    else:
        for child in children:
            export_collection_recursive(child, manifest['buildings'], parent_name=None)

# 2. Export terrain (all Terrain objects as one combined GLB)
if SKIP_TERRAIN or BUILDING_FILTER:
    # On a focused per-building run, terrain rarely needs to change.
    # Re-run without --building (or without --skip-terrain) to refresh it.
    if BUILDING_FILTER and not SKIP_TERRAIN:
        print('\n=== Skipping terrain (focused --building run) ===')
    else:
        print('\n=== Skipping terrain (--skip-terrain) ===')
    terrain_objects = []
else:
    print('\n=== Exporting terrain ===')
    terrain_objects = []
    for col_name in TERRAIN_COLLECTIONS:
        if col_name in bpy.data.collections:
            terrain_objects.extend(all_objects_recursive(bpy.data.collections[col_name]))

if terrain_objects:
    terrain_glb = os.path.join(OUTPUT_DIR, 'terrain.glb')
    print(f'  → {len(terrain_objects)} objects total')
    success = export_glb(terrain_glb, terrain_objects)
    if success:
        # Compute overall terrain bbox
        mesh_t = [o for o in terrain_objects if o.type == 'MESH']
        tbmin_all, tbmax_all = [], []
        for o in mesh_t:
            bmin, bmax = world_bbox(o)
            if bmin:
                tbmin_all.append(bmin)
                tbmax_all.append(bmax)
        if tbmin_all:
            tbbox_min = [min(b[i] for b in tbmin_all) for i in range(3)]
            tbbox_max = [max(b[i] for b in tbmax_all) for i in range(3)]
            manifest['terrain'] = {
                'file':     'terrain.glb',
                'bbox_min': tbbox_min,
                'bbox_max': tbbox_max,
                'center':   [(tbbox_min[i] + tbbox_max[i]) / 2 for i in range(3)],
            }
        print(f'  → terrain.glb written')
else:
    print('  [skip] no terrain objects found')

# 3. Save manifest
try:
    manifest['errors'].extend(_PENDING_WARNINGS)
except NameError:
    pass
manifest_path = os.path.join(OUTPUT_DIR, 'manifest.json')
with open(manifest_path, 'w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)

print(f'\n=== Done ===')
print(f'  {len(manifest["buildings"])} building GLBs exported')
print(f'  manifest → {manifest_path}')
if manifest['errors']:
    print(f'\n  !! {len(manifest["errors"])} WARNING(S) — check manifest.json["errors"]:')
    for e in manifest['errors']:
        print(f'     - {e}')
