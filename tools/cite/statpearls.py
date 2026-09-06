#!/usr/bin/env python3
"""Add verified StatPearls (NCBI Bookshelf) chapters to content/bibliography/.

  python3 tools/cite/statpearls.py "Neuroanatomy, Putamen"            # exact title search, writes content/bibliography/<slug>.json
  python3 tools/cite/statpearls.py --id sp-putamen "Neuroanatomy, Putamen"
  python3 tools/cite/statpearls.py --search "phrenic nerve"            # list candidate titles (no write)
  python3 tools/cite/statpearls.py --nbk NBK542170                     # add by accession

Every written entry is verified against the live esummary record (title + contributors + NBK accession),
so `verified: true` is only ever set from API data. Uses the public E-utilities (no key; <=3 req/s).
"""
import argparse, json, re, sys, time, urllib.parse, urllib.request, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BIB = ROOT / "content" / "bibliography"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"


def _get(url):
    time.sleep(0.34)
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def esearch(term, retmax=20):
    q = urllib.parse.quote(term)
    d = _get(f"{EUTILS}esearch.fcgi?db=books&term={q}&retmax={retmax}&retmode=json")["esearchresult"]
    return d["idlist"]


def esummary(uids):
    if not uids:
        return []
    d = _get(f"{EUTILS}esummary.fcgi?db=books&id={','.join(uids)}&retmode=json")["result"]
    return [d[u] for u in d["uids"] if d[u].get("rtype") == "chapter"]


def parse(rec):
    info = rec.get("bookinfo", "")
    m = re.search(r"<Contributors>(.*?)</Contributors>", info)
    contributors = [c.strip().rstrip(".") for c in m.group(1).split(",")] if m else []
    year = int(rec["pubdate"][:4]) if rec.get("pubdate") else datetime.date.today().year
    return {"title": rec["title"].rstrip("."), "authors": contributors, "year": year, "nbk": rec["chapteraccessionid"]}


def slugify(title):
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    s = re.sub(r"^(neuroanatomy|anatomy|physiology)-", "", s)
    return "sp-" + s


def write(entry_id, meta, tags):
    entry = {
        "id": entry_id, "type": "statpearls", "title": meta["title"], "authors": meta["authors"] or ["StatPearls contributors"],
        "year": meta["year"], "container": "StatPearls [Internet]", "publisher": "StatPearls Publishing, Treasure Island (FL)",
        "url": f"https://www.ncbi.nlm.nih.gov/books/{meta['nbk']}/", "nbk": meta["nbk"], "license": "CC BY-NC-ND 4.0",
        "accessed": datetime.date.today().isoformat(), "verified": True, "tags": tags,
    }
    BIB.mkdir(parents=True, exist_ok=True)
    p = BIB / f"{entry_id}.json"
    p.write_text(json.dumps(entry, indent=2, ensure_ascii=False) + "\n")
    return p


def find_existing(nbk):
    for p in BIB.glob("*.json"):
        try:
            if json.loads(p.read_text()).get("nbk") == nbk:
                return p
        except Exception:
            pass
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("title", nargs="?")
    ap.add_argument("--id")
    ap.add_argument("--nbk")
    ap.add_argument("--search")
    ap.add_argument("--tag", action="append", default=[])
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    if a.search:
        for r in esummary(esearch(f"{a.search}[title] AND statpearls[book]", 40)):
            m = parse(r); print(f"{m['nbk']}\t{m['title']}\t{', '.join(m['authors'])}")
        return
    if a.nbk:
        recs = [r for r in esummary(esearch(f"{a.nbk}[accn] AND statpearls[book]", 5)) if r.get("chapteraccessionid") == a.nbk]
    else:
        if not a.title:
            ap.error("title, --nbk or --search required")
        recs = [r for r in esummary(esearch(f'"{a.title}"[title] AND statpearls[book]', 10)) if r["title"].rstrip(".").lower() == a.title.lower()]
    if not recs:
        print(f"NOT FOUND: {a.title or a.nbk}", file=sys.stderr); sys.exit(2)
    meta = parse(recs[0])
    existing = find_existing(meta["nbk"])
    if existing and not a.id:
        if not a.quiet: print(f"exists {existing.stem}\t{meta['title']}")
        print(existing.stem) if a.quiet else None
        return
    entry_id = a.id or slugify(meta["title"])
    p = write(entry_id, meta, a.tag)
    print(f"{entry_id}\t{meta['title']}\t{meta['nbk']}\t{', '.join(meta['authors'])}" if not a.quiet else entry_id)


if __name__ == "__main__":
    main()
