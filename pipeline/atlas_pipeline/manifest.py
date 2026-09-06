"""Step 08: public/data/manifest.json (private edition) and public/data/manifest.public.json (--public)."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
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
    for spec in (catalog.ENVELOPE, catalog.ARTERIES_MRA, *catalog.venat_entries().values(),
                 *catalog.lc_metamask_entries().values()):
        put(spec.id, spec.colour, spec.opacity, spec.structure_id)
    try:
        from .brainstem_nav import palette_specs
        for spec in palette_specs().values():
            put(spec.id, spec.colour, spec.opacity, spec.structure_id)
    except Exception:  # noqa: BLE001 - the Brainstem Navigator mapping is optional
        pass
    for e in yaml.safe_load((CONFIG / "bp3d_selection.yaml").read_text())["meshes"]:
        put(e["id"], e.get("colour") or catalog.jitter(catalog.SYSTEM_COLOUR[e["system"]], e.get("structureId") or e["id"]), e.get("opacity", 1.0))
    for e in yaml.safe_load((CONFIG / "zanatomy_selection.yaml").read_text())["entries"]:
        col = e.get("colour") or catalog.jitter(catalog.SYSTEM_COLOUR[e["system"]], e.get("structureId") or e["id"])
        for mid in (e["id"], e["id"] + "-l", e["id"] + "-r"):
            put(mid, col, e.get("opacity", 1.0))
    return look


# ---------------------------------------------------------------- public edition
# The public edition ships only data that may be redistributed under CC BY-SA 4.0. Everything whose licence
# is marked `nc: true` (non-commercial) or `no_redistribution: true` in pipeline/config/sources.yaml is cut:
# Harvard-Oxford (FSL-NC), the Diedrichsen cerebellar atlas (CC-BY-NC-3.0), the Brainstem Navigator meshes and
# the PAM50 cord MRI (which reaches the manifest through grids.cord, so its volumes go with it).


# Names that must not appear anywhere in the public data files, even in prose: a mention means the record
# still carries provenance from a dataset we may not redistribute.
NAME_STRINGS = ("Brainstem Navigator", "BrainstemNavigator", "Harvard-Oxford", "Diedrichsen", "PAM50")


def restricted_licences(licenses: dict) -> dict[str, str]:
    """licence id -> why it cannot ship in the public edition (empty when the licence is fine)."""
    out: dict[str, str] = {}
    for k, v in licenses.items():
        nc = bool(v.get("nc"))
        nr = bool(v.get("noRedistribution") or v.get("no_redistribution"))
        if nc and nr:
            out[k] = "non-commercial licence and no redistribution of derived files"
        elif nr:
            out[k] = "no redistribution of derived files"
        elif nc:
            out[k] = "non-commercial licence"
    return out


def filter_public(man: dict) -> tuple[dict, dict]:
    """Split a built manifest into (public manifest, exclusions record). The input is never mutated."""
    restricted = restricted_licences(man["licenses"])
    cord = (man.get("grids") or {}).get("cord")

    ex_sources = {sid: {"license": s["license"], "reason": restricted[s["license"]]}
                  for sid, s in man["sources"].items() if s["license"] in restricted}
    # A mesh cut or shaped with a restricted dataset is itself a derived file of it, even when the surface it
    # started from is freely licensed: the cord segment blocks are Z-Anatomy geometry sliced at PAM50 level
    # boundaries, so they leave with PAM50. `derived` records exactly that provenance, so it is what we test.
    tokens = {sid.lower() for sid in ex_sources} | {n.lower() for n in NAME_STRINGS}

    def derived_from_restricted(m: dict) -> str | None:
        d = (m.get("derived") or "").lower()
        hit = next((t for t in sorted(tokens) if t and t in d), None)
        return f"geometry derived from restricted data ({hit})" if hit else None

    ex_meshes, keep_meshes = [], []
    for m in man["meshes"]:
        why = (restricted.get(m["license"]) or (ex_sources[m["source"]]["reason"] if m["source"] in ex_sources else None)
               or derived_from_restricted(m))
        (ex_meshes if why else keep_meshes).append(m)

    reasons = {m["id"]: (restricted.get(m["license"]) or (ex_sources[m["source"]]["reason"] if m["source"] in ex_sources else None)
                         or derived_from_restricted(m)) for m in ex_meshes}

    ex_grids = {}
    if cord and cord.get("license") in restricted:
        ex_grids["cord"] = {"license": cord["license"], "source": cord["source"], "reason": restricted[cord["license"]]}

    ex_volumes, keep_volumes = [], {}
    for k, v in man["volumes"].items():
        lic = v.get("license") or (cord.get("license") if (v.get("space") == "cord" and cord) else None)
        drop = (lic in restricted) or (v.get("space") == "cord" and "cord" in ex_grids)
        if drop:
            ex_volumes.append({"key": k, "file": v["file"], "license": lic, "space": v.get("space"),
                               "bytes": v.get("bytes_gz", 0),
                               "reason": restricted.get(lic, "sits on a grid that is not redistributable"),
                               **({"lut": v["lut"]} if v.get("lut") else {})})
        else:
            keep_volumes[k] = v

    referenced = {m["license"] for m in keep_meshes}
    referenced |= {s["license"] for sid, s in man["sources"].items() if sid not in ex_sources}
    if cord and "cord" not in ex_grids:
        referenced.add(cord["license"])
    ex_licenses = {k: restricted[k] for k in restricted}
    for k in man["licenses"]:
        if k not in restricted and k not in referenced:
            ex_licenses[k] = "no remaining mesh, volume or source uses it"

    public = {
        **man,
        "edition": "public",
        "volumes": keep_volumes,
        "grids": {k: v for k, v in (man.get("grids") or {}).items() if k not in ex_grids},
        "licenses": {k: v for k, v in man["licenses"].items() if k not in ex_licenses},
        "sources": {k: v for k, v in man["sources"].items() if k not in ex_sources},
        "meshes": keep_meshes,
    }
    exclusions = {
        "generated": man["generated"],
        "edition": "public",
        "rule": "excluded when the licence is marked nc: true or no_redistribution: true in pipeline/config/sources.yaml",
        "licenses": ex_licenses,
        "sources": ex_sources,
        "grids": ex_grids,
        "volumes": ex_volumes,
        "meshes": [{"id": m["id"], "structureId": m["structureId"], "name": m["name"], "system": m["system"],
                    "source": m["source"], "license": m["license"], "bytes": m["bytes"],
                    "files": [m["file"]] + ([m["lod"]["file"]] if m.get("lod") else []),
                    "reason": reasons[m["id"]]}
                   for m in ex_meshes],
        "totals": {
            "meshes": len(ex_meshes),
            "meshBytes": sum(m["bytes"] + (m["lod"]["bytes"] if m.get("lod") else 0) for m in ex_meshes),
            "volumes": len(ex_volumes),
            "volumeBytes": sum(v["bytes"] or 0 for v in ex_volumes),
            "licenses": len(ex_licenses),
            "sources": len(ex_sources),
            "grids": len(ex_grids),
            "meshesKept": len(keep_meshes),
            "meshBytesKept": sum(m["bytes"] + (m["lod"]["bytes"] if m.get("lod") else 0) for m in keep_meshes),
        },
    }
    return public, exclusions


def verify_public(public: dict, exclusions: dict) -> list[str]:
    """Every reason the manifest may not be published. An empty list means it is clean."""
    bad: list[str] = []
    ex_ids = {m["id"] for m in exclusions["meshes"]}
    left = restricted_licences(public["licenses"])
    if left:
        bad.append(f"restricted licences still in manifest.licenses: {sorted(left)}")
    for sid in exclusions["sources"]:
        if sid in public["sources"]:
            bad.append(f"restricted source {sid} still in manifest.sources")
    for m in public["meshes"]:
        if m["id"] in ex_ids:
            bad.append(f"excluded mesh {m['id']} still in manifest.meshes")
        if m.get("nc"):
            bad.append(f"mesh {m['id']} is flagged nc")
        if m["license"] not in public["licenses"]:
            bad.append(f"mesh {m['id']} references dropped licence {m['license']}")
        if m["source"] not in public["sources"]:
            bad.append(f"mesh {m['id']} references dropped source {m['source']}")
    for sid, s in public["sources"].items():
        if s["license"] not in public["licenses"]:
            bad.append(f"source {sid} references dropped licence {s['license']}")
    for k, v in public["volumes"].items():
        if v.get("space") and not (public.get("grids") or {}).get(v["space"]):
            bad.append(f"volume {k} sits on the dropped grid '{v['space']}'")
    for g, grid in (public.get("grids") or {}).items():
        if grid.get("license") not in public["licenses"]:
            bad.append(f"grids.{g} references dropped licence {grid.get('license')}")
    blob = json.dumps(public)
    for name in NAME_STRINGS:
        if name in blob:
            bad.append(f"the string {name!r} survives in the public manifest")
    return bad


def _args(argv) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="atlas-manifest", description=__doc__)
    ap.add_argument("--public", action="store_true",
                    help="write the redistributable public edition to manifest.public.json instead of manifest.json")
    a = ap.parse_args(sys.argv[1:] if argv is None else argv)
    if os.environ.get("ATLAS_EDITION") == "public":
        a.public = True
    return a


def main(argv=None) -> None:
    args = _args(argv)
    meshes = json.loads((WORK / "meshes.json").read_text())
    # A mesh recorded with edition "public" only exists because the private edition's source may not be
    # redistributed (the CerebrA cortex stands in for Harvard-Oxford): it ships in the public edition and
    # is left out of the private one, where the original parcellation is there instead.
    meshes = [m for m in meshes if args.public or m.get("edition") != "public"]
    labels = json.loads((VOLUMES / "labels.json").read_text())
    volume = json.loads((VOLUMES / "volume.json").read_text())
    # the cord MRI (atlas-pam50) lives on its own grid off the 193x229x193 brain box, so it ships as a second
    # volume set with its own affine; absent until atlas-pam50 has run.
    cord_path = VOLUMES / "cord.json"
    cord = json.loads(cord_path.read_text()) if cord_path.exists() else None
    if cord and "labels_spine" in cord["contrasts"] and (VOLUMES / "labels_spine.json").exists():
        cord["contrasts"]["labels_spine"]["lut"] = "volumes/labels_spine.json"   # spinal-level LUT (atlas-pam50)
    cfg = load_sources()
    # the data folder carries its own licence (CC BY-SA 4.0 + what it covers and how the sources were changed)
    shutil.copyfile(CONFIG / "data_LICENSE.txt", OUT / "LICENSE")
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
            **({"derived": m["derived"]} if m.get("derived") else {}),
            **({"edition": m["edition"]} if m.get("edition") else {}),
        })
    # "private" as soon as anything that may not be redistributed is in the build (Brainstem Navigator meshes,
    # the PAM50 cord MRI); a build without them can be shared, and the About panel says which edition this is.
    restricted = {m["license"] for m in out_meshes if cfg["licenses"][m["license"]].get("no_redistribution")}
    if cord and cfg["licenses"].get(cord.get("license"), {}).get("no_redistribution"):
        restricted.add(cord["license"])
    manifest = {
        "schema": 1, "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "space": "MNI152NLin2009cAsym",
        "edition": "private" if restricted else "public",
        "grid": {"shape": volume["shape"], "spacing": volume["spacing"], "origin_ras": volume["origin_ras"], "affine_ras": volume["affine_ras"]},
        "volumes": {**volume["contrasts"], **{k: {**v, "lut": "volumes/labels.json"} for k, v in labels["volumes"].items()},
                    **(cord["contrasts"] if cord else {})},
        "grids": {"cord": {k: cord[k] for k in ("shape", "spacing", "origin_ras", "affine_ras", "source", "license", "reformat")}} if cord else {},
        "transforms": transforms,
        "systems": [{"id": s[0], "name": s[1], "colour": s[2], "defaultVisible": s[3]} for s in catalog.SYSTEMS],
        "licenses": {k: {"name": v["name"], "url": v["url"], "attribution": v.get("attribution", ""), "nc": bool(v.get("nc", False)), "noRedistribution": bool(v.get("no_redistribution", False)),
                         "text": f"licenses/{k}.txt"} for k, v in cfg["licenses"].items()},
        # every shipped source with the attribution the About panel and NOTICE need: dataset name, citation,
        # licence id and the download URLs the files actually came from (url = the dataset's landing/first URL).
        "sources": {s["id"]: {"name": s.get("name", s["id"]), "license": s["license"], "citation": s["citation"],
                              "url": (s["files"][0]["url"] if s.get("files") else ""),
                              "urls": [d["url"] for d in s.get("files", [])],
                              "manual": bool(s.get("manual", False)),
                              "files": {f: lock.get(f"{s['id']}/{f}", {}).get("sha256") for f in [d.get("dest") or d["url"].rsplit("/", 1)[-1] for d in s["files"]]}}
                    for s in cfg["sources"] if any(m["source"] == s["id"] for m in meshes) or s["id"] == "mni_t1w"
                    or (cord is not None and s["id"] == cord.get("source"))},
        "meshes": out_meshes,
    }
    if args.public:
        public, exclusions = filter_public(manifest)
        bad = verify_public(public, exclusions)
        if bad:
            for b in bad:
                print(f"manifest --public: {b}", file=sys.stderr)
            raise SystemExit(f"manifest --public: {len(bad)} restricted item(s) left in the public manifest")
        (OUT / "manifest.public.json").write_text(json.dumps(public, indent=1))
        (OUT / "manifest.public.exclusions.json").write_text(json.dumps(exclusions, indent=1))
        t = exclusions["totals"]
        print(f"manifest --public: dropped {t['meshes']} meshes ({t['meshBytes']/1e6:.1f} MB), {t['volumes']} volumes "
              f"({t['volumeBytes']/1e6:.1f} MB), {t['grids']} grid(s), {t['licenses']} licences, {t['sources']} sources "
              f"-> {OUT / 'manifest.public.exclusions.json'}")
        print(f"manifest --public: {t['meshesKept']} meshes ({t['meshBytesKept']/1e6:.1f} MB), "
              f"{len(public['volumes'])} volumes, {len(public['licenses'])} licences, {len(public['sources'])} sources "
              f"-> {OUT / 'manifest.public.json'}")
        return
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1))
    total = sum(m["bytes"] for m in out_meshes)
    lod_total = sum(m["lod"]["bytes"] for m in out_meshes if m.get("lod"))
    first = sum((m["lod"]["bytes"] if m.get("lod") else m["bytes"]) for m in out_meshes if m["visible"])
    if cord:
        print(f"manifest: + cord volumes {list(cord['contrasts'])} on a {cord['shape']} grid at {cord['spacing'][0]} mm")
    print(f"manifest: {len(out_meshes)} meshes, {total/1e6:.1f} MB full + {lod_total/1e6:.1f} MB stand-ins, first paint ~{first/1e6:.1f} MB, systems {len(manifest['systems'])} -> {OUT / 'manifest.json'}")


if __name__ == "__main__":
    main()
