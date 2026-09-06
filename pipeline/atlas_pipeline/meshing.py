"""Mask -> smooth surface -> decimated glb (RAS mm) -> meshopt-compressed glb."""
from __future__ import annotations

import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import trimesh
from scipy import ndimage
from skimage import measure

from .paths import ROOT

GLTF_TRANSFORM = ROOT / "node_modules" / ".bin" / "gltf-transform"


def mesh_from_mask(mask: np.ndarray, affine: np.ndarray, target_faces: int, sigma: float = 0.6,
                   min_component_frac: float = 0.03, pad: int = 2) -> trimesh.Trimesh | None:
    if not mask.any():
        return None
    idx = np.argwhere(mask)
    lo = np.maximum(idx.min(0) - pad, 0)
    hi = np.minimum(idx.max(0) + pad + 1, np.array(mask.shape))
    sub = mask[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]].astype(np.float32)
    if min(sub.shape) < 3:
        return None
    if sigma > 0:
        sub = ndimage.gaussian_filter(sub, sigma)
        # keep tiny structures from vanishing after smoothing
        if sub.max() < 0.55:
            sub = sub / sub.max() * 0.8
    try:
        verts, faces, _, _ = measure.marching_cubes(sub, level=0.5)
    except (ValueError, RuntimeError):
        return None
    verts = verts + lo
    verts_mm = verts @ affine[:3, :3].T + affine[:3, 3]
    mesh = trimesh.Trimesh(verts_mm, faces, process=True)
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.remove_unreferenced_vertices()
    # drop specks
    parts = mesh.split(only_watertight=False)
    if len(parts) > 1:
        sizes = np.array([len(p.faces) for p in parts])
        keep = [p for p, sz in zip(parts, sizes) if sz >= min_component_frac * sizes.max()]
        mesh = trimesh.util.concatenate(keep) if len(keep) > 1 else keep[0]
    if len(mesh.faces) > 200:
        trimesh.smoothing.filter_taubin(mesh, lamb=0.5, nu=0.53, iterations=8)
    if len(mesh.faces) > target_faces:
        mesh = mesh.simplify_quadric_decimation(face_count=target_faces)
    mesh.fix_normals()
    return mesh


def export_glb(mesh: trimesh.Trimesh, path: Path, name: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    mesh.metadata["name"] = name
    scene = trimesh.Scene()
    scene.add_geometry(mesh, node_name=name, geom_name=name)
    tmp = path.with_suffix(".raw.glb")
    scene.export(tmp, file_type="glb", include_normals=True)
    return compress(tmp, path)


def compress(src: Path, dst: Path) -> int:
    cmd = [str(GLTF_TRANSFORM), "meshopt", str(src), str(dst), "--level", "medium"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        # fall back to the uncompressed file
        src.replace(dst)
        return dst.stat().st_size
    src.unlink(missing_ok=True)
    return dst.stat().st_size


def mesh_stats(mesh: trimesh.Trimesh) -> dict:
    b = mesh.bounds
    return {"triangles": int(len(mesh.faces)), "bbox": [[round(float(x), 1) for x in b[0]], [round(float(x), 1) for x in b[1]]],
            "centroid": [round(float(x), 1) for x in mesh.vertices.mean(0)], "watertight": bool(mesh.is_watertight)}
