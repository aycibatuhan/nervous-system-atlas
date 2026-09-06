#!/usr/bin/env python3
"""Build reference/index.json: chapters and sections (detected headings) of the private plagiarism-check corpus.

Private tooling: it reads PDFs under source/ (never committed) and writes reference/ (gitignored). The atlas
itself cites only the open-access bibliography in content/bibliography/ — see tools/cite/."""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from refcorpus import BOOKS, REF, ROOT, chapter_ranges, clean_pages

index = {"books": {}, "chapters": {}}
for book, b in BOOKS.items():
    index["books"][book] = {"file": str(b["file"].relative_to(ROOT)), "cite": b["cite"], "title": b["title"],
                            "pdfOffset": b["pdfOffset"], "pages": b["pages"]}
    pages = clean_pages(book)
    chapters = []
    for n, (s, e) in chapter_ranges(book).items():
        sections = []
        for p in range(s, e + 1):
            for line in pages.get(p, "").splitlines():
                t = line.strip()
                # headings: short Title-Case lines without terminal punctuation
                if 3 < len(t) < 70 and not t.endswith((".", ",", ";", ":")) and not t.startswith("[FIG]") \
                        and re.match(r"^[A-Z][A-Za-z0-9’'(),/ -]+$", t) and sum(w[0].isupper() for w in t.split() if w[0].isalpha()) >= max(1, len(t.split()) * 0.6):
                    if len(sections) == 0 or sections[-1]["title"] != t:
                        sections.append({"title": t, "page": p})
        ch = {"n": n, "title": b["chapterTitles"].get(n, ""), "printed": [s, e], "sections": sections[:80]}
        if book == "snell":
            ch["clinicalNotes"] = b["clinicalNotes"].get(n); ch["problemSolving"] = b["problemSolving"].get(n)
        chapters.append(ch)
    index["chapters"][book] = chapters

(REF / "index.json").write_text(json.dumps(index, indent=1))
print("wrote", REF / "index.json", "chapters:", {k: len(v) for k, v in index["chapters"].items()})
