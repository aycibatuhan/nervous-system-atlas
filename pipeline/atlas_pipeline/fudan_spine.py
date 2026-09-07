"""Phase 10d: a straightened whole-cord T2 template for the PUBLIC edition, from the Fudan lumbosacral dataset.

  atlas-fudan-spine [--no-write] [--quiet] [--subjects 01,07]

Why a whole-spine template
--------------------------
`atlas-spine-generic` gives the public edition an isotropic, manually labelled cervical template, but its
subjects were scanned head-and-neck only: it stops at about T3, and everything below -- the thoracic cord, the
lumbar enlargement, the conus medullaris and the lumbosacral thecal sac -- had no openly licensed MRI at all.
The Fudan "open-access lumbosacral spine MRI dataset" (Li et al., Sci Data 2024, CC BY 4.0) ships, for each of
14 healthy young adults, a *composed whole-spine* sagittal T2-TSE that runs from the skull base to the sacrum.
This step turns those 14 scans into the second template `atlas-cord-public` composes, in the same contract
(see the docstring of cord_public.py): a straightened, level-matched, averaged (arc, u, v) volume whose arc
length is measured from the C2/C3 intervertebral disc.

What the dataset does *not* ship is any cord segmentation or any disc label -- the manual markers cover only
the conus region on the high-resolution CISS.  So the centreline and all 23 discs are found here, with numpy /
scipy / scikit-image only: no Spinal Cord Toolbox, no deep-learning model, and nothing derived from PAM50.

How
---
1. **Marker overlay check.**  The 3D Slicer markups (LPS mm, converted to RAS by negating x and y) are in the
   same session's scanner world, so they overlay the T2-TSE through world coordinates.  We verify that before
   trusting them: the cord-outline centroids must be dark and the ring 5 mm around them bright (the cord inside
   its CSF).  The measured ratio is reported per subject and carried into the QA block.

2. **Centreline.**  The CISS `cord_*` ClosedCurve outlines give the conus centreline for free -- their
   per-slice centroids are ground truth, and the lowest outlined slice is that subject's conus tip.  From
   there the cord is tracked through the T2-TSE by a Viterbi pass over z (1 mm steps) on a matched filter for
   "dark cord between two bright CSF bands": at each candidate centre the mean over |v| <= 2 mm is subtracted
   from the *smaller* of the two means over v in [r, r + 3.5] mm anterior and posterior, maximised over
   r in {3.5, 4.5, 5.5, 6.5} mm so that the same filter fits the cervical enlargement and the thin thoracic
   cord.  Taking the *minimum* of the two flanks is what keeps the track off the posterior epidural fat, which
   is also a dark stripe but is bright on one side only.  Inside the marker range the path is pinned to the
   markers.  Below the conus tip a second Viterbi pass follows the bright CSF of the thecal sac down to the S2
   ganglion markers.  The result is boxcar-smoothed, resampled to a uniform arc step and continued straight a
   few mm off both ends (as spine_generic.extend does) so the template reaches the medulla.

3. **Discs.**  On the straightened mid-sagittal reformat the anterior wall of the spinal canal is found per
   arc (the last sample still at half the CSF peak), and two strips are read relative to it: the *posterior
   annulus* band (wall - 3 .. wall + 4 mm) and the *nucleus* band (wall + 7 .. wall + 25 mm).  Their difference
   is large exactly at a disc -- bright nucleus, dark annulus and posterior longitudinal ligament -- and small
   in mid-body, where the basivertebral vein would otherwise fake a disc at half the vertebral period (it is
   bright, but it has no dark endplate under it).  A Viterbi assignment over the 23 discs C2-C3 ... L5-S1 then
   maximises that evidence under a prior on disc-to-disc distance (cervical ~17-19 mm, thoracic 20.5 growing to
   31, lumbar 32-35, scaled per subject), softly anchored at the bottom by the L1..L5 dorsal-root-ganglion
   markers, which sit about 9 mm rostral to their foramen's disc, and at the top by the ~30 mm disc-free
   stretch of the C2 body and dens.  Two details earn their keep:

   * the chain may extrapolate its C2/C3 up to 70 mm *above* the top of the image.  Some subjects lie low
     enough in the scanner that the composed stack starts below C2 (sub-06 starts 38 mm below its C2/C3), and
     without that freedom the whole assignment is dragged down a vertebra to find something imaged to sit on.
   * the five cervical intervals are held to a tighter prior (sd 9 % of the height, floor 1.8 mm) than the
     rest (15 %).  The cervical bodies are the most uniform part of the spine and the part where this
     sequence's contrast is weakest, and with independent per-interval priors a systematic stretch of the
     whole chain is almost free -- which is exactly how a subject with no usable cervical disc evidence ends
     up with its arc 0, the anchor of the entire template, drifting 50 mm up towards the skull base.

4. **Straightening, level matching, averaging.**  Each subject is resampled onto the (arc, u, v) lattice at
   0.5 mm, +-16 mm (pam50.R_FADE) in plane, with arc measured from its own C2/C3 disc, and normalised on two
   robust anchors inside the tube exactly as spine_generic.straighten does (cord median -> 0.5, CSF 95th
   percentile -> 1.0).  The subject is sampled directly at the *inverse* of the piecewise-linear warp that
   takes its discs onto the group-mean disc arcs, so it lands level-matched with a single interpolation.  Rows
   are averaged with a per-row subject count and dropped below MIN_SUBJECTS.

5. **Cord probability.**  With no segmentation to average, the cord is taken to be the connected dark blob
   around the centre: normalised intensity below 0.75 (halfway between the cord anchor at 0.5 and the CSF
   anchor at 1.0) within 6.5 mm of the centre, connected to it, and nothing below that subject's conus tip.
   Averaged over subjects it is an honest "fraction of subjects whose cord covers this voxel".

Caveats
-------
Arc 0 is the C2/C3 disc and the lattice runs -46 .. +620 mm, further than the +520 mm the cord alone needs:
the extra 100 mm carry the lumbosacral thecal sac down to about S2, which is the whole reason this dataset is
worth straightening.  Every row still has at least MIN_SUBJECTS subjects.

The T2-TSE is a DICOM-COMPOSED image of four stations; the seams are visible as faint intensity steps across
the thoracolumbar junction, and the per-subject normalisation is a single global pair of anchors (the contract
asks for exactly the spine_generic normalisation), so a little banding survives into the average.  Left-right
resolution is 3.3 mm, so the template is sharp in the sagittal plane and blurred across it -- which is why
`atlas-cord-public` prefers the isotropic spine-generic template wherever the two overlap.

Outputs
-------
pipeline/work/cord_public/fudan_t2.npz + fudan_t2.json   the template, in the cord_public.py contract
pipeline/qa/fudan_spine.json                             the same QA numbers
pipeline/qa/fudan_spine/sub-XX.png, template.png         the pictures this step must be judged on
"""
from __future__ import annotations

import argparse
import glob
import json
import re
from pathlib import Path

import numpy as np

from . import pam50
from .paths import QA, RAW, WORK

SRC = RAW / "lumbosacral_fudan"
CACHE = WORK / "fudan_spine"
TEMPLATE_DIR = WORK / "cord_public"
QA_DIR = QA / "fudan_spine"
NAME = "fudan_t2"
SOURCE = "lumbosacral_fudan"
LICENSE = "CC-BY-4.0"

# ---------------------------------------------------------------- straightening lattice
STEP = 0.5              # mm, the contract's arc and in-plane step
RADIUS = pam50.R_FADE   # 16 mm
ARC_LO = -46.0          # mm rostral to the C2/C3 disc: into the medulla, past the foramen magnum
ARC_HI = 620.0          # mm caudal to it: past the S2 ganglia, i.e. the bottom of the thecal sac
MIN_SUBJECTS = 9        # of 14, per the brief
EXTRAPOLATE = 8.0       # mm the centreline may be continued straight beyond the tracked span

# ---------------------------------------------------------------- centreline tracking
Z_STEP = 1.0            # mm, the Viterbi step along z
XY_STEP = 1.0           # mm, the Viterbi state grid
X_HALF = 20.0           # mm, half-width in x of the Viterbi search window about the marker median
# ... and in y, where the window has to be asymmetric: the marker median is the conus, and the cervical cord
# is far *anterior* of it -- up to 70 mm in a subject scanned with the neck flexed (sub-14)
Y_CORD = (-62.0, 88.0)
Y_SAC = (-45.0, 50.0)   # below the conus the thecal sac stays near the conus, so the window can be tighter
CORD_RADII = (3.5, 4.5, 5.5, 6.5)   # mm, the CSF-band offsets the matched filter tries
DARK_MM = 4.0           # mm, width of the "cord" box (|v| <= 2)
BAND_MM = 3.5           # mm, width of each "CSF" box
SAC_MM = 8.0            # mm, width of the "thecal sac" box below the conus
LAM_CORD, LAM_SAC = 0.05, 0.10      # Viterbi step penalty per mm^2
SMOOTH_X, SMOOTH_Y = 15, 9          # boxcar widths (in 1 mm samples) of the tracked centreline

# ---------------------------------------------------------------- discs
DISCS = (["C2-C3"] + [f"C{i}-C{i + 1}" for i in range(3, 7)] + ["C7-T1"]
         + [f"T{i}-T{i + 1}" for i in range(1, 12)] + ["T12-L1"]
         + [f"L{i}-L{i + 1}" for i in range(1, 5)] + ["L5-S1"])
assert len(DISCS) == 23 and DISCS[0] == "C2-C3" and DISCS[-1] == "L5-S1"
# prior disc-to-disc distance, i.e. the height of the vertebral body between them plus one disc, in mm;
# HEIGHTS[k] separates DISCS[k] from DISCS[k+1] and is named after the vertebra in between
HEIGHT_NAMES = ([f"C{i}" for i in range(3, 8)] + [f"T{i}" for i in range(1, 13)]
                + [f"L{i}" for i in range(1, 6)])
HEIGHTS = np.array([17.0, 17.5, 18.0, 18.0, 19.0,                       # C3..C7
                    20.5, 21.5, 22.0, 22.5, 23.0, 24.0, 25.0, 26.0, 27.0, 28.0, 29.5, 31.0,   # T1..T12
                    33.0, 34.5, 35.0, 34.5, 32.0])                      # L1..L5
assert len(HEIGHTS) == len(DISCS) - 1 == len(HEIGHT_NAMES)
# fraction of the (scaled) prior height allowed as the sd of one interval.  The cervical bodies are the most
# uniform part of the spine and the part where the disc evidence is weakest (the neck station of the composed
# stack has the lowest contrast), so their intervals are held tighter: without that, a subject with no usable
# cervical evidence buys a 20 mm stretch of the whole chain for almost nothing, and the C2/C3 anchor -- arc 0
# of the whole template -- drifts up towards the skull base.
HEIGHT_SD = np.where(np.arange(22) < 5, 0.09, 0.15)
HEIGHT_SD_FLOOR = 1.8   # mm
GANGLION_LEAD = 9.0     # mm the disc of a foramen sits caudal to that level's dorsal root ganglion marker
GANGLION_SD = 8.0       # mm
GANGLION_ANCHORS = {"L1": "L1-L2", "L2": "L2-L3", "L3": "L3-L4", "L4": "L4-L5", "L5": "L5-S1"}
SPAN_SD = 22.0          # mm: how far the C2/C3 disc may sit from where the ganglion-anchored proportions
                        # predict it.  Without this the per-interval height priors are independent, so a
                        # systematic stretch of the whole chain -- which is exactly what a subject with weak
                        # cervical disc contrast invites -- costs almost nothing
DISC_WEIGHT = 6.0       # weight of the image evidence against the (unit-variance) shape priors
TOP_GAP = (14.0, 34.0)  # mm above C2-C3 that must be free of discs (the C2 body and the dens)
TOP_WEIGHT = 8.0
ABOVE_FOV = 70.0        # mm the disc chain may be extrapolated above the top of the image

# vertebra v is bounded by the disc above and the disc below it
VERTEBRAE = [f"C{i}" for i in range(3, 8)] + [f"T{i}" for i in range(1, 13)] + [f"L{i}" for i in range(1, 6)]


# ================================================================ inputs
def subjects() -> list[str]:
    ids = sorted(p.name for p in (SRC / "rawdata").glob("sub-*") if p.is_dir())
    if not ids:
        raise SystemExit(f"no Fudan subjects under {SRC}/rawdata; run atlas-download --with lumbosacral-fudan")
    return ids


def ras(path):
    import nibabel as nib
    return nib.as_closest_canonical(nib.load(str(path)))


def t2_image(sub: str):
    return ras(SRC / "rawdata" / sub / "anat" / f"{sub}_T2TSE.nii.gz")


def markup_points(path) -> np.ndarray:
    """Every control point of a 3D Slicer markups file, in RAS mm.

    The dataset writes `coordinateSystem: LPS`, which is the DICOM convention; RAS is LPS with x and y
    negated, and that is the frame the NIfTI affines (after nib.as_closest_canonical) are in.
    """
    d = json.loads(Path(path).read_text())
    pts = np.array([cp["position"] for m in d["markups"] for cp in m["controlPoints"]], float)
    if str(d["markups"][0].get("coordinateSystem", "LPS")).upper().startswith("LPS"):
        pts[:, :2] *= -1.0
    return pts


def marker_files(sub: str, pattern: str) -> list[Path]:
    """Markers of one subject matching `*<pattern>*.json` -- sub-14 spells some of its files `sub_14_`."""
    return sorted(Path(p) for p in glob.glob(str(SRC / "markers" / sub / f"*{pattern}*.json")))


def cord_outlines(sub: str) -> tuple[np.ndarray, np.ndarray]:
    """Centroid and mean in-plane radius of every CISS cord outline, ordered from rostral to caudal."""
    files = marker_files(sub, "cord_")
    files.sort(key=lambda p: int(re.search(r"cord_(\d+)\.json", p.name).group(1)))
    pts = [markup_points(p) for p in files]
    cen = np.array([q.mean(0) for q in pts])
    rad = np.array([np.linalg.norm(q[:, :2] - q.mean(0)[:2], axis=1).mean() for q in pts])
    order = np.argsort(-cen[:, 2])
    return cen[order], rad[order]


def rootlet_origins(sub: str, P, arc, T) -> dict[str, float]:
    """Arc of the rostral end of each traced intradural nerve root, L1 .. S2, mean of the two sides.

    These are *not* published as spinal levels: the markers trace each root only from where the annotator
    could first separate it inside the thecal sac, which is a few millimetres caudal of its true rootlet
    attachment, and they are truncated at the bottom of the CISS field of view.  They are carried in the QA
    block because their order and spacing are a useful independent check on the conus end of the template.
    """
    out = {}
    for lv in ("L1", "L2", "L3", "L4", "L5", "S1", "S2"):
        tops = []
        for f in marker_files(sub, f"nerveroots_{lv}_"):
            a = project(P, arc, T, markup_points(f))
            tops.append(float(a.min()))
        if tops:
            out[lv] = float(np.mean(tops))
    return out


def ganglia(sub: str) -> dict[str, np.ndarray]:
    """Level -> the mid-point of that level's left and right dorsal-root-ganglion markers, in RAS mm."""
    out = {}
    for lv in ("L1", "L2", "L3", "L4", "L5", "S1", "S2"):
        files = marker_files(sub, f"ganglions_{lv}_")
        if files:
            out[lv] = np.vstack([markup_points(p) for p in files]).mean(0)
    return out


def sample_at(img, world: np.ndarray, order: int = 1, with_fov: bool = False):
    """Trilinear (order 0 = nearest) read of a nibabel image at world points, zero outside.

    `with_fov` also returns the mask of points that actually fall inside the image: the composed T2-TSE stops
    at the skull base, so a straightened row near ARC_LO can leave the field of view, and a zero there would
    otherwise enter the average as very dark tissue instead of as "this subject has no data".
    """
    from scipy import ndimage
    data = np.asanyarray(img.dataobj).astype(np.float32)
    v = (np.asarray(world, float) - img.affine[:3, 3]) @ np.linalg.inv(img.affine[:3, :3]).T
    out = ndimage.map_coordinates(data, v.T, order=order, mode="constant", cval=0.0)
    if not with_fov:
        return out
    fov = np.all((v >= 0) & (v <= np.array(data.shape) - 1), axis=1)
    return out, fov


def project(P: np.ndarray, s: np.ndarray, T: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Arc length of the foot of the perpendicular from each point onto the centreline."""
    from scipy.spatial import cKDTree
    _, i = cKDTree(P).query(np.atleast_2d(pts))
    return s[i] + np.einsum("ij,ij->i", np.atleast_2d(pts) - P[i], T[i])


def extend(P: np.ndarray, s: np.ndarray, by: float, step: float) -> tuple[np.ndarray, np.ndarray]:
    """Continue a centreline straight off both ends by `by` mm, along its own end tangents."""
    n = int(round(by / step))
    if n <= 0:
        return P, s
    t0 = P[0] - P[1]; t0 /= np.linalg.norm(t0)
    t1 = P[-1] - P[-2]; t1 /= np.linalg.norm(t1)
    pre = P[0] + np.outer(np.arange(n, 0, -1) * step, t0)
    post = P[-1] + np.outer(np.arange(1, n + 1) * step, t1)
    return np.vstack([pre, P, post]), np.concatenate([s[0] - np.arange(n, 0, -1) * step, s,
                                                      s[-1] + np.arange(1, n + 1) * step])


# ================================================================ centreline
def _sample_box(img, X, Y, Z) -> np.ndarray:
    XX, YY, ZZ = np.meshgrid(X, Y, Z, indexing="ij")
    W = np.stack([XX.ravel(), YY.ravel(), ZZ.ravel()], -1)
    return sample_at(img, W).reshape(XX.shape).astype(np.float32)


def _viterbi(score: np.ndarray, lam: float, maxstep: int = 2) -> np.ndarray:
    """Best (x, y) path through a stack of (x, y) score maps, penalising |step|^2 between planes."""
    nx, ny, nz = score.shape
    offs = [(dx, dy) for dx in range(-maxstep, maxstep + 1) for dy in range(-maxstep, maxstep + 1)]
    F = score[:, :, 0].copy()
    back = np.zeros((nz, nx, ny), np.int8)
    NEG = np.float32(-1e6)
    for k in range(1, nz):
        best = np.full((nx, ny), NEG, np.float32)
        which = np.zeros((nx, ny), np.int8)
        for oi, (dx, dy) in enumerate(offs):
            shifted = np.full((nx, ny), NEG, np.float32)
            xs = slice(max(0, dx), nx + min(0, dx)); xd = slice(max(0, -dx), nx + min(0, -dx))
            ys = slice(max(0, dy), ny + min(0, dy)); yd = slice(max(0, -dy), ny + min(0, -dy))
            shifted[xd, yd] = F[xs, ys] - lam * (dx * dx + dy * dy)
            m = shifted > best
            best[m] = shifted[m]; which[m] = oi
        F = best + score[:, :, k]
        back[k] = which
    i, j = np.unravel_index(int(np.argmax(F)), F.shape)
    path = np.zeros((nz, 2), int)
    for k in range(nz - 1, -1, -1):
        path[k] = (i, j)
        if k:
            dx, dy = offs[back[k][i, j]]
            i, j = i + dx, j + dy
    return path


def track_centreline(sub: str, img, cen: np.ndarray, gang: dict, verbose: bool = True) -> dict:
    """The cord centreline from the medulla to the conus tip, then the thecal sac down to the S2 foramen."""
    from scipy import ndimage
    aff = img.affine
    shape = np.asanyarray(img.dataobj).shape
    x0, y0 = float(np.median(cen[:, 0])), float(np.median(cen[:, 1]))
    X = np.arange(x0 - X_HALF, x0 + X_HALF + 1e-6, XY_STEP)
    Yc = np.arange(y0 + Y_CORD[0], y0 + Y_CORD[1] + 1e-6, STEP)
    Ys = np.arange(y0 + Y_SAC[0], y0 + Y_SAC[1] + 1e-6, STEP)
    z_top = aff[2, 3] + (shape[2] - 1) * aff[2, 2]
    z_bot = min(gang.get("S2", cen[-1])[2] - 12.0, cen[-1, 2] - 40.0)

    def blur(a, mm_y, mm_x=5.0):
        ky = max(1, int(round(mm_y / STEP)))
        kx = max(1, int(round(mm_x / XY_STEP))); kx += (kx + 1) % 2
        return ndimage.uniform_filter1d(ndimage.uniform_filter1d(a, ky, axis=1, mode="nearest"),
                                        kx, axis=0, mode="nearest")

    def normalise(I):
        ref = np.percentile(I, 99, axis=(0, 1))
        return I / ndimage.uniform_filter1d(np.maximum(ref, 1.0), 25, mode="nearest")[None, None, :]

    # --- cord: image top down to the conus tip
    Zc = np.arange(z_top, cen[-1, 2] - 1e-6, -Z_STEP)
    In = normalise(_sample_box(img, X, Yc, Zc))
    dark = blur(In, DARK_MM)
    band = blur(In, BAND_MM)
    cordsc = None
    for r in CORD_RADII:
        sh = int(round(r / STEP))
        flank = np.minimum(np.roll(band, sh, axis=1), np.roll(band, -sh, axis=1))
        cordsc = flank - dark if cordsc is None else np.maximum(cordsc, flank - dark)
    zs, xs, ys = cen[::-1, 2], cen[::-1, 0], cen[::-1, 1]
    inside = (Zc >= cen[-1, 2] - 0.6) & (Zc <= cen[0, 2] + 0.6)
    for k in np.flatnonzero(inside):
        d = np.hypot(X[:, None] - np.interp(Zc[k], zs, xs), Yc[None, :] - np.interp(Zc[k], zs, ys))
        cordsc[:, :, k] = np.where(d <= 2.0, cordsc[:, :, k] + 1.0, -9.0)
    pc = _viterbi(cordsc, LAM_CORD)
    Pc = np.column_stack([X[pc[:, 0]], Yc[pc[:, 1]], Zc])
    cord_score = float(np.median(cordsc[pc[:, 0], pc[:, 1], np.arange(len(Zc))][~inside]))
    # the outlines are ground truth -- use them verbatim where they exist
    Pc[inside, 0] = np.interp(Zc[inside], zs, xs)
    Pc[inside, 1] = np.interp(Zc[inside], zs, ys)

    # --- thecal sac: conus tip down to the S2 foramen
    Zs = np.arange(cen[-1, 2] - Z_STEP, z_bot - 1e-6, -Z_STEP)
    In2 = normalise(_sample_box(img, X, Ys, Zs))
    sacsc = blur(In2, SAC_MM)
    start = np.hypot(X[:, None] - Pc[-1, 0], Ys[None, :] - Pc[-1, 1]) <= 2.0
    sacsc[:, :, 0] = np.where(start, sacsc[:, :, 0] + 2.0, -9.0)
    ps = _viterbi(sacsc, LAM_SAC)
    Ps = np.column_stack([X[ps[:, 0]], Ys[ps[:, 1]], Zs])
    sac_score = float(np.median(sacsc[ps[:, 0], ps[:, 1], np.arange(len(Zs))]))

    C = np.vstack([Pc, Ps])
    C[:, 0] = ndimage.uniform_filter1d(C[:, 0], SMOOTH_X, mode="nearest")
    C[:, 1] = ndimage.uniform_filter1d(C[:, 1], SMOOTH_Y, mode="nearest")
    P, s = pam50.resample_arc(C, 0.25)
    P, s = extend(P, s, EXTRAPOLATE, 0.25)
    T, R, A = pam50.carry_frame(P)
    if verbose:
        print(f"  {sub}: centreline {s[-1]:.0f} mm, cord filter {cord_score:.3f}, sac filter {sac_score:.3f}")
    return {"P": P, "s": s, "T": T, "R": R, "A": A,
            "cord_score": cord_score, "sac_score": sac_score,
            "conus_tip": float(project(P, s, T, cen[-1:])[0]),
            "marker_arc": [float(project(P, s, T, cen[:1])[0]), float(project(P, s, T, cen[-1:])[0])]}


OVERLAY_MIN = 1.8       # the cord must be at least this much darker than the CSF around it


def overlay_check(img, cen: np.ndarray) -> dict:
    """Are the CISS markers really on the T2-TSE cord?  Dark core, bright CSF somewhere in the annulus.

    The CSF ring sits at a different radius in every subject (the cord is 8-9 mm across in the lumbar
    enlargement and 2 mm at the conus tip), so the annulus is read at 4, 5, 6 and 7 mm and summarised by its
    90th percentile: "somewhere around this point, within 7 mm, there is CSF".
    """
    ang = np.linspace(0, 2 * np.pi, 32, endpoint=False)

    def ring(r):
        return np.concatenate([sample_at(img, cen + np.array([r * np.cos(a), r * np.sin(a), 0.0]))
                               for a in ang])

    core = float(np.mean([ring(0.0).mean(), ring(1.5).mean()]))
    csf = float(np.percentile(np.concatenate([ring(r) for r in (4.0, 5.0, 6.0, 7.0)]), 90))
    return {"cord_core_mean": round(core, 1), "csf_annulus_p90": round(csf, 1),
            "ratio": round(csf / max(core, 1e-6), 2)}


# ================================================================ discs
def disc_profile(img, fr: dict) -> dict:
    """Anterior canal wall and the disc evidence, per arc, on the straightened mid-sagittal reformat."""
    from scipy.ndimage import gaussian_filter1d, uniform_filter1d
    P, s, A = fr["P"], fr["s"], fr["A"]
    vv = np.arange(-14.0, 40.0 + 1e-6, 0.5)
    W = (P[:, None, :] + vv[None, :, None] * A[:, None, :]).reshape(-1, 3)
    S = sample_at(img, W).reshape(len(P), len(vv))
    ds = s[1] - s[0]
    Sm = uniform_filter1d(S, int(round(3.0 / ds)), axis=0, mode="nearest")
    i0, i1, i2 = (int(np.argmin(np.abs(vv - t))) for t in (1.0, 14.0, 17.0))
    peak = Sm[:, i0:i1].max(1)
    wall = np.empty(len(s))
    for k in range(len(s)):
        good = np.flatnonzero(Sm[k, i0:i2] >= 0.5 * peak[k])
        wall[k] = vv[i0 + good[-1]] + 1.0 if len(good) else 8.0
    wall = uniform_filter1d(np.clip(wall, 3.0, 16.0), int(round(15.0 / ds)), mode="nearest")

    def strip(a, b):
        return np.array([S[k, (vv >= wall[k] + a) & (vv <= wall[k] + b)].mean() for k in range(len(s))])

    post, nucleus = strip(-3.0, 4.0), strip(7.0, 25.0)
    scale = np.maximum(uniform_filter1d(0.5 * (post + nucleus), int(round(120.0 / ds)), mode="nearest"), 1e-6)
    f = (nucleus - post) / scale
    d = gaussian_filter1d(f, 2.0 / ds) - gaussian_filter1d(f, 12.0 / ds)
    return {"vv": vv, "sag": S, "wall": wall, "disc": d.astype(np.float32)}


def disc_viterbi(fr: dict, prof: dict, gang_arc: dict, scale: float) -> tuple[dict[str, float], float]:
    """Assign the 23 named discs to arc positions: image evidence under height and ganglion priors."""
    s, d = fr["s"], prof["disc"]
    step = 0.5
    # positions may run above the top of the image: some subjects (sub-06 most of all) are laid so low in
    # the scanner that the composed stack starts below C2, and the only honest thing to do is to let the
    # chain extrapolate its C2/C3 into the void rather than to pull the whole assignment down a vertebra
    a = np.arange(s[0] - ABOVE_FOV, s[-1] - 4.0, step)
    seen = (a >= s[0] + 2.0) & (a <= s[-1] - 2.0)
    ev = np.where(seen, DISC_WEIGHT * np.interp(a, s, d, left=0.0, right=0.0), 0.0)
    heights = HEIGHTS * scale

    # the C2 body and the dens leave a disc-free stretch immediately above the C2/C3 disc: reward a window
    # there with no disc evidence in it (a window outside the image is neutral, since ev is 0 there)
    lo, hi = (int(round(t / step)) for t in TOP_GAP)
    pad = np.concatenate([np.zeros(hi), ev])
    gap = np.array([pad[k:k + hi - lo].mean() for k in range(len(a))])
    top = -TOP_WEIGHT * gap / max(DISC_WEIGHT, 1e-6)

    anchor = {}
    for lv, name in GANGLION_ANCHORS.items():
        if lv in gang_arc:
            anchor[DISCS.index(name)] = gang_arc[lv] + GANGLION_LEAD * scale
    k_l1 = DISCS.index("L1-L2")
    span = (anchor[k_l1] - scale * float(HEIGHTS[:k_l1].sum())) if k_l1 in anchor else None

    def node(k):
        v = ev.copy()
        if k == 0:
            v = v + top
            if span is not None:
                v = v - 0.5 * ((a - span) / SPAN_SD) ** 2
        if k in anchor:
            v = v - 0.5 * ((a - anchor[k]) / GANGLION_SD) ** 2
        return v

    n = len(a)
    F = node(0)
    back = np.zeros((len(DISCS), n), np.int32)
    for k in range(1, len(DISCS)):
        h = heights[k - 1]
        sd = max(HEIGHT_SD_FLOOR, HEIGHT_SD[k - 1] * h)
        lo_s, hi_s = int(round(0.45 * h / step)), int(round(1.75 * h / step))
        best = np.full(n, -1e9); which = np.zeros(n, np.int32)
        for sh in range(lo_s, hi_s + 1):
            cand = np.full(n, -1e9)
            cand[sh:] = F[:n - sh] - 0.5 * ((sh * step - h) / sd) ** 2
            m = cand > best
            best[m] = cand[m]; which[m] = np.flatnonzero(m) - sh
        F = best + node(k)
        back[k] = which
    j = int(np.argmax(F))
    total = float(F[j])
    out = {}
    for k in range(len(DISCS) - 1, -1, -1):
        out[DISCS[k]] = float(a[j])
        j = int(back[k][j])
    return {k: out[k] for k in DISCS}, total


def find_discs(fr: dict, prof: dict, gang_arc: dict) -> tuple[dict[str, float], dict]:
    """Two passes: a first assignment at the ganglion-derived scale, then one at the measured scale."""
    lumbar = [gang_arc[l] for l in ("L1", "L2", "L3", "L4") if l in gang_arc]
    ref = HEIGHTS[DISCS.index("L1-L2"):DISCS.index("L4-L5")]
    scale = float(np.median(np.diff(lumbar) / ref[:len(lumbar) - 1])) if len(lumbar) >= 3 else 1.0
    scale = float(np.clip(scale, 0.85, 1.2))
    discs, total = disc_viterbi(fr, prof, gang_arc, scale)
    span = discs["L1-L2"] - discs["C2-C3"]
    ref_span = float(HEIGHTS[:DISCS.index("L1-L2")].sum())
    scale2 = float(np.clip(span / ref_span, 0.85, 1.2))
    discs2, total2 = disc_viterbi(fr, prof, gang_arc, scale2)
    if total2 >= total:
        discs, total, scale = discs2, total2, scale2
    return discs, {"scale": round(scale, 4), "viterbi_score": round(total, 2)}


# ================================================================ per subject
def geometry(sub: str, verbose: bool = True) -> dict:
    """Everything about one subject that does not depend on the group: cached, because it is the slow part."""
    cache = CACHE / f"{sub}.json"
    if cache.exists():
        g = json.loads(cache.read_text())
        g["P"] = np.array(g["P"], float); g["s"] = np.array(g["s"], float)
        if verbose:
            print(f"  {sub}: cached, C2-C3 at arc {g['discs']['C2-C3']:.1f} mm")
        return g
    img = t2_image(sub)
    cen, rad = cord_outlines(sub)
    overlay = overlay_check(img, cen)
    if overlay["ratio"] < OVERLAY_MIN:
        raise SystemExit(f"{sub}: cord markers do not sit on a dark cord inside bright CSF "
                         f"({overlay}); the markers and the T2-TSE may not share a world frame")
    gang = ganglia(sub)
    fr = track_centreline(sub, img, cen, gang, verbose)
    prof = disc_profile(img, fr)
    gang_arc = {lv: float(project(fr["P"], fr["s"], fr["T"], p[None])[0]) for lv, p in gang.items()}
    discs, meta = find_discs(fr, prof, gang_arc)
    s0 = discs["C2-C3"]
    g = {"id": sub, "P": fr["P"], "s": fr["s"],
         "discs": {k: round(v - s0, 3) for k, v in discs.items()},
         "disc_arc_raw": {k: round(v, 3) for k, v in discs.items()},
         "s0": round(s0, 3),
         "conus_tip": round(fr["conus_tip"] - s0, 2),
         "conus_radius_mm": round(float(rad[-1]), 2),
         "sac_end": round(float(fr["s"][-1] - EXTRAPOLATE - s0), 2),
         "marker_arc": [round(x - s0, 2) for x in fr["marker_arc"]],
         "ganglion_arc": {k: round(v - s0, 2) for k, v in gang_arc.items()},
         "rootlet_origin_arc": {k: round(v - s0, 2)
                                for k, v in rootlet_origins(sub, fr["P"], fr["s"], fr["T"]).items()},
         "imaged_from_arc": round(float(fr["s"][0] + EXTRAPOLATE - s0), 2),
         "cord_score": round(fr["cord_score"], 4), "sac_score": round(fr["sac_score"], 4),
         "overlay": overlay, "disc_meta": meta}
    CACHE.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({**g, "P": np.round(g["P"], 4).tolist(),
                                 "s": np.round(g["s"], 4).tolist()}))
    return g


def straighten(sub: str, g: dict, arc: np.ndarray, warp: np.ndarray, verbose: bool = True) -> dict:
    """Resample one subject onto the group lattice, normalised, with its cord mask.

    `warp[i]` is the arc *in this subject* that belongs at template row `arc[i]`, so the level matching and the
    reformat happen in a single interpolation.
    """
    from scipy import ndimage
    img = t2_image(sub)
    P, s = g["P"], g["s"]
    T, R, A = pam50.carry_frame(P)
    uu = np.arange(-RADIUS, RADIUS + 1e-6, STEP)
    AA, UU, VV = np.meshgrid(warp + g["s0"], uu, uu, indexing="ij")
    a = AA.ravel()
    inside = (a >= s[0]) & (a <= s[-1])
    world = np.empty((a.size, 3), np.float32)
    for k in range(3):
        world[:, k] = (np.interp(a, s, P[:, k])
                       + UU.ravel() * np.interp(a, s, R[:, k]) + VV.ravel() * np.interp(a, s, A[:, k]))
    img_v, fov = sample_at(img, world, with_fov=True)
    img_v = img_v.astype(np.float32)
    inside &= fov
    img_v[~inside] = np.nan

    r = np.hypot(UU.ravel(), VV.ravel())
    is_cord = (warp <= g["conus_tip"]) & (warp >= -20.0)     # the cord-bearing rows, in this subject's arc
    band = inside & np.repeat(is_cord, uu.size * uu.size)
    core = band & (r <= 3.0)
    tube = band & (r <= 8.0)
    cord_med = float(np.median(img_v[core])) if core.any() else 1.0
    csf_p95 = float(np.percentile(img_v[tube], 95)) if tube.any() else cord_med + 1.0
    norm = (img_v - cord_med) * (0.5 / max(csf_p95 - cord_med, 1e-6)) + 0.5

    shape = (arc.size, uu.size, uu.size)
    vol = norm.reshape(shape)
    mask = ((norm < 0.75) & (r <= 6.5) & inside).reshape(shape)
    mask[warp > g["conus_tip"]] = False
    cord = np.zeros(shape, bool)
    c = uu.size // 2
    for i in np.flatnonzero(warp <= g["conus_tip"]):
        if not mask[i, c, c]:
            continue
        lab, _ = ndimage.label(mask[i])
        cord[i] = lab == lab[c, c]
    if verbose:
        print(f"  {sub}: cord {cord_med:.0f} / CSF {csf_p95:.0f}, "
              f"{int(np.isfinite(vol).any(axis=(1, 2)).sum())} of {arc.size} rows covered")
    return {"vol": vol, "cord": cord, "norm": {"cord_median": cord_med, "csf_p95": csf_p95}}


# ================================================================ template
def warp_arcs(subs: list[dict], arc: np.ndarray) -> tuple[dict[str, float], dict[str, np.ndarray], np.ndarray]:
    """Group-mean disc arcs, and for each subject the inverse warp template arc -> that subject's arc."""
    keys = [k for k in DISCS if all(k in g["discs"] for g in subs)]
    mean = {k: float(np.mean([g["discs"][k] for g in subs])) for k in keys}
    xs = np.array([mean[k] for k in keys])
    warps = {}
    for g in subs:
        src = np.array([g["discs"][k] for k in keys])
        w = np.interp(arc, xs, src, left=np.nan, right=np.nan)
        k0 = (src[1] - src[0]) / (xs[1] - xs[0]); k1 = (src[-1] - src[-2]) / (xs[-1] - xs[-2])
        lo = np.isnan(w) & (arc < xs[0]); hi = np.isnan(w) & (arc > xs[-1])
        w[lo] = src[0] + (arc[lo] - xs[0]) * k0
        w[hi] = src[-1] + (arc[hi] - xs[-1]) * k1
        warps[g["id"]] = w
    before = np.array([[g["discs"][k] - mean[k] for k in keys] for g in subs])
    return mean, warps, before


def build_template(ids: list[str], geoms: list[dict], verbose: bool = True) -> dict:
    min_n = min(MIN_SUBJECTS, len(geoms))   # a --subjects subset still builds, for QA
    arc = np.arange(ARC_LO, ARC_HI + 1e-6, STEP)
    uu = np.arange(-RADIUS, RADIUS + 1e-6, STEP)
    mean_disc, warps, before = warp_arcs(geoms, arc)
    shape = (arc.size, uu.size, uu.size)
    total = np.zeros(shape, np.float32)
    count = np.zeros(shape, np.int16)
    cord = np.zeros(shape, np.float32)
    cord_n = np.zeros(shape, np.int16)
    norms = {}
    for g in geoms:
        sb = straighten(g["id"], g, arc, warps[g["id"]], verbose)
        ok = np.isfinite(sb["vol"])
        total[ok] += sb["vol"][ok]
        count[ok] += 1
        cord += sb["cord"].astype(np.float32)
        cord_n[ok] += 1
        norms[g["id"]] = sb["norm"]
        del sb
    with np.errstate(invalid="ignore"):
        avg = total / np.maximum(count, 1)
        prob = cord / np.maximum(cord_n, 1)
    keep = count >= min_n
    avg[~keep] = np.nan
    prob[~keep] = 0.0
    per_arc = count.max(axis=(1, 2))
    return {"arc": arc, "inplane": uu, "avg": avg, "count": count.astype(np.int16), "cord": prob,
            "row_count": per_arc, "keep": per_arc >= min_n, "min_n": min_n, "discs": mean_disc,
            "disc_sd": {k: float(before[:, i].std()) for i, k in enumerate(mean_disc)},
            "norms": norms}


# ================================================================ QA pictures
def _panel(ax, image, extent, title=None):
    ax.imshow(image, cmap="gray", vmin=0, vmax=np.nanpercentile(image, 99.5), extent=extent,
              aspect="equal", origin="upper")
    if title:
        ax.set_title(title, fontsize=7)
    ax.tick_params(labelsize=6)


def subject_figure(sub: str, g: dict, out):
    """Curved sagittal and coronal reformats of one subject with the centreline and the labelled discs."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    img = t2_image(sub)
    P, s = g["P"], g["s"]
    T, R, A = pam50.carry_frame(P)
    off = np.arange(-30.0, 40.0 + 1e-6, 0.5)
    sagittal = sample_at(img, (P[:, None, :] + off[None, :, None] * A[:, None, :]).reshape(-1, 3)
                         ).reshape(len(P), len(off))
    coff = np.arange(-25.0, 25.0 + 1e-6, 0.5)
    coronal = sample_at(img, (P[:, None, :] + coff[None, :, None] * R[:, None, :]).reshape(-1, 3)
                        ).reshape(len(P), len(coff))
    s0 = g["s0"]
    bands = np.linspace(s[0], s[-1], 4)
    fig, axs = plt.subplots(1, 6, figsize=(17, 13))
    for b in range(3):
        m = (s >= bands[b]) & (s <= bands[b + 1])
        for col, (data, xs) in enumerate([(sagittal, off), (coronal, coff)]):
            ax = axs[2 * b + col]
            _panel(ax, data[m], [xs[0], xs[-1], s[m][-1] - s0, s[m][0] - s0],
                   f"{sub} {'sagittal' if col == 0 else 'coronal'}")
            ax.axvline(0.0, color="r", lw=0.5, alpha=0.7)
            for name, a in g["discs"].items():
                if bands[b] - s0 <= a <= bands[b + 1] - s0:
                    ax.axhline(a, color="lime", lw=0.6)
                    if col == 0:
                        ax.text(xs[-1] - 1, a, name, color="lime", fontsize=6, ha="right", va="bottom")
            for a, lab, c in [(g["conus_tip"], "conus", "cyan"), (0.0, "arc 0", "yellow")]:
                if bands[b] - s0 <= a <= bands[b + 1] - s0:
                    ax.axhline(a, color=c, lw=0.8, ls="--")
                    ax.text(xs[0] + 1, a, lab, color=c, fontsize=6, va="top")
    fig.suptitle(f"{sub}  C2-C3 -> conus {g['conus_tip']:.0f} mm, sac to {g['sac_end']:.0f} mm, "
                 f"cord filter {g['cord_score']:.2f}, marker overlay ratio {g['overlay']['ratio']}", fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.985))
    fig.savefig(out, dpi=95)
    plt.close(fig)


def template_figure(tpl: dict, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    arc, uu, avg = tpl["arc"], tpl["inplane"], tpl["avg"]
    c = uu.size // 2
    keep = tpl["keep"]
    lo, hi = float(arc[keep].min()), float(arc[keep].max())
    fig = plt.figure(figsize=(17, 13))
    gs = fig.add_gridspec(2, 6, height_ratios=[6, 1])
    bands = np.linspace(lo, hi, 4)
    for b in range(3):
        m = (arc >= bands[b]) & (arc <= bands[b + 1])
        for col, (data, name) in enumerate([(avg[:, c, :], "sagittal (u = 0)"),
                                            (avg[:, :, c], "coronal (v = 0)")]):
            ax = fig.add_subplot(gs[0, 2 * b + col])
            _panel(ax, data[m], [uu[0], uu[-1], arc[m][-1], arc[m][0]], name)
            for key, a in tpl["discs"].items():
                if bands[b] <= a <= bands[b + 1]:
                    ax.axhline(a, color="lime", lw=0.6)
                    if col == 0:
                        ax.text(uu[-1] - 0.5, a, key, color="lime", fontsize=6, ha="right", va="bottom")
    shows = [k for k in ("C4-C5", "C7-T1", "T4-T5", "T8-T9", "T12-L1", "L3-L4") if k in tpl["discs"]]
    for i, key in enumerate(shows):
        ax = fig.add_subplot(gs[1, i])
        j = int(np.argmin(np.abs(arc - tpl["discs"][key])))
        _panel(ax, avg[j].T[::-1], [uu[0], uu[-1], uu[0], uu[-1]], f"axial at {key}")
        ax.contour(uu, uu[::-1], tpl["cord"][j].T[::-1], levels=[0.25, 0.5, 0.75],
                   colors=["#ff6", "#f60", "#f00"], linewidths=0.7)
    fig.suptitle(f"fudan_t2 template: arc {lo:.0f} .. {hi:.0f} mm from C2-C3, "
                 f"{int(tpl['row_count'].max())} subjects at best, >= {tpl['min_n']} per row; axial contours = cord probability 0.25 / 0.5 / 0.75", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.985))
    fig.savefig(out, dpi=95)
    plt.close(fig)


# ================================================================ driver
def conus_level(tpl_discs: dict[str, float], conus: float) -> str:
    """Which vertebra the conus tip sits at, from that subject's own discs."""
    keys = [k for k in DISCS if k in tpl_discs]
    for v in VERTEBRAE:
        above = next((k for k in keys if k.endswith(f"-{v}")), None)
        below = next((k for k in keys if k.startswith(f"{v}-")), None)
        if above and below and tpl_discs[above] <= conus < tpl_discs[below]:
            frac = (conus - tpl_discs[above]) / (tpl_discs[below] - tpl_discs[above])
            return f"{v}{'upper' if frac < 0.34 else ('mid' if frac < 0.67 else 'lower')}"
        if below and conus < tpl_discs[below] and above is None:
            return f"above {below}"
    return "below the last disc"


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="atlas-fudan-spine", description=__doc__.split("\n")[0])
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--subjects", default="", help="comma separated, e.g. 01,07 or sub-01")
    a = ap.parse_args(argv)
    v = not a.quiet

    ids = subjects()
    if a.subjects:
        want = {x if x.startswith("sub-") else f"sub-{x}" for x in a.subjects.split(",")}
        ids = [i for i in ids if i in want]
    print(f"lumbosacral_fudan: {len(ids)} subjects -> {', '.join(i.replace('sub-', '') for i in ids)}")

    geoms = [geometry(sub, v) for sub in ids]
    tpl = build_template(ids, geoms, v)
    QA_DIR.mkdir(parents=True, exist_ok=True)
    for g in geoms:
        subject_figure(g["id"], g, QA_DIR / f"{g['id']}.png")
    template_figure(tpl, QA_DIR / "template.png")

    # ---------------- plausibility
    print("\nvertebral heights (disc to disc, mm)")
    print(f"{'vert':>5} {'mean':>7} {'sd':>6} {'prior':>7}")
    heights = {}
    for i, name in enumerate(HEIGHT_NAMES):
        k0, k1 = DISCS[i], DISCS[i + 1]
        hs = [g["discs"][k1] - g["discs"][k0] for g in geoms if k0 in g["discs"] and k1 in g["discs"]]
        if hs:
            heights[name] = (float(np.mean(hs)), float(np.std(hs)))
            print(f"{name:>5} {np.mean(hs):7.1f} {np.std(hs):6.1f} {HEIGHTS[i]:7.1f}")
    lengths = [g["conus_tip"] for g in geoms]
    print(f"\nC2-C3 -> conus tip: mean {np.mean(lengths):.0f} mm, sd {np.std(lengths):.0f}, "
          f"range {min(lengths):.0f} .. {max(lengths):.0f} (literature 380-430)")
    levels, vertebra = {}, {}
    print(f"{'subject':>8} {'conus arc':>10} {'level':>10} {'sac end':>9} {'discs':>6} {'overlay':>8}")
    for g in geoms:
        lv = conus_level(g["discs"], g["conus_tip"])
        levels[g["id"]] = lv
        vertebra[g["id"]] = lv.rstrip("upermidlow")
        print(f"{g['id']:>8} {g['conus_tip']:10.1f} {lv:>10} {g['sac_end']:9.1f} "
              f"{len(g['discs']):6d} {g['overlay']['ratio']:8.2f}")
    print("\ndisc scatter before the warp (mm sd over subjects)")
    for k, sd in tpl["disc_sd"].items():
        print(f"   {k:>7} mean arc {tpl['discs'][k]:7.1f}   sd {sd:5.2f}")
    per = tpl["row_count"]
    keep = tpl["keep"]
    print(f"\nrows with >= {tpl['min_n']} subjects: {int(keep.sum())} of {keep.size} "
          f"(arc {tpl['arc'][keep].min():.1f} .. {tpl['arc'][keep].max():.1f} mm); "
          f"all {len(ids)} subjects on {int((per == len(ids)).sum())} rows")

    qa = {"subjects": ids, "n_subjects": len(ids),
          "marker_overlay": {g["id"]: g["overlay"] for g in geoms},
          "tracking": {g["id"]: {"cord_filter": g["cord_score"], "sac_filter": g["sac_score"],
                                 "conus_tip_arc": g["conus_tip"], "conus_level": levels[g["id"]],
                                 "sac_end_arc": g["sac_end"], "disc_scale": g["disc_meta"]["scale"],
                                 "viterbi_score": g["disc_meta"]["viterbi_score"],
                                 "n_discs": len(g["discs"]),
                                 "imaged_from_arc": g["imaged_from_arc"]} for g in geoms},
          "rootlet_origin_arc_mm": {g["id"]: g["rootlet_origin_arc"] for g in geoms},
          "rootlet_note": "arc of the rostral end of each traced intradural nerve root (mean of the two "
                          "sides).  Ordered L1 .. S2 in every subject, but the traces start where the "
                          "annotator could first separate the root inside the sac, so they are a "
                          "consistency check on the conus end of the template and NOT published as "
                          "spinal levels",
          "disc_sd_before_warp_mm": {k: round(x, 2) for k, x in tpl["disc_sd"].items()},
          "disc_arc_per_subject_mm": {g["id"]: g["discs"] for g in geoms},
          "vertebral_height_mm": {k: [round(m, 1), round(sd, 1)] for k, (m, sd) in heights.items()},
          "cord_length_c2c3_to_conus_mm": {"mean": round(float(np.mean(lengths)), 1),
                                           "sd": round(float(np.std(lengths)), 1),
                                           "min": round(min(lengths), 1), "max": round(max(lengths), 1)},
          "rows_per_subject_count": {str(int(n)): int((per == n).sum()) for n in np.unique(per)},
          "normalisation": tpl["norms"],
          "note": "the T2-TSE is a DICOM-COMPOSED four-station whole-spine image; faint intensity steps at "
                  "the station seams survive the single global pair of intensity anchors the template "
                  "contract asks for"}
    if a.no_write:
        print("\n--no-write: nothing written")
        return
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(TEMPLATE_DIR / f"{NAME}.npz",
                        arc=tpl["arc"].astype(np.float32), inplane=tpl["inplane"].astype(np.float32),
                        avg=tpl["avg"].astype(np.float32), cord=tpl["cord"].astype(np.float32),
                        count=tpl["row_count"].astype(np.int16))
    meta = {
        "source": SOURCE, "license": LICENSE, "step_mm": STEP,
        "discs": {k: round(x, 2) for k, x in tpl["discs"].items()},
        "subjects": [i.replace("sub-", "") for i in ids],
        "conus_tip_arc": round(float(np.mean(lengths)), 2),
        "coverage": {
            "arc_mm": [round(float(tpl["arc"][keep].min()), 2), round(float(tpl["arc"][keep].max()), 2)],
            "vertebral_levels": ["C2", "S2"],
            "sequence": "T2-TSE, composed whole spine (4 stations), sagittal",
            "resolution_mm": "0.62 x 0.62 x 3.3 mm sagittal, composed whole spine",
            "n_subjects": len(ids), "min_subjects_per_row": tpl["min_n"],
            "conus_tip_level_mode": max(set(vertebra.values()), key=list(vertebra.values()).count),
            "conus_tip_level_per_subject": levels,
            "note": "healthy adults 22-25 y; arc 0 is the C2-C3 disc.  The arc range runs from about the "
                    "foramen magnum (the medulla, roughly 46 mm rostral of the C2-C3 disc) to about the S2 "
                    "level, where the thecal sac ends; the last named disc is L5-S1 at the sacral "
                    "promontory.  The cord probability is 0 below the conus tip, where the volume shows the "
                    "thecal sac and cauda equina only.  In-plane resolution is 0.62 mm sagittal but 3.3 mm "
                    "left-right, so the template is blurred across the sagittal plane"},
        "qa": qa,
    }
    (TEMPLATE_DIR / f"{NAME}.json").write_text(json.dumps(meta, indent=1))
    (QA / "fudan_spine.json").write_text(json.dumps(qa, indent=1))
    size = (TEMPLATE_DIR / f"{NAME}.npz").stat().st_size
    print(f"\nwrote {TEMPLATE_DIR / (NAME + '.npz')} ({size / 1e6:.1f} MB), "
          f"{TEMPLATE_DIR / (NAME + '.json')} and {QA / 'fudan_spine.json'}")
    print(f"      {QA_DIR}/sub-XX.png and {QA_DIR}/template.png")


if __name__ == "__main__":
    main()
