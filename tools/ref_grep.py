#!/usr/bin/env python3
"""Search the clean corpus.  usage: ref_grep.py [-b snell|berkowitz] [-C n] <regex>
Prints book, printed page, chapter and the matching line (with n lines of context)."""
import argparse, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from refcorpus import clean_pages, chapter_of, BOOKS

ap = argparse.ArgumentParser(); ap.add_argument("-b", "--book"); ap.add_argument("-C", type=int, default=0); ap.add_argument("-m", "--max", type=int, default=60)
ap.add_argument("pattern")
a = ap.parse_args()
pat = re.compile(a.pattern, re.I)
n = 0
for book in ([a.book] if a.book else ["snell", "berkowitz"]):
    for p, text in sorted(clean_pages(book).items()):
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if pat.search(line):
                n += 1
                if n > a.max:
                    print(f"... more than {a.max} hits, refine the pattern"); sys.exit(0)
                ctx = lines[max(0, i - a.C): i + a.C + 1]
                print(f"[{BOOKS[book]['cite']} p.{p} ch.{chapter_of(book, p)}] " + " / ".join(l.strip() for l in ctx))
