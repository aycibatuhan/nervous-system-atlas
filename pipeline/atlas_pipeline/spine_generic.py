"""Phase 10b: an openly licensed spinal cord MRI for the PUBLIC edition, from the spine-generic database.

  atlas-spine-generic [--spacing 0.75] [--no-write] [--quiet]

Why a second cord MRI
---------------------
`atlas-pam50` gives the private edition its cord MRI, but the PAM50 data repository ships no licence file and
states no licence, so nothing derived from it may be redistributed and `atlas-manifest --public` drops the whole
cord grid.  The public edition therefore had no MRI at all below the foramen magnum.

This step builds a replacement out of data that *may* be redistributed: ten T2w scans from the spine-generic
multi-subject public database (Cohen-Adad et al., Sci Data 2021 / Nat Protoc 2021), whose repository carries the
verbatim CC BY 4.0 legal code -- see pipeline/raw/spine_generic/LICENCE_VERIFICATION.txt.  It is *our own*
template: the subjects are straightened, aligned and averaged here, and the result is then laid along our cord
centreline by the same curved reformat `atlas-pam50` uses (pam50.cord_frame / pam50.tube_grid, shared so that
both editions measure the cord on exactly the same curve).

No Spinal Cord Toolbox is needed and none is used.  Every per-subject label this step would otherwise have had
to compute is manual ground truth shipped in the dataset's own derivatives/labels: the cord segmentation, the
intervertebral disc labels, and -- the reason this template can be honest about spinal levels -- the manually
corrected C2-T1 dorsal and ventral **rootlet** segmentations.  Spinal levels are read off the rootlets, not
guessed from vertebral levels with the "spinal level = vertebral level minus one" rule of thumb.

How
---
1. Per subject, in its own scanner space: the cord centreline is the per-slice centroid of the shipped cord
   segmentation (boxcar-smoothed), resampled to a uniform arc-length step, with the same anterior-referenced
   frame the PAM50 reformat carries.  The T2w image is resampled onto a straight (arc, u, v) lattice --
   `sct_straighten_spinalcord` in pure numpy, and the inverse of what the reformat later does.
2. Arc length is measured from that subject's **C2/C3 intervertebral disc** (manual disc label 2), the anchor.
   The remaining disc labels then give a piecewise-linear arc warp onto the group-mean disc positions, so the
   subjects are level-matched and not merely translated; the residual disc scatter before and after is printed.
3. Intensities are normalised per subject on two robust anchors measured inside the tube -- the median of the
   cord itself and the 95th percentile of the surrounding CSF -- and averaged with a per-arc subject count.
4. Spinal levels come from the rootlets: the boundary between segment n and n+1 is the midpoint between the
   caudal end of the n rootlets and the rostral end of the n+1 rootlets, averaged over the subjects.
5. The template is laid on our centreline with arc length 1:1, anchored so that its C2/C3 disc sits at the
   arc length where the Z-Anatomy vertebral column (the same geometry the atlas is registered from, mapped
   through `zanatomy_to_mni.json`) puts the C2/C3 disc.  Nothing in the chain touches PAM50.

Outputs (public/data/volumes/), all tagged `edition: "public"` by atlas-manifest
-------------------------------------------------------------------------------
cord_t2_public.u8.bin        the reformatted template on its own axis-aligned MNI-frame grid, gzipped
labels_spine_public.u8.bin   spinal levels through the same reformat, in the same 1 = C1 ... 30 = S5 id space
                             the private volume uses -- but only the ids this template actually measured
                             (C2..T1) are ever painted
labels_spine_public.json     its lookup table, the same shape labels_spine.json has
cord_public.json             grid + per-volume metadata, swapped in for grids.cord by `atlas-manifest --public`
cord_levels_public.json      measured spinal levels (rootlets) and vertebral levels (disc labels) in world mm
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from . import midline, pam50
from .paths import CONFIG, RAW, VOLUMES, WORK

SRC = RAW / "spine_generic"
MNI_T2 = RAW / "mni_t1w" / "tpl-MNI152NLin2009cAsym_res-01_T2w.nii.gz"

# ---------------------------------------------------------------- straightening lattice
STEP = 0.5              # mm, isotropic, of the straightened per-subject volumes and of the template
ARC_LO = -38.0          # mm rostral to the C2/C3 disc: up to the top of our own cord surface
ARC_HI = 140.0          # mm caudal to it: about the T3/T4 vertebral level
RADIUS = pam50.R_FADE   # 16 mm, the same tube the reformat reads back
SEG_SLAB = 0.8          # mm: z step of the per-subject centreline slabs (one source voxel)
SEG_SMOOTH = 13         # centreline boxcar width in slabs
EXTRAPOLATE = 10.0      # mm the centreline may be extended straight beyond the cord segmentation
MIN_SUBJECTS = 7        # an arc bin needs at least this many subjects to enter the template

ANCHOR_DISC = 3         # the C2/C3 intervertebral disc -- see DISC_NAMES for why that is label 3
ZA_ANCHOR = "Intervertebral disc C2-C3"

# Disc-label convention: label 1 is a point at the top of C1 and label n (n >= 2) is the disc between vertebra
# n-1 and vertebra n, so the C2/C3 disc is label 3.  Verified against this dataset's own TotalSpineSeg
# vertebral-body segmentation (derivatives/labels/.../_label-spine_dseg.nii.gz, whose 11..17 = C1..C7 and
# 21.. = T1..) on sub-balgrist01: its C2/C3 disc (TotalSpineSeg 63, z 4.8..14.4 mm) coincides with manual disc
# label 3 (z 12.0), its C6/C7 disc (67, z -54.8..-43.7) with label 7 (-47), and its C7/T1 disc (71) with
# label 8 -- an offset of one from the other reading of the convention, and one that would have put the whole
# template a vertebral body too low.
DISC_NAMES = {1: "C1(top)", 2: "C1-C2", 3: "C2-C3", 4: "C3-C4", 5: "C4-C5", 6: "C5-C6", 7: "C6-C7",
              8: "C7-T1", 9: "T1-T2", 10: "T2-T3", 11: "T3-T4", 12: "T4-T5", 13: "T5-T6", 14: "T6-T7"}
# vertebra v runs from disc label v (its rostral disc) to disc label v+1 (its caudal one)
VERTEBRAE = [f"C{i}" for i in range(1, 8)] + [f"T{i}" for i in range(1, 13)]
# rootlet-label convention (ivadomed model-spinal-rootlets, and the manual ground truth here):
# the value is the spinal level the rootlets belong to, 2 = C2 ... 8 = C8, 9 = T1.
ROOTLET_NAMES = {2: "C2", 3: "C3", 4: "C4", 5: "C5", 6: "C6", 7: "C7", 8: "C8", 9: "T1"}

SPINE_SOURCE = "spine_generic"
MESH_SUFFIX = "-vert"   # the public edition's cord segment blocks are the `-vert` ones (Z-Anatomy cuts)


# ---------------------------------------------------------------- inputs
def subjects() -> list[str]:
    ids = sorted({p.name.split("_")[0] for p in SRC.glob("sub-*_T2w.nii.gz")})
    if not ids:
        raise SystemExit(f"no spine-generic T2w under {SRC}; run atlas-download --with spine-open")
    return ids


def ras(path: Path):
    import nibabel as nib
    return nib.as_closest_canonical(nib.load(str(path)))


def subject_files(sub: str) -> dict[str, Path]:
    return {"t2": SRC / f"{sub}_T2w.nii.gz",
            "seg": SRC / f"{sub}_T2w_label-SC_seg.nii.gz",
            "disc": SRC / f"{sub}_T2w_label-discs_dlabel.nii.gz",
            "root": SRC / f"{sub}_T2w_label-rootlets_dseg.nii.gz"}


def sample_at(img, world: np.ndarray, order: int = 1) -> np.ndarray:
    """Trilinear (order 0 = nearest) read of a nibabel image at world points, zero outside."""
    from scipy import ndimage
    data = np.asanyarray(img.dataobj).astype(np.float32)
    v = (np.asarray(world, float) - img.affine[:3, 3]) @ np.linalg.inv(img.affine[:3, :3]).T
    return ndimage.map_coordinates(data, v.T, order=order, mode="constant", cval=0.0)


def label_points(img) -> dict[int, np.ndarray]:
    """label value -> world-mm centroid of its voxels."""
    d = np.rint(np.asanyarray(img.dataobj)).astype(np.int32)
    out = {}
    for val in np.unique(d[d > 0]):
        idx = np.argwhere(d == val)
        out[int(val)] = (idx @ img.affine[:3, :3].T + img.affine[:3, 3]).mean(0)
    return out


def label_spans(img) -> dict[int, np.ndarray]:
    """label value -> the world-mm point cloud of its voxels, for arc extents."""
    d = np.rint(np.asanyarray(img.dataobj)).astype(np.int32)
    return {int(v): np.argwhere(d == v) @ img.affine[:3, :3].T + img.affine[:3, 3] for v in np.unique(d[d > 0])}


# ---------------------------------------------------------------- per-subject straightening
def seg_centreline(seg_img, slab: float = SEG_SLAB, smooth: int = SEG_SMOOTH) -> np.ndarray:
    """Per-axial-slice centroid of a cord segmentation, in world mm, smoothed in x and y, top down."""
    from scipy.ndimage import uniform_filter1d
    d = np.asanyarray(seg_img.dataobj) > 0.5
    idx = np.argwhere(d)
    if not len(idx):
        raise SystemExit("empty cord segmentation")
    w = idx @ seg_img.affine[:3, :3].T + seg_img.affine[:3, 3]
    rows = []
    for z in np.arange(w[:, 2].max(), w[:, 2].min() - 1e-6, -slab):
        sel = np.abs(w[:, 2] - z) < slab / 2 + 1e-6
        if sel.sum() >= 3:
            rows.append([w[sel, 0].mean(), w[sel, 1].mean(), z])
    C = np.array(rows)
    C[:, 0] = uniform_filter1d(C[:, 0], smooth, mode="nearest")
    C[:, 1] = uniform_filter1d(C[:, 1], smooth, mode="nearest")
    return C


def extend(P: np.ndarray, s: np.ndarray, by: float, step: float = 0.25) -> tuple[np.ndarray, np.ndarray]:
    """Continue a centreline straight off both ends by `by` mm, along its own end tangents.

    The cord segmentation stops where the model stops calling the medulla "cord", a few millimetres short of
    the top of the image; the MRI itself carries on.  A straight continuation of at most `by` mm is enough to
    reach the foramen magnum, and the cord is all but vertical there.
    """
    n = int(round(by / step))
    if n <= 0:
        return P, s
    t0 = P[0] - P[1]; t0 /= np.linalg.norm(t0)
    t1 = P[-1] - P[-2]; t1 /= np.linalg.norm(t1)
    pre = P[0] + np.outer(np.arange(n, 0, -1) * step, t0)
    post = P[-1] + np.outer(np.arange(1, n + 1) * step, t1)
    return np.vstack([pre, P, post]), np.concatenate([s[0] - np.arange(n, 0, -1) * step, s,
                                                      s[-1] + np.arange(1, n + 1) * step])


def project(P: np.ndarray, s: np.ndarray, T: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Arc length of the foot of the perpendicular from each point onto the centreline."""
    from scipy.spatial import cKDTree
    d, i = cKDTree(P).query(np.atleast_2d(pts))
    return s[i] + np.einsum("ij,ij->i", np.atleast_2d(pts) - P[i], T[i])


def straighten(sub: str, verbose: bool = True) -> dict:
    """One subject: its cord centreline, the straight (arc, u, v) lattice, and where its landmarks fall on it."""
    f = subject_files(sub)
    t2, seg = ras(f["t2"]), ras(f["seg"])
    C = seg_centreline(seg)
    P, s = pam50.resample_arc(C, 0.25)
    P, s = extend(P, s, EXTRAPOLATE)
    T, R, A = pam50.carry_frame(P)

    discs = label_points(ras(f["disc"]))
    if ANCHOR_DISC not in discs:
        raise SystemExit(f"{sub}: no disc label {ANCHOR_DISC} ({DISC_NAMES[ANCHOR_DISC]})")
    disc_arc = {k: float(a) for k, a in zip(discs, project(P, s, T, np.array(list(discs.values()))))}
    s0 = disc_arc[ANCHOR_DISC]

    roots = {}
    for v, pts in label_spans(ras(f["root"])).items():
        a = project(P, s, T, pts)
        roots[v] = (float(a.min() - s0), float(a.max() - s0))

    # the straight lattice, in template coordinates (arc from the C2/C3 disc, u right, v anterior)
    aa = np.arange(ARC_LO, ARC_HI + 1e-6, STEP)
    uu = np.arange(-RADIUS, RADIUS + 1e-6, STEP)
    AA, UU, VV = np.meshgrid(aa, uu, uu, indexing="ij")
    arc = AA.ravel() + s0
    inside = (arc >= s[0]) & (arc <= s[-1])
    world = np.zeros((arc.size, 3), np.float64)
    for k in range(3):
        world[:, k] = (np.interp(arc, s, P[:, k])
                       + UU.ravel() * np.interp(arc, s, R[:, k]) + VV.ravel() * np.interp(arc, s, A[:, k]))
    img = sample_at(t2, world, 1).astype(np.float32)
    cord = sample_at(seg, world, 1) > 0.5
    img[~inside] = np.nan

    # two robust anchors measured inside the tube: the cord itself and the CSF around it
    band = inside & (np.hypot(UU.ravel(), VV.ravel()) <= 8.0)
    c = float(np.median(img[band & cord])) if (band & cord).any() else 1.0
    csf = float(np.percentile(img[band], 95))
    scale = 0.5 / max(csf - c, 1e-6)
    norm = (img - c) * scale + 0.5

    shape = (aa.size, uu.size, uu.size)
    return {"id": sub, "arc": aa, "inplane": uu, "shape": shape,
            "vol": norm.reshape(shape), "cord": (cord & inside).reshape(shape),
            "cover": inside.reshape(shape).any(axis=(1, 2)),
            "discs": {k: v - s0 for k, v in disc_arc.items()}, "rootlets": roots,
            "cord_arc": (float(s[0] - s0 + EXTRAPOLATE), float(s[-1] - s0 - EXTRAPOLATE)),
            "norm": {"cord_median": c, "csf_p95": csf}}


# ---------------------------------------------------------------- template
def warp_arcs(subs: list[dict], keys: list[int]) -> tuple[dict[int, float], list[np.ndarray]]:
    """Group-mean disc arcs, and the piecewise-linear arc warp that takes each subject onto them.

    The C2/C3 disc is already at arc 0 in every subject (it is the origin), so the warp is the anchoring the
    remaining discs ask for on top of it: identical outside the labelled range, linear between the discs.
    """
    mean = {k: float(np.mean([sb["discs"][k] for sb in subs])) for k in keys}
    xs = np.array([mean[k] for k in keys])
    warps = []
    for sb in subs:
        src = np.array([sb["discs"][k] for k in keys])
        warps.append(np.interp(sb["arc"], src, xs, left=np.nan, right=np.nan))
        # outside the labelled span, continue with the end slopes so the ends are not clipped
        w = warps[-1]
        lo, hi = np.isnan(w) & (sb["arc"] < src[0]), np.isnan(w) & (sb["arc"] > src[-1])
        k0 = (xs[1] - xs[0]) / (src[1] - src[0]); k1 = (xs[-1] - xs[-2]) / (src[-1] - src[-2])
        w[lo] = xs[0] + (sb["arc"][lo] - src[0]) * k0
        w[hi] = xs[-1] + (sb["arc"][hi] - src[-1]) * k1
    return mean, warps


def resample_arc_axis(vol: np.ndarray, src_arc: np.ndarray, dst_arc: np.ndarray) -> np.ndarray:
    """Resample an (arc, u, v) volume along its first axis: row i of `vol` sits at `src_arc[i]`, and the
    result is that volume read at the arc lengths `dst_arc`.  Outside the source range the result is NaN, so
    the average that follows can count how many subjects a bin actually has."""
    from scipy import ndimage
    src_arc = np.asarray(src_arc, float)
    good = np.isfinite(src_arc)
    idx = np.interp(dst_arc, src_arc[good], np.flatnonzero(good).astype(float), left=np.nan, right=np.nan)
    n, ny, nz = vol.shape
    grid = np.stack(np.broadcast_arrays(np.nan_to_num(idx, nan=-1.0)[:, None, None],
                                        np.arange(ny)[None, :, None], np.arange(nz)[None, None, :]))
    out = ndimage.map_coordinates(np.nan_to_num(vol, nan=0.0), grid, order=1, mode="constant", cval=0.0)
    miss = np.isnan(idx) | (idx < 0) | (idx > n - 1)
    hole = ndimage.map_coordinates(np.isnan(vol).astype(np.float32), grid, order=1, mode="constant", cval=1.0)
    out[miss] = np.nan
    out[hole > 0.01] = np.nan
    return out.astype(np.float32)


def build_template(subs: list[dict], verbose: bool = True) -> dict:
    """Warp every subject onto the group-mean disc positions and average them."""
    keys = sorted(set.intersection(*[{k for k in sb["discs"]} for sb in subs]))
    mean_disc, warps = warp_arcs(subs, keys)
    aa = subs[0]["arc"]

    before = np.array([[sb["discs"][k] - mean_disc[k] for k in keys] for sb in subs])
    stack, cordstack = [], []
    for sb, w in zip(subs, warps):
        stack.append(resample_arc_axis(sb["vol"], w, aa))
        cordstack.append(resample_arc_axis(sb["cord"].astype(np.float32), w, aa))
    S = np.stack(stack); K = np.stack(cordstack)
    n = np.sum(~np.isnan(S), axis=0).astype(np.int16)
    with np.errstate(invalid="ignore"):
        avg = np.nanmean(S, axis=0)
        cordprob = np.nanmean(K, axis=0)
    ok = n >= MIN_SUBJECTS
    avg[~ok] = np.nan
    per_arc = n.max(axis=(1, 2))
    keep = per_arc >= MIN_SUBJECTS
    if verbose:
        print(f"template: {len(subs)} subjects, arc {aa[keep].min():.1f} .. {aa[keep].max():.1f} mm "
              f"from the C2/C3 disc, {int(keep.sum())} of {aa.size} arc bins with >= {MIN_SUBJECTS} subjects")
        print(f"disc alignment (mm from the group mean, sd over {len(subs)} subjects):")
        for i, k in enumerate(keys):
            print(f"   {DISC_NAMES.get(k, k):>6} mean arc {mean_disc[k]:7.2f}   sd before warp "
                  f"{before[:, i].std():5.2f} -> after 0.00")
    return {"arc": aa, "inplane": subs[0]["inplane"], "avg": avg, "count": n, "cord": cordprob,
            "keep": keep, "discs": mean_disc, "disc_keys": keys,
            "disc_sd": {k: float(before[:, i].std()) for i, k in enumerate(keys)}}


def spinal_levels(subs: list[dict], verbose: bool = True) -> tuple[dict[str, tuple[float, float]], dict]:
    """Spinal-level boundaries in template arc, measured from the rootlets alone.

    The boundary between segment n and n+1 is the midpoint between the caudal end of the n rootlets and the
    rostral end of the n+1 rootlets, averaged over the subjects.  The two outer boundaries -- above C2 and
    below T1 -- have no rootlet group on the far side, so they are extrapolated by the median distance the
    other boundaries sit from the neighbouring rootlet tip; they are reported as extrapolated.
    """
    vals = sorted(set.intersection(*[{v for v in sb["rootlets"]} for sb in subs]))
    lo = {v: float(np.mean([sb["rootlets"][v][0] for sb in subs])) for v in vals}
    hi = {v: float(np.mean([sb["rootlets"][v][1] for sb in subs])) for v in vals}
    sd = {v: float(np.std([sb["rootlets"][v][0] for sb in subs])) for v in vals}
    bound = {}
    for a, b in zip(vals, vals[1:]):
        bound[(a, b)] = 0.5 * (hi[a] + lo[b])
    gap_top = float(np.median([lo[b] - bound[(a, b)] for a, b in bound]))
    gap_bot = float(np.median([bound[(a, b)] - hi[a] for a, b in bound]))
    top = {vals[0]: lo[vals[0]] - gap_top}
    bottom = {vals[-1]: hi[vals[-1]] + gap_bot}
    out, meta = {}, {"measured": [], "extrapolated": []}
    for v in vals:
        a0 = top.get(v, bound.get((v - 1, v)))
        a1 = bottom.get(v, bound.get((v, v + 1)))
        out[ROOTLET_NAMES[v]] = (float(a0), float(a1))
        (meta["extrapolated"] if v in (vals[0], vals[-1]) else meta["measured"]).append(ROOTLET_NAMES[v])
    meta.update({"rootlet_rostral_sd_mm": {ROOTLET_NAMES[v]: round(sd[v], 2) for v in vals},
                 "boundary_rule": "midpoint between the caudal end of the rootlets of segment n and the "
                                  "rostral end of those of segment n+1, averaged over the subjects",
                 "outer_boundary_rule": f"the rostral edge of {ROOTLET_NAMES[vals[0]]} and the caudal edge of "
                                        f"{ROOTLET_NAMES[vals[-1]]} have no rootlet group beyond them, so they "
                                        f"are set {gap_top:.2f} mm above and {gap_bot:.2f} mm below the "
                                        "outermost rootlet tip -- the median of the measured boundaries"})
    if verbose:
        print("spinal levels from the rootlets (arc mm from the C2/C3 disc):")
        for name, (a0, a1) in out.items():
            print(f"   {name:>3} {a0:7.2f} .. {a1:7.2f}  ({a1 - a0:5.2f} mm long)")
    return out, meta


# ---------------------------------------------------------------- placing it on our cord
def anchor_on_centreline(fr: dict) -> tuple[float, dict]:
    """Arc length on our own cord centreline of the C2/C3 disc, from the Z-Anatomy vertebral column.

    The atlas' cord surface and its vertebral column are the same Z-Anatomy specimen, mapped to MNI by the
    same affine and midline correction, so the disc gives a landmark on our geometry that owes nothing to any
    cord template.  It is the one number that fixes where the spine-generic average is laid down.
    """
    cfg = json.loads((CONFIG / "zanatomy_to_mni.json").read_text())
    objs = json.loads((WORK / "zanatomy" / "objects.json").read_text())
    by = {o["name"]: o for o in objs}
    out = {}
    for name in [n for n in by if n.startswith("Intervertebral disc ")]:
        centre = np.array(by[name]["bbox"], float).mean(0)
        out[name[len("Intervertebral disc "):]] = midline.transform(centre[None, :], np.array(cfg["matrix"]),
                                                                    cfg.get("post_correction"))[0]
    if ZA_ANCHOR not in by:
        raise SystemExit(f"{ZA_ANCHOR} is not in work/zanatomy/objects.json")
    P, s = fr["centreline"], fr["arc"]
    T = fr["frame"][0]
    arcs = {k: float(project(P, s, T, v)[0]) for k, v in out.items()}
    key = ZA_ANCHOR[len("Intervertebral disc "):]
    return arcs[key], {"landmark": ZA_ANCHOR, "world_mm": [round(float(x), 2) for x in out[key]],
                       "arc_mm": round(arcs[key], 2),
                       "all_disc_arc_mm": {k: round(v, 2) for k, v in sorted(arcs.items(), key=lambda kv: kv[1])}}


def reformat(tpl: dict, spacing: float, verbose: bool = True) -> dict:
    """Lay the straightened template along our cord centreline, arc length 1:1 from the C2/C3 disc."""
    from scipy import ndimage
    fr = pam50.cord_frame()
    s_anchor, anchor = anchor_on_centreline(fr)
    aa = tpl["arc"][tpl["keep"]]
    lo, hi = s_anchor + float(aa.min()), s_anchor + float(aa.max())
    g = pam50.tube_grid(fr, lo, hi, spacing)
    if verbose:
        print(f"\nour cord centreline: {len(fr['centreline'])} points, total arc {fr['cord_arc_total']:.1f} mm; "
              f"{anchor['landmark']} at arc {s_anchor:.2f} mm (world {anchor['world_mm']})")
        print(f"grid {g['dims'][0]}x{g['dims'][1]}x{g['dims'][2]} at {spacing} mm, "
              f"origin {np.round(g['origin'], 2).tolist()}, {np.prod(g['dims'])/1e6:.2f} M voxels, "
              f"{len(g['sel'])/1e3:.0f} k inside the tube")

    def read(vol: np.ndarray, order: int = 1, cval: float = 0.0) -> np.ndarray:
        a = tpl["arc"]; p = tpl["inplane"]
        c = np.stack([(g["arc_of_voxel"] - s_anchor - a[0]) / STEP,
                      (g["u"] - p[0]) / STEP, (g["v"] - p[0]) / STEP])
        return ndimage.map_coordinates(np.nan_to_num(vol, nan=cval), c, order=order, mode="constant", cval=cval)

    return {"frame": fr, "grid": g, "anchor": anchor, "s_anchor": s_anchor, "read": read,
            "arc_band": (float(aa.min()), float(aa.max()))}


def level_volume(tpl: dict, levels: dict[str, tuple[float, float]]) -> np.ndarray:
    """A (arc, u, v) volume of spinal-level ids, painted only where the template measured a level."""
    ids = {n: pam50.SPINAL_LEVELS.index(n) + 1 for n in levels}
    a = tpl["arc"]
    lab = np.zeros(a.size, np.uint8)
    for name, (a0, a1) in levels.items():
        lab[(a >= a0) & (a < a1)] = ids[name]
    vol = np.broadcast_to(lab[:, None, None], tpl["avg"].shape).astype(np.uint8).copy()
    vol[~np.isfinite(tpl["avg"])] = 0
    return vol


# ---------------------------------------------------------------- QA: does it land on the MNI medulla?
def medulla_residual(cord: np.ndarray, origin, spacing: float, band=(-77.0, -70.0),
                     verbose: bool = True) -> dict:
    """Cord centre in the public cord volume vs the medulla in the MNI T2w, over the band where both exist.

    Both volumes are T2-weighted there, so in a small disc around the cord the tissue is the dark part and the
    CSF the bright part; the centre is the intensity-*inverted* centroid inside that disc.  A small residual
    says the reformat put the cord where the MNI template's medulla actually is.
    """
    from scipy import ndimage
    from .spaces import load_ras
    mni = load_ras(MNI_T2)
    M = np.asanyarray(mni.dataobj).astype(np.float32)
    C = np.asarray(cord, np.float32)
    xs = np.arange(-9, 9.01, 0.25)
    XX, YY = np.meshgrid(xs, xs, indexing="ij")
    aff_c = np.eye(4); aff_c[:3, :3] = np.diag([spacing] * 3); aff_c[:3, 3] = origin

    def centre(data, aff, z, x0, y0):
        W = np.stack([(XX + x0).ravel(), (YY + y0).ravel(), np.full(XX.size, z)], -1)
        v = (W - aff[:3, 3]) @ np.linalg.inv(aff[:3, :3]).T
        img = ndimage.map_coordinates(data, v.T, order=1, mode="constant", cval=0.0).reshape(XX.shape)
        r = np.hypot(XX, YY)
        disc = r <= 6.0
        if img[disc].max() <= 0:
            return None
        w = np.clip(img[disc].max() - img, 0, None) * disc
        w = np.where(w >= w.max() * 0.5, w, 0.0)
        if w.sum() <= 0:
            return None
        return float(((XX + x0) * w).sum() / w.sum()), float(((YY + y0) * w).sum() / w.sum())

    out = []
    for z in np.arange(band[0], band[1] + 1e-6, 0.5):
        # start both searches from the cord volume's own bright/dark structure near the midline
        a = centre(C, aff_c, z, 0.0, -47.0)
        if a is None:
            continue
        b = centre(M, mni.affine, z, *a)
        if b is None:
            continue
        out.append([z, a[0], a[1], b[0], b[1]])
    if not out:
        return {"n_slices": 0, "note": "no overlap between the public cord grid and the MNI volume"}
    r = np.array(out)
    dx, dy = r[:, 1] - r[:, 3], r[:, 2] - r[:, 4]
    res = {"band_mm": [float(band[0]), float(band[1])], "n_slices": len(r),
           "dx_mean": float(np.mean(dx)), "dx_sd": float(np.std(dx)),
           "dy_mean": float(np.mean(dy)), "dy_sd": float(np.std(dy)),
           "dxy_rms": float(np.sqrt(np.mean(dx ** 2 + dy ** 2)))}
    if verbose:
        print(f"\npublic cord <-> MNI T2w, cord centre over z {band[0]:.0f} .. {band[1]:.0f} mm "
              f"({len(r)} slices at 0.5 mm)")
        print(f"{'z':>7} {'cord x':>7} {'cord y':>7} {'MNI x':>7} {'MNI y':>7} {'dx':>6} {'dy':>6}")
        for row, a, b in zip(r, dx, dy):
            print(f"{row[0]:7.1f} {row[1]:7.2f} {row[2]:7.2f} {row[3]:7.2f} {row[4]:7.2f} {a:6.2f} {b:6.2f}")
        print(f"residual dx {res['dx_mean']:+.2f} +- {res['dx_sd']:.2f} mm, dy {res['dy_mean']:+.2f} +- "
              f"{res['dy_sd']:.2f} mm, RMS {res['dxy_rms']:.2f} mm")
    return res


# ---------------------------------------------------------------- driver
def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="atlas-spine-generic", description=__doc__.split("\n")[0])
    ap.add_argument("--spacing", type=float, default=pam50.SPACING)
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    v = not a.quiet

    ids = subjects()
    print(f"spine-generic: {len(ids)} subjects -> {', '.join(s.replace('sub-', '') for s in ids)}")
    subs = []
    for sid in ids:
        sb = straighten(sid, v)
        subs.append(sb)
        if v:
            print(f"  {sid:16s} cord arc {sb['cord_arc'][0]:7.1f} .. {sb['cord_arc'][1]:6.1f} mm from C2/C3, "
                  f"{len(sb['discs'])} discs, rootlets {min(sb['rootlets'])}-{max(sb['rootlets'])}, "
                  f"cord {sb['norm']['cord_median']:.0f} / CSF {sb['norm']['csf_p95']:.0f}")

    tpl = build_template(subs, v)
    levels, level_meta = spinal_levels(subs, v)
    rf = reformat(tpl, a.spacing, v)
    g, fr = rf["grid"], rf["frame"]

    # intensity: window on the template's own cord, exactly as the private reformat windows PAM50's
    cordmask = np.isfinite(tpl["avg"]) & (tpl["cord"] > 0.5)
    c5, c95 = np.percentile(tpl["avg"][cordmask], [5, 95])
    span = max(float(c95 - c5), 1e-3)
    lo, hi = float(c5) - 0.25 * span, float(c95) + 0.25 * span
    vals = rf["read"](tpl["avg"], 1, cval=lo)
    u8 = np.clip((vals - lo) / (hi - lo) * 255.0, 0, 255) * g["fade"]

    lab = rf["read"](level_volume(tpl, levels).astype(np.float32), 0, cval=0.0).astype(np.uint8)

    dims, sel = g["dims"], g["sel"]
    zmin = float(g["origin"][2]); zmax = zmin + (dims[2] - 1) * a.spacing
    out = {
        "space": "MNI152NLin2009cAsym", "edition": "public",
        "shape": [int(d) for d in dims], "spacing": [a.spacing] * 3,
        "origin_ras": [round(float(x), 4) for x in g["origin"]],
        "affine_ras": [[round(float(x), 6) for x in row] for row in g["affine"][:3].tolist()] + [[0, 0, 0, 1]],
        "source": SPINE_SOURCE, "license": "CC-BY-4.0",
        "reformat": {
            "method": "curved reformat of an average T2w cord template built here from "
                      f"{len(subs)} spine-generic subjects (each straightened along the centreline of its own "
                      "shipped cord segmentation, arc length measured from its manual C2/C3 disc label, "
                      "piecewise-linearly level-matched on the remaining disc labels, then averaged) onto the "
                      f"centreline of {fr['mesh_source']} (per-z slab centroids, {pam50.SMOOTH} mm boxcar); "
                      "arc length mapped 1:1 and anchored at the C2/C3 intervertebral disc of the Z-Anatomy "
                      "vertebral column, the same specimen the cord surface comes from",
            "anchor": rf["anchor"], "anchor_arc_mm": round(rf["s_anchor"], 3),
            "template_arc_mm": [round(x, 2) for x in rf["arc_band"]],
            "cord_arc_total_mm": round(fr["cord_arc_total"], 2),
            "radius_full_mm": pam50.R_FULL, "radius_fade_mm": pam50.R_FADE,
            "subjects": [s.replace("sub-", "") for s in ids],
            "template_step_mm": STEP, "min_subjects_per_bin": MIN_SUBJECTS,
            "disc_sd_before_warp_mm": {DISC_NAMES.get(k, str(k)): round(x, 2) for k, x in tpl["disc_sd"].items()},
        },
        "coverage": {"z_mm": [round(zmin, 2), round(zmax, 2)],
                     "vertebral_levels": vertebral_span(tpl),
                     "spinal_levels": sorted(levels, key=pam50.SPINAL_LEVELS.index),
                     "note": "the template covers the cervical and upper thoracic cord only; spinal levels are "
                             "painted only where the rootlets measured them"},
        "contrasts": {},
    }

    rec = pam50.write_volume("cord_t2_public", dims, u8.astype(np.uint8), sel) if not a.no_write else {}
    rec.update({"window": 255, "level": 127, "source_window": [round(lo, 3), round(hi, 3)],
                "space": "cord", "edition": "public", "spacing": [a.spacing] * 3,
                "origin_ras": out["origin_ras"], "affine_ras": out["affine_ras"]})
    out["contrasts"]["cord_t2"] = rec
    print(f"\n  {'cord_t2':16s} window {lo:.2f}..{hi:.2f}  {rec.get('bytes_gz', 0)/1024:8.1f} KB gz "
          f"({rec.get('bytes_raw', 0)/1e6:.1f} MB raw)")

    rec = pam50.write_volume("labels_spine_public", dims, lab, sel) if not a.no_write else {}
    rec.update({"space": "cord", "edition": "public", "spacing": [a.spacing] * 3,
                "origin_ras": out["origin_ras"], "affine_ras": out["affine_ras"],
                "lut": "volumes/labels_spine_public.json"})
    out["contrasts"]["labels_spine"] = rec
    print(f"  {'labels_spine':16s} {len(levels)} levels      {rec.get('bytes_gz', 0)/1024:8.1f} KB gz")

    spinal = world_levels(fr, rf["s_anchor"], levels)
    vert = world_levels(fr, rf["s_anchor"], vertebral_levels(tpl))
    dense = np.zeros(int(np.prod(dims)), np.float32)
    dense[sel] = u8
    residual = medulla_residual(dense.reshape(dims), g["origin"], a.spacing, verbose=v)
    out["reformat"]["mni_residual"] = residual

    print(f"\n{'level':>6} {'arc mm':>16} {'our world z':>17}  centre (x, y) mm")
    for r in spinal:
        print(f"{r['name']:>6} {r['arc_mm'][0]:7.1f}..{r['arc_mm'][1]:7.1f} {r['z_mm'][1]:8.1f}..{r['z_mm'][0]:7.1f}"
              f"  ({r['top'][0]:5.1f}, {r['top'][1]:7.1f})")

    if a.no_write:
        return
    (VOLUMES / "cord_public.json").write_text(json.dumps(out, indent=1))
    sl = pam50.spine_lut(spinal, mesh_suffix=MESH_SUFFIX, source=SPINE_SOURCE, volume="labels_spine_public",
                         note="Spinal levels measured on the dorsal and ventral nerve rootlets of "
                              f"{len(subs)} spine-generic subjects and carried onto our cord centreline by the "
                              "atlas-spine-generic curved reformat. ids are the same 1 = C1 ... 30 = S5 ids the "
                              "private volume uses, as they appear in volumes/labels_spine_public.u8.bin; only "
                              "the levels this template measured are ever painted. meshId is the cord segment "
                              "block that contains the level, so selecting a level and selecting its 3D block "
                              "are the same selection.")
    sl["coverage"] = out["coverage"]
    sl["levelMethod"] = level_meta
    (VOLUMES / "labels_spine_public.json").write_text(json.dumps(sl, indent=1))
    cl_s, cl_p = pam50.centreline_table({"centreline": fr["centreline"], "arc": fr["arc"]})
    (VOLUMES / "cord_levels_public.json").write_text(json.dumps(
        {"space": "MNI152NLin2009cAsym", "edition": "public", "source": SPINE_SOURCE,
         "note": "spinal levels measured on the nerve rootlets and vertebral levels measured on the disc "
                 "labels of the spine-generic subjects, carried onto our cord centreline by the "
                 "atlas-spine-generic curved reformat; top/bottom are world mm on the centreline",
         "anchor": rf["anchor"], "centrelineSource": fr["mesh_source"],
         "centreline": {"stepMm": pam50.CENTRELINE_STEP,
                        "arc": [round(float(x), 3) for x in cl_s],
                        "points": [[round(float(c), 3) for c in q] for q in cl_p]},
         "levelMethod": level_meta,
         "spinalLevels": spinal, "vertebralLevels": vert}, indent=1))
    print(f"\nwrote {VOLUMES / 'cord_public.json'}, {VOLUMES / 'labels_spine_public.json'} and "
          f"{VOLUMES / 'cord_levels_public.json'}")
    print(f"total shipped: {sum(x.get('bytes_gz', 0) for x in out['contrasts'].values())/1e6:.2f} MB gz")


def vertebral_levels(tpl: dict) -> dict[str, tuple[float, float]]:
    """Vertebral levels from the mean disc arcs: vertebra v runs from disc label v to disc label v + 1.

    C1 is bounded rostrally by label 1, which is a point at the top of C1 rather than a disc, so the C1 entry
    is the C1 arch and the odontoid together; every level below it is between two real discs.
    """
    d = tpl["discs"]
    return {name: (d[v], d[v + 1]) for v, name in enumerate(VERTEBRAE, start=1) if v in d and (v + 1) in d}


def vertebral_span(tpl: dict) -> list[str]:
    v = vertebral_levels(tpl)
    return [next(iter(v)), list(v)[-1]] if v else []


def world_levels(fr: dict, s_anchor: float, levels: dict[str, tuple[float, float]]) -> list[dict]:
    """Template arc -> arc on our centreline -> world mm, in the shape cord_levels.json uses."""
    P, s = fr["centreline"], fr["arc"]
    out = []
    for name, (a0, a1) in levels.items():
        rec = {"name": name, "arc_mm": [round(s_anchor + a0, 2), round(s_anchor + a1, 2)]}
        for key, arc in (("top", s_anchor + a0), ("bottom", s_anchor + a1)):
            rec[key] = [round(float(np.interp(arc, s, P[:, k])), 2) for k in range(3)]
        rec["z_mm"] = [rec["bottom"][2], rec["top"][2]]
        out.append(rec)
    return out


if __name__ == "__main__":
    main()
