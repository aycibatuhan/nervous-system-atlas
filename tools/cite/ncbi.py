#!/usr/bin/env python3
"""Shared, cached NCBI E-utilities client for the citation tooling.

Every network response is cached under reference/cite-cache/ (gitignored) so reruns are free.
Rate limited to <=3 requests/s as required by the public E-utilities.
"""
import hashlib, json, re, sys, threading, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "reference" / "cite-cache"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
_last = [0.0]
_lock = threading.Lock()


def _sleep():
    """Global token bucket: at most 3 requests/s, the public E-utilities limit."""
    with _lock:
        dt = time.time() - _last[0]
        if dt < 0.5:
            time.sleep(0.5 - dt)
        _last[0] = time.time()


def get_json(url: str, *, cache: bool = True):
    key = hashlib.sha1(url.encode()).hexdigest()[:20]
    p = CACHE / f"{key}.json"
    if cache and p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    _sleep()
    for attempt in range(6):
        try:
            with urllib.request.urlopen(url, timeout=45) as r:
                d = json.load(r)
            break
        except Exception:                          # transient NCBI 429/500
            if attempt == 5:
                raise
            time.sleep(2.0 * (attempt + 1))
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d))
    return d


def cache_path(url: str) -> Path:
    return CACHE / f"{hashlib.sha1(url.encode()).hexdigest()[:20]}.json"


def prefetch(urls: list[str], workers: int = 2, progress: str = "") -> None:
    """Warm the cache for many URLs at once, still respecting the 3 req/s cap."""
    todo = [u for u in dict.fromkeys(urls) if not cache_path(u).exists()]
    if not todo:
        return
    done = [0]

    def one(u):
        try:
            get_json(u)
        except Exception as e:
            print(f"  prefetch failed: {e}", file=sys.stderr)
        done[0] += 1
        if progress and done[0] % 50 == 0:
            print(f"  {progress} {done[0]}/{len(todo)}", file=sys.stderr, flush=True)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(one, todo))


def search_url(db: str, term: str, retmax: int = 200, retstart: int = 0) -> str:
    return f"{EUTILS}esearch.fcgi?db={db}&term={urllib.parse.quote(term)}&retmax={retmax}&retstart={retstart}&retmode=json"


def esearch(db: str, term: str, retmax: int = 200, retstart: int = 0) -> list[str]:
    d = get_json(search_url(db, term, retmax, retstart))
    return d["esearchresult"].get("idlist", [])


def esearch_all(db: str, term: str, cap: int = 2000) -> list[str]:
    out, start = [], 0
    while start < cap:
        got = esearch(db, term, 200, start)
        out += got
        if len(got) < 200:
            break
        start += 200
    return out


def summary_url(db: str, uids: list[str]) -> str:
    return f"{EUTILS}esummary.fcgi?db={db}&id={','.join(uids)}&retmode=json"


def esummary(db: str, uids: list[str]) -> list[dict]:
    out = []
    chunks = [uids[i:i + 100] for i in range(0, len(uids), 100)]
    prefetch([summary_url(db, c) for c in chunks], progress="esummary")
    for chunk in chunks:
        d = get_json(summary_url(db, chunk))["result"]
        for u in d.get("uids", []):
            out.append(d[u])
    return out


CONTRIB = re.compile(r"<Contributors>(.*?)</Contributors>", re.S)


def parse_book(rec: dict) -> dict | None:
    """Normalise a db=books esummary chapter record."""
    if rec.get("rtype") != "chapter":
        return None
    info = rec.get("bookinfo", "")
    m = CONTRIB.search(info)
    authors = [c.strip().rstrip(".") for c in m.group(1).split(",")] if m else []
    authors = [a for a in authors if a]
    pub = rec.get("pubdate") or ""
    year = int(pub[:4]) if pub[:4].isdigit() else 2025
    return {
        "title": (rec.get("title") or "").rstrip("."),
        "authors": authors,
        "year": year,
        "nbk": rec.get("chapteraccessionid", ""),
        "book": rec.get("book", ""),
    }
