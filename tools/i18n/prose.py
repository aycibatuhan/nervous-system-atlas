#!/usr/bin/env python3
"""Turkish translation of the clinical prose: extraction, checking, status.

  python3 tools/i18n/prose.py extract [--words 12000] [--kinds syndromes,topics]   # task files for the translators
  python3 tools/i18n/prose.py check [--strict]                                     # every overlay against its entry
  python3 tools/i18n/prose.py status                                               # coverage by kind

Layout.  The English entries stay in content/data/<kind>/<id>.json.  A translation is an overlay file
content/i18n/tr/<kind>/<id>.json:

  { "id": "syn-wallenberg-lateral-medullary", "kind": "syndromes", "lang": "tr", "source": "<sha1 of the English strings>",
    "fields": { "name": "…", "presentation": "…", "deficits[0].sign": "…", … } }

`fields` maps a flattened JSON path of the English entry to the translated string; every translatable path of the
entry must be present (check fails on missing or extra paths), and `source` pins the English text the translation
was made from, so an edited English entry shows up as stale.  scripts/content/build.ts applies the overlays and
writes public/data/content.tr.json next to content.json.

What is translatable: every string of an entry except identifiers and enumerations (ids, kinds, mesh ids, cross
references, citations, sides, modalities, sequences, planes, categories, tiers, quiz answer keys, MNI numbers) and,
for structures, cranial nerves and pathways, the `name` (Turkish mode shows the Latin term from `names.tr`).
Syndrome and topic names, glossary terms, and every clinical sentence are translated.

`extract` writes reference/i18n-tasks/<batch>.json (gitignored): one file per batch of about --words English
words, holding the English strings by entry and path, plus the style guide the translators must follow.  A
translator writes the overlay files directly; `check` then verifies them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "content" / "data"
TR = ROOT / "content" / "i18n" / "tr"
TASKS = ROOT / "reference" / "i18n-tasks"
STYLE = ROOT / "tools" / "i18n" / "STYLE-tr.md"
KINDS = ["structures", "cranial-nerves", "pathways", "syndromes", "topics", "glossary", "quiz"]

# keys whose strings are never translated (identifiers, enumerations, references, numbers)
DENY = {"id", "kind", "ref", "section", "meshId", "meshIds", "structureId", "structures", "pathways", "syndromes",
        "related", "parent", "system", "subsystem", "status", "tags", "latin", "synonyms", "eponyms", "side", "modality",
        "sequence", "plane", "region", "sub", "roman", "components", "component", "type", "category", "tier",
        "cameraPreset", "answer", "key", "difficulty", "mni", "x", "y", "z", "order", "number", "names",
        "synonymsByLang", "sideRelativeToOrigin", "arteries", "territories", "lesionMarker", "citations", "targets",
        "highlightOnReveal", "original", "localisation", "substrate", "arteryId", "territoryId", "generated", "lang"}
# the display name of a structure / nerve / pathway is the Latin term in Turkish mode, not a translation
NAME_KEPT = {"structures", "cranial-nerves", "pathways"}


def flatten(o, path: str = "", kind: str = "") -> list[tuple[str, str]]:
    """(path, string) for every translatable string, in document order."""
    out: list[tuple[str, str]] = []
    if isinstance(o, dict):
        for k, v in o.items():
            if k in DENY or (k == "name" and not path and kind in NAME_KEPT):
                continue
            out += flatten(v, f"{path}.{k}" if path else k, kind)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            out += flatten(v, f"{path}[{i}]", kind)
    elif isinstance(o, str) and o.strip():
        out.append((path, o))
    return out


def source_hash(pairs: list[tuple[str, str]]) -> str:
    return hashlib.sha1(json.dumps(pairs, ensure_ascii=False).encode()).hexdigest()[:16]


def entries() -> list[tuple[str, str, dict, list[tuple[str, str]]]]:
    out = []
    for kind in KINDS:
        for f in sorted((DATA / kind).glob("*.json")):
            d = json.loads(f.read_text())
            out.append((kind, d["id"], d, flatten(d, kind=kind)))
    return out


def overlay_path(kind: str, eid: str) -> Path:
    return TR / kind / f"{eid}.json"


def load_overlay(kind: str, eid: str) -> dict | None:
    p = overlay_path(kind, eid)
    return json.loads(p.read_text()) if p.exists() else None


# ------------------------------------------------------------------ extract ----
def cmd_extract(a) -> None:
    TASKS.mkdir(parents=True, exist_ok=True)
    style = STYLE.read_text() if STYLE.exists() else ""
    kinds = a.kinds.split(",") if a.kinds else KINDS
    todo = [(k, i, d, p) for k, i, d, p in entries() if k in kinds and (a.redo or not _fresh(k, i, p))]
    batches: list[list] = []
    cur: list = []
    words = 0
    for k, i, d, p in todo:
        n = sum(len(s.split()) for _, s in p)
        if cur and (words + n > a.words or cur[-1][0] != k):
            batches.append(cur)
            cur, words = [], 0
        cur.append((k, i, d, p))
        words += n
    if cur:
        batches.append(cur)
    for old in TASKS.glob("*.json"):
        old.unlink()
    for b, batch in enumerate(batches, 1):
        kind = batch[0][0]
        name = f"{b:02d}-{kind}"
        body = {
            "batch": name,
            "instructions": f"Translate every string under `entries` into Turkish and write one overlay file per entry at "
                            f"content/i18n/tr/<kind>/<id>.json with the exact shape shown in `overlay_example`; keep every "
                            f"path key exactly as given, translate only the values. Style guide: tools/i18n/STYLE-tr.md "
                            f"(copied below). Then run `python3 tools/i18n/prose.py check` and fix what it reports.",
            "overlay_example": {"id": "<id>", "kind": "<kind>", "lang": "tr", "source": "<the source hash given with the entry>",
                                "fields": {"<path>": "<Turkish text>"}},
            "style_guide": style,
            "entries": [{"kind": k, "id": i, "file": f"content/i18n/tr/{k}/{i}.json", "source": source_hash(p),
                         "english_name": d.get("name") or d.get("term") or i, "latin": d.get("latin", ""),
                         "fields": dict(p)} for k, i, d, p in batch],
        }
        (TASKS / f"{name}.json").write_text(json.dumps(body, ensure_ascii=False, indent=1))
        print(f"{name}: {len(batch)} entries, {sum(len(s.split()) for _, _, _, p in batch for _, s in p)} words")
    print(f"{len(batches)} task files in {TASKS}")


def _fresh(kind: str, eid: str, pairs: list[tuple[str, str]]) -> bool:
    ov = load_overlay(kind, eid)
    return bool(ov) and ov.get("source") == source_hash(pairs) and set(ov.get("fields", {})) == {p for p, _ in pairs}


# ------------------------------------------------------------------ check ----
LINK = re.compile(r"\]\((#/[^)]+)\)")
NUM = re.compile(r"\d+(?:[.,]\d+)?")


def check_entry(kind: str, eid: str, pairs: list[tuple[str, str]], ov: dict) -> tuple[list[str], list[str]]:
    errors, warns = [], []
    want = {p for p, _ in pairs}
    have = set(ov.get("fields", {}))
    for p in sorted(want - have):
        errors.append(f"missing {p}")
    for p in sorted(have - want):
        errors.append(f"unknown path {p}")
    if ov.get("id") != eid or ov.get("kind") != kind or ov.get("lang") != "tr":
        errors.append("header must be id/kind/lang: tr")
    if ov.get("source") != source_hash(pairs):
        errors.append("stale: the English text changed since this translation (source hash differs)")
    en = dict(pairs)
    for p, v in ov.get("fields", {}).items():
        if p not in en:
            continue
        if not isinstance(v, str) or not v.strip():
            errors.append(f"{p}: empty")
            continue
        if v.strip() == en[p].strip() and len(en[p].split()) > 3 and not _looks_latin(en[p]):
            warns.append(f"{p}: identical to the English")
        if sorted(LINK.findall(v)) != sorted(LINK.findall(en[p])):
            errors.append(f"{p}: cross-links differ from the English ({LINK.findall(en[p])} vs {LINK.findall(v)})")
        if Counter(NUM.findall(v.replace(",", "."))) != Counter(NUM.findall(en[p].replace(",", "."))):
            warns.append(f"{p}: numbers differ ({' '.join(NUM.findall(en[p]))} vs {' '.join(NUM.findall(v))})")
        if en[p].count("**") != v.count("**"):
            warns.append(f"{p}: bold markers differ")
        r = len(v) / max(1, len(en[p]))
        if r < 0.6 or r > 2.2:
            warns.append(f"{p}: length ratio {r:.2f}")
    return errors, warns


def _looks_latin(s: str) -> bool:
    return bool(re.fullmatch(r"[A-Z][a-z]+( [a-z]+){0,4}", s.strip()))


def cmd_check(a) -> None:
    n_err = n_warn = n_ok = n_missing = 0
    for kind, eid, d, pairs in entries():
        ov = load_overlay(kind, eid)
        if not ov:
            n_missing += 1
            continue
        errors, warns = check_entry(kind, eid, pairs, ov)
        for e in errors:
            print(f"ERROR {kind}/{eid}: {e}")
        for w in warns:
            print(f"WARN  {kind}/{eid}: {w}")
        n_err += len(errors)
        n_warn += len(warns)
        n_ok += not errors
    print(f"check: {n_ok} overlays ok, {n_err} errors, {n_warn} warnings, {n_missing} entries without a translation")
    for p in TR.glob("*/*.json"):
        if not (DATA / p.parent.name / p.name).exists():
            print(f"ERROR orphan overlay {p.relative_to(ROOT)}")
            n_err += 1
    if n_err or (a.strict and n_missing):
        sys.exit(1)


def cmd_status(a) -> None:
    rows = defaultdict(lambda: [0, 0, 0, 0])   # entries, translated, words, translated words
    for kind, eid, d, pairs in entries():
        w = sum(len(s.split()) for _, s in pairs)
        r = rows[kind]
        r[0] += 1
        r[2] += w
        if _fresh(kind, eid, pairs):
            r[1] += 1
            r[3] += w
    tot = [0, 0, 0, 0]
    print(f"{'kind':16s} {'entries':>8s} {'done':>6s} {'words':>8s} {'done':>8s}")
    for kind in KINDS:
        r = rows[kind]
        tot = [x + y for x, y in zip(tot, r)]
        print(f"{kind:16s} {r[0]:8d} {r[1]:6d} {r[2]:8d} {r[3]:8d}")
    print(f"{'total':16s} {tot[0]:8d} {tot[1]:6d} {tot[2]:8d} {tot[3]:8d}")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    x = sub.add_parser("extract")
    x.add_argument("--words", type=int, default=12000)
    x.add_argument("--kinds", default="")
    x.add_argument("--redo", action="store_true", help="include entries that already have a fresh translation")
    c = sub.add_parser("check")
    c.add_argument("--strict", action="store_true", help="also fail when an entry has no translation")
    sub.add_parser("status")
    a = ap.parse_args(argv)
    {"extract": cmd_extract, "check": cmd_check, "status": cmd_status}.get(a.cmd, lambda _: ap.print_help())(a)


if __name__ == "__main__":
    main()
