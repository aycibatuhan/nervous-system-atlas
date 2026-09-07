"""Phase 7: derived meshes -- structures that no source atlas ships, constructed from atlas geometry we do have.

  atlas-derived [--only id1,id2]

Every record written here carries a `derived` field with a one-line description of the construction, which the
manifest passes through, so the UI and the content entries can say plainly that the shape is schematic.

What is built
-------------
spinal-segment-cervical / -thoracic / -lumbar / -sacral, filum-terminale,
spinal-enlargement-cervical / -lumbosacral
    The Z-Anatomy cord surface (pipeline/work/zanatomy/objs/spinal-white-columns.ply, world metres), mapped to
    MNI with the affine and the post-correction (atlas_pipeline.midline: the sub-cranial x shear and the
    anteroposterior ramp) and then cut and capped.  The cut levels are *measured*: atlas-pam50 reformats the
    PAM50 spinal template along this cord's own centreline and writes every PAM50 spinal level C1-S5 as world
    points on that centreline (public/data/volumes/cord_levels.json), so a block boundary is the PAM50
    level boundary and the cut is the plane through that centreline point normal to the local tangent -- not a
    horizontal z plane, which would cut obliquely wherever the cord leans.  PAM50's S5 ends about 90 mm above
    the caudal end of the Z-Anatomy surface, because that surface tapers on into the filum terminale: the
    remainder below the S5 boundary is exported as `filum-terminale` (Z-Anatomy has no "Filum terminale"
    object of its own).  The two enlargements are the same cut machinery over C5-T1 and L1-S3, off by default.
    Without cord_levels.json the step warns and falls back to the previous construction, horizontal planes at
    the Z-Anatomy vertebral-body landmarks with the classical cord-segment-to-vertebra rule.  (Z-Anatomy models
    one spinal root and ganglion pair per intervertebral foramen from C2 to L2, i.e. it puts every cord segment
    opposite the same-numbered vertebra, so its own roots can never supply the boundaries.)

phrenic-nerve-l/-r, lumbosacral-trunk-l/-r
    Polylines from pipeline/config/derived_nerves.yaml (each waypoint read off a named Z-Anatomy object),
    mapped to MNI mm, smoothed with a centripetal Catmull-Rom spline and swept into a round, round-capped tube.
    The waypoints are corrected before the spline, so the tube is round in corrected MNI space.

choroid-plexus-fourth-ventricle
    The posterior (roof) boundary of the caudal half of the FreeSurfer aseg fourth ventricle (label 15),
    dilated 1 mm, with two short lateral extensions along the lateral recesses towards the foramina of Luschka.

spinal-segment-*-vert, filum-terminale-vert  (PUBLIC edition only)
    The same four cord blocks cut the *other* way: horizontal planes at the Z-Anatomy vertebral-body landmarks
    with the classical cord-segment-to-vertebra rule, i.e. `cord_segments_by_vertebrae()` above.  The measured
    cut uses PAM50 spinal levels, which makes those four blocks derived files of a template the public edition
    may not redistribute; this variant is Z-Anatomy geometry and a textbook rule and nothing else, so it ships
    in the public edition instead.  The sacral block ends at the conus, whose tip is put at the middle of the
    Z-Anatomy "Intervertebral disc L1-L2" (`conus_level()`, read from work/zanatomy/objects.json) -- the
    classical adult level -- and the remainder of the cord surface below it is exported as `filum-terminale-vert`,
    the public edition's filum.  No PAM50 number enters either cut.

<nucleus>-anchor[-l/-r]  (PUBLIC edition only)
    Landmark-anchored location markers for the brainstem nuclei whose only delineation in this atlas comes
    from a source the public edition may not redistribute.  Each is an ellipsoid of the nucleus's PUBLISHED
    volume, placed by a textbook topographic relation to open geometry (the aseg brainstem and fourth
    ventricle, MASSP20 nuclei, HCP1065 tracts) and clipped to the aseg brainstem label dilated 1 mm.  The
    recipes, the volumes and the bibliography refs they come from live in
    pipeline/config/brainstem_landmarks.yaml; not one number in this construction is measured on, or copied
    from, the restricted data.  Records carry `derived: "landmark-anchored: ..."` so the UI and the content
    entries say plainly that the shape is schematic and marks a location, not a boundary.
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import trimesh
import yaml

from . import midline
from .catalog import BUDGET, LOD_FACES, LOD_MIN_FACES, MeshSpec
from .meshing import export_with_lod, mesh_from_mask
from .paths import CONFIG, MESHES, RAW, VOLUMES, WORK

ZW = WORK / "zanatomy"
CORD_PLY = ZW / "objs" / "spinal-white-columns.ply"
CORD_LEVELS_JSON = VOLUMES / "cord_levels.json"   # written by atlas-pam50
ASEG = RAW / "mni_aseg" / "tpl-MNI152NLin2009cAsym_res-01_seg-aseg_dseg.nii.gz"

# ---------------------------------------------------------------- spinal cord segments
# Preferred: the measured PAM50 spinal levels that atlas-pam50 lands on our own cord centreline
# (public/data/volumes/cord_levels.json).  Each block runs from the boundary above its first level to the
# boundary below its last, cut on the plane through that centreline point normal to the local tangent.
CORD_BLOCKS = [
    # id, name, first level, last level, colour, visible, note
    ("spinal-segment-cervical", "Cervical cord (C1-C8)", "C1", "C8", "#DDC8AD", False,
     "runs from the top of the cord surface (the cervicomedullary junction) to the PAM50 C8/T1 boundary"),
    ("spinal-segment-thoracic", "Thoracic cord (T1-T12)", "T1", "T12", "#D0B899", False,
     "runs from the PAM50 C8/T1 boundary to the PAM50 T12/L1 boundary"),
    ("spinal-segment-lumbar", "Lumbar cord (L1-L5)", "L1", "L5", "#C3A785", False,
     "runs from the PAM50 T12/L1 boundary to the PAM50 L5/S1 boundary"),
    ("spinal-segment-sacral", "Sacral and coccygeal cord (S1-S5, Co)", "S1", "S5", "#B69771", False,
     "runs from the PAM50 L5/S1 boundary to the caudal end of the PAM50 S5 level, i.e. the tip of the conus "
     "medullaris"),
]
# Overlays cut from the same centreline; off by default, so they never double the cord in the default scene.
CORD_OVERLAYS = [
    ("spinal-enlargement-cervical", "Cervical enlargement (C5-T1)", "C5", "T1", "#E2CDB1", "cervical-enlargement",
     "the C5 to T1 span of the cord, the segments of the brachial plexus"),
    ("spinal-enlargement-lumbosacral", "Lumbosacral enlargement (L1-S3)", "L1", "S3", "#CBB08D", "spinal-cord",
     "the L1 to S3 span of the cord, the segments of the lumbosacral plexus"),
]
FILUM = ("filum-terminale", "Filum terminale", "#C9BBA6",
         "everything below the caudal end of the PAM50 S5 level: the thread of pia and glial tissue that the "
         "Z-Anatomy cord surface continues into below the conus")
CORD_METHOD_PAM50 = (
    "Z-Anatomy cord surface, mapped to MNI with the affine and the sub-cranial post-correction, then cut on "
    "planes normal to the local tangent of its own measured centreline at the PAM50 spinal-level boundaries "
    "(atlas-pam50 curved reformat, public/data/volumes/cord_levels.json); the levels are those of the PAM50 "
    "template average, not of an individual")
# Fallback: the old cut planes in Z-Anatomy world metres (+z up), from work/zanatomy/objects.json bboxes.
CORD_LEVELS = [
    ("spinal-segment-cervical", "Cervical cord (C1-C8)", 1.4420, None,
     "C8 ends at the C7/T1 intervertebral disc (Intervertebral disc C7-T1, z 1.436-1.448)", "#DDC8AD"),
    ("spinal-segment-thoracic", "Thoracic cord (T1-T12)", 1.2245, 1.4420,
     "T12 ends at the T9/T10 disc (Intervertebral disc T9-T10, z 1.217-1.232): lumbar segments lie opposite T10-T12", "#D0B899"),
    ("spinal-segment-lumbar", "Lumbar cord (L1-L5)", 1.1390, 1.2245,
     "L5 ends at the mid-body of the T12 vertebra (Vertebra T12, z 1.112-1.166): sacral segments lie opposite T12-L1", "#C3A785"),
    ("spinal-segment-sacral", "Sacral and coccygeal cord (S1-S5, Co)", None, 1.1390,
     "runs to the tip of the conus medullaris (the caudal end of the Z-Anatomy cord surface)", "#B69771"),
]
# The PUBLIC cord blocks stop at the conus and a filum runs on below it.  The conus tip is put at the L1-L2
# intervertebral disc -- the classical adult level -- read off the Z-Anatomy vertebral column itself, so this
# cut, like the four block cuts above it, is Z-Anatomy geometry and a textbook rule and nothing else.
ZOBJECTS = ZW / "objects.json"
CONUS_DISC = "Intervertebral disc L1-L2"
FILUM_VERT = ("filum-terminale", "Filum terminale", "#C9BBA6")
CORD_METHOD = ("Z-Anatomy cord surface cut by horizontal planes at the classical cord-segment / vertebral-body "
               "levels (cervical opposite C1-C7, thoracic opposite T1-T9/T10, lumbar opposite T10-T12, sacral "
               "and coccygeal opposite T12-L1); block boundaries are schematic, not measured on this specimen")

# ---------------------------------------------------------------- fourth-ventricle choroid plexus
FV_LABEL = 15
FV_AQUEDUCT_Z = -25.0     # above this the aseg fourth-ventricle label is the cerebral aqueduct
FV_OBEX_Z = -54.0         # below this it is the central canal at the obex
FV_RECESS_BAND = (-45.0, -34.0)   # z band that holds the lateral recesses
FV_RECESS_LEN = 7.0       # mm of lateral extension towards each foramen of Luschka
FV_RECESS_R = 1.6         # mm radius of that extension


def ztomni() -> tuple[np.ndarray, dict | None]:
    """The Z-Anatomy affine and the post-correction fitted by `atlas-zanatomy-midline` (x shear + AP ramp).

    Everything built here from Z-Anatomy geometry goes through both, so the cord blocks, the phrenic nerves
    and the lumbosacral trunks sit on the same corrected midline -- and at the same corrected anteroposterior
    position -- as the exported Z-Anatomy meshes."""
    cfg = json.loads((CONFIG / "zanatomy_to_mni.json").read_text())
    pc = cfg.get("post_correction")
    if pc is not None and pc.get("stale"):
        raise SystemExit("post_correction is marked stale (the affine was refitted): run atlas-zanatomy-midline")
    return np.array(cfg["matrix"]), pc


def apply(T: np.ndarray, P: np.ndarray, pc: dict | None = None) -> np.ndarray:
    """Z-Anatomy world metres -> corrected MNI mm."""
    return midline.transform(np.asarray(P, float), T, pc)


# ---------------------------------------------------------------- polyline -> tube
def catmull_rom(P: np.ndarray, per_segment: int = 12) -> np.ndarray:
    """Centripetal Catmull-Rom through every waypoint (no overshoot, no cusps at the joints)."""
    P = np.asarray(P, float)
    if len(P) < 3:
        return P
    Q = np.vstack([P[0] + (P[0] - P[1]), P, P[-1] + (P[-1] - P[-2])])
    d = np.linalg.norm(np.diff(Q, axis=0), axis=1) ** 0.5
    t = np.concatenate([[0.0], np.cumsum(np.maximum(d, 1e-6))])
    out = []
    for i in range(1, len(Q) - 2):
        t0, t1, t2, t3 = t[i - 1:i + 3]
        p0, p1, p2, p3 = Q[i - 1:i + 3]
        for u in np.linspace(t1, t2, per_segment, endpoint=(i == len(Q) - 3)):
            a1 = (t1 - u) / (t1 - t0) * p0 + (u - t0) / (t1 - t0) * p1
            a2 = (t2 - u) / (t2 - t1) * p1 + (u - t1) / (t2 - t1) * p2
            a3 = (t3 - u) / (t3 - t2) * p2 + (u - t2) / (t3 - t2) * p3
            b1 = (t2 - u) / (t2 - t0) * a1 + (u - t0) / (t2 - t0) * a2
            b2 = (t3 - u) / (t3 - t1) * a2 + (u - t1) / (t3 - t1) * a3
            out.append((t2 - u) / (t2 - t1) * b1 + (u - t1) / (t2 - t1) * b2)
    return np.array(out)


def tube(points: np.ndarray, radius: float, sections: int = 16) -> trimesh.Trimesh:
    """Round tube of constant radius along a polyline, with hemispherical caps.

    Uses rotation-minimising frames (the previous normal projected onto each new normal plane), so the ring
    seam does not twist around bends."""
    P = np.asarray(points, float)
    keep = np.concatenate([[True], np.linalg.norm(np.diff(P, axis=0), axis=1) > 1e-6])
    P = P[keep]
    n = len(P)
    if n < 2:
        raise ValueError("a tube needs at least two distinct points")
    T = np.gradient(P, axis=0) if n > 2 else np.repeat((P[1] - P[0])[None], 2, axis=0)
    T /= np.linalg.norm(T, axis=1)[:, None]
    up = np.array([0.0, 0.0, 1.0])
    if abs(T[0] @ up) > 0.9:
        up = np.array([1.0, 0.0, 0.0])
    N = np.cross(T[0], up); N /= np.linalg.norm(N)
    normals = [N]
    for i in range(1, n):
        v = N - T[i] * (N @ T[i])
        nv = np.linalg.norm(v)
        if nv < 1e-8:
            v = np.cross(T[i], up); nv = np.linalg.norm(v)
        N = v / nv
        normals.append(N)
    N = np.array(normals)
    B = np.cross(T, N)
    # hemispherical caps: extra rings of shrinking radius beyond each end, then an apex vertex
    phis = [np.pi / 6, np.pi / 3]
    centres = ([P[0] - T[0] * radius * np.sin(p) for p in reversed(phis)] + list(P)
               + [P[-1] + T[-1] * radius * np.sin(p) for p in phis])
    radii = [radius * np.cos(p) for p in reversed(phis)] + [radius] * n + [radius * np.cos(p) for p in phis]
    frames = [(N[0], B[0])] * len(phis) + list(zip(N, B)) + [(N[-1], B[-1])] * len(phis)
    th = np.linspace(0.0, 2 * np.pi, sections, endpoint=False)
    cs, sn = np.cos(th)[:, None], np.sin(th)[:, None]
    rings = [np.asarray(c) + r * (cs * np.asarray(f[0]) + sn * np.asarray(f[1])) for c, r, f in zip(centres, radii, frames)]
    V = np.vstack(rings)
    F = []
    for i in range(len(rings) - 1):
        a, b = i * sections, (i + 1) * sections
        for j in range(sections):
            k = (j + 1) % sections
            F.append([a + j, b + j, b + k]); F.append([a + j, b + k, a + k])
    tip0 = len(V); tip1 = tip0 + 1
    V = np.vstack([V, P[0] - T[0] * radius, P[-1] + T[-1] * radius])
    last = (len(rings) - 1) * sections
    for j in range(sections):
        k = (j + 1) % sections
        F.append([tip0, k, j])
        F.append([tip1, last + j, last + k])
    m = trimesh.Trimesh(V, np.array(F), process=True)
    m.remove_unreferenced_vertices()
    m.fix_normals()
    return m


# ---------------------------------------------------------------- builders
def cord_levels() -> dict | None:
    """The measured PAM50 levels on our cord centreline, or None if atlas-pam50 has not run."""
    if not CORD_LEVELS_JSON.exists():
        return None
    d = json.loads(CORD_LEVELS_JSON.read_text())
    if "centreline" not in d or not d.get("spinalLevels"):
        return None
    return d


def centreline_frame(levels: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(arc, points, unit tangents) of the cord centreline shipped in cord_levels.json, in world mm."""
    c = levels["centreline"]
    s = np.asarray(c["arc"], float)
    P = np.asarray(c["points"], float)
    Tg = np.gradient(P, axis=0)
    Tg /= np.linalg.norm(Tg, axis=1)[:, None]
    return s, P, Tg


def cut_plane(frame: tuple[np.ndarray, np.ndarray, np.ndarray], arc: float) -> tuple[np.ndarray, np.ndarray]:
    """The point at arc length `arc` on the centreline and the unit tangent (caudal) there."""
    s, P, Tg = frame
    pt = np.array([np.interp(arc, s, P[:, k]) for k in range(3)])
    tan = np.array([np.interp(arc, s, Tg[:, k]) for k in range(3)])
    return pt, tan / np.linalg.norm(tan)


def boundary_arc(by: dict, above: str, below: str) -> float:
    """Arc length of the boundary between two consecutive PAM50 spinal levels (they abut within 0.5 mm)."""
    return 0.5 * (by[above]["arc_mm"][1] + by[below]["arc_mm"][0])


def slice_between(cord: trimesh.Trimesh, frame, arc_top: float | None, arc_bottom: float | None):
    """The part of the cord between two centreline arc lengths, cut normal to the local tangent and capped."""
    m = cord.copy()
    if arc_top is not None:
        pt, tan = cut_plane(frame, arc_top)
        m = m.slice_plane(pt, tan, cap=True)          # keep the caudal side
    if m is not None and len(m.faces) and arc_bottom is not None:
        pt, tan = cut_plane(frame, arc_bottom)
        m = m.slice_plane(pt, -tan, cap=True)         # keep the rostral side
    return m


def tidy(m: trimesh.Trimesh, faces: int = 6000) -> trimesh.Trimesh:
    m.update_faces(m.nondegenerate_faces()); m.remove_unreferenced_vertices()
    if len(m.faces) > faces:
        m = m.simplify_quadric_decimation(face_count=faces)
        m.update_faces(m.nondegenerate_faces()); m.remove_unreferenced_vertices()
    try:
        m.fix_normals()
    except Exception:  # noqa: BLE001
        pass
    return m


def cord_segments(T: np.ndarray, pc: dict | None = None) -> list[tuple[MeshSpec, trimesh.Trimesh, str]]:
    """The four cord blocks, the filum terminale and the two enlargement overlays.

    Preferred path: cut the corrected cord surface at the PAM50 spinal-level boundaries that atlas-pam50 landed
    on our own centreline, on planes normal to the local tangent.  If cord_levels.json is missing, fall back to
    the old horizontal cuts at the Z-Anatomy vertebral landmarks and say so.
    """
    levels = cord_levels()
    if levels is None:
        print("  [warn] no public/data/volumes/cord_levels.json: falling back to the Z-Anatomy vertebral "
              "landmarks for the cord segment blocks (run atlas-pam50 first for the measured PAM50 levels)")
        return cord_segments_by_vertebrae(T, pc)

    cord = trimesh.load(str(CORD_PLY), force="mesh", process=True)
    # map to corrected MNI mm *first*: the post-correction is not a plane-preserving map, so the cut planes
    # have to be applied after it if they are to be planes on the shipped geometry
    cord.vertices = apply(T, np.asarray(cord.vertices, float), pc)
    frame = centreline_frame(levels)
    by = {r["name"]: r for r in levels["spinalLevels"]}
    order = [r["name"] for r in sorted(levels["spinalLevels"], key=lambda r: r["arc_mm"][0])]
    arc_end = float(frame[0][-1])

    def arc_top_of(first: str) -> float | None:
        i = order.index(first)
        return None if i == 0 else boundary_arc(by, order[i - 1], first)

    def arc_bottom_of(last: str) -> float:
        i = order.index(last)
        return by[last]["arc_mm"][1] if i == len(order) - 1 else boundary_arc(by, last, order[i + 1])

    out = []
    for mid, name, first, last, colour, visible, note in CORD_BLOCKS:
        a0, a1 = arc_top_of(first), arc_bottom_of(last)
        m = slice_between(cord, frame, a0, a1)
        if m is None or not len(m.faces):
            print("  [empty]", mid); continue
        out.append((MeshSpec(id=mid, name=name, system="spinal-cord", subsystem="segments", side="midline",
                             colour=colour, visible=visible, structure_id=mid, budget="medium"),
                    tidy(m), f"{CORD_METHOD_PAM50}; this block {note} "
                             f"(arc {0.0 if a0 is None else a0:.1f}-{a1:.1f} mm along the centreline)"))

    # the filum terminale: whatever the cord surface still has below the caudal end of S5
    a0 = by[order[-1]]["arc_mm"][1]
    m = slice_between(cord, frame, a0, None)
    if m is not None and len(m.faces):
        mid, name, colour, note = FILUM
        out.append((MeshSpec(id=mid, name=name, system="spinal-cord", subsystem="segments", side="midline",
                             colour=colour, visible=False, structure_id=mid, budget="medium"),
                    tidy(m, 4000), f"{CORD_METHOD_PAM50}; this mesh is {note} "
                                   f"(arc {a0:.1f}-{arc_end:.1f} mm along the centreline)"))
    else:
        print("  [empty] filum-terminale: the cord surface stops at the S5 boundary")

    for mid, name, first, last, colour, sid, note in CORD_OVERLAYS:
        a0, a1 = by[first]["arc_mm"][0], by[last]["arc_mm"][1]
        m = slice_between(cord, frame, a0, a1)
        if m is None or not len(m.faces):
            print("  [empty]", mid); continue
        out.append((MeshSpec(id=mid, name=name, system="spinal-cord", subsystem="segments", side="midline",
                             colour=colour, visible=False, structure_id=sid, budget="medium"),
                    tidy(m), f"{CORD_METHOD_PAM50}; this overlay is {note} "
                             f"(arc {a0:.1f}-{a1:.1f} mm along the centreline)"))
    return out


def cord_segments_by_vertebrae(T: np.ndarray, pc: dict | None = None,
                               conus: tuple[float, str] | None = None) -> list[tuple[MeshSpec, trimesh.Trimesh, str]]:
    """Horizontal cuts at the Z-Anatomy vertebral landmarks: the pre-PAM50 fallback, and the public edition's cut.

    With `conus` given (the public edition), the sacral block stops at that level instead of running on to the
    caudal end of the surface, and everything below it is exported as the filum terminale.  Without it (the
    fallback) the sacral block keeps its old extent and there is no filum, exactly as before."""
    cord = trimesh.load(str(CORD_PLY), force="mesh", process=True)
    levels = list(CORD_LEVELS)
    if conus is not None:
        conus_z, conus_note = conus
        levels = [(mid, name, conus_z if mid == "spinal-segment-sacral" else zmin, zmax,
                   (f"ends at {conus_note}, i.e. at the tip of the conus medullaris; below it the cord surface "
                    "is exported as the filum terminale") if mid == "spinal-segment-sacral" else note, colour)
                  for mid, name, zmin, zmax, note, colour in levels]
        fid, fname, fcolour = FILUM_VERT
        levels.append((fid, fname, None, conus_z,
                       f"is the remainder of the cord surface below {conus_note}: the thread of pia and glial "
                       "tissue that the Z-Anatomy cord surface tapers into below the conus", fcolour))
    out = []
    for mid, name, zmin, zmax, note, colour in levels:
        m = cord.copy()
        if zmax is not None:
            m = m.slice_plane([0, 0, zmax], [0, 0, -1], cap=True)
        if zmin is not None:
            m = m.slice_plane([0, 0, zmin], [0, 0, 1], cap=True)
        if m is None or len(m.faces) == 0:
            print("  [empty]", mid); continue
        # cut in Z-Anatomy world metres (the CORD_LEVELS planes), then map with the affine + midline correction
        m.vertices = apply(T, np.asarray(m.vertices, float), pc)
        spec = MeshSpec(id=mid, name=name, system="spinal-cord", subsystem="segments", side="midline",
                        colour=colour, visible=False, structure_id=mid, budget="medium")
        out.append((spec, tidy(m), f"{CORD_METHOD}; this block {note}"))
    return out


def zanatomy_object_z(name: str) -> tuple[float, float]:
    """The z extent (Z-Anatomy world metres) of one exported Z-Anatomy object, from work/zanatomy/objects.json."""
    for o in json.loads(ZOBJECTS.read_text()):
        if o["name"].strip() == name:
            return float(o["bbox"][0][2]), float(o["bbox"][1][2])
    raise SystemExit(f"{ZOBJECTS} has no object named {name!r} (re-run the Z-Anatomy export)")


def conus_level() -> tuple[float, str]:
    """Where the public cord stops being cord: the middle of the Z-Anatomy L1-L2 intervertebral disc."""
    z0, z1 = zanatomy_object_z(CONUS_DISC)
    z = 0.5 * (z0 + z1)
    return z, (f'the middle of the Z-Anatomy "{CONUS_DISC}" (z {z0:.4f}-{z1:.4f} m, midpoint {z:.4f} m), the '
               "classical adult level of the tip of the conus medullaris")


def derived_nerves(T: np.ndarray, pc: dict | None = None) -> list[tuple[MeshSpec, trimesh.Trimesh, str]]:
    cfg = yaml.safe_load((CONFIG / "derived_nerves.yaml").read_text())
    out = []
    for e in cfg["nerves"]:
        for side, pts in e["sides"].items():
            mid = f"{e['id']}-{side}"
            P = apply(T, np.array(pts, float), pc)
            curve = catmull_rom(P, per_segment=14)
            m = tube(curve, e["radius_mm"], sections=16)
            if len(m.faces) > e.get("budget", 4000):
                m = m.simplify_quadric_decimation(face_count=e["budget"])
                m.update_faces(m.nondegenerate_faces()); m.remove_unreferenced_vertices()
                m.fix_normals()
            spec = MeshSpec(id=mid, name=f"{e['name']} ({'left' if side == 'l' else 'right'})", system=e["system"],
                            subsystem=e.get("subsystem"), side="left" if side == "l" else "right",
                            colour=e.get("colour"), structure_id=e.get("structureId"), budget="medium")
            out.append((spec, m, e["derived"]))
    return out


def fourth_ventricle_plexus() -> list[tuple[MeshSpec, trimesh.Trimesh, str]]:
    import nibabel as nib
    img = nib.load(str(ASEG))
    data = np.rint(np.asanyarray(img.dataobj)).astype(np.int32)
    aff = img.affine
    mask = data == FV_LABEL
    idx = np.argwhere(mask)
    world = idx @ aff[:3, :3].T + aff[:3, 3]
    # voxel step that moves the world point posteriorly (-y): the axis whose y-component dominates
    ax = int(np.argmax(np.abs(aff[1, :3])))
    step = -1 if aff[1, ax] > 0 else 1
    body = (world[:, 2] >= FV_OBEX_Z) & (world[:, 2] <= FV_AQUEDUCT_Z)
    split = 0.5 * (FV_OBEX_Z + FV_AQUEDUCT_Z)
    caudal = idx[body & (world[:, 2] <= split)]
    # roof = the posterior boundary of that band
    nb = caudal.copy(); nb[:, ax] += step
    roof = caudal[~mask[nb[:, 0], nb[:, 1], nb[:, 2]]]
    out = np.zeros_like(mask)
    out[roof[:, 0], roof[:, 1], roof[:, 2]] = True
    # lateral recesses -> foramina of Luschka: extend the widest voxels of the recess band sideways
    band = world[(world[:, 2] >= FV_RECESS_BAND[0]) & (world[:, 2] <= FV_RECESS_BAND[1])]
    inv = np.linalg.inv(aff)
    tips = []
    if len(band):
        for pick in (np.argmax(band[:, 0]), np.argmin(band[:, 0])):
            tips.append(band[int(pick)])
    for tip in tips:
        # laterally away from the midline and slightly forward, i.e. towards the cerebellopontine angle cistern
        d = np.array([1.0 if tip[0] >= 0 else -1.0, 0.40, -0.15])
        d = d / np.linalg.norm(d)
        for t in np.linspace(0.0, FV_RECESS_LEN, int(FV_RECESS_LEN * 4) + 1):
            c = tip + d * t
            cv = inv[:3, :3] @ c + inv[:3, 3]     # world mm -> voxel index
            r = int(np.ceil(FV_RECESS_R)) + 1
            i0 = np.maximum(np.round(cv).astype(int) - r, 0)
            i1 = np.minimum(np.round(cv).astype(int) + r + 1, np.array(mask.shape))
            gi = np.mgrid[i0[0]:i1[0], i0[1]:i1[1], i0[2]:i1[2]].reshape(3, -1).T
            if not len(gi):
                continue
            gw = gi @ aff[:3, :3].T + aff[:3, 3]
            sel = np.linalg.norm(gw - c, axis=1) <= FV_RECESS_R
            g = gi[sel]
            out[g[:, 0], g[:, 1], g[:, 2]] = True
    from scipy import ndimage
    out = ndimage.binary_dilation(out, ndimage.generate_binary_structure(3, 1), iterations=1)
    m = mesh_from_mask(out, aff, target_faces=6000, sigma=0.7, min_component_frac=0.02)
    if m is None:
        return []
    spec = MeshSpec(id="choroid-plexus-fourth-ventricle", name="Choroid plexus of the fourth ventricle",
                    system="ventricles-csf", subsystem="csf", side="midline", colour="#D08A8A",
                    structure_id="choroid-plexus", budget="small")
    method = ("posterior (roof) boundary voxels of the caudal half of the aseg fourth ventricle (label 15, "
              f"z {FV_OBEX_Z:.0f} to {split:.0f} mm), dilated 1 mm, with two {FV_RECESS_LEN:.0f} mm extensions "
              "along the lateral recesses towards the foramina of Luschka")
    return [(spec, m, method)]


# ---------------------------------------------------------------- public-edition cord blocks
# The measured cut (cord_segments) lands on PAM50 spinal-level boundaries, so those four blocks are derived
# files of a template that may not be redistributed and `atlas-manifest --public` drops them.  The vertebral
# fallback is Z-Anatomy geometry plus the classical cord-segment/vertebra rule and nothing else, so it is
# built a second time under `-vert` ids, tagged `edition: "public"`, and ships in the public edition alone.
CORD_VERT_SUFFIX = "-vert"


def cord_segments_public(T: np.ndarray, pc: dict | None = None) -> list[tuple[MeshSpec, trimesh.Trimesh, str]]:
    out = []
    for spec, mesh, method in cord_segments_by_vertebrae(T, pc, conus=conus_level()):
        pub = MeshSpec(**{**spec.__dict__, "id": spec.id + CORD_VERT_SUFFIX, "structure_id": spec.id,
                          "name": spec.name})
        out.append((pub, mesh, f"vertebral-landmark cut (Z-Anatomy geometry only): {method}"))
    return out


# ---------------------------------------------------------------- landmark-anchored brainstem nuclei
LANDMARKS = CONFIG / "brainstem_landmarks.yaml"
ANCHOR_SUFFIX = "-anchor"
ANCHOR_SOURCE = {"aseg": "mni_aseg", "massp": "massp", "hcp": "hcp1065_tracts", "zanatomy": "zanatomy"}
ANCHOR_FILE = {"aseg": ASEG,
               "massp": RAW / "massp" / "tpl-MNI152NLin2009cAsym_res-01_atlas-MASSP20_dseg.nii.gz",
               "hcp": RAW / "hcp1065_tracts" / "nifti"}
ZOBJS = ZW / "objs"          # the exported Z-Anatomy objects, in Z-Anatomy world metres
# a marker's own geometry is an ellipsoid in world mm, but its POSITION is read off the anchor dataset, so the
# record inherits that dataset's alignment
ANCHOR_ALIGNMENT = {"zanatomy": "registered-affine", "lc_metamask": "nlin6-identity"}
ANCHOR_GRID_MM = 0.5      # sub-grid the ellipsoid is voxelised on (the label volumes are 1 mm)
BRAINSTEM_LABEL = 16
_vol_cache: dict = {}
ANCHOR_IDS: list[str] = []


def _volume(path):
    import nibabel as nib
    key = str(path)
    if key not in _vol_cache:
        img = nib.as_closest_canonical(nib.load(key))
        _vol_cache[key] = (np.asanyarray(img.dataobj), img.affine)
    return _vol_cache[key]


def _sub(name: str, side: str) -> str:
    """`{S}` -> L/R, `{s}` -> l/r, `{side}` -> left/right, for a per-side anchor file name."""
    return (name.replace("{S}", "L" if side == "l" else "R").replace("{s}", side)
                .replace("{side}", "left" if side == "l" else "right"))


def source_dataset(source: dict) -> str:
    """The downloaded dataset an anchor's geometry comes from (for the record's `source` and the NOTICE)."""
    return source["dataset"] if source["kind"] == "mask" else ANCHOR_SOURCE[source["kind"]]


def anchor_points(source: dict, side: str) -> np.ndarray:
    """World-mm coordinates of every voxel of one anchor source."""
    kind = source["kind"]
    if kind in ("aseg", "massp"):
        data, aff = _volume(ANCHOR_FILE[kind])
        mask = np.isin(np.rint(data).astype(np.int32), source["labels"])
    elif kind == "hcp":
        name = source["file"].replace("{S}", "L" if side == "l" else "R")
        data, aff = _volume(ANCHOR_FILE["hcp"] / f"{name}.nii.gz")
        mask = np.asarray(data) >= source.get("threshold", 0.5)
    elif kind == "zanatomy":
        # an open Z-Anatomy object (work/zanatomy/objs/*.ply), mapped to corrected MNI mm through exactly the
        # same affine + post-correction as every other Z-Anatomy mesh in the atlas, so the anchor sits where
        # the shipped surface sits.  Its vertices, not its voxels, are the point set.
        T, pc = ztomni()
        m = trimesh.load(str(ZOBJS / f"{_sub(source['file'], side)}.ply"), force="mesh", process=True)
        return apply(T, np.asarray(m.vertices, float), pc)
    elif kind == "mask":
        # any other openly licensed probability/label volume under pipeline/raw, named by `dataset` so the
        # record can credit it (e.g. the Dahl locus coeruleus meta mask, dataset lc_metamask)
        data, aff = _volume(RAW / _sub(source["file"], side))
        mask = np.nan_to_num(np.asarray(data, float), nan=0.0) >= source.get("threshold", 0.5)
    else:
        raise SystemExit(f"brainstem_landmarks.yaml: unknown anchor source kind {kind!r}")
    idx = np.argwhere(mask)
    return idx @ aff[:3, :3].T + aff[:3, 3]


def _axis_value(col: np.ndarray, rule: str) -> float:
    if rule == "centroid":
        return float(col.mean())
    if rule == "min":
        return float(col.min())
    if rule == "max":
        return float(col.max())
    if rule.startswith("frac:"):
        f = float(rule.split(":", 1)[1])
        return float(col.min() + f * (col.max() - col.min()))
    if rule.startswith("mm:"):
        return float(rule.split(":", 1)[1])
    raise SystemExit(f"brainstem_landmarks.yaml: unknown axis rule {rule!r}")


def anchor_point(anchor: dict, side: str) -> tuple[np.ndarray, int]:
    P = anchor_points(anchor["source"], side)
    for k, ax in (("x", 0), ("y", 1), ("z", 2)):
        band = (anchor.get("within") or {}).get(k)
        if band:
            P = P[(P[:, ax] >= band[0]) & (P[:, ax] <= band[1])]
    if anchor.get("split_sides"):
        P = P[P[:, 0] < 0] if side == "l" else P[P[:, 0] >= 0]
    if not len(P):
        raise SystemExit("brainstem_landmarks.yaml: an anchor selected no voxels")
    at = anchor["at"]
    p = np.array([_axis_value(P[:, i], at[k]) for i, k in enumerate("xyz")])
    off = np.array(anchor.get("offset") or [0.0, 0.0, 0.0], float)
    if side == "l":
        off = off * np.array([-1.0, 1.0, 1.0])
    return p + off, len(P)


def semi_axes(volume_mm3: float, ratio) -> np.ndarray:
    """Semi-axes proportional to `ratio` whose ellipsoid has exactly `volume_mm3`."""
    r = np.asarray(ratio, float)
    return r * (3.0 * volume_mm3 / (4.0 * np.pi * float(r.prod()))) ** (1.0 / 3.0)


def brainstem_envelope() -> tuple[np.ndarray, np.ndarray]:
    """The aseg brainstem label dilated by 1 mm, and its affine. Every marker is clipped to it."""
    from scipy import ndimage
    data, aff = _volume(ASEG)
    mask = np.rint(data).astype(np.int32) == BRAINSTEM_LABEL
    return ndimage.binary_dilation(mask, ndimage.generate_binary_structure(3, 1), iterations=1), aff


def ellipsoid_mesh(centre: np.ndarray, axes: np.ndarray, target_faces: int):
    """An ellipsoid voxelised on a 0.5 mm sub-grid, clipped to the dilated brainstem, then meshed."""
    env, env_aff = brainstem_envelope()
    pad = 2.0
    lo = centre - axes - pad
    shape = np.ceil((2 * (axes + pad)) / ANCHOR_GRID_MM).astype(int) + 1
    aff = np.eye(4)
    aff[:3, :3] = np.diag([ANCHOR_GRID_MM] * 3)
    aff[:3, 3] = lo
    g = np.stack(np.meshgrid(*[np.arange(n) for n in shape], indexing="ij"), -1).reshape(-1, 3)
    w = g * ANCHOR_GRID_MM + lo
    inside = (((w - centre) / axes) ** 2).sum(1) <= 1.0
    inv = np.linalg.inv(env_aff)
    vi = np.rint(w @ inv[:3, :3].T + inv[:3, 3]).astype(int)
    ok = np.all((vi >= 0) & (vi < np.array(env.shape)), axis=1)
    keep = inside.copy()
    keep[~ok] = False
    keep[ok] &= env[vi[ok, 0], vi[ok, 1], vi[ok, 2]]
    mask = np.zeros(tuple(shape), bool)
    mask[g[keep, 0], g[keep, 1], g[keep, 2]] = True
    clipped = 1.0 - (keep.sum() / max(inside.sum(), 1))
    return mesh_from_mask(mask, aff, target_faces, sigma=0.6, min_component_frac=0.05), clipped


def landmark_nuclei() -> list[tuple[MeshSpec, trimesh.Trimesh, str]]:
    """Ellipsoids of published volume at textbook positions relative to open geometry (see the yaml)."""
    if not LANDMARKS.exists():
        print(f"  [skip] {LANDMARKS} is missing"); return []
    cfg = yaml.safe_load(LANDMARKS.read_text())
    out = []
    for n in cfg["nuclei"]:
        axes = semi_axes(float(n["volume_mm3"]), n["axes"])
        sides = [("m", "", "midline")] if n["side"] == "midline" else [("l", "-l", "left"), ("r", "-r", "right")]
        for side, sfx, side_name in sides:
            centre, npts = anchor_point(n["anchor"], side)
            mesh, clipped = ellipsoid_mesh(centre, axes, BUDGET["tiny"])
            if mesh is None:
                print(f"  [empty] {n['id']}{ANCHOR_SUFFIX}{sfx}"); continue
            # `<entry-id>-anchor[-l/-r]`, never `<entry-id>[-l/-r]`: the private edition already owns those ids
            # and scripts/check-public.ts rejects any text that holds one.
            mid = f"{n['id']}{ANCHOR_SUFFIX}{sfx}"
            spec = MeshSpec(id=mid, name=f"{n['name']}{'' if side == 'm' else f' ({side.upper()})'} (location marker)",
                            system="brainstem", subsystem=n.get("subsystem"), side=side_name,
                            colour=n.get("colour"), visible=False, budget="tiny", structure_id=n["id"])
            method = ("landmark-anchored: an ellipsoid of the published volume of this nucleus "
                      f"({n['volume_note']}), centred where a textbook puts it -- {n['topography']} -- "
                      f"relative to geometry this atlas holds openly, and clipped to the brainstem. "
                      f"It marks a location, not a boundary; the centre is at MNI "
                      f"({centre[0]:.1f}, {centre[1]:.1f}, {centre[2]:.1f}) mm with semi-axes "
                      f"{axes[0]:.1f} x {axes[1]:.1f} x {axes[2]:.1f} mm.")
            out.append((spec, mesh, method))
            print(f"  {mid:44s} centre ({centre[0]:6.1f},{centre[1]:6.1f},{centre[2]:6.1f}) "
                  f"axes {np.round(axes, 2).tolist()} V={n['volume_mm3']} mm3 "
                  f"surface {mesh.volume:6.1f} mm3, {clipped*100:4.1f}% clipped, anchor {npts} vox "
                  f"[{n['anchor']['source']['kind']}]")
    return out


def landmark_source(mesh_id: str) -> str:
    """Which downloaded dataset a landmark marker's geometry comes from (its anchor's own volume)."""
    cfg = yaml.safe_load(LANDMARKS.read_text()) if LANDMARKS.exists() else {"nuclei": []}
    for n in cfg["nuclei"]:
        base = f"{n['id']}{ANCHOR_SUFFIX}"
        if mesh_id in (base, base + "-l", base + "-r"):
            return source_dataset(n["anchor"]["source"])
    return "mni_aseg"


# ---------------------------------------------------------------- driver
def main(argv=None) -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--only"); a = ap.parse_args(argv)
    only = set(a.only.split(",")) if a.only else None
    global ANCHOR_IDS
    ANCHOR_IDS = [n["id"] for n in (yaml.safe_load(LANDMARKS.read_text())["nuclei"] if LANDMARKS.exists() else [])]
    T, pc = ztomni()
    from .atlas_meshes import record
    items: list[tuple[MeshSpec, trimesh.Trimesh, str]] = []
    items += cord_segments(T, pc)
    items += cord_segments_public(T, pc)
    items += derived_nerves(T, pc)
    items += fourth_ventricle_plexus()
    items += landmark_nuclei()
    meshes_json = WORK / "meshes.json"
    existing = {m["id"]: m for m in json.loads(meshes_json.read_text())} if meshes_json.exists() else {}
    n = 0
    for spec, m, method in items:
        if only and spec.id not in only and (spec.structure_id or "") not in only:
            continue
        path = MESHES / spec.system / f"{spec.id}.glb"
        nbytes, lod = export_with_lod(m, path, spec.id, LOD_FACES, LOD_MIN_FACES)
        anchored = spec.id.startswith(tuple(f"{n}{ANCHOR_SUFFIX}" for n in ANCHOR_IDS))
        if anchored:
            source = landmark_source(spec.id)
        elif spec.id.startswith("choroid-plexus-fourth"):
            source = "mni_aseg"
        else:
            source = "zanatomy"
        alignment = ANCHOR_ALIGNMENT.get(source, "native-mni")
        # public-only: the measured cord blocks and the private nuclei already fill these ids in the
        # private edition, so these records exist for `atlas-manifest --public` alone (see manifest.py)
        public = anchored or spec.id.endswith(CORD_VERT_SUFFIX)
        rec = record(spec, source, None, alignment, m, path, nbytes, 0,
                     {"labelVolume": None, "lod": lod, "derived": method,
                      **({"edition": "public"} if public else {})})
        existing[rec["id"]] = rec; n += 1
        print(f"  {spec.id:38s} {len(m.faces):6d} tris {nbytes/1024:7.1f} KB  bbox {np.round(m.bounds, 1).tolist()}")
    meshes_json.write_text(json.dumps(list(existing.values()), indent=1))
    print(f"updated {meshes_json} (+{n} derived meshes)")


if __name__ == "__main__":
    main()
