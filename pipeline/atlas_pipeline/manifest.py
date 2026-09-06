"""Step 08: public/data/manifest.json."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import yaml

from . import catalog
from .download import load_sources, load_lock
from .paths import CONFIG, OUT, VOLUMES, WORK


def palette() -> dict[str, dict]:
    """mesh id -> {colour, opacity} from the current catalogue and selection files, so colour edits never need a re-mesh."""
    look: dict[str, dict] = {}

    def put(mid, colour, opacity, structure_id=None):
        if colour:
            look[mid] = {"colour": colour, "opacity": opacity, **({"structureId": structure_id} if structure_id else {})}
    for a in catalog.atlases():
        for spec in list(a.entries.values()) + list(a.files.values()):
            put(spec.id, spec.colour, spec.opacity, spec.structure_id)
            if spec.side == "bilateral":
                put(spec.id + "-l", spec.colour, spec.opacity); put(spec.id + "-r", spec.colour, spec.opacity)
    for spec in (catalog.ENVELOPE, catalog.ARTERIES_MRA):
        put(spec.id, spec.colour, spec.opacity)
    for e in yaml.safe_load((CONFIG / "bp3d_selection.yaml").read_text())["meshes"]:
        put(e["id"], e.get("colour") or catalog.jitter(catalog.SYSTEM_COLOUR[e["system"]], e.get("structureId") or e["id"]), e.get("opacity", 1.0))
    for e in yaml.safe_load((CONFIG / "zanatomy_selection.yaml").read_text())["entries"]:
        col = e.get("colour") or catalog.jitter(catalog.SYSTEM_COLOUR[e["system"]], e.get("structureId") or e["id"])
        for mid in (e["id"], e["id"] + "-l", e["id"] + "-r"):
            put(mid, col, e.get("opacity", 1.0))
    return look


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
    pal = palette()
    out_meshes = []
    for m in sorted(meshes, key=lambda m: (order.get(m["system"], 99), m["subsystem"] or "", m["name"])):
        lic = cfg["sources"] and next((s["license"] for s in cfg["sources"] if s["id"] == m["source"]), "MNI")
        look = pal.get(m["id"], {"colour": m["colour"], "opacity": m["opacity"]})
        out_meshes.append({
            "id": m["id"], "structureId": look.get("structureId", m["structureId"]), "name": m["name"], "system": m["system"], "subsystem": m["subsystem"],
            "side": m["side"], "source": m["source"], "license": lic, "nc": bool(cfg["licenses"][lic].get("nc", False)),
            "alignment": m["alignment"], "file": m["file"], "bytes": m["bytes"], "triangles": m["triangles"], "compression": "meshopt",
            "colour": look["colour"], "opacity": look["opacity"], "visible": m["visible"], "bbox": m["bbox"], "centroid": m["centroid"],
            "labels": by_mesh.get(m["id"], {}), "ontology": {k: v for k, v in (("atlasLabels", m.get("atlasLabels")),) if v},
            **({"lod": m["lod"]} if m.get("lod") else {}),
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
    lod_total = sum(m["lod"]["bytes"] for m in out_meshes if m.get("lod"))
    first = sum((m["lod"]["bytes"] if m.get("lod") else m["bytes"]) for m in out_meshes if m["visible"])
    print(f"manifest: {len(out_meshes)} meshes, {total/1e6:.1f} MB full + {lod_total/1e6:.1f} MB stand-ins, first paint ~{first/1e6:.1f} MB, systems {len(manifest['systems'])} -> {OUT / 'manifest.json'}")


if __name__ == "__main__":
    main()
