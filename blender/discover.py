"""Open the Z-Anatomy blend headlessly and dump every mesh/curve object: name, type, collection path, vertex count, bbox."""
import bpy, json, sys, glob, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
blends = sorted(glob.glob(str(ROOT / "pipeline/raw/zanatomy/**/*.blend"), recursive=True), key=lambda p: -pathlib.Path(p).stat().st_size)
print("blend files:", blends)
bpy.ops.wm.open_mainfile(filepath=blends[0], load_ui=False)
def coll_path(obj):
    out = []
    for c in bpy.data.collections:
        if obj.name in c.objects: out.append(c.name)
    return out
rows = []
for o in bpy.data.objects:
    if o.type not in ("MESH", "CURVE"): continue
    bb = [list(o.matrix_world @ __import__("mathutils").Vector(v)) for v in o.bound_box]
    xs, ys, zs = zip(*bb)
    n = len(o.data.vertices) if o.type == "MESH" else sum(len(s.points) + len(s.bezier_points) for s in o.data.splines)
    rows.append({"name": o.name, "type": o.type, "collections": coll_path(o), "verts": n, "bbox": [[min(xs), min(ys), min(zs)], [max(xs), max(ys), max(zs)]], "parent": o.parent.name if o.parent else None, "hide": o.hide_viewport})
out = ROOT / "pipeline/work/zanatomy/objects.json"
out.write_text(json.dumps(rows, indent=0))
print(len(rows), "objects ->", out)
print("units:", bpy.context.scene.unit_settings.system, bpy.context.scene.unit_settings.scale_length)
