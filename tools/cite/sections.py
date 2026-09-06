#!/usr/bin/env python3
"""Fetch the real section headings of an NCBI Bookshelf chapter, so `section` is never invented.

Cached under reference/section-cache/ (gitignored).  python3 tools/cite/sections.py NBK542170
"""
import html, json, re, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "reference" / "section-cache"
UA = {"User-Agent": "nervous-system-atlas citation checker (+local build)"}
_lock = threading.Lock()
_last = [0.0]
H2 = re.compile(r"<h2[^>]*>(.*?)</h2>", re.S | re.I)


def _throttle():
    with _lock:
        dt = time.time() - _last[0]
        if dt < 0.5:
            time.sleep(0.5 - dt)
        _last[0] = time.time()


def headings(nbk: str) -> list[str]:
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f"{nbk}.json"
    if p.exists():
        return json.loads(p.read_text())
    _throttle()
    out: list[str] = []
    try:
        req = urllib.request.Request(f"https://www.ncbi.nlm.nih.gov/books/{nbk}/", headers=UA)
        with urllib.request.urlopen(req, timeout=45) as r:
            body = r.read().decode("utf-8", "replace")
        for m in H2.findall(body):
            t = html.unescape(re.sub(r"<[^>]+>", " ", m))
            t = re.sub(r"\s+", " ", t).strip()
            if t and len(t) < 80 and t.lower() not in {"navigation menu", "search", "related information"}:
                out.append(t)
        seen, uniq = set(), []
        for t in out:
            if t not in seen:
                seen.add(t)
                uniq.append(t)
        out = uniq
    except Exception as e:
        print(f"  headings failed {nbk}: {e}", file=sys.stderr)
        return []
    p.write_text(json.dumps(out))
    return out


def warm(nbks: list[str], workers: int = 2) -> None:
    todo = [n for n in dict.fromkeys(nbks) if not (CACHE / f"{n}.json").exists()]
    if not todo:
        return
    done = [0]

    def one(n):
        headings(n)
        done[0] += 1
        if done[0] % 25 == 0:
            print(f"  sections {done[0]}/{len(todo)}", flush=True)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(one, todo))


if __name__ == "__main__":
    for n in sys.argv[1:]:
        print(n, headings(n))
