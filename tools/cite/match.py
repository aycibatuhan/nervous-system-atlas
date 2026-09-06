#!/usr/bin/env python3
"""Score StatPearls catalog titles against an atlas entry and rank candidates."""
import json, math, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import catalog

STOP = {"the", "of", "and", "a", "an", "in", "to", "part", "left", "right", "s"}
IRREGULAR = {"nuclei": "nucleus", "gyri": "gyrus", "sulci": "sulcus", "ganglia": "ganglion",
             "cortices": "cortex", "fasciculi": "fasciculus", "lemnisci": "lemniscus", "plexi": "plexus",
             "arteries": "artery", "veins": "vein", "sinuses": "sinus", "nerves": "nerve", "bodies": "body",
             "areas": "area", "tracts": "tract", "lobes": "lobe", "fibers": "fiber", "fibres": "fiber"}
# words that only say what *kind* of thing this is collapse onto one token, so that "Cingulate gyrus"
# matches "Neuroanatomy, Cingulate Cortex" — but "Frontal lobe" still does not match "Frontal Bone".
CATEGORY = {
    "gyrus": "\x01cortex", "cortex": "\x01cortex", "lobe": "\x01cortex", "area": "\x01cortex",
    "region": "\x01cortex", "cortical": "\x01cortex", "sulcus": "\x01cortex",
    "nucleus": "\x01nucleus", "ganglion": "\x01nucleus",
    "artery": "\x01artery", "arterial": "\x01artery",
    "vein": "\x01vein", "venous": "\x01vein", "sinus": "\x01vein",
    "nerve": "\x01nerve", "neural": "\x01nerve",
    "tract": "\x01tract", "fasciculus": "\x01tract", "pathway": "\x01tract", "bundle": "\x01tract",
    "lemniscus": "\x01tract", "fiber": "\x01tract", "column": "\x01tract",
    "syndrome": "\x01syndrome", "disease": "\x01syndrome", "disorder": "\x01syndrome",
}
PREFIX = re.compile(r"^(neuroanatomy|anatomy|physiology|histology|embryology|biochemistry)\s*,\s*", re.I)
SUBPREFIX = re.compile(r"^(head and neck|back and spine|abdomen and pelvis|thorax|upper limb and lower limb|"
                       r"central nervous system|bony pelvis and lower limb|shoulder and upper limb|skin)\s*[:,]\s*", re.I)


def norm(s: str) -> str:
    s = s.lower().replace("’", "'")
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def core(title: str) -> str:
    t = PREFIX.sub("", title)
    t = SUBPREFIX.sub("", t)
    return norm(t)


def _sing(w: str) -> str:
    if w in IRREGULAR:
        return IRREGULAR[w]
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("ses") and len(w) > 4:
        return w[:-2]
    if w.endswith("s") and len(w) > 3 and not w.endswith(("ss", "us", "is", "as")):
        return w[:-1]
    return w


def toks(s: str) -> set[str]:
    out = set()
    for w in norm(s).split():
        w = _sing(w)
        if w in STOP:
            continue
        out.add(CATEGORY.get(w, w))
    return out


_idf: dict[str, float] = {}


def idf(t: str) -> float:
    """Rarity of a word across the catalog: 'raphe' must count for far more than 'cell' or 'anterior'."""
    if not _idf:
        df: dict[str, int] = {}
        for r in cat():
            for w in r["_toks"]:
                df[w] = df.get(w, 0) + 1
        n = max(1, len(cat()))
        for w, d in df.items():
            _idf[w] = math.log(n / d) + 1.0
        _idf["\x00default"] = math.log(n) + 1.0
    return _idf.get(t, _idf["\x00default"])


def score(key: str, rec: dict) -> float:
    c = rec["_core"]
    k = norm(key)
    if not k or not c:
        return 0.0
    if k == c:
        return 100.0
    kt, ct = toks(k), rec["_toks"]
    if not kt or not ct:
        return 0.0
    if kt == ct:                                   # same significant words (plural/order/"gyrus" vs "cortex")
        return 96.0
    if re.search(rf"\b{re.escape(k)}\b", c):        # the entry name appears verbatim in the chapter title
        return 88.0 - min(20.0, 2.0 * (len(ct) - len(kt)))
    inter = kt & ct
    if not inter:
        return 0.0
    # rarity-weighted F1: sharing "raphe" is evidence, sharing "anterior" or "cell" is not
    wi = sum(idf(t) for t in inter)
    cov = wi / sum(idf(t) for t in kt)
    prec = wi / sum(idf(t) for t in ct)
    f1 = 2 * cov * prec / (cov + prec)
    return 92.0 * f1


_cat = None


def cat() -> list[dict]:
    global _cat
    if _cat is None:
        _cat = catalog.load()
        for r in _cat:
            r["_core"] = core(r["title"])
            r["_toks"] = toks(r["_core"])
    return _cat


_index: dict[str, list[dict]] | None = None


def index() -> dict[str, list[dict]]:
    """token -> catalog records, so only plausible candidates are scored."""
    global _index
    if _index is None:
        _index = {}
        for r in cat():
            for t in r["_toks"]:
                _index.setdefault(t, []).append(r)
    return _index


def rank(keys: list[str], n: int = 8) -> list[tuple[float, dict]]:
    best: dict[str, tuple[float, dict]] = {}
    idx = index()
    for k in keys:
        cands: dict[str, dict] = {}
        for t in toks(k):
            for r in idx.get(t, ()):
                cands[r["nbk"]] = r
        for r in cands.values():
            s = score(k, r)
            if s > 0 and (r["nbk"] not in best or s > best[r["nbk"]][0]):
                best[r["nbk"]] = (s, r)
    return sorted(best.values(), key=lambda x: -x[0])[:n]


if __name__ == "__main__":
    for s, r in rank(sys.argv[1:]):
        print(f"{s:6.1f} {r['nbk']}\t{r['title']}")
