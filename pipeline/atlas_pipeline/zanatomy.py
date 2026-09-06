"""Phase 6: Z-Anatomy meshes (exported by blender/export_zanatomy.py) -> MNI registration -> glb records.

atlas-zanatomy-register : landmark affine (Z-Anatomy meters, +x left, +y posterior, +z up) -> MNI RAS mm
atlas-zanatomy-meshes   : apply the transform, decimate, export glb, merge records into work/meshes.json
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import trimesh
import yaml

from .catalog import LOD_FACES, LOD_MIN_FACES, MeshSpec
from .meshing import export_glb, export_with_lod
from .paths import CONFIG, MESHES, WORK
from .register import affine_lsq, mni_reference_centroids

ZW = WORK / "zanatomy"
BUDGET = {"small": 3000, "medium": 8000, "large": 16000}
# Z-Anatomy base object name -> MNI reference (mesh id base for paired, mesh id for midline, or explicit RAS mm)
LANDMARKS = {
    "Putamen": "putamen", "Thalamus": "thalamus", "Hippocampus": "hippocampus", "Amygdaloid body": "amygdala", "Lateral ventricle": "ventricle-lateral",
    "Superior colliculus": "superior-colliculus", "Inferior colliculus": "inferior-colliculus", "Globus pallidus": "globus-pallidus", "Red nucleus": "red-nucleus",
    "Mamillary body": "mammillary-body", "Habenula": "habenula", "Lateral geniculate body": "lateral-geniculate-nucleus", "Medial geniculate body": "medial-geniculate-nucleus",
    "Caudate nucleus": "caudate-nucleus",
    "Third ventricle": "ventricle-third", "Fourth ventricle": "ventricle-fourth", "Corpus callosum": "corpus-callosum",
    "Pineal gland": (0.0, -33.0, 3.0), "Optic chiasm": (0.0, 2.0, -18.0), "Pituitary gland": (0.0, 2.0, -32.0), "Hypophysis": (0.0, 2.0, -32.0),
}
PRE = np.diag([-1000.0, -1000.0, 1000.0, 1.0])   # meters -> mm, +x left -> RAS -x, +y posterior -> RAS -y


def _side(name: str) -> str | None:
    return name[-1] if name.endswith((".l", ".r")) else None


def main_register(argv=None) -> None:
    lm = json.loads((ZW / "landmarks.json").read_text())
    ref = mni_reference_centroids()
    src, dst, names = [], [], []
    # brainstem: union of medulla + pons + midbrain (both sides), weighted by vertex count
    bs = [(np.array(v["centroid_m"]), v["verts"]) for k, v in lm.items() if k.split(".")[0] in ("Medulla oblongata", "Pons", "Midbrain")]
    if bs and "brainstem" in ref:
        c = sum(p * w for p, w in bs) / sum(w for _, w in bs); src.append(c); dst.append(ref["brainstem"]); names.append("brainstem")
    merged = {}
    for k, v in lm.items():
        base = k.split(".")[0]
        if base not in LANDMARKS: continue
        merged.setdefault((base, _side(k)), []).append((np.array(v["centroid_m"]), v["verts"]))
    for (base, side), pts in merged.items():
        c = sum(p * w for p, w in pts) / sum(w for _, w in pts)
        target = LANDMARKS[base]
        if isinstance(target, tuple):
            key = base
            if side is not None:   # e.g. optic chiasm halves: average both halves onto the midline target
                key = base; c = c
            src.append(c); dst.append(np.array(target)); names.append(key); continue
        key = f"{target}-{side}" if side else target
        if key not in ref:
            print("  [no ref]", key); continue
        src.append(c); dst.append(ref[key]); names.append(key)
    S = np.array(src) @ PRE[:3, :3].T
    D = np.array(dst)
    T = affine_lsq(S, D)
    fitted = S @ T[:3, :3].T + T[:3, 3]
    res = np.linalg.norm(fitted - D, axis=1)
    for n, r, f, d in sorted(zip(names, res, fitted, D), key=lambda x: -x[1]):
        print(f"  {n:34s} residual {r:5.1f} mm   fitted {np.round(f, 1)}  ref {np.round(d, 1)}")
    # drop outliers (> 2.5x median) and refit once
    keep = res <= max(6.0, 2.5 * np.median(res))
    if keep.sum() >= 8 and keep.sum() < len(res):
        T = affine_lsq(S[keep], D[keep]); fitted = S @ T[:3, :3].T + T[:3, 3]; res = np.linalg.norm(fitted - D, axis=1)
        print(f"  refit without {int((~keep).sum())} outliers: {[n for n, k in zip(names, keep) if not k]}")
    full = T @ PRE
    metrics = {"landmark_mean_mm": round(float(res[keep].mean()), 2), "landmark_max_mm": round(float(res[keep].max()), 2), "n": int(keep.sum()),
               "scale": round(float(np.cbrt(abs(np.linalg.det(full[:3, :3]))) / 1000), 4)}
    out = {"method": "landmark-affine", "matrix": np.round(full, 6).tolist(), "metrics": metrics,
           "landmarks": {n: {"residual_mm": round(float(r), 1), "used": bool(k)} for n, r, k in zip(names, res, keep)},
           "notes": "Z-Anatomy world meters (+x subject left, +y posterior, +z up) -> MNI152NLin2009cAsym RAS mm; 12-dof affine from landmark centroids."}
    (CONFIG / "zanatomy_to_mni.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(metrics)); print("wrote", CONFIG / "zanatomy_to_mni.json")


def main_meshes(argv=None) -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--only"); a = ap.parse_args(argv)
    T = np.array(json.loads((CONFIG / "zanatomy_to_mni.json").read_text())["matrix"])
    cfg = yaml.safe_load((CONFIG / "zanatomy_selection.yaml").read_text())
    report = {r["id"]: r for r in json.loads((ZW / "export_report.json").read_text())}
    from .atlas_meshes import record
    meshes_json = WORK / "meshes.json"
    existing = {m["id"]: m for m in json.loads(meshes_json.read_text())} if meshes_json.exists() else {}
    n = 0
    for e in cfg["entries"]:
        if a.only and e["id"] not in a.only.split(","): continue
        for mid, rep in report.items():
            if not (mid == e["id"] or mid.startswith(e["id"] + "-") and mid[len(e["id"]) + 1:] in ("l", "r")): continue
            side = mid[-1] if mid != e["id"] else "midline"
            p = ZW / "objs" / f"{mid}.ply"
            if not p.exists(): continue
            m = trimesh.load(str(p), force="mesh", process=True)
            m.apply_transform(T)
            m.update_faces(m.nondegenerate_faces()); m.remove_unreferenced_vertices()
            if len(m.faces) > 200:
                trimesh.smoothing.filter_taubin(m, lamb=0.5, nu=0.53, iterations=6)
            target = BUDGET[e.get("budget", "medium")]
            if len(m.faces) > target:
                m = m.simplify_quadric_decimation(face_count=target)
                m.update_faces(m.nondegenerate_faces()); m.remove_unreferenced_vertices()
            try: m.fix_normals()
            except Exception: pass  # noqa: BLE001
            side_name = {"l": "left", "r": "right"}.get(side, "midline")
            spec = MeshSpec(id=mid, name=e["name"] + (f" ({side_name})" if side != "midline" else ""), system=e["system"], subsystem=e.get("subsystem"), side=side_name,
                            colour=e.get("colour"), visible=e.get("visible", False), budget=e.get("budget", "medium"), structure_id=e.get("structureId"), opacity=e.get("opacity", 1.0))
            path = MESHES / spec.system / f"{spec.id}.glb"
            nbytes, lod = export_with_lod(m, path, spec.id, LOD_FACES, LOD_MIN_FACES)
            rec = record(spec, "zanatomy", None, "registered-affine", m, path, nbytes, 0, {"zanatomyObjects": rep["objects"], "labelVolume": None, "lod": lod})
            existing[rec["id"]] = rec; n += 1
            print(f"  {spec.id:44s} {len(m.faces):6d} tris {nbytes/1024:7.1f} KB  bbox {np.round(m.bounds, 0).tolist()}")
    meshes_json.write_text(json.dumps(list(existing.values()), indent=1))
    print(f"updated {meshes_json} (+{n} zanatomy meshes)")
