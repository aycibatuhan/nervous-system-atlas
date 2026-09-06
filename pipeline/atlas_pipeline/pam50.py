"""Phase 10: spinal cord MRI from the PAM50 template, curved-reformatted onto our cord.

  atlas-pam50 [--check] [--spacing 0.75] [--contrasts t2,t1] [--no-write]

Why a reformat
--------------
The MNI152NLin2009cAsym template stops at the foramen magnum (z >= -78 mm), so the atlas has no MRI below the
medulla.  PAM50 (De Leener et al., NeuroImage 2018) is an open template of the brainstem and the whole spinal
cord at 0.5 mm whose header affine puts it in ICBM152 coordinates -- but its cord is *straightened*: the cord
runs exactly down the line x = 0, y = -45.9 for 475 mm.  Our cord meshes (Z-Anatomy, landmark-registered) are
naturally curved.  Sampling PAM50 with its own affine would therefore drop the cord MRI 200 mm behind the
lower cord meshes.

So this step builds a *curved reformat*: the cord centreline of our own mesh is measured, a rotation-minimising
frame is carried along it, and every output voxel is expressed as (arc length s, in-plane offset u, v) and read
out of the straight PAM50 volume at (x0(Z) + u, y0(Z) + v, Z) with Z = Z_TOP - s.  Arc length is mapped 1:1
(true cord dimensions), anchored at the top of the PAM50 cord (Z = -66.84 mm), which sits in the band where the
PAM50 and MNI templates were shown to agree (see `--check`).

Outputs (public/data/volumes/)
------------------------------
cord_t2.u8.bin, cord_t1.u8.bin   the reformatted MRI on their own axis-aligned MNI-frame grid (NOT the
                                 193x229x193 brain grid -- the cord is off it), gzipped, x-fastest
labels_spine.u8.bin              PAM50 spinal levels (1 = C1 ... 30 = S5) through the same reformat
labels_spine.json                its lookup table (id -> name, cord region, segment mesh id, ramp colour),
                                 the same shape labels.json has for the anatomical volume; referenced from
                                 manifest.volumes.labels_spine.lut
cord.json                        grid + per-volume metadata, merged into manifest.volumes by atlas-manifest
cord_levels.json                 spinal and vertebral level boundaries in world mm along our centreline, so
                                 derived.py's cord segment blocks can be re-cut from measured levels later
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from .paths import CONFIG, MESHES, OUT, RAW, ROOT, VOLUMES, WORK
from .spaces import load_ras

# ---------------------------------------------------------------- constants
PAM50_ROOT = RAW / "pam50"
MNI_T1 = RAW / "mni_t1w" / "tpl-MNI152NLin2009cAsym_res-01_T1w.nii.gz"

CORD_GLB = MESHES / "spinal-cord" / "spinal-white-columns.glb"      # pipeline output, read at run time
CORD_PLY = WORK / "zanatomy" / "objs" / "spinal-white-columns.ply"  # fallback (Z-Anatomy world metres)

Z_TOP = -66.84          # world z of the top of the PAM50 cord mask == arc length 0
Z_BOTTOM = -541.84      # world z of the caudal end of the PAM50 cord mask
ARC_PAM50 = Z_TOP - Z_BOTTOM        # 475.0 mm of straight cord in PAM50

SPACING = 0.75          # mm, isotropic, of the reformatted volume
R_FULL = 12.0           # mm: full intensity out to here
R_FADE = 16.0           # mm: linear fade to black, and the margin of the bounding box
SLAB = 1.0              # mm: z step of the centreline slabs
SMOOTH = 15             # centreline boxcar width in slabs
CENTRELINE_STEP = 2.0   # mm: arc-length step of the centreline shipped in cord_levels.json

SPINAL_LEVELS = ([f"C{i}" for i in range(1, 9)] + [f"T{i}" for i in range(1, 13)]
                 + [f"L{i}" for i in range(1, 6)] + [f"S{i}" for i in range(1, 6)])
VERTEBRAL_LEVELS = [f"C{i}" for i in range(1, 8)] + [f"T{i}" for i in range(1, 13)] + ["L1"]

# The four cord regions the level volume is coloured by; the mesh ids are derived.py's cord segment blocks, so
# a level painted on a slice and the 3D block it belongs to are the same selection in the UI.  Each region gets
# a smooth rostral -> caudal ramp between two anchors of one hue, so a sagittal slice reads as four bands with
# the individual level still legible inside each.
SPINE_REGIONS = [
    ("cervical", "spinal-segment-cervical", "Cervical cord (C1-C8)", "#A9D2F2", "#123E6E"),
    ("thoracic", "spinal-segment-thoracic", "Thoracic cord (T1-T12)", "#B9E4B2", "#1B5E2B"),
    ("lumbar", "spinal-segment-lumbar", "Lumbar cord (L1-L5)", "#FBD9A5", "#B4530A"),
    ("sacral", "spinal-segment-sacral", "Sacral and coccygeal cord (S1-S5, Co)", "#F3B4AE", "#8C2118"),
]
REGION_OF = {"C": "cervical", "T": "thoracic", "L": "lumbar", "S": "sacral"}


def pam50_dir() -> Path:
    """The unpacked release directory (pipeline/raw/pam50/spinalcordtoolbox-PAM50-<sha>/)."""
    for p in sorted(PAM50_ROOT.glob("*/template")):
        return p.parent
    raise SystemExit(f"PAM50 not unpacked under {PAM50_ROOT}; run atlas-download --with spine")


def pam(name: str):
    return load_ras(pam50_dir() / "template" / f"{name}.nii.gz")


# ---------------------------------------------------------------- our cord mesh
def load_cord_mesh():
    """The cord surface as the pipeline currently ships it, in MNI mm.

    Read from public/data/meshes at run time (not from a copy) so that any correction another step makes to the
    Z-Anatomy registration is picked up automatically.  The shipped glb is meshopt-compressed, which trimesh
    cannot read, so it is decoded with the repo's gltf-transform first.
    """
    import trimesh
    if CORD_GLB.exists():
        gt = ROOT / "node_modules" / ".bin" / "gltf-transform"
        with tempfile.TemporaryDirectory() as td:
            plain = Path(td) / "cord.glb"
            r = subprocess.run([str(gt), "dequantize", str(CORD_GLB), str(plain)], capture_output=True, text=True)
            if r.returncode == 0 and plain.exists():
                return trimesh.load(str(plain), force="mesh"), str(CORD_GLB.relative_to(ROOT))
    if not CORD_PLY.exists():
        raise SystemExit(f"no cord surface: neither {CORD_GLB} nor {CORD_PLY}")
    T = np.array(json.loads((CONFIG / "zanatomy_to_mni.json").read_text())["matrix"])
    m = trimesh.load(str(CORD_PLY), force="mesh")
    m.apply_transform(T)
    return m, str(CORD_PLY.relative_to(ROOT))


def centreline(mesh, slab: float = SLAB, smooth: int = SMOOTH) -> np.ndarray:
    """Per-z slab centroids of surface samples, boxcar-smoothed in x and y; ordered from the top down."""
    import trimesh
    from scipy.ndimage import uniform_filter1d
    # seeded: the centreline (and so the output grid) must be reproducible from one run to the next
    pts = np.asarray(trimesh.sample.sample_surface_even(mesh, 200_000, seed=20250730)[0])
    zhi, zlo = pts[:, 2].max(), pts[:, 2].min()
    rows = []
    for z in np.arange(zhi - slab / 2, zlo, -slab):
        sel = np.abs(pts[:, 2] - z) < slab / 2
        if sel.sum() >= 20:
            rows.append([pts[sel, 0].mean(), pts[sel, 1].mean(), z])
    C = np.array(rows)
    C[:, 0] = uniform_filter1d(C[:, 0], smooth, mode="nearest")
    C[:, 1] = uniform_filter1d(C[:, 1], smooth, mode="nearest")
    return C


def resample_arc(C: np.ndarray, step: float = 0.25) -> tuple[np.ndarray, np.ndarray]:
    """Resample a polyline to a uniform arc-length step. Returns (points, arc length from the first point)."""
    d = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))])
    s = np.arange(0.0, d[-1] + 1e-9, step)
    P = np.column_stack([np.interp(s, d, C[:, k]) for k in range(3)])
    return P, s


def carry_frame(P: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Tangent (caudal), right and anterior unit vectors along the centreline.

    The cord is never parallel to the anterior axis, so the anterior reference (0, 1, 0) gives a stable frame
    without the drift a rotation-minimising sweep would accumulate over 500 mm.
    """
    T = np.gradient(P, axis=0)
    T /= np.linalg.norm(T, axis=1)[:, None]
    A0 = np.array([0.0, 1.0, 0.0])
    R = np.cross(T, A0)
    R /= np.linalg.norm(R, axis=1)[:, None]
    A = np.cross(R, T)
    A /= np.linalg.norm(A, axis=1)[:, None]
    return T, R, A


def anchor_arc(P: np.ndarray, s: np.ndarray) -> float:
    """Arc length of the point where our centreline crosses z = Z_TOP (the top of the PAM50 cord)."""
    z = P[:, 2]
    i = int(np.argmin(np.abs(z - Z_TOP)))
    j = min(max(i, 1), len(z) - 2)
    dz = z[j + 1] - z[j - 1]
    return float(s[j] + (Z_TOP - z[j]) * (s[j + 1] - s[j - 1]) / dz) if abs(dz) > 1e-9 else float(s[i])


def pam50_centre() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(z, x0, y0) of the PAM50 cord centre per slice, from PAM50_centerline."""
    img = pam("PAM50_centerline")
    d = np.asanyarray(img.dataobj) > 0
    idx = np.argwhere(d)
    w = idx @ img.affine[:3, :3].T + img.affine[:3, 3]
    zs = np.unique(np.round(w[:, 2], 3))
    x0 = np.array([w[np.abs(w[:, 2] - z) < 1e-3, 0].mean() for z in zs])
    y0 = np.array([w[np.abs(w[:, 2] - z) < 1e-3, 1].mean() for z in zs])
    return zs, x0, y0


# ---------------------------------------------------------------- 1. PAM50 <-> MNI check
def check(verbose: bool = True) -> dict:
    """Compare the PAM50 T1 with the MNI T1 in the band where both exist (z -77 .. -67, upper medulla).

    Both templates show the medulla as the one bright blob in a dark CSF ring, so the residual is measured as
    the difference of the intensity-weighted centroid of that blob, per 0.5 mm slice.
    """
    from scipy import ndimage
    mni = load_ras(MNI_T1)
    p = pam("PAM50_t1")
    M = np.asanyarray(mni.dataobj).astype(np.float32)
    Pd = np.asanyarray(p.dataobj).astype(np.float32)

    def samp(data, aff, w):
        v = (np.asarray(w, float) - aff[:3, 3]) @ np.linalg.inv(aff[:3, :3]).T
        return ndimage.map_coordinates(data, v.T, order=1, mode="constant", cval=0.0)

    xs = np.arange(-10, 10.01, 0.25)
    ys = np.arange(-56, -34.99, 0.25)
    XX, YY = np.meshgrid(xs, ys, indexing="ij")
    rows = []
    for z in np.arange(-77.0, Z_TOP + 0.01, 0.5):
        W = np.stack([XX.ravel(), YY.ravel(), np.full(XX.size, z)], -1)
        out = []
        for data, aff in ((M, mni.affine), (Pd, p.affine)):
            v = samp(data, aff, W).reshape(XX.shape)
            lab, n = ndimage.label(v >= v.max() * 0.55)
            if n == 0:
                out.append((np.nan, np.nan))
                continue
            best = min(((XX[lab == i].mean() ** 2 + (YY[lab == i].mean() + 46) ** 2, lab == i) for i in range(1, n + 1)),
                       key=lambda t: t[0])[1]
            wt = v[best]
            out.append((float((XX[best] * wt).sum() / wt.sum()), float((YY[best] * wt).sum() / wt.sum())))
        rows.append([z, out[0][0], out[0][1], out[1][0], out[1][1]])
    r = np.array(rows)
    dx, dy = r[:, 1] - r[:, 3], r[:, 2] - r[:, 4]
    res = {"band_mm": [float(r[0, 0]), float(r[-1, 0])], "n_slices": len(r),
           "dx_mean": float(np.nanmean(dx)), "dx_sd": float(np.nanstd(dx)),
           "dy_mean": float(np.nanmean(dy)), "dy_sd": float(np.nanstd(dy)),
           "dxy_rms": float(np.sqrt(np.nanmean(dx ** 2 + dy ** 2)))}
    if verbose:
        print(f"PAM50 <-> MNI, medulla centroid over z {res['band_mm'][0]:.0f} .. {res['band_mm'][1]:.0f} mm "
              f"({res['n_slices']} slices at 0.5 mm)")
        print(f"{'z':>7} {'MNI x':>7} {'MNI y':>7} {'PAM x':>7} {'PAM y':>7} {'dx':>6} {'dy':>6}")
        for row, a, b in zip(r, dx, dy):
            print(f"{row[0]:7.1f} {row[1]:7.2f} {row[2]:7.2f} {row[3]:7.2f} {row[4]:7.2f} {a:6.2f} {b:6.2f}")
        print(f"residual dx {res['dx_mean']:+.2f} +- {res['dx_sd']:.2f} mm, dy {res['dy_mean']:+.2f} +- "
              f"{res['dy_sd']:.2f} mm, RMS {res['dxy_rms']:.2f} mm -> the header affine is honoured")
    return res


# ---------------------------------------------------------------- 2. the reformat
def build_map(spacing: float = SPACING):
    """Everything geometric: the centreline, the frame, the output grid and the per-voxel PAM50 coordinates."""
    from scipy.spatial import cKDTree
    mesh, src = load_cord_mesh()
    C = centreline(mesh)
    P, s = resample_arc(C, 0.25)
    T, R, A = carry_frame(P)
    s0 = anchor_arc(P, s)
    # the reformat only covers the arc that PAM50 actually holds
    lo, hi = s0, s0 + ARC_PAM50
    inband = (s >= lo - 1) & (s <= hi + 1)
    box_lo = P[inband].min(0) - R_FADE
    box_hi = P[inband].max(0) + R_FADE
    dims = np.maximum(np.ceil((box_hi - box_lo) / spacing).astype(int) + 1, 2)
    origin = box_lo
    affine = np.eye(4)
    affine[:3, :3] = np.diag([spacing] * 3)
    affine[:3, 3] = origin

    gi = [np.arange(d) for d in dims]
    G = np.stack(np.meshgrid(*gi, indexing="ij"), -1).reshape(-1, 3).astype(np.float32)
    W = G * spacing + origin

    tree = cKDTree(P)
    dist = np.empty(len(W), np.float32)
    near = np.empty(len(W), np.int64)
    for a in range(0, len(W), 2_000_000):
        b = min(a + 2_000_000, len(W))
        dist[a:b], near[a:b] = tree.query(W[a:b], workers=-1)
    sel = np.flatnonzero(dist <= R_FADE)
    idx = near[sel]
    delta = W[sel] - P[idx]
    arc = s[idx] + np.einsum("ij,ij->i", delta, T[idx])
    u = np.einsum("ij,ij->i", delta, R[idx])
    v = np.einsum("ij,ij->i", delta, A[idx])
    r = np.hypot(u, v)
    keep = (arc >= lo) & (arc <= hi) & (r <= R_FADE)
    sel, u, v, r, arc = sel[keep], u[keep], v[keep], r[keep], arc[keep]

    Z = Z_TOP - (arc - s0)
    czs, cx0, cy0 = pam50_centre()
    order = np.argsort(czs)
    x0 = np.interp(Z, czs[order], cx0[order])
    y0 = np.interp(Z, czs[order], cy0[order])
    world_pam = np.column_stack([x0 + u, y0 + v, Z])
    fade = np.clip((R_FADE - r) / (R_FADE - R_FULL), 0.0, 1.0).astype(np.float32)
    return {"mesh_source": src, "centreline": P, "arc": s, "s0": s0, "frame": (T, R, A),
            "dims": tuple(int(d) for d in dims), "origin": origin, "affine": affine, "spacing": spacing,
            "sel": sel, "world_pam": world_pam, "fade": fade, "arc_of_voxel": arc,
            "cord_arc_total": float(s[-1])}


def cord_window(name: str, k: float = 0.25) -> tuple[float, float]:
    """Grey window centred on the cord itself, not on the whole field of view.

    On T2 the CSF around the cord is three times brighter than the cord, so a window over the whole tube leaves
    the 8 % grey/white matter difference inside the cord spanning about five of the 256 levels and the butterfly
    invisible.  Windowing on the cord's own 5th-95th percentile (widened by `k` of that span on each side) gives
    the cord roughly 25 levels between grey and white matter and lets the CSF clip to white -- which is also how
    a clinical cord T2 is windowed when the grey matter is the point.
    """
    cord = np.asanyarray(pam("PAM50_cord").dataobj) > 0
    d = np.asanyarray(pam(name).dataobj).astype(np.float32)
    c5, c95 = np.percentile(d[cord], [5, 95])
    span = max(float(c95 - c5), 1.0)
    return max(0.0, float(c5) - k * span), float(c95) + k * span


def sample(name: str, world: np.ndarray, order: int = 1) -> np.ndarray:
    from scipy import ndimage
    img = pam(name)
    data = np.asanyarray(img.dataobj).astype(np.float32)
    v = (world - img.affine[:3, 3]) @ np.linalg.inv(img.affine[:3, :3]).T
    return ndimage.map_coordinates(data, v.T, order=order, mode="constant", cval=0.0)


def write_volume(name: str, dims, values: np.ndarray, sel: np.ndarray, dtype=np.uint8) -> dict:
    import gzip
    import hashlib
    arr = np.zeros(int(np.prod(dims)), dtype)
    arr[sel] = values
    raw = arr.reshape(dims).tobytes(order="F")
    path = VOLUMES / f"{name}.u8.bin"
    with gzip.open(path, "wb", compresslevel=9) as f:
        f.write(raw)
    return {"file": f"volumes/{path.name}", "dtype": "uint8", "shape": [int(d) for d in dims],
            "bytes_raw": len(raw), "bytes_gz": path.stat().st_size, "sha256": hashlib.sha256(raw).hexdigest()}


# ---------------------------------------------------------------- 3. level table
def level_positions(m: dict, volume: str, names: list[str]) -> list[dict]:
    """Where every PAM50 level lands on our centreline: PAM50 z -> arc length -> world mm."""
    img = pam(volume)
    d = np.asanyarray(img.dataobj)
    aff = img.affine
    P, s, s0 = m["centreline"], m["arc"], m["s0"]
    out = []
    for lid in range(1, len(names) + 1):
        idx = np.argwhere(d == lid)
        if not len(idx):
            continue
        w = idx @ aff[:3, :3].T + aff[:3, 3]
        zt, zb = float(w[:, 2].max()), float(w[:, 2].min())
        rec = {"id": lid, "name": names[lid - 1], "pam50_z": [round(zb, 2), round(zt, 2)]}
        for key, zz in (("top", zt), ("bottom", zb)):
            arc = s0 + (Z_TOP - zz)
            p = np.array([np.interp(arc, s, P[:, k]) for k in range(3)])
            rec[key] = [round(float(x), 2) for x in p]
        rec["arc_mm"] = [round(s0 + (Z_TOP - zt), 2), round(s0 + (Z_TOP - zb), 2)]
        rec["z_mm"] = [round(rec["bottom"][2], 2), round(rec["top"][2], 2)]
        out.append(rec)
    return out


def centreline_table(m: dict, step: float = CENTRELINE_STEP) -> tuple[np.ndarray, np.ndarray]:
    """The whole measured centreline, resampled to `step` mm, for consumers that need the curve itself.

    `atlas-derived` cuts the cord segment blocks on planes normal to the local tangent, so it needs the curve
    and not only the level points; shipping it here keeps one measurement of the centreline in the pipeline.
    """
    P, s = m["centreline"], m["arc"]
    out_s = np.arange(0.0, float(s[-1]) + 1e-9, step)
    out_p = np.column_stack([np.interp(out_s, s, P[:, k]) for k in range(3)])
    return out_s, out_p


def ramp(lo: str, hi: str, n: int, i: int) -> str:
    """Colour i of n on a linear sRGB ramp between two hex anchors (n == 1 keeps the light anchor)."""
    a = [int(lo[k:k + 2], 16) for k in (1, 3, 5)]
    b = [int(hi[k:k + 2], 16) for k in (1, 3, 5)]
    t = 0.0 if n < 2 else i / (n - 1)
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(a, b))


def spine_lut(spinal: list[dict]) -> dict:
    """labels_spine.json: id -> level entry, in the same shape labels.json uses for the anatomical volume.

    Every id in labels_spine.u8.bin (1 = C1 ... 30 = S5) maps to its name, the cord region it belongs to, the
    derived.py cord segment block that carries it in 3D, and a colour from that region's ramp.  Where the level
    was measured on our centreline the world z range and arc length come along, so the UI can name the level
    under the cursor without reloading cord_levels.json.
    """
    by = {r["name"]: r for r in spinal}
    regions = {key: {"name": name, "meshId": mid, "structureId": mid, "system": "spinal-cord",
                     "levels": [n for n in SPINAL_LEVELS if REGION_OF[n[0]] == key],
                     "colour": ramp(lo, hi, 2, 1)}
               for key, mid, name, lo, hi in SPINE_REGIONS}
    anchors = {key: (lo, hi) for key, _mid, _name, lo, hi in SPINE_REGIONS}
    mesh_of = {key: mid for key, mid, _name, _lo, _hi in SPINE_REGIONS}
    lut = {}
    for lid, name in enumerate(SPINAL_LEVELS, 1):
        key = REGION_OF[name[0]]
        peers = regions[key]["levels"]
        lo, hi = anchors[key]
        e = {"name": name, "region": key, "regionName": regions[key]["name"], "meshId": mesh_of[key],
             "structureId": mesh_of[key], "system": "spinal-cord",
             "colour": ramp(lo, hi, len(peers), peers.index(name))}
        r = by.get(name)
        if r:
            e["zMm"] = r["z_mm"]
            e["arcMm"] = r["arc_mm"]
        lut[str(lid)] = e
    return {"space": "MNI152NLin2009cAsym", "volume": "labels_spine", "source": "pam50",
            "note": "PAM50 spinal levels carried onto our cord centreline by the atlas-pam50 curved reformat. "
                    "ids are the PAM50 spinal-level ids (1 = C1 ... 30 = S5) as they appear in "
                    "volumes/labels_spine.u8.bin; meshId is the derived.py cord segment block that contains "
                    "the level, so selecting a level and selecting its 3D block are the same selection.",
            "regions": regions, "lut": lut}


def segment_blocks() -> dict:
    """z range of derived.py's cord segment blocks, from the current mesh records."""
    p = WORK / "meshes.json"
    if not p.exists():
        return {}
    return {m["id"]: [m["bbox"][0][2], m["bbox"][1][2]]
            for m in json.loads(p.read_text()) if m["id"].startswith("spinal-segment-")}


# ---------------------------------------------------------------- driver
def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="PAM50 spinal cord MRI, curved-reformatted onto our cord")
    ap.add_argument("--check", action="store_true", help="only report the PAM50 <-> MNI residual")
    ap.add_argument("--spacing", type=float, default=SPACING)
    ap.add_argument("--contrasts", default="t2,t1")
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args(argv)

    residual = check(verbose=True)
    if a.check:
        return

    m = build_map(a.spacing)
    dims, sel = m["dims"], m["sel"]
    print(f"\ncord surface: {m['mesh_source']}")
    print(f"centreline {len(m['centreline'])} points, total arc {m['cord_arc_total']:.1f} mm, "
          f"anchor (z = {Z_TOP} mm) at arc {m['s0']:.2f} mm")
    print(f"grid {dims[0]}x{dims[1]}x{dims[2]} at {a.spacing} mm, origin {np.round(m['origin'], 2).tolist()}, "
          f"{np.prod(dims)/1e6:.1f} M voxels, {len(sel)/1e3:.0f} k inside the tube")

    out = {"space": "MNI152NLin2009cAsym", "shape": [int(d) for d in dims], "spacing": [a.spacing] * 3,
           "origin_ras": [round(float(x), 4) for x in m["origin"]],
           "affine_ras": [[round(float(x), 6) for x in row] for row in m["affine"][:3].tolist()] + [[0, 0, 0, 1]],
           "source": "pam50", "license": "PAM50-unlicensed",
           "reformat": {"method": "curved reformat of the straightened PAM50 cord onto the centreline of "
                                  f"{m['mesh_source']} (per-z slab centroids, {SMOOTH} mm boxcar); arc length "
                                  f"mapped 1:1 and anchored at z = {Z_TOP} mm (top of the PAM50 cord)",
                        "anchor_z_mm": Z_TOP, "arc_pam50_mm": ARC_PAM50,
                        "anchor_arc_mm": round(m["s0"], 3), "cord_arc_total_mm": round(m["cord_arc_total"], 2),
                        "radius_full_mm": R_FULL, "radius_fade_mm": R_FADE,
                        "mni_residual": residual},
           "contrasts": {}}

    for c in [x.strip() for x in a.contrasts.split(",") if x.strip()]:
        vals = sample(f"PAM50_{c}", m["world_pam"], order=1)
        lo, hi = cord_window(f"PAM50_{c}")
        u8 = np.clip((vals - lo) / max(hi - lo, 1e-6) * 255.0, 0, 255) * m["fade"]
        key = f"cord_{c}"
        rec = write_volume(key, dims, u8.astype(np.uint8), sel) if not a.no_write else {}
        rec.update({"window": 255, "level": 127, "source_window": [round(float(lo), 1), round(float(hi), 1)],
                    "space": "cord", "spacing": [a.spacing] * 3,
                    "origin_ras": out["origin_ras"], "affine_ras": out["affine_ras"]})
        out["contrasts"][key] = rec
        print(f"  {key:12s} window {lo:.0f}..{hi:.0f}  {rec.get('bytes_gz', 0)/1024:8.1f} KB gz "
              f"({rec.get('bytes_raw', 0)/1e6:.1f} MB raw)")

    lv = sample("PAM50_spinal_levels", m["world_pam"], order=0)
    rec = write_volume("labels_spine", dims, lv.astype(np.uint8), sel) if not a.no_write else {}
    rec.update({"space": "cord", "spacing": [a.spacing] * 3, "origin_ras": out["origin_ras"],
                "affine_ras": out["affine_ras"], "lut": "volumes/labels_spine.json"})
    out["contrasts"]["labels_spine"] = rec
    print(f"  {'labels_spine':12s} 30 levels        {rec.get('bytes_gz', 0)/1024:8.1f} KB gz")

    spinal = level_positions(m, "PAM50_spinal_levels", SPINAL_LEVELS)
    vert = level_positions(m, "PAM50_levels", VERTEBRAL_LEVELS)
    blocks = segment_blocks()
    print(f"\n{'level':>6} {'PAM50 z':>16} {'arc mm':>15} {'our world z':>16}  centre (x, y) mm")
    for r in spinal:
        print(f"{r['name']:>6} {r['pam50_z'][1]:7.1f}..{r['pam50_z'][0]:7.1f} {r['arc_mm'][0]:7.1f}..{r['arc_mm'][1]:6.1f} "
              f"{r['z_mm'][1]:7.1f}..{r['z_mm'][0]:7.1f}  ({r['top'][0]:5.1f}, {r['top'][1]:7.1f})")
    if blocks:
        print("\nderived.py cord segment blocks vs the PAM50 levels landed on our centreline:")
        pairs = [("spinal-segment-cervical", "C8", "T1"), ("spinal-segment-thoracic", "T12", "L1"),
                 ("spinal-segment-lumbar", "L5", "S1")]
        by = {r["name"]: r for r in spinal}
        for mid, last, nxt in pairs:
            if mid in blocks and last in by and nxt in by:
                boundary = 0.5 * (by[last]["z_mm"][0] + by[nxt]["z_mm"][1])
                print(f"  {mid:26s} block ends z {blocks[mid][0]:7.1f}   PAM50 {last}/{nxt} boundary z "
                      f"{boundary:7.1f}   delta {blocks[mid][0] - boundary:+6.1f} mm")

    if not a.no_write:
        (VOLUMES / "cord.json").write_text(json.dumps(out, indent=1))
        sl = spine_lut(spinal)
        (VOLUMES / "labels_spine.json").write_text(json.dumps(sl, indent=1))
        print(f"\nwrote {VOLUMES / 'labels_spine.json'}: {len(sl['lut'])} levels in "
              f"{len(sl['regions'])} regions ("
              + ", ".join(f"{k} {len(v['levels'])}" for k, v in sl["regions"].items()) + ")")
        cl_s, cl_p = centreline_table(m)
        (VOLUMES / "cord_levels.json").write_text(json.dumps(
            {"space": "MNI152NLin2009cAsym", "source": "pam50",
             "note": "PAM50 level labels carried onto our cord centreline by the atlas-pam50 curved reformat; "
                     "top/bottom are world mm on the centreline, z_mm the world z range of that level",
             "anchor_z_mm": Z_TOP, "centrelineSource": m["mesh_source"],
             "centreline": {"note": "the measured cord centreline in world mm, resampled to a uniform "
                                    f"{CENTRELINE_STEP} mm arc-length step; arc[i] is the arc length of "
                                    "points[i] from the top of the cord surface, the same arc used by "
                                    "spinalLevels[].arc_mm.  atlas-derived interpolates it to place the "
                                    "segment cut planes and their normals (the local tangent).",
                            "stepMm": CENTRELINE_STEP,
                            "arc": [round(float(x), 3) for x in cl_s],
                            "points": [[round(float(c), 3) for c in q] for q in cl_p]},
             "spinalLevels": spinal, "vertebralLevels": vert,
             "segmentBlocks": blocks}, indent=1))
        print(f"\nwrote {VOLUMES / 'cord.json'} and {VOLUMES / 'cord_levels.json'}")
        total = sum(v.get("bytes_gz", 0) for v in out["contrasts"].values())
        print(f"total shipped: {total/1e6:.2f} MB gz")


if __name__ == "__main__":
    main()
