#!/usr/bin/env python3
"""Harvest a local catalog of StatPearls chapter titles relevant to neuroanatomy/neurology.

  python3 tools/cite/catalog.py            # build/refresh reference/statpearls-catalog.json
  python3 tools/cite/catalog.py --grep putamen

Uses cached E-utilities calls (reference/cite-cache/), so reruns cost nothing.
"""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import ncbi

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reference" / "statpearls-catalog.json"

# title keywords that between them cover the atlas's subject matter
TERMS = [
    "neuroanatomy", "neurophysiology", "physiology", "embryology", "histology",
    "head and neck", "back and spine", "abdomen and pelvis", "thorax", "upper limb and lower limb",
    "brain", "brainstem", "cerebral", "cerebellum", "cerebellar", "cortex", "cortical", "nucleus", "nuclei",
    "thalamus", "hypothalamus", "basal ganglia", "limbic", "hippocampus", "amygdala", "pituitary",
    "spinal", "spine", "vertebral", "cord", "meninges", "meningeal", "dura", "arachnoid", "pia",
    "ventricle", "ventricular", "cerebrospinal", "choroid", "hydrocephalus", "intracranial",
    "nerve", "nerves", "neural", "neuron", "plexus", "ganglion", "ganglia", "root", "rootlet",
    "cranial nerve", "olfactory", "optic", "oculomotor", "trochlear", "trigeminal", "abducens",
    "facial", "vestibulocochlear", "glossopharyngeal", "vagus", "accessory", "hypoglossal",
    "artery", "arteries", "arterial", "vein", "veins", "venous", "sinus", "circle of willis",
    "stroke", "infarct", "infarction", "ischemia", "ischemic", "hemorrhage", "hemorrhagic", "aneurysm",
    "thrombosis", "dissection", "vasospasm", "hematoma", "hemianopia", "amaurosis",
    "syndrome", "palsy", "paralysis", "paresis", "plegia", "neuropathy", "myelopathy", "radiculopathy",
    "aphasia", "apraxia", "agnosia", "neglect", "amnesia", "dementia", "delirium",
    "ataxia", "tremor", "dystonia", "chorea", "parkinson", "myoclonus", "dyskinesia", "spasticity",
    "seizure", "epilepsy", "status epilepticus", "migraine", "headache", "neuralgia",
    "vertigo", "nystagmus", "diplopia", "ptosis", "pupil", "papilledema", "hearing", "deafness", "tinnitus",
    "dysphagia", "dysarthria", "hoarseness", "taste", "smell", "anosmia",
    "sclerosis", "myasthenia", "guillain", "botulism", "tetanus", "neuromuscular", "muscle",
    "reflex", "gait", "sensation", "sensory", "motor", "pain", "temperature", "vibration", "proprioception",
    "tract", "pathway", "lemniscus", "capsule", "commissure", "fasciculus", "decussation", "peduncle",
    "gyrus", "sulcus", "lobe", "fissure", "insula", "operculum", "claustrum", "fornix",
    "herniation", "coma", "consciousness", "brain death", "concussion", "traumatic brain injury",
    "tumor", "glioma", "meningioma", "schwannoma", "metastasis", "abscess", "meningitis", "encephalitis",
    "autonomic", "sympathetic", "parasympathetic", "horner", "sweating", "bladder", "bowel",
    "electroencephalogram", "electromyography", "magnetic resonance", "computed tomography", "lumbar puncture",
    "myelin", "demyelinating", "neurotransmitter", "receptor", "blood brain barrier", "action potential",
    "eye", "orbit", "ear", "tongue", "pharynx", "larynx", "face", "scalp", "skull", "foramen", "sella",
    "shoulder", "arm", "forearm", "hand", "wrist", "thigh", "leg", "foot", "ankle", "hip", "knee",
    "diaphragm", "phrenic", "thoracic outlet", "carpal tunnel", "cubital", "peroneal", "sciatic",
]


UIDS = ROOT / "reference" / "statpearls-uids.json"


def harvest(terms: list[str] | None = None, quiet: bool = False) -> list[dict]:
    """esearch every term (cheap, cached), then esummary only the UIDs we have not summarised yet."""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    seen = {r["nbk"]: r for r in load()}
    known_uids = set(json.loads(UIDS.read_text())) if UIDS.exists() else set()
    terms = terms if terms is not None else TERMS
    uids: set[str] = set()
    ncbi.prefetch([ncbi.search_url("books", f'"{t}"[title] AND statpearls[book]', 200) for t in terms], progress="esearch")
    for i, t in enumerate(terms, 1):
        got = ncbi.esearch_all("books", f'"{t}"[title] AND statpearls[book]', cap=1200)
        uids.update(got)
        if not quiet and (i % 25 == 0 or i == len(terms)):
            print(f"  esearch {i}/{len(terms)} terms, {len(uids)} uids", flush=True)
    fresh = sorted(uids - known_uids)
    for i in range(0, len(fresh), 100):
        for x in ncbi.esummary("books", fresh[i:i + 100]):
            r = ncbi.parse_book(x)
            if r and r["nbk"]:
                seen.setdefault(r["nbk"], r)
        if not quiet:
            print(f"  esummary {min(i + 100, len(fresh))}/{len(fresh)} (catalog {len(seen)})", flush=True)
    known_uids |= uids
    UIDS.write_text(json.dumps(sorted(known_uids)))
    out = sorted(seen.values(), key=lambda r: r["title"].lower())
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return out


STOPWORDS = set("""the of and a an in to or with for on by from at as is are its his her their this that
left right anterior posterior superior inferior medial lateral dorsal ventral rostral caudal upper lower
major minor primary secondary common internal external deep superficial proximal distal middle
i ii iii iv v vi vii viii ix x xi xii b c d""".split())


def content_terms() -> list[str]:
    """Significant words used in entry names/synonyms -> extra title queries (broadens the catalog)."""
    sys.path.insert(0, str(Path(__file__).parent))
    import inventory, re as _re
    words: set[str] = set()
    for e in inventory.entries():
        for s in [e["name"], *e["synonyms"]]:
            for w in _re.findall(r"[A-Za-z][A-Za-z-]{3,}", s):
                w = w.lower().strip("-")
                if w and w not in STOPWORDS:
                    words.add(w)
    return sorted(words)


def load() -> list[dict]:
    return json.loads(OUT.read_text()) if OUT.exists() else []


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--grep")
    ap.add_argument("--terms-from-content", action="store_true",
                    help="also harvest one query per significant word used in entry names/synonyms")
    a = ap.parse_args()
    if a.grep:
        for r in load():
            if a.grep.lower() in r["title"].lower():
                print(f"{r['nbk']}\t{r['title']}")
    else:
        terms = list(TERMS)
        if a.terms_from_content:
            terms += content_terms()
        rows = harvest(terms)
        print(f"catalog: {len(rows)} chapters -> {OUT}")
