#!/usr/bin/env python3
"""Print clean reference text for a printed page range.  usage: ref_pages.py <snell|berkowitz> <from>[-<to>]"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from refcorpus import clean_pages, chapter_of, BOOKS

book, rng = sys.argv[1], sys.argv[2]
a, _, b = rng.partition("-")
a = int(a); b = int(b) if b else a
pages = clean_pages(book)
for p in range(a, b + 1):
    ch = chapter_of(book, p)
    title = BOOKS[book]["chapterTitles"].get(ch, "")
    print(f"\n===== {BOOKS[book]['cite']} p.{p}  (ch. {ch}: {title}) =====")
    print(pages.get(p, "<no text>"))
