#!/usr/bin/env python3
"""Build reference/index.json: chapters, sections (detected headings) and topics (from content/coverage.json)."""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from refcorpus import BOOKS, REF, ROOT, chapter_ranges, clean_pages

index = {"books": {}, "chapters": {}, "topics": {}}
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

cov = ROOT / "content" / "coverage.json"
if cov.exists():
    for entry in json.loads(cov.read_text()).get("entries", []):
        src = entry.get("sources", {})
        index["topics"][entry["id"]] = {"kind": entry["kind"], "snell": src.get("snell", []), "berkowitz": src.get("berkowitz", []),
                                        "coveredBy": [k for k in ("snell", "berkowitz") if src.get(k)]}
(REF / "index.json").write_text(json.dumps(index, indent=1))
print("wrote", REF / "index.json", "chapters:", {k: len(v) for k, v in index["chapters"].items()}, "topics:", len(index["topics"]))
