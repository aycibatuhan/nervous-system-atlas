#!/usr/bin/env python3
"""Open-access fallbacks for the bibliography: PMC articles and verified open-textbook / web pages.

  python3 tools/cite/oa.py --pmc-search "claustrum review"        # list candidate open-access articles
  python3 tools/cite/oa.py --pmcid PMC5695711 --id oa-claustrum   # add a verified PMC article
  python3 tools/cite/oa.py --doi 10.1007/s00429-019-01919-4 --id oa-venat-atlas    # verify via Crossref (paywalled: no license, publisher URL)
  python3 tools/cite/oa.py --web https://openstax.org/books/anatomy-and-physiology-2e/pages/14-1-sensory-perception \
      --id ox-sensory-perception --title "Sensory Perception" --authors "OpenStax" --year 2022 \
      --container "Anatomy and Physiology 2e" --license "CC BY 4.0"

Nothing is written unless the record was confirmed: PMC entries come from the live esummary record,
web/book entries are only written after the URL returns HTTP 200, and --doi entries come from the live
Crossref record (a licence is written only when Crossref reports a Creative Commons one).
"""
import argparse, datetime, json, re, sys, urllib.parse, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import ncbi

ROOT = Path(__file__).resolve().parents[2]
BIB = ROOT / "content" / "bibliography"
UA = {"User-Agent": "nervous-system-atlas citation checker (+local build)"}


def pmc_search(query: str, n: int = 10) -> list[dict]:
    ids = ncbi.esearch("pmc", f"{query} AND open access[filter]", retmax=n)
    out = []
    for r in ncbi.esummary("pmc", ids):
        out.append(parse_pmc(r))
    return [x for x in out if x]


def parse_pmc(rec: dict) -> dict | None:
    pmcid = rec.get("uid")
    for aid in rec.get("articleids", []):
        if aid.get("idtype") == "pmcid":
            pmcid = aid["value"].replace("pmc-id: ", "").strip().rstrip(";")
    if not pmcid:
        return None
    pmcid = pmcid if str(pmcid).startswith("PMC") else f"PMC{pmcid}"
    doi = next((a["value"] for a in rec.get("articleids", []) if a.get("idtype") == "doi"), None)
    pmid = next((a["value"] for a in rec.get("articleids", []) if a.get("idtype") == "pmid"), None)
    year = re.search(r"\d{4}", rec.get("pubdate", "") or rec.get("epubdate", "") or "")
    return {
        "pmcid": pmcid, "doi": doi, "pmid": pmid,
        "title": re.sub(r"<[^>]+>", "", rec.get("title", "")).rstrip("."),
        "authors": [a["name"] for a in rec.get("authors", []) if a.get("authtype") == "Author"],
        "year": int(year.group()) if year else datetime.date.today().year,
        "container": rec.get("fulljournalname") or rec.get("source", "PMC"),
        "url": f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/",
    }


CROSSREF = "https://api.crossref.org/works/"


def crossref(doi: str) -> dict:
    """Live Crossref record for a DOI; raises if the DOI does not resolve."""
    req = urllib.request.Request(CROSSREF + urllib.parse.quote(doi), headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["message"]


def _initials(given: str) -> str:
    return "".join(w[0] for w in re.split(r"[\s.\-]+", given) if w)


def parse_crossref(m: dict) -> dict:
    title = (m.get("title") or [""])[0]
    authors = []
    for a in m.get("author", []):
        name = " ".join(x for x in [a.get("family", ""), _initials(a.get("given", ""))] if x)
        if name:
            authors.append(name)
    parts = (m.get("issued", {}).get("date-parts") or [[None]])[0]
    lic = next((l.get("URL", "") for l in m.get("license", []) if "creativecommons.org" in l.get("URL", "")), None)
    return {
        "title": re.sub(r"<[^>]+>", "", title).rstrip("."),
        "authors": authors,
        "year": parts[0] if parts and parts[0] else datetime.date.today().year,
        "container": (m.get("container-title") or [""])[0],
        "url": m.get("URL", ""),
        "license": lic,
    }


def add_doi(doi: str, entry_id: str, tags: list[str], url: str | None = None) -> Path:
    """Add a journal entry verified against the live Crossref record.

    Used for the few sources that are not in PMC at all: the entry keeps its DOI and a publisher URL,
    and carries a licence only when Crossref reports a Creative Commons one (paywalled records get none).
    """
    meta = parse_crossref(crossref(doi))
    if not meta["title"] or not meta["authors"]:
        raise SystemExit(f"Crossref record incomplete, refusing to mark verified: {doi}")
    entry = {"id": entry_id, "type": "journal", "title": meta["title"], "authors": meta["authors"],
             "year": meta["year"], "container": meta["container"] or "n/a", "url": url or meta["url"],
             "doi": doi, "accessed": datetime.date.today().isoformat(), "verified": True, "tags": tags}
    if meta["license"]:
        entry["license"] = meta["license"]
    pmids = ncbi.esearch("pubmed", f"{doi}[DOI]", retmax=2)
    if len(pmids) == 1:
        entry["pmid"] = pmids[0]
    return write(entry)


def url_ok(url: str) -> bool:
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status == 200
    except Exception:
        return False


def write(entry: dict) -> Path:
    BIB.mkdir(parents=True, exist_ok=True)
    p = BIB / f"{entry['id']}.json"
    p.write_text(json.dumps(entry, indent=2, ensure_ascii=False) + "\n")
    return p


def add_pmc(pmcid: str, entry_id: str, tags: list[str]) -> Path:
    rec = ncbi.esummary("pmc", [pmcid.replace("PMC", "")])
    meta = parse_pmc(rec[0]) if rec else None
    if not meta:
        raise SystemExit(f"PMC record not found: {pmcid}")
    entry = {"id": entry_id, "type": "journal", "title": meta["title"], "authors": meta["authors"] or ["PMC"],
             "year": meta["year"], "container": meta["container"], "url": meta["url"], "pmcid": meta["pmcid"],
             "license": "open access (PMC)", "accessed": datetime.date.today().isoformat(), "verified": True, "tags": tags}
    if meta["doi"]:
        entry["doi"] = meta["doi"]
    if meta["pmid"]:
        entry["pmid"] = meta["pmid"]
    return write(entry)


def add_web(url: str, entry_id: str, title: str, authors: list[str], year: int, container: str,
            kind: str, license_: str | None, tags: list[str]) -> Path:
    if not url_ok(url):
        raise SystemExit(f"URL did not return 200, refusing to mark verified: {url}")
    entry = {"id": entry_id, "type": kind, "title": title, "authors": authors, "year": year,
             "container": container, "url": url, "accessed": datetime.date.today().isoformat(),
             "verified": True, "tags": tags}
    if license_:
        entry["license"] = license_
    return write(entry)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pmc-search")
    ap.add_argument("--pmcid")
    ap.add_argument("--doi")
    ap.add_argument("--web")
    ap.add_argument("--url", help="publisher URL for a --doi entry (default: the Crossref DOI link)")
    ap.add_argument("--id")
    ap.add_argument("--title")
    ap.add_argument("--authors", default="")
    ap.add_argument("--year", type=int, default=datetime.date.today().year)
    ap.add_argument("--container", default="")
    ap.add_argument("--kind", default="web", choices=["web", "book"])
    ap.add_argument("--license")
    ap.add_argument("--tag", action="append", default=[])
    a = ap.parse_args()
    if a.pmc_search:
        for m in pmc_search(a.pmc_search):
            print(f"{m['pmcid']}\t{m['year']}\t{m['container'][:34]:34s}\t{m['title'][:90]}")
    elif a.pmcid:
        print(add_pmc(a.pmcid, a.id or a.pmcid.lower(), a.tag))
    elif a.doi:
        print(add_doi(a.doi, a.id or a.doi.replace("/", "-"), a.tag, a.url))
    elif a.web:
        print(add_web(a.web, a.id, a.title, [x.strip() for x in a.authors.split(";") if x.strip()],
                      a.year, a.container, a.kind, a.license, a.tag))
    else:
        ap.error("one of --pmc-search / --pmcid / --doi / --web required")
