"""Step 09: QA gates over the generated data (mesh integrity, FOV, budgets, licences, registration metrics)."""
from __future__ import annotations

import json

import numpy as np

from .download import load_sources
from .paths import CONFIG, OUT, WORK

MNI_MIN, MNI_MAX = np.array([-96.0, -132.0, -78.0]), np.array([96.0, 96.0, 114.0])
MAX_BYTES = 1_500_000


def main(argv=None) -> None:
    meshes = json.loads((WORK / "meshes.json").read_text())
    cfg = load_sources()
    licences = cfg["licenses"]; sources = {s["id"]: s for s in cfg["sources"]}
    problems, warnings = [], []
    total_bytes = 0; total_tris = 0
    for m in meshes:
        total_bytes += m["bytes"]; total_tris += m["triangles"]
        b = np.array(m["bbox"], float); c = np.array(m["centroid"], float)
        if not np.all(np.isfinite(b)) or not np.all(np.isfinite(c)):
            problems.append(f"{m['id']}: non-finite bbox/centroid"); continue
        if not (np.all(c >= b[0] - 1e-6) and np.all(c <= b[1] + 1e-6)):
            problems.append(f"{m['id']}: centroid outside bbox")
        if m["triangles"] < 4:
            problems.append(f"{m['id']}: degenerate mesh ({m['triangles']} triangles)")
        if m["bytes"] > MAX_BYTES:
            warnings.append(f"{m['id']}: {m['bytes']/1e6:.2f} MB exceeds the per-mesh budget")
        outside = np.any(b[0] < MNI_MIN - 10) or np.any(b[1] > MNI_MAX + 10)
        if outside:
            (warnings if m["alignment"].startswith("registered") else problems).append(f"{m['id']}: extends beyond the MNI volume ({m['alignment']})")
        src = sources.get(m["source"])
        if src is None:
            problems.append(f"{m['id']}: unknown source '{m['source']}'")
        elif src["license"] not in licences:
            problems.append(f"{m['id']}: licence '{src['license']}' not described in sources.yaml")
        if not (OUT / m["file"]).exists():
            problems.append(f"{m['id']}: file missing {m['file']}")
    nc = sorted({m["source"] for m in meshes if licences.get(sources.get(m["source"], {}).get("license", ""), {}).get("nc")})
    # cord MRI (atlas-pam50): a second volume grid, not a mesh, so it needs its own licence/source check
    cord = {}
    cp = OUT / "volumes" / "cord.json"
    if cp.exists():
        c = json.loads(cp.read_text())
        lic = licences.get(c.get("license"), None)
        if lic is None:
            problems.append(f"cord.json: licence '{c.get('license')}' not described in sources.yaml")
        elif lic.get("no_redistribution"):
            warnings.append(f"cord volumes are {c['license']} (no redistribution): keep {sorted(c['contrasts'])} out of any shared build")
        if c.get("source") not in sources:
            problems.append(f"cord.json: unknown source '{c.get('source')}'")
        elif lic is not None and lic.get("nc"):
            nc = sorted(set(nc) | {c["source"]})
        for k, v in c.get("contrasts", {}).items():
            if not (OUT / v["file"]).exists():
                problems.append(f"cord volume {k}: file missing {v['file']}")
        cord = {"grid": c["shape"], "spacing": c["spacing"][0],
                "bytes_gz": sum(v.get("bytes_gz", 0) for v in c.get("contrasts", {}).values()),
                "mni_residual_rms_mm": round(c["reformat"]["mni_residual"]["dxy_rms"], 2)}
        if cord["mni_residual_rms_mm"] > 2.0:
            problems.append(f"cord.json: PAM50 <-> MNI residual {cord['mni_residual_rms_mm']} mm exceeds the 2 mm gate")
    # Z-Anatomy sub-cranial midline: the brain-only affine leaves an x-from-z shear below the skull base, removed
    # by the post-correction fitted by atlas-zanatomy-midline.  Gate on the residual it reports.
    midline = {}
    mrep = WORK / "zanatomy" / "midline" / "report.json"
    zt = CONFIG / "zanatomy_to_mni.json"
    if any(m["source"] == "zanatomy" for m in meshes):
        pc = json.loads(zt.read_text()).get("post_correction") if zt.exists() else None
        if pc is None:
            problems.append("zanatomy_to_mni.json: no post_correction (run atlas-zanatomy-midline)")
        elif pc.get("stale"):
            problems.append("zanatomy_to_mni.json: post_correction is stale (run atlas-zanatomy-midline)")
        if pc is not None and not pc.get("ap"):
            warnings.append("zanatomy_to_mni.json: post_correction has no `ap` block -- the Z-Anatomy cord is "
                            "~23 mm posterior to the MNI cord at the CMJ (run atlas-zanatomy-midline)")
        if mrep.exists():
            rep = json.loads(mrep.read_text())
            r = rep["residual_subcranial"]
            midline = {"before_max_abs_mm": r["before_max_abs_mm"], "after_max_abs_mm": r["after_max_abs_mm"]}
            if r["after_max_abs_mm"] > 1.0:
                problems.append(f"zanatomy sub-cranial midline residual {r['after_max_abs_mm']} mm exceeds the 1 mm gate")
            # anteroposterior ramp: the cord must be continuous with the MNI brainstem at the cervicomedullary
            # junction, and nothing at or above the upper (pontomesencephalic) anchor may move at all.
            ap = rep.get("ap")
            if ap:
                cmj = ap.get("cmj_residual", {}).get("max_abs_mm")
                above = ap.get("above_anchor_max_abs_dy_mm")
                moved = ap.get("meshes_moved", [])
                midline["ap"] = {"cmj_residual_max_abs_mm": cmj, "above_anchor_max_abs_dy_mm": above,
                                 "full_dy_mm": ap["knots"][0][1], "meshes_moved": len(moved),
                                 "max_mesh_dy_mm": max((m["max_dy_mm"] for m in moved), default=0.0)}
                if cmj is None:
                    warnings.append("zanatomy AP ramp: no measured profile in the midline report")
                elif cmj > 1.5:
                    problems.append(f"zanatomy AP residual at the cervicomedullary junction {cmj} mm exceeds "
                                    f"the 1.5 mm gate")
                if above is None or above > 0.0:
                    problems.append(f"zanatomy AP ramp displaces geometry at or above the upper anchor "
                                    f"({above} mm; must be exactly 0)")
        else:
            warnings.append("no work/zanatomy/midline/report.json (run atlas-zanatomy-midline)")
    reg = {}
    for name in ("bp3d_to_mni.json", "zanatomy_to_mni.json"):
        p = CONFIG / name
        if p.exists():
            t = json.loads(p.read_text()); reg[name] = t.get("metrics", {})
            mean = t.get("metrics", {}).get("landmark_mean_mm")
            if mean is not None and mean > 4.0:
                problems.append(f"{name}: landmark mean residual {mean} mm exceeds the 4 mm gate")
    report = {"meshes": len(meshes), "bytes": total_bytes, "triangles": total_tris, "registration": reg,
              "zanatomyMidline": midline, "cordVolume": cord, "ncSources": nc, "problems": problems, "warnings": warnings}
    (WORK.parent / "qa").mkdir(exist_ok=True)
    (WORK.parent / "qa" / "report.json").write_text(json.dumps(report, indent=1))
    print(f"QA: {len(meshes)} meshes, {total_bytes/1e6:.1f} MB, {total_tris/1e6:.2f} M triangles; registration {json.dumps(reg)}")
    if midline:
        print(f"  zanatomy sub-cranial midline: {midline['before_max_abs_mm']} mm -> {midline['after_max_abs_mm']} mm (gate 1.0)")
        a = midline.get("ap")
        if a:
            print(f"  zanatomy AP ramp: +{a['full_dy_mm']} mm at the CMJ, residual there {a['cmj_residual_max_abs_mm']} mm "
                  f"(gate 1.5); {a['above_anchor_max_abs_dy_mm']} mm above the anchor (gate 0); "
                  f"{a['meshes_moved']} meshes move, max {a['max_mesh_dy_mm']} mm")
    if cord:
        print(f"  cord MRI: {'x'.join(map(str, cord['grid']))} at {cord['spacing']} mm, {cord['bytes_gz']/1e6:.2f} MB gz, "
              f"PAM50<->MNI residual {cord['mni_residual_rms_mm']} mm (gate 2.0)")
    for w in warnings: print("  warn:", w)
    for p_ in problems: print("  FAIL:", p_)
    print(f"non-commercial sources: {nc}")
    print("QA", "PASSED" if not problems else f"FAILED ({len(problems)} problems)")
    if problems:
        raise SystemExit(1)
