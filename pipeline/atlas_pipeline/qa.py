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
            # junction, every named brainstem level must sit on the MNI centreline, and nothing at or above
            # the upper anchor -- the mesencephalic-diencephalic junction, above the top of the Z-Anatomy
            # midbrain, so the whole midbrain is inside the corrected band -- may move at all.
            ap = rep.get("ap")
            if ap:
                cmj = ap.get("cmj_residual", {}).get("max_abs_mm")
                above = ap.get("above_anchor_max_abs_dy_mm")
                anchor = ap.get("anchor_zero_m")
                moved = ap.get("meshes_moved", [])
                levels = ap.get("per_level", [])
                gate = ap.get("per_level_gate_mm", 2.0)
                bad = [L for L in levels if abs(L["after_mm"]) > gate]
                midline["ap"] = {"cmj_residual_max_abs_mm": cmj, "above_anchor_max_abs_dy_mm": above,
                                 "anchor_zero_m": anchor, "full_dy_mm": ap["knots"][0][1],
                                 "midbrain_min_dy_mm": min((v for _, v in ap["knots"]), default=0.0),
                                 "per_level_gate_mm": gate, "per_level_n": len(levels),
                                 "per_level_max_abs_mm": ap.get("per_level_max_abs_mm"),
                                 "meshes_moved": len(moved),
                                 "max_mesh_abs_dy_mm": max((m.get("max_abs_dy_mm", m["max_dy_mm"])
                                                            for m in moved), default=0.0)}
                if cmj is None:
                    warnings.append("zanatomy AP ramp: no measured profile in the midline report")
                elif cmj > 1.5:
                    problems.append(f"zanatomy AP residual at the cervicomedullary junction {cmj} mm exceeds "
                                    f"the 1.5 mm gate")
                if above is None or above > 0.0:
                    problems.append(f"zanatomy AP ramp displaces geometry at or above the upper anchor "
                                    f"({above} mm; must be exactly 0)")
                if anchor is None or anchor < 1.6175:
                    problems.append(f"zanatomy AP upper anchor {anchor} m is not above the top of the "
                                    f"Z-Anatomy Midbrain object (1.6175 m): the midbrain would be left "
                                    f"outside the corrected band")
                if not levels:
                    warnings.append("zanatomy AP ramp: no per-level residual table in the midline report")
                for L in bad:
                    problems.append(f"zanatomy AP residual at the {L['level']} {L['after_mm']} mm exceeds "
                                    f"the {gate} mm per-level gate")
        else:
            warnings.append("no work/zanatomy/midline/report.json (run atlas-zanatomy-midline)")
    # BodyParts3D sub-cranial anteroposterior correction (atlas-register --post-correction).  Three things
    # are gated: that the split of the two vertebral arteries has not regressed to the shared whole-tree
    # union, that the ramp removed the sub-cranial offset, and the hard rule that it moved no cranial mesh.
    bp3d_ap = {}
    bt = CONFIG / "bp3d_to_mni.json"
    prep = WORK / "bp3d" / "post_correction.json"
    bp_meshes = {m["id"]: m for m in meshes if m["source"] == "bodyparts3d"}
    vl, vr = bp_meshes.get("artery-vertebral-l"), bp_meshes.get("artery-vertebral-r")
    if vl and vr:
        bl, br = np.array(vl["bbox"], float), np.array(vr["bbox"], float)
        bp3d_ap["vertebral_x_mm"] = {"left": [bl[0][0], bl[1][0]], "right": [br[0][0], br[1][0]]}
        if bl[1][0] > 2.0 or br[0][0] < -2.0:
            problems.append("artery-vertebral-l/r cross the midline: the concepts have gone back to the "
                            "shared `partof` whole-tree union (bp3d_selection.yaml needs `tree: isa`)")
        if np.allclose(bl, br, atol=1e-6):
            problems.append("artery-vertebral-l and artery-vertebral-r have identical bounds (duplicate mesh)")
    if any(m.get("postCorrectionMaxMm") for m in bp_meshes.values()):
        pc = json.loads(bt.read_text()).get("post_correction")
        if pc is None:
            problems.append("bp3d_to_mni.json: meshes carry a post-correction but the config has no "
                            "post_correction block (run atlas-register --post-correction)")
        elif pc.get("stale"):
            problems.append("bp3d_to_mni.json: post_correction is stale (run atlas-register --post-correction)")
    if prep.exists():
        rep = json.loads(prep.read_text())
        sub, gate = rep["subcranial"], rep["cranial_gate"]
        vbj, vbj0 = rep["vertebrobasilar_junction"]["after"], rep["vertebrobasilar_junction"]["before"]
        bp3d_ap |= {"before_max_abs_mm": sub["before_max_abs_mm"], "after_max_abs_mm": sub["after_max_abs_mm"],
                    "fit_rms_mm": rep["fit"]["rms_mm"], "meshes_moved": gate["meshes_moved"],
                    "worst_cranial_dy_mm": gate["worst_cranial"]["max_dy_mm"],
                    "vbj_to_basilar_mm": vbj.get("junction_to_basilar_mm"),
                    "vbj_to_mra_mm": vbj.get("distance_to_mra_mm")}
        if sub["after_max_abs_mm"] > 3.0:
            problems.append(f"bp3d sub-cranial AP residual {sub['after_max_abs_mm']} mm exceeds the 3 mm gate")
        if gate["worst_cranial"]["max_dy_mm"] > 1.0:
            problems.append(f"bp3d post-correction moves the cranial mesh {gate['worst_cranial']['id']} by "
                            f"{gate['worst_cranial']['max_dy_mm']} mm; no mesh entirely above MNI z = -70 may "
                            f"move by more than 1 mm")
        d = vbj.get("junction_to_basilar_mm")
        if d is not None and d > 6.0:
            problems.append(f"vertebrobasilar junction {d} mm from the basilar's inferior end (gate 6 mm): "
                            f"the vertebral arteries have come off the basilar")
        d = vbj.get("distance_to_mra_mm"); d0 = vbj0.get("distance_to_mra_mm")
        if d is not None:
            # 8 mm is the landmark maximum of the BodyParts3D affine itself; the correction is pinned to
            # zero at the junction so that the basilar does not move, and cannot improve on it there.
            if d > 8.0:
                problems.append(f"vertebrobasilar junction {d} mm from the MRA atlas midline vessel "
                                f"(gate 8 mm, the affine's own landmark maximum)")
            if d0 is not None and d > d0 + 0.5:
                problems.append(f"the post-correction moved the vertebrobasilar junction away from the MRA "
                                f"atlas ({d0} -> {d} mm)")
    elif any(m.get("postCorrectionMaxMm") for m in bp_meshes.values()):
        warnings.append("no work/bp3d/post_correction.json (run atlas-register --post-correction)")
    reg = {}
    for name in ("bp3d_to_mni.json", "zanatomy_to_mni.json"):
        p = CONFIG / name
        if p.exists():
            t = json.loads(p.read_text()); reg[name] = t.get("metrics", {})
            mean = t.get("metrics", {}).get("landmark_mean_mm")
            if mean is not None and mean > 4.0:
                problems.append(f"{name}: landmark mean residual {mean} mm exceeds the 4 mm gate")
    report = {"meshes": len(meshes), "bytes": total_bytes, "triangles": total_tris, "registration": reg,
              "zanatomyMidline": midline, "bp3dSubcranialAp": bp3d_ap, "cordVolume": cord, "ncSources": nc,
              "problems": problems, "warnings": warnings}
    (WORK.parent / "qa").mkdir(exist_ok=True)
    (WORK.parent / "qa" / "report.json").write_text(json.dumps(report, indent=1))
    print(f"QA: {len(meshes)} meshes, {total_bytes/1e6:.1f} MB, {total_tris/1e6:.2f} M triangles; registration {json.dumps(reg)}")
    if midline:
        print(f"  zanatomy sub-cranial midline: {midline['before_max_abs_mm']} mm -> {midline['after_max_abs_mm']} mm (gate 1.0)")
        a = midline.get("ap")
        if a:
            print(f"  zanatomy AP ramp: +{a['full_dy_mm']} mm at the CMJ, residual there {a['cmj_residual_max_abs_mm']} mm "
                  f"(gate 1.5); {a['midbrain_min_dy_mm']} mm at the intercollicular knot; "
                  f"{a['above_anchor_max_abs_dy_mm']} mm at/above the anchor {a['anchor_zero_m']} m (gate 0); "
                  f"per-level max {a['per_level_max_abs_mm']} mm over {a['per_level_n']} levels "
                  f"(gate {a['per_level_gate_mm']}); {a['meshes_moved']} meshes move, "
                  f"max {a['max_mesh_abs_dy_mm']} mm")
    if bp3d_ap.get("after_max_abs_mm") is not None:
        print(f"  bp3d sub-cranial AP ramp: offset {bp3d_ap['before_max_abs_mm']} mm -> "
              f"{bp3d_ap['after_max_abs_mm']} mm (gate 3.0), fit rms {bp3d_ap['fit_rms_mm']} mm; "
              f"{len(bp3d_ap['meshes_moved'])} meshes move, worst cranial {bp3d_ap['worst_cranial_dy_mm']} mm "
              f"(gate 1.0); vertebrobasilar junction {bp3d_ap['vbj_to_basilar_mm']} mm from the basilar "
              f"(gate 6.0), {bp3d_ap['vbj_to_mra_mm']} mm from the MRA atlas (gate 8.0)")
    if cord:
        print(f"  cord MRI: {'x'.join(map(str, cord['grid']))} at {cord['spacing']} mm, {cord['bytes_gz']/1e6:.2f} MB gz, "
              f"PAM50<->MNI residual {cord['mni_residual_rms_mm']} mm (gate 2.0)")
    for w in warnings: print("  warn:", w)
    for p_ in problems: print("  FAIL:", p_)
    print(f"non-commercial sources: {nc}")
    print("QA", "PASSED" if not problems else f"FAILED ({len(problems)} problems)")
    if problems:
        raise SystemExit(1)
