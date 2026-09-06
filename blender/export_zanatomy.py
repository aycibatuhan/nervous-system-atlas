"""Headless bpy: export the selected Z-Anatomy objects as PLY (native meters, world space) and write landmark centroids.

Usage: blender/.venv/bin/python blender/export_zanatomy.py [--only id1,id2]
Writes pipeline/work/zanatomy/objs/<id>[-l|-r].ply and pipeline/work/zanatomy/landmarks.json

Selection entries may restrict the geometry that is taken from each object:
  zrange_m: [zmin, zmax]  keep only geometry whose centroid lies in that world-z band (Z-Anatomy metres,
                          +z up). Curve splines are kept or dropped whole (mean z of their control points),
                          so bevelled tubes keep their round caps; mesh triangles are kept whole (face centroid).
  splines: [i, j, ...]    keep only these spline indices of a curve object (indices are Blender's spline order).
Both are per entry and apply to every object listed in it.
"""
import bpy, bmesh, json, sys, re, glob, pathlib, argparse
import numpy as np
import yaml
from mathutils import Vector

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORK = ROOT / "pipeline/work/zanatomy"; (WORK / "objs").mkdir(parents=True, exist_ok=True)
ap = argparse.ArgumentParser(); ap.add_argument("--only"); a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
blend = sorted(glob.glob(str(ROOT / "pipeline/raw/zanatomy/**/*.blend"), recursive=True), key=lambda p: -pathlib.Path(p).stat().st_size)[0]
bpy.ops.wm.open_mainfile(filepath=blend, load_ui=False)
sel = yaml.safe_load((ROOT / "pipeline/config/zanatomy_selection.yaml").read_text())["entries"]
by_base = {}
for o in bpy.data.objects:
    if o.type in ("MESH", "CURVE"):
        base = re.sub(r"\.(l|r)$", "", o.name); by_base.setdefault(base, []).append(o)

MIN_BEVEL = 0.0006  # default 0.6 mm radius for zero-width curves (metres)
# minimum tube radius per system: cranial nerves 1.0 mm, peripheral/autonomic nerves and roots 1.5 mm
MIN_BEVEL_BY_SYSTEM = {"cranial-nerves": 0.0010, "peripheral": 0.0015, "autonomic": 0.0015, "spinal-cord": 0.0012}

def _z(v, M):
    return (M @ v).z


def _subset_curve(o, zrange, splines):
    """A temporary copy of a curve object holding only the wanted splines (so the bevel caps the cut ends)."""
    o2 = o.copy(); o2.data = o.data.copy()
    bpy.context.scene.collection.objects.link(o2)
    M = o.matrix_world
    for i, s in reversed(list(enumerate(o2.data.splines))):
        pts = [p.co.xyz for p in s.points] + [p.co for p in s.bezier_points]
        keep = True
        if splines is not None and i not in splines:
            keep = False
        if keep and zrange is not None and pts:
            zc = sum(_z(p, M) for p in pts) / len(pts)
            keep = zrange[0] <= zc <= zrange[1]
        if not keep:
            o2.data.splines.remove(s)
    return o2


def world_mesh(o, min_bevel=MIN_BEVEL, zrange=None, splines=None):
    """Evaluated world-space triangles of a mesh or curve object -> (verts Nx3, faces Mx3).

    `zrange` (world metres) and `splines` (curve spline indices) restrict what is taken from the object."""
    tmp = None
    is_curve = o.type == "CURVE"
    if is_curve and (zrange is not None or splines is not None):
        tmp = o = _subset_curve(o, zrange, splines)
        if len(o.data.splines) == 0:
            bpy.data.objects.remove(tmp, do_unlink=True); return None, None
    if o.type == "CURVE":
        d = o.data
        if d.bevel_object is None and d.bevel_depth < min_bevel:
            d.bevel_depth = min_bevel
        if d.bevel_object is None:
            d.bevel_resolution = max(d.bevel_resolution, 6)   # round cross-section
            d.use_fill_caps = True                           # closed (round-ish) ends
            d.resolution_u = max(d.resolution_u, 24)         # smooth sampling along the curve
            d.bevel_mode = "ROUND"
    dg = bpy.context.evaluated_depsgraph_get(); ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    if me is None or len(me.polygons) == 0:
        ev.to_mesh_clear(); return None, None
    bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.triangulate(bm, faces=bm.faces[:])
    M = o.matrix_world
    verts = np.array([list(M @ v.co) for v in bm.verts], float)
    faces = np.array([[v.index for v in f.verts] for f in bm.faces], int)
    bm.free(); ev.to_mesh_clear()
    if tmp is not None:
        bpy.data.objects.remove(tmp, do_unlink=True)
    if zrange is not None and not is_curve:
        c = verts[faces].mean(1)[:, 2]
        keep = (c >= zrange[0]) & (c <= zrange[1])
        if not keep.any():
            return None, None
        faces = faces[keep]
        used, faces = np.unique(faces, return_inverse=True)
        verts, faces = verts[used], faces.reshape(-1, 3)
    return verts, faces

def write_ply(path, verts, faces):
    with open(path, "wb") as f:
        f.write(f"ply\nformat binary_little_endian 1.0\nelement vertex {len(verts)}\nproperty float x\nproperty float y\nproperty float z\nelement face {len(faces)}\nproperty list uchar int vertex_indices\nend_header\n".encode())
        f.write(verts.astype("<f4").tobytes())
        fb = np.hstack([np.full((len(faces), 1), 3, "u1").view("u1"), faces.astype("<i4").view("u1").reshape(len(faces), -1)])
        f.write(fb.tobytes())

# ---- landmarks: world-space vertex-mean centroids
LANDMARKS = ["Putamen", "Thalamus", "Hippocampus", "Amygdaloid body", "Lateral ventricle", "Superior colliculus", "Inferior colliculus", "Third ventricle", "Fourth ventricle", "Corpus callosum", "Pineal gland", "Optic chiasm", "Globus pallidus", "Caudate nucleus", "Red nucleus", "Mamillary body", "Medulla oblongata", "Pons", "Midbrain", "Pituitary gland", "Hypophysis", "Habenula", "Lateral geniculate body", "Medial geniculate body", "Anterior commissure", "Posterior commissure", "Fornix"]
lm = {}
for base in LANDMARKS:
    for o in by_base.get(base, []):
        v, f = world_mesh(o)
        if v is None: continue
        lm[o.name] = {"centroid_m": v.mean(0).tolist(), "verts": int(len(v))}
(WORK / "landmarks.json").write_text(json.dumps(lm, indent=1))
print("landmarks:", len(lm))

# ---- selection export
report = []
for e in sel:
    if a.only and e["id"] not in a.only.split(","): continue
    paired = e.get("paired", True)
    groups = {}
    for base in e["objects"]:
        objs = by_base.get(base)
        if not objs: print("  [missing object]", base); continue
        for o in objs:
            side = o.name[-1] if paired and re.search(r"\.(l|r)$", o.name) else ""
            groups.setdefault(side, []).append(o)
    for side, objs in groups.items():
        vs, fs, off = [], [], 0
        for o in objs:
            v, f = world_mesh(o, MIN_BEVEL_BY_SYSTEM.get(e.get("system"), MIN_BEVEL), zrange=e.get("zrange_m"), splines=set(e["splines"]) if e.get("splines") else None)
            if v is None: print("  [empty]", o.name); continue
            vs.append(v); fs.append(f + off); off += len(v)
        if not vs: continue
        V, F = np.vstack(vs), np.vstack(fs)
        mid = f"{e['id']}-{side}" if side else e["id"]
        write_ply(WORK / "objs" / f"{mid}.ply", V, F)
        report.append({"id": mid, "verts": int(len(V)), "faces": int(len(F)), "objects": [o.name for o in objs], "bbox_m": [V.min(0).tolist(), V.max(0).tolist()]})
        print(f"  {mid:40s} {len(V):7d} v {len(F):7d} f  <- {', '.join(o.name for o in objs)[:80]}")
(WORK / "export_report.json").write_text(json.dumps(report, indent=1))
print("exported", len(report), "meshes")
