"""Coordinate spaces, grids and NIfTI helpers.

World frame everywhere = MNI152NLin2009cAsym RAS millimetres. The web app uses the same frame (camera up = +Z).
"""
from __future__ import annotations

import numpy as np
import nibabel as nib
from nibabel.processing import resample_from_to

# res-01 grid of tpl-MNI152NLin2009cAsym
GRID_SHAPE = (193, 229, 193)
GRID_AFFINE = np.array([[1.0, 0, 0, -96.0], [0, 1.0, 0, -132.0], [0, 0, 1.0, -78.0], [0, 0, 0, 1.0]])
MNI_FOV = ((-96.0, -132.0, -78.0), (96.0, 96.0, 114.0))


def load_ras(path, fix_affine: np.ndarray | None = None, dtype=None) -> nib.Nifti1Image:
    """Load a NIfTI and reorient it to RAS voxel order. `fix_affine` replaces a broken header affine first."""
    img = nib.load(str(path))
    if fix_affine is not None:
        img = nib.Nifti1Image(np.asanyarray(img.dataobj), fix_affine, img.header)
    img = nib.as_closest_canonical(img)
    if dtype is not None:
        img = nib.Nifti1Image(np.asanyarray(img.dataobj).astype(dtype), img.affine, img.header)
    return img


def arterial_atlas_affine(shape) -> np.ndarray:
    """The Liu 2023 arterial atlas ships with a zero translation; this is the FSL MNI152 (NLin6) box affine
    for the 182x218x182 (and 181x217x181) grids: voxel (90,126,72) = world origin, x flipped (LAS storage)."""
    return np.array([[-1.0, 0, 0, 90.0], [0, 1.0, 0, -126.0], [0, 0, 1.0, -72.0], [0, 0, 0, 1.0]])


def to_grid(img: nib.Nifti1Image, order: int = 0) -> nib.Nifti1Image:
    """Resample onto the atlas 1 mm grid (nearest neighbour for labels, order=1 for intensities)."""
    return resample_from_to(img, (GRID_SHAPE, GRID_AFFINE), order=order, mode="constant", cval=0)


def voxel_to_ras(affine: np.ndarray, ijk: np.ndarray) -> np.ndarray:
    ijk = np.asarray(ijk, dtype=float)
    return ijk @ affine[:3, :3].T + affine[:3, 3]


def robust_window(data: np.ndarray, mask: np.ndarray | None = None, lo_p=0.5, hi_p=99.5) -> tuple[float, float]:
    vals = data[mask > 0] if mask is not None else data[data > 0]
    lo, hi = np.percentile(vals, [lo_p, hi_p])
    return float(lo), float(hi)


def to_uint8(data: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return np.clip((data - lo) / max(hi - lo, 1e-6) * 255.0, 0, 255).astype(np.uint8)
