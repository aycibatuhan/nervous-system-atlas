"""Phase 7: derived meshes -- structures that no source atlas ships, constructed from atlas geometry we do have.

  atlas-derived [--only id1,id2]

Every record written here carries a `derived` field with a one-line description of the construction, which the
manifest passes through, so the UI and the content entries can say plainly that the shape is schematic.

What is built
-------------
spinal-segment-cervical / -thoracic / -lumbar / -sacral
    The Z-Anatomy cord surface (pipeline/work/zanatomy/objs/spinal-white-columns.ply, world metres) cut by
    horizontal planes and capped.  The cut levels come from the Z-Anatomy vertebral bodies together with the
    classical cord-segment-to-vertebra relationship (cervical segments opposite C1-C7, thoracic opposite
    T1-T9/T10, lumbar opposite T10-T12, sacral and coccygeal opposite T12-L1, conus at the cord's own tip).
    Z-Anatomy models one spinal root and ganglion pair per intervertebral foramen from C2 to L2, i.e. it puts
    every cord segment opposite the same-numbered vertebra, so its roots cannot supply the boundaries; the
    vertebral-body landmarks are used instead.

phrenic-nerve-l/-r, lumbosacral-trunk-l/-r
    Polylines from pipeline/config/derived_nerves.yaml (each waypoint read off a named Z-Anatomy object),
    mapped to MNI mm, smoothed with a centripetal Catmull-Rom spline and swept into a round, round-capped tube.

choroid-plexus-fourth-ventricle
    The posterior (roof) boundary of the caudal half of the FreeSurfer aseg fourth ventricle (label 15),
    dilated 1 mm, with two short lateral extensions along the lateral recesses towards the foramina of Luschka.
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import trimesh
import yaml

from .catalog import LOD_FACES, LOD_MIN_FACES, MeshSpec
from .meshing import export_with_lod, mesh_from_mask
from .paths import CONFIG, MESHES, RAW, WORK

ZW = WORK / "zanatomy"
CORD_PLY = ZW / "objs" / "spinal-white-columns.ply"
ASEG = RAW / "mni_aseg" / "tpl-MNI152NLin2009cAsym_res-01_seg-aseg_dseg.nii.gz"

# ---------------------------------------------------------------- spinal cord segments
# Cut planes in Z-Anatomy world metres (+z up).  Vertebral landmarks are bboxes from work/zanatomy/objects.json.
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


def ztomni() -> np.ndarray:
    return np.array(json.loads((CONFIG / "zanatomy_to_mni.json").read_text())["matrix"])


def apply(T: np.ndarray, P: np.ndarray) -> np.ndarray:
    return np.asarray(P, float) @ T[:3, :3].T + T[:3, 3]


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
def cord_segments(T: np.ndarray) -> list[tuple[MeshSpec, trimesh.Trimesh, str]]:
    cord = trimesh.load(str(CORD_PLY), force="mesh", process=True)
    out = []
    for mid, name, zmin, zmax, note, colour in CORD_LEVELS:
        m = cord.copy()
        if zmax is not None:
            m = m.slice_plane([0, 0, zmax], [0, 0, -1], cap=True)
        if zmin is not None:
            m = m.slice_plane([0, 0, zmin], [0, 0, 1], cap=True)
        if m is None or len(m.faces) == 0:
            print("  [empty]", mid); continue
        m.apply_transform(T)
        m.update_faces(m.nondegenerate_faces()); m.remove_unreferenced_vertices()
        if len(m.faces) > 6000:
            m = m.simplify_quadric_decimation(face_count=6000)
            m.update_faces(m.nondegenerate_faces()); m.remove_unreferenced_vertices()
        try:
            m.fix_normals()
        except Exception:  # noqa: BLE001
            pass
        spec = MeshSpec(id=mid, name=name, system="spinal-cord", subsystem="segments", side="midline",
                        colour=colour, structure_id=mid, budget="medium")
        out.append((spec, m, f"{CORD_METHOD}; this block {note}"))
    return out


def derived_nerves(T: np.ndarray) -> list[tuple[MeshSpec, trimesh.Trimesh, str]]:
    cfg = yaml.safe_load((CONFIG / "derived_nerves.yaml").read_text())
    out = []
    for e in cfg["nerves"]:
        for side, pts in e["sides"].items():
            mid = f"{e['id']}-{side}"
            P = apply(T, np.array(pts, float))
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


# ---------------------------------------------------------------- driver
def main(argv=None) -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--only"); a = ap.parse_args(argv)
    only = set(a.only.split(",")) if a.only else None
    T = ztomni()
    from .atlas_meshes import record
    items: list[tuple[MeshSpec, trimesh.Trimesh, str]] = []
    items += cord_segments(T)
    items += derived_nerves(T)
    items += fourth_ventricle_plexus()
    meshes_json = WORK / "meshes.json"
    existing = {m["id"]: m for m in json.loads(meshes_json.read_text())} if meshes_json.exists() else {}
    n = 0
    for spec, m, method in items:
        if only and spec.id not in only and (spec.structure_id or "") not in only:
            continue
        path = MESHES / spec.system / f"{spec.id}.glb"
        nbytes, lod = export_with_lod(m, path, spec.id, LOD_FACES, LOD_MIN_FACES)
        source = "mni_aseg" if spec.id.startswith("choroid-plexus-fourth") else "zanatomy"
        alignment = "native-mni" if source == "mni_aseg" else "registered-affine"
        rec = record(spec, source, None, alignment, m, path, nbytes, 0,
                     {"labelVolume": None, "lod": lod, "derived": method})
        existing[rec["id"]] = rec; n += 1
        print(f"  {spec.id:38s} {len(m.faces):6d} tris {nbytes/1024:7.1f} KB  bbox {np.round(m.bounds, 1).tolist()}")
    meshes_json.write_text(json.dumps(list(existing.values()), indent=1))
    print(f"updated {meshes_json} (+{n} derived meshes)")


if __name__ == "__main__":
    main()
