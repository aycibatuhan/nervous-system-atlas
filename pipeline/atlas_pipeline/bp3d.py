"""Steps 03 + 05: BodyParts3D concept meshes (native frame) and registered/decimated glb export."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh
import yaml

from . import catalog
from .catalog import BUDGET, MeshSpec
from .meshing import export_glb, mesh_stats
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


def load_concept(fma: str, emap: dict) -> trimesh.Trimesh | None:
    meshes = []
    seen = set()
    for fid, tree in emap.get(fma, []):
        if fid in seen:
            continue
        seen.add(fid)
        p = BP / f"{tree}_BP3D_4.0_obj_99" / f"{fid}.obj"
        if not p.exists():
            other = BP / ("partof_BP3D_4.0_obj_99" if tree == "isa" else "isa_BP3D_4.0_obj_99") / f"{fid}.obj"
            if not other.exists():
                continue
            p = other
        m = trimesh.load(str(p), force="mesh", process=False)
        if isinstance(m, trimesh.Trimesh) and len(m.faces):
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
        parts = [load_concept(f"FMA{f}", emap) for f in fmas]
        parts = [p for p in parts if p is not None]
        if not parts:
            missing.append((sel["id"], fmas)); continue
        m = trimesh.util.concatenate(parts) if len(parts) > 1 else parts[0]
        m.export(out_dir / f"{sel['id']}.ply")
        index.append({"id": sel["id"], "fma": fmas, "names": [names.get(f"FMA{f}", "?") for f in fmas], "faces": int(len(m.faces)),
                      "bounds": m.bounds.tolist()})
        print(f"  {sel['id']:44s} {len(m.faces):8d} faces  {[names.get(f'FMA{f}', '?') for f in fmas]}")
    for e in index:
        prev[e["id"]] = e
    idx_path.write_text(json.dumps(list(prev.values()), indent=1))
    for mid, fmas in missing:
        print(f"  [missing] {mid}: FMA {fmas} not found in v4.0 element maps")
    print(f"selected {len(index)} concept meshes -> {out_dir}")


def main_meshes(argv=None) -> None:
    """Apply the BP3D->MNI transform, clean, decimate and export glb + records."""
    ap = argparse.ArgumentParser(); ap.add_argument("--only"); a = ap.parse_args(argv)
    T = np.array(json.loads((CONFIG / "bp3d_to_mni.json").read_text())["matrix"])
    index = {e["id"]: e for e in json.loads((WORK / "bp3d" / "index.json").read_text())}
    from .atlas_meshes import record
    meshes_json = WORK / "meshes.json"
    existing = {m["id"]: m for m in json.loads(meshes_json.read_text())} if meshes_json.exists() else {}
    for sel in selection():
        if a.only and sel["id"] not in a.only.split(","):
            continue
        p = WORK / "bp3d" / f"{sel['id']}.ply"
        if not p.exists():
            continue
        m = trimesh.load(str(p), force="mesh", process=True)
        m.apply_transform(T)
        m.update_faces(m.nondegenerate_faces()); m.remove_unreferenced_vertices()
        if len(m.faces) > 200:
            trimesh.smoothing.filter_taubin(m, lamb=0.5, nu=0.53, iterations=5)
        target = BUDGET[sel.get("budget", "medium")]
        if len(m.faces) > target:
            m = m.simplify_quadric_decimation(face_count=target)
        try:
            m.fix_normals()
        except Exception:  # noqa: BLE001
            pass
        spec = MeshSpec(id=sel["id"], name=sel["name"], system=sel["system"], subsystem=sel.get("subsystem"), side=sel.get("side", "midline"),
                        colour=sel.get("colour"), visible=sel.get("visible", False), budget=sel.get("budget", "medium"), structure_id=sel.get("structureId"))
        path = MESHES / spec.system / f"{spec.id}.glb"
        nbytes = export_glb(m, path, spec.id)
        rec = record(spec, "bodyparts3d", None, "registered-affine", m, path, nbytes, 0, {"fma": index[sel["id"]]["fma"], "labelVolume": None})
        existing[rec["id"]] = rec
        print(f"  {spec.id:44s} {len(m.faces):6d} tris {nbytes/1024:7.1f} KB  bbox {np.round(m.bounds, 0).tolist()}")
    meshes_json.write_text(json.dumps(list(existing.values()), indent=1))
    print("updated", meshes_json)
