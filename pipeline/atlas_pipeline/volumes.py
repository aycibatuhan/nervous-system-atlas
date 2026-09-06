"""Step 02: MRI volumes for the web (uint8, x-fastest, gzip) + volume.json."""
from __future__ import annotations

import gzip
import hashlib
import json

import numpy as np
import nibabel as nib

from .paths import RAW, VOLUMES, OUT
from .spaces import GRID_AFFINE, GRID_SHAPE, load_ras, robust_window, to_uint8

T1 = RAW / "mni_t1w" / "tpl-MNI152NLin2009cAsym_res-01_T1w.nii.gz"
T2 = RAW / "mni_t1w" / "tpl-MNI152NLin2009cAsym_res-01_T2w.nii.gz"
MASK = RAW / "mni_t1w" / "tpl-MNI152NLin2009cAsym_res-01_desc-brain_mask.nii.gz"


def write_u8(name: str, arr: np.ndarray) -> dict:
    """arr is (x, y, z) in RAS voxel order; write x-fastest bytes (Fortran order) gzipped."""
    raw = np.ascontiguousarray(arr.astype(np.uint8)).tobytes(order="F")
    path = VOLUMES / f"{name}.u8.bin"
    with gzip.open(path, "wb", compresslevel=6) as f:
        f.write(raw)
    return {"file": f"volumes/{path.name}", "dtype": "uint8", "shape": list(arr.shape),
            "bytes_raw": len(raw), "bytes_gz": path.stat().st_size, "sha256": hashlib.sha256(raw).hexdigest()}


def main(argv=None) -> None:
    mask_img = load_ras(MASK)
    mask = np.asanyarray(mask_img.dataobj) > 0
    assert mask.shape == GRID_SHAPE, mask.shape
    out = {"space": "MNI152NLin2009cAsym", "shape": list(GRID_SHAPE), "spacing": [1, 1, 1],
           "origin_ras": [-96, -132, -78], "affine_ras": GRID_AFFINE.tolist(), "contrasts": {}}
    for key, path in (("t1w", T1), ("t2w", T2)):
        img = load_ras(path)
        assert np.allclose(img.affine, GRID_AFFINE), img.affine
        data = np.asanyarray(img.dataobj).astype(np.float32)
        lo, hi = robust_window(data, mask)
        # keep some skull/scalp visible: window from 0 to the 99.5th brain percentile
        u8 = to_uint8(data, 0.0, hi)
        meta = write_u8(key, u8)
        meta.update({"window": 255, "level": 127, "source_window": [0.0, hi]})
        out["contrasts"][key] = meta
        if key == "t1w":
            prev = u8[::2, ::2, ::2]
            out["contrasts"]["t1w_preview"] = write_u8("t1w_preview", prev) | {"spacing": [2, 2, 2], "window": 255, "level": 127}
        print(key, "window", (0.0, round(hi, 1)), meta["bytes_gz"], "bytes gz")
    (VOLUMES / "volume.json").write_text(json.dumps(out, indent=1))
    print("wrote", VOLUMES / "volume.json")


if __name__ == "__main__":
    main()
