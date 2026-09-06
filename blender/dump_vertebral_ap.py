"""Headless bpy: dump the world-space geometry the vertebral-artery correction is measured against.

Usage: blender/.venv/bin/python blender/dump_vertebral_ap.py
Writes pipeline/work/zanatomy/vertebral_dump.npz -- one float64 (N, 3) array per object, Z-Anatomy world
metres (+x subject left, +y posterior, +z up).  Curve objects are dumped as their spline control points
(suffix "#curve"), which is exactly the vessel centreline; mesh objects as their evaluated vertices.

Why this is separate from export_zanatomy.py: these objects are *measurement references* for the
BodyParts3D sub-cranial post-correction (atlas_pipeline/bp3d.py), not meshes the atlas ships -- the
published arteries are the BodyParts3D ones and the published vertebrae are none.
"""
import glob
import pathlib

import bpy
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "pipeline/work/zanatomy/vertebral_dump.npz"
WANT = [
    "Vertebral artery.l", "Vertebral artery.r", "Basilar artery",
    "Internal carotid artery.l", "Internal carotid artery.r",
    "Left subclavian artery", "Right subclavian artery",
    "Atlas (C1)", "Axis (C2)", "Vertebra C3", "Vertebra C4", "Vertebra C5", "Vertebra C6", "Vertebra C7",
    "Occipital bone",
]

blend = sorted(glob.glob(str(ROOT / "pipeline/raw/zanatomy/**/*.blend"), recursive=True),
               key=lambda p: -pathlib.Path(p).stat().st_size)[0]
bpy.ops.wm.open_mainfile(filepath=blend, load_ui=False)
dep = bpy.context.evaluated_depsgraph_get()
out = {}
for name in WANT:
    o = bpy.data.objects.get(name)
    if o is None or o.type not in ("MESH", "CURVE"):
        print("MISSING", name)
        continue
    M = np.array(o.matrix_world)
    if o.type == "CURVE":
        pts = []
        for si, s in enumerate(o.data.splines):
            co = [tuple(p.co)[:3] for p in s.points] + [tuple(p.co)[:3] for p in s.bezier_points]
            pts += [(si,) + c for c in co]
        A = np.array(pts, float)
        out[name + "#curve"] = np.column_stack([A[:, 0], A[:, 1:] @ M[:3, :3].T + M[:3, 3]])
        print(f"{name:32s} CURVE {len(A):5d} control points, {len(o.data.splines)} splines")
    ev = o.evaluated_get(dep)
    me = ev.to_mesh()
    if me is not None and len(me.vertices):
        V = np.empty((len(me.vertices), 3), float)
        me.vertices.foreach_get("co", V.ravel())
        out[name] = V @ M[:3, :3].T + M[:3, 3]
        print(f"{name:32s} {o.type:5s} {len(V):7d} verts  z {out[name][:, 2].min():.4f}..{out[name][:, 2].max():.4f} m")
    ev.to_mesh_clear()
OUT.parent.mkdir(parents=True, exist_ok=True)
np.savez_compressed(OUT, **out)
print("wrote", OUT)
