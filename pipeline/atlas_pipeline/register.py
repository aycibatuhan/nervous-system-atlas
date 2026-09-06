"""Step 04: similarity registration of the BodyParts3D frame onto MNI152 RAS mm."""
from __future__ import annotations

import argparse
import itertools
import json

import nibabel as nib
import numpy as np
import trimesh
from scipy import ndimage
from scipy.spatial import cKDTree
from skimage import measure

from .paths import CONFIG, RAW, WORK, QA
from .spaces import load_ras

MASK = RAW / "mni_t1w" / "tpl-MNI152NLin2009cAsym_res-01_desc-brain_mask.nii.gz"

# MNI landmarks (mm) for QA
LANDMARKS = {"optic-chiasm": (0, 2, -18), "pituitary-gland": (0, 2, -32), "pineal-gland": (0, -33, 3)}


ASEG = RAW / "mni_aseg" / "tpl-MNI152NLin2009cAsym_res-01_seg-aseg_dseg.nii.gz"


def brain_target():
    """MNI cerebrum surface: brain mask minus cerebellum, brainstem and ventral diencephalon (aseg)."""
    img = load_ras(ASEG)
    aseg = np.asanyarray(img.dataobj)
    cerebrum = [2, 3, 41, 42, 4, 5, 43, 44, 10, 11, 12, 13, 17, 18, 26, 49, 50, 51, 52, 53, 54, 58, 251, 252, 253, 254, 255, 30, 62, 31, 63, 77, 85, 14]
    mask = np.isin(aseg, cerebrum)
    mask = ndimage.binary_closing(mask, iterations=4)
    mask = ndimage.binary_fill_holes(mask)
    verts, faces, _, _ = measure.marching_cubes(ndimage.gaussian_filter(mask.astype(np.float32), 1.0), level=0.5)
    verts = verts @ img.affine[:3, :3].T + img.affine[:3, 3]
    target = trimesh.Trimesh(verts, faces, process=True)
    if len(target.faces) > 60000:
        target = target.simplify_quadric_decimation(face_count=60000)
    # signed distance field for residual evaluation (mm)
    inside = ndimage.distance_transform_edt(mask)
    outside = ndimage.distance_transform_edt(~mask)
    sdf = outside - inside
    return target, sdf, img.affine, mask


def outer_surface(mesh: trimesh.Trimesh, pitch: float = 1.0):
    """Voxelise (filled) a possibly multi-shell mesh and return its outer surface + filled volume in mm^3."""
    vg = mesh.voxelized(pitch)
    mat = ndimage.binary_closing(vg.matrix, iterations=2)
    mat = ndimage.binary_fill_holes(mat)
    verts, faces, _, _ = measure.marching_cubes(ndimage.gaussian_filter(mat.astype(np.float32), 1.0), level=0.5)
    T = vg.transform
    verts = verts @ T[:3, :3].T + T[:3, 3]
    out = trimesh.Trimesh(verts, faces, process=True)
    return out, float(mat.sum() * pitch ** 3)


def rigid_from_points(src: np.ndarray, dst: np.ndarray, scale: float) -> np.ndarray:
    """Kabsch with a fixed scale: dst ≈ scale * R @ src + t."""
    mu_s, mu_d = src.mean(0), dst.mean(0)
    S, D = src - mu_s, dst - mu_d
    U, _, Vt = np.linalg.svd(D.T @ S)
    d = np.ones(3); d[2] = np.sign(np.linalg.det(U) * np.linalg.det(Vt))
    R = U @ np.diag(d) @ Vt
    T = np.eye(4); T[:3, :3] = scale * R; T[:3, 3] = mu_d - scale * R @ mu_s
    return T


def sdf_residual(points: np.ndarray, sdf: np.ndarray, affine: np.ndarray) -> np.ndarray:
    inv = np.linalg.inv(affine)
    vox = points @ inv[:3, :3].T + inv[:3, 3]
    return ndimage.map_coordinates(sdf, vox.T, order=1, mode="nearest")


def similarity_from_points(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """Closed-form similarity (Umeyama) mapping src -> dst."""
    mu_s, mu_d = src.mean(0), dst.mean(0)
    S, D = src - mu_s, dst - mu_d
    cov = D.T @ S / len(src)
    U, sig, Vt = np.linalg.svd(cov)
    d = np.ones(3); d[2] = np.sign(np.linalg.det(U) * np.linalg.det(Vt))
    R = U @ np.diag(d) @ Vt
    var_s = (S ** 2).sum() / len(src)
    scale = (sig * d).sum() / var_s
    t = mu_d - scale * R @ mu_s
    T = np.eye(4); T[:3, :3] = scale * R; T[:3, 3] = t
    return T


def icp(src_pts: np.ndarray, target: trimesh.Trimesh, T0: np.ndarray, iters=40, trim=0.9, z_clip=None, scale: float | None = None) -> tuple[np.ndarray, float]:
    T = T0.copy()
    tree = cKDTree(target.vertices)
    for _ in range(iters):
        p = src_pts @ T[:3, :3].T + T[:3, 3]
        d, idx = tree.query(p)
        keep = d <= np.quantile(d, trim)
        if z_clip is not None:
            keep &= p[:, 2] > z_clip
        T = rigid_from_points(src_pts[keep], target.vertices[idx[keep]], scale) if scale else similarity_from_points(src_pts[keep], target.vertices[idx[keep]])
    p = src_pts @ T[:3, :3].T + T[:3, 3]
    d, _ = tree.query(p)
    return T, float(np.sqrt(np.mean(np.sort(d)[: int(len(d) * trim)] ** 2)))


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manual", action="store_true", help="skip ICP and use config/bp3d_to_mni.json as is")
    ap.add_argument("--refine", action="store_true", help="start ICP from the stored matrix")
    ap.add_argument("--samples", type=int, default=30000)
    ap.add_argument("--icp", action="store_true", help="surface ICP instead of the default landmark affine")
    a = ap.parse_args(argv)
    out_path = CONFIG / "bp3d_to_mni.json"
    if not a.icp and not a.manual and not a.refine:
        main_landmarks(); return
    if a.manual:
        print("manual mode: using", out_path); return
    target, sdf, affine, mask = brain_target()
    src_raw = trimesh.util.concatenate([trimesh.load(str(WORK / "bp3d" / f"bp3d-cerebrum-{s}.ply"), force="mesh", process=True) for s in ("l", "r")])
    src, src_vol = outer_surface(src_raw, pitch=1.0)
    tgt_vol = float(mask.sum())
    scale = float(np.cbrt(tgt_vol / src_vol))
    print(f"volumes: BP3D cerebrum {src_vol/1000:.0f} mL, MNI cerebrum {tgt_vol/1000:.0f} mL -> fixed scale {scale:.4f}")
    src_pts = src.sample(a.samples)
    tgt_pts = target.sample(a.samples)
    best = None
    if a.refine and out_path.exists():
        T0 = np.array(json.loads(out_path.read_text())["matrix"])
        best = icp(src_pts, target, T0, iters=80, trim=0.92, scale=scale)
    else:
        # try every proper axis permutation/sign as initialisation, scale by bbox size, align centroids
        src_c, tgt_c = src_pts.mean(0), tgt_pts.mean(0)
        src_ext = np.ptp(src_pts, axis=0); tgt_ext = np.ptp(tgt_pts, axis=0)
        for perm in itertools.permutations(range(3)):
            for signs in itertools.product([1, -1], repeat=3):
                R = np.zeros((3, 3))
                for i, j in enumerate(perm):
                    R[i, j] = signs[i]
                if np.linalg.det(R) < 0:
                    continue
                T0 = np.eye(4); T0[:3, :3] = scale * R; T0[:3, 3] = tgt_c - scale * R @ src_c
                T, rms = icp(src_pts, target, T0, iters=25, trim=0.9, scale=scale)
                if best is None or rms < best[1]:
                    best = (T, rms); print(f"  init perm={perm} signs={signs} rms={rms:.2f}")
        T, _ = icp(src_pts, target, best[0], iters=80, trim=0.92, scale=scale)
        best = (T, best[1])
    T = best[0]
    p_all = src_pts @ T[:3, :3].T + T[:3, 3]
    print("source extent after T:", np.round(np.ptp(p_all, axis=0), 1), "target extent:", np.round(np.ptp(target.vertices, axis=0), 1))
    print("source centroid:", np.round(p_all.mean(0), 1), "target centroid:", np.round(target.vertices.mean(0), 1))
    # metrics
    p = src_pts @ T[:3, :3].T + T[:3, 3]
    res = np.abs(sdf_residual(p, sdf, affine))
    rms = float(np.sqrt(np.mean(res ** 2))); p95 = float(np.percentile(res, 95))
    metrics = {"surface_rms_mm": round(rms, 2), "surface_p95_mm": round(p95, 2), "scale": round(float(np.cbrt(abs(np.linalg.det(T[:3, :3])))), 4)}
    # landmarks
    lm = {}
    for mid, mni in LANDMARKS.items():
        f = WORK / "bp3d" / f"{mid}.ply"
        if f.exists():
            m = trimesh.load(str(f), force="mesh"); c = m.vertices.mean(0) @ T[:3, :3].T + T[:3, 3]
            lm[mid] = {"registered": np.round(c, 1).tolist(), "expected": list(mni), "distance_mm": round(float(np.linalg.norm(c - np.array(mni))), 1)}
    # ventricle dice
    vent = WORK / "bp3d" / "bp3d-lateral-ventricle-l.ply"
    if vent.exists():
        from .spaces import GRID_AFFINE, GRID_SHAPE
        aseg = load_ras(RAW / "mni_aseg" / "tpl-MNI152NLin2009cAsym_res-01_seg-aseg_dseg.nii.gz")
        aseg_v = np.isin(np.asanyarray(aseg.dataobj), [4, 43])
        vm = trimesh.util.concatenate([trimesh.load(str(WORK / "bp3d" / f"bp3d-lateral-ventricle-{s}.ply"), force="mesh") for s in ("l", "r")])
        vm.apply_transform(T)
        inv = np.linalg.inv(GRID_AFFINE)
        vox = vm.voxelized(pitch=1.0).fill()
        pts = vox.points @ inv[:3, :3].T + inv[:3, 3]
        ijk = np.rint(pts).astype(int)
        ok = np.all((ijk >= 0) & (ijk < np.array(GRID_SHAPE)), axis=1)
        bp = np.zeros(GRID_SHAPE, bool); bp[tuple(ijk[ok].T)] = True
        dice = 2 * (bp & aseg_v).sum() / (bp.sum() + aseg_v.sum())
        metrics["ventricle_dice"] = round(float(dice), 3)
    gates = {"surface_rms_mm": rms <= 3.0, "surface_p95_mm": p95 <= 7.0, "landmarks": all(v["distance_mm"] <= 6 for v in lm.values()) if lm else None,
             "ventricle_dice": (metrics.get("ventricle_dice", 1) >= 0.4)}
    out = {"method": "icp-similarity", "matrix": np.round(T, 6).tolist(), "metrics": metrics, "landmarks": lm, "gates": gates,
           "notes": "BodyParts3D v4.0 whole-brain surface (FMA50801) registered to the MNI152NLin2009cAsym brain mask by trimmed point-to-point ICP with similarity transform. Edit 'matrix' to override; rerun with --manual."}
    out_path.write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("metrics", "landmarks", "gates")}, indent=1))
    print("wrote", out_path)
    # QA render
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        t1 = np.asanyarray(load_ras(RAW / "mni_t1w" / "tpl-MNI152NLin2009cAsym_res-01_T1w.nii.gz").dataobj)
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))
        brain = trimesh.load(str(WORK / "bp3d" / "bp3d-brain.ply"), force="mesh"); brain.apply_transform(T)
        inv = np.linalg.inv(affine)
        for ax, (axis, pos) in zip(axes, [(0, 0), (1, -20), (2, 0)]):
            sl = [slice(None)] * 3; idx = int(round((pos - affine[axis, 3]) / affine[axis, axis])); sl[axis] = idx
            img2d = t1[tuple(sl)]
            ax.imshow(img2d.T, cmap="gray", origin="lower")
            for name, mesh, col in (("brain", brain, "yellow"), ("vent", vm if vent.exists() else None, "cyan")):
                if mesh is None: continue
                origin = np.zeros(3); origin[axis] = pos; normal = np.zeros(3); normal[axis] = 1
                lines = trimesh.intersections.mesh_plane(mesh, normal, origin)
                for seg in lines:
                    v = seg @ inv[:3, :3].T + inv[:3, 3]
                    other = [i for i in range(3) if i != axis]
                    ax.plot(v[:, other[0]], v[:, other[1]], color=col, linewidth=0.6)
            ax.set_title(f"axis {axis} = {pos} mm"); ax.axis("off")
        QA.mkdir(exist_ok=True); fig.savefig(QA / "registration_bp3d.png", dpi=110, bbox_inches="tight")
        print("QA render:", QA / "registration_bp3d.png")
    except Exception as e:  # noqa: BLE001
        print("QA render failed:", e)


if __name__ == "__main__":
    main()


# ----------------------------------------------------------------------------- landmark-based affine
# BodyParts3D concept -> MNI reference (mesh id in work/meshes.json, or explicit mm). Paired concepts are split by side after the axis flip.
LANDMARK_PAIRS = [
    (["FMA72828", "FMA72829"], "putamen"), (["FMA258714", "FMA258716"], "thalamus"),
    (["FMA72713", "FMA72714"], "hippocampus"), (["FMA72832", "FMA72833"], "amygdala"), (["FMA78449", "FMA78450"], "ventricle-lateral"),
    (["FMA73422", "FMA73423"], "superior-colliculus"), (["FMA73434", "FMA73435"], "inferior-colliculus"),
    (["FMA78454"], "ventricle-third"), (["FMA78469"], "ventricle-fourth"), (["FMA86464"], "corpus-callosum"), (["FMA79876"], "brainstem"),
    (["FMA13889"], (0.0, 2.0, -32.0)), (["FMA62045"], (0.0, 2.0, -18.0)), (["FMA62033"], (0.0, -33.0, 3.0)),
    (["FMA72830", "FMA72831"], "globus-pallidus"),
]


def mni_reference_centroids() -> dict[str, np.ndarray]:
    meshes = {m["id"]: m for m in json.loads((WORK / "meshes.json").read_text())}
    ref = {mid: np.array(m["centroid"], float) for mid, m in meshes.items()}
    aseg = load_ras(ASEG); data = np.asanyarray(aseg.dataobj)
    for name, labs in (("cerebellum-aseg", [7, 8, 46, 47]),):
        ijk = np.argwhere(np.isin(data, labs)); c = ijk.mean(0) @ aseg.affine[:3, :3].T + aseg.affine[:3, 3]; ref[name] = c
    for side in ("l", "r"):
        gi, ge = ref.get(f"globus-pallidus-internus-{side}"), ref.get(f"globus-pallidus-externus-{side}")
        if gi is not None and ge is not None: ref[f"globus-pallidus-{side}"] = (gi + 2 * ge) / 3
    return ref


def affine_lsq(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    A = np.hstack([src, np.ones((len(src), 1))])
    X, *_ = np.linalg.lstsq(A, dst, rcond=None)
    T = np.eye(4); T[:3, :] = X.T
    return T


def main_landmarks(argv=None) -> None:
    from .bp3d import element_map, load_concept
    emap = element_map()
    ref = mni_reference_centroids()
    flip = np.diag([-1.0, -1.0, 1.0])       # BodyParts3D: +x = subject's left, -y = anterior
    src_pts, dst_pts, names = [], [], []
    for fmas, target in LANDMARK_PAIRS:
        cents = []
        for f in fmas:
            m = load_concept(f, emap)
            if m is None: print("  [missing]", f); continue
            cents.append(m.vertices.mean(0))
        if not cents: continue
        if isinstance(target, tuple):
            src_pts.append(cents[0]); dst_pts.append(np.array(target)); names.append(str(target)); continue
        if len(cents) == 1:
            if target not in ref: print("  [no ref]", target); continue
            src_pts.append(cents[0]); dst_pts.append(ref[target]); names.append(target); continue
        # paired: after the flip, MNI left = negative x; BP3D left = positive x
        for c in cents:
            side = "l" if c[0] > 0 else "r"
            key = f"{target}-{side}"
            if key not in ref: print("  [no ref]", key); continue
            src_pts.append(c); dst_pts.append(ref[key]); names.append(key)
    S, D = np.array(src_pts), np.array(dst_pts)
    T = affine_lsq(S, D)
    fitted = S @ T[:3, :3].T + T[:3, 3]
    res = np.linalg.norm(fitted - D, axis=1)
    for n, r, f, d in zip(names, res, fitted, D):
        print(f"  {n:26s} residual {r:5.1f} mm   fitted {np.round(f,1)}  ref {np.round(d,1)}")
    print(f"landmarks: n={len(S)} mean residual {res.mean():.2f} mm, max {res.max():.2f} mm; det scale {np.cbrt(abs(np.linalg.det(T[:3,:3]))):.3f}")
    # surface check against the cerebrum envelope
    target, sdf, affine, mask = brain_target()
    src_raw = trimesh.util.concatenate([trimesh.load(str(WORK / "bp3d" / f"bp3d-cerebrum-{s}.ply"), force="mesh", process=True) for s in ("l", "r")])
    src, _ = outer_surface(src_raw)
    p = src.sample(20000) @ T[:3, :3].T + T[:3, 3]
    r = np.abs(sdf_residual(p, sdf, affine))
    metrics = {"landmark_mean_mm": round(float(res.mean()), 2), "landmark_max_mm": round(float(res.max()), 2), "surface_rms_mm": round(float(np.sqrt(np.mean(r ** 2))), 2),
               "surface_p95_mm": round(float(np.percentile(r, 95)), 2), "scale": round(float(np.cbrt(abs(np.linalg.det(T[:3, :3])))), 4)}
    out = {"method": "landmark-affine", "matrix": np.round(T, 6).tolist(), "metrics": metrics,
           "landmarks": {n: {"residual_mm": round(float(r_), 1)} for n, r_ in zip(names, res)},
           "gates": {"landmark_mean_mm": bool(res.mean() <= 4.0), "landmark_max_mm": bool(res.max() <= 8.0)},
           "notes": "12-dof affine from BodyParts3D concept centroids to MNI atlas mesh centroids (deep nuclei, ventricles, brainstem, cerebellum, chiasm, pituitary, pineal). Edit 'matrix' to override; rerun with --manual."}
    (CONFIG / "bp3d_to_mni.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(metrics, indent=1)); print("wrote", CONFIG / "bp3d_to_mni.json")
    # QA render
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    t1 = np.asanyarray(load_ras(RAW / "mni_t1w" / "tpl-MNI152NLin2009cAsym_res-01_T1w.nii.gz").dataobj)
    brain = trimesh.load(str(WORK / "bp3d" / "bp3d-brain.ply"), force="mesh"); brain.apply_transform(T)
    vm = trimesh.util.concatenate([trimesh.load(str(WORK / "bp3d" / f"bp3d-lateral-ventricle-{s}.ply"), force="mesh") for s in ("l", "r")]); vm.apply_transform(T)
    inv = np.linalg.inv(affine)
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    for ax, (axis, pos) in zip(axes, [(0, 0), (1, -20), (2, 0)]):
        sl = [slice(None)] * 3; idx = int(round((pos - affine[axis, 3]) / affine[axis, axis])); sl[axis] = idx
        ax.imshow(t1[tuple(sl)].T, cmap="gray", origin="lower")
        for mesh, col in ((brain, "yellow"), (vm, "cyan")):
            origin = np.zeros(3); origin[axis] = pos; normal = np.zeros(3); normal[axis] = 1
            for seg in trimesh.intersections.mesh_plane(mesh, normal, origin):
                v = seg @ inv[:3, :3].T + inv[:3, 3]; other = [i for i in range(3) if i != axis]
                ax.plot(v[:, other[0]], v[:, other[1]], color=col, linewidth=0.6)
        ax.set_title(f"axis {axis} = {pos} mm"); ax.axis("off")
    QA.mkdir(exist_ok=True); fig.savefig(QA / "registration_bp3d.png", dpi=110, bbox_inches="tight"); print("QA render:", QA / "registration_bp3d.png")
