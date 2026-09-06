"""Headless bpy: dump the world-space vertices of the Z-Anatomy brainstem, cord and fourth ventricle.

Usage: blender/.venv/bin/python blender/dump_brainstem_ap.py
Writes pipeline/work/zanatomy/brainstem_dump.npz -- one float64 (N, 3) array per object, Z-Anatomy world
metres (+x subject left, +y posterior, +z up).

Why this is separate from export_zanatomy.py: those objects are *measurement references* for the
anteroposterior post-correction fitted by `atlas-zanatomy-midline` (atlas_pipeline/midline.py), not meshes the
atlas ships -- the published brainstem is the MNI aseg one.  They are dumped raw (no decimation, no bevel, no
transform) so the fit sees exactly the source geometry.
"""
import glob
import pathlib

import bpy
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "pipeline/work/zanatomy/brainstem_dump.npz"
WANT = [
    "Midbrain.l", "Midbrain.r", "Pons.l", "Pons.r", "Medulla oblongata.l", "Medulla oblongata.r",
    "White matter of spinal cord", "Anterior horn of spinal cord", "Posterior horn of spinal cord",
    "Olive.l", "Olive.r", "Pyramid of medulla oblongata.l", "Pyramid of medulla oblongata.r",
    "Fourth ventricle", "Occipital bone",
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
    ev = o.evaluated_get(dep)
    me = ev.to_mesh()
    M = np.array(o.matrix_world)
    V = np.empty((len(me.vertices), 3), float)
    me.vertices.foreach_get("co", V.ravel())
    out[name] = V @ M[:3, :3].T + M[:3, 3]
    ev.to_mesh_clear()
    print(f"{name:36s} {len(V):7d} verts  z {out[name][:, 2].min():.4f}..{out[name][:, 2].max():.4f} m")
OUT.parent.mkdir(parents=True, exist_ok=True)
np.savez_compressed(OUT, **out)
print("wrote", OUT)
