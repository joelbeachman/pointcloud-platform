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
"""

import bpy
import json
import os
import sys

# ── config ────────────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__ if '__file__' in dir() else sys.argv[0]))
OUTPUT_DIR  = os.path.normpath(os.path.join(SCRIPT_DIR, '..', 'data', 'blender', 'export'))

EXPORT_COLLECTIONS  = ['Häuser']   # per-building GLBs from these
TERRAIN_COLLECTIONS = ['Terrain']  # combined terrain GLB from these
SKIP_COLLECTIONS    = ['Terrain_Substitute', 'Misc']  # too heavy / point clouds

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
    - Viewport-hidden objects (hide_viewport=True; these are intentionally
      invisible and should not appear in the export).
    - Objects whose names start with EXCLUDE_NAME_PREFIXES (e.g. DGM terrain
      meshes that are embedded inside building collections by mistake).
    """
    deselect_all()
    active = None
    for obj in objects:
        if obj.type in ('MESH', 'EMPTY', 'CURVE', 'SURFACE'):
            # Skip zero-scale
            s = obj.scale
            if s.x == 0 or s.y == 0 or s.z == 0:
                continue
            # Skip viewport-hidden
            if obj.hide_viewport or obj.hide_get():
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


def export_collection_recursive(col, manifest_buildings, rel_path_prefix='buildings'):
    """
    Recursively export leaf collections as individual GLBs.
    Leaf = a collection with no child collections.
    """
    if is_leaf_collection(col):
        # Export this collection as one GLB
        safe_name = col.name.replace('/', '_').replace(' ', '_').replace('\\', '_')
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

        print(f'  → exporting "{col.name}"  ({vcount:,} verts, size={size:.1f}m)')
        success = export_glb(glb_abs, objects)
        # Free orphaned data blocks between exports to reclaim memory
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=False, do_recursive=True)
        if success:
            manifest_buildings.append({
                'name':       col.name,
                'collection': col.name,
                'file':       glb_rel,
                'bbox_min':   bbox_min,
                'bbox_max':   bbox_max,
                'center':     center,
                'size':       round(size, 3),
                'vertex_count': vcount,
            })
        else:
            print(f'  [ERROR] export failed for {col.name}')
    else:
        # Recurse into child collections
        print(f'  [{col.name}] → {len(col.children)} sub-collections')
        for child in col.children:
            export_collection_recursive(child, manifest_buildings, rel_path_prefix)


# ── main ──────────────────────────────────────────────────────────────────────

manifest = {'buildings': [], 'terrain': None, 'errors': []}

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
    if col.children:
        for child in col.children:
            export_collection_recursive(child, manifest['buildings'])
    else:
        export_collection_recursive(col, manifest['buildings'])

# 2. Export terrain (all Terrain objects as one combined GLB)
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
manifest_path = os.path.join(OUTPUT_DIR, 'manifest.json')
with open(manifest_path, 'w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)

print(f'\n=== Done ===')
print(f'  {len(manifest["buildings"])} building GLBs exported')
print(f'  manifest → {manifest_path}')
