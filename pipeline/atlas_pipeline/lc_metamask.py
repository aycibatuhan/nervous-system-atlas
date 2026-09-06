"""Step 06e: the locus coeruleus of the PUBLIC edition, from the openly licensed Dahl et al. meta mask.

  atlas-lc-metamask            (or: python -m atlas_pipeline.lc_metamask)

WHY A SECOND LOCUS COERULEUS
----------------------------
The atlas already has an LC from the Brainstem Navigator, but that toolkit's licence forbids
redistributing derived files, so the public edition cannot ship it (see manifest.py). The two meshes
built here (`locus-coeruleus-meta-l/-r`) are the public stand-in: they carry `edition: "public"`, which means `atlas-manifest` drops
them from the private manifest and `atlas-manifest --public` keeps them. Neither edition ever shows two
locus coerulei, and both hang off the same content entry (structureId `locus-coeruleus`).

WHAT THE MASK IS
----------------
Dahl et al. (2022, Neurobiology of Aging 112:39-54) aggregated six previously published LC maps into a
single consensus volume of interest -- a "meta mask" -- and share it in OSF project sf2ky, whose project
licence is CC BY 4.0 (verified live against https://api.osf.io/v2/nodes/sf2ky/?embed=license, which
reports "CC-By Attribution 4.0 International"; the mask sits in that project's own osfstorage). It is a
*volume of interest* built for reliable LC sampling, not a delineation of the nucleus in one template,
and it is deliberately generous: 40.2 mm3 on the left and 33.8 mm3 on the right, against the roughly
10-25 mm3 per side that histology gives. The content entry's pitfall says exactly that.

Registration: the masks are 364x436x364 at 0.5 mm on the affine
[[-0.5,0,0,90],[0,0.5,0,-126],[0,0,0.5,-72]] -- the FSL MNI152 182x218x182 box at half the voxel size
(the reference brain the project ships beside them is FSL's avg152T1, and the project's transform folder
calls the space "MNI152 lin"). That is the same box every other FSL-space atlas in this pipeline sits on
(the arterial territories, the MRA and VENAT vessel atlases, the cerebellar atlas), so the masks are
taken as they are and tagged "nlin6-identity" like those. The residual FSL-MNI152-to-2009cAsym
difference in the dorsal pons is on the order of 1-2 mm; the pipeline has no antspyx and no
MNI152lin->2009c warp, and using the identity keeps the public LC in the same place as the private one,
which is tagged the same way.

Meshing: 0.5 mm voxels and a mask about 4 x 4.5 x 13 mm, i.e. a thin column 7-9 voxels across. The
default signed-distance smoothing (sigma 0.6 voxels, no upsampling below 0.75 mm) erodes such a column
by about 15% of its volume, so the mask is meshed on the finer rung of the same sub-voxel ladder
brainstem_nav.py uses for its smallest nuclei: 2x upsampling of the distance field with sigma 0.35. The
result spans >=99% of the mask bounding box. Nothing here reads Brainstem Navigator data.
"""
from __future__ import annotations

import argparse
import json

import numpy as np

from . import catalog
from .atlas_meshes import record
from .catalog import BUDGET, LOD_FACES, LOD_MIN_FACES
from .meshing import export_with_lod, mesh_from_mask
from .paths import MESHES, RAW, WORK
from .spaces import load_ras

SOURCE_ID = "lc_metamask"
ROOT_DIR = RAW / SOURCE_ID
FILES = {"left": "LCmetaMask_left_MNI05_s01f_plus50.nii.gz",
         "right": "LCmetaMask_right_MNI05_s01f_plus50.nii.gz"}
ALIGNMENT = "nlin6-identity"
EDITION = "public"
# the shipped masks are already binary uint8 0/1, so this is the mask's own binarisation, not a choice
THRESHOLD = 0.5
# (upsample, sigma) rungs, finest-preserving first; the first rung whose surface spans MIN_EXTENT_FRAC
# of the mask bounding box wins, and the widest-spanning rung is the fallback
SMOOTHING_LADDER = ((2, 0.35), (2, 0.15), (1, 0.6))
MIN_EXTENT_FRAC = 0.95

# NOTE: no `derived` field. That field means "no source atlas provides this shape, we constructed it",
# and the UI renders it as a schematic tag; this mask IS a source atlas, so the provenance travels the
# ordinary way -- source id, the citation in manifest.sources, and the pitfall in the content entry.


def _mask_diagonal_mm(mask: np.ndarray, affine: np.ndarray) -> float:
    idx = np.argwhere(mask)
    lo, hi = idx.min(0), idx.max(0) + 1          # +1: a single voxel still spans one voxel
    corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])], float)
    mm = corners @ affine[:3, :3].T + affine[:3, 3]
    return float(np.linalg.norm(mm.max(0) - mm.min(0)))


def mesh_thin(mask: np.ndarray, affine: np.ndarray, target_faces: int):
    """mesh_from_mask on the sub-voxel ladder. Returns (mesh|None, {"smoothing": ...} | {})."""
    want = MIN_EXTENT_FRAC * _mask_diagonal_mm(mask, affine)
    best, best_extra, best_span = None, {}, -1.0
    for up, sigma in SMOOTHING_LADDER:
        mesh = mesh_from_mask(mask, affine, target_faces, sigma=sigma, upsample=up, min_component_frac=0.05)
        if mesh is None or len(mesh.faces) < 40:
            continue
        span = float(np.linalg.norm(mesh.bounds[1] - mesh.bounds[0]))
        extra = {"smoothing": {"upsample": up, "sigma": sigma}}
        if span > best_span:
            best, best_extra, best_span = mesh, extra, span
        if span >= want:
            return mesh, extra
    return best, best_extra


def build(only: set[str] | None = None) -> list[dict]:
    specs = catalog.lc_metamask_entries()
    out: list[dict] = []
    for side, name in FILES.items():
        path_in = ROOT_DIR / name
        if not path_in.exists():
            print(f"  [skip] {name} not downloaded (atlas-download --with brainstem-open)")
            continue
        spec = specs["locus-coeruleus-meta" + ("-l" if side == "left" else "-r")]
        if only and spec.id not in only and spec.structure_id not in only and SOURCE_ID not in only:
            continue
        img = load_ras(path_in)
        data = np.asanyarray(img.dataobj).astype(np.float32)
        data = data[..., 0] if data.ndim == 4 else data
        mask = data >= THRESHOLD
        if not mask.any():
            print(f"  [skip] {spec.id}: empty mask")
            continue
        mesh, smoothing = mesh_thin(mask, img.affine, BUDGET[spec.budget])
        if mesh is None:
            print(f"  [skip] {spec.id}: no surface ({int(mask.sum())} voxels)")
            continue
        path = MESHES / spec.system / f"{spec.id}.glb"
        nbytes, lod = export_with_lod(mesh, path, spec.id, LOD_FACES, LOD_MIN_FACES)
        out.append(record(spec, SOURCE_ID, None, ALIGNMENT, mesh, path, nbytes, int(mask.sum()),
                          {"labelVolume": None, "lod": lod, "edition": EDITION, "sourceFile": name,
                           "threshold": THRESHOLD, **smoothing}))
        vol_mask = float(mask.sum()) * abs(np.linalg.det(img.affine[:3, :3]))
        print(f"  {spec.id:24s} {len(mesh.faces):5d} tris {nbytes/1024:6.1f} KB  "
              f"mask {int(mask.sum())} vox = {vol_mask:.1f} mm3, surface {mesh.volume:.1f} mm3, "
              f"centroid {np.round(mesh.vertices.mean(0), 1).tolist()}")
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", help="comma list of mesh ids / structure ids")
    a = ap.parse_args(argv)
    print("[lc_metamask]")
    results = build(set(a.only.split(",")) if a.only else None)
    if not results:
        print("  nothing built")
        return
    out_path = WORK / "meshes.json"
    existing = {m["id"]: m for m in json.loads(out_path.read_text())} if out_path.exists() else {}
    for r in results:
        existing[r["id"]] = r
    out_path.write_text(json.dumps(list(existing.values()), indent=1))
    print(f"lc meta mask: {len(results)} meshes (edition {EDITION}) -> {out_path}")


if __name__ == "__main__":
    main()
