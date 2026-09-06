"""Step 06: meshes from MNI-space label/binary atlases (+ brain envelope, MRA arterial iso-surface)."""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy import ndimage

from . import catalog
from .catalog import BUDGET, LOD_FACES, LOD_MIN_FACES, MeshSpec
from .meshing import export_glb, export_with_lod, mesh_from_mask, mesh_stats, weld_group
from .paths import MESHES, RAW, WORK
from .spaces import arterial_atlas_affine, load_ras

MASK = RAW / "mni_t1w" / "tpl-MNI152NLin2009cAsym_res-01_desc-brain_mask.nii.gz"


def load_atlas(a: catalog.AtlasSpec) -> nib.Nifti1Image:
    path = RAW / a.file
    if a.fix == "arterial":
        img = nib.load(str(path))
        data = np.asanyarray(img.dataobj)
        data = data[..., 0] if data.ndim == 4 else data
        img = nib.Nifti1Image(data.astype(np.int16), arterial_atlas_affine(data.shape))
        return nib.as_closest_canonical(img)
    return load_ras(path)


RECORDS = WORK / "records"
# atlas ids that share one download/licence entry in sources.yaml
SOURCE_ALIAS = {"arterial_l1": "arterial_territories", "arterial_l2": "arterial_territories"}


def cached(out_id: str, path: Path, force: bool) -> dict | None:
    rp = RECORDS / f"{out_id}.json"
    if not force and rp.exists() and path.exists():
        return json.loads(rp.read_text())
    return None


def record(spec: MeshSpec, atlas_id: str, atlas_labels, alignment: str, mesh, path: Path, nbytes: int, voxels: int, extra=None) -> dict:
    st = mesh_stats(mesh)
    RECORDS.mkdir(parents=True, exist_ok=True)
    rec = _record(spec, atlas_id, atlas_labels, alignment, st, path, nbytes, voxels, extra)
    (RECORDS / f"{spec.id}.json").write_text(json.dumps(rec))
    return rec


def _record(spec, atlas_id, atlas_labels, alignment, st, path, nbytes, voxels, extra=None) -> dict:
    return {"id": spec.id, "structureId": spec.structure_id, "name": spec.name, "system": spec.system, "subsystem": spec.subsystem,
            "side": spec.side, "source": SOURCE_ALIAS.get(atlas_id, atlas_id), "alignment": alignment, "file": str(path.relative_to(MESHES.parent)).replace("\\", "/"),
            "bytes": nbytes, "colour": spec.colour, "opacity": spec.opacity, "visible": spec.visible,
            "atlasLabels": list(atlas_labels) if atlas_labels is not None else None, "voxels": int(voxels), **st, **(extra or {})}


def build_label_atlas(a: catalog.AtlasSpec, only: set[str] | None, force: bool = False) -> list[dict]:
    img = load_atlas(a)
    data = np.rint(np.asanyarray(img.dataobj)).astype(np.int32)
    aff = img.affine
    alignment = a.alignment or ("native-mni" if a.space == "mni2009" else "nlin6-identity")
    # x coordinate of every voxel (for side splitting of unlateralised atlases)
    xs = None
    by_id: dict[str, list[tuple[int, MeshSpec]]] = {}
    for lab, spec in a.entries.items():
        by_id.setdefault(spec.id, []).append((lab, spec))
    out = []
    built: list[tuple[MeshSpec, list[int], object, Path, int]] = []
    for mid, items in by_id.items():
        spec = items[0][1]
        labels = [lab for lab, _ in items]
        if only and spec.id not in only and spec.structure_id not in only and a.id not in only:
            continue
        sides = [(spec.side, spec.id)]
        if spec.side == "bilateral":   # split by hemisphere
            sides = [("left", spec.id + "-l"), ("right", spec.id + "-r")]
        mask_all = np.isin(data, labels)
        for side, out_id in sides:
            mask = mask_all
            if spec.side == "bilateral":
                if xs is None:
                    i = np.arange(data.shape[0]); xs = aff[0, 0] * i + aff[0, 3]
                sel = (xs < 0) if side == "left" else (xs >= 0)
                mask = mask & sel[:, None, None]
            path = MESHES / spec.system / f"{out_id}.glb"
            c = cached(out_id, path, force)
            if c:
                out.append(c); continue
            spec_side = MeshSpec(**{**spec.__dict__, "id": out_id, "side": side, "name": spec.name + (f" ({'L' if side == 'left' else 'R'})" if spec.side == "bilateral" else ""),
                                    "structure_id": spec.structure_id})
            mesh = mesh_from_mask(mask, aff, BUDGET[spec.budget], sigma=0.6 if abs(aff[0, 0]) >= 0.9 else 1.0)
            if mesh is None:
                print(f"  [skip] {out_id}: empty"); continue
            built.append((spec_side, labels, mesh, path, int(mask.sum())))
    # weld shared borders between the parcels of this atlas, then export
    if len(built) > 1 and a.label_volume in ("anat", "vascular", "vascular2"):
        n = weld_group([b[2] for b in built], tol_mm=0.35)
        print(f"  welded {n} border vertices across {len(built)} parcels")
    for spec_side, labels, mesh, path, voxels in built:
        mesh.fix_normals()
        nbytes, lod = export_with_lod(mesh, path, spec_side.id, LOD_FACES, LOD_MIN_FACES)
        out.append(record(spec_side, a.id, labels, alignment, mesh, path, nbytes, voxels,
                          {"labelVolume": a.label_volume, "lod": lod, **({"edition": a.edition} if a.edition else {})}))
        print(f"  {spec_side.id:48s} {len(mesh.faces):6d} tris {nbytes/1024:7.1f} KB" + (f"  (lod {lod['triangles']} tris)" if lod else ""))
    return out


def build_binary_atlas(a: catalog.AtlasSpec, only: set[str] | None, force: bool = False) -> list[dict]:
    out = []
    for rel, spec in a.files.items():
        if only and spec.id not in only and spec.structure_id not in only and a.id not in only:
            continue
        path = MESHES / spec.system / f"{spec.id}.glb"
        c = cached(spec.id, path, force)
        if c:
            out.append(c); continue
        img = load_ras(RAW / a.file / f"{rel}.nii.gz")
        data = np.asanyarray(img.dataobj)
        mask = data >= (a.threshold if a.threshold is not None else 0.5)
        mesh = mesh_from_mask(mask, img.affine, BUDGET[spec.budget], sigma=1.0, min_component_frac=0.05)
        if mesh is None:
            print(f"  [skip] {spec.id}: empty"); continue
        path = MESHES / spec.system / f"{spec.id}.glb"
        nbytes, lod = export_with_lod(mesh, path, spec.id, LOD_FACES, LOD_MIN_FACES)
        out.append(record(spec, a.id, None, "native-mni", mesh, path, nbytes, mask.sum(), {"labelVolume": "tract", "file_key": rel, "lod": lod}))
        print(f"  {spec.id:48s} {len(mesh.faces):6d} tris {nbytes/1024:7.1f} KB")
    return out


# ---------------------------------------------------------------- CerebrA (public-edition cortex)
# CerebrA is defined on the 2009c *symmetric* template. Its grid is identical to ours (193x229x193, 1 mm,
# origin -96/-132/-78), so the labels can simply be read as they are ("nlin2009csym-identity"); the anatomy
# underneath is the symmetric average, though, so a quick SyN of the symmetric T1w onto our asymmetric T1w
# and a genericLabel resampling of the labels ("warped-sym-to-asym") sits them a little better -- measured on
# this data: cortical Dice against DKT31-in-2009cAsym 0.587 -> 0.610, subcortical Dice against aseg
# 0.760 -> 0.770, region centroids 2.48 -> 2.24 mm, label voxels outside our brain mask 8147 -> 5499.
# antspyx is the pipeline's optional [warp] extra, so this is best-effort: the warped volume is cached in
# work/ and used when it is there, and the identity labels are the fallback. Each mesh record says which.
CEREBRA_WARPED = WORK / "cerebra_space-MNI152NLin2009cAsym_dseg.nii.gz"


def cerebra_warp() -> bool:
    """SyN the 2009cSym T1w onto our 2009cAsym T1w and carry the CerebrA labels over. False without antspyx."""
    try:
        import ants  # noqa: PLC0415
    except ImportError:
        return False
    fixed = ants.image_read(str(RAW / "mni_t1w" / "tpl-MNI152NLin2009cAsym_res-01_T1w.nii.gz"))
    moving = ants.image_read(str(RAW / "cerebra" / "tpl-MNI152NLin2009cSym_res-1_T1w.nii.gz"))
    reg = ants.registration(fixed=fixed, moving=moving, type_of_transform="SyN")
    lab = ants.image_read(str(RAW / catalog.CEREBRA_FILE))
    out = ants.apply_transforms(fixed=fixed, moving=lab, transformlist=reg["fwdtransforms"], interpolator="genericLabel")
    CEREBRA_WARPED.parent.mkdir(parents=True, exist_ok=True)
    ants.image_write(out, str(CEREBRA_WARPED))
    return True


def cerebra_spec() -> catalog.AtlasSpec | None:
    """None when the CerebrA download is missing (`atlas-download --with public-parcellations`)."""
    if not (RAW / catalog.CEREBRA_FILE).exists():
        return None
    if not CEREBRA_WARPED.exists() and not cerebra_warp():
        print("  [cerebra] antspyx not installed (pipeline[warp]) -- using the symmetric labels as they are")
        return catalog.cerebra_atlas()
    # load_atlas() joins the spec path onto RAW; an absolute path wins that join, which is what we want here
    # because the warped copy is a build product and lives in work/, not in raw/.
    return catalog.cerebra_atlas(str(CEREBRA_WARPED), alignment="warped-sym-to-asym")


def build_envelope() -> dict:
    img = load_ras(MASK)
    mask = np.asanyarray(img.dataobj) > 0
    mask = ndimage.binary_closing(mask, iterations=2)
    spec = catalog.ENVELOPE
    mesh = mesh_from_mask(mask, img.affine, BUDGET[spec.budget], sigma=1.0, taubin_iterations=30)
    path = MESHES / spec.system / f"{spec.id}.glb"
    nbytes, lod = export_with_lod(mesh, path, spec.id, 6000, LOD_MIN_FACES)
    print(f"  {spec.id:48s} {len(mesh.faces):6d} tris {nbytes/1024:7.1f} KB")
    return record(spec, "mni_t1w", None, "native-mni", mesh, path, nbytes, mask.sum(), {"lod": lod})


def build_mra(threshold: float) -> dict | None:
    p = RAW / "mouches_arteries" / "vesselProbabilities.nii.gz"
    if not p.exists():
        print("  [skip] MRA atlas not downloaded"); return None
    img = load_ras(p)
    prob = np.asanyarray(img.dataobj)
    mask_img = load_ras(MASK)
    # brain mask resampled to the 0.5 mm MRA grid, dilated ~8 mm
    from nibabel.processing import resample_from_to
    bm = resample_from_to(mask_img, (prob.shape, img.affine), order=0)
    bmask = ndimage.binary_dilation(np.asanyarray(bm.dataobj) > 0, iterations=16)
    mask = (prob >= threshold) & bmask
    print(f"  MRA voxels >= {threshold}: {mask.sum()} ({mask.sum() * 0.125 / 1000:.1f} mL)")
    spec = catalog.ARTERIES_MRA
    mesh = mesh_from_mask(mask, img.affine, BUDGET[spec.budget], sigma=0.7, min_component_frac=0.01, taubin_iterations=10)
    path = MESHES / spec.system / f"{spec.id}.glb"
    nbytes, lod = export_with_lod(mesh, path, spec.id, 8000, LOD_MIN_FACES)
    print(f"  {spec.id:48s} {len(mesh.faces):6d} tris {nbytes/1024:7.1f} KB")
    return record(spec, "mouches_arteries", None, "nlin6-identity", mesh, path, nbytes, mask.sum(), {"threshold": threshold, "lod": lod})


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma list of atlas ids / mesh ids to (re)build")
    ap.add_argument("--mra-threshold", type=float, default=30.0)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    only = set(a.only.split(",")) if a.only else None
    out_path = WORK / "meshes.json"
    existing = {m["id"]: m for m in json.loads(out_path.read_text())} if out_path.exists() else {}
    results: list[dict] = []
    for atlas in catalog.atlases():
        if only and not (atlas.id in only or any(s.id in only or s.structure_id in only for s in list(atlas.entries.values()) + list(atlas.files.values()))):
            continue
        print(f"[{atlas.id}]")
        results += build_label_atlas(atlas, only, a.force) if atlas.kind == "labels" else build_binary_atlas(atlas, only, a.force)
        for r in results:
            existing[r["id"]] = r
        out_path.write_text(json.dumps(list(existing.values()), indent=1))
    ce = cerebra_spec()
    if ce is None:
        print("[cerebra] skipped: run `atlas-download --with public-parcellations` for the public-edition cortex")
    elif not only or ce.id in only or any(s.id in only or s.structure_id in only for s in ce.entries.values()):
        print(f"[{ce.id}]")
        results += build_label_atlas(ce, only, a.force)
        for r in results:
            existing[r["id"]] = r
        out_path.write_text(json.dumps(list(existing.values()), indent=1))
    if not only or "envelope" in only:
        print("[envelope]"); results.append(build_envelope())
    if not only or "mra" in only:
        print("[mra]")
        r = build_mra(a.mra_threshold)
        if r: results.append(r)
    for r in results:
        existing[r["id"]] = r
    out_path.write_text(json.dumps(list(existing.values()), indent=1))
    total = sum(m["bytes"] for m in existing.values())
    print(f"meshes: {len(existing)}  total {total/1e6:.1f} MB  -> {out_path}")


if __name__ == "__main__":
    main()
