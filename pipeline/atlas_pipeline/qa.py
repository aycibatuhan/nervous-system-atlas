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
    reg = {}
    for name in ("bp3d_to_mni.json", "zanatomy_to_mni.json"):
        p = CONFIG / name
        if p.exists():
            t = json.loads(p.read_text()); reg[name] = t.get("metrics", {})
            mean = t.get("metrics", {}).get("landmark_mean_mm")
            if mean is not None and mean > 4.0:
                problems.append(f"{name}: landmark mean residual {mean} mm exceeds the 4 mm gate")
    report = {"meshes": len(meshes), "bytes": total_bytes, "triangles": total_tris, "registration": reg, "ncSources": nc, "problems": problems, "warnings": warnings}
    (WORK.parent / "qa").mkdir(exist_ok=True)
    (WORK.parent / "qa" / "report.json").write_text(json.dumps(report, indent=1))
    print(f"QA: {len(meshes)} meshes, {total_bytes/1e6:.1f} MB, {total_tris/1e6:.2f} M triangles; registration {json.dumps(reg)}")
    for w in warnings: print("  warn:", w)
    for p_ in problems: print("  FAIL:", p_)
    print(f"non-commercial sources: {nc}")
    print("QA", "PASSED" if not problems else f"FAILED ({len(problems)} problems)")
    if problems:
        raise SystemExit(1)
