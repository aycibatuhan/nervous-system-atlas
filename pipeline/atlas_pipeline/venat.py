"""Step 06c: the deep cerebral veins and the straight sinus from the VENAT venous atlas.

Source
------
Huck J, Wanner Y, Fan AP, Jaeger AT, Grahl S, Schneider U, Villringer A, Steele CJ, Tardif CL,
Bazin PL, Gauthier CJ. "High resolution atlas of the venous brain vasculature from 7 T quantitative
susceptibility maps." Brain Struct Funct 2019;224(7):2467-2485. doi:10.1007/s00429-019-01919-4.
Data: figshare doi:10.6084/m9.figshare.7205960.v4, licence CC BY 4.0.
Files (see config/sources.yaml, group "vessels"): raw/venat/VENAT_PartialVolume.nii.gz (float32 venous
partial-volume fraction, 0..0.84) and raw/venat/VENAT_diameter.nii.gz, both 364x436x364 at 0.5 mm on the
FSL MNI152 (NLin6) box - the same grid as raw/mouches_arteries - so the meshes carry alignment
"nlin6-identity" like the MRA arterial iso-surface.

What this step builds
---------------------
1. `veins-venat-atlas` - one iso-surface of the whole thresholded venous partial-volume map inside the
   dilated brain mask (the venous counterpart of `arteries-mra-atlas`).
2. Named deep veins cut out of the *same* voxel mask with region masks written in MNI millimetres and
   anchored to the aseg segmentation of the template (third ventricle, splenium of the corpus callosum,
   midbrain, thalamus, caudate), then reduced to their largest connected component:
     vein-internal-cerebral-l / -r  roof of the third ventricle, foramen of Monro -> velum interpositum
     vein-great-cerebral            vein of Galen, midline under the splenium
     vein-basal-l / -r              basal vein of Rosenthal, around the cerebral peduncle
     sinus-straight-venat           vein of Galen -> torcular (the id `sinus-straight` is already taken
                                    by the Z-Anatomy mesh, so the VENAT surface gets its own id and
                                    keeps `sinus-straight` as its content structure id)

The thalamostriate vein is *not* built: along the caudothalamic groove the atlas never rises above a
partial volume of about 0.4 and the ridge is not separable from the shoulder of the internal cerebral
vein, so any cut there would be invented rather than measured (see `--inventory`).

QA
--
`--qa` writes slice overlays of every region on the template T1 into work/venat/ and a summary
work/venat/venat_qa.json with the anchor checks (each vein's centroid against the aseg anchors).
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
from scipy import ndimage

from . import catalog
from .atlas_meshes import record
from .catalog import BUDGET, LOD_MIN_FACES, MeshSpec
from .meshing import export_with_lod, mesh_from_mask
from .paths import MESHES, RAW, WORK
from .spaces import load_ras

SOURCE_ID = "venat"
PARTIAL_VOLUME = RAW / "venat" / "VENAT_PartialVolume.nii.gz"
BRAIN_MASK = RAW / "mni_t1w" / "tpl-MNI152NLin2009cAsym_res-01_desc-brain_mask.nii.gz"
T1 = RAW / "mni_t1w" / "tpl-MNI152NLin2009cAsym_res-01_T1w.nii.gz"
ASEG = RAW / "mni_aseg" / "tpl-MNI152NLin2009cAsym_res-01_seg-aseg_dseg.nii.gz"
WORKDIR = WORK / "venat"

# Chosen by inspection of the partial-volume histogram and of the deep venous ridge (see --inventory):
# 0.22 keeps the whole dural sinus / deep venous tree connected (26 mL of venous volume, close to the
# published cerebral venous blood volume) while dropping the diffuse medullary-vein haze that 0.15 adds.
THRESHOLD = 0.22
MIN_COMPONENT_MM3 = 150.0     # whole-atlas iso-surface
BRAIN_DILATE_MM = 8.0
VOXEL_MM3 = 0.125

ASEG_THIRD_VENTRICLE = 14
ASEG_SPLENIUM = 251
ASEG_BRAINSTEM = 16
ASEG_THALAMUS = (10, 49)
ASEG_CAUDATE = (11, 50)


# ---------------------------------------------------------------- context


@dataclass
class Ctx:
    """The thresholded venous mask plus everything a region mask needs, in MNI millimetres."""
    shape: tuple
    affine: np.ndarray
    mask: np.ndarray           # bool, the thresholded + component-filtered venous voxels
    ijk: np.ndarray            # (N, 3) voxel indices of mask
    P: np.ndarray              # (N, 3) world mm of mask
    anchors: dict              # aseg-derived boxes and fields
    prob: np.ndarray

    def scatter(self, sel: np.ndarray) -> np.ndarray:
        out = np.zeros(self.shape, bool)
        if sel.any():
            k = self.ijk[sel]
            out[k[:, 0], k[:, 1], k[:, 2]] = True
        return out


def world_grid(shape, affine):
    xs = affine[0, 3] + affine[0, 0] * np.arange(shape[0])
    ys = affine[1, 3] + affine[1, 1] * np.arange(shape[1])
    zs = affine[2, 3] + affine[2, 2] * np.arange(shape[2])
    return xs, ys, zs


def brain_mask_on(shape, affine, dilate_mm: float = BRAIN_DILATE_MM) -> np.ndarray:
    from nibabel.processing import resample_from_to
    bm = resample_from_to(load_ras(BRAIN_MASK), (shape, affine), order=0)
    it = int(round(dilate_mm / abs(affine[0, 0])))
    return ndimage.binary_dilation(np.asanyarray(bm.dataobj) > 0, iterations=it)


def venous_mask(prob, bmask, threshold: float, min_mm3: float) -> np.ndarray:
    m = (prob >= threshold) & bmask
    lab, _ = ndimage.label(m, np.ones((3, 3, 3)))
    sizes = np.bincount(lab.ravel())
    sizes[0] = 0
    keep = np.where(sizes * VOXEL_MM3 >= min_mm3)[0]
    return np.isin(lab, keep)


def _box(pts_world):
    return {"min": pts_world.min(0), "max": pts_world.max(0), "centroid": pts_world.mean(0)}


def anchors() -> dict:
    """Boxes and distance fields derived from the aseg segmentation of the template (1 mm, 2009c)."""
    img = load_ras(ASEG)
    d = np.rint(np.asanyarray(img.dataobj)).astype(np.int32)
    aff = img.affine

    def world(mask):
        idx = np.argwhere(mask)
        return idx * np.array([aff[0, 0], aff[1, 1], aff[2, 2]]) + np.array([aff[0, 3], aff[1, 3], aff[2, 3]])

    third = world(d == ASEG_THIRD_VENTRICLE)
    splen = world(d == ASEG_SPLENIUM)
    # midbrain = the top of the FreeSurfer brainstem label (the pons starts below about z = -24 mm)
    zs = aff[2, 3] + aff[2, 2] * np.arange(d.shape[2])
    zsel = ((zs >= -24) & (zs <= 4))[None, None, :]
    midbrain = (d == ASEG_BRAINSTEM) & zsel
    dist_out = ndimage.distance_transform_edt(~midbrain, sampling=[abs(aff[i, i]) for i in range(3)])
    # third ventricle roof: highest z of the label at each y (used to keep the ICV above the ventricle)
    roof_y = np.arange(third[:, 1].min(), third[:, 1].max() + 1)
    roof_z = np.array([third[np.abs(third[:, 1] - y) <= 1.0, 2].max() if (np.abs(third[:, 1] - y) <= 1.0).any() else np.nan for y in roof_y])
    ok = ~np.isnan(roof_z)
    return {
        "affine": aff, "shape": d.shape,
        "third_ventricle": _box(third), "splenium": _box(splen),
        "brainstem": _box(world(d == ASEG_BRAINSTEM)), "midbrain": _box(world(midbrain)),
        "thalamus": _box(world(np.isin(d, ASEG_THALAMUS))), "caudate": _box(world(np.isin(d, ASEG_CAUDATE))),
        "dist_midbrain": dist_out, "roof_y": roof_y[ok], "roof_z": roof_z[ok],
    }


def sample_field(field, aff, P) -> np.ndarray:
    """Nearest-voxel lookup of a 1 mm template field at world points P (mm)."""
    ijk = np.rint((P - np.array([aff[0, 3], aff[1, 3], aff[2, 3]])) / np.array([aff[0, 0], aff[1, 1], aff[2, 2]])).astype(int)
    for k in range(3):
        ijk[:, k] = np.clip(ijk[:, k], 0, field.shape[k] - 1)
    return field[ijk[:, 0], ijk[:, 1], ijk[:, 2]]


def dist_to_polyline(P, poly) -> np.ndarray:
    """Distance in mm from every point of P to a polyline given as a list of (x, y, z) in MNI mm."""
    poly = np.asarray(poly, float)
    best = np.full(len(P), np.inf)
    for a, b in zip(poly[:-1], poly[1:]):
        ab = b - a
        t = np.clip(((P - a) @ ab) / max(float(ab @ ab), 1e-9), 0.0, 1.0)
        best = np.minimum(best, np.linalg.norm(P - (a + t[:, None] * ab), axis=1))
    return best


# ---------------------------------------------------------------- region masks
# Every limit below is a millimetre in the world frame; the ones marked "anchor" are recomputed from the
# aseg boxes at run time so they follow the template rather than a remembered number.

Z_ICV = (4.0, 20.0)          # velum interpositum: above the third-ventricle roof, below the body of the CC
X_ICV = 9.0
Z_GALEN = (-2.0, 15.0)
X_GALEN = 7.0
# the straight sinus centreline read off the partial-volume ridge (see --inventory), Galen -> torcular
STRAIGHT_POLY = [(0.0, -48.0, 6.5), (0.0, -56.0, 8.0), (0.0, -64.0, 4.0), (0.0, -71.0, -1.0),
                 (0.0, -77.0, -7.0), (0.0, -83.0, -14.0), (0.0, -87.0, -17.0)]
STRAIGHT_RADIUS = 6.5
BASAL_SHELL_MM = 14.0        # crural + ambient cistern: within this of the midbrain surface
Z_BASAL = (-24.0, 8.0)
X_BASAL_MIN = 4.0


@dataclass
class Region:
    spec: MeshSpec
    build: Callable[[Ctx], np.ndarray]      # -> bool over ctx.P
    note: str = ""
    min_mm3: float = 60.0
    keep: str = "largest"                    # "largest" | "all"
    checks: list = field(default_factory=list)   # (label, callable(centroid, anchors) -> bool)


def _split_y(anchors) -> float:
    """Where the internal cerebral veins end and the vein of Galen begins: the posterior edge of the
    splenium of the corpus callosum, which the great vein curls around."""
    return float(anchors["splenium"]["min"][1] + 4.0)      # about -39 mm


def regions(anchors) -> list[Region]:
    y_split = _split_y(anchors)
    y_monro = float(anchors["third_ventricle"]["max"][1] + 2.0)     # about +5 mm, the front of the third ventricle
    roof_y, roof_z = anchors["roof_y"], anchors["roof_z"]
    aff1 = anchors["affine"]
    dist = anchors["dist_midbrain"]

    def icv(side):
        def f(ctx):
            x, y, z = ctx.P[:, 0], ctx.P[:, 1], ctx.P[:, 2]
            roof = np.interp(y, roof_y, roof_z, left=roof_z[0], right=roof_z[-1])
            keep = (np.abs(x) <= X_ICV) & (y >= y_split) & (y <= y_monro) & (z >= Z_ICV[0]) & (z <= Z_ICV[1]) & (z >= roof - 1.0)
            return keep & ((x < 0) if side == "left" else (x > 0))
        return f

    def galen(ctx):
        x, y, z = ctx.P[:, 0], ctx.P[:, 1], ctx.P[:, 2]
        return (np.abs(x) <= X_GALEN) & (y >= -50.0) & (y <= y_split) & (z >= Z_GALEN[0]) & (z <= Z_GALEN[1])

    def straight(ctx):
        y = ctx.P[:, 1]
        return (y <= -50.0) & (dist_to_polyline(ctx.P, STRAIGHT_POLY) <= STRAIGHT_RADIUS)

    def basal(side):
        def f(ctx):
            x, y, z = ctx.P[:, 0], ctx.P[:, 1], ctx.P[:, 2]
            dm = sample_field(dist, aff1, ctx.P)
            keep = (dm <= BASAL_SHELL_MM) & (dm > 0.5) & (np.abs(x) >= X_BASAL_MIN) \
                & (z >= Z_BASAL[0]) & (z <= Z_BASAL[1]) & (y >= -42.0) & (y <= 10.0)
            return keep & ((x < 0) if side == "left" else (x > 0))
        return f

    spec = catalog.venat_entries()      # ids, names, systems and colours live in catalog.py
    out: list[Region] = []
    for side, sfx in (("left", "-l"), ("right", "-r")):
        out.append(Region(
            spec["vein-internal-cerebral" + sfx], icv(side),
            note="roof of the third ventricle, foramen of Monro to the velum interpositum",
            checks=[("above the third-ventricle roof", lambda c, a: c[2] > a["third_ventricle"]["max"][2]),
                    ("below the top of the splenium", lambda c, a: c[2] < a["splenium"]["max"][2]),
                    ("within 12 mm of the midline", lambda c, a: abs(c[0]) < 12.0)]))
    out.append(Region(
        spec["vein-great-cerebral"], galen,
        note="midline under the splenium, ending where the straight sinus begins",
        checks=[("behind the splenium centroid", lambda c, a: c[1] < a["splenium"]["centroid"][1]),
                ("below the top of the splenium", lambda c, a: c[2] < a["splenium"]["max"][2]),
                ("on the midline", lambda c, a: abs(c[0]) < 4.0)]))
    for side, sfx in (("left", "-l"), ("right", "-r")):
        out.append(Region(
            spec["vein-basal" + sfx], basal(side),
            note="crural and ambient cisterns around the cerebral peduncle", min_mm3=100.0,
            checks=[("lateral to the midline", lambda c, a: abs(c[0]) > 8.0),
                    ("beside or behind the midbrain", lambda c, a: c[1] < a["midbrain"]["max"][1] + 8.0),
                    ("below the thalamus", lambda c, a: c[2] < a["thalamus"]["centroid"][2])]))
    out.append(Region(
        spec["sinus-straight-venat"], straight,
        note="vein of Galen to the torcular, in the attached edge of the tentorium", min_mm3=200.0,
        checks=[("behind the vein of Galen", lambda c, a: c[1] < -50.0),
                ("on the midline", lambda c, a: abs(c[0]) < 4.0)]))
    return out


WHOLE = catalog.VEINS_VENAT


# ---------------------------------------------------------------- build


def load_context(threshold: float, min_mm3: float) -> Ctx:
    img = load_ras(PARTIAL_VOLUME)
    prob = np.asanyarray(img.dataobj)
    bmask = brain_mask_on(prob.shape, img.affine)
    mask = venous_mask(prob, bmask, threshold, min_mm3)
    ijk = np.argwhere(mask)
    aff = img.affine
    P = ijk * np.array([aff[0, 0], aff[1, 1], aff[2, 2]]) + np.array([aff[0, 3], aff[1, 3], aff[2, 3]])
    return Ctx(prob.shape, aff, mask, ijk, P, anchors(), prob)


def largest_components(m: np.ndarray, min_mm3: float, keep: str) -> tuple[np.ndarray, list[float]]:
    lab, _ = ndimage.label(m, np.ones((3, 3, 3)))
    sizes = np.bincount(lab.ravel())
    sizes[0] = 0
    if not sizes.any():
        return m, []
    if keep == "largest":
        sel = [int(sizes.argmax())]
    else:
        sel = [int(i) for i in np.where(sizes * VOXEL_MM3 >= min_mm3)[0]]
    return np.isin(lab, sel), sorted((float(sizes[i] * VOXEL_MM3) for i in sel), reverse=True)


def build_whole(ctx: Ctx, threshold: float) -> dict:
    print(f"  venous voxels >= {threshold}: {int(ctx.mask.sum())} ({ctx.mask.sum() * VOXEL_MM3 / 1000:.1f} mL)")
    mesh = mesh_from_mask(ctx.mask, ctx.affine, BUDGET[WHOLE.budget], sigma=0.7, min_component_frac=0.01, taubin_iterations=10)
    path = MESHES / WHOLE.system / f"{WHOLE.id}.glb"
    nbytes, lod = export_with_lod(mesh, path, WHOLE.id, 8000, LOD_MIN_FACES)
    print(f"  {WHOLE.id:32s} {len(mesh.faces):6d} tris {nbytes / 1024:7.1f} KB")
    return record(WHOLE, SOURCE_ID, None, "nlin6-identity", mesh, path, nbytes, int(ctx.mask.sum()),
                  {"threshold": threshold, "lod": lod})


def build_named(ctx: Ctx, only: set[str] | None, qa: bool) -> tuple[list[dict], list[dict]]:
    out, report = [], []
    for r in regions(ctx.anchors):
        if only and r.spec.id not in only and r.spec.structure_id not in only:
            continue
        sel = r.build(ctx)
        raw_mm3 = float(sel.sum() * VOXEL_MM3)
        m = ctx.scatter(sel)
        m, comps = largest_components(m, r.min_mm3, r.keep)
        mm3 = float(m.sum() * VOXEL_MM3)
        entry = {"id": r.spec.id, "note": r.note, "regionVolumeMm3": round(raw_mm3, 1),
                 "keptVolumeMm3": round(mm3, 1), "components": [round(c, 1) for c in comps]}
        if mm3 < r.min_mm3:
            entry["status"] = "skipped: below the minimum volume"
            print(f"  [skip] {r.spec.id}: {mm3:.0f} mm3 < {r.min_mm3:.0f} mm3")
            report.append(entry)
            continue
        mesh = mesh_from_mask(m, ctx.affine, BUDGET[r.spec.budget], sigma=0.8, min_component_frac=0.15, taubin_iterations=14)
        if mesh is None:
            entry["status"] = "skipped: empty mesh"
            report.append(entry)
            continue
        c = np.asarray(mesh.vertices).mean(0)
        checks = {label: bool(fn(c, ctx.anchors)) for label, fn in r.checks}
        entry["centroid"] = [round(float(v), 1) for v in c]
        entry["anchorChecks"] = checks
        entry["status"] = "ok" if all(checks.values()) else "ANCHOR CHECK FAILED"
        path = MESHES / r.spec.system / f"{r.spec.id}.glb"
        nbytes, lod = export_with_lod(mesh, path, r.spec.id, 3000, LOD_MIN_FACES)
        entry["triangles"] = int(len(mesh.faces))
        entry["bytes"] = int(nbytes)
        out.append(record(r.spec, SOURCE_ID, None, "nlin6-identity", mesh, path, nbytes, int(m.sum()),
                          {"threshold": THRESHOLD, "region": r.note, "lod": lod}))
        flag = "" if all(checks.values()) else "  <-- ANCHOR CHECK FAILED"
        print(f"  {r.spec.id:32s} {len(mesh.faces):6d} tris {nbytes / 1024:7.1f} KB  {mm3:6.0f} mm3{flag}")
        for label, okv in checks.items():
            if not okv:
                print(f"      failed: {label}")
        report.append(entry)
        if qa:
            qa_overlay(ctx, m, r.spec.id, c)
    return out, report


# ---------------------------------------------------------------- QA


def qa_overlay(ctx: Ctx, m: np.ndarray, name: str, centroid) -> None:
    """Three T1 slices through the mesh centroid with the whole venous mask in grey and the cut in colour."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from nibabel.processing import resample_from_to
        import nibabel as nib
    except Exception as e:  # noqa: BLE001
        print("  QA overlay unavailable:", e)
        return
    t1img = load_ras(T1)
    t1 = np.asanyarray(t1img.dataobj)
    aff = t1img.affine
    to_t1 = lambda a: np.asanyarray(resample_from_to(nib.Nifti1Image(a.astype(np.uint8), ctx.affine), (t1.shape, aff), order=0).dataobj) > 0
    allv = to_t1(ctx.mask)
    cut = to_t1(m)
    WORKDIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.4))
    for ax, axis in zip(axes, (0, 1, 2)):
        pos = float(centroid[axis])
        i = int(round((pos - aff[axis, 3]) / aff[axis, axis]))
        i = int(np.clip(i, 0, t1.shape[axis] - 1))
        sl = [slice(None)] * 3
        sl[axis] = i
        other = [k for k in range(3) if k != axis]
        base = t1[tuple(sl)].T
        ax.imshow(base, cmap="gray", origin="lower")
        av = allv[tuple(sl)].T.astype(float)
        cv = cut[tuple(sl)].T.astype(float)
        ax.imshow(np.dstack([av, av, av, av * 0.45]), origin="lower")
        ax.imshow(np.dstack([cv, cv * 0.25, cv * 0.05, cv * 0.95]), origin="lower")
        ax.set_title(f"{'xyz'[axis]} = {pos:.0f} mm", fontsize=9)
        ax.set_xlabel("xyz"[other[0]] + " (vox)", fontsize=7)
        ax.axis("off")
    fig.suptitle(f"{name}  (orange = cut, grey = whole venous mask, T1 MNI152NLin2009cAsym)", fontsize=10)
    p = WORKDIR / f"{name}.png"
    fig.savefig(p, dpi=110, bbox_inches="tight")
    plt.close(fig)
    print("      QA:", p)


def inventory(ctx: Ctx) -> None:
    """Print the evidence the thresholds and cuts were chosen from."""
    prob, aff = ctx.prob, ctx.affine
    bmask = brain_mask_on(prob.shape, aff)
    print("threshold sweep (inside the dilated brain mask):")
    for t in (0.10, 0.15, 0.20, 0.22, 0.25, 0.30, 0.40):
        m = (prob >= t) & bmask
        lab, n = ndimage.label(m, np.ones((3, 3, 3)))
        sizes = np.bincount(lab.ravel())[1:]
        print(f"  t={t:.2f} {m.sum() * VOXEL_MM3 / 1000:6.1f} mL  {n:5d} components, "
              f"{int((sizes * VOXEL_MM3 >= MIN_COMPONENT_MM3).sum()):4d} of them >= {MIN_COMPONENT_MM3:.0f} mm3, "
              f"largest {sizes.max() * VOXEL_MM3 / 1000:5.1f} mL")
    xs, ys, zs = world_grid(prob.shape, aff)
    near = lambda a, v: int(np.argmin(np.abs(a - v)))
    print("\ninternal cerebral veins: peak partial volume across x at each y (z 4..20 mm)")
    xi = np.where((xs >= -12) & (xs <= 12))[0]
    zi = np.where((zs >= 4) & (zs <= 20))[0]
    for y in range(2, -42, -4):
        prof = prob[np.ix_(xi, [near(ys, y)], zi)].max(axis=(1, 2))
        pk = [f"x={xs[xi[i]]:+.1f}:{prof[i]:.2f}" for i in range(1, len(prof) - 1)
              if prof[i] > prof[i - 1] and prof[i] >= prof[i + 1] and prof[i] > 0.25]
        print(f"  y={y:+4d} max={prof.max():.2f}  peaks: {', '.join(pk) or 'none'}")
    print("\nbasal vein of Rosenthal: peak in the lateral band at each y (z -22..6 mm)")
    zi = np.where((zs >= -22) & (zs <= 6))[0]
    for y in range(6, -42, -3):
        row = []
        for lo, hi, lab in ((-34, -6, "L"), (6, 34, "R")):
            xj = np.where((xs >= lo) & (xs <= hi))[0]
            sub = prob[np.ix_(xj, [near(ys, y)], zi)][:, 0, :]
            i, k = np.unravel_index(sub.argmax(), sub.shape)
            row.append(f"{lab} {sub.max():.2f} at x={xs[xj[i]]:+6.1f} z={zs[zi[k]]:+6.1f}")
        print(f"  y={y:+4d}  " + "  |  ".join(row))
    print("\nthalamostriate vein: peak in the caudothalamic groove (|x| 8..26 mm, z 6..22 mm)")
    zi = np.where((zs >= 6) & (zs <= 22))[0]
    for y in range(0, -30, -3):
        row = []
        for lo, hi, lab in ((-26, -8, "L"), (8, 26, "R")):
            xj = np.where((xs >= lo) & (xs <= hi))[0]
            sub = prob[np.ix_(xj, [near(ys, y)], zi)][:, 0, :]
            i, k = np.unravel_index(sub.argmax(), sub.shape)
            row.append(f"{lab} {sub.max():.2f} at x={xs[xj[i]]:+6.1f} z={zs[zi[k]]:+6.1f}")
        print(f"  y={y:+4d}  " + "  |  ".join(row))
    print("\nstraight sinus ridge: argmax over |x| <= 8 mm, z -25..25 mm")
    xi = np.where(np.abs(xs) <= 8)[0]
    zi = np.where((zs >= -25) & (zs <= 25))[0]
    for y in range(-44, -92, -4):
        sub = prob[np.ix_(xi, [near(ys, y)], zi)][:, 0, :]
        i, k = np.unravel_index(sub.argmax(), sub.shape)
        print(f"  y={y:+4d} max={sub.max():.2f} at x={xs[xi[i]]:+.1f} z={zs[zi[k]]:+.1f}")
    a = ctx.anchors
    print("\naseg anchors (MNI mm):")
    for k in ("third_ventricle", "splenium", "midbrain", "thalamus", "caudate"):
        b = a[k]
        print(f"  {k:16s} x[{b['min'][0]:6.1f},{b['max'][0]:6.1f}] y[{b['min'][1]:6.1f},{b['max'][1]:6.1f}] "
              f"z[{b['min'][2]:6.1f},{b['max'][2]:6.1f}] centroid {np.round(b['centroid'], 1)}")


# ---------------------------------------------------------------- entry point


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Deep cerebral veins and the straight sinus from the VENAT atlas")
    ap.add_argument("--threshold", type=float, default=THRESHOLD)
    ap.add_argument("--min-component", type=float, default=MIN_COMPONENT_MM3, help="mm^3")
    ap.add_argument("--only", help="comma list of mesh ids / structure ids to (re)build")
    ap.add_argument("--inventory", action="store_true", help="print the evidence for the threshold and the cuts, build nothing")
    ap.add_argument("--no-qa", action="store_true", help="skip the slice overlays in work/venat/")
    ap.add_argument("--dry-run", action="store_true", help="report the region volumes without meshing")
    a = ap.parse_args(argv)
    if not PARTIAL_VOLUME.exists():
        print(f"[skip] VENAT atlas not downloaded ({PARTIAL_VOLUME})")
        return
    only = set(a.only.split(",")) if a.only else None
    print("[venat]")
    ctx = load_context(a.threshold, a.min_component)
    if a.inventory:
        inventory(ctx)
        return
    if a.dry_run:
        for r in regions(ctx.anchors):
            sel = r.build(ctx)
            m, comps = largest_components(ctx.scatter(sel), r.min_mm3, r.keep)
            pts = ctx.P[sel]
            box = "" if not len(pts) else (f"x[{pts[:, 0].min():6.1f},{pts[:, 0].max():6.1f}] "
                                           f"y[{pts[:, 1].min():6.1f},{pts[:, 1].max():6.1f}] "
                                           f"z[{pts[:, 2].min():6.1f},{pts[:, 2].max():6.1f}]")
            print(f"  {r.spec.id:32s} region {sel.sum() * VOXEL_MM3:7.0f} mm3 -> kept {m.sum() * VOXEL_MM3:7.0f} mm3  "
                  f"comps {[round(c) for c in comps[:5]]}  {box}")
        return
    results: list[dict] = []
    if not only or WHOLE.id in only:
        results.append(build_whole(ctx, a.threshold))
    named, report = build_named(ctx, only, qa=not a.no_qa)
    results += named
    WORKDIR.mkdir(parents=True, exist_ok=True)
    (WORKDIR / "venat_qa.json").write_text(json.dumps(
        {"threshold": a.threshold, "minComponentMm3": a.min_component,
         "venousVolumeMl": round(float(ctx.mask.sum() * VOXEL_MM3 / 1000), 2),
         "anchors": {k: {kk: [round(float(x), 1) for x in vv] for kk, vv in v.items()}
                     for k, v in ctx.anchors.items() if isinstance(v, dict)},
         "regions": report}, indent=1))
    out_path = WORK / "meshes.json"
    existing = {m["id"]: m for m in json.loads(out_path.read_text())} if out_path.exists() else {}
    for r in results:
        existing[r["id"]] = r
    out_path.write_text(json.dumps(list(existing.values()), indent=1))
    total = sum(r["bytes"] for r in results)
    print(f"venat: {len(results)} meshes, {total / 1e6:.2f} MB -> {out_path}")
    failed = [r["id"] for r in report if r.get("status", "").startswith("ANCHOR")]
    if failed:
        print("anchor checks failed for:", ", ".join(failed))


if __name__ == "__main__":
    main()
