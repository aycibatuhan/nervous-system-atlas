#!/usr/bin/env python3
"""Build the private reference corpus in reference/ from the two textbooks.

  uv run --project pipeline python tools/ref_extract.py [snell|berkowitz|all] [--force]

Snell   : pdftotext (poppler) per chapter + OCR clean-up rules (tools/ref_ocr_rules.snell.json)
Berkowitz: PyMuPDF rawdict with glyph-gap repair (the PDF's ligature glyphs fi/fl/ff/ffi/Th lose their
           second letter; the survivor is followed by a measurable horizontal gap which we fill back in).
Outputs per chapter: raw/chNN.txt, clean/chNN.txt (with ⟦book p.N | pdf M⟧ markers), tables/chNN.txt (snell),
plus lexicon/words.txt, <book>/changes.log and berkowitz/repair-report.json.
"""
from __future__ import annotations

import collections
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from refcorpus import BOOKS, REF, chapter_ranges, page_marker  # noqa: E402

WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")


# ----------------------------------------------------------------------------- lexicon
def build_lexicon(snell_tokens: collections.Counter | None) -> set[str]:
    lex = {w for w in Path("/usr/share/dict/words").read_text().lower().split() if len(w) > 1} | {"a", "i"}
    hand = (Path(__file__).parent / "lexicon_extra.txt")
    if hand.exists():
        lex |= set(hand.read_text().lower().split())
    if snell_tokens:
        lex |= {w for w, n in snell_tokens.items() if n >= 2 and len(w) > 2}
    (REF / "lexicon").mkdir(parents=True, exist_ok=True)
    (REF / "lexicon" / "words.txt").write_text("\n".join(sorted(lex)))
    return lex


# ----------------------------------------------------------------------------- Snell
def snell_extract(force: bool = False) -> collections.Counter:
    b = BOOKS["snell"]
    rules = json.loads((Path(__file__).parent / "ref_ocr_rules.snell.json").read_text())
    drop = [re.compile(p) for p in rules["dropLinePatterns"]]
    figcap = re.compile(rules["figureCaption"])
    subs = [(re.compile(p), r) for p, r in rules["substitutions"]]
    base_lex = set(Path("/usr/share/dict/words").read_text().lower().split())
    for d in ("raw", "clean", "tables"):
        (REF / "snell" / d).mkdir(parents=True, exist_ok=True)
    log = (REF / "snell" / "changes.log").open("w")
    tokens: collections.Counter = collections.Counter()
    for ch, (s, e) in chapter_ranges("snell").items():
        out_clean = REF / "snell" / "clean" / f"ch{ch:02d}.txt"
        if out_clean.exists() and not force:
            for w in WORD.findall(out_clean.read_text()):
                tokens[w.lower()] += 1
            continue
        f1, l1 = s + b["pdfOffset"], e + b["pdfOffset"]
        raw = subprocess.run(["pdftotext", "-f", str(f1), "-l", str(l1), "-enc", "UTF-8", str(b["file"]), "-"],
                             capture_output=True, text=True, check=True).stdout
        lay = subprocess.run(["pdftotext", "-layout", "-f", str(f1), "-l", str(l1), "-enc", "UTF-8", str(b["file"]), "-"],
                             capture_output=True, text=True, check=True).stdout
        raw_pages = raw.split("\f")
        lay_pages = lay.split("\f")
        raw_lines, clean_lines, tab_lines = [], [], []
        for i in range(l1 - f1 + 1):
            printed = s + i
            mark = page_marker("snell", printed)
            raw_lines += [mark, raw_pages[i] if i < len(raw_pages) else ""]
            tab_lines += [mark, lay_pages[i] if i < len(lay_pages) else ""]
            clean_lines.append(mark)
            page_text = raw_pages[i] if i < len(raw_pages) else ""
            lines = page_text.splitlines()
            kept: list[str] = []
            for line in lines:
                if any(p.match(line) for p in drop):
                    log.write(f"p{printed} DROP {line.strip()!r}\n"); continue
                alpha = sum(c.isalpha() for c in line); nonan = sum((not c.isalnum()) and (not c.isspace()) for c in line)
                if line.strip() and (alpha < 3 or nonan > 0.3 * max(1, len(line.strip()))) and not figcap.match(line):
                    log.write(f"p{printed} JUNK {line.strip()!r}\n"); continue
                if figcap.match(line):
                    line = "[FIG] " + line
                for pat, rep in subs:
                    new = pat.sub(rep, line)
                    if new != line:
                        log.write(f"p{printed} SUB {line.strip()!r} -> {new.strip()!r}\n"); line = new
                kept.append(line)
            # join line-end hyphenation when the joined word is a dictionary word
            joined: list[str] = []
            j = 0
            while j < len(kept):
                line = kept[j]
                m = re.search(r"(\w+)[-—–]$", line)
                if m and j + 1 < len(kept):
                    nxt = kept[j + 1].lstrip()
                    m2 = re.match(r"(\w+)", nxt)
                    if m2 and (m.group(1) + m2.group(1)).lower() in base_lex:
                        line = line[: m.start(1)] + m.group(1) + m2.group(1) + nxt[m2.end():]
                        kept[j + 1] = ""
                        log.write(f"p{printed} JOIN {m.group(1)}-{m2.group(1)}\n")
                joined.append(line); j += 1
            clean_lines += [ln for ln in joined if ln is not None]
        (REF / "snell" / "raw" / f"ch{ch:02d}.txt").write_text("\n".join(raw_lines))
        (REF / "snell" / "tables" / f"ch{ch:02d}.txt").write_text("\n".join(tab_lines))
        text = "\n".join(clean_lines)
        out_clean.write_text(text)
        for w in WORD.findall(text):
            tokens[w.lower()] += 1
        print(f"snell ch{ch:02d} printed {s}-{e} ok")
    log.close()
    return tokens


# ----------------------------------------------------------------------------- Berkowitz
FI_WORDS_PREFER_L = None  # decided by lexicon


def berkowitz_extract(lex: set[str], freq: collections.Counter, force: bool = False) -> None:
    import pymupdf

    b = BOOKS["berkowitz"]
    doc = pymupdf.open(str(b["file"]))
    for d in ("raw", "clean"):
        (REF / "berkowitz" / d).mkdir(parents=True, exist_ok=True)
    log = (REF / "berkowitz" / "changes.log").open("w")
    report: dict[str, dict] = {}
    flags = pymupdf.TEXT_INHIBIT_SPACES | pymupdf.TEXT_PRESERVE_WHITESPACE

    # Times New Roman advance widths (em) of the glyphs that this PDF loses. A lost ligature either
    # (a) surfaces as a U+0020 whose advance is wider than a space, or (b) leaves a survivor letter followed by a gap.
    W = {" ": 0.25, "f": 0.333, "i": 0.278, "l": 0.278, "t": 0.278, "h": 0.5, "d": 0.5, "e": 0.444, "r": 0.333, "T": 0.611}
    FILLS = [" ", "i", "l", "f", "t", "h", "d", "fi", "fl", "ff", "ft", "f ", "t ", "d ", "e", "ffi", "ffl", "ft ", "fi ", "fl ",
             "ff ", "th", "e ", "r", "i ", "l ", "h ", "de", "ed", "di", "id", "fd", "T", "T "]
    FILL_W = {s: sum(W[c] for c in s) for s in FILLS}
    # measured ligature advances in this font (fi/fl/ff ≈ 0.556, ffi/ffl ≈ 0.833)
    FILL_W.update({"fi": 0.556, "fl": 0.556, "ff": 0.556, "ffi": 0.833, "ffl": 0.833, "fi ": 0.806, "fl ": 0.806, "ff ": 0.806})
    hole_hist: collections.Counter = collections.Counter()

    SHORT_OK = {"a", "i", "of", "if", "it", "is", "in", "he", "to", "at", "be", "as", "or", "an", "on", "by", "we", "do",
                "no", "so", "up", "us", "me", "my", "ch", "cn", "mm", "cm", "ms", "mg", "iv", "ct", "mr", "dr", "et", "al",
                "eg", "ie", "vs", "am", "pm", "hz", "ml", "kg", "ii", "iii"}

    def norm(w: str) -> str:
        return re.sub(r"[^A-Za-z]", "", w).lower()

    def word_ok(w: str) -> bool:
        w = norm(w)
        if not w:
            return True
        if len(w) <= 2:
            return w in SHORT_OK
        if w in lex:
            return True
        return (w.endswith("s") and w[:-1] in lex) or (w.endswith("ed") and (w[:-2] in lex or w[:-1] in lex)) \
            or (w.endswith("ing") and (w[:-3] in lex or w[:-3] + "e" in lex)) or (w.endswith("ly") and w[:-2] in lex)

    def best_fill(prefix: str, suffix: str, width: float, is_space: bool, unresolved: list[str]) -> str:
        tol = lambda s: 0.1 if len(s.strip()) <= 1 else 0.14
        cands = [s for s in FILLS if abs(FILL_W[s] - width) <= tol(s)]
        if is_space and width <= 0.5 and " " not in cands:
            cands.insert(0, " ")          # a justified/stretched real space
        caps = (prefix + suffix).isupper() and len(prefix + suffix) >= 2
        if caps:
            cands = [s for s in cands if s.strip() in ("", "T")]
        else:
            cands = [s for s in cands if "T" not in s]
        space_default = " " if (is_space or width >= 0.2) else ""
        if not prefix and not suffix:
            return space_default
        if not cands:
            return space_default
        if not suffix:                      # hole at a word end
            if word_ok(prefix):
                return space_default
            letters = [s for s in cands if s.strip() and word_ok(prefix + s.strip())]
            if letters:
                return letters[0].strip() + (" " if letters[0].endswith(" ") else "")
            if width >= 0.29 or not is_space:
                unresolved.append(f"{prefix}[{width:.2f}{'s' if is_space else ''}]")
            return space_default
        if not prefix:                      # hole at a word start
            if word_ok(suffix):
                return space_default
            letters = [s for s in cands if s.strip() and word_ok(s.strip() + suffix)]
            if letters:
                return (" " if letters[0].startswith(" ") else "") + letters[0].strip()
            if width >= 0.29 or not is_space:
                unresolved.append(f"[{width:.2f}{'s' if is_space else ''}]{suffix}")
            return space_default
        good = [s for s in cands if all(word_ok(w) for w in (prefix + s + suffix).replace("-", " ").split())]
        letter_good = sorted([s for s in good if s.strip()],
                             key=lambda s: (-freq.get(norm((prefix + s + suffix).split()[0]), 0), abs(FILL_W[s] - width)))
        if is_space and " " in good and word_ok(prefix) and word_ok(suffix):
            joined = [s for s in letter_good if " " not in s]
            if joined:
                jw = norm(prefix + joined[0] + suffix)
                if freq.get(jw, 0) >= 3 and freq.get(jw, 0) > 2 * min(freq.get(norm(prefix), 0), freq.get(norm(suffix), 0)):
                    return joined[0]
            return " "
        if letter_good and not is_space and 0.18 <= width <= 0.45 and word_ok(prefix) and word_ok(suffix):
            jw = norm((prefix + letter_good[0] + suffix).split()[0])
            if not (freq.get(jw, 0) >= 3 and freq.get(jw, 0) > 2 * min(freq.get(norm(prefix), 0), freq.get(norm(suffix), 0))):
                return " "
        if letter_good:
            return letter_good[0]
        if good:
            return good[0]
        if is_space:
            if width >= 0.29:
                unresolved.append(f"{prefix}[{width:.2f}s]{suffix}")
            return " "
        unresolved.append(f"{prefix}[{width:.2f}]{suffix}")
        return cands[0]

    def line_text(chars: list[dict], size: float, printed: int, unresolved: list[str]) -> str:
        items: list[tuple[str, float, bool]] = []   # (text, hole width after it, hole came from a space glyph)
        n = len(chars)
        for i, ch in enumerate(chars):
            c = ch["c"]
            bw = (ch["bbox"][2] - ch["bbox"][0]) / size
            adv = ((chars[i + 1]["origin"][0] - ch["origin"][0]) / size) if i + 1 < n else bw
            if c.isspace():
                items.append(("", adv, True))
            else:
                hole = adv - bw
                items.append((c, hole if hole >= 0.12 else 0.0, False))
        segs: list[str] = []; pending: list[tuple[float, bool]] = []; cur = ""
        for text, hole, is_space in items:
            cur += text
            if hole > 0:
                segs.append(cur); pending.append((hole, is_space)); cur = ""
                hole_hist[(round(hole, 2), is_space)] += 1
        segs.append(cur)
        # pass 1: survivor+gap holes (inside words); pass 2: space-glyph holes
        fills: list[str | None] = [None] * len(pending)
        for pass_space in (False, True):
            for k, (width, is_space) in enumerate(pending):
                if is_space != pass_space:
                    continue
                left = segs[k] + ("" if k == 0 or fills[k - 1] is None else "")
                # assemble text to the left/right using fills decided so far
                lt = "".join(segs[j] + (fills[j] if fills[j] is not None else "\u0001") for j in range(k)) + segs[k]
                rt = "".join((fills[j] if fills[j] is not None else "\u0001") + segs[j + 1] for j in range(k, len(pending)))
                rt = rt[len(fills[k]) if fills[k] else 1:] if False else rt
                # rt starts with the current hole placeholder; strip it
                rt = rt[1:] if rt.startswith("\u0001") else rt
                m = re.search(r"[A-Za-z’'-]*$", lt); prefix = m.group(0) if m else ""
                m2 = re.match(r"[A-Za-z’'-]*", rt); suffix = m2.group(0) if m2 else ""
                fills[k] = best_fill(prefix, suffix, width, is_space, unresolved)
        out = segs[0]
        for f, nxt in zip(fills, segs[1:]):
            out += (f or "") + nxt
        return re.sub(r"[ ]{2,}", " ", out)

    for ch, (s, e) in chapter_ranges("berkowitz").items():
        out_clean = REF / "berkowitz" / "clean" / f"ch{ch:02d}.txt"
        if out_clean.exists() and not force:
            continue
        raw_lines, clean_lines = [], []
        for printed in range(s, e + 1):
            pno = printed + b["pdfOffset"] - 1
            page = doc[pno]
            mark = page_marker("berkowitz", printed)
            raw_lines += [mark, page.get_text()]
            clean_lines.append(mark)
            unresolved: list[str] = []
            d = page.get_text("rawdict", flags=flags, sort=True)
            nwords = 0
            for blk in d["blocks"]:
                if blk.get("type", 0) != 0:
                    continue
                para: list[str] = []
                for ln in blk.get("lines", []):
                    chars = [c for sp in ln["spans"] for c in sp["chars"]]
                    if not chars:
                        continue
                    size = max(sp["size"] for sp in ln["spans"])
                    t = line_text(chars, size, printed, unresolved).strip()
                    if not t:
                        continue
                    # running header / page number lines
                    if re.match(r"^(CHAPTER \d+|PART [IVX]+)", t) or re.fullmatch(r"\d{1,3}", t):
                        continue
                    if re.match(r"^\S+\.indd\s+\d+", t):
                        continue
                    if re.match(r"^(FIGURE|TABLE)\s+\d+[-–]\d+", t):
                        t = "[FIG] " + t
                    para.append(t)
                    nwords += len(WORD.findall(t))
                if para:
                    # de-hyphenate within paragraph
                    txt = "\n".join(para)
                    txt = re.sub(r"(\w+)-\n(\w+)", lambda m: m.group(1) + m.group(2) if (m.group(1) + m.group(2)).lower() in lex else m.group(0), txt)
                    clean_lines.append(txt)
                    clean_lines.append("")
            report[str(printed)] = {"words": nwords, "unresolved": unresolved}
            for u in unresolved:
                log.write(f"p{printed} UNRESOLVED {u}\n")
        (REF / "berkowitz" / "raw" / f"ch{ch:02d}.txt").write_text("\n".join(raw_lines))
        out_clean.write_text("\n".join(clean_lines))
        print(f"berkowitz ch{ch:02d} printed {s}-{e} ok")
    log.close()
    report["_holes"] = {f"{k[0]}{'s' if k[1] else ''}": v for k, v in sorted(hole_hist.items())}
    (REF / "berkowitz" / "repair-report.json").write_text(json.dumps(report, indent=1))


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    which = args[0] if args else "all"
    tokens = None
    if which in ("snell", "all"):
        tokens = snell_extract(force)
    elif (REF / "snell" / "clean").exists():
        tokens = collections.Counter()
        for f in (REF / "snell" / "clean").glob("ch*.txt"):
            for w in WORD.findall(f.read_text()):
                tokens[w.lower()] += 1
    lex = build_lexicon(tokens)
    if which in ("berkowitz", "all"):
        berkowitz_extract(lex, tokens or collections.Counter(), force)


if __name__ == "__main__":
    main()
