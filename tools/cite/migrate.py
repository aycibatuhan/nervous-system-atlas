#!/usr/bin/env python3
"""Replace the textbook citations of every content entry with open-access bibliography refs.

  python3 tools/cite/migrate.py                 # dry run: plan + match-quality table
  python3 tools/cite/migrate.py --report        # per-entry plan
  python3 tools/cite/migrate.py --unmatched     # entries the automatic pass cannot cover (input to the manual pass)
  python3 tools/cite/migrate.py --apply         # write content/bibliography/*.json and rewrite entry citations

Idempotent: entries whose citations are already refs are left alone. --force re-derives the entries this
tool migrated before (recorded in the log) plus anything named in mapping.json; entries authored directly
in {"ref": ...} form by someone else are never rewritten.
Only NCBI-verified records are ever written; nothing is invented.
"""
import argparse, collections, datetime, json, os, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import catalog, inventory, match, sections

ROOT = Path(__file__).resolve().parents[2]
BIB = ROOT / "content" / "bibliography"
LOG = ROOT / "reference" / "citation-migration.json"
MAPPING = Path(__file__).parent / "mapping.json"

ACCEPT = float(os.environ.get("CITE_ACCEPT", 62.0))   # rarity-weighted score at which an automatic match is trusted            # automatic match trusted at or above this score
MAXREFS = 4

# "hub" chapters added as supporting refs, by entry system / category and (for the cortex) by lobe.
# Every title here must exist in the harvested catalog; migrate.py warns loudly if one does not.
HUBS: dict[str, list[str]] = {
    "cerebrum": ["Neuroanatomy, Cerebral Cortex", "Neuroanatomy, Cerebral Hemisphere"],
    "basal-ganglia": ["Neuroanatomy, Basal Ganglia", "Neuroanatomy, Extrapyramidal System"],
    "diencephalon": ["Neuroanatomy, Thalamus", "Neuroanatomy, Thalamic Nuclei"],
    "brainstem": ["Neuroanatomy, Brainstem", "Neuroanatomy, Cranial Nerve"],
    "cerebellum": ["Neuroanatomy, Cerebellum", "Cerebellar Dysfunction"],
    "cranial-nerves": ["Neuroanatomy, Cranial Nerve", "Cranial Nerve Testing"],
    "spinal-cord": ["Neuroanatomy, Spinal Cord", "Neuroanatomy, Spinal Cord Morphology"],
    "peripheral": ["Neuroanatomy, Spinal Nerves", "Peripheral Nerve Injury"],
    "autonomic": ["Anatomy, Autonomic Nervous System", "Neuroanatomy, Sympathetic Nervous System"],
    "ventricles-csf": ["Neuroanatomy, Ventricular System", "Neuroanatomy, Cerebrospinal Fluid"],
    "meninges": ["Neuroanatomy, Cranial Meninges"],
    "arteries": ["Neuroanatomy, Cerebral Blood Supply", "Neuroanatomy, Circle of Willis"],
    "arterial-territories": ["Neuroanatomy, Cerebral Blood Supply", "Ischemic Stroke"],
    "venous": ["Neuroanatomy, Dural Venous Sinuses", "Neuroanatomy, Brain Veins"],
    "tracts": ["Neuroanatomy, Cerebral Hemisphere", "Neuroanatomy, Gray Matter"],
    "envelope": ["Neuroanatomy, Cerebral Cortex"],
    # syndrome categories
    "vascular": ["Neuroanatomy, Cerebral Blood Supply", "Ischemic Stroke"],
    "lacunar": ["Lacunar Stroke", "Neuroanatomy, Cerebral Blood Supply"],
    "herniation": ["Neuroanatomy, Cranial Meninges"],
    "csf-pressure": ["Neuroanatomy, Cerebrospinal Fluid"],
    "entrapment": ["Peripheral Nerve Injury"],
    "plexopathy": ["Neuroanatomy, Spinal Nerves", "Peripheral Nerve Injury"],
    "radiculopathy": ["Neuroanatomy, Spinal Nerves"],
    "compressive": ["Peripheral Nerve Injury"],
    "traumatic": ["Peripheral Nerve Injury"],
    "demyelinating": ["Neuroanatomy, Nodes of Ranvier"],
    "neuromuscular": ["Neuroanatomy, Motor Neuron"],
    "otologic": ["Neuroanatomy, Vestibular Pathways"],
    "functional-pattern": ["Neuroanatomy, Cerebral Cortex"],
}
# entries carry a subsystem ("lobe-frontal", "projection", ...): cite the more specific chapter first
LOBE_HUBS: dict[str, list[str]] = {
    "association": ["Neuroanatomy, Cerebral Cortex", "Neuroanatomy, Corpus Callosum"],
    "projection": ["Neuroanatomy, Internal Capsule", "Neuroanatomy, Thalamocortical Radiations"],
    "limbic": ["Neuroanatomy, Limbic System", "Neuroanatomy, Corpus Callosum"],
    "cerebellar": ["Neuroanatomy, Cerebellum", "Neuroanatomy, Spinocerebellar Dorsal Tract"],
    "lobe-frontal": ["Neuroanatomy, Frontal Cortex"],
    "lobe-temporal": ["Neuroanatomy, Temporal Lobe"],
    "lobe-parietal": ["Neuroanatomy, Somatosensory Cortex"],
    "lobe-occipital": ["Neuroanatomy, Occipital Lobe", "Neuroanatomy, Visual Cortex"],
    "lobe-insula": ["Insular Cortex"],
    "lobe-limbic": ["Neuroanatomy, Limbic System"],
    "lobe-cingulate": ["Neuroanatomy, Cingulate Cortex"],
}

ANATOMY_TITLE = re.compile(r"^(neuroanatomy|anatomy|physiology|histology|embryology)\b", re.I)


def slug(title: str) -> str:
    s = match.core(title)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    s = "-".join(s.split("-")[:8])
    return f"sp-{s}"[:64].rstrip("-")


class Bib:
    """Bibliography files on disk, indexed by accession so ids stay stable across runs."""

    def __init__(self):
        self.by_id: dict[str, dict] = {}
        self.by_nbk: dict[str, str] = {}
        for p in sorted(BIB.glob("*.json")):
            d = json.loads(p.read_text())
            self.by_id[d["id"]] = d
            if d.get("nbk"):
                self.by_nbk[d["nbk"]] = d["id"]
        self.pending: dict[str, dict] = {}

    def ref_for(self, rec: dict) -> str:
        """Bibliography id for a catalog record, creating the entry if new."""
        nbk = rec["nbk"]
        if nbk in self.by_nbk:
            return self.by_nbk[nbk]
        base = slug(rec["title"])
        rid, n = base, 2
        while rid in self.by_id or rid in self.pending:
            rid, n = f"{base}-{n}", n + 1
        self.pending[rid] = {
            "id": rid, "type": "statpearls", "title": rec["title"],
            "authors": rec["authors"] or ["StatPearls contributors"], "year": rec["year"],
            "container": "StatPearls [Internet]", "publisher": "StatPearls Publishing, Treasure Island (FL)",
            "url": f"https://www.ncbi.nlm.nih.gov/books/{nbk}/", "nbk": nbk,
            "license": "CC BY-NC-ND 4.0", "accessed": datetime.date.today().isoformat(),
            "verified": True, "tags": [],
        }
        self.by_nbk[nbk] = rid
        return rid

    def write(self) -> int:
        BIB.mkdir(parents=True, exist_ok=True)
        for rid, d in self.pending.items():
            (BIB / f"{rid}.json").write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
        n = len(self.pending)
        self.by_id.update(self.pending)
        self.pending = {}
        return n

    def title(self, rid: str) -> str:
        d = self.by_id.get(rid) or self.pending.get(rid) or {}
        return d.get("title", rid)

    def nbk(self, rid: str) -> str | None:
        d = self.by_id.get(rid) or self.pending.get(rid) or {}
        return d.get("nbk")


ID_PREFIX = re.compile(r"^(syn|pathway|topic|q|gl|cn)-(\d+-)?")


def keys_for(e: dict) -> list[str]:
    ks = [e["name"], *e["synonyms"]]
    i = ID_PREFIX.sub("", e["id"])
    ks.append(i.replace("-", " "))
    parts = i.split("-")
    if 1 < len(parts) <= 4:
        ks.append(" ".join(parts[::-1]))
    if e["kind"] == "cranial-nerve":
        n = re.match(r"cn-(\d+)", e["id"])
        if n:
            ks.append(f"cranial nerve {int(n.group(1))}")
    out, seen = [], set()
    for k in ks:
        k = re.sub(r"\s+", " ", str(k)).strip()
        if k and k.lower() not in seen and len(k) > 2:
            seen.add(k.lower())
            out.append(k)
    return out


def by_title(title: str) -> dict | None:
    t = title.lower().rstrip(".")
    for r in match.cat():
        if r["title"].lower().rstrip(".") == t:
            return r
    return None


def pick_section(nbk: str, kind: str, chapter_title: str) -> str | None:
    hs = sections.headings(nbk)
    if not hs:
        return None
    anat = bool(ANATOMY_TITLE.match(chapter_title))
    if kind in ("structure", "cranial-nerve", "pathway", "topic", "glossary"):
        want = ["Structure and Function", "Pathophysiology", "Introduction"] if anat else ["Pathophysiology", "Introduction"]
    else:                                        # syndrome / quiz
        want = ["Clinical Significance", "Introduction"] if anat else ["History and Physical", "Pathophysiology", "Introduction"]
    for w in want:
        if w in hs:
            return w
    return None


def plan(entries: list[dict], bib: Bib, manual: dict) -> dict[str, dict]:
    plans: dict[str, dict] = {}
    for e in entries:
        old = e["citations"]
        if old and all("ref" in c for c in old):
            plans[e["id"]] = {"quality": "already", "refs": [c["ref"] for c in old], "cites": old}
            continue
        refs: list[str] = []
        m = manual.get(e["id"])
        if m:
            quality = "manual"
            for item in m:
                if "ref" in item:
                    refs.append(item["ref"])
                else:
                    rec = by_title(item["title"]) if "title" in item else next((r for r in match.cat() if r["nbk"] == item["nbk"]), None)
                    if rec is None:
                        raise SystemExit(f"mapping.json: unknown chapter for {e['id']}: {item}")
                    refs.append(bib.ref_for(rec))
        else:
            ranked = match.rank(keys_for(e), 12)
            anat_entry = e["kind"] in ("structure", "cranial-nerve", "pathway", "topic")
            # tie-break toward anatomy chapters for anatomy entries and toward disease chapters for syndromes
            ranked = sorted(((sc + (5.0 if bool(ANATOMY_TITLE.match(rec["title"])) == anat_entry else 0.0), rec)
                             for sc, rec in ranked), key=lambda x: -x[0])
            top = ranked[0][0] if ranked else 0.0
            quality = "exact" if top >= 96 else "strong" if top >= ACCEPT else "unmatched"
            for sc, rec in ranked:
                if sc >= ACCEPT and len(refs) < 3:
                    refs.append(bib.ref_for(rec))
        # top up with system/lobe chapters: manual picks were made with the hubs already on the table,
        # so only guarantee a second ref there; automatic matches get up to three.
        target = 2 if quality == "manual" else 3
        for t in [*LOBE_HUBS.get(e["subsystem"], []), *HUBS.get(e["system"], [])]:
            if len(refs) >= min(target, MAXREFS):
                break
            rec = by_title(t)
            if rec:
                r = bib.ref_for(rec)
                if r not in refs:
                    refs.append(r)
        refs = list(dict.fromkeys(refs))
        if quality == "unmatched" and refs:
            quality = "hub"                       # no chapter on this exact subject; cited to its system/lobe chapters
        plans[e["id"]] = {"quality": quality, "refs": refs, "old": old, "kind": e["kind"]}
    # quiz items inherit the refs of the structures/syndromes/pathways they test
    for e in entries:
        p = plans[e["id"]]
        if e["kind"] != "quiz" or p["quality"] == "already":
            continue
        t = e["targets"]
        inherited: list[str] = []
        for tid in [*t.get("syndromeIds", []), *t.get("pathwayIds", []), *t.get("structureIds", [])]:
            for r in plans.get(tid, {}).get("refs", []):
                if r not in inherited:
                    inherited.append(r)
        merged = list(dict.fromkeys([*p["refs"], *inherited]))[:MAXREFS]
        if merged:
            p["refs"] = merged
            if p["quality"] == "unmatched":
                p["quality"] = "inherited"
    return plans


def rewrite(e: dict, refs: list[str], bib: Bib) -> bool:
    """Read-modify-write one entry file, preserving field order and 2-space JSON formatting."""
    p: Path = e["path"]
    d = json.loads(p.read_text())
    cites = []
    for r in refs:
        c: dict = {"ref": r}
        nbk = bib.nbk(r)
        if nbk:
            sec = pick_section(nbk, e["kind"], bib.title(r))
            if sec:
                c["section"] = sec
        cites.append(c)
    if d.get("citations") == cites:
        return False
    if "citations" in d:
        d["citations"] = cites
    else:
        d["citations"] = cites
    p.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--unmatched", action="store_true")
    ap.add_argument("--force", action="store_true", help="re-derive refs for entries this tool migrated before")
    ap.add_argument("--prune", action="store_true", help="with --apply: delete bibliography entries nothing cites")
    a = ap.parse_args()

    entries = inventory.entries()
    manual = json.loads(MAPPING.read_text()).get("map", {})
    if a.force:
        # re-derive only the entries this tool migrated before (or that mapping.json names);
        # entries authored directly in {"ref": ...} form by someone else are never touched
        prev_log = json.loads(LOG.read_text()) if LOG.exists() else {}
        previous = {k for k, v in prev_log.items() if v.get("quality") != "already"}
        for e in entries:
            if e["id"] in previous or e["id"] in manual:
                e["citations"] = [c for c in e["citations"] if "ref" not in c]
    bib = Bib()
    for sysname, titles in HUBS.items():
        for t in titles:
            if not by_title(t):
                print(f"WARNING hub chapter missing from catalog: {t} ({sysname})", file=sys.stderr)
    plans = plan(entries, bib, manual)

    buckets = collections.Counter((e["kind"], plans[e["id"]]["quality"]) for e in entries)
    need = [e for e in entries if e["kind"] != "glossary" and not plans[e["id"]]["refs"]]
    if a.unmatched:
        import fulltext
        todo = [e for e in entries if plans[e["id"]]["quality"] in ("unmatched", "hub")]
        fulltext.warm([e["name"] for e in todo])
        for e in todo:
            cands = match.rank(keys_for(e), 8)
            ft = [c for c in fulltext.candidates(e["name"]) if c["nbk"] not in {r["nbk"] for _, r in cands}]
            print(json.dumps({"id": e["id"], "kind": e["kind"], "name": e["name"], "synonyms": e["synonyms"],
                              "system": e["system"], "quality": plans[e["id"]]["quality"],
                              "current": [bib.title(r) for r in plans[e["id"]]["refs"]],
                              "summary": e["summary"][:300],
                              "candidates": [{"nbk": r["nbk"], "title": r["title"]} for _, r in cands]
                                            + [{"nbk": c["nbk"], "title": c["title"], "via": "full-text"} for c in ft[:6]]},
                             ensure_ascii=False))
        return
    if a.report:
        for e in entries:
            p = plans[e["id"]]
            print(f"{p['quality']:9s} {e['kind']:13s} {e['id']:42s} " + "; ".join(bib.title(r) for r in p["refs"]))
    print("match quality:")
    for k in sorted(buckets):
        print(f"  {k[0]:13s} {k[1]:10s} {buckets[k]}")
    print(f"entries with no ref (non-glossary): {len(need)}")

    if not a.apply:
        print(f"(dry run; {len(bib.pending)} new bibliography entries would be written)")
        return
    # warm the section cache for every chapter we are about to cite
    nbks = [bib.nbk(r) for p in plans.values() for r in p["refs"]]
    sections.warm([n for n in nbks if n])
    n_new = bib.write()
    changed = 0
    log = {}
    for e in entries:
        p = plans[e["id"]]
        if not p["refs"]:
            continue
        if p["quality"] != "already" and rewrite(e, p["refs"], bib):
            changed += 1
        log[e["id"]] = {"kind": e["kind"], "quality": p["quality"], "old": p.get("old", []),
                        "new": p["refs"], "titles": [bib.title(r) for r in p["refs"]]}
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False))
    print(f"wrote {n_new} new bibliography entries; rewrote {changed} entry files; log -> {LOG}")
    # bibliography entries nothing cites any more (superseded by a better match)
    used = {c["ref"] for e in inventory.entries() for c in e["citations"]}
    orphans = sorted(set(bib.by_id) - used)
    if orphans and a.prune:
        for rid in orphans:
            (BIB / f"{rid}.json").unlink(missing_ok=True)
        print(f"pruned {len(orphans)} uncited bibliography entries")
    elif orphans:
        print(f"{len(orphans)} uncited bibliography entries (re-run with --prune to delete): {', '.join(orphans[:10])}"
              + (" ..." if len(orphans) > 10 else ""))


if __name__ == "__main__":
    main()
