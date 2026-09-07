"""Phase 10c: compose the PUBLIC edition's cord MRI out of one or more openly licensed straightened templates.

  atlas-cord-public [--spacing 0.75] [--no-write] [--quiet]

Why a compose step
------------------
The public edition may not ship anything derived from PAM50, so its cord MRI is built here from data that may
be redistributed.  No single open dataset covers the whole cord well: the spine-generic average
(`atlas-spine-generic`, 10 subjects, 0.8 mm isotropic, manual disc + rootlet labels) stops at about T3, and the
Fudan whole-spine T2-TSE average (`atlas-fudan-spine`, 14 subjects, 0.62 x 0.62 x 3.3 mm sagittal) runs from
the foramen magnum to the sacrum but is anisotropic.  Each of those steps writes a *straightened template* into
pipeline/work/cord_public/ in the contract below; this step lays every template it finds along our own cord
centreline (pam50.cord_frame / pam50.tube_grid, the same curve the private edition uses), level-matches them to
the Z-Anatomy vertebral column, blends their overlap and writes the public cord volumes.

Template contract (pipeline/work/cord_public/<name>.npz + <name>.json)
----------------------------------------------------------------------
<name>.npz (np.savez_compressed), all in "template coordinates": arc length along the straightened cord in mm,
measured from the template's own C2/C3 intervertebral disc (arc 0), positive caudally; u = right, v = anterior.
  arc      float32 (N,)       arc of each row, increasing, uniform step (STEP = 0.5 mm)
  inplane  float32 (M,)       u and v sample positions, uniform, symmetric about 0, spanning +-16 mm (R_FADE)
  avg      float32 (N, M, M)  the averaged, normalised intensity; NaN wherever the template has no data.
                              Normalisation: the cord's own median -> 0.5 and the 95th percentile of the
                              surrounding CSF -> 1.0 (spine_generic.straighten does exactly this), so two
                              templates can be blended without re-windowing
  cord     float32 (N, M, M)  cord probability 0..1 (fraction of subjects whose cord covers the voxel); 0 or
                              NaN where unknown
  count    int16   (N,)       subjects contributing to each arc row (0 where avg is NaN)
<name>.json
  source           the sources.yaml id (spine_generic, lumbosacral_fudan)
  license          its licence id (must not be nc / no_redistribution)
  step_mm          0.5
  discs            {"C2-C3": 0.0, "C3-C4": 14.1, ...}: group-mean arc of every intervertebral disc the
                   template located, keyed exactly like the Z-Anatomy objects ("Intervertebral disc <key>"),
                   so the compose step can map template arc -> Z-Anatomy disc arc on our centreline
                   piecewise-linearly.  The C2-C3 entry is always 0.0
  subjects         list of subject ids
  spinal_levels    optional {"C2": [a0, a1], ...} measured spinal-level bands in template arc (rootlets)
  level_method     optional, free-form provenance of spinal_levels
  conus_tip_arc    optional, group-mean arc of the tip of the conus medullaris
  coverage         {"arc_mm": [lo, hi], "vertebral_levels": [first, last], "note": "..."} and anything else
                   worth carrying into cord_public.json (resolution, sequence, subject count)
  qa               optional per-template QA numbers (disc scatter before/after warp, ...)

Precedence when templates overlap: the isotropic spine-generic template wins where it has data, and the
blend into the next template happens over the last BLEND_MM of its coverage.

Outputs (public/data/volumes/), all tagged `edition: "public"` by atlas-manifest
-------------------------------------------------------------------------------
cord_t2_public.u8.bin, labels_spine_public.u8.bin, labels_spine_public.json, cord_public.json,
cord_levels_public.json -- the same files atlas-spine-generic used to write on its own.
"""
from __future__ import annotations

from .paths import WORK

TEMPLATE_DIR = WORK / "cord_public"
STEP = 0.5          # mm, arc and in-plane step of every template
BLEND_MM = 20.0     # mm over which one template hands over to the next


def main(argv=None) -> None:  # filled in by the compose implementation
    raise SystemExit("atlas-cord-public: not implemented yet")
