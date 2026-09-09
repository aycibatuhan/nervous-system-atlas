"""Steps 03 + 05: BodyParts3D concept meshes (native frame) and registered/decimated glb export."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh
import yaml

from . import catalog
from .catalog import BUDGET, BUDGET_BUMP, LOD_FACES, LOD_MIN_FACES, MeshSpec
from .meshing import export_glb, export_with_lod, mesh_stats
from .paths import CONFIG, MESHES, RAW, WORK

BP = RAW / "bodyparts3d"


def element_map() -> dict[str, list[tuple[str, str]]]:
    """FMA concept id -> [(element file id, tree)]"""
    out: dict[str, list[tuple[str, str]]] = {}
    for tree in ("isa", "partof"):
        p = BP / f"{tree}_element_parts.txt"
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            out.setdefault(parts[0].strip(), []).append((parts[2].strip(), tree))
    return out


def concept_names() -> dict[str, str]:
    names = {}
    for tree in ("isa", "partof"):
        p = BP / f"{tree}_parts_list_e.txt"
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
            parts = line.split("\t")
            if len(parts) >= 2:
                names.setdefault(parts[0].strip(), parts[1].strip())
    return names


def load_element(fid: str, tree: str = "isa") -> trimesh.Trimesh | None:
    p = BP / f"{tree}_BP3D_4.0_obj_99" / f"{fid}.obj"
    if not p.exists():
        p = BP / ("partof_BP3D_4.0_obj_99" if tree == "isa" else "isa_BP3D_4.0_obj_99") / f"{fid}.obj"
        if not p.exists():
            return None
    m = trimesh.load(str(p), force="mesh", process=False)
    return m if isinstance(m, trimesh.Trimesh) and len(m.faces) else None


def load_concept(fma: str, emap: dict, trees: tuple[str, ...] = ("isa", "partof")) -> trimesh.Trimesh | None:
    """Union of the element files BodyParts3D lists for a concept.

    `trees` selects which of the two element maps is used.  Both is the default and is right for concepts
    whose `partof` list is genuinely the concept plus its own branches (the carotid with its branches, PICA).
    It is wrong for the vertebrobasilar concepts, whose `partof` list is the whole vertebrobasilar tree
    repeated for every member of it -- 43 element files for each vertebral artery, 29 of them shared, so the
    left and the right concept produce byte-identical whole-tree meshes.  Those entries set `tree: isa`,
    where each concept lists exactly the one element file that is that vessel."""
    meshes = []
    seen = set()
    for fid, tree in emap.get(fma, []):
        if tree not in trees or fid in seen:
            continue
        seen.add(fid)
        m = load_element(fid, tree)
        if m is not None:
            meshes.append(m)
    if not meshes:
        return None
    m = trimesh.util.concatenate(meshes) if len(meshes) > 1 else meshes[0]
    m.merge_vertices()
    m.update_faces(m.nondegenerate_faces())
    m.remove_unreferenced_vertices()
    return m


def selection() -> list[dict]:
    return yaml.safe_load((CONFIG / "bp3d_selection.yaml").read_text())["meshes"]


# --------------------------------------------------------------- per-entry geometry restrictions
# BodyParts3D world: +x = the subject's left, +y = posterior, +z = up, millimetres, midline at x = 0.
def restrict(m: trimesh.Trimesh, sel: dict) -> trimesh.Trimesh:
    """Apply an entry's `sideClip` / `srcZMin` / `srcZMax` / `minComponentFaces` restrictions.

    Faces are kept or dropped whole, by their centroid, so the cut is clean at the mesh's own resolution;
    the clip planes are stated in the BodyParts3D source frame (millimetres), which is where the anatomy
    the entry is talking about -- a side of the midline, a level of the vertebrobasilar junction -- is
    axis-aligned.  The registration to MNI rotates that frame by ~23 degrees, so an MNI-frame clip would cut
    a slanted plane through the body."""
    side, zmin, zmax = sel.get("sideClip"), sel.get("srcZMin"), sel.get("srcZMax")
    if side or zmin is not None or zmax is not None:
        c = m.triangles_center
        keep = np.ones(len(m.faces), bool)
        if side == "left":
            keep &= c[:, 0] >= 0.0
        elif side == "right":
            keep &= c[:, 0] <= 0.0
        elif side:
            raise SystemExit(f"{sel['id']}: sideClip must be 'left' or 'right', got {side!r}")
        if zmin is not None:
            keep &= c[:, 2] >= float(zmin)
        if zmax is not None:
            keep &= c[:, 2] <= float(zmax)
        m.update_faces(keep)
        m.remove_unreferenced_vertices()
    return m


# --------------------------------------------------------------- sub-cranial anteroposterior correction
def post_correction() -> dict | None:
    """The `post_correction` block of config/bp3d_to_mni.json (fitted by `atlas-register --post-correction`)."""
    pc = json.loads((CONFIG / "bp3d_to_mni.json").read_text()).get("post_correction")
    return pc if pc and pc.get("enabled", True) else None


def ap_shift(z_src: np.ndarray, pc: dict | None) -> np.ndarray:
    """+y (anterior) shift in MNI mm for each BodyParts3D source height, from the post-correction knots.

    A Fritsch-Carlson monotone cubic Hermite through the knots, clamped outside them, so it is exactly the
    top knot's value (0.0) at and above the vertebrobasilar junction and exactly the bottom knot's value
    below C6.  Same curve and the same helper as the Z-Anatomy anteroposterior ramp."""
    from .midline import mono_cubic
    z_src = np.asarray(z_src, float)
    if not pc:
        return np.zeros(z_src.shape)
    k = np.asarray(pc["knots"], float)
    return mono_cubic(k[:, 0], k[:, 1], z_src)


def main_select(argv=None) -> None:
    """Union element files per concept -> work/bp3d/<id>.ply (native BodyParts3D mm)."""
    ap = argparse.ArgumentParser(); ap.add_argument("--only"); a = ap.parse_args(argv)
    emap = element_map(); names = concept_names()
    out_dir = WORK / "bp3d"; out_dir.mkdir(parents=True, exist_ok=True)
    idx_path = out_dir / "index.json"
    prev = {e["id"]: e for e in json.loads(idx_path.read_text())} if idx_path.exists() else {}
    index = []
    missing = []
    for sel in selection():
        if a.only and sel["id"] not in a.only.split(","):
            continue
        fmas = sel["fma"] if isinstance(sel["fma"], list) else [sel["fma"]]
        trees = (sel["tree"],) if sel.get("tree") else ("isa", "partof")
        if sel.get("elements"):
            parts = [load_element(e, trees[0]) for e in sel["elements"]]
        else:
            parts = [load_concept(f"FMA{f}", emap, trees) for f in fmas]
        parts = [p for p in parts if p is not None]
        if not parts:
            missing.append((sel["id"], fmas)); continue
        m = trimesh.util.concatenate(parts) if len(parts) > 1 else parts[0]
        m = restrict(m, sel)
        if not len(m.faces):
            missing.append((sel["id"], fmas)); continue
        m.export(out_dir / f"{sel['id']}.ply")
        entry = {"id": sel["id"], "fma": fmas, "names": [names.get(f"FMA{f}", "?") for f in fmas], "faces": int(len(m.faces)),
                 "bounds": m.bounds.tolist()}
        for k in ("tree", "elements", "sideClip", "srcZMin", "srcZMax"):
            if sel.get(k) is not None:
                entry[k] = sel[k]
        index.append(entry)
        print(f"  {sel['id']:44s} {len(m.faces):8d} faces  {[names.get(f'FMA{f}', '?') for f in fmas]}"
              f"{'  [' + ' '.join(f'{k}={sel[k]}' for k in ('tree', 'sideClip', 'srcZMin', 'srcZMax') if sel.get(k) is not None) + ']' if any(sel.get(k) is not None for k in ('tree', 'sideClip', 'srcZMin', 'srcZMax')) else ''}")
    for e in index:
        prev[e["id"]] = e
    idx_path.write_text(json.dumps(list(prev.values()), indent=1))
    for mid, fmas in missing:
        print(f"  [missing] {mid}: FMA {fmas} not found in v4.0 element maps")
    print(f"selected {len(index)} concept meshes -> {out_dir}")


def retire(sel: dict, existing: dict) -> None:
    """Remove a formerly exported entry's glb, stand-in, record and meshes.json row (all no-ops when absent)."""
    path = MESHES / sel["system"] / f"{sel['id']}.glb"
    gone = [p for p in (path, path.with_name(path.stem + ".lod.glb"), WORK / "records" / f"{sel['id']}.json") if p.exists()]
    for p in gone:
        p.unlink()
    if existing.pop(sel["id"], None) is not None or gone:
        print(f"  {sel['id']:44s} retired (export: false)")


def main_meshes(argv=None) -> None:
    """Apply the BP3D->MNI transform, clean, decimate and export glb + records."""
    ap = argparse.ArgumentParser(); ap.add_argument("--only"); a = ap.parse_args(argv)
    T = np.array(json.loads((CONFIG / "bp3d_to_mni.json").read_text())["matrix"])
    pc = post_correction()
    index = {e["id"]: e for e in json.loads((WORK / "bp3d" / "index.json").read_text())}
    from .atlas_meshes import record
    meshes_json = WORK / "meshes.json"
    existing = {m["id"]: m for m in json.loads(meshes_json.read_text())} if meshes_json.exists() else {}
    for sel in selection():
        if a.only and sel["id"] not in a.only.split(","):
            continue
        if sel.get("export") is False:
            # a registration input (see the gross-brain group in bp3d_selection.yaml): the concept mesh exists in
            # work/bp3d/ for atlas-register, but nothing of it reaches public/data/. Clear anything an earlier build
            # left behind, so the manifest cannot keep listing it.
            retire(sel, existing)
            continue
        p = WORK / "bp3d" / f"{sel['id']}.ply"
        if not p.exists():
            continue
        m = trimesh.load(str(p), force="mesh", process=True)
        z_src = np.asarray(m.vertices)[:, 2].copy()      # BodyParts3D source height, before the affine
        m.apply_transform(T)
        dy = 0.0
        if pc is not None and sel.get("postCorrection"):
            shift = ap_shift(z_src, pc)
            m.vertices[:, 1] += shift
            dy = float(np.abs(shift).max())
        m.update_faces(m.nondegenerate_faces()); m.remove_unreferenced_vertices()
        if len(m.faces) > 200:
            trimesh.smoothing.filter_taubin(m, lamb=0.5, nu=0.53, iterations=8)
        budget = sel.get("budget", "medium")
        if sel["system"] in ("arteries", "venous", "cranial-nerves", "peripheral", "autonomic"):
            budget = BUDGET_BUMP.get(budget, budget)
        target = BUDGET[budget]
        if len(m.faces) > target:
            m = m.simplify_quadric_decimation(face_count=target)
            m.update_faces(m.nondegenerate_faces()); m.remove_unreferenced_vertices()
        try:
            m.fix_normals()
        except Exception:  # noqa: BLE001
            pass
        spec = MeshSpec(id=sel["id"], name=sel["name"], system=sel["system"], subsystem=sel.get("subsystem"), side=sel.get("side", "midline"),
                        colour=sel.get("colour"), visible=sel.get("visible", False), budget=sel.get("budget", "medium"), structure_id=sel.get("structureId"))
        path = MESHES / spec.system / f"{spec.id}.glb"
        nbytes, lod = export_with_lod(m, path, spec.id, LOD_FACES, LOD_MIN_FACES)
        # like the Z-Anatomy meshes, a post-corrected mesh keeps the `registered-affine` alignment string
        # (the manifest's alignment vocabulary is a closed set in src/types/manifest.ts); the correction is
        # recorded per mesh instead.
        extra = {"fma": index[sel["id"]]["fma"], "labelVolume": None, "lod": lod}
        if dy:
            extra["postCorrectionMaxMm"] = round(dy, 2)
        rec = record(spec, "bodyparts3d", None, "registered-affine", m, path, nbytes, 0, extra)
        existing[rec["id"]] = rec
        print(f"  {spec.id:44s} {len(m.faces):6d} tris {nbytes/1024:7.1f} KB  bbox {np.round(m.bounds, 0).tolist()}"
              f"{f'  +ap<={dy:.1f}mm' if dy else ''}")
    meshes_json.write_text(json.dumps(list(existing.values()), indent=1))
    print("updated", meshes_json)
