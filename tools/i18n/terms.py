#!/usr/bin/env python3
"""Terminology review table for the Turkish edition.

Pulls the Latin and English terms of FIPAT's Terminologia Anatomica 2 (TA2, 2019) and Terminologia
Neuroanatomica (TNA, 2017), the Turkish labels of Wikidata and the titles + redirects of Turkish Wikipedia,
and matches all of them to the atlas's structures, cranial nerves and pathways.  The result is a table the
author checks once, before any Turkish label is written into content/.

  pipeline/.venv/bin/python tools/i18n/terms.py fetch     # FIPAT PDFs -> reference/terms/fipat/, parsed to JSON;
                                                         #   Wikidata items with a TA98/TA2 id; trwiki redirects
  python3 tools/i18n/terms.py table                       # content/i18n/review/terms-review.csv + .md
  python3 tools/i18n/terms.py show substantia-nigra       # every candidate for one entry, with the reasons
  python3 tools/i18n/terms.py --selftest

`fetch` needs pymupdf (in pipeline/.venv) for the PDFs; `table` and `show` only read the cached JSON.
Everything downloaded is cached under the gitignored reference/terms/ and nothing is refetched unless
--refresh is given.

Licences.  The FIPAT PDFs are CC BY-ND 4.0 and are not redistributed; the terms in them are public domain
(FIPAT front matter).  Wikidata is CC0.  Turkish Wikipedia titles and redirects are CC BY-SA 4.0, the same
licence as the atlas content.  The TA2 term numbers are the same numbers Wikidata carries as "TA2 ID"
(P7173), which is how the three sources are joined; TNA has its own numbering and is joined by Latin term.

Table columns (one row per atlas entry):
  kind id name latin                       the atlas entry as it is today
  ta2 ta2_la ta2_en ta2_path               best TA2 term (number, Latin, UK English, ancestors)
  tna tna_la tna_en tna_path               best TNA term
  wd ta98 wd_en wd_tr wd_tr_aliases        Wikidata item, its TA98 code, English and Turkish labels
  trwiki trwiki_redirects                  Turkish Wikipedia article and the titles that redirect to it
  match                                    how each source was matched: latin / en / syn / fuzzy
  alt                                      other candidates the reviewer may prefer (source:id "term")
  note                                     ambiguity or disagreement flags
  decision                                 filled in by the reviewer and kept across regenerations: "ok" to accept
                                           the row as it stands, "ta2:5728" / "tna:1931" / "wd:Q5298925" to pick
                                           another candidate, "none" when FIPAT has no such concept
"""
from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTENT = ROOT / "content" / "data"
CACHE = ROOT / "reference" / "terms"
FIPAT_DIR = CACHE / "fipat"
REVIEW = ROOT / "content" / "i18n" / "review"
UA = "nervous-system-atlas terminology tool (https://github.com/batuhanayci; batuhanayci@gmail.com)"

FIPAT_CDN = "https://cdn.dal.ca/content/dam/dalhousie/pdf/library/FIPAT/"
FIPAT_FILES = {
    "ta2": [f"TA2/FIPAT-TA2-Part-{i}.pdf" for i in range(1, 6)],
    "tna": [f"TNA/FIPAT-TNA-Ch{i}.pdf" for i in range(1, 4)],
}
FIPAT_FRONT = ["TA2/FIPAT-TA2-Front-Matter.pdf", "TNA/FIPAT-TNA-Front-Matter.pdf"]

# Column layout of the FIPAT tables (landscape A4, points).  The header row reads
# "Latin term | Latin synonym | UK English | US English | English synonym | Other".
# Column left edges are 100/214/327/441/554/667 in every part (Part 2 puts Other at 679); a word can start a
# few points before its header's x, so each boundary sits 4 pt to the left of the header.
COLUMNS = [("id", 50, 96), ("la", 96, 210), ("la_syn", 210, 323), ("en_uk", 323, 437),
           ("en_us", 437, 550), ("en_syn", 550, 663), ("other", 663, 900)]
FOOTER_Y = 530          # "FIPAT.library.dal.ca  TA2, Part 5  260" sits below this
INDENT_X0 = 100.0       # x of an unindented Latin term
INDENT_STEP = 5.5       # one hierarchy level of indentation
LINE_TOL = 4.0

KINDS = ("structures", "cranial-nerves", "pathways")
WD_PROPS = {"P1323": "ta98", "P7173": "ta2", "P3982": "ta98_la", "P1402": "fma", "P1554": "uberon",
            "P4394": "neuronames", "P486": "mesh"}


# ------------------------------------------------------------------ cached HTTP ----
def _get(url: str, *, refresh: bool = False, binary: bool = False, pause: float = 0.25):
    key = hashlib.sha1(url.encode()).hexdigest()[:20]
    p = CACHE / "http" / (key + (".bin" if binary else ".json"))
    if p.exists() and not refresh:
        return p.read_bytes() if binary else json.loads(p.read_text())
    time.sleep(pause)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json" if not binary else "*/*"})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            break
        except Exception:
            if attempt == 5:
                raise
            time.sleep(2.0 * (attempt + 1))
    p.parent.mkdir(parents=True, exist_ok=True)
    if binary:
        p.write_bytes(data)
        return data
    d = json.loads(data.decode("utf-8"))
    p.write_text(json.dumps(d, ensure_ascii=False))
    return d


def download_fipat(refresh: bool = False) -> None:
    FIPAT_DIR.mkdir(parents=True, exist_ok=True)
    for rel in FIPAT_FRONT + FIPAT_FILES["ta2"] + FIPAT_FILES["tna"]:
        dest = FIPAT_DIR / Path(rel).name
        if dest.exists() and not refresh:
            continue
        print(f"[fipat] {rel}", file=sys.stderr)
        data = _get(FIPAT_CDN + rel, refresh=refresh, binary=True, pause=1.0)
        dest.write_bytes(data)


# ------------------------------------------------------------------ FIPAT PDF tables ----
def _col(x0: float) -> str:
    for name, lo, hi in COLUMNS:
        if lo <= x0 < hi:
            return name
    return "other"


def _lines(words: list[tuple]) -> list[str]:
    """Group words of one cell into lines (by y), each line read left to right."""
    words = sorted(words, key=lambda w: (round(w[1] / LINE_TOL), w[0]))
    lines: list[list[tuple]] = []
    for w in words:
        if lines and abs(w[1] - lines[-1][0][1]) <= LINE_TOL:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [" ".join(x[4] for x in sorted(l, key=lambda x: x[0])) for l in lines]


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip(" ;,")


def _split_syn(cell: str) -> list[str]:
    return [_clean(x) for x in cell.split(";") if _clean(x)]


def parse_fipat(paths: list[Path], vocab: str) -> list[dict]:
    """Rows of a FIPAT terminology PDF: id, la, la_syn, en_uk, en_us, en_syn, other, depth, chapter, parent."""
    import pymupdf  # noqa: WPS433  (pipeline/.venv)

    rows: list[dict] = []
    chapter = ""
    for path in paths:
        doc = pymupdf.open(path)
        last_id = 0
        for page in doc:
            text = page.get_text()
            # every part/chapter ends with its endnotes, prose whose numbers would read as term numbers
            if re.search(r"^\s*ENDNOTES?\s*$", text, re.M | re.I):
                break
            words = [w for w in page.get_text("words") if w[1] < FOOTER_Y]
            words.sort(key=lambda w: (w[1], w[0]))
            # bold spans mark the heading rows (H levels); their font size ranks the headings
            bold = [(sp["bbox"], sp["size"]) for b in page.get_text("dict")["blocks"] for l in b.get("lines", [])
                    for sp in l["spans"] if sp["flags"] & 16 and sp["text"].strip()]
            m = re.search(r"Caput [IVXL]+: ([^\n]+)\n\s*Chapter (\d+): ([^\n]+)", text)
            next_chapter, caput_y = chapter, None
            if m:
                next_chapter = f"{m.group(2)}: {_clean(m.group(3)).title()}"
                # a chapter may start mid-page: rows above its "Caput" line still belong to the previous one
                caput_y = next((w[1] for w in words if w[4] == "Caput"), None)
                if caput_y is None or caput_y < 100:
                    chapter, caput_y = next_chapter, None
            # id words open a row: numeric, in the id column, first on their line
            ids = [w for w in words if _col(w[0]) == "id" and re.fullmatch(r"\d+", w[4])]
            starts = [w[1] for w in ids]
            # words above the first id: header (chapter start) or the tail of the previous page's row
            head = [w for w in words if not starts or w[1] < starts[0] - 1]
            header_words = {"Latin", "term", "synonym", "UK", "US", "English", "Other", "Caput", "Chapter"}
            is_header = bool(m) or any(w[4] in ("Latin", "Caput") for w in head)
            if head and not is_header and rows:
                _fill(rows[-1], head, cont=True)
            elif head and is_header:
                # a chapter page may still carry the tail of the previous row above the heading; ignore it
                pass
            for k, w in enumerate(ids):
                if int(w[4]) <= last_id:            # numbering restarted: endnotes without a heading
                    break
                last_id = int(w[4])
                y0, y1 = w[1], starts[k + 1] - 1 if k + 1 < len(starts) else FOOTER_Y
                if caput_y is not None and y0 > caput_y:
                    chapter, caput_y = next_chapter, None
                elif caput_y is not None and y1 > caput_y:
                    y1 = caput_y - 1                    # the chapter heading (and its column header) is not a cell
                body = [x for x in words if y0 - 1 <= x[1] < y1 and x is not w]
                row = {"vocab": vocab, "id": int(w[4]), "chapter": chapter, "page": f"{path.name}#{page.number + 1}",
                       "cells": defaultdict(list), "bold": bold}
                _fill(row, body)
                rows.append(row)
    out = []
    for r in rows:
        cells = r.pop("cells")
        bold = r.pop("bold")
        la_lines = _lines(cells.get("la", []))
        la_words = cells.get("la", [])
        top = min((w[1] for w in la_words), default=0)
        first = sorted((w for w in la_words if abs(w[1] - top) <= LINE_TOL), key=lambda w: w[0])
        first_line_x = first[0][0] if first else INDENT_X0
        size = 0.0
        if first:
            cx, cy = (first[0][0] + first[0][2]) / 2, (first[0][1] + first[0][3]) / 2
            for (x0, y0, x1, y1), sz in bold:
                if x0 - 1 <= cx <= x1 + 1 and y0 - 1 <= cy <= y1 + 1:
                    size = max(size, sz)
        r["la"] = _clean(" ".join(la_lines))
        r["la_syn"] = _split_syn(" ".join(_lines(cells.get("la_syn", []))))
        r["en_uk"] = _clean(" ".join(_lines(cells.get("en_uk", []))))
        r["en_us"] = _clean(" ".join(_lines(cells.get("en_us", []))))
        r["en_syn"] = _split_syn(" ".join(_lines(cells.get("en_syn", []))))
        other = " ".join(_lines(cells.get("other", [])))
        r["endnotes"] = [int(n) for n in re.findall(r"Endnote (\d+)", other)]
        r["other"] = _split_syn(re.sub(r"Endnotes? [\d, ]+", "", other))
        r["note"] = _clean(" ".join(_lines(cells.get("id", []))))
        r["depth"] = max(0, round((first_line_x - INDENT_X0) / INDENT_STEP))
        r["heading"] = size > 0
        caps = bool(r["la"]) and r["la"] == r["la"].upper() and any(c.isalpha() for c in r["la"])
        # heading rank: larger font first, then capitalised headings above mixed-case ones
        r["rank"] = (-round(size), 0 if caps else 1) if r["heading"] else None
        if caps:                                       # "TRUNCUS ENCEPHALI" -> "Truncus encephali"
            for k in ("la", "en_uk", "en_us"):
                r[k] = r[k][:1] + r[k][1:].lower()
        out.append(r)
    out = [r for r in out if r["la"] or r["en_uk"] or r["note"]]   # TA2 2259 and TNA 1999 are numbers with no term
    _parents(out)
    return out


def _fill(row: dict, words: list[tuple], cont: bool = False) -> None:
    for w in words:
        row["cells"][_col(w[0])].append(w)


def _parents(rows: list[dict]) -> None:
    """Parent of a heading = the nearest earlier heading of a higher rank (bigger font, or capitals over
    mixed case); parent of a term = the nearest earlier term that is less indented, else the nearest heading."""
    stack: list[dict] = []
    for r in rows:
        if r["heading"]:
            while stack and (not stack[-1]["heading"] or stack[-1]["rank"] >= r["rank"]):
                stack.pop()
        else:
            while stack and not stack[-1]["heading"] and stack[-1]["depth"] >= r["depth"]:
                stack.pop()
        r["parent"] = stack[-1]["id"] if stack else None
        stack.append(r)


def breadcrumb(rows_by_id: dict[int, dict], rid: int, n: int = 3) -> str:
    out, seen = [], set()
    r = rows_by_id.get(rid)
    while r and r.get("parent") is not None and len(out) < n and r["parent"] not in seen:
        seen.add(r["parent"])
        r = rows_by_id.get(r["parent"])
        if r:
            out.append(r["la"].title() if r["heading"] else r["la"])
    return " < ".join(out)


# ------------------------------------------------------------------ Wikidata + trwiki ----
def fetch_wikidata(refresh: bool = False) -> dict[str, dict]:
    q = "SELECT ?i WHERE { { ?i wdt:P1323 ?x } UNION { ?i wdt:P7173 ?y } }"
    url = "https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(q)
    res = _get(url, refresh=refresh, pause=1.0)
    qids = sorted({b["i"]["value"].rsplit("/", 1)[1] for b in res["results"]["bindings"]},
                  key=lambda s: int(s[1:]))
    print(f"[wikidata] {len(qids)} items with a TA98 or TA2 id", file=sys.stderr)
    items: dict[str, dict] = {}
    for k in range(0, len(qids), 50):
        batch = qids[k:k + 50]
        url = ("https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&props=labels|aliases|sitelinks|claims"
               "&languages=en|tr|la&ids=" + "|".join(batch))
        d = _get(url, refresh=refresh)
        for qid, e in d.get("entities", {}).items():
            if "missing" in e:
                continue
            it = {"q": qid}
            for lang in ("en", "tr", "la"):
                if lang in e.get("labels", {}):
                    it[lang] = e["labels"][lang]["value"]
                al = [a["value"] for a in e.get("aliases", {}).get(lang, [])]
                if al:
                    it[lang + "_aliases"] = al
            for wiki in ("enwiki", "trwiki", "lawiki"):
                if wiki in e.get("sitelinks", {}):
                    it[wiki] = e["sitelinks"][wiki]["title"]
            for p, name in WD_PROPS.items():
                vals = [c["mainsnak"].get("datavalue", {}).get("value") for c in e.get("claims", {}).get(p, [])]
                vals = [v for v in vals if isinstance(v, str)]
                if vals:
                    it[name] = vals
            items[qid] = it
        if (k // 50) % 20 == 0:
            print(f"[wikidata] {min(k + 50, len(qids))}/{len(qids)}", file=sys.stderr)
    return items


def fetch_trwiki_redirects(titles: list[str], refresh: bool = False) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    titles = sorted(set(titles))
    for k in range(0, len(titles), 20):
        batch = titles[k:k + 20]
        params = {"action": "query", "prop": "redirects", "rdlimit": "500", "format": "json", "redirects": "1",
                  "titles": "|".join(batch)}
        cont: dict = {}
        while True:
            url = "https://tr.wikipedia.org/w/api.php?" + urllib.parse.urlencode({**params, **cont})
            d = _get(url, refresh=refresh)
            for pg in d.get("query", {}).get("pages", {}).values():
                t = pg.get("title")
                if not t:
                    continue
                out.setdefault(t, [])
                out[t] += [r["title"] for r in pg.get("redirects", [])]
            # a batch title that is itself a redirect is reported under its target
            for r in d.get("query", {}).get("redirects", []):
                out.setdefault(r["to"], [])
                if r["from"] not in out[r["to"]]:
                    out[r["to"]].append(r["from"])
            if "continue" in d:
                cont = d["continue"]
            else:
                break
    return {t: sorted(set(v)) for t, v in out.items()}


# ------------------------------------------------------------------ normalisation + index ----
def norm(s: str) -> str:
    """Matching key: lower-case, ASCII, ae/oe folded, possessives and punctuation dropped."""
    s = unicodedata.normalize("NFKD", s or "").replace("æ", "ae").replace("œ", "oe").replace("ß", "ss")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"'s\b", "", s)
    s = s.replace("ae", "e").replace("oe", "e")
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return re.sub(r"\s+", " ", s)


PLURALS = [("bodies", "body"), ("arteries", "artery"), ("nuclei", "nucleus"), ("gyri", "gyrus"), ("sulci", "sulcus"),
           ("sinuses", "sinus"), ("plexuses", "plexus"), ("ganglia", "ganglion"), ("fasciculi", "fasciculus"),
           ("pedicles", "pedicle"), ("branches", "branch"), ("veins", "vein"), ("nerves", "nerve"), ("tracts", "tract"),
           ("fibres", "fibre"), ("fibers", "fiber"), ("columns", "column"), ("horns", "horn"), ("roots", "root"),
           ("commissures", "commissure"), ("peduncles", "peduncle"), ("colliculi", "colliculus"), ("lobes", "lobe"),
           ("lobules", "lobule"), ("cisterns", "cistern"), ("spaces", "space"), ("granulations", "granulation")]


def name_variants(name: str) -> list[str]:
    """Extra keys for an atlas name: without a bracketed qualifier, without a leading Left/Right, the parts of
    "A and B" / "A, B part" names, and the singular of a plural ("Mammillary bodies" -> "Mammillary body")."""
    out = [name]
    bare = re.sub(r"\s*\(.*?\)", "", name).strip()
    if bare != name:
        out.append(bare)
    for v in list(out):
        m = re.match(r"^(left|right)\s+(.+)$", v, re.I)
        if m and m.group(2) not in out:
            out.append(m.group(2))
    for v in list(out):
        if " and " in v and ":" not in v:
            a, b = [x.strip() for x in v.split(" and ", 1)]
            if len(a.split()) == 1 and len(b.split()) >= 2:
                a = a + " " + " ".join(b.split()[1:])
            out += [x for x in (a, b) if len(x.split()) >= 2 and x not in out]
        m = re.match(r"^(.+?),\s+(.+)$", v)
        if m and m.group(1) not in out:
            out.append(m.group(1))
    for v in list(out):
        for pl, sg in PLURALS:
            if v.lower().endswith(" " + pl) or v.lower() == pl:
                w = v[: len(v) - len(pl)] + sg
                if w not in out:
                    out.append(w)
    return out


PARENT_ADJ = {"hypothalamus": "hypothalamic", "thalamus": "thalamic", "cerebellum": "cerebellar", "pons": "pontine",
              "medulla oblongata": "medullary", "medulla": "medullary", "midbrain": "mesencephalic", "spinal cord": "spinal",
              "hippocampus": "hippocampal", "amygdala": "amygdaloid", "insula": "insular", "cerebral cortex": "cortical",
              "epithalamus": "epithalamic", "subthalamus": "subthalamic", "reticular formation": "reticular"}


def is_abbrev(s: str) -> bool:
    """SMA, V1, PICA, CA1: matched by hand, never automatically (SMA is also the superior mesenteric artery)."""
    t = s.strip()
    return len(t) <= 5 and (t.upper() == t or bool(re.search(r"\d", t)))


class Index:
    def __init__(self):
        self.exact: dict[str, list[tuple[str, str, str]]] = defaultdict(list)   # key -> (source, id, field)
        self.en_keys: dict[str, set[str]] = defaultdict(set)                     # source -> keys for fuzzy
        self.chapter: dict[tuple[str, str], str] = {}                            # (source, id) -> chapter
        self.latin: dict[tuple[str, str], str] = {}                              # (source, id) -> norm(Latin)
        self.path: dict[tuple[str, str], str] = {}                               # (source, id) -> norm(Latin + ancestors)
        self.links: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)   # (source, id) -> [(other, id)]

    def add(self, source: str, rid: str, field: str, term: str, fuzzy: bool = True):
        k = norm(term)
        if not k or is_abbrev(term):
            return
        if (source, rid, field) not in self.exact[k]:
            self.exact[k].append((source, rid, field))
        if fuzzy:
            self.en_keys[source].add(k)


def build_index(ta2: list[dict], tna: list[dict], wd: dict[str, dict]) -> Index:
    ix = Index()
    for rows, src in ((ta2, "ta2"), (tna, "tna")):
        by_id = {r["id"]: r for r in rows}
        for r in rows:
            ix.path[(src, str(r["id"]))] = norm(r["la"] + " " + breadcrumb(by_id, r["id"], 6))
            if r["chapter"].startswith("1: General") or (src == "tna" and r["id"] < 40):
                continue                                   # "Superior", "Medialis", "Tractus": directions and generic nouns
            rid = str(r["id"])
            ix.chapter[(src, rid)] = r["chapter"]
            ix.latin[(src, rid)] = norm(r["la"])
            ix.add(src, rid, "latin", r["la"], fuzzy=False)
            for s in r["la_syn"]:
                ix.add(src, rid, "latin-syn", s, fuzzy=False)
            ix.add(src, rid, "en", r["en_uk"])
            ix.add(src, rid, "en", r["en_us"])
            for s in r["en_syn"]:
                ix.add(src, rid, "syn", s)
            for s in r["other"]:
                if not re.search(r"[A-Z]\d|cell group|^see ", s):
                    ix.add(src, rid, "other", s, fuzzy=False)
    ta2_ids = {str(r["id"]) for r in ta2}
    tna_by_la: dict[str, list[str]] = defaultdict(list)
    for r in tna:
        tna_by_la[norm(r["la"])].append(str(r["id"]))
    for r in ta2:
        for tid in tna_by_la.get(norm(r["la"]), []):
            ix.links[("ta2", str(r["id"]))].append(("tna", tid))
            ix.links[("tna", tid)].append(("ta2", str(r["id"])))
    for q, it in wd.items():
        if it.get("ta98") and all(t.startswith("A01.0") for t in it["ta98"]):
            continue                                       # TA98 general terms
        ix.latin[("wd", q)] = norm((it.get("ta98_la") or [it.get("la", q)])[0])
        ix.path[("wd", q)] = norm(" ".join(it.get("ta98_la", []) + [it.get("en", ""), it.get("la", "")]))
        for t in it.get("ta2", []):
            if t in ta2_ids:
                ix.links[("wd", q)].append(("ta2", t))
                ix.links[("ta2", t)].append(("wd", q))
        if "en" in it:
            ix.add("wd", q, "en", it["en"])
        for s in it.get("en_aliases", []):
            ix.add("wd", q, "syn", s)
        for s in it.get("ta98_la", []):
            ix.add("wd", q, "latin", s, fuzzy=False)
        if "la" in it:
            ix.add("wd", q, "latin-syn", it["la"], fuzzy=False)
    return ix


FIELD_RANK = {"latin": 0, "en": 1, "latin-syn": 2, "syn": 3, "other": 4, "fuzzy": 5}


def candidates(entry: dict, ix: Index) -> dict[str, list[dict]]:
    """Per source, candidates ordered by match quality: [{'id','field','via','score'}]."""
    queries: list[tuple[str, str]] = []                      # (our text, our field)
    for lat in re.split(r"\s*;\s*", entry.get("latin") or ""):
        if lat:
            queries.append((re.sub(r"\s*\(.*?\)", "", lat), "latin"))
    for v in name_variants(entry["name"]):
        queries.append((v, "name"))
    parent = entry.get("parent_name") or ""
    if parent and len(entry["name"].split()) <= 3:        # "Dorsomedial nucleus" under "Hypothalamus"
        for v in name_variants(entry["name"]):
            for pv in name_variants(parent):
                queries.append((f"{v} of {pv.lower()}", "name"))
                queries.append((f"{v} of the {pv.lower()}", "name"))
                queries.append((f"{pv.lower()} {v.lower()}", "name"))
                adj = PARENT_ADJ.get(norm(pv))
                if adj and len(v.split()) >= 2:            # "Dorsomedial hypothalamic nucleus"
                    w = v.split()
                    queries.append((" ".join(w[:-1] + [adj, w[-1]]), "name"))
    for s in entry.get("synonyms") or []:
        if not is_abbrev(s):
            queries.append((s, "synonym"))
    found: dict[str, dict[str, dict]] = defaultdict(dict)
    for text, ours in queries:
        k = norm(text)
        for source, rid, field in ix.exact.get(k, []):
            # a Latin key must be matched by a Latin field, an English key by an English field
            latin_side = ours == "latin" or (ours == "synonym" and _looks_latin(text))
            if latin_side != field.startswith("latin"):
                if not (ours != "latin" and field in ("other",)):
                    continue
            f = field if ours != "synonym" else ("syn" if not field.startswith("latin") else "latin-syn")
            cur = found[source].get(rid)
            if cur is None or FIELD_RANK[f] < FIELD_RANK[cur["field"]]:
                found[source][rid] = {"id": rid, "field": f, "via": text, "score": 1.0}
    # fuzzy fallback on English keys, only when nothing exact turned up for that source
    for source in ("ta2", "tna", "wd"):
        if found[source]:
            continue
        for text, ours in queries:
            if ours == "latin" or _looks_latin(text):
                continue
            k = norm(text)
            if len(k) < 8:
                continue
            for close in difflib.get_close_matches(k, ix.en_keys[source], n=3, cutoff=0.92):
                if _numerals(close) != _numerals(k):   # "lobule ix" is not "lobule ii"
                    continue
                ratio = difflib.SequenceMatcher(None, k, close).ratio()
                for src, rid, field in ix.exact[close]:
                    if src != source:
                        continue
                    cur = found[source].get(rid)
                    if cur is None or ratio > cur["score"]:
                        found[source][rid] = {"id": rid, "field": "fuzzy", "via": f"{text} ~ {close}", "score": round(ratio, 3)}
    # a hit in one source nominates the linked concept in the others (TA2 <-> Wikidata by TA2 number,
    # TA2 <-> TNA by Latin term); candidates named by several sources come first
    for source in ("ta2", "tna", "wd"):
        for c in list(found[source].values()):
            for other, oid in ix.links.get((source, c["id"]), []):
                if oid not in found[other]:
                    found[other][oid] = {"id": oid, "field": c["field"], "via": f"{source} {c['id']}", "score": c["score"] - 0.01,
                                         "linked": True}
    for source in ("ta2", "tna", "wd"):
        for c in found[source].values():
            c["support"] = sum(1 for other, oid in ix.links.get((source, c["id"]), []) if oid in found[other])
    ctx = {t[:7] for t in re.split(r"[-\s]+", (entry["id"] + " " + norm(entry.get("parent_name") or "")).lower()) if len(t) >= 6}
    out = {}
    for source, d in found.items():
        for c in d.values():
            path = ix.path.get((source, c["id"]), "")
            c["context"] = any(t in path for t in ctx)
        cands = sorted(d.values(), key=lambda c: (-c["support"], FIELD_RANK[c["field"]], c.get("linked", False), -c["score"],
                                                  not c["context"],
                                                  0 if ix.chapter.get((source, c["id"]), "").startswith(("14", "1:", "2:", "3:")) else 1,
                                                  int(re.sub(r"\D", "", c["id"]) or 0)))
        seen, uniq = set(), []                       # the same Latin term listed twice (two chapters) is one concept
        for c in cands:
            k = ix.latin.get((source, c["id"]), c["id"])
            if k not in seen:
                seen.add(k)
                uniq.append(c)
        out[source] = uniq
    return out


LATIN_HEADS = set("""nervus nervi nucleus nuclei arteria arteriae vena venae tractus fasciculus fasciculi corpus gyrus gyri
sulcus sulci lobus lobulus pars ramus rami substantia medulla cortex ganglion ganglia plexus commissura capsula fissura
lamina pedunculus colliculus foramen cisterna sinus funiculus columna radix radices truncus striatum thalamus lemniscus
locus cauda falx tentorium area regio fibrae stria striae tela tuber tuberculum insula claustrum putamen pallidum
hippocampus formatio decussatio brachium velum vermis tonsilla flocculus uncus cuneus precuneus fornix septum globus
crus cerebellum cerebrum pons mesencephalon diencephalon telencephalon hypothalamus epithalamus subthalamus infundibulum
hypophysis glandula bulbus chiasma tegmentum operculum polus facies margo dura arachnoidea pia spatium cavum ventriculus
aqueductus canalis filum conus intumescentia segmentum segmenta""".split())
LATIN_ENDINGS = re.compile(r"(us|um|is|ae|orum|arum|ii|alis|aris|icus|ica|icum|ior|ius|es|ium)$")


def _numerals(k: str) -> set[str]:
    return {t for t in k.split() if re.fullmatch(r"[ivx]+[ab]?|\d+[a-z]?", t)}


def _looks_latin(s: str) -> bool:
    """True for a Latin phrase ("Nucleus ruber"), False for English ("red nucleus", "nucleus of abducens nerve")."""
    k = norm(s)
    words = k.split()
    if not words or re.search(r"\b(of|the|and|or|nerve|artery|vein|tract|part|matter|area of)\b", k):
        return False
    if words[0] in LATIN_HEADS:
        return True
    return len(words) >= 2 and sum(1 for w in words if LATIN_ENDINGS.search(w)) >= 2


# ------------------------------------------------------------------ atlas entries ----
def load_entries() -> list[dict]:
    out, names = [], {}
    for kind in KINDS:
        for f in sorted((CONTENT / kind).glob("*.json")):
            d = json.loads(f.read_text())
            names[d["id"]] = d["name"]
            out.append({"kind": kind, "id": d["id"], "name": d["name"], "latin": d.get("latin") or "",
                        "synonyms": d.get("synonyms") or [], "system": d.get("system") or "",
                        "subsystem": d.get("subsystem") or d.get("type") or "", "parent": d.get("parent") or ""})
    for e in out:
        e["parent_name"] = names.get(e["parent"], "")
    return out


# ------------------------------------------------------------------ the table ----
def load_cache() -> tuple[list[dict], list[dict], dict[str, dict], dict[str, list[str]]]:
    def rd(name):
        p = CACHE / name
        if not p.exists():
            raise SystemExit(f"{p} is missing: run `pipeline/.venv/bin/python tools/i18n/terms.py fetch` first")
        return json.loads(p.read_text())
    return rd("fipat_ta2.json"), rd("fipat_tna.json"), rd("wikidata_ta.json"), rd("trwiki_redirects.json")


def resolve(entry: dict, ix: Index, ta2_by: dict, tna_by: dict, wd: dict, wd_by_ta2: dict, wd_by_la: dict,
            tna_by_la: dict, ta2_by_la: dict, redirects: dict) -> dict:
    c = candidates(entry, ix)
    row = {"kind": entry["kind"], "id": entry["id"], "name": entry["name"], "latin": entry["latin"],
           "ta2": "", "ta2_la": "", "ta2_en": "", "ta2_path": "", "tna": "", "tna_la": "", "tna_en": "", "tna_path": "",
           "wd": "", "ta98": "", "wd_en": "", "wd_tr": "", "wd_tr_aliases": "", "trwiki": "", "trwiki_redirects": "",
           "match": "", "alt": "", "note": "", "decision": ""}
    match, alt, notes = [], [], []
    best = {s: (c.get(s) or [None])[0] for s in ("ta2", "tna", "wd")}
    # cross-fill: a TA2 hit names the Wikidata item (P7173) and the TNA row with the same Latin term, and so on
    if best["ta2"] and not best["wd"] and best["ta2"]["id"] in wd_by_ta2:
        best["wd"] = {"id": wd_by_ta2[best["ta2"]["id"]], "field": "via-ta2", "via": best["ta2"]["id"], "score": 1}
    if best["wd"] and not best["ta2"]:
        for t in wd[best["wd"]["id"]].get("ta2", []):
            if t in ta2_by:
                best["ta2"] = {"id": t, "field": "via-wd", "via": best["wd"]["id"], "score": 1}
                break
    if best["ta2"] and not best["tna"]:
        k = norm(ta2_by[best["ta2"]["id"]]["la"])
        if k in tna_by_la:
            best["tna"] = {"id": tna_by_la[k], "field": "via-ta2", "via": best["ta2"]["id"], "score": 1}
    if best["tna"] and not best["ta2"]:
        k = norm(tna_by[best["tna"]["id"]]["la"])
        if k in ta2_by_la:
            best["ta2"] = {"id": ta2_by_la[k], "field": "via-tna", "via": best["tna"]["id"], "score": 1}
            if not best["wd"] and best["ta2"]["id"] in wd_by_ta2:
                best["wd"] = {"id": wd_by_ta2[best["ta2"]["id"]], "field": "via-ta2", "via": best["ta2"]["id"], "score": 1}
    if best["tna"] and not best["wd"]:
        k = norm(tna_by[best["tna"]["id"]]["la"])
        if k in wd_by_la:
            best["wd"] = {"id": wd_by_la[k], "field": "via-latin", "via": tna_by[best["tna"]["id"]]["la"], "score": 1}
    for s in ("ta2", "tna", "wd"):
        b = best[s]
        if not b:
            continue
        match.append(f"{s}:{b['field']}")
        for other in (c.get(s) or [])[1:4]:
            if other["id"] != b["id"]:
                alt.append(f"{s}:{other['id']} \"{_term(s, other['id'], ta2_by, tna_by, wd)}\" ({other['field']})")
        if s == "ta2":
            r = ta2_by[b["id"]]
            row.update(ta2=b["id"], ta2_la=r["la"], ta2_en=r["en_uk"], ta2_path=breadcrumb(ta2_by, int(b["id"])))
        elif s == "tna":
            r = tna_by[b["id"]]
            row.update(tna=b["id"], tna_la=r["la"], tna_en=r["en_uk"], tna_path=breadcrumb(tna_by, int(b["id"])))
        else:
            it = wd[b["id"]]
            row.update(wd=b["id"], ta98=", ".join(it.get("ta98", [])), wd_en=it.get("en", ""), wd_tr=it.get("tr", ""),
                       wd_tr_aliases="; ".join(it.get("tr_aliases", [])), trwiki=it.get("trwiki", ""),
                       trwiki_redirects="; ".join(redirects.get(it.get("trwiki", ""), [])))
    # disagreement flags
    if row["ta2_la"] and row["tna_la"] and norm(row["ta2_la"]) != norm(row["tna_la"]):
        notes.append("TA2/TNA Latin differ")
    if row["latin"] and row["ta2_la"] and norm(row["latin"]) != norm(row["ta2_la"]):
        notes.append("our Latin differs from TA2")
    elif row["latin"] and not row["ta2_la"] and row["tna_la"] and norm(row["latin"]) != norm(row["tna_la"]):
        notes.append("our Latin differs from TNA")
    if row["wd"] and row["ta2"] and row["ta2"] not in wd[row["wd"]].get("ta2", []) and wd[row["wd"]].get("ta2"):
        notes.append(f"Wikidata TA2 id {'/'.join(wd[row['wd']]['ta2'])} is not {row['ta2']}")
    if any(b and b["field"] == "fuzzy" for b in best.values()):
        notes.append("fuzzy")
    if any(len(c.get(s) or []) > 1 and c[s][0]["field"] == c[s][1]["field"] for s in c):
        notes.append("ambiguous")
    if not any(best.values()):
        notes.append("no TA concept found")
    row.update(match=" ".join(match), alt=" | ".join(alt), note="; ".join(notes))
    return row


def _term(source: str, rid: str, ta2_by, tna_by, wd) -> str:
    if source == "ta2":
        return ta2_by[rid]["la"]
    if source == "tna":
        return tna_by[rid]["la"]
    return wd[rid].get("en") or wd[rid].get("la") or rid


def build_table() -> tuple[list[dict], dict]:
    ta2, tna, wd, redirects = load_cache()
    ta2_by = {str(r["id"]): r for r in ta2}
    tna_by = {str(r["id"]): r for r in tna}
    for by in (ta2_by, tna_by):                       # breadcrumb() walks int ids
        by.update({int(k): v for k, v in list(by.items())})
    wd_by_ta2 = {t: q for q, it in wd.items() for t in it.get("ta2", [])}
    wd_by_la = {}
    for q, it in wd.items():
        for s in it.get("ta98_la", []) + ([it["la"]] if "la" in it else []):
            wd_by_la.setdefault(norm(s), q)
    tna_by_la = {norm(r["la"]): str(r["id"]) for r in reversed(tna) if r["la"]}
    ta2_by_la = {norm(r["la"]): str(r["id"]) for r in reversed(ta2) if r["la"]}
    ix = build_index(ta2, tna, wd)
    rows = [resolve(e, ix, ta2_by, tna_by, wd, wd_by_ta2, wd_by_la, tna_by_la, ta2_by_la, redirects)
            for e in load_entries()]
    stats = {
        "entries": len(rows),
        "ta2": sum(1 for r in rows if r["ta2"]), "tna": sum(1 for r in rows if r["tna"]),
        "wd": sum(1 for r in rows if r["wd"]), "wd_tr": sum(1 for r in rows if r["wd_tr"]),
        "trwiki": sum(1 for r in rows if r["trwiki"]),
        "any_tr": sum(1 for r in rows if r["wd_tr"] or r["trwiki"]),
        "latin_any": sum(1 for r in rows if r["ta2_la"] or r["tna_la"]),
        "none": sum(1 for r in rows if "no TA concept" in r["note"]),
        "fuzzy": sum(1 for r in rows if "fuzzy" in r["note"]),
        "ambiguous": sum(1 for r in rows if "ambiguous" in r["note"]),
        "latin_differs": sum(1 for r in rows if "our Latin differs" in r["note"]),
        "sources": {"ta2_rows": len(ta2), "tna_rows": len(tna), "wd_items": len(wd),
                    "wd_tr_labels": sum(1 for it in wd.values() if "tr" in it),
                    "wd_trwiki": sum(1 for it in wd.values() if "trwiki" in it)},
    }
    return rows, stats


def write_table(rows: list[dict], stats: dict) -> None:
    REVIEW.mkdir(parents=True, exist_ok=True)
    cols = list(rows[0].keys())
    old = REVIEW / "terms-review.csv"
    if old.exists():                                        # the reviewer's decisions survive a rebuild
        with old.open(newline="") as f:
            decided = {r["id"]: r.get("decision", "") for r in csv.DictReader(f)}
        for r in rows:
            r["decision"] = decided.get(r["id"], "")
    stats["decided"] = sum(1 for r in rows if r["decision"])
    with (REVIEW / "terms-review.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    entries = load_entries()
    by_kind = Counter((e["kind"], e["subsystem"]) for e in entries)
    L = ["# Terminology review table", "",
         "Generated by `tools/i18n/terms.py table`; the reviewed columns are in `terms-review.csv` next to this file. "
         "One row per structure, cranial nerve and pathway: its best FIPAT TA2 and TNA term, the Wikidata item "
         "(joined by TA2 number, then by Latin term) with its Turkish label, and the Turkish Wikipedia article with "
         "the titles that redirect to it. Nothing here is applied to `content/` yet.", "",
         "| | count |", "|---|---|",
         f"| atlas entries | {stats['entries']} |",
         f"| with a TA2 term | {stats['ta2']} |",
         f"| with a TNA term | {stats['tna']} |",
         f"| with a Latin term from either | {stats['latin_any']} |",
         f"| with a Wikidata item | {stats['wd']} |",
         f"| with a Wikidata Turkish label | {stats['wd_tr']} |",
         f"| with a Turkish Wikipedia article | {stats['trwiki']} |",
         f"| with any Turkish name | {stats['any_tr']} |",
         f"| no TA concept found (to be named by hand) | {stats['none']} |",
         f"| fuzzy matches to check | {stats['fuzzy']} |",
         f"| ambiguous (several equal candidates) | {stats['ambiguous']} |",
         f"| our `latin` differs from FIPAT | {stats['latin_differs']} |",
         f"| rows with a reviewer decision | {stats['decided']} |", "",
         f"Sources: TA2 {stats['sources']['ta2_rows']} rows, TNA {stats['sources']['tna_rows']} rows, "
         f"Wikidata {stats['sources']['wd_items']} items with a TA98/TA2 id "
         f"({stats['sources']['wd_tr_labels']} with a Turkish label, {stats['sources']['wd_trwiki']} with a Turkish article).", ""]
    L += ["## Coverage by group", "", "| kind | group | entries | TA2 | TNA | Turkish name |", "|---|---|---|---|---|---|"]
    rb = {r["id"]: r for r in rows}
    for (kind, sub), n in sorted(by_kind.items()):
        ids = [e["id"] for e in entries if e["kind"] == kind and e["subsystem"] == sub]
        L.append(f"| {kind} | {sub or '-'} | {n} | {sum(1 for i in ids if rb[i]['ta2'])} | {sum(1 for i in ids if rb[i]['tna'])} | "
                 f"{sum(1 for i in ids if rb[i]['wd_tr'] or rb[i]['trwiki'])} |")
    L += ["", "## Rows to look at first", ""]
    for title, pred in (("Our Latin differs from FIPAT", lambda r: "our Latin differs" in r["note"]),
                        ("TA2 and TNA Latin differ", lambda r: "TA2/TNA Latin differ" in r["note"]),
                        ("Fuzzy matches", lambda r: "fuzzy" in r["note"]),
                        ("Ambiguous", lambda r: "ambiguous" in r["note"])):
        sel = [r for r in rows if pred(r)]
        L += [f"### {title} ({len(sel)})", ""]
        for r in sel:
            L.append(f"- `{r['id']}` {r['name']}" + (f" — ours *{r['latin']}*" if r["latin"] else "") +
                     (f"; TA2 {r['ta2']} *{r['ta2_la']}*" if r["ta2"] else "") +
                     (f"; TNA {r['tna']} *{r['tna_la']}*" if r["tna"] else "") +
                     (f"; alt: {r['alt']}" if r["alt"] else ""))
        L.append("")
    sel = [r for r in rows if "no TA concept" in r["note"]]
    L += [f"### No TA concept found ({len(sel)})", "", "Territories, composite meshes, clinical regions and pathways "
          "that FIPAT does not name; their Turkish names will be authored.", ""]
    for r in sel:
        L.append(f"- `{r['id']}` {r['name']}")
    L.append("")
    (REVIEW / "terms-review.md").write_text("\n".join(L))
    print(f"wrote {REVIEW / 'terms-review.csv'} ({len(rows)} rows) and terms-review.md")
    for k in ("entries", "ta2", "tna", "latin_any", "wd", "wd_tr", "trwiki", "any_tr", "none", "fuzzy", "ambiguous", "latin_differs"):
        print(f"  {k:14s} {stats[k]}")


# ------------------------------------------------------------------ commands ----
def cmd_fetch(a) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    download_fipat(a.refresh)
    for vocab in ("ta2", "tna"):
        paths = [FIPAT_DIR / Path(r).name for r in FIPAT_FILES[vocab]]
        rows = parse_fipat(paths, vocab)
        (CACHE / f"fipat_{vocab}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=0))
        print(f"[fipat] {vocab}: {len(rows)} rows, {sum(1 for r in rows if r['heading'])} headings, "
              f"{sum(1 for r in rows if not r['la'])} rows without a Latin term", file=sys.stderr)
    wd = fetch_wikidata(a.refresh)
    (CACHE / "wikidata_ta.json").write_text(json.dumps(wd, ensure_ascii=False, indent=0))
    titles = [it["trwiki"] for it in wd.values() if "trwiki" in it]
    print(f"[trwiki] redirects for {len(titles)} articles", file=sys.stderr)
    red = fetch_trwiki_redirects(titles, a.refresh)
    (CACHE / "trwiki_redirects.json").write_text(json.dumps(red, ensure_ascii=False, indent=0))
    print(f"[trwiki] {sum(len(v) for v in red.values())} redirects", file=sys.stderr)


def cmd_table(a) -> None:
    rows, stats = build_table()
    write_table(rows, stats)


def cmd_show(a) -> None:
    ta2, tna, wd, redirects = load_cache()
    ix = build_index(ta2, tna, wd)
    ta2_by = {str(r["id"]): r for r in ta2}
    tna_by = {str(r["id"]): r for r in tna}
    entry = next((e for e in load_entries() if e["id"] == a.id), None)
    if not entry:
        raise SystemExit(f"no entry {a.id}")
    print(json.dumps(entry, ensure_ascii=False))
    for source, cands in candidates(entry, ix).items():
        for c in cands:
            if source == "ta2":
                r = ta2_by[c["id"]]; desc = f"{r['la']} | {r['en_uk']} | syn {r['en_syn']} | {r['chapter']}"
            elif source == "tna":
                r = tna_by[c["id"]]; desc = f"{r['la']} | {r['en_uk']} | syn {r['en_syn']} | {r['chapter']}"
            else:
                it = wd[c["id"]]; desc = f"{it.get('en')} | tr {it.get('tr')} | trwiki {it.get('trwiki')} | ta98 {it.get('ta98')} ta2 {it.get('ta2')}"
            print(f"  {source:4s} {c['id']:>8s} {c['field']:10s} {c['score']:<5} support {c['support']} {'ctx ' if c['context'] else '    '}via {c['via']!r}: {desc}")
    rows, _ = build_table()
    print(json.dumps(next(r for r in rows if r["id"] == a.id), ensure_ascii=False, indent=1))


def selftest() -> None:
    assert norm("Nucleus nervi abducentis") == "nucleus nervi abducentis"
    assert norm("Broca's area") == "broca area"
    assert norm("Praecuneus") == norm("Precuneus") == norm("precuneus")
    assert norm("Hemisphaerii cerebri") == norm("hemispherii cerebri")
    assert norm("Locus cœruleus") == norm("locus ceruleus")
    assert _looks_latin("Nucleus ruber") and not _looks_latin("red nucleus") and not _looks_latin("nucleus of abducens nerve")
    assert name_variants("Left cerebral hemisphere (MRA)")[:2] == ["Left cerebral hemisphere (MRA)", "Left cerebral hemisphere"]
    assert "cerebral hemisphere" in name_variants("Left cerebral hemisphere (MRA)")
    assert "Mammillary body" in name_variants("Mammillary bodies")
    assert name_variants("Medullary pyramid and pyramidal decussation")[1:] == ["Medullary pyramid", "pyramidal decussation"]
    v = name_variants("Superior and inferior petrosal sinuses")
    assert v[1:3] == ["Superior petrosal sinuses", "inferior petrosal sinuses"] and "inferior petrosal sinus" in v, v
    assert "Middle temporal gyrus" in name_variants("Middle temporal gyrus, posterior division")
    assert is_abbrev("SMA") and is_abbrev("V1") and is_abbrev("CA1") and not is_abbrev("Pons") and not is_abbrev("Broca")
    assert _numerals("lobule ix") == {"ix"} and _numerals("lobule viiia") == {"viiia"} and _numerals("cuneiform 2") == {"2"}
    # row assembly: a synthetic page of words (x0, y0, x1, y1, text)
    words = [(72, 73, 87, 82, "5881"), (106, 73, 137, 82, "Substantia"), (139, 73, 153, 82, "nigra"),
             (333, 73, 364, 82, "Substantia"), (365, 73, 380, 82, "nigra"), (446, 73, 477, 82, "Substantia"),
             (479, 73, 493, 82, "nigra"), (667, 73, 691, 82, "Nucleus"), (693, 73, 708, 82, "niger"),
             (667, 82, 692, 91, "Endnote"), (694, 82, 704, 91, "854"),
             (72, 92, 87, 101, "5882"), (111, 92, 125, 101, "Pars"), (127, 92, 155, 101, "compacta"),
             (157, 92, 190, 101, "substantiae"), (100, 101, 119, 110, "nigrae"),
             (338, 92, 364, 101, "Compact"), (366, 92, 377, 101, "part"), (379, 92, 385, 101, "of"),
             (387, 92, 416, 101, "substantia"), (327, 101, 342, 110, "nigra"),
             (554, 92, 600, 101, "Compact"), (601, 92, 640, 101, "SN;"), (554, 101, 590, 110, "SNc")]
    cells = defaultdict(list)
    for w in words[1:11]:
        cells[_col(w[0])].append(w)
    assert _clean(" ".join(_lines(cells["la"]))) == "Substantia nigra"
    assert _split_syn(re.sub(r"Endnotes? [\d, ]+", "", " ".join(_lines(cells["other"])))) == ["Nucleus niger"]
    cells = defaultdict(list)
    for w in words[12:]:
        cells[_col(w[0])].append(w)
    assert _clean(" ".join(_lines(cells["la"]))) == "Pars compacta substantiae nigrae"
    assert _clean(" ".join(_lines(cells["en_uk"]))) == "Compact part of substantia nigra"
    assert _split_syn(" ".join(_lines(cells["en_syn"]))) == ["Compact SN", "SNc"]
    H, T = (lambda i, rank: {"id": i, "depth": 0, "heading": True, "rank": rank}), (lambda i, d: {"id": i, "depth": d, "heading": False, "rank": None})
    rows = [H(1, (-10, 1)), H(2, (-8, 0)), T(3, 0), T(4, 1), T(5, 2), T(6, 1), H(7, (-8, 0)), T(8, 0), H(9, (-10, 1)), T(10, 0)]
    _parents(rows)
    assert [r["parent"] for r in rows] == [None, 1, 2, 3, 4, 3, 1, 7, None, 9], [r["parent"] for r in rows]
    print("selftest ok")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--selftest", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    f = sub.add_parser("fetch", help="download and parse the FIPAT PDFs, pull Wikidata and Turkish Wikipedia")
    f.add_argument("--refresh", action="store_true", help="refetch everything instead of using reference/terms/")
    sub.add_parser("table", help="write content/i18n/review/terms-review.csv and .md")
    s = sub.add_parser("show", help="print every candidate for one atlas entry")
    s.add_argument("id")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.cmd == "fetch":
        return cmd_fetch(a)
    if a.cmd == "table":
        return cmd_table(a)
    if a.cmd == "show":
        return cmd_show(a)
    ap.print_help()


if __name__ == "__main__":
    main()
