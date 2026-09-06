"""Step 08: public/data/manifest.json."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import yaml

from . import catalog
from .download import load_sources, load_lock
from .paths import CONFIG, OUT, VOLUMES, WORK


def main(argv=None) -> None:
    meshes = json.loads((WORK / "meshes.json").read_text())
    labels = json.loads((VOLUMES / "labels.json").read_text())
    volume = json.loads((VOLUMES / "volume.json").read_text())
    cfg = load_sources()
    lock = load_lock()
    by_mesh = labels["byMesh"]
    transforms = {}
    p = CONFIG / "bp3d_to_mni.json"
    if p.exists():
        t = json.loads(p.read_text()); transforms["bp3d_to_mni"] = {k: t[k] for k in ("method", "matrix", "metrics") if k in t}
    order = {s[0]: i for i, s in enumerate(catalog.SYSTEMS)}
    out_meshes = []
    for m in sorted(meshes, key=lambda m: (order.get(m["system"], 99), m["subsystem"] or "", m["name"])):
        lic = cfg["sources"] and next((s["license"] for s in cfg["sources"] if s["id"] == m["source"]), "MNI")
        out_meshes.append({
            "id": m["id"], "structureId": m["structureId"], "name": m["name"], "system": m["system"], "subsystem": m["subsystem"],
            "side": m["side"], "source": m["source"], "license": lic, "nc": bool(cfg["licenses"][lic].get("nc", False)),
            "alignment": m["alignment"], "file": m["file"], "bytes": m["bytes"], "triangles": m["triangles"], "compression": "meshopt",
            "colour": m["colour"], "opacity": m["opacity"], "visible": m["visible"], "bbox": m["bbox"], "centroid": m["centroid"],
            "labels": by_mesh.get(m["id"], {}), "ontology": {k: v for k, v in (("atlasLabels", m.get("atlasLabels")),) if v},
        })
    manifest = {
        "schema": 1, "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "space": "MNI152NLin2009cAsym",
        "grid": {"shape": volume["shape"], "spacing": volume["spacing"], "origin_ras": volume["origin_ras"], "affine_ras": volume["affine_ras"]},
        "volumes": {**volume["contrasts"], **{k: {**v, "lut": "volumes/labels.json"} for k, v in labels["volumes"].items()}},
        "transforms": transforms,
        "systems": [{"id": s[0], "name": s[1], "colour": s[2], "defaultVisible": s[3]} for s in catalog.SYSTEMS],
        "licenses": {k: {"name": v["name"], "url": v["url"], "attribution": v.get("attribution", ""), "nc": bool(v.get("nc", False)),
                         "text": f"licenses/{k}.txt"} for k, v in cfg["licenses"].items()},
        "sources": {s["id"]: {"license": s["license"], "citation": s["citation"],
                              "files": {f: lock.get(f"{s['id']}/{f}", {}).get("sha256") for f in [d.get("dest") or d["url"].rsplit("/", 1)[-1] for d in s["files"]]}}
                    for s in cfg["sources"] if any(m["source"] == s["id"] for m in meshes) or s["id"] == "mni_t1w"},
        "meshes": out_meshes,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1))
    total = sum(m["bytes"] for m in out_meshes)
    print(f"manifest: {len(out_meshes)} meshes, {total/1e6:.1f} MB meshes, systems {len(manifest['systems'])} -> {OUT / 'manifest.json'}")


if __name__ == "__main__":
    main()
