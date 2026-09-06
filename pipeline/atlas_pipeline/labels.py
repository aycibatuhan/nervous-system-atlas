"""Step 07: composite label volumes on the 1 mm MNI grid + labels.json lookup."""
from __future__ import annotations

import gzip
import json

import numpy as np
from nibabel.processing import resample_from_to

from . import catalog
from .atlas_meshes import load_atlas
from .paths import RAW, VOLUMES, WORK
from .spaces import GRID_AFFINE, GRID_SHAPE, load_ras


def write_gz(name: str, arr: np.ndarray) -> dict:
    raw = np.ascontiguousarray(arr).tobytes(order="F")
    path = VOLUMES / name
    with gzip.open(path, "wb", compresslevel=6) as f:
        f.write(raw)
    return {"file": f"volumes/{name}", "dtype": str(arr.dtype), "shape": list(arr.shape), "bytes_raw": len(raw), "bytes_gz": path.stat().st_size}


def main(argv=None) -> None:
    meshes = {m["id"]: m for m in json.loads((WORK / "meshes.json").read_text())}
    anat = np.zeros(GRID_SHAPE, np.uint16)
    tract = np.zeros(GRID_SHAPE, np.uint8)
    vasc1 = np.zeros(GRID_SHAPE, np.uint8)
    vasc2 = np.zeros(GRID_SHAPE, np.uint8)
    lut = {"anat": {}, "tract": {}, "vascular": {}, "vascular2": {}}
    by_mesh: dict[str, dict[str, list[int]]] = {}
    next_anat = 1
    next_tract = 1
    xs = GRID_AFFINE[0, 0] * np.arange(GRID_SHAPE[0]) + GRID_AFFINE[0, 3]

    def entry(m: dict) -> dict:
        return {"meshId": m["id"], "structureId": m["structureId"], "name": m["name"], "colour": m["colour"], "system": m["system"]}

    for a in sorted(catalog.atlases(), key=lambda a: a.priority):
        if a.kind == "labels":
            img = load_atlas(a)
            if not (img.shape == GRID_SHAPE and np.allclose(img.affine, GRID_AFFINE)):
                img = resample_from_to(img, (GRID_SHAPE, GRID_AFFINE), order=0)
            data = np.rint(np.asanyarray(img.dataobj)).astype(np.int32)
            if a.label_volume in ("vascular", "vascular2"):
                target = vasc1 if a.label_volume == "vascular" else vasc2
                for lab, spec in a.entries.items():
                    m = meshes.get(spec.id)
                    if not m:
                        continue
                    target[data == lab] = lab
                    lut[a.label_volume][str(lab)] = entry(m)
                    by_mesh.setdefault(spec.id, {}).setdefault(a.label_volume, []).append(int(lab))
                continue
            by_id: dict[str, list[int]] = {}
            for lab, spec in a.entries.items():
                by_id.setdefault(spec.id, []).append(lab)
            for mid, labs in by_id.items():
                spec = a.entries[labs[0]]
                mask_all = np.isin(data, labs)
                sides = [(None, mid)] if spec.side != "bilateral" else [("left", mid + "-l"), ("right", mid + "-r")]
                for side, out_id in sides:
                    m = meshes.get(out_id)
                    if not m:
                        continue
                    mask = mask_all if side is None else mask_all & ((xs < 0) if side == "left" else (xs >= 0))[:, None, None]
                    gid = next_anat; next_anat += 1
                    anat[mask] = gid
                    lut["anat"][str(gid)] = entry(m) | {"atlas": a.id, "atlasLabels": labs}
                    by_mesh.setdefault(out_id, {}).setdefault("anat", []).append(gid)
        else:  # binary tract files
            for rel, spec in a.files.items():
                m = meshes.get(spec.id)
                if not m:
                    continue
                img = load_ras(RAW / a.file / f"{rel}.nii.gz")
                img = resample_from_to(img, (GRID_SHAPE, GRID_AFFINE), order=0)
                mask = np.asanyarray(img.dataobj) >= 0.5
                gid = next_tract; next_tract += 1
                tract[mask] = gid
                lut["tract"][str(gid)] = entry(m) | {"atlas": a.id, "file": rel}
                by_mesh.setdefault(spec.id, {}).setdefault("tract", []).append(gid)
        print(f"painted {a.id}: anat ids so far {next_anat - 1}, tract ids {next_tract - 1}")
    vols = {"labels_anat": write_gz("labels_anat.u16.bin", anat), "labels_tract": write_gz("labels_tract.u8.bin", tract),
            "labels_vascular": write_gz("labels_vascular.u8.bin", vasc1), "labels_vascular2": write_gz("labels_vascular2.u8.bin", vasc2)}
    (VOLUMES / "labels.json").write_text(json.dumps({"volumes": vols, "lut": lut, "byMesh": by_mesh}, indent=1))
    for k, v in vols.items():
        print(k, v["bytes_gz"], "bytes gz")
    print("wrote labels.json")


if __name__ == "__main__":
    main()
