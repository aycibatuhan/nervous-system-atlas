"""Phase 6b: measure the Z-Anatomy midline in MNI space and fit the sub-cranial post-correction.

  atlas-zanatomy-midline [--no-write] [--no-plots]

Why
---
`zanatomy_to_mni.json` is a single 12-dof landmark affine fitted on 31 *brain* landmarks, all of which sit in
a 12 cm band around the diencephalon.  Nothing in that fit constrains the x-from-z shear of the matrix, so the
mapped midline is a plane that drifts away from MNI x = 0 as you go down the body: about -0.5 mm at the
foramen magnum, -1.2 mm at C7, -3.6 mm at T12, -4.2 mm at the conus, -5.2 mm at the sacrum and -12 mm at the
ankle.  Everything below the skull base -- cord, roots, ganglia, cauda equina, sympathetic trunk, plexuses,
limb nerves and the derived meshes built from them -- inherits it.

What is measured
----------------
The Z-Anatomy source is mirror-symmetric to machine precision: over the 1356 `.l`/`.r` object pairs in
work/zanatomy/objects.json the per-slab median of the pair midpoint is 0.000 mm with a 0.000 mm MAD in every
5 cm band from the feet to the vertex, and the bbox x-centre of every true midline object (vertebrae,
intervertebral discs, sacrum, coccyx, cord grey/white matter, cauda equina, occipital bone) is within 0.25 mm
of x = 0.  So the true midline of the model is the source plane x = 0, and its image under the affine is the
plane this module fits.

The model
---------
    dx(p) = -w(p_z) * (ky*p_y + kz*p_z + k0)          p = source point in Z-Anatomy world metres
    w(p_z) = smoothstep((Z_ZERO - p_z) / (Z_ZERO - Z_FULL)), clamped to [0, 1]

`ky, kz, k0` are least-squares-fitted (MAD-clipped) to the measured midline samples, in mm; the fit recovers
the first row of the affine, which is what makes the correction exact rather than approximate.  `w` is a
smoothstep in *source* height, so the ramp is a horizontal plane in the body and not in tilted MNI z: a plain
MNI-z threshold would also catch the orbit and the skull base, which the affine rotates ~23 deg backwards and
therefore pushes below MNI z = -60.  w is exactly 0 at and above the foramen magnum, so every vertex above it
is bit-identical, and exactly 1 below Z_FULL, where the residual midline offset is 0.

The anteroposterior model
-------------------------
The same brain-only affine also leaves the Z-Anatomy brainstem pitched too far back: measured against the MNI
aseg brainstem (label 16), the mid-sagittal AP centre of the Z-Anatomy brainstem matches at the
pontomesencephalic junction and then falls behind it continuously -- ~3 mm at mid-pons, ~9 mm at the
pontomedullary junction, ~16 mm at the obex and ~22 mm at the cervicomedullary junction, where the Z-Anatomy
cord sits at MNI y ~ -67 against an MNI cord at y ~ -45 and visibly emerges behind the occiput.  It is not a
sub-cranial drift like the x shear -- it starts in the pons -- so it cannot be fixed below the foramen magnum
alone without tearing the cord off the medulla.

    dy(p) = ramp(p_z)                                 p = source point in Z-Anatomy world metres

`ramp` is a Fritsch-Carlson monotone cubic Hermite through six anatomical knots (pontomesencephalic junction,
mid-pons, pontomedullary junction, obex, foramen magnum, cervicomedullary junction) with clamped zero end
tangents, so it joins the untouched region above and the constant region below without a crease.  The knot
*heights* are anatomy (read off the Z-Anatomy objects); the knot *values* are least-squares-fitted to the
measured per-slab profile.  It is exactly 0 at and above the pontomesencephalic junction, so the midbrain,
diencephalon and the whole forebrain are bit-identical, and constant below the cervicomedullary junction, so
the cord's own shape and slope (~21 deg, which already matches the MNI brainstem axis) are preserved and the
whole sub-cranial body inherits one rigid AP translation.

The measurement needs the Z-Anatomy brainstem surfaces, which the atlas does not ship (the published brainstem
is the MNI aseg one).  `blender/dump_brainstem_ap.py` dumps them to work/zanatomy/brainstem_dump.npz; without
that file the AP knots already in the config are kept and only the x model is refitted.
"""
from __future__ import annotations

import argparse
import json
import re

import numpy as np

from .paths import CONFIG, RAW, WORK

ZW = WORK / "zanatomy"
MID = ZW / "midline"
CORD_PLY = ZW / "objs" / "spinal-white-columns.ply"
ASEG = RAW / "mni_aseg" / "tpl-MNI152NLin2009cAsym_res-01_seg-aseg_dseg.nii.gz"
T1W = RAW / "mni_t1w" / "tpl-MNI152NLin2009cAsym_res-01_T1w.nii.gz"

# Blend band in Z-Anatomy world metres (+z up).  Z_ZERO is the foramen magnum (the `Foramen magnum.j` label
# anchor spans z 1.5505-1.5561); Z_FULL is 30 mm lower, at the C2/C3 disc (z 1.5197-1.5253).
Z_ZERO = 1.5505
Z_FULL = 1.5205

# --- anteroposterior model ------------------------------------------------------------------------------
BS_DUMP = ZW / "brainstem_dump.npz"                 # written by blender/dump_brainstem_ap.py
# Z-Anatomy objects whose mid-sagittal silhouette defines the brainstem/cord AP axis, top to bottom.
AP_REF_OBJECTS = ("Midbrain.l", "Midbrain.r", "Pons.l", "Pons.r", "Medulla oblongata.l",
                  "Medulla oblongata.r", "White matter of spinal cord")
AP_SLAB_M = 0.0020        # measurement slab thickness in source metres (~2.1 mm of MNI z)
AP_XW_MM = 3.0            # mid-sagittal half-width used for the silhouette centre, both sides
AP_MEAS_TOP_M = 1.6130    # measure from the upper midbrain ...
AP_MEAS_BOT_M = 1.5410    # ... down to just below the cervicomedullary junction
# Knot heights in Z-Anatomy world metres, ascending.  All six are read off the source objects:
#   1.5430  cervicomedullary junction, just below the top of `White matter of spinal cord` (z 1.5452)
#   1.5505  foramen magnum (the `Foramen magnum.j` label anchor, z 1.5505-1.5561)
#   1.5646  obex -- the caudal tip of the `Fourth ventricle` object
#   1.5770  pontomedullary junction (`Pons` bottom 1.5753, `Medulla oblongata` top 1.5789)
#   1.5890  mid-pons (`Pons` spans 1.5753-1.6030)
#   1.5990  pontomesencephalic junction, just below the `Midbrain` bottom (1.6009): the upper anchor, dy = 0
AP_KNOT_Z = (1.5430, 1.5505, 1.5646, 1.5770, 1.5890, 1.5990)
AP_KNOT_LABEL = ("cervicomedullary junction", "foramen magnum", "obex", "pontomedullary junction",
                 "mid-pons", "pontomesencephalic junction")

# True midline objects in work/zanatomy/objects.json, used as direct midline samples (bbox x-centre).
MIDLINE_OBJECTS = (
    ["White matter of spinal cord", "Anterior horn of spinal cord", "Posterior horn of spinal cord",
     "Cauda equina", "Sacrum", "Coccyx", "Occipital bone", "Sphenoid bone", "Sternum", "Hyoid bone"]
    + [f"Vertebra {v}" for v in ("C3", "C4", "C5", "C6", "C7", "T1", "T2", "T3", "T4", "T5", "T6", "T7",
                                 "T8", "T9", "T10", "T11", "T12", "L1", "L2", "L3", "L4", "L5")]
    + [f"Intervertebral disc {d}" for d in ("C2-C3", "C3-C4", "C4-C5", "C5-C6", "C6-C7", "C7-T1", "T1-T2",
                                            "T2-T3", "T3-T4", "T4-T5", "T5-T6", "T6-T7", "T7-T8", "T8-T9",
                                            "T9-T10", "T10-T11", "T11-T12", "T12-L1", "L1-L2", "L2-L3",
                                            "L3-L4", "L4-L5", "L5-S1")]
)

# Named levels for the reported offset profile: (label, source object used for the z level)
LEVELS = [
    ("foramen magnum", "Foramen magnum.j"),
    ("C4 vertebra", "Vertebra C4"),
    ("C7 vertebra", "Vertebra C7"),
    ("T1 vertebra", "Vertebra T1"),
    ("T6 vertebra", "Vertebra T6"),
    ("T10 vertebra", "Vertebra T10"),
    ("T12 vertebra", "Vertebra T12"),
    ("conus (cord tip)", None),          # filled from the cord PLY
    ("L5 vertebra", "Vertebra L5"),
    ("sacrum", "Sacrum"),
    ("coccyx", "Coccyx"),
]


# ---------------------------------------------------------------- the correction itself
def smoothstep(t: np.ndarray) -> np.ndarray:
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def blend_weight(z_src: np.ndarray, pc: dict) -> np.ndarray:
    b = pc["blend"]
    return smoothstep((b["z_zero_m"] - np.asarray(z_src, float)) / (b["z_zero_m"] - b["z_full_m"]))


def mono_cubic(x, y, xq) -> np.ndarray:
    """Fritsch-Carlson monotone cubic Hermite with clamped (zero) end tangents; `x` strictly ascending.

    `xq` is clamped to [x[0], x[-1]], so the curve is exactly y[0] below the first knot and exactly y[-1]
    above the last one -- which is what makes "nothing above the upper anchor moves" bit-exact."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    xq = np.clip(np.asarray(xq, float), x[0], x[-1])
    h = np.diff(x)
    d = np.diff(y) / h
    m = np.zeros_like(y)
    if len(x) > 2:
        a, b, h0, h1 = d[:-1], d[1:], h[:-1], h[1:]
        w = (2 * h0 + h1) * b + (h0 + 2 * h1) * a
        m[1:-1] = np.where((a * b > 0) & (w != 0), 3 * (h0 + h1) * a * b / np.where(w == 0, 1.0, w), 0.0)
    i = np.clip(np.searchsorted(x, xq) - 1, 0, len(x) - 2)
    t = (xq - x[i]) / h[i]
    t2, t3 = t * t, t * t * t
    return ((2 * t3 - 3 * t2 + 1) * y[i] + (t3 - 2 * t2 + t) * h[i] * m[i]
            + (-2 * t3 + 3 * t2) * y[i + 1] + (t3 - t2) * h[i] * m[i + 1])


def ap_shift(z_src: np.ndarray, ap: dict | None) -> np.ndarray:
    """+y (anterior) shift in MNI mm for each source height, from the `post_correction.ap` knots."""
    z_src = np.asarray(z_src, float)
    if not ap or not ap.get("enabled", True):
        return np.zeros(z_src.shape)
    k = np.asarray(ap["knots"], float)
    return mono_cubic(k[:, 0], k[:, 1], z_src)


def correct(src: np.ndarray, mni: np.ndarray, pc: dict | None) -> np.ndarray:
    """Apply the midline post-correction. `src` = Z-Anatomy metres, `mni` = the affine image, mm.

    Returns a new array; `mni` is not modified.  With `pc` None this is the identity.  x: for vertices at or
    above the foramen magnum the blend weight is exactly 0.0, so the returned x is bit-identical to the input.
    y: for vertices at or above the pontomesencephalic anchor the ramp is exactly 0.0, likewise."""
    out = np.array(mni, float, copy=True)
    if not pc or not pc.get("enabled", True):
        return out
    src = np.asarray(src, float)
    k = pc["dx_mm"]
    drift = k["ky"] * src[:, 1] + k["kz"] * src[:, 2] + k["k0"]
    out[:, 0] += -blend_weight(src[:, 2], pc) * drift
    out[:, 1] += ap_shift(src[:, 2], pc.get("ap"))
    return out


def load() -> dict | None:
    cfg = json.loads((CONFIG / "zanatomy_to_mni.json").read_text())
    return cfg.get("post_correction")


def transform(src: np.ndarray, T: np.ndarray, pc: dict | None) -> np.ndarray:
    """Z-Anatomy world metres -> corrected MNI mm (the full map used by every Z-Anatomy consumer)."""
    src = np.asarray(src, float)
    return correct(src, src @ T[:3, :3].T + T[:3, 3], pc)


# ---------------------------------------------------------------- measurement
def midline_samples(objects: list[dict]) -> tuple[np.ndarray, list[str]]:
    """Measured midline points in Z-Anatomy world metres, one row per sample: (x_mid, y, z)."""
    rows, names = [], []
    by: dict[str, dict[str, dict]] = {}
    for o in objects:
        m = re.match(r"^(.*)\.(l|r)$", o["name"])
        if m:
            by.setdefault(m.group(1), {})[m.group(2)] = o
    for base, v in by.items():
        if "l" not in v or "r" not in v:
            continue
        bl, br = np.array(v["l"]["bbox"], float), np.array(v["r"]["bbox"], float)
        x = ((bl[0, 0] + br[1, 0]) + (bl[1, 0] + br[0, 0])) / 4.0
        rows.append([x, (bl[:, 1].mean() + br[:, 1].mean()) / 2, (bl[:, 2].mean() + br[:, 2].mean()) / 2])
        names.append(f"pair:{base}")
    byname = {o["name"]: o for o in objects}
    for n in MIDLINE_OBJECTS:
        o = byname.get(n)
        if o is None:
            continue
        b = np.array(o["bbox"], float)
        rows.append([b[:, 0].mean(), b[:, 1].mean(), b[:, 2].mean()])
        names.append(f"midline:{n}")
    # per-slab centre of the cord surface: the one sub-cranial midline structure we have real vertices for
    if CORD_PLY.exists():
        import trimesh
        V = np.asarray(trimesh.load(str(CORD_PLY), force="mesh", process=False).vertices, float)
        for z0 in np.arange(V[:, 2].min(), V[:, 2].max(), 0.02):
            s = (V[:, 2] >= z0) & (V[:, 2] < z0 + 0.02)
            if s.sum() < 20:
                continue
            rows.append([(V[s, 0].min() + V[s, 0].max()) / 2, V[s, 1].mean(), V[s, 2].mean()])
            names.append(f"cord:z{z0:.2f}")
    return np.array(rows, float), names


def fit_plane(S: np.ndarray, X: np.ndarray, clip: float = 4.0) -> tuple[np.ndarray, np.ndarray]:
    """Least squares X ~ ky*y + kz*z + k0 with one MAD clip; returns (coefficients, keep mask)."""
    A = np.column_stack([S[:, 1], S[:, 2], np.ones(len(S))])
    k = np.linalg.lstsq(A, X, rcond=None)[0]
    r = X - A @ k
    mad = np.median(np.abs(r - np.median(r)))
    keep = np.abs(r - np.median(r)) <= max(clip * mad, 0.5)
    if keep.sum() >= 20:
        k = np.linalg.lstsq(A[keep], X[keep], rcond=None)[0]
    return k, keep


# ---------------------------------------------------------------- anteroposterior measurement and fit
def aseg_brainstem() -> np.ndarray:
    """MNI aseg Brain-Stem (label 16) voxel centres in MNI RAS mm."""
    import nibabel as nib
    img = nib.load(str(ASEG))
    d = np.rint(np.asanyarray(img.dataobj)).astype(np.int32)
    return np.argwhere(d == 16) @ img.affine[:3, :3].T + img.affine[:3, 3]


def _silhouette_y(P: np.ndarray, sel: np.ndarray) -> float:
    """AP centre of a mid-sagittal slab: midway between its anterior and posterior surface."""
    y = P[sel, 1]
    return float((y.min() + y.max()) / 2.0)


def t1_cord_y(zc: float, y0: float, half: float = 12.0) -> float | None:
    """Crude mid-sagittal cord centre from the MNI T1 below the caudal end of the aseg brainstem label.

    Only the last few millimetres of the volume need this, and only for the report -- the fit uses the aseg
    label alone.  The cord is the bright band in the canal, so take the intensity-weighted centroid of the
    upper part of the normalised y profile at x = 0, in a +/- `half` mm window around `y0`, the reference
    position one slab higher; without that seed the suboccipital muscles win the profile."""
    import nibabel as nib
    img = nib.load(str(T1W))
    vol = np.asanyarray(img.dataobj).astype(float)
    aff = img.affine
    k = int(round(zc - aff[2, 3]))
    if not (0 <= k < vol.shape[2]):
        return None
    i0 = int(round(0.0 - aff[0, 3]))
    prof = vol[i0 - 2:i0 + 3, :, k].mean(0)
    yy = np.arange(len(prof)) + aff[1, 3]
    m = (yy >= y0 - half) & (yy <= y0 + half)
    q = prof[m] - prof[m].min()
    if q.max() <= 0:
        return None
    q = q / q.max()
    sel = q > 0.6
    return float((yy[m][sel] * q[sel]).sum() / q[sel].sum()) if sel.sum() >= 3 else None


def measure_ap(T: np.ndarray) -> list[dict]:
    """Per source slab: the Z-Anatomy brainstem/cord AP centre in MNI, the MNI reference, and the gap.

    Both sides are measured the same way -- the midpoint of the anterior and posterior surface of the
    mid-sagittal (|x| <= 3 mm) slab -- so the number is a silhouette centre, not a density-weighted centroid,
    and does not care that one side is a surface mesh and the other a voxel label.  `dy_mm` is the shift the
    Z-Anatomy geometry needs (positive = move anterior)."""
    if not (BS_DUMP.exists() and ASEG.exists()):
        return []
    D = np.load(BS_DUMP)
    have = [n for n in AP_REF_OBJECTS if n in D]
    S = np.vstack([D[n] for n in have])
    P = S @ T[:3, :3].T + T[:3, 3]
    W = aseg_brainstem()
    zmin = float(W[:, 2].min())
    rows = []
    last_ref_y = None
    for z0 in np.arange(AP_MEAS_TOP_M, AP_MEAS_BOT_M - 1e-9, -AP_SLAB_M):
        sel = (S[:, 2] >= z0 - AP_SLAB_M) & (S[:, 2] < z0) & (np.abs(P[:, 0]) <= AP_XW_MM)
        if sel.sum() < 8:
            continue
        zc = float(P[sel, 2].mean())
        row = {"z_src_m": round(z0 - AP_SLAB_M / 2, 4), "z_mni_mm": round(zc, 1),
               "zanatomy_y_mm": round(_silhouette_y(P, sel), 2), "n": int(sel.sum())}
        ref = (np.abs(W[:, 2] - zc) < 1.0) & (np.abs(W[:, 0]) <= AP_XW_MM)
        # only slabs whose whole height is inside the label: the caudal one is cut by the MNI field of view
        if ref.sum() >= 8 and zc - 1.0 >= zmin:
            last_ref_y = _silhouette_y(W, ref)
            row |= {"mni_y_mm": round(last_ref_y, 2), "mni_n": int(ref.sum()), "ref": "aseg-brainstem"}
        else:
            y = t1_cord_y(zc, last_ref_y) if last_ref_y is not None else None
            if y is None:
                rows.append(row)
                continue
            last_ref_y = y
            row |= {"mni_y_mm": round(y, 2), "mni_n": 0, "ref": "t1-cord-estimate"}
        row["dy_mm"] = round(row["mni_y_mm"] - row["zanatomy_y_mm"], 2)
        rows.append(row)
    return rows


def fit_ap(profile: list[dict]) -> tuple[list[list[float]], dict]:
    """Least-squares fit of the six knot values to the measured profile, monotone and anchored at zero.

    The knot heights are fixed anatomy; only their values move, parameterised as a cumulative sum of
    non-negative increments from the upper anchor down, which makes the ramp monotone by construction."""
    from scipy.optimize import minimize
    pts = [(r["z_src_m"], r["dy_mm"]) for r in profile
           if r.get("ref") == "aseg-brainstem" and AP_KNOT_Z[0] <= r["z_src_m"] <= AP_KNOT_Z[-1]]
    Z = np.array([a for a, _ in pts])
    Y = np.array([b for _, b in pts])
    kz = np.array(AP_KNOT_Z, float)

    def values(q):
        return np.concatenate([[0.0], np.cumsum(np.abs(q))])[::-1]

    def cost(q):
        return float(np.mean((Y - mono_cubic(kz, values(q), Z)) ** 2))

    q0 = np.full(len(kz) - 1, (Y.max() if len(Y) else 20.0) / (len(kz) - 1))
    res = minimize(cost, q0, method="Nelder-Mead",
                   options={"maxiter": 40000, "maxfev": 40000, "xatol": 1e-7, "fatol": 1e-10})
    v = values(res.x)
    r = Y - mono_cubic(kz, v, Z)
    stats = {"samples": int(len(Y)), "rms_mm": round(float(np.sqrt((r ** 2).mean())), 3),
             "mean_abs_mm": round(float(np.abs(r).mean()), 3), "max_abs_mm": round(float(np.abs(r).max()), 3)}
    return [[round(float(a), 4), round(float(b), 2)] for a, b in zip(kz, v)], stats


def ap_residuals(profile: list[dict], ap: dict) -> tuple[list[dict], dict]:
    """Measured profile with the fitted ramp and the residual that is left after applying it."""
    rows, cmj, cmj_t1 = [], [], []
    for r in profile:
        if "dy_mm" not in r:
            continue
        fit = float(ap_shift(np.array([r["z_src_m"]]), ap)[0])
        row = r | {"fit_mm": round(fit, 2), "residual_mm": round(r["dy_mm"] - fit, 2)}
        rows.append(row)
        if r["z_mni_mm"] <= -62.0:
            (cmj if r.get("ref") == "aseg-brainstem" else cmj_t1).append(abs(row["residual_mm"]))
    out = {"band": "MNI z <= -62 mm (cervicomedullary junction)", "reference": "aseg-brainstem",
           "n": len(cmj), "max_abs_mm": round(max(cmj), 2) if cmj else None,
           "mean_abs_mm": round(float(np.mean(cmj)), 2) if cmj else None}
    if cmj_t1:   # the last few slabs, below the caudal end of the aseg label: reported, not gated
        out["t1_estimate"] = {"n": len(cmj_t1), "max_abs_mm": round(max(cmj_t1), 2),
                              "mean_abs_mm": round(float(np.mean(cmj_t1)), 2)}
    return rows, out


def mesh_ap_displacements(T: np.ndarray, pc: dict) -> list[dict]:
    """How far every exported Z-Anatomy object moves in y, and the proof that nothing above the anchor does."""
    import trimesh
    anchor = float(pc["ap"]["knots"][-1][0])
    rows, worst_above = [], 0.0
    for path in sorted((ZW / "objs").glob("*.ply")):
        try:
            V = np.asarray(trimesh.load(str(path), force="mesh", process=False).vertices, float)
        except Exception:  # noqa: BLE001
            continue
        if not len(V):
            continue
        dy = ap_shift(V[:, 2], pc["ap"])
        above = V[:, 2] >= anchor
        if above.any():
            worst_above = max(worst_above, float(np.abs(dy[above]).max()))
        if float(np.abs(dy).max()) < 0.005:
            continue
        rows.append({"mesh": path.stem, "max_dy_mm": round(float(dy.max()), 2),
                     "mean_dy_mm": round(float(dy.mean()), 2),
                     "fraction_moved": round(float((dy > 0.005).mean()), 3)})
    rows.sort(key=lambda r: -r["max_dy_mm"])
    return rows, worst_above


def cn_check(T: np.ndarray, pc: dict) -> list[dict]:
    """Where the Z-Anatomy cranial-nerve *roots* sit, before and after, against both brainstems.

    The root zone of each nerve is the part of its mesh within 2 mm of its Z-Anatomy parent surface (pons for
    V-VIII, medulla for IX-XII).  Two numbers per nerve: the gap from that zone to the Z-Anatomy parent, which
    must not change (root and parent sit at the same source height and move together), and the gap from it to
    the MNI aseg brainstem, which is what the correction is for -- IX-XII start ~10 mm behind the MNI medulla
    and should end up on it.  Measuring the root zone rather than the whole nerve matters: a whole peripheral
    course wanders past the brainstem somewhere and its minimum distance is ~0 either way."""
    import trimesh
    from scipy.spatial import cKDTree
    if not (BS_DUMP.exists() and ASEG.exists()):
        return []
    D = np.load(BS_DUMP)
    W = cKDTree(aseg_brainstem())
    parents = {}
    for tag, keys in (("pons", ("Pons.l", "Pons.r")), ("medulla", ("Medulla oblongata.l", "Medulla oblongata.r"))):
        V = np.vstack([D[k] for k in keys if k in D])
        parents[tag] = (cKDTree(V), cKDTree(V @ T[:3, :3].T + T[:3, 3]), cKDTree(transform(V, T, pc)))
    PARENT = {"05": "pons", "06": "pons", "07": "pons", "08": "pons",
              "09": "medulla", "10": "medulla", "11": "medulla", "12": "medulla"}
    rows = []
    for path in sorted((ZW / "objs").glob("cn-*.ply")):
        tag = PARENT.get(path.stem.split("-")[1])
        if tag is None:
            continue
        V = np.asarray(trimesh.load(str(path), force="mesh", process=False).vertices, float)
        if not len(V):
            continue
        src_tree, tree0, tree1 = parents[tag]
        root = V[src_tree.query(V)[0] <= 0.002]              # within 2 mm of the parent surface, in metres
        row = {"mesh": path.stem, "parent": tag, "root_verts": int(len(root)),
               "max_dy_mm": round(float(ap_shift(V[:, 2], pc["ap"]).max()), 2)}
        if len(root) < 3:
            row["note"] = "no vertex within 2 mm of the parent surface (this object is not a root)"
            rows.append(row)
            continue
        for tag2, tree, P in (("before", tree0, root @ T[:3, :3].T + T[:3, 3]),
                              ("after", tree1, transform(root, T, pc))):
            row |= {f"root_centroid_{tag2}": [round(float(x), 1) for x in P.mean(0)],
                    f"gap_to_zanatomy_parent_{tag2}_mm": round(float(tree.query(P)[0].mean()), 2),
                    f"gap_to_mni_brainstem_{tag2}_mm": round(float(W.query(P)[0].mean()), 2)}
        rows.append(row)
    return rows


def ap_landmarks(T: np.ndarray, pc: dict) -> dict:
    """Corresponding-structure cross-checks the silhouette profile does not use, before and after.

    Reported, not fitted: the Z-Anatomy / MNI fourth ventricle (an AP *and* vertical landmark pair), and the
    Z-Anatomy brainstem centroids against the aseg brainstem at their own height."""
    import nibabel as nib
    out: dict = {}
    if not ASEG.exists():
        return out
    img = nib.load(str(ASEG))
    d = np.rint(np.asanyarray(img.dataobj)).astype(np.int32)
    aff = img.affine
    W = aseg_brainstem()
    if BS_DUMP.exists():
        D = np.load(BS_DUMP)
        if "Fourth ventricle" in D:
            V4 = np.argwhere(d == 15) @ aff[:3, :3].T + aff[:3, 3]
            src = D["Fourth ventricle"]
            for tag, use in (("before", None), ("after", pc)):
                Z4 = correct(src, src @ T[:3, :3].T + T[:3, 3], use)
                a, b = Z4[np.abs(Z4[:, 0]) < 2], V4[np.abs(V4[:, 0]) < 2]
                ka = a[:, 2] < np.percentile(a[:, 2], 2)
                kb = b[:, 2] < np.percentile(b[:, 2], 2)
                out.setdefault("fourth_ventricle", {})[tag] = {
                    "obex_zanatomy_y_z": [round(float(a[ka, 1].mean()), 1), round(float(a[ka, 2].mean()), 1)],
                    "obex_mni_y_z": [round(float(b[kb, 1].mean()), 1), round(float(b[kb, 2].mean()), 1)],
                    "centroid_zanatomy": [round(float(x), 1) for x in Z4.mean(0)],
                    "centroid_mni": [round(float(x), 1) for x in V4.mean(0)]}
    lmp = ZW / "landmarks.json"
    if lmp.exists():
        lm = json.loads(lmp.read_text())
        for base in ("Midbrain", "Pons", "Medulla oblongata"):
            pts = [np.array(v["centroid_m"]) for k, v in lm.items() if k.split(".")[0] == base]
            if not pts:
                continue
            src = np.mean(pts, axis=0)[None, :]
            row = {"structure": base}
            for tag, use in (("before", None), ("after", pc)):
                c = correct(src, src @ T[:3, :3].T + T[:3, 3], use)[0]
                sel = np.abs(W[:, 2] - c[2]) < 3.0
                if sel.sum() < 10:
                    continue
                row |= {"z_mni_mm": round(float(c[2]), 1), f"zanatomy_y_{tag}": round(float(c[1]), 1),
                        "mni_y_mm": round(float(W[sel, 1].mean()), 1),
                        f"offset_{tag}_mm": round(float(c[1] - W[sel, 1].mean()), 1)}
            out.setdefault("brainstem_centroids", []).append(row)
    return out


# ---------------------------------------------------------------- figures
def figures(T: np.ndarray, pc: dict, S: np.ndarray, X: np.ndarray, keep: np.ndarray,
            ap: dict | None = None) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import nibabel as nib
    import trimesh
    MID.mkdir(parents=True, exist_ok=True)
    written = []

    def load_src(name):
        p = ZW / "objs" / f"{name}.ply"
        return np.asarray(trimesh.load(str(p), force="mesh", process=False).vertices, float) if p.exists() else None

    # --- 1. the measured midline profile, before and after
    Sk, Xk = S[keep], X[keep]
    Z = (Sk @ T[:3, :3].T + T[:3, 3])[:, 2]
    Xa = correct(Sk, Sk @ T[:3, :3].T + T[:3, 3], pc)[:, 0]
    fig, ax = plt.subplots(1, 2, figsize=(11, 6), sharey=True)
    for a, xs, ttl in ((ax[0], Xk, "before"), (ax[1], Xa, "after")):
        a.axvline(0, color="0.3", lw=1)
        a.scatter(xs, Z, s=6, c=np.where(Sk[:, 2] >= Z_ZERO, "#2F4C8F", "#B4553F"), alpha=0.7)
        a.axhline(float((np.array([0, 0.03, Z_ZERO]) @ T[:3, :3].T + T[:3, 3])[2]), color="#3A7D44", ls="--", lw=1)
        a.set_xlim(-14, 14); a.set_xlabel("MNI x of the measured midline (mm)"); a.set_title(ttl)
        a.grid(alpha=0.25)
    ax[0].set_ylabel("MNI z (mm)")
    fig.suptitle("Z-Anatomy midline in MNI space (blue = above the foramen magnum, red = below;\n"
                 "dashed = foramen magnum plane)")
    fig.tight_layout(); p = MID / "profile.png"; fig.savefig(p, dpi=120); plt.close(fig)
    written.append(str(p))

    # --- 2. coronal MNI T1 at y = -40 with the cord / roots / trunk contours projected on (x, z)
    if T1W.exists():
        img = nib.load(str(T1W))
        vol = np.asanyarray(img.dataobj).astype(float)
        aff = img.affine
        j = int(round(-40.0 - aff[1, 3]))
        sl = vol[:, j, :].T
        ext = [aff[0, 3], aff[0, 3] + vol.shape[0], aff[2, 3], aff[2, 3] + vol.shape[2]]
        fig, ax = plt.subplots(1, 2, figsize=(11, 7), sharey=True)
        parts = [("spinal-white-columns", "#B4553F"), ("spinal-roots-anterior-l", "#D6BFA2"),
                 ("spinal-roots-anterior-r", "#D6BFA2"), ("sympathetic-trunk-l", "#E8A33D"),
                 ("sympathetic-trunk-r", "#E8A33D"), ("cauda-equina", "#7A5C3E")]
        for a, use_pc, ttl in ((ax[0], None, "before"), (ax[1], pc, "after")):
            a.imshow(sl, cmap="gray", origin="lower", extent=ext, aspect="equal", vmax=np.percentile(sl, 99.5))
            a.axvline(0, color="#3A7D44", lw=0.8, ls="--")
            for name, col in parts:
                V = load_src(name)
                if V is None:
                    continue
                P = transform(V, T, use_pc)
                a.scatter(P[:, 0], P[:, 2], s=0.4, c=col, alpha=0.5, linewidths=0)
            a.set_xlim(-45, 45); a.set_ylim(-220, 40); a.set_title(ttl); a.set_xlabel("MNI x (mm)")
        ax[0].set_ylabel("MNI z (mm)")
        fig.suptitle("Coronal MNI T1 at y = -40 with the cord, roots, sympathetic trunk and cauda equina\n"
                     "projected on (x, z); green dashed = MNI midline")
        fig.tight_layout(); p = MID / "coronal_y-40.png"; fig.savefig(p, dpi=120); plt.close(fig)
        written.append(str(p))

    # --- 3. axial cross sections at C4 and T10
    byname = {o["name"]: o for o in json.loads((ZW / "objects.json").read_text())}
    for lvl, obj in (("C4", "Vertebra C4"), ("T10", "Vertebra T10")):
        zc = float(np.array(byname[obj]["bbox"], float)[:, 2].mean())
        fig, ax = plt.subplots(1, 2, figsize=(10, 5), sharey=True)
        for a, use_pc, ttl in ((ax[0], None, "before"), (ax[1], pc, "after")):
            for name, col in (("spinal-white-columns", "#B4553F"), ("spinal-grey-anterior-horn", "#C8A79A"),
                              ("spinal-roots-anterior-l", "#D6BFA2"), ("spinal-roots-anterior-r", "#D6BFA2"),
                              ("spinal-roots-posterior-l", "#8C7A5E"), ("spinal-roots-posterior-r", "#8C7A5E"),
                              ("sympathetic-trunk-l", "#E8A33D"), ("sympathetic-trunk-r", "#E8A33D")):
                V = load_src(name)
                if V is None:
                    continue
                s = np.abs(V[:, 2] - zc) < 0.006
                if s.sum() < 3:
                    continue
                P = transform(V[s], T, use_pc)
                a.scatter(P[:, 0], P[:, 1], s=3, c=col, alpha=0.8, linewidths=0)
            a.axvline(0, color="#3A7D44", lw=0.8, ls="--")
            a.set_aspect("equal"); a.grid(alpha=0.25); a.set_title(ttl); a.set_xlabel("MNI x (mm)")
        ax[0].set_ylabel("MNI y (mm)")
        fig.suptitle(f"Axial section at the {lvl} vertebral body (Z-Anatomy z {zc:.3f} m); green dashed = MNI midline")
        fig.tight_layout(); p = MID / f"axial_{lvl.lower()}.png"; fig.savefig(p, dpi=120); plt.close(fig)
        written.append(str(p))

    # --- 4. the anteroposterior correction: mid-sagittal MNI T1 at x = 0, before and after
    D = np.load(BS_DUMP) if BS_DUMP.exists() else None
    if T1W.exists() and ASEG.exists():
        img = nib.load(str(T1W)); vol = np.asanyarray(img.dataobj).astype(float); aff = img.affine
        sl = vol[int(round(0.0 - aff[0, 3])), :, :].T
        ext = [aff[1, 3], aff[1, 3] + vol.shape[1], aff[2, 3], aff[2, 3] + vol.shape[2]]
        W = aseg_brainstem()
        Wm = W[np.abs(W[:, 0]) < 2]
        cordV = load_src("spinal-white-columns")
        fig, ax = plt.subplots(1, 2, figsize=(12, 7), sharey=True)
        for a, use_pc, ttl in ((ax[0], None, "before (affine only)"), (ax[1], pc, "after (affine + AP ramp)")):
            a.imshow(sl, cmap="gray", origin="lower", extent=ext, aspect="equal", vmax=np.percentile(sl, 99.5))
            a.scatter(Wm[:, 1], Wm[:, 2], s=1, c="#2F4C8F", alpha=0.22, linewidths=0, label="MNI aseg brainstem")
            if D is not None:
                for name, col, lab in (("Pons.l", "#3A7D44", "Z-Anatomy pons"),
                                       ("Medulla oblongata.l", "#E8A33D", "Z-Anatomy medulla"),
                                       ("Midbrain.l", "#7A5C3E", "Z-Anatomy midbrain")):
                    if name not in D:
                        continue
                    V = np.vstack([D[name], D[name.replace(".l", ".r")]])
                    P = transform(V, T, use_pc)
                    m = np.abs(P[:, 0]) < 3
                    a.scatter(P[m, 1], P[m, 2], s=1.2, c=col, alpha=0.45, linewidths=0, label=lab)
            if cordV is not None:
                P = transform(cordV, T, use_pc)
                m = P[:, 2] > -130
                a.scatter(P[m, 1], P[m, 2], s=1, c="#B4553F", alpha=0.5, linewidths=0, label="Z-Anatomy cord")
            for z in (-70.0,):
                a.axhline(z, color="#B4553F", ls=":", lw=0.8)
            a.set_xlim(-110, 40); a.set_ylim(-130, 20); a.set_title(ttl, fontsize=10)
            a.set_xlabel("MNI y (mm)")
        ax[0].set_ylabel("MNI z (mm)"); ax[1].legend(loc="lower left", fontsize=7, markerscale=6)
        full = pc.get("ap", {}).get("full_dy_mm")
        fig.suptitle("Mid-sagittal MNI T1 (x = 0): the Z-Anatomy brainstem and cord before and after the AP ramp"
                     + (f"\n(0 at the pontomesencephalic junction, +{full:.1f} mm at and below the CMJ; dotted = MNI z -70)"
                        if full else ""), fontsize=10)
        fig.tight_layout(); p = MID / "ap_cmj.png"; fig.savefig(p, dpi=120); plt.close(fig)
        written.append(str(p))

        # --- 5. axial MNI T1 at z = -60 (lower medulla), before and after
        k = int(round(-60.0 - aff[2, 3]))
        sla = vol[:, :, k].T
        exta = [aff[0, 3], aff[0, 3] + vol.shape[0], aff[1, 3], aff[1, 3] + vol.shape[1]]
        Wa = W[np.abs(W[:, 2] + 60.0) < 1.0]
        fig, ax = plt.subplots(1, 2, figsize=(11, 6), sharey=True)
        for a, use_pc, ttl in ((ax[0], None, "before"), (ax[1], pc, "after")):
            a.imshow(sla, cmap="gray", origin="lower", extent=exta, aspect="equal", vmax=np.percentile(sla, 99.5))
            a.scatter(Wa[:, 0], Wa[:, 1], s=6, c="#2F4C8F", alpha=0.35, linewidths=0, label="MNI aseg brainstem")
            if D is not None and "Medulla oblongata.l" in D:
                V = np.vstack([D["Medulla oblongata.l"], D["Medulla oblongata.r"]])
                P = transform(V, T, use_pc)
                m = np.abs(P[:, 2] + 60.0) < 1.5
                a.scatter(P[m, 0], P[m, 1], s=4, c="#E8A33D", alpha=0.8, linewidths=0, label="Z-Anatomy medulla")
            for name, col, lab in (("cn-09-glossopharyngeal", "#3A7D44", "CN IX"),
                                   ("cn-10-vagus", "#B4553F", "CN X"),
                                   ("cn-12-hypoglossal", "#7A5C3E", "CN XII")):
                V = [load_src(f"{name}-{sd}") for sd in ("l", "r")]
                V = [v for v in V if v is not None]
                if not V:
                    continue
                P = transform(np.vstack(V), T, use_pc)
                m = np.abs(P[:, 2] + 60.0) < 2.5
                a.scatter(P[m, 0], P[m, 1], s=4, c=col, alpha=0.9, linewidths=0, label=lab)
            a.axvline(0, color="#3A7D44", lw=0.6, ls="--")
            a.set_xlim(-60, 60); a.set_ylim(-100, 20); a.set_title(ttl); a.set_xlabel("MNI x (mm)")
        ax[0].set_ylabel("MNI y (mm)"); ax[1].legend(loc="lower left", fontsize=7, markerscale=3)
        fig.suptitle("Axial MNI T1 at z = -60 mm (lower medulla): Z-Anatomy medulla and CN IX/X/XII\n"
                     "against the MNI aseg brainstem, before and after the AP ramp", fontsize=10)
        fig.tight_layout(); p = MID / "ap_axial_z-60.png"; fig.savefig(p, dpi=120); plt.close(fig)
        written.append(str(p))

    # --- 6. the measured AP profile and the fitted ramp
    if ap and ap.get("profile"):
        rows = ap["profile"]
        zs = np.array([r["z_src_m"] for r in rows]); dy = np.array([r["dy_mm"] for r in rows])
        zm = np.array([r["z_mni_mm"] for r in rows]); est = np.array([r["ref"] == "aseg-brainstem" for r in rows])
        g = np.linspace(min(zs) - 0.002, max(zs) + 0.004, 800)
        fig, a = plt.subplots(figsize=(8, 6.5))
        a.plot(ap_shift(g, pc["ap"]), g, color="#2F4C8F", lw=2, label="fitted ramp", zorder=3)
        a.scatter(dy[est], zs[est], s=18, c="#B4553F", label="measured (vs aseg brainstem)", zorder=4)
        if (~est).any():
            a.scatter(dy[~est], zs[~est], s=18, facecolors="none", edgecolors="#B4553F",
                      label="measured (vs T1 cord estimate)", zorder=4)
        for (kz, kv), lbl in zip(ap["knots"], ap["knot_labels"]):
            a.axhline(kz, color="0.75", lw=0.6)
            a.annotate(f"{lbl}  ({kv:.1f} mm)", (0.5, kz), fontsize=7, va="bottom", color="0.35")
        a.set_xlabel("dy needed (mm of MNI y, + = move anterior)"); a.set_ylabel("Z-Anatomy source height (m)")
        c1, c0 = np.polyfit(zs, zm, 1)          # z_mni is very nearly linear in z_src along the brainstem
        sec = a.secondary_yaxis("right", functions=(lambda v: c1 * v + c0, lambda v: (v - c0) / c1))
        sec.set_ylabel("MNI z (mm), approximate")
        a.axhline(ap["knots"][-1][0], color="#2F4C8F", lw=1.0, ls="--")
        a.annotate("above the anchor the affine leaves the Z-Anatomy midbrain\nslightly anterior; not corrected",
                   (-9.5, ap["knots"][-1][0] + 0.0012), fontsize=7, color="#2F4C8F")
        a.grid(alpha=0.25); a.legend(loc="upper left", fontsize=8)
        f = ap["fit"]
        a.set_title(f"Anteroposterior offset of the Z-Anatomy brainstem/cord and the fitted ramp\n"
                    f"(fit rms {f['rms_mm']} mm over {f['samples']} slabs)", fontsize=10)
        fig.tight_layout(); p = MID / "ap_profile.png"; fig.savefig(p, dpi=120); plt.close(fig)
        written.append(str(p))
    return written


# ---------------------------------------------------------------- driver
def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="fit the Z-Anatomy sub-cranial midline correction")
    ap.add_argument("--no-write", action="store_true", help="report only, do not touch the config")
    ap.add_argument("--no-plots", action="store_true")
    a = ap.parse_args(argv)

    cfg = json.loads((CONFIG / "zanatomy_to_mni.json").read_text())
    T = np.array(cfg["matrix"], float)
    objects = json.loads((ZW / "objects.json").read_text())
    S, names = midline_samples(objects)
    X = (S @ T[:3, :3].T + T[:3, 3])[:, 0]                      # MNI x of the measured midline
    k, keep = fit_plane(S, X)
    resid = X - (k[0] * S[:, 1] + k[1] * S[:, 2] + k[2])
    pc = {
        "enabled": True,
        "model": "midline-shear",
        "space": "zanatomy-source-metres",
        "applies_to": "x",
        "dx_mm": {"ky": round(float(k[0]), 6), "kz": round(float(k[1]), 6), "k0": round(float(k[2]), 6)},
        "blend": {"kind": "smoothstep", "z_zero_m": Z_ZERO, "z_full_m": Z_FULL},
        "fit": {"samples": int(len(S)), "used": int(keep.sum()),
                "residual_mean_mm": round(float(np.abs(resid[keep]).mean()), 4),
                "residual_max_mm": round(float(np.abs(resid[keep]).max()), 4)},
        "notes": ("dx = -w(z_src) * (ky*y_src + kz*z_src + k0), applied to MNI x after the affine; y_src/z_src "
                  "are Z-Anatomy world metres and w is a smoothstep that is exactly 0 at and above the foramen "
                  "magnum (z_src >= z_zero_m) and exactly 1 below z_full_m. Fitted to the mirror-symmetric "
                  "midline of the Z-Anatomy source (1356 .l/.r object pairs plus the vertebral column, cord "
                  "and sacrum); it removes the x-from-z shear of the brain-only landmark affine, which is "
                  "unconstrained below the skull base."),
    }

    # --- anteroposterior: measure the brainstem/cord profile against the MNI aseg brainstem and fit the ramp
    profile = measure_ap(T)
    if profile:
        knots, apfit = fit_ap(profile)
        pc["ap"] = {
            "enabled": True,
            "model": "monotone-cubic-ramp",
            "space": "zanatomy-source-metres",
            "applies_to": "y",
            "knots": knots,
            "knot_labels": list(AP_KNOT_LABEL),
            "anchor_zero_m": knots[-1][0],
            "anchor_full_m": knots[0][0],
            "full_dy_mm": knots[0][1],
            "fit": apfit,
            "notes": ("dy = ramp(z_src), added to MNI y (positive = anterior) after the affine. ramp is a "
                      "Fritsch-Carlson monotone cubic Hermite through the knots with clamped zero end "
                      "tangents, exactly 0.0 at and above anchor_zero_m (the pontomesencephalic junction, so "
                      "the midbrain and everything above it is bit-identical) and exactly full_dy_mm at and "
                      "below anchor_full_m (the cervicomedullary junction, so the cord's own shape and its "
                      "~21 deg slope are preserved). Knot heights are anatomy read off the Z-Anatomy objects; "
                      "knot values are least-squares-fitted to the measured per-slab AP profile of the "
                      "Z-Anatomy brainstem silhouette against the MNI aseg brainstem (label 16)."),
        }
    else:
        old_ap = (cfg.get("post_correction") or {}).get("ap")
        if old_ap:
            pc["ap"] = old_ap
            print(f"  note: no {BS_DUMP.name} -- keeping the AP knots already in the config "
                  f"(run blender/dump_brainstem_ap.py to refit)")
        else:
            print(f"  note: no {BS_DUMP.name} and no AP model in the config: only x is corrected "
                  f"(run blender/dump_brainstem_ap.py)")

    # offset profile at the named levels, before and after
    byname = {o["name"]: o for o in objects}
    levels = []
    import trimesh
    cordV = np.asarray(trimesh.load(str(CORD_PLY), force="mesh", process=False).vertices, float) if CORD_PLY.exists() else None
    for label, obj in LEVELS:
        if obj is None:
            if cordV is None:
                continue
            zc = float(cordV[:, 2].min())
            s = cordV[:, 2] < zc + 0.005
            yc = float(cordV[s, 1].mean())
        else:
            o = byname.get(obj)
            if o is None:
                continue
            b = np.array(o["bbox"], float)
            zc, yc = float(b[:, 2].mean()), float(b[:, 1].mean())
        p = np.array([[0.0, yc, zc]])
        before = float((p @ T[:3, :3].T + T[:3, 3])[0, 0])
        after = float(correct(p, p @ T[:3, :3].T + T[:3, 3], pc)[0, 0])
        levels.append({"level": label, "z_src_m": round(zc, 4),
                       "z_mni_mm": round(float((p @ T[:3, :3].T + T[:3, 3])[0, 2]), 1),
                       "before_mm": round(before, 2), "after_mm": round(after, 2)})

    # residual of every measured sample after the correction
    after_all = correct(S, S @ T[:3, :3].T + T[:3, 3], pc)[:, 0]
    sub = S[:, 2] < Z_FULL
    report = {
        "fit": pc["fit"] | {"ky": pc["dx_mm"]["ky"], "kz": pc["dx_mm"]["kz"], "k0": pc["dx_mm"]["k0"]},
        "blend": pc["blend"],
        "levels": levels,
        "residual_subcranial": {
            "n": int((sub & keep).sum()),
            "before_mean_abs_mm": round(float(np.abs(X[sub & keep]).mean()), 3),
            "before_max_abs_mm": round(float(np.abs(X[sub & keep]).max()), 3),
            "after_mean_abs_mm": round(float(np.abs(after_all[sub & keep]).mean()), 4),
            "after_max_abs_mm": round(float(np.abs(after_all[sub & keep]).max()), 4),
        },
        "dropped_samples": [n for n, kk in zip(names, keep) if not kk],
    }
    if pc.get("ap"):
        prof_rows, cmj = ap_residuals(profile, pc["ap"]) if profile else ([], {})
        disp, worst_above = mesh_ap_displacements(T, pc)
        report["ap"] = {
            "knots": pc["ap"]["knots"], "knot_labels": list(AP_KNOT_LABEL), "fit": pc["ap"]["fit"],
            "profile": prof_rows, "cmj_residual": cmj,
            "above_anchor_max_abs_dy_mm": round(worst_above, 6),
            "meshes_moved": disp,
            "landmarks": ap_landmarks(T, pc),
            "cranial_nerve_roots": cn_check(T, pc),
        }
    MID.mkdir(parents=True, exist_ok=True)
    (MID / "report.json").write_text(json.dumps(report, indent=1))

    print(f"midline samples {len(S)} ({int(keep.sum())} used, {int((~keep).sum())} clipped as genuinely asymmetric)")
    print(f"fit  dx_mm = -(ky*y + kz*z + k0)  ky={k[0]:.4f}  kz={k[1]:.4f}  k0={k[2]:.4f}   "
          f"residual mean {pc['fit']['residual_mean_mm']:.4f} max {pc['fit']['residual_max_mm']:.4f} mm")
    print(f"blend smoothstep in source z: 0 at {Z_ZERO} m (foramen magnum) -> 1 at {Z_FULL} m")
    print(f"{'level':20s} {'z_src':>8s} {'z_MNI':>9s} {'before':>9s} {'after':>8s}")
    for L in levels:
        print(f"{L['level']:20s} {L['z_src_m']:8.4f} {L['z_mni_mm']:9.1f} {L['before_mm']:9.2f} {L['after_mm']:8.2f}")
    r = report["residual_subcranial"]
    print(f"sub-cranial midline residual: before mean {r['before_mean_abs_mm']} max {r['before_max_abs_mm']} mm"
          f"  ->  after mean {r['after_mean_abs_mm']} max {r['after_max_abs_mm']} mm  (n={r['n']})")
    if "ap" in report:
        apr = report["ap"]
        print("\nanteroposterior ramp (dy added to MNI y, + = anterior), knots in Z-Anatomy source metres:")
        for (z, v), lbl in zip(apr["knots"], apr["knot_labels"]):
            print(f"  {lbl:28s} z_src {z:.4f}   dy {v:6.2f} mm")
        f = apr["fit"]
        print(f"  fit to {f['samples']} measured slabs: rms {f['rms_mm']} mm, mean |r| {f['mean_abs_mm']}, "
              f"max |r| {f['max_abs_mm']}")
        c = apr["cmj_residual"]
        if c.get("max_abs_mm") is not None:
            print(f"  residual over {c['band']}: mean {c['mean_abs_mm']} max {c['max_abs_mm']} mm "
                  f"(gate 1.5, n={c['n']})")
        print(f"  displacement above the upper anchor: {apr['above_anchor_max_abs_dy_mm']} mm "
              f"({len(apr['meshes_moved'])} of the exported objects move)")
        print(f"  {'z_src':>8} {'z_MNI':>7} {'ZA y':>8} {'MNI y':>8} {'need':>7} {'ramp':>7} {'resid':>7}  ref")
        for r in apr["profile"]:
            print(f"  {r['z_src_m']:8.4f} {r['z_mni_mm']:7.1f} {r['zanatomy_y_mm']:8.2f} {r['mni_y_mm']:8.2f}"
                  f" {r['dy_mm']:7.2f} {r['fit_mm']:7.2f} {r['residual_mm']:+7.2f}  {r['ref']}")
        print(f"  {'mesh':44s} {'max dy':>8} {'mean dy':>8}")
        for r in apr["meshes_moved"][:200]:
            print(f"  {r['mesh']:44s} {r['max_dy_mm']:8.2f} {r['mean_dy_mm']:8.2f}")
        if apr.get("cranial_nerve_roots"):
            print(f"\n  cranial-nerve roots: gap to the Z-Anatomy parent (must not change) and to the MNI "
                  f"aseg brainstem, averaged over the root zone"
                  f"\n  {'mesh':34s} {'parent':8s} {'ZA before':>10} {'ZA after':>9} "
                  f"{'MNI before':>11} {'MNI after':>10}")
            for r in apr["cranial_nerve_roots"]:
                if "gap_to_mni_brainstem_after_mm" not in r:
                    print(f"  {r['mesh']:34s} {r['parent']:8s}  {r['note']}")
                    continue
                print(f"  {r['mesh']:34s} {r['parent']:8s} {r['gap_to_zanatomy_parent_before_mm']:10.2f} "
                      f"{r['gap_to_zanatomy_parent_after_mm']:9.2f} {r['gap_to_mni_brainstem_before_mm']:11.2f} "
                      f"{r['gap_to_mni_brainstem_after_mm']:10.2f}")

    if not a.no_plots:
        for p in figures(T, pc, S, X, keep, report.get("ap")):
            print("wrote", p)
    if not a.no_write:
        cfg["post_correction"] = pc
        (CONFIG / "zanatomy_to_mni.json").write_text(json.dumps(cfg, indent=1))
        print("wrote", CONFIG / "zanatomy_to_mni.json", "(post_correction)")
    print("wrote", MID / "report.json")


if __name__ == "__main__":
    main()
