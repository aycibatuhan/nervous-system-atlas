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


def carry_post_correction(out: dict, path) -> dict:
    """Keep the fitted `post_correction` block when the affine is rewritten, and flag it as stale.

    Refitting the affine invalidates the ramp -- it was fitted against *this* matrix -- so the block is kept
    (so the meshes do not silently lose it) but marked, and `atlas-qa` fails on a stale block."""
    from pathlib import Path
    p = Path(path)
    if not p.exists():
        return out
    pc = json.loads(p.read_text()).get("post_correction")
    if pc is None:
        return out
    old = json.loads(p.read_text()).get("matrix")
    if old is not None and np.allclose(np.array(old, float), np.array(out["matrix"], float), atol=1e-9):
        out["post_correction"] = pc
        return out
    pc = dict(pc); pc["stale"] = True
    pc["stale_reason"] = "the affine was refitted after this ramp; rerun atlas-register --post-correction"
    out["post_correction"] = pc
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manual", action="store_true", help="skip ICP and use config/bp3d_to_mni.json as is")
    ap.add_argument("--refine", action="store_true", help="start ICP from the stored matrix")
    ap.add_argument("--samples", type=int, default=30000)
    ap.add_argument("--icp", action="store_true", help="surface ICP instead of the default landmark affine")
    ap.add_argument("--post-correction", action="store_true",
                    help="measure and fit the sub-cranial anteroposterior ramp only; the affine is not touched")
    a, _ = ap.parse_known_args(argv)
    out_path = CONFIG / "bp3d_to_mni.json"
    if a.post_correction:
        main_post_correction(argv); return
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
    out_path.write_text(json.dumps(carry_post_correction(out, out_path), indent=1))
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
    (CONFIG / "bp3d_to_mni.json").write_text(json.dumps(carry_post_correction(out, CONFIG / "bp3d_to_mni.json"), indent=1))
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


# ----------------------------------------------------------------------------- sub-cranial AP post-correction
"""The BodyParts3D affine is fitted on brain landmarks only, and like the Z-Anatomy one it leaves the body
below the skull base pitched too far back.  Measured two independent ways it is the same error:

  * the BodyParts3D brainstem concept (FMA79876), which the affine registers, against the MNI aseg Brain-Stem
    label -- mid-sagittal silhouette centres, MNI's own data, no second model involved;
  * the BodyParts3D vertebral artery against the Z-Anatomy vertebral artery mapped through the corrected
    Z-Anatomy transform (affine + `post_correction`), which is the frame the atlas's cord and roots live in.

Both say the same thing: 0 at the vertebrobasilar junction, about +17 mm (anterior) from just below the
foramen magnum down to C2/C3, and back to 0 by C5/C6, where the two bodies' necks stop diverging.  It is not
an affine residual -- no linear map is 0 at the pons, 17 mm at C2 and 0 again at C6 -- so refitting the
affine cannot remove it, and the model is a per-height ramp like the Z-Anatomy one:

    dy(p) = ramp(p_z)        p = source point in BodyParts3D millimetres, dy added to MNI y (+ = anterior)

`ramp` is a Fritsch-Carlson monotone cubic Hermite through eight knots at anatomical heights (C6, C5, C4, C3,
the axis, the atlas, the foramen magnum, the vertebrobasilar junction), clamped outside them.  The top knot is
hard-pinned to 0 at the vertebrobasilar junction, so the vertebral arteries stay welded to the basilar, which
does not move: the basilar is a cranial mesh and the hard rule for this correction is that no mesh that lies
entirely above MNI z = -70 may move by more than 1 mm.  That pin is why the ramp deliberately leaves the
intracranial V4 residual (up to ~9 mm at the mid-clivus) in place -- that part is the affine's own residual,
inside its 8.5 mm landmark maximum, and removing it would drag the basilar with it.

The knot *values* are least-squares-fitted to the two measured profiles below the foramen magnum; the knot
*heights* are anatomy, read off the BodyParts3D concepts themselves.  Which meshes it applies to is a
per-entry `postCorrection: true` flag in bp3d_selection.yaml, not a global rule, because the BodyParts3D
carotid does *not* share the error: see `CAROTID_NOTE` below and the report written next to the figures."""

ZDUMP = WORK / "zanatomy" / "vertebral_dump.npz"

# Knot heights in BodyParts3D source millimetres (+z up), ascending.  All eight are read off the source
# concepts: the vertebra mid-heights from FMA12519..FMA12525, the foramen magnum from the top of the atlas
# (1481.4; the occipital bone's inferior limit is 1477.8), the vertebrobasilar junction from the top of the
# vertebral artery element (1502.5), which is also the inferior end of the basilar element.
PC_KNOT_Z = (1393.2, 1405.9, 1418.4, 1431.4, 1455.8, 1471.8, 1481.4, 1502.5)
PC_KNOT_LABEL = ("C6 vertebra", "C5 vertebra", "C4 vertebra", "C3 vertebra", "axis (C2)", "atlas (C1)",
                 "foramen magnum", "vertebrobasilar junction")
PC_FIT_MAX_Z = 1481.5      # fit below the foramen magnum only (see the module note)
PC_VA_FIT_MAX_Z = 1474.0   # ... and the vertebral-artery profile only below the V3 atlas loop
PC_APPLY = ("artery-vertebral-l", "artery-vertebral-r")
CAROTID_NOTE = (
    "The correction is restricted to the posterior circulation.  The BodyParts3D cervical spine is 18 mm "
    "posterior at C3, 12 mm at C4, 8 mm at C5 and 2 mm at C7 against the corrected Z-Anatomy vertebrae, and "
    "the BodyParts3D vertebral artery sits 10-12 mm behind its own vertebral bodies -- the same as "
    "Z-Anatomy's -- so the artery is right in its own body and the whole neck is what the affine misplaces.  "
    "The BodyParts3D internal carotid, however, is drawn about 18 mm anterior of its own cervical spine "
    "(31-38 mm in front of the vertebral artery at C3-C4, against 14-19 mm in Z-Anatomy and in life), so the "
    "two errors cancel and the registered carotid already lands within 2-8 mm of the corrected Z-Anatomy "
    "carotid, slightly anterior.  Giving it the same ramp would push it 15-20 mm too far forward, out of the "
    "carotid sheath.  Hence the per-entry flag rather than a rule over every sub-cranial BodyParts3D vertex."
)


def _bp3d_source(fid: str, tree: str = "isa", largest: bool = True) -> np.ndarray:
    from .bp3d import load_element
    m = load_element(fid, tree)
    if largest:
        m = sorted(m.split(only_watertight=False), key=lambda c: -len(c.faces))[0]
    return np.asarray(m.vertices, float)


def _silhouette_y(P: np.ndarray, sel: np.ndarray) -> float:
    y = P[sel, 1]
    return float((y.min() + y.max()) / 2.0)


def measure_brainstem(T: np.ndarray, slab: float = 3.0, xw: float = 3.0) -> list[dict]:
    """Per BodyParts3D source slab: the BP3D brainstem AP centre in MNI, the aseg reference, and the gap.

    Both sides are the midpoint of the anterior and posterior surface of the mid-sagittal slab, so the number
    is a silhouette centre and does not care that one side is a mesh and the other a voxel label."""
    p = WORK / "bp3d" / "bp3d-brainstem.ply"
    if not (p.exists() and ASEG.exists()):
        return []
    S = np.asarray(trimesh.load(str(p), force="mesh", process=False).vertices, float)
    P = S @ T[:3, :3].T + T[:3, 3]
    img = load_ras(ASEG)
    d = np.rint(np.asanyarray(img.dataobj)).astype(np.int32)
    W = np.argwhere(d == 16) @ img.affine[:3, :3].T + img.affine[:3, 3]
    zmin = float(W[:, 2].min())
    rows = []
    for z0 in np.arange(1462.0, 1530.0, slab):
        sel = (S[:, 2] >= z0) & (S[:, 2] < z0 + slab) & (np.abs(P[:, 0]) <= xw)
        if sel.sum() < 8:
            continue
        zc = float(P[sel, 2].mean())
        ref = (np.abs(W[:, 2] - zc) < 1.0) & (np.abs(W[:, 0]) <= xw)
        row = {"z_src_mm": round(z0 + slab / 2, 1), "z_mni_mm": round(zc, 1), "ref": "aseg-brainstem",
               "n": int(sel.sum()), "bp3d_y_mm": round(_silhouette_y(P, sel), 2)}
        if ref.sum() < 8 or zc - 1.0 < zmin:
            row["note"] = "below the caudal end of the aseg Brain-Stem label: measured, not comparable"
            rows.append(row); continue
        row["mni_y_mm"] = round(_silhouette_y(W, ref), 2)
        row["dy_mm"] = round(row["mni_y_mm"] - row["bp3d_y_mm"], 2)
        row["in_fit"] = bool(row["z_src_mm"] <= PC_FIT_MAX_Z)
        if not row["in_fit"]:
            row["note"] = ("above the foramen magnum: measured and reported, not fitted -- the ramp is pinned "
                           "to 0 at the vertebrobasilar junction so the basilar does not move")
        rows.append(row)
    return rows


def measure_vertebral(T: np.ndarray, slab: float = 4.0) -> list[dict]:
    """Per BodyParts3D source slab: the BP3D vertebral artery against the corrected Z-Anatomy one.

    Both arteries are reduced to a per-MNI-z-slab mean y of both sides, so the same thing is compared on both
    sides even where the V3 segment loops over the atlas; the loop is nevertheless excluded from the fit,
    because there the map from MNI z to a point on the vessel is multivalued."""
    from . import midline
    if not ZDUMP.exists():
        return []
    D = np.load(ZDUMP)
    if "Vertebral artery.l" not in D:
        return []
    zcfg = json.loads((CONFIG / "zanatomy_to_mni.json").read_text())
    Tz, pc = np.array(zcfg["matrix"]), zcfg.get("post_correction")
    ZA = np.vstack([midline.transform(D[f"Vertebral artery.{s}"], Tz, pc) for s in ("r", "l")])
    S = np.vstack([_bp3d_source("FJ1725"), _bp3d_source("FJ1725M")])
    P = S @ T[:3, :3].T + T[:3, 3]
    zs = np.arange(-215.0, -40.0, 2.5)
    ty = np.array([ZA[(ZA[:, 2] >= z - 3) & (ZA[:, 2] < z + 3), 1].mean()
                   if ((ZA[:, 2] >= z - 3) & (ZA[:, 2] < z + 3)).sum() >= 6 else np.nan for z in zs])
    ok = ~np.isnan(ty)
    rows = []
    for z0 in np.arange(1390.0, 1506.0, slab):
        sel = (S[:, 2] >= z0) & (S[:, 2] < z0 + slab)
        if sel.sum() < 6:
            continue
        zc = float(P[sel, 2].mean())
        yza = float(np.interp(zc, zs[ok], ty[ok], left=np.nan, right=np.nan))
        if np.isnan(yza):
            continue
        ybp = float(P[sel, 1].mean())
        row = {"z_src_mm": round(z0 + slab / 2, 1), "z_mni_mm": round(zc, 1), "ref": "zanatomy-vertebral-artery",
               "n": int(sel.sum()), "bp3d_y_mm": round(ybp, 2), "mni_y_mm": round(yza, 2),
               "dy_mm": round(yza - ybp, 2), "in_fit": bool(z0 + slab / 2 <= PC_VA_FIT_MAX_Z)}
        if not row["in_fit"]:
            row["note"] = ("V3 atlas loop and the intradural V4: MNI z maps to more than one point of the "
                           "vessel there, so it is measured and reported, not fitted")
        rows.append(row)
    return rows


def fit_post_correction(profile: list[dict]) -> tuple[list[list[float]], dict]:
    """Least-squares fit of the knot values to the measured profiles; the top knot is hard-pinned to 0.

    Values are parameterised as absolute values, so the ramp never carries anything posterior (every
    measurement below the foramen magnum asks for an anterior shift), and a light second-difference penalty
    keeps eight knots from chasing 17 samples."""
    from scipy.optimize import least_squares
    from .midline import mono_cubic
    pts = [(r["z_src_mm"], r["dy_mm"]) for r in profile if r.get("in_fit")]
    Z = np.array([a for a, _ in pts]); Y = np.array([b for _, b in pts])
    kz = np.array(PC_KNOT_Z, float)

    def values(q):
        return np.concatenate([np.abs(q), [0.0]])

    def resid(q):
        v = values(q)
        return np.concatenate([mono_cubic(kz, v, Z) - Y, 0.15 * np.diff(v, 2)])

    res = least_squares(resid, np.full(len(kz) - 1, float(Y.max()) / 2 if len(Y) else 8.0))
    v = values(res.x)
    v[-1] = 0.0
    r = Y - mono_cubic(kz, v, Z)
    stats = {"samples": int(len(Y)), "rms_mm": round(float(np.sqrt((r ** 2).mean())), 2),
             "mean_abs_mm": round(float(np.abs(r).mean()), 2), "max_abs_mm": round(float(np.abs(r).max()), 2)}
    return [[round(float(a), 1), round(float(b), 2)] for a, b in zip(kz, v)], stats


def mesh_displacements(T: np.ndarray, pc: dict) -> tuple[list[dict], dict]:
    """Per selected mesh: how far the ramp moves it, and the hard-rule check on the cranial ones.

    The hard rule for this correction is that no BodyParts3D mesh lying entirely above MNI z = -70 may move
    by more than 1 mm.  The flag makes that trivially true -- an unflagged mesh is bit-identical -- but it is
    checked over every mesh's actual vertices rather than assumed, and reported so a future flag cannot
    quietly break it."""
    from .bp3d import ap_shift, selection
    rows, worst_cranial = [], {"id": None, "max_dy_mm": 0.0}
    for sel in selection():
        p = WORK / "bp3d" / f"{sel['id']}.ply"
        if not p.exists():
            continue
        m = trimesh.load(str(p), force="mesh", process=True)
        S = np.asarray(m.vertices, float)
        P = S @ T[:3, :3].T + T[:3, 3]
        d = np.abs(ap_shift(S[:, 2], pc)) if sel.get("postCorrection") else np.zeros(len(S))
        cranial = bool(P[:, 2].min() > -70.0)
        row = {"id": sel["id"], "applied": bool(sel.get("postCorrection")), "cranial": cranial,
               "max_dy_mm": round(float(d.max()), 2), "mean_dy_mm": round(float(d.mean()), 2),
               "mni_z_min": round(float(P[:, 2].min()), 1)}
        rows.append(row)
        if cranial and row["max_dy_mm"] > worst_cranial["max_dy_mm"]:
            worst_cranial = {"id": sel["id"], "max_dy_mm": row["max_dy_mm"]}
    gate = {"rule": "no BodyParts3D mesh entirely above MNI z = -70 mm moves by more than 1 mm",
            "worst_cranial": worst_cranial, "pass": bool(worst_cranial["max_dy_mm"] <= 1.0),
            "meshes_moved": [r["id"] for r in rows if r["max_dy_mm"] > 0.0]}
    return rows, gate


def mra_midline_centreline() -> np.ndarray | None:
    """Centre of the Mouches MRA atlas's mid-sagittal posterior-circulation vessel, per MNI z (mm).

    Rows are (z, x, y): the probability-weighted centre of the |x| <= 4 mm strip in each 1 mm slice, over the
    band that holds the basilar and the vertebrobasilar junction.  The atlas is a probability map, so the
    ridge is taken at 60% of the slice maximum and slices whose maximum is below 12% are dropped.  The band
    stops at z = -56 mm: below that the midline strip of the atlas is a broad low-probability blob spanning
    the vertebrobasilar confluence and the ridge is no longer a single vessel."""
    p = RAW / "mouches_arteries" / "vesselProbabilities.nii.gz"
    if not p.exists():
        return None
    img = load_ras(p)
    V = np.asanyarray(img.dataobj).astype(np.float32)
    A = img.affine
    xs = A[0, 3] + A[0, 0] * np.arange(V.shape[0]); ys = A[1, 3] + A[1, 1] * np.arange(V.shape[1])
    ix = np.where(np.abs(xs) <= 4.0)[0]; iy = np.where((ys > -60.0) & (ys < 10.0))[0]
    out = []
    for z in np.arange(-56.0, -18.0, 1.0):
        k = int(round((z - A[2, 3]) / A[2, 2]))
        if not (0 <= k < V.shape[2]):
            continue
        sl = V[np.ix_(ix, iy, [k])][:, :, 0]
        mx = float(sl.max())
        if mx < 12.0:
            continue
        w = np.where(sl >= 0.6 * mx, sl, 0.0)
        out.append([z, float((w.sum(1) @ xs[ix]) / w.sum()), float((w.sum(0) @ ys[iy]) / w.sum())])
    return np.array(out) if out else None


def vertebrobasilar_junction(T: np.ndarray, pc: dict | None) -> dict:
    """Where the two vertebral arteries meet, and how far that is from the MRA atlas's midline vessel.

    The junction is the mean of the top 3 mm of each corrected vertebral artery; the reference is the MRA
    centreline at the same MNI z, so the number is a lateral/anteroposterior miss and not a height mismatch
    between two atlases whose vertebrobasilar junctions sit at different levels."""
    from .bp3d import ap_shift
    out = {}
    tops = []
    for fid, side in (("FJ1725", "r"), ("FJ1725M", "l")):
        S = _bp3d_source(fid)
        P = S @ T[:3, :3].T + T[:3, 3]
        if pc is not None:
            P[:, 1] += ap_shift(S[:, 2], pc)
        top = P[P[:, 2] >= P[:, 2].max() - 3.0]
        tops.append(top.mean(0))
        out[f"top_{side}"] = np.round(top.mean(0), 1).tolist()
    j = np.mean(tops, axis=0)
    out["junction"] = np.round(j, 1).tolist()
    mra = mra_midline_centreline()
    if mra is not None:
        i = int(np.argmin(np.abs(mra[:, 0] - j[2])))
        ref = mra[i]
        out["mra_reference"] = {"z_mni_mm": round(float(ref[0]), 1), "x_mm": round(float(ref[1]), 1),
                                "y_mm": round(float(ref[2]), 1)}
        out["distance_to_mra_mm"] = round(float(np.hypot(j[0] - ref[1], j[1] - ref[2])), 2)
    bas = WORK / "bp3d" / "artery-basilar.ply"
    if bas.exists():
        B = np.asarray(trimesh.load(str(bas), force="mesh", process=False).vertices, float)
        B = B @ T[:3, :3].T + T[:3, 3]
        low = B[B[:, 2] <= B[:, 2].min() + 3.0].mean(0)
        out["basilar_inferior_end"] = np.round(low, 1).tolist()
        out["junction_to_basilar_mm"] = round(float(np.linalg.norm(j - low)), 2)
    return out


def post_correction_figures(T: np.ndarray, pc: dict, profile: list[dict], rows: list[dict], vbj: dict) -> list[str]:
    """work/bp3d/vertebral_{profile,overlay,mra}.png -- the fit, the T1 overlay and the MRA overlay."""
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from . import midline
    from .bp3d import ap_shift
    out_dir = WORK / "bp3d"; out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    src = {s: _bp3d_source(f) for s, f in (("l", "FJ1725M"), ("r", "FJ1725"))}
    before = {s: v @ T[:3, :3].T + T[:3, 3] for s, v in src.items()}
    after = {}
    for s, v in src.items():
        P = (v @ T[:3, :3].T + T[:3, 3]).copy(); P[:, 1] += ap_shift(v[:, 2], pc); after[s] = P
    bas = None
    if (out_dir / "artery-basilar.ply").exists():
        bas = np.asarray(trimesh.load(str(out_dir / "artery-basilar.ply"), force="mesh", process=False).vertices, float)
        bas = bas @ T[:3, :3].T + T[:3, 3]
    za = zcord = None
    if ZDUMP.exists():
        D = np.load(ZDUMP)
        zcfg = json.loads((CONFIG / "zanatomy_to_mni.json").read_text())
        Tz, zpc = np.array(zcfg["matrix"]), zcfg.get("post_correction")
        if "Vertebral artery.l" in D:
            za = np.vstack([midline.transform(D[f"Vertebral artery.{s}"], Tz, zpc) for s in ("l", "r")])
        cp = WORK / "zanatomy" / "objs" / "spinal-white-columns.ply"
        if cp.exists():
            zcord = midline.transform(np.asarray(trimesh.load(str(cp), force="mesh", process=False).vertices, float), Tz, zpc)

    # --- 1. the fit ---------------------------------------------------------------------------------
    k = np.array(pc["knots"], float)
    zz = np.linspace(k[0, 0] - 10, k[-1, 0] + 10, 600)
    fig, ax = plt.subplots(1, 2, figsize=(13, 5.2))
    for ref, col, mk in (("aseg-brainstem", "#2F4C8F", "o"), ("zanatomy-vertebral-artery", "#B0302A", "s")):
        sel = [r for r in profile if r["ref"] == ref and "dy_mm" in r]
        for used, alpha in ((True, 1.0), (False, 0.3)):
            q = [r for r in sel if bool(r.get("in_fit")) is used]
            if q:
                ax[0].plot([r["dy_mm"] for r in q], [r["z_src_mm"] for r in q], mk, ms=4, color=col, alpha=alpha,
                           label=f"{ref}{'' if used else ' (not fitted)'}")
    ax[0].plot(ap_shift(zz, pc), zz, "-", color="#111", lw=1.6, label="fitted ramp")
    for (kz, kv), lbl in zip(k, pc["knot_labels"]):
        ax[0].plot([kv], [kz], "d", color="#111", ms=5)
        ax[0].annotate(lbl, (kv + 0.6, kz), fontsize=7, va="center")
    ax[0].set_xlabel("anteroposterior correction dy (mm, + = anterior)"); ax[0].set_ylabel("BodyParts3D source height (mm)")
    ax[0].set_title(f"sub-cranial AP ramp: fit rms {pc['fit']['rms_mm']} mm over {pc['fit']['samples']} slabs")
    ax[0].legend(fontsize=7, loc="lower right"); ax[0].grid(alpha=0.25)
    for r in profile:
        if "dy_mm" not in r:
            continue
        res = r["dy_mm"] - float(ap_shift(np.array([r["z_src_mm"]]), pc)[0])
        ax[1].plot([r["dy_mm"]], [r["z_src_mm"]], ".", color="#999", ms=6)
        ax[1].plot([res], [r["z_src_mm"]], "o", ms=4, color="#B0302A" if r.get("in_fit") else "#DDA0A0")
    ax[1].axvline(0, color="#111", lw=1)
    ax[1].axhline(pc["knots"][-1][0], color="#2F4C8F", lw=1, ls="--")
    ax[1].annotate("vertebrobasilar junction (anchor, dy = 0)", (0.5, pc["knots"][-1][0] + 1), fontsize=7, color="#2F4C8F")
    ax[1].axhline(1481.4, color="#2F8F4C", lw=1, ls=":")
    ax[1].annotate("foramen magnum", (0.5, 1482.5), fontsize=7, color="#2F8F4C")
    ax[1].set_xlabel("grey: offset before   red: residual after"); ax[1].set_title("before and after")
    ax[1].grid(alpha=0.25)
    fig.tight_layout(); fp = out_dir / "vertebral_profile.png"; fig.savefig(fp, dpi=120); plt.close(fig)
    written.append(str(fp))

    # --- 2. T1 overlay ------------------------------------------------------------------------------
    t1 = load_ras(RAW / "mni_t1w" / "tpl-MNI152NLin2009cAsym_res-01_T1w.nii.gz")
    vol = np.asanyarray(t1.dataobj); A = t1.affine
    fig, axes = plt.subplots(1, 2, figsize=(12, 7))
    i0 = int(round((0.0 - A[0, 3]) / A[0, 0]))
    yy = A[1, 3] + A[1, 1] * np.arange(vol.shape[1]); zz2 = A[2, 3] + A[2, 2] * np.arange(vol.shape[2])
    axes[0].pcolormesh(yy, zz2, vol[i0].T, cmap="gray", shading="auto", rasterized=True)
    j0 = int(round((-45.0 - A[1, 3]) / A[1, 1]))
    xx = A[0, 3] + A[0, 0] * np.arange(vol.shape[0])
    axes[1].pcolormesh(xx, zz2, vol[:, j0, :].T, cmap="gray", shading="auto", rasterized=True)
    def scat(ax, P, c, lab, a=0.8, s=1.5, cols=(1, 2)):
        ax.plot(P[:, cols[0]], P[:, cols[1]], ".", ms=s, color=c, alpha=a, label=lab)
    for ax, cols, ttl in ((axes[0], (1, 2), "sagittal projection (T1 at x = 0)"), (axes[1], (0, 2), "coronal projection (T1 at y = -45)")):
        if zcord is not None:
            scat(ax, zcord, "#3AA0C8", "Z-Anatomy cord (corrected)", 0.35, 1.0, cols)
        if za is not None:
            scat(ax, za, "#2F8F4C", "Z-Anatomy vertebral artery (corrected)", 0.5, 1.0, cols)
        for s in ("l", "r"):
            scat(ax, before[s], "#9A9A9A", "BP3D vertebral, before" if s == "l" else None, 0.6, 1.2, cols)
            scat(ax, after[s], "#B0302A", "BP3D vertebral, after" if s == "l" else None, 0.9, 1.6, cols)
        if bas is not None:
            scat(ax, bas, "#E0533F", "BP3D basilar (unmoved)", 0.9, 1.6, cols)
        ax.set_title(ttl); ax.set_aspect("equal"); ax.set_ylim(-180, 10)
        ax.set_xlim(-110, 40) if cols == (1, 2) else ax.set_xlim(-60, 60)
        ax.legend(fontsize=7, loc="lower left", markerscale=4)
    fig.suptitle("BodyParts3D vertebral arteries before and after the sub-cranial AP correction")
    fig.tight_layout(); fp = out_dir / "vertebral_overlay.png"; fig.savefig(fp, dpi=120); plt.close(fig)
    written.append(str(fp))

    # --- 3. MRA overlay -----------------------------------------------------------------------------
    mp = RAW / "mouches_arteries" / "vesselProbabilities.nii.gz"
    if mp.exists():
        img = load_ras(mp); V = np.asanyarray(img.dataobj); Am = img.affine
        ijk = np.argwhere(V >= 30); M = ijk @ Am[:3, :3].T + Am[:3, 3]
        M = M[(M[:, 2] < -15) & (M[:, 1] < 5)]
        cl = mra_midline_centreline()
        fig, axes = plt.subplots(1, 2, figsize=(12, 6))
        for ax, cols, ttl in ((axes[0], (0, 2), "posterior view (x-z)"), (axes[1], (1, 2), "lateral view (y-z)")):
            ax.plot(M[:, cols[0]], M[:, cols[1]], ".", ms=1, color="#C8C8C8", alpha=0.5, label="MRA atlas (p >= 30%)")
            if cl is not None:
                ax.plot(cl[:, 1] if cols[0] == 0 else cl[:, 2], cl[:, 0], "-", color="#2F4C8F", lw=1.4, label="MRA midline centreline")
            for s in ("l", "r"):
                ax.plot(before[s][:, cols[0]], before[s][:, cols[1]], ".", ms=1.2, color="#9A9A9A", alpha=0.6,
                        label="BP3D vertebral, before" if s == "l" else None)
                ax.plot(after[s][:, cols[0]], after[s][:, cols[1]], ".", ms=1.6, color="#B0302A",
                        label="BP3D vertebral, after" if s == "l" else None)
            if bas is not None:
                ax.plot(bas[:, cols[0]], bas[:, cols[1]], ".", ms=1.6, color="#E0533F", label="BP3D basilar")
            j = vbj["junction"]
            ax.plot([j[cols[0]]], [j[cols[1]]], "*", ms=11, color="#111")      # annotated, not in the legend
            ax.annotate("vertebrobasilar junction", (j[cols[0]] + 2, j[cols[1]] + 1), fontsize=7, color="#111")
            ax.set_title(ttl); ax.set_aspect("equal"); ax.set_ylim(-90, -15); ax.grid(alpha=0.25)
            ax.legend(fontsize=7, markerscale=5, loc="lower left")
        d = vbj.get("distance_to_mra_mm")
        fig.suptitle(f"corrected vertebral arteries on the Mouches MRA atlas -- vertebrobasilar junction "
                     f"{d} mm from the MRA midline vessel" if d is not None else "corrected vertebral arteries on the MRA atlas")
        fig.tight_layout(); fp = out_dir / "vertebral_mra.png"; fig.savefig(fp, dpi=120); plt.close(fig)
        written.append(str(fp))
    return written


def main_post_correction(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="atlas-register --post-correction")
    ap.add_argument("--post-correction", action="store_true")
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--no-plots", action="store_true")
    a = ap.parse_args(argv)
    out_path = CONFIG / "bp3d_to_mni.json"
    cfg = json.loads(out_path.read_text())
    T = np.array(cfg["matrix"])
    profile = measure_brainstem(T) + measure_vertebral(T)
    profile.sort(key=lambda r: r["z_src_mm"])
    if not any(r.get("in_fit") for r in profile):
        raise SystemExit("no fittable measurements: run atlas-bp3d-select and "
                         "blender/.venv/bin/python blender/dump_vertebral_ap.py first")
    knots, stats = fit_post_correction(profile)
    pc = {"enabled": True, "model": "monotone-cubic-ramp", "axis": "y",
          "space": "BodyParts3D source millimetres (+x subject left, +y posterior, +z up)",
          "applies_to": list(PC_APPLY), "knots": knots, "knot_labels": list(PC_KNOT_LABEL),
          "anchor_zero_mm": knots[-1][0], "full_dy_mm": max(v for _, v in knots), "fit": stats,
          "references": sorted({r["ref"] for r in profile if r.get("in_fit")}),
          "notes": ("Anteroposterior ramp added to MNI y after the affine, as a function of BodyParts3D "
                    "source height: a Fritsch-Carlson monotone cubic Hermite through the knots, clamped "
                    "outside them, so it is exactly 0.0 at and above the vertebrobasilar junction (the "
                    "basilar therefore does not move and the vertebral arteries stay welded to it) and "
                    "exactly the bottom knot's value below C6.  Applied only to the bp3d_selection.yaml "
                    "entries flagged `postCorrection: true`. " + CAROTID_NOTE)}
    rows, gate = mesh_displacements(T, pc)
    vbj = vertebrobasilar_junction(T, pc)
    vbj_before = vertebrobasilar_junction(T, None)
    from .bp3d import ap_shift
    prof_rows = []
    for r in profile:
        if "dy_mm" not in r:
            prof_rows.append(r); continue
        f = float(ap_shift(np.array([r["z_src_mm"]]), pc)[0])
        prof_rows.append(r | {"fit_mm": round(f, 2), "residual_mm": round(r["dy_mm"] - f, 2)})
    sub = [r for r in prof_rows if r.get("in_fit")]
    report = {"knots": knots, "knot_labels": list(PC_KNOT_LABEL), "fit": stats, "profile": prof_rows,
              "subcranial": {"n": len(sub),
                             "before_max_abs_mm": round(max(abs(r["dy_mm"]) for r in sub), 2),
                             "after_max_abs_mm": round(max(abs(r["residual_mm"]) for r in sub), 2),
                             "before_mean_abs_mm": round(float(np.mean([abs(r["dy_mm"]) for r in sub])), 2),
                             "after_mean_abs_mm": round(float(np.mean([abs(r["residual_mm"]) for r in sub])), 2)},
              "cranial_gate": gate, "meshes": rows,
              "vertebrobasilar_junction": {"before": vbj_before, "after": vbj},
              "carotid": CAROTID_NOTE}
    (WORK / "bp3d").mkdir(parents=True, exist_ok=True)
    (WORK / "bp3d" / "post_correction.json").write_text(json.dumps(report, indent=1))
    print("sub-cranial anteroposterior correction (dy added to MNI y, + = anterior)")
    print("  knots (BodyParts3D source mm):")
    for (kz, kv), lbl in zip(knots, PC_KNOT_LABEL):
        print(f"    {kz:8.1f}  {kv:+7.2f} mm   {lbl}")
    print(f"  fit: {stats['samples']} slabs, rms {stats['rms_mm']} mm, max {stats['max_abs_mm']} mm")
    print(f"  sub-cranial offset: max |{report['subcranial']['before_max_abs_mm']}| mm -> "
          f"|{report['subcranial']['after_max_abs_mm']}| mm; mean "
          f"{report['subcranial']['before_mean_abs_mm']} -> {report['subcranial']['after_mean_abs_mm']} mm")
    print(f"  meshes moved: {gate['meshes_moved']}")
    for r in rows:
        if r["max_dy_mm"]:
            print(f"    {r['id']:28s} max {r['max_dy_mm']:5.2f} mm  mean {r['mean_dy_mm']:5.2f} mm")
    print(f"  cranial hard rule ({gate['rule']}): worst {gate['worst_cranial']} -> "
          f"{'PASS' if gate['pass'] else 'FAIL'}")
    print(f"  vertebrobasilar junction {vbj['junction']}, {vbj.get('distance_to_mra_mm')} mm from the MRA "
          f"midline vessel (before: {vbj_before.get('distance_to_mra_mm')} mm); "
          f"{vbj.get('junction_to_basilar_mm')} mm from the basilar's inferior end")
    if not a.no_plots:
        for f in post_correction_figures(T, pc, profile, rows, vbj):
            print("  figure:", f)
    if a.no_write:
        print("--no-write: config not touched"); return
    cfg["post_correction"] = pc
    out_path.write_text(json.dumps(cfg, indent=1))
    print("wrote", out_path, "(post_correction)")
