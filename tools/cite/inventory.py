#!/usr/bin/env python3
"""Load every content entry with the fields the citation tooling needs."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "content" / "data"
KIND_DIRS = {"structures": "structure", "cranial-nerves": "cranial-nerve", "pathways": "pathway",
             "syndromes": "syndrome", "glossary": "glossary", "quiz": "quiz", "topics": "topic"}


def entries() -> list[dict]:
    out = []
    for d in sorted(DATA.iterdir()):
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.json")):
            e = json.loads(p.read_text())
            out.append({
                "path": p, "id": e["id"], "kind": e["kind"],
                "name": e.get("name") or e.get("term") or e["id"],
                "synonyms": e.get("synonyms") or e.get("eponyms") or [],
                "system": e.get("system") or e.get("category") or "",
                "subsystem": e.get("subsystem") or "",
                "summary": (e.get("summary") or e.get("presentation") or e.get("definition") or e.get("vignette") or "")[:400],
                "citations": e.get("citations") or [],
                "targets": e.get("targets") or {},
                "localisation": e.get("localisation") or {},
                "related": e.get("related") or {},
                "raw": e,
            })
    return out


if __name__ == "__main__":
    for e in entries():
        print(f"{e['kind']:14s} {e['id']:44s} {e['name']}")
