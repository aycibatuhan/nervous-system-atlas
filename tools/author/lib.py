"""Tiny helpers for writing content JSON from Python dicts (keeps authoring terse)."""
import json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
DIRS = {"structure": "structures", "cranial-nerve": "cranial-nerves", "pathway": "pathways", "syndrome": "syndromes", "glossary": "glossary", "quiz": "quiz"}

def C(book, ch, a, b=None, section=None):
    d = {"book": book, "chapter": ch, "pages": [a, b or a]}
    if section: d["section"] = section
    return d

def img(best, normal, path, seq=None):
    d = {"bestView": best, "normalAppearance": normal, "pathology": path}
    if seq: d["sequenceOfChoice"] = seq
    return d

def view(plane, x, y, z, label):
    return {"plane": plane, "mni": {"x": x, "y": y, "z": z}, "label": label}

def pathol(pathology, modality, finding, sequence=None, timing=None, pitfalls=None):
    d = {"pathology": pathology, "modality": modality, "finding": finding}
    if sequence: d["sequence"] = sequence
    if timing: d["timing"] = timing
    if pitfalls: d["pitfalls"] = pitfalls
    return d

def structure(id, name, system, summary, location, function, arteries, imaging, lesion, exam, pearls, citations, *,
              synonyms=(), latin=None, subsystem=None, parent=None, meshIds=(), level=None, boundaries=None, subdivisions=(), relations=None,
              afferents=(), efferents=(), pathways=(), territories=(), venous=None, bloodNote=None, syndromes=(), pitfalls=(), tags=(), kind="structure", extra=None):
    d = {"kind": kind, "id": id, "name": name, "synonyms": list(synonyms), "system": system, "meshIds": list(meshIds), "summary": summary,
         "anatomy": {"location": location, "subdivisions": [{"name": n, "note": t} for n, t in subdivisions]},
         "connections": {"afferents": [{"from": a[0], **({"via": a[1]} if len(a) > 1 and a[1] else {}), **({"note": a[2]} if len(a) > 2 else {})} for a in afferents],
                         "efferents": [{"to": e[0], **({"via": e[1]} if len(e) > 1 and e[1] else {}), **({"note": e[2]} if len(e) > 2 else {})} for e in efferents],
                         "pathways": list(pathways)},
         "function": function,
         "bloodSupply": {"arteries": list(arteries), "territories": list(territories)},
         "imaging": imaging,
         "clinical": {"lesionEffects": [{"deficit": a, "side": b, "mechanism": c} for a, b, c in lesion], "examination": list(exam), "syndromes": list(syndromes), "pearls": list(pearls)},
         "pitfalls": list(pitfalls), "citations": citations, "tags": list(tags), "status": "draft"}
    if latin: d["latin"] = latin
    if subsystem: d["subsystem"] = subsystem
    if parent: d["parent"] = parent
    if level: d["level"] = level
    if boundaries: d["anatomy"]["boundaries"] = boundaries
    if relations: d["anatomy"]["relations"] = relations
    if venous: d["bloodSupply"]["venous"] = venous
    if bloodNote: d["bloodSupply"]["note"] = bloodNote
    if extra: d.update(extra)
    return d

BRIT = [("fibres", "fibers"), ("fibre", "fiber"), ("centred", "centered"), ("centres", "centers"), ("centre", "center"), ("haemorrhag", "hemorrhag"), ("oedema", "edema"),
        ("anaemi", "anemi"), ("paediatric", "pediatric"), ("foetal", "fetal"), ("tumour", "tumor"), ("colour", "color"), ("localis", "localiz"), ("localiz", "localiz"),
        ("recognis", "recogniz"), ("organis", "organiz"), ("hospitalis", "hospitaliz"), ("normalis", "normaliz"), ("pseudonormalis", "pseudonormaliz"), ("mobilis", "mobiliz"),
        ("stabilis", "stabiliz"), ("characteris", "characteriz"), ("visualis", "visualiz"), ("emphasis", "emphasis"), ("analys", "analyz"), ("paralys", "paralyz"),
        ("oesophag", "esophag"), ("diarrhoea", "diarrhea"), ("grey", "gray"), ("licence", "license"), ("practise", "practice"), ("behaviour", "behavior"),
        ("favour", "favor"), ("neighbour", "neighbor"), ("labelled", "labeled"), ("modelling", "modeling"), ("signalling", "signaling"), ("travelled", "traveled"),
        ("cancelled", "canceled"), ("sulph", "sulf"), ("caesar", "cesar"), ("orthopaedic", "orthopedic"), ("gynaecolog", "gynecolog"), ("leukaemi", "leukemi"),
        ("ischaemi", "ischemi"), ("haemat", "hemat"), ("aetiolog", "etiolog"), ("anaesth", "anesth"), ("oestrogen", "estrogen"), ("faeces", "feces")]
KEEP = {"emphasis", "analysis", "paralysis", "dialysis", "basis", "crisis", "diagnosis", "prognosis", "hemiparesis", "paresis", "ptosis", "miosis", "mydriasis", "stenosis", "thrombosis", "ataxis"}

def american(s):
    if not isinstance(s, str):
        return s
    out = s
    for b, a in BRIT:
        if b == a:
            continue
        # replace with case preservation, skipping words in KEEP
        import re
        def rep(m):
            w = m.group(0)
            low = w.lower()
            if any(low.endswith(k) or low == k for k in KEEP) and b in ("analys", "paralys", "emphasis"):
                return w
            r = w.replace(b, a).replace(b.capitalize(), a.capitalize())
            return r
        out = re.sub(r"\b\w*" + b + r"\w*\b", rep, out, flags=re.I) if b not in ("analys", "paralys") else re.sub(r"\b(?!analysis|paralysis)\w*" + b + r"(?!is\b)\w*\b", rep, out, flags=re.I)
    return out

def americanize(v):
    if isinstance(v, str):
        return american(v)
    if isinstance(v, list):
        return [americanize(x) for x in v]
    if isinstance(v, dict):
        return {k: (v2 if k in ("id", "kind", "meshIds", "book", "structureId", "meshId", "parent", "system", "subsystem", "arteries", "territories", "pathways", "syndromes", "tags") else americanize(v2)) for k, v2 in v.items()}
    return v

def write(entries):
    entries = [americanize(e) for e in entries]
    for e in entries:
        p = ROOT / "content" / "data" / DIRS[e["kind"]] / f"{e['id']}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(e, indent=1, ensure_ascii=False) + "\n")
    print("wrote", len(entries), "entries")
