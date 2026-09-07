"""Step 06f: brainstem arousal nuclei of the PUBLIC edition, from the Harvard Ascending Arousal Network atlas.

  atlas-aan [--only id1,id2] [--threshold 0.35]      (or: python -m atlas_pipeline.aan)

WHY
---
Most of the small brainstem nuclei in this atlas come from the Brainstem Navigator, whose licence forbids
redistributing derived files, so the public edition cannot ship them (see manifest.py).  The Harvard
Ascending Arousal Network (AAN) atlas is an openly licensed second delineation of a few of the same
nuclei: the meshes built here carry `edition: "public"`, which means `atlas-manifest` drops them from the
private manifest and `atlas-manifest --public` keeps them.  Neither edition ever shows the same nucleus
twice, and both hang off the same content entry (`structureId`).

WHAT THE ATLAS IS
-----------------
Edlow BL, Kinney HC et al., "Harvard Ascending Arousal Network Atlas - Version 2.0", Dryad
doi:10.5061/dryad.zw3r228d2.  The Dryad record reports `license:
https://spdx.org/licenses/CC0-1.0.html`, i.e. CC0 1.0 (verified live against
https://datadryad.org/api/v2/datasets/doi%3A10.5061%2Fdryad.zw3r228d2), so the ROIs may be redistributed
in derived form.  Version 2.0 ships 25 files: a whole-brainstem label volume with a FreeSurfer colour LUT,
a README, and per-node ROIs in FSL MNI152 1 mm space for

    DR    dorsal raphe                      MnR   median raphe
    LC    locus coeruleus (also _L, _R)     mRt   mesencephalic reticular formation (also _L, _R)
    LDTg  laterodorsal tegmental (_L, _R)   PAG   periaqueductal grey
    PBC   parabrachial complex (_L, _R)     PnO   pontis oralis / oral pontine reticular n. (_L, _R)
    PTg   pedunculotegmental n. (_L, _R)    VTA   ventral tegmental area

Only four of those are meshed here.  The rest already have an openly licensed mesh in the public edition:
the locus coeruleus has the Dahl meta mask (`atlas-lc-metamask`), and PAG, VTA, DR, MnR and PTg (which
this atlas renames from "pedunculopontine nucleus") all come from MASSP20, which is MNI-licensed and ships
in both editions.  Meshing them again would put two surfaces on one content entry.

    AAN node                                content entry                        mesh ids
    PBC   parabrachial complex              nucleus-parabrachial-lateral         ...-aan-l / -aan-r
    LDTg  laterodorsal tegmental n.         nucleus-laterodorsal-tegmental       ...-aan-l / -aan-r
    PnO   oral pontine reticular n.         reticular-formation-pontine          ...-aan-l / -aan-r
    mRt   mesencephalic reticular formation reticular-formation-mesencephalic    ...-aan-l / -aan-r

PBC is one node covering the whole parabrachial complex, so it is attached to the lateral parabrachial
entry (the larger of the pair); the medial parabrachial entry gets the landmark-anchored ellipsoid that
`atlas-derived` builds, and both entries' pitfalls say which surface they are looking at.

DOWNLOAD IS MANUAL, AND NOT BY CHOICE
-------------------------------------
Dryad no longer serves file bytes to a script: `/api/v2/files/<id>/download` answers 401 "Unauthorized,
must have current bearer token", and the browser path `/downloads/file_stream/<id>` sits behind an Anubis
proof-of-work anti-bot interstitial.  Neither is something this pipeline may work around.  So `aan_atlas`
is registered in sources.yaml as a manual source, with the Dryad download URLs and the sha256 digests
Dryad publishes for each file pre-seeded in sources.lock.yaml: fetch the eight lateralised ROIs from
https://datadryad.org/dataset/doi:10.5061/dryad.zw3r228d2 in a browser, drop them in
pipeline/raw/aan_atlas/, and `atlas-download --with brainstem-open` verifies every digest before this step
meshes them.  Until then this step prints what is missing and builds nothing.

REGISTRATION
------------
The v2.0 ROIs are named "MNI152_1mm" and are 182x218x182 on the FSL MNI152 box, the same grid the
arterial, MRA, VENAT and cerebellar atlases sit on, so they are taken as they are and tagged
"nlin6-identity" like those (the residual FSL-MNI152-to-2009cAsym difference in the brainstem is on the
order of 1-2 mm; the pipeline has no antspyx and no MNI152lin->2009c warp).  The grid is *checked* rather
than assumed: `alignment_for` reads the header, and a file that turns out to be on the 193x229x193
2009cAsym grid is tagged "native-mni" instead.

Meshing: 1 mm voxels and nuclei of 30-400 mm3, i.e. between about 3 and 9 voxels across, so the same
sub-voxel smoothing ladder lc_metamask.py uses for the thin LC column is used here, and the coarsest rung
is the pipeline default.  Nothing here reads Brainstem Navigator data.
"""
from __future__ import annotations

import argparse
import json

import numpy as np

from . import catalog
from .atlas_meshes import record
from .catalog import BUDGET, LOD_FACES, LOD_MIN_FACES
from .lc_metamask import mesh_thin
from .meshing import export_with_lod
from .paths import MESHES, RAW, WORK
from .spaces import GRID_AFFINE, GRID_SHAPE, load_ras

SOURCE_ID = "aan_atlas"
ROOT_DIR = RAW / SOURCE_ID
EDITION = "public"
DEFAULT_THRESHOLD = 0.35     # the same threshold the private 7 T probabilistic maps are meshed at
FILE_TEMPLATE = "AAN_{node}_{side}_MNI152_1mm_v2p0.nii"

# FSL MNI152 1 mm box (182x218x182): voxel (90,126,72) = world origin, x flipped in storage
FSL_SHAPE = (182, 218, 182)


def alignment_for(img) -> str:
    """"native-mni" when the file is already on our 2009cAsym grid, else "nlin6-identity" (the FSL box)."""
    shape = tuple(int(x) for x in img.shape[:3])
    if shape == GRID_SHAPE and np.allclose(img.affine, GRID_AFFINE, atol=1e-3):
        return "native-mni"
    return "nlin6-identity"


def build(only: set[str] | None = None, threshold: float = DEFAULT_THRESHOLD) -> list[dict]:
    specs = catalog.aan_entries()
    missing: list[str] = []
    out: list[dict] = []
    for mid, spec in specs.items():
        node = catalog.AAN_NODE_OF[mid]
        side = "L" if mid.endswith("-l") else "R"
        name = FILE_TEMPLATE.format(node=node, side=side)
        path_in = ROOT_DIR / name
        if not path_in.exists():
            missing.append(name)
            continue
        if only and spec.id not in only and (spec.structure_id or "") not in only and SOURCE_ID not in only:
            continue
        img = load_ras(path_in)
        data = np.asanyarray(img.dataobj).astype(np.float32)
        data = data[..., 0] if data.ndim == 4 else data
        hi = float(data.max()) if data.size else 0.0
        if hi > 1.0:                      # a 0-100 probability or a labelled ROI: scale to 0-1
            data = data / hi
        mask = data >= threshold
        if not mask.any():
            print(f"  [skip] {spec.id}: empty mask in {name}")
            continue
        alignment = alignment_for(img)
        mesh, smoothing = mesh_thin(mask, img.affine, BUDGET[spec.budget])
        if mesh is None:
            print(f"  [skip] {spec.id}: no surface ({int(mask.sum())} voxels)")
            continue
        path = MESHES / spec.system / f"{spec.id}.glb"
        nbytes, lod = export_with_lod(mesh, path, spec.id, LOD_FACES, LOD_MIN_FACES)
        out.append(record(spec, SOURCE_ID, None, alignment, mesh, path, nbytes, int(mask.sum()),
                          {"labelVolume": None, "lod": lod, "edition": EDITION, "sourceFile": name,
                           "threshold": threshold, "aanNode": node, **smoothing}))
        vol_mask = float(mask.sum()) * abs(np.linalg.det(img.affine[:3, :3]))
        print(f"  {spec.id:38s} {len(mesh.faces):5d} tris {nbytes/1024:6.1f} KB  "
              f"mask {int(mask.sum())} vox = {vol_mask:.1f} mm3, surface {mesh.volume:.1f} mm3, "
              f"centroid {np.round(mesh.vertices.mean(0), 1).tolist()}, {alignment}")
    if missing:
        print(f"  [skip] {len(missing)} AAN ROI(s) not downloaded: {', '.join(sorted(missing))}")
        print("         Dryad serves these only through a browser (the API needs a bearer token and the web "
              "download sits behind an anti-bot challenge):")
        print("         fetch them from https://datadryad.org/dataset/doi:10.5061/dryad.zw3r228d2 into "
              f"{ROOT_DIR}, then run `atlas-download --with brainstem-open` and this step again.")
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", help="comma list of mesh ids / structure ids")
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    a = ap.parse_args(argv)
    print("[aan]")
    results = build(set(a.only.split(",")) if a.only else None, a.threshold)
    if not results:
        print("  nothing built")
        return
    out_path = WORK / "meshes.json"
    existing = {m["id"]: m for m in json.loads(out_path.read_text())} if out_path.exists() else {}
    for r in results:
        existing[r["id"]] = r
    out_path.write_text(json.dumps(list(existing.values()), indent=1))
    print(f"AAN atlas: {len(results)} meshes (edition {EDITION}) -> {out_path}")


if __name__ == "__main__":
    main()
