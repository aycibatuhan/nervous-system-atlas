"""Phase 10c: compose the PUBLIC edition's cord MRI out of one or more openly licensed straightened templates.

  atlas-cord-public [--spacing 0.75] [--no-write] [--quiet] [--selftest]

Why a compose step
------------------
The public edition may not ship anything derived from PAM50, so its cord MRI is built here from data that may
be redistributed.  No single open dataset covers the whole cord well: the spine-generic average
(`atlas-spine-generic`, 10 subjects, 0.8 mm isotropic, manual disc + rootlet labels) stops at about T3, and the
Fudan whole-spine T2-TSE average (`atlas-fudan-spine`, 14 subjects, 0.62 x 0.62 x 3.3 mm sagittal) runs from
the foramen magnum to the sacrum but is anisotropic.  Each of those steps writes a *straightened template* into
pipeline/work/cord_public/ in the contract below; this step lays every template it finds along our own cord
centreline (pam50.cord_frame / pam50.tube_grid, the same curve the private edition uses), level-matches them to
the Z-Anatomy vertebral column, blends their overlap and writes the public cord volumes.

Template contract (pipeline/work/cord_public/<name>.npz + <name>.json)
----------------------------------------------------------------------
<name>.npz (np.savez_compressed), all in "template coordinates": arc length along the straightened cord in mm,
measured from the template's own C2/C3 intervertebral disc (arc 0), positive caudally; u = right, v = anterior.
  arc      float32 (N,)       arc of each row, increasing, uniform step (STEP = 0.5 mm)
  inplane  float32 (M,)       u and v sample positions, uniform, symmetric about 0, spanning +-16 mm (R_FADE)
  avg      float32 (N, M, M)  the averaged, normalised intensity; NaN wherever the template has no data.
                              Normalisation: the cord's own median -> 0.5 and the 95th percentile of the
                              surrounding CSF -> 1.0 (spine_generic.straighten does exactly this), so two
                              templates can be blended without re-windowing
  cord     float32 (N, M, M)  cord probability 0..1 (fraction of subjects whose cord covers the voxel); 0 or
                              NaN where unknown
  count    int16   (N,)       subjects contributing to each arc row (0 where avg is NaN)
<name>.json
  source           the sources.yaml id (spine_generic, lumbosacral_fudan)
  license          its licence id (must not be nc / no_redistribution)
  step_mm          0.5
  discs            {"C2-C3": 0.0, "C3-C4": 14.1, ...}: group-mean arc of every intervertebral disc the
                   template located, keyed exactly like the Z-Anatomy objects ("Intervertebral disc <key>"),
                   so the compose step can map template arc -> Z-Anatomy disc arc on our centreline
                   piecewise-linearly.  The C2-C3 entry is always 0.0
  subjects         list of subject ids
  spinal_levels    optional {"C2": [a0, a1], ...} measured spinal-level bands in template arc (rootlets)
  level_method     optional, free-form provenance of spinal_levels
  conus_tip_arc    optional, group-mean arc of the tip of the conus medullaris
  coverage         {"arc_mm": [lo, hi], "vertebral_levels": [first, last], "note": "..."} and anything else
                   worth carrying into cord_public.json (resolution, sequence, subject count)
  qa               optional per-template QA numbers (disc scatter before/after warp, ...)

Precedence when templates overlap: the isotropic spine-generic template wins where it has data, and the
blend into the next template happens over the last BLEND_MM of its coverage.

How a template is laid down
---------------------------
1. `zanatomy_disc_arcs()` projects the centre of every "Intervertebral disc <key>" object of the Z-Anatomy
   vertebral column -- the same specimen the cord surface comes from, mapped by the same affine and midline
   correction -- onto our cord centreline, giving the arc length of each disc on our own geometry.
2. For each template, the discs it shares with that list give a piecewise-linear map template arc -> our arc.
   The map is exact at every shared disc (so the level-matching residual is zero by construction; what is
   reported instead is the stretch factor of each inter-disc segment) and has slope exactly 1 beyond the
   outermost shared disc in each direction, so the medulla band above the C2/C3 disc is translated, never
   stretched.
3. One tube grid is built over the union of the templates' arc coverage, every template is read on it, and
   the templates are blended in precedence order: the first wins wherever it has data and hands over to the
   next across the last BLEND_MM of its coverage with a smoothstep ramp.  Both templates are normalised the
   same way, so the blend is a plain intensity mix; the composite is then windowed on its own cord voxels.
4. Spinal levels are painted from whatever template measured them (the spine-generic rootlets, C2-T1), and
   below the last measured level from the classical cord-segment-to-vertebra rule read off the same
   Z-Anatomy landmarks `derived.py` cuts the public `-vert` cord blocks at.  Those ids are marked
   `estimated` in the lookup table, and the app names them "<level> (vertebral rule)".

Outputs (public/data/volumes/), all tagged `edition: "public"` by atlas-manifest
-------------------------------------------------------------------------------
cord_t2_public.u8.bin, labels_spine_public.u8.bin, labels_spine_public.json, cord_public.json,
cord_levels_public.json -- the same files atlas-spine-generic used to write on its own.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from . import midline, pam50
from .paths import CONFIG, MESHES, RAW, ROOT, VOLUMES, WORK

TEMPLATE_DIR = WORK / "cord_public"
STEP = 0.5          # mm, arc and in-plane step of every template
BLEND_MM = 20.0     # mm over which one template hands over to the next

# Which template wins where they overlap: the isotropic cervical average first, then the whole-spine one,
# then anything else that turns up, alphabetically.
PRECEDENCE = ("spine_generic_t2", "fudan_t2")

MNI_T2 = RAW / "mni_t1w" / "tpl-MNI152NLin2009cAsym_res-01_T2w.nii.gz"
ZA_DISC_PREFIX = "Intervertebral disc "
ZA_ANCHOR = ZA_DISC_PREFIX + "C2-C3"
STRETCH_FLAG = (0.85, 1.15)     # inter-disc stretch outside this is worth naming in cord_public.json
STRETCH_GATE = (0.7, 1.45)      # ... and outside this atlas-qa fails the build (see canal_frame / qa.py)
CANAL_GLB = MESHES / "spinal-cord" / "cauda-equina.glb"   # continues the canal below the cord surface
CANAL_HALF_WIDTH = 6.0          # mm: only vertices this close to the midline trace the sac, not the exiting roots
CANAL_SLAB = 2.0                # mm: z step of the canal centroids appended below the cord
MESH_SUFFIX = "-vert"           # the public edition's cord segment blocks are the `-vert` ones
SPINE_SOURCE = "spine_generic"  # fallback `source` when no template says

# vertebra -> the disc above it and the disc below it, keyed like the Z-Anatomy objects.  Label 1 of the
# spine-generic disc convention is a point at the top of C1 rather than a disc, so C1 is bounded above by
# "C1(top)"; there is no Z-Anatomy object for it, and none for "C1-C2" either, which is why those two keys
# only ever come from a template and never from the vertebral column.
VERTEBRAE = [f"C{i}" for i in range(1, 8)] + [f"T{i}" for i in range(1, 13)] + [f"L{i}" for i in range(1, 6)]
DISC_ABOVE = {"C1": "C1(top)", **{b: f"{a}-{b}" for a, b in zip(VERTEBRAE, VERTEBRAE[1:])}}
DISC_BELOW = {**{a: f"{a}-{b}" for a, b in zip(VERTEBRAE, VERTEBRAE[1:])}, "L5": "L5-S1"}

# The classical cord-segment-to-vertebra rule, exactly as the public `-vert` cord blocks in derived.py cut it:
# each block ends at a Z-Anatomy landmark, and the levels it holds divide it equally.  `conus_level()` there
# puts the tip of the conus at the middle of the L1-L2 disc, so the sacral block ends where that block does.
ESTIMATED_BLOCKS = [
    ("cervical", [f"C{i}" for i in range(1, 9)], ZA_DISC_PREFIX + "C7-T1"),
    ("thoracic", [f"T{i}" for i in range(1, 13)], ZA_DISC_PREFIX + "T9-T10"),
    ("lumbar", [f"L{i}" for i in range(1, 6)], "Vertebra T12"),
    ("sacral", [f"S{i}" for i in range(1, 6)], ZA_DISC_PREFIX + "L1-L2"),
]
ESTIMATED_RULE = (
    "below the last measured level the ids are ESTIMATED from the classical cord-segment-to-vertebra rule and "
    "the Z-Anatomy vertebral column alone, not from any image: C8 ends at the C7/T1 intervertebral disc, T12 "
    "at the T9/T10 disc, L5 at the mid-body of the T12 vertebra and S5 at the tip of the conus medullaris, "
    "put at the middle of the L1-L2 disc -- the same four landmarks derived.py cuts the public cord segment "
    "blocks at -- with each block divided equally among the levels it holds, starting where the measured T1 "
    "ends.  They say which vertebra a level lies opposite, not where the rootlets actually leave the cord.")


# ---------------------------------------------------------------- geometry helpers
def project(P: np.ndarray, s: np.ndarray, T: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Arc length of the foot of the perpendicular from each point onto the centreline."""
    from scipy.spatial import cKDTree
    d, i = cKDTree(P).query(np.atleast_2d(pts))
    return s[i] + np.einsum("ij,ij->i", np.atleast_2d(pts) - P[i], T[i])


def zanatomy_points() -> dict[str, np.ndarray]:
    """Every exported Z-Anatomy object -> the MNI-mm centre of its bounding box."""
    cfg = json.loads((CONFIG / "zanatomy_to_mni.json").read_text())
    objs = json.loads((WORK / "zanatomy" / "objects.json").read_text())
    M, pc = np.array(cfg["matrix"]), cfg.get("post_correction")
    return {o["name"].strip(): midline.transform(np.array(o["bbox"], float).mean(0)[None, :], M, pc)[0]
            for o in objs}


def canal_frame(verbose: bool = True) -> dict:
    """pam50.cord_frame() continued down the lumbosacral canal.

    The Z-Anatomy cord surface (and its spinal dura) stop at the L2/L3 disc, but the Fudan template runs on
    to the end of the thecal sac at S2 and the L3-L4 .. L5-S1 discs it is level-matched on lie below the
    cord's end.  A tube that simply carries on along the cord's last tangent misses the Z-Anatomy sacral
    canal by up to 70 mm at S1, because the canal bends posteriorly through the sacrum.  So below the cord
    the centreline follows the Z-Anatomy "Cauda equina" surface: per-z medians of its vertices within
    CANAL_HALF_WIDTH of the midline (the roots leaving through the foramina lie further out and are ignored),
    which trace the sac itself from the cord's end to the coccyx, joined to the cord centreline and smoothed
    across the junction.  Above the cord's end nothing changes, so the private edition's reformat and every
    arc measured on the cord are untouched.
    """
    import subprocess
    import tempfile
    import trimesh
    from scipy.ndimage import uniform_filter1d
    fr = pam50.cord_frame()
    P = fr["centreline"]
    if not CANAL_GLB.exists():
        if verbose:
            print(f"canal: {CANAL_GLB} is missing, the tube ends with the cord surface")
        return fr
    gt = ROOT / "node_modules" / ".bin" / "gltf-transform"
    with tempfile.TemporaryDirectory() as td:
        plain = Path(td) / "canal.glb"
        r = subprocess.run([str(gt), "dequantize", str(CANAL_GLB), str(plain)], capture_output=True, text=True)
        if r.returncode != 0 or not plain.exists():
            raise SystemExit(f"canal: gltf-transform could not decode {CANAL_GLB}: {r.stderr}")
        V = np.asarray(trimesh.load(str(plain), force="mesh").vertices, float)
    mid = V[np.abs(V[:, 0]) < CANAL_HALF_WIDTH]
    z_end = float(P[-1, 2])
    rows = []
    for z in np.arange(z_end - CANAL_SLAB, mid[:, 2].min(), -CANAL_SLAB):
        sel = np.abs(mid[:, 2] - z) < CANAL_SLAB
        if sel.sum() >= 6:
            rows.append([float(np.median(mid[sel, 0])), float(np.median(mid[sel, 1])), float(z)])
    if len(rows) < 5:
        if verbose:
            print("canal: the cauda equina surface has no midline vertices below the cord, tube ends with the cord")
        return fr
    C = np.array(rows)
    # join: the cord centreline at its own (0.25 mm) step, then the canal rows; smooth x and y across the seam
    tail = P[-int(round(40 / 0.25)):]                    # the last 40 mm of cord
    J = np.vstack([tail, C])
    w = int(round(15 / CANAL_SLAB)) | 1
    J[:, 0] = uniform_filter1d(J[:, 0], w, mode="nearest")
    J[:, 1] = uniform_filter1d(J[:, 1], w, mode="nearest")
    ext = np.vstack([P[:-len(tail)], J])
    P2, s2 = pam50.resample_arc(ext, 0.25)
    T, R, A = pam50.carry_frame(P2)
    out = {**fr, "centreline": P2, "arc": s2, "frame": (T, R, A), "canal_arc_total": float(s2[-1]),
           "canal_source": str(CANAL_GLB.relative_to(ROOT)),
           "canal_z_mm": [round(float(C[-1, 2]), 2), round(z_end, 2)]}
    if verbose:
        print(f"canal: centreline continued below the cord (z {z_end:.1f}) along {out['canal_source']} "
              f"to z {C[-1, 2]:.1f}; total arc {s2[-1]:.1f} mm (cord {fr['cord_arc_total']:.1f})")
    return out


def zanatomy_disc_arcs(fr: dict) -> tuple[dict[str, float], dict[str, list[float]]]:
    """Arc length on our own cord centreline of every Z-Anatomy intervertebral disc, and its world point.

    The atlas' cord surface and its vertebral column are the same Z-Anatomy specimen, mapped to MNI by the
    same affine and midline correction, so the discs give a ladder of landmarks on our geometry that owes
    nothing to any cord template.  It is what fixes where each template is laid down, and how it is stretched.
    """
    pts = {n[len(ZA_DISC_PREFIX):]: p for n, p in zanatomy_points().items() if n.startswith(ZA_DISC_PREFIX)}
    if not pts:
        raise SystemExit("no 'Intervertebral disc ...' objects in work/zanatomy/objects.json")
    P, s, T = fr["centreline"], fr["arc"], fr["frame"][0]
    arcs = {k: float(a) for k, a in zip(pts, project(P, s, T, np.array(list(pts.values()))))}
    order = sorted(arcs, key=lambda k: arcs[k])
    return {k: arcs[k] for k in order}, {k: [round(float(x), 2) for x in pts[k]] for k in order}


def zanatomy_landmark_arc(fr: dict, name: str) -> float:
    """Arc on our centreline of one named Z-Anatomy object (its bounding-box centre)."""
    pts = zanatomy_points()
    if name not in pts:
        raise SystemExit(f"work/zanatomy/objects.json has no object named {name!r}")
    P, s, T = fr["centreline"], fr["arc"], fr["frame"][0]
    return float(project(P, s, T, pts[name][None, :])[0])


def anchor_on_centreline(fr: dict) -> tuple[float, dict]:
    """Arc length on our own cord centreline of the C2/C3 disc, from the Z-Anatomy vertebral column.

    Kept at its original name and signature (`atlas-spine-generic` re-exports it): the second element is the
    provenance block cord_public.json carries, including `all_disc_arc_mm`, the whole disc ladder.
    """
    arcs, world = zanatomy_disc_arcs(fr)
    key = ZA_ANCHOR[len(ZA_DISC_PREFIX):]
    if key not in arcs:
        raise SystemExit(f"{ZA_ANCHOR} is not in work/zanatomy/objects.json")
    return arcs[key], {"landmark": ZA_ANCHOR, "world_mm": world[key], "arc_mm": round(arcs[key], 2),
                       "all_disc_arc_mm": {k: round(v, 2) for k, v in arcs.items()}}


def world_levels(fr: dict, s_anchor: float, levels: dict[str, tuple[float, float]]) -> list[dict]:
    """Template arc -> arc on our centreline -> world mm, in the shape cord_levels.json uses.

    With `s_anchor = 0` the bands are already arcs on our centreline, which is how the compose step calls it.
    """
    P, s = fr["centreline"], fr["arc"]
    out = []
    for name, band in levels.items():
        a0, a1 = float(band[0]), float(band[1])
        rec = {"name": name, "arc_mm": [round(s_anchor + a0, 2), round(s_anchor + a1, 2)]}
        for key, arc in (("top", s_anchor + a0), ("bottom", s_anchor + a1)):
            rec[key] = [round(float(np.interp(arc, s, P[:, k])), 2) for k in range(3)]
        rec["z_mm"] = [rec["bottom"][2], rec["top"][2]]
        out.append(rec)
    return out


def world_point(fr: dict, arc: float) -> list[float]:
    P, s = fr["centreline"], fr["arc"]
    return [round(float(np.interp(arc, s, P[:, k])), 2) for k in range(3)]


# ---------------------------------------------------------------- one straightened template
def _pwl(x, src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """Piecewise-linear map through the knots (src -> dst), continued with slope exactly 1 beyond them."""
    x = np.atleast_1d(np.asarray(x, float))
    y = np.interp(x, src, dst)
    lo, hi = x < src[0], x > src[-1]
    y[lo] = dst[0] + (x[lo] - src[0])
    y[hi] = dst[-1] + (x[hi] - src[-1])
    return y


class Template:
    """One straightened template of the contract above, and where it lands on our centreline."""

    def __init__(self, name: str, npz: Path, meta: dict):
        self.name, self.meta = name, meta
        z = np.load(npz)
        self.arc = np.asarray(z["arc"], np.float64)
        self.inplane = np.asarray(z["inplane"], np.float64)
        self.avg = np.asarray(z["avg"], np.float32)
        self.cord = np.asarray(z["cord"], np.float32) if "cord" in z else np.zeros_like(self.avg)
        self.count = np.asarray(z["count"]).astype(np.int32) if "count" in z else np.zeros(self.arc.size, int)
        if self.avg.shape != (self.arc.size, self.inplane.size, self.inplane.size):
            raise SystemExit(f"{name}: avg {self.avg.shape} does not match arc/inplane "
                             f"({self.arc.size}, {self.inplane.size})")
        self.step = float(meta.get("step_mm", STEP))
        self.du = float(self.inplane[1] - self.inplane[0]) if self.inplane.size > 1 else self.step
        row = np.isfinite(self.avg).any(axis=(1, 2))
        if not row.any():
            raise SystemExit(f"{name}: the template is empty (avg is NaN everywhere)")
        i0, i1 = int(np.argmax(row)), int(len(row) - 1 - np.argmax(row[::-1]))
        self.arc_band = (float(self.arc[i0]), float(self.arc[i1]))
        self.src = self.dst = None
        self.mapping: dict = {}

    # -- template arc <-> our arc
    def map_to(self, za: dict[str, float]) -> dict:
        discs = {k: float(v) for k, v in (self.meta.get("discs") or {}).items()}
        shared = sorted((k for k in discs if k in za), key=lambda k: discs[k])
        if not shared:
            raise SystemExit(f"{self.name}: none of its discs {sorted(discs)} is a Z-Anatomy disc; the "
                             "template cannot be level-matched to our vertebral column")
        src = np.array([discs[k] for k in shared], float)
        dst = np.array([za[k] for k in shared], float)
        keep = np.concatenate([[True], (np.diff(src) > 1e-6) & (np.diff(dst) > 1e-6)])
        shared = [k for k, ok in zip(shared, keep) if ok]
        self.src, self.dst = src[keep], dst[keep]
        segs = []
        for a, b, s0, s1, d0, d1 in zip(shared, shared[1:], self.src, self.src[1:], self.dst, self.dst[1:]):
            k = (d1 - d0) / (s1 - s0)
            segs.append({"from": a, "to": b, "template_mm": round(float(s1 - s0), 2),
                         "ours_mm": round(float(d1 - d0), 2), "stretch": round(float(k), 4)})
        flagged = [f"{s['from']}..{s['to']} {s['stretch']:.3f}" for s in segs
                   if not (STRETCH_FLAG[0] <= s["stretch"] <= STRETCH_FLAG[1])]
        self.mapping = {
            "shared_discs": shared, "segments": segs,
            "stretch_range": [round(min((s["stretch"] for s in segs), default=1.0), 4),
                              round(max((s["stretch"] for s in segs), default=1.0), 4)],
            "flagged": flagged,
            "residual_mm": 0.0,
            "note": "template arc -> arc on our centreline is piecewise linear through the discs both the "
                    "template and the Z-Anatomy vertebral column have, so the disc residual is zero by "
                    "construction and what is reported is the stretch of each inter-disc segment; beyond the "
                    "outermost shared disc the slope is exactly 1, so the medulla band is not distorted. "
                    "The Z-Anatomy column is one specimen registered with an anisotropic affine: measured "
                    "along the cord its neck is shorter and its thoracic vertebrae taller than the group "
                    "mean, so a template is compressed by up to a fifth in the lower neck and stretched by "
                    "up to a third in the mid-thoracic region to keep its discs on the model's discs -- "
                    "the price of slices that agree with the vertebra meshes and the -vert cord blocks",
        }
        return self.mapping

    def to_ours(self, a) -> np.ndarray:
        return _pwl(a, self.src, self.dst)

    def to_template(self, s) -> np.ndarray:
        return _pwl(s, self.dst, self.src)

    @property
    def ours_band(self) -> tuple[float, float]:
        lo, hi = self.to_ours(np.array(self.arc_band))
        return float(lo), float(hi)

    # -- reading it on our grid
    def sample(self, arc_ours: np.ndarray, u: np.ndarray, v: np.ndarray):
        """Intensity, cord probability and a 0/1 data weight of this template at grid voxels."""
        from scipy import ndimage
        a = self.to_template(arc_ours)
        c = np.stack([(a - self.arc[0]) / self.step,
                      (u - self.inplane[0]) / self.du, (v - self.inplane[0]) / self.du])
        ok = np.isfinite(self.avg)
        w = ndimage.map_coordinates(ok.astype(np.float32), c, order=1, mode="constant", cval=0.0)
        num = ndimage.map_coordinates(np.nan_to_num(self.avg, nan=0.0), c, order=1, mode="constant", cval=0.0)
        cor = ndimage.map_coordinates(np.nan_to_num(self.cord, nan=0.0) * ok, c, order=1,
                                      mode="constant", cval=0.0)
        d = np.maximum(w, 1e-3)
        return (num / d).astype(np.float32), (cor / d).astype(np.float32), (w > 0.5).astype(np.float32)

    def taper(self, arc_ours: np.ndarray) -> np.ndarray:
        """1, ramping smoothly to 0 across the last BLEND_MM of this template's coverage."""
        hi = self.ours_band[1]
        t = np.clip((hi - arc_ours) / BLEND_MM, 0.0, 1.0)
        return (t * t * (3.0 - 2.0 * t)).astype(np.float32)

    def record(self, reaches_conus: bool, fr: dict | None = None) -> dict:
        cov = dict(self.meta.get("coverage") or {})
        lo, hi = self.ours_band
        z = [world_point(fr, hi)[2], world_point(fr, lo)[2]] if fr is not None else []
        conus = ({"conus_tip_arc_mm": round(float(self.to_ours(float(self.meta["conus_tip_arc"]))[0]), 2),
                  "conus_tip_template_arc_mm": round(float(self.meta["conus_tip_arc"]), 2)}
                 if "conus_tip_arc" in self.meta else {})
        return {**conus, "name": self.name, "source": self.meta.get("source", ""),
                "license": self.meta.get("license", ""),
                "subjects": [str(x) for x in (self.meta.get("subjects") or [])],
                "resolution": cov.get("resolution") or self.meta.get("resolution", ""),
                "sequence": cov.get("sequence") or self.meta.get("sequence", ""),
                "template_arc_mm": [round(x, 2) for x in self.arc_band],
                "arc_mm": [round(lo, 2), round(hi, 2)],
                "z_mm": z,
                "template_step_mm": self.step,
                "vertebral_levels": cov.get("vertebral_levels", []),
                "spinal_levels": sorted((self.meta.get("spinal_levels") or {}),
                                        key=lambda n: pam50.SPINAL_LEVELS.index(n)),
                "reaches_conus": bool(reaches_conus),
                "note": cov.get("note", ""),
                "disc_mapping": self.mapping,
                "qa": self.meta.get("qa", {})}


def load_templates(dirpath: Path = TEMPLATE_DIR) -> list[Template]:
    """Every <name>.npz/<name>.json in `dirpath`, in precedence order."""
    found = {p.stem: p for p in sorted(dirpath.glob("*.npz")) if (dirpath / f"{p.stem}.json").exists()}
    if not found:
        raise SystemExit(f"no straightened cord templates in {dirpath} "
                         "(run atlas-spine-generic, and atlas-fudan-spine if its raw data is present)")
    order = [n for n in PRECEDENCE if n in found] + sorted(n for n in found if n not in PRECEDENCE)
    out = []
    for n in order:
        meta = json.loads((dirpath / f"{n}.json").read_text())
        out.append(Template(n, found[n], meta))
    return out


# ---------------------------------------------------------------- spinal levels
def measured_bands(tpls: list[Template]) -> tuple[dict[str, tuple[float, float]], dict[str, str]]:
    """Every spinal level a template measured, in arc on our centreline; first template in precedence wins."""
    bands: dict[str, tuple[float, float]] = {}
    owner: dict[str, str] = {}
    for t in tpls:
        for name, band in (t.meta.get("spinal_levels") or {}).items():
            if name in bands or name not in pam50.SPINAL_LEVELS:
                continue
            a0, a1 = t.to_ours(np.array([float(band[0]), float(band[1])]))
            bands[name] = (float(a0), float(a1))
            owner[name] = t.name
    return {k: bands[k] for k in sorted(bands, key=pam50.SPINAL_LEVELS.index)}, owner


def estimated_bands(fr: dict, measured: dict[str, tuple[float, float]],
                    limit: float) -> tuple[dict[str, tuple[float, float]], dict]:
    """Levels below the last measured one, by the classical cord-segment-to-vertebra rule.

    Each block of ESTIMATED_BLOCKS ends at a Z-Anatomy landmark projected onto our centreline, and the levels
    of that block that no template measured divide what is left of it equally.  Nothing is invented below
    `limit`, the caudal end of the composite.
    """
    if not measured:
        return {}, {}
    cursor = max(b[1] for b in measured.values())
    out, blocks = {}, []
    for _key, levels, landmark in ESTIMATED_BLOCKS:
        end = zanatomy_landmark_arc(fr, landmark)
        todo = [n for n in levels if n not in measured]
        if end <= cursor + 1e-6 or not todo:
            cursor = max(cursor, end)
            continue
        step = (end - cursor) / len(todo)
        for i, n in enumerate(todo):
            out[n] = (cursor + i * step, cursor + (i + 1) * step)
        blocks.append({"block": _key, "levels": todo, "landmark": landmark,
                       "arc_mm": [round(cursor, 2), round(end, 2)], "level_mm": round(step, 2)})
        cursor = end
    kept = {n: (b[0], min(b[1], limit)) for n, b in out.items() if b[0] < limit}
    meta = {"levels": sorted(kept, key=pam50.SPINAL_LEVELS.index), "rule": ESTIMATED_RULE,
            "blocks": [b for b in blocks if any(n in kept for n in b["levels"])]}
    return {k: kept[k] for k in sorted(kept, key=pam50.SPINAL_LEVELS.index)}, meta


def vertebral_bands(tpls: list[Template], lo: float, hi: float) -> dict[str, tuple[float, float]]:
    """Vertebral levels from the templates' own disc ladders, mapped onto our centreline."""
    out: dict[str, tuple[float, float]] = {}
    for t in tpls:
        d = {k: float(v) for k, v in (t.meta.get("discs") or {}).items()}
        for v in VERTEBRAE:
            a, b = DISC_ABOVE.get(v), DISC_BELOW.get(v)
            if v in out or a not in d or b not in d:
                continue
            a0, a1 = t.to_ours(np.array([d[a], d[b]]))
            if a0 >= lo - 1e-6 and a1 <= hi + 1e-6:
                out[v] = (float(a0), float(a1))
    return {k: out[k] for k in sorted(out, key=lambda n: out[n][0])}


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
        print(f"residual dx {res['dx_mean']:+.2f} +- {res['dx_sd']:.2f} mm, dy {res['dy_mean']:+.2f} +- "
              f"{res['dy_sd']:.2f} mm, RMS {res['dxy_rms']:.2f} mm")
    return res


# ---------------------------------------------------------------- the compose itself
def compose(dirpath: Path = TEMPLATE_DIR, spacing: float = pam50.SPACING, write: bool = True,
            verbose: bool = True) -> dict:
    tpls = load_templates(dirpath)
    fr = canal_frame(verbose)
    za, _za_world = zanatomy_disc_arcs(fr)
    s_anchor, anchor = anchor_on_centreline(fr)
    if verbose:
        print(f"templates ({len(tpls)}, in precedence order): {', '.join(t.name for t in tpls)}")
        print(f"our cord centreline: {len(fr['centreline'])} points, total arc {fr['cord_arc_total']:.1f} mm; "
              f"{anchor['landmark']} at arc {s_anchor:.2f} mm (world {anchor['world_mm']})")

    for t in tpls:
        t.map_to(za)
        if verbose:
            lo, hi = t.ours_band
            m = t.mapping
            print(f"\n  {t.name}: source {t.meta.get('source', '?')} ({t.meta.get('license', '?')}), "
                  f"{len(t.meta.get('subjects') or [])} subjects, template arc "
                  f"{t.arc_band[0]:.1f} .. {t.arc_band[1]:.1f} mm -> our arc {lo:.1f} .. {hi:.1f} mm")
            print(f"    {len(m['shared_discs'])} shared discs {m['shared_discs'][0]}..{m['shared_discs'][-1]}, "
                  f"stretch {m['stretch_range'][0]:.3f} .. {m['stretch_range'][1]:.3f}"
                  + (f"  [flagged: {', '.join(m['flagged'])}]" if m["flagged"] else ""))
            for s in m["segments"]:
                print(f"      {s['from']:>6} -> {s['to']:<6} template {s['template_mm']:6.2f} mm  "
                      f"ours {s['ours_mm']:6.2f} mm  stretch {s['stretch']:.3f}")

    lo = min(t.ours_band[0] for t in tpls)
    hi = max(t.ours_band[1] for t in tpls)
    g = pam50.tube_grid(fr, lo, hi, spacing)
    A, U, V = g["arc_of_voxel"], g["u"], g["v"]
    if verbose:
        print(f"\ngrid {g['dims'][0]}x{g['dims'][1]}x{g['dims'][2]} at {spacing} mm over our arc "
              f"{lo:.1f} .. {hi:.1f} mm, origin {np.round(g['origin'], 2).tolist()}, "
              f"{np.prod(g['dims'])/1e6:.2f} M voxels, {len(g['sel'])/1e3:.0f} k inside the tube")

    acc = np.zeros(A.size, np.float32)
    accc = np.zeros(A.size, np.float32)
    accw = np.zeros(A.size, np.float32)
    remaining = np.ones(A.size, np.float32)
    shares = {}
    for i, t in enumerate(tpls):
        val, cor, w = t.sample(A, U, V)
        if i < len(tpls) - 1:
            w = w * t.taper(A)
        take = remaining * w
        acc += take * val
        accc += take * cor
        accw += take
        remaining *= (1.0 - w)
        shares[t.name] = float(take.sum())
    have = accw > 1e-6
    d = np.maximum(accw, 1e-6)
    comp = np.where(have, acc / d, np.nan).astype(np.float32)
    compcord = np.where(have, accc / d, 0.0).astype(np.float32)
    total = max(sum(shares.values()), 1e-6)
    blend = {"band_mm": BLEND_MM,
             "ramp": "smoothstep over the last BLEND_MM of each template's coverage, the next template "
                     "taking the weight it gives up; NaN in a template is no data and carries no weight",
             "voxel_share": {k: round(v / total, 4) for k, v in shares.items()},
             "voxels_with_data": int(have.sum()), "voxels_in_tube": int(A.size)}
    if verbose:
        print("blend: " + ", ".join(f"{k} {v*100:.1f}%" for k, v in blend["voxel_share"].items())
              + f"; {blend['voxels_with_data']/1e3:.0f} k of {A.size/1e3:.0f} k tube voxels carry data")

    # intensity: window on the composite's own cord voxels, as the single-template reformat did
    cordmask = have & (compcord > 0.5)
    if not cordmask.any():
        raise SystemExit("the composite has no cord voxels; cannot window it")
    c5, c95 = np.percentile(comp[cordmask], [5, 95])
    span = max(float(c95 - c5), 1e-3)
    wlo, whi = float(c5) - 0.25 * span, float(c95) + 0.25 * span
    u8 = np.clip((np.nan_to_num(comp, nan=wlo) - wlo) / (whi - wlo) * 255.0, 0, 255) * g["fade"]
    u8[~have] = 0.0

    # spinal levels: measured where a template measured them, estimated by the vertebral rule below that
    measured, owner = measured_bands(tpls)
    est, est_meta = estimated_bands(fr, measured, hi)
    bands = {**measured, **est}
    bands = {k: bands[k] for k in sorted(bands, key=pam50.SPINAL_LEVELS.index)}
    lab = np.zeros(A.size, np.uint8)
    for name, (a0, a1) in bands.items():
        lab[(A >= a0) & (A < a1)] = pam50.SPINAL_LEVELS.index(name) + 1
    lab[~have] = 0
    painted = sorted({int(x) for x in np.unique(lab) if x})
    if verbose:
        print(f"\nspinal levels: {len(measured)} measured ({', '.join(measured) or '-'}), "
              f"{len(est)} estimated by the vertebral rule ({', '.join(est) or '-'}); "
              f"{len(painted)} painted in the volume")

    dims, sel = g["dims"], g["sel"]
    zmin = float(g["origin"][2]); zmax = zmin + (dims[2] - 1) * spacing
    conus_arc = zanatomy_landmark_arc(fr, ESTIMATED_BLOCKS[-1][2])
    reaches = {t.name: t.ours_band[1] >= conus_arc - 5.0 or "conus_tip_arc" in t.meta for t in tpls}
    sources = []
    for t in tpls:
        sid = t.meta.get("source")
        if sid and sid not in sources:
            sources.append(sid)
    if not sources:
        sources = [SPINE_SOURCE]

    out = {
        "space": "MNI152NLin2009cAsym", "edition": "public",
        "shape": [int(x) for x in dims], "spacing": [spacing] * 3,
        "origin_ras": [round(float(x), 4) for x in g["origin"]],
        "affine_ras": [[round(float(x), 6) for x in row] for row in g["affine"][:3].tolist()] + [[0, 0, 0, 1]],
        "source": sources[0], "sources": sources,
        "license": tpls[0].meta.get("license", "CC-BY-4.0"),
        "reformat": {
            "method": "curved reformat of " + (f"{len(tpls)} openly licensed straightened cord templates"
                                               if len(tpls) > 1 else "an openly licensed straightened cord "
                                                                     "template")
                      + f" ({', '.join(t.name for t in tpls)}), composed by atlas-cord-public onto the "
                      f"centreline of {fr['mesh_source']} (per-z slab centroids, {pam50.SMOOTH} mm boxcar); "
                      "each template's arc length is mapped onto ours piecewise-linearly through the "
                      "intervertebral discs it shares with the Z-Anatomy vertebral column -- the same "
                      "specimen the cord surface comes from -- with slope 1 beyond the outermost shared "
                      "disc, and the templates are blended in precedence order across the last "
                      f"{BLEND_MM:.0f} mm of each one's coverage",
            "anchor": anchor, "anchor_arc_mm": round(s_anchor, 3),
            "arc_mm": [round(lo, 2), round(hi, 2)],
            "cord_arc_total_mm": round(fr["cord_arc_total"], 2),
            "canal": ({"source": fr["canal_source"], "z_mm": fr["canal_z_mm"],
                       "arc_total_mm": round(fr["canal_arc_total"], 2),
                       "note": "below the end of the cord surface the centreline follows the midline of the "
                               "Z-Anatomy cauda equina surface through the lumbosacral canal, so the sac of "
                               "the template lands in the model's sacral canal"} if "canal_source" in fr
                      else None),
            "radius_full_mm": pam50.R_FULL, "radius_fade_mm": pam50.R_FADE,
            "subjects": [s for t in tpls for s in (t.meta.get("subjects") or [])],
            "template_step_mm": tpls[0].step,
            "templates": [t.record(reaches[t.name], fr) for t in tpls],
            "blend": blend,
        },
        "coverage": {"z_mm": [round(zmin, 2), round(zmax, 2)],
                     "vertebral_levels": [], "spinal_levels": [], "note": ""},
        "contrasts": {},
    }

    vert = vertebral_bands(tpls, lo, hi)
    out["coverage"]["vertebral_levels"] = [next(iter(vert)), list(vert)[-1]] if vert else []
    out["coverage"]["spinal_levels"] = [pam50.SPINAL_LEVELS[i - 1] for i in painted]
    out["coverage"]["note"] = (
        f"composed from {', '.join(t.name for t in tpls)}; "
        + ("the cord is covered to the conus" if any(reaches.values())
           else "the templates cover the cervical and upper thoracic cord only")
        + ". Levels " + (", ".join(measured) if measured else "-") + " are measured on the nerve rootlets; "
        + (("levels " + ", ".join(est) + " below them are estimated from the classical "
            "cord-segment-to-vertebra rule and the Z-Anatomy vertebral column, not from the image")
           if est else "no level below them is claimed"))

    rec = pam50.write_volume("cord_t2_public", dims, u8.astype(np.uint8), sel) if write else {}
    rec.update({"window": 255, "level": 127, "source_window": [round(wlo, 3), round(whi, 3)],
                "space": "cord", "edition": "public", "spacing": [spacing] * 3,
                "origin_ras": out["origin_ras"], "affine_ras": out["affine_ras"]})
    out["contrasts"]["cord_t2"] = rec
    if verbose:
        print(f"\n  {'cord_t2':16s} window {wlo:.2f}..{whi:.2f}  {rec.get('bytes_gz', 0)/1024:8.1f} KB gz "
              f"({rec.get('bytes_raw', 0)/1e6:.1f} MB raw)")

    rec = pam50.write_volume("labels_spine_public", dims, lab, sel) if write else {}
    rec.update({"space": "cord", "edition": "public", "spacing": [spacing] * 3,
                "origin_ras": out["origin_ras"], "affine_ras": out["affine_ras"],
                "lut": "volumes/labels_spine_public.json"})
    out["contrasts"]["labels_spine"] = rec
    if verbose:
        print(f"  {'labels_spine':16s} {len(painted)} levels     {rec.get('bytes_gz', 0)/1024:8.1f} KB gz")

    dense = np.zeros(int(np.prod(dims)), np.float32)
    dense[sel] = u8
    out["reformat"]["mni_residual"] = medulla_residual(dense.reshape(dims), g["origin"], spacing, verbose=verbose)

    # ---- the level tables
    spinal = world_levels(fr, 0.0, bands)
    for r in spinal:
        if r["name"] in est:
            r["estimated"] = True
    vert_tab = world_levels(fr, 0.0, vert)
    level_meta = level_method(tpls, owner, est_meta)
    if verbose:
        print(f"\n{'level':>6} {'arc mm':>16} {'our world z':>17}  centre (x, y) mm")
        for r in spinal:
            print(f"{r['name']:>6} {r['arc_mm'][0]:7.1f}..{r['arc_mm'][1]:7.1f} "
                  f"{r['z_mm'][1]:8.1f}..{r['z_mm'][0]:7.1f}  ({r['top'][0]:5.1f}, {r['top'][1]:7.1f})"
                  + ("  estimated" if r.get("estimated") else ""))
    if not write:
        return out

    (VOLUMES / "cord_public.json").write_text(json.dumps(out, indent=1))
    sl = pam50.spine_lut(spinal, mesh_suffix=MESH_SUFFIX, source=out["source"], volume="labels_spine_public",
                         note="Spinal levels of the public edition's composed cord MRI (atlas-cord-public). "
                              "Levels the nerve rootlets of a template measured are carried onto our cord "
                              "centreline by the curved reformat; levels marked `estimated` are placed by the "
                              "classical cord-segment-to-vertebra rule on the Z-Anatomy vertebral column "
                              "instead, and the app names them \"<level> (vertebral rule)\". ids are the same "
                              "1 = C1 ... 30 = S5 ids the private volume uses, as they appear in "
                              "volumes/labels_spine_public.u8.bin. meshId is the cord segment block that "
                              "contains the level, so selecting a level and selecting its 3D block are the "
                              "same selection.")
    for e in sl["lut"].values():
        if e["name"] in est:
            e["estimated"] = True
    sl["coverage"] = out["coverage"]
    sl["levelMethod"] = level_meta
    (VOLUMES / "labels_spine_public.json").write_text(json.dumps(sl, indent=1))

    cl_s, cl_p = pam50.centreline_table({"centreline": fr["centreline"], "arc": fr["arc"]})
    levels_json = {
        "space": "MNI152NLin2009cAsym", "edition": "public", "source": out["source"], "sources": sources,
        "note": "spinal levels of the composed public cord MRI (atlas-cord-public): measured on the nerve "
                "rootlets where a template measured them, estimated from the classical "
                "cord-segment-to-vertebra rule on the Z-Anatomy vertebral column below that; vertebral "
                "levels are the templates' own disc ladders mapped onto our centreline. top/bottom are "
                "world mm on the centreline",
        "anchor": anchor, "centrelineSource": fr["mesh_source"],
        "centreline": {"stepMm": pam50.CENTRELINE_STEP,
                       "arc": [round(float(x), 3) for x in cl_s],
                       "points": [[round(float(c), 3) for c in q] for q in cl_p]},
        "levelMethod": level_meta,
        "conusTip": {"arc_mm": round(conus_arc, 2), "world_mm": world_point(fr, conus_arc),
                     "landmark": ESTIMATED_BLOCKS[-1][2],
                     "method": "the middle of the Z-Anatomy L1-L2 intervertebral disc, the classical adult "
                               "level of the tip of the conus medullaris (the same landmark derived.py cuts "
                               "the public sacral cord block and the filum at)"},
        "spinalLevels": spinal, "vertebralLevels": vert_tab,
    }
    for t in tpls:
        if "conus_tip_arc" in t.meta:
            a = float(t.to_ours(float(t.meta["conus_tip_arc"]))[0])   # == its record's conus_tip_arc_mm
            levels_json["conusTipMeasured"] = {
                "arc_mm": round(a, 2), "world_mm": world_point(fr, a), "template": t.name,
                "source": t.meta.get("source", ""),
                "template_arc_mm": round(float(t.meta["conus_tip_arc"]), 2),
                "note": "measured on the template image and carried onto our centreline; recorded for "
                        "information -- the level tables and the cord blocks use the rule-based conusTip"}
            break
    (VOLUMES / "cord_levels_public.json").write_text(json.dumps(levels_json, indent=1))
    if verbose:
        print(f"\nwrote {VOLUMES / 'cord_public.json'}, {VOLUMES / 'labels_spine_public.json'} and "
              f"{VOLUMES / 'cord_levels_public.json'}")
        print(f"total shipped: {sum(x.get('bytes_gz', 0) for x in out['contrasts'].values())/1e6:.2f} MB gz")
    return out


def level_method(tpls: list[Template], owner: dict[str, str], est_meta: dict) -> dict:
    """The provenance block both labels_spine_public.json and cord_levels_public.json carry."""
    meta: dict = {"measured": [], "extrapolated": [], "estimated": est_meta.get("levels", []),
                  "estimated_rule": est_meta.get("rule", ESTIMATED_RULE),
                  "estimated_blocks": est_meta.get("blocks", []),
                  "measuredBy": owner, "templates": {}}
    for t in tpls:
        lm = t.meta.get("level_method")
        if lm is None:
            continue
        meta["templates"][t.name] = lm
        for k in ("measured", "extrapolated"):
            for n in lm.get(k, []) if isinstance(lm, dict) else []:
                if owner.get(n) == t.name and n not in meta[k]:
                    meta[k].append(n)
    for k in ("measured", "extrapolated"):
        meta[k] = sorted(meta[k], key=pam50.SPINAL_LEVELS.index)
    return meta


# ---------------------------------------------------------------- self-test
def selftest(spacing: float = pam50.SPACING) -> dict:
    """Compose with a fabricated second template, so the multi-template path is never dead code.

    The synthetic template is the spine-generic one shifted three vertebrae caudally: the same voxels, the
    same normalisation, but discs relabelled C5-C6 .. T5-T6 and a conus tip, so it level-matches to a lower
    stretch of the Z-Anatomy column, overlaps the real template and hands over inside the blend band.
    """
    import shutil
    import tempfile
    src = TEMPLATE_DIR / "spine_generic_t2"
    if not src.with_suffix(".npz").exists():
        raise SystemExit("--selftest needs work/cord_public/spine_generic_t2.npz (run atlas-spine-generic)")
    tmp = Path(tempfile.mkdtemp(prefix="cord-public-selftest-"))
    try:
        shutil.copy(src.with_suffix(".npz"), tmp / "spine_generic_t2.npz")
        shutil.copy(src.with_suffix(".json"), tmp / "spine_generic_t2.json")
        meta = json.loads(src.with_suffix(".json").read_text())
        z = np.load(src.with_suffix(".npz"))
        shift = 90.0
        np.savez_compressed(tmp / "zz_synthetic_t2.npz", arc=np.asarray(z["arc"]) + shift,
                            inplane=z["inplane"], avg=z["avg"], cord=z["cord"], count=z["count"])
        down = {"C2-C3": "C5-C6", "C3-C4": "C6-C7", "C4-C5": "C7-T1", "C5-C6": "T1-T2", "C6-C7": "T2-T3",
                "C7-T1": "T3-T4", "T1-T2": "T4-T5", "T2-T3": "T5-T6"}
        discs = {down[k]: v + shift for k, v in meta["discs"].items() if k in down}
        (tmp / "zz_synthetic_t2.json").write_text(json.dumps({
            "source": meta["source"], "license": meta["license"], "step_mm": meta["step_mm"],
            "discs": discs, "subjects": ["synthetic"],
            "conus_tip_arc": max(discs.values()) + 5.0,
            "coverage": {"arc_mm": meta["coverage"]["arc_mm"], "vertebral_levels": ["C5", "T5"],
                         "resolution": "synthetic", "note": "fabricated by atlas-cord-public --selftest"},
        }, indent=1))
        out = compose(tmp, spacing, write=False, verbose=True)
        names = [t["name"] for t in out["reformat"]["templates"]]
        share = out["reformat"]["blend"]["voxel_share"]
        assert names == ["spine_generic_t2", "zz_synthetic_t2"], names
        assert share.get("zz_synthetic_t2", 0) > 0.05, f"the second template contributed nothing: {share}"
        assert share.get("spine_generic_t2", 0) > 0.05, f"the first template contributed nothing: {share}"
        one = compose(TEMPLATE_DIR, spacing, write=False, verbose=False)
        assert out["reformat"]["arc_mm"][1] > one["reformat"]["arc_mm"][1] + 10, "the union did not grow"
        assert out["shape"] != one["shape"], "the grid did not grow with the second template"
        syn = out["reformat"]["templates"][1]
        assert syn["reaches_conus"], "a template with a conus tip was not flagged as reaching the conus"
        assert syn["conus_tip_arc_mm"] > syn["arc_mm"][0], f"conus tip not mapped: {syn}"
        assert not out["reformat"]["templates"][0]["reaches_conus"], "spine-generic must not claim the conus"
        assert syn["disc_mapping"]["flagged"], "a 1.5x stretch should have been flagged"
        assert out["sources"] == one["sources"], "the synthetic template shares spine-generic's source id"
        assert "T7" in out["coverage"]["spinal_levels"], "the estimated levels did not follow the coverage"
        print(f"\n--selftest ok: {names}, share {share}, arc "
              f"{out['reformat']['arc_mm']} vs {one['reformat']['arc_mm']} with one template, "
              f"grid {out['shape']} vs {one['shape']}")
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="atlas-cord-public", description=__doc__.split("\n")[0])
    ap.add_argument("--spacing", type=float, default=pam50.SPACING)
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--selftest", action="store_true",
                    help="compose with a fabricated second template and check the blend; writes nothing")
    a = ap.parse_args(argv)
    if a.selftest:
        selftest(a.spacing)
        return
    compose(TEMPLATE_DIR, a.spacing, write=not a.no_write, verbose=not a.quiet)


if __name__ == "__main__":
    main()
