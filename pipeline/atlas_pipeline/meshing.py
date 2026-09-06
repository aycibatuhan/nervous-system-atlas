"""Mask -> signed-distance field (2x upsampled) -> marching cubes -> Taubin -> decimation -> glb (RAS mm) -> meshopt.

Every atlas-derived surface goes through `mesh_from_mask`; `weld_group` snaps shared borders between neighbouring
parcels of one atlas together; `make_lod` produces a small stand-in used for the first paint.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import trimesh
from scipy import ndimage
from scipy.spatial import cKDTree
from skimage import measure

from .paths import ROOT

GLTF_TRANSFORM = ROOT / "node_modules" / ".bin" / "gltf-transform"

TAUBIN = {"lamb": 0.5, "nu": 0.53, "iterations": 20}   # trimesh applies +lamb then -nu (i.e. mu = -0.53)
MIN_COMPONENT_FACES = 40


def signed_distance(sub: np.ndarray) -> np.ndarray:
    """Signed distance in voxels, positive inside. The zero level sits on voxel faces, so two labels that touch
    produce coincident surfaces (the basis for seam-free neighbouring parcels)."""
    inside = ndimage.distance_transform_edt(sub)
    outside = ndimage.distance_transform_edt(~sub)
    return (inside - outside).astype(np.float32)


def mesh_from_mask(mask: np.ndarray, affine: np.ndarray, target_faces: int, sigma: float = 0.6,
                   min_component_frac: float = 0.03, pad: int = 3, upsample: int = 2,
                   taubin_iterations: int | None = None) -> trimesh.Trimesh | None:
    if not mask.any():
        return None
    idx = np.argwhere(mask)
    lo = np.maximum(idx.min(0) - pad, 0)
    hi = np.minimum(idx.max(0) + pad + 1, np.array(mask.shape))
    sub = mask[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]].astype(bool)
    if min(sub.shape) < 3:
        return None
    vox = float(np.cbrt(abs(np.linalg.det(affine[:3, :3]))))
    up = upsample if vox >= 0.75 else 1          # 0.5 mm atlases are already fine enough
    sdf = signed_distance(sub)
    if up > 1:
        # trilinear upsample of the SDF (not of the binary mask) keeps the surface position sub-voxel accurate
        shape_in = np.array(sdf.shape)
        sdf = ndimage.zoom(sdf, up, order=1, mode="nearest", grid_mode=False)
        scale = (shape_in - 1) / (np.array(sdf.shape) - 1)
    else:
        scale = np.ones(3)
    if sigma > 0:
        sdf = ndimage.gaussian_filter(sdf, sigma * up)
    try:
        verts, faces, _, _ = measure.marching_cubes(sdf, level=0.0)
    except (ValueError, RuntimeError):
        return None
    verts = verts * scale + lo
    verts_mm = verts @ affine[:3, :3].T + affine[:3, 3]
    mesh = trimesh.Trimesh(verts_mm, faces, process=True)
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.remove_unreferenced_vertices()
    mesh = drop_specks(mesh, min_component_frac)
    if mesh is None:
        return None
    it = TAUBIN["iterations"] if taubin_iterations is None else taubin_iterations
    if len(mesh.faces) > 200 and it > 0:
        trimesh.smoothing.filter_taubin(mesh, lamb=TAUBIN["lamb"], nu=TAUBIN["nu"], iterations=it)
    if len(mesh.faces) > target_faces:
        mesh = mesh.simplify_quadric_decimation(face_count=target_faces)
        mesh.update_faces(mesh.nondegenerate_faces()); mesh.remove_unreferenced_vertices()
    mesh.fix_normals()
    return mesh


def drop_specks(mesh: trimesh.Trimesh, min_component_frac: float) -> trimesh.Trimesh | None:
    parts = mesh.split(only_watertight=False)
    if len(parts) <= 1:
        return mesh
    sizes = np.array([len(p.faces) for p in parts])
    keep = [p for p, sz in zip(parts, sizes) if sz >= max(MIN_COMPONENT_FACES, min_component_frac * sizes.max())]
    if not keep:
        keep = [parts[int(sizes.argmax())]]
    return trimesh.util.concatenate(keep) if len(keep) > 1 else keep[0]


def weld_group(meshes: list[trimesh.Trimesh], tol_mm: float = 0.35) -> int:
    """Snap vertices of *different* meshes that lie within tol_mm of each other onto their mean position, so the
    borders between neighbouring parcels close without cracks. Returns the number of welded vertices."""
    if len(meshes) < 2:
        return 0
    owner = np.concatenate([np.full(len(m.vertices), i) for i, m in enumerate(meshes)])
    V = np.vstack([m.vertices for m in meshes]).astype(np.float64)
    tree = cKDTree(V)
    pairs = tree.query_pairs(tol_mm, output_type="ndarray")
    if len(pairs) == 0:
        return 0
    pairs = pairs[owner[pairs[:, 0]] != owner[pairs[:, 1]]]
    if len(pairs) == 0:
        return 0
    parent = np.arange(len(V))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for a, b in pairs:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
    roots = np.array([find(i) for i in range(len(V))])
    touched = np.unique(roots[pairs.ravel()])
    sums = np.zeros_like(V); counts = np.zeros(len(V))
    np.add.at(sums, roots, V); np.add.at(counts, roots, 1)
    mean = sums[roots] / counts[roots][:, None]
    sel = np.isin(roots, touched)
    V[sel] = mean[sel]
    off = 0
    for m in meshes:
        n = len(m.vertices)
        m.vertices = V[off:off + n]
        off += n
        m._cache.clear()
    return int(sel.sum())


def make_lod(mesh: trimesh.Trimesh, faces: int) -> trimesh.Trimesh | None:
    """Low-detail stand-in for the first paint; None when the mesh is already small."""
    if len(mesh.faces) <= 2 * faces:
        return None
    lod = mesh.simplify_quadric_decimation(face_count=faces)
    lod.update_faces(lod.nondegenerate_faces()); lod.remove_unreferenced_vertices()
    try:
        lod.fix_normals()
    except Exception:  # noqa: BLE001
        pass
    return lod


def export_glb(mesh: trimesh.Trimesh, path: Path, name: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    mesh.metadata["name"] = name
    scene = trimesh.Scene()
    scene.add_geometry(mesh, node_name=name, geom_name=name)
    tmp = path.with_suffix(".raw.glb")
    scene.export(tmp, file_type="glb", include_normals=True)
    return compress(tmp, path)


def export_with_lod(mesh: trimesh.Trimesh, path: Path, name: str, lod_faces: int = 3000, lod_min_faces: int = 12000) -> tuple[int, dict | None]:
    """Export the full mesh and, for large meshes, a `<name>.lod.glb` stand-in. Returns (bytes, lod record)."""
    nbytes = export_glb(mesh, path, name)
    lod_rec = None
    if len(mesh.faces) >= lod_min_faces:
        lod = make_lod(mesh, lod_faces)
        if lod is not None:
            lp = path.with_name(path.stem + ".lod.glb")
            lb = export_glb(lod, lp, name)
            lod_rec = {"file": str(lp.relative_to(path.parents[2])).replace("\\", "/"), "bytes": lb, "triangles": int(len(lod.faces))}
    return nbytes, lod_rec


def compress(src: Path, dst: Path) -> int:
    cmd = [str(GLTF_TRANSFORM), "meshopt", str(src), str(dst), "--level", "medium"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        src.replace(dst)
        return dst.stat().st_size
    src.unlink(missing_ok=True)
    return dst.stat().st_size


def mesh_stats(mesh: trimesh.Trimesh) -> dict:
    b = mesh.bounds
    return {"triangles": int(len(mesh.faces)), "bbox": [[round(float(x), 1) for x in b[0]], [round(float(x), 1) for x in b[1]]],
            "centroid": [round(float(x), 1) for x in mesh.vertices.mean(0)], "watertight": bool(mesh.is_watertight)}
