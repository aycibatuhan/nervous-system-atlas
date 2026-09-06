"""Shared helpers for the private reference corpus (tools/ref_*.py).

The corpus lives in reference/ (gitignored). Nothing here ships with the atlas.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "source"
REF = ROOT / "reference"

BOOKS = {
    "snell": {
        "file": SOURCE / "Snell’s Clinical Neuroanatomy, 8E.pdf",
        "cite": "Snell 8e",
        "title": "Snell's Clinical Neuroanatomy, 8th ed. (Splittgerber, Wolters Kluwer 2019)",
        "pdfOffset": 28,
        "pages": 555,
        # printed page of each chapter opener; 19 = appendix
        "chapterStarts": {1: 1, 2: 33, 3: 71, 4: 131, 5: 185, 6: 229, 7: 249, 8: 279, 9: 299, 10: 309,
                          11: 323, 12: 363, 13: 373, 14: 387, 15: 417, 16: 436, 17: 463, 18: 486, 19: 507},
        "lastPrinted": 514,
        "chapterTitles": {1: "Introduction and Organization of the Nervous System", 2: "Neurons and Neuroglia",
                          3: "Nerve Fibers and Peripheral Innervation",
                          4: "Spinal Cord and Ascending, Descending, and Intersegmental Tracts", 5: "Brainstem",
                          6: "Cerebellum and Its Connections", 7: "Cerebrum",
                          8: "The Structure and Functional Localization of the Cerebral Cortex",
                          9: "Reticular Formation and Limbic System", 10: "Basal Nuclei (Basal Ganglia)",
                          11: "Cranial Nerve Nuclei", 12: "Thalamus", 13: "Hypothalamus", 14: "Autonomic Nervous System",
                          15: "Meninges", 16: "Ventricular System and Cerebrospinal Fluid",
                          17: "Blood Supply of the Brain and Spinal Cord", 18: "Nervous System Development",
                          19: "Appendix: Neuroanatomical Data of Clinical Significance and Clinical Neuroanatomy Techniques"},
        "clinicalNotes": {1: 16, 2: 62, 3: 105, 4: 163, 5: 215, 6: 241, 7: 267, 8: 290, 9: 306, 10: 315, 11: 348,
                          12: 369, 13: 382, 14: 406, 15: 428, 16: 455, 17: 472, 18: 498},
        "problemSolving": {1: 27, 2: 65, 3: 119, 4: 175, 5: 219, 6: 244, 7: 273, 8: 293, 9: 307, 10: 319, 11: 356,
                           12: 370, 13: 383, 14: 411, 15: 432, 16: 458, 17: 480, 18: 502},
    },
    "berkowitz": {
        "file": SOURCE / "Clinical Neurology and Neuroanatomy, A Localization-Based Approach.pdf",
        "cite": "Berkowitz",
        "title": "Berkowitz AL. Clinical Neurology and Neuroanatomy: A Localization-Based Approach (Lange/McGraw-Hill 2017)",
        "pdfOffset": 15,
        "pages": 337,
        "chapterStarts": {1: 1, 2: 11, 3: 25, 4: 33, 5: 41, 6: 47, 7: 53, 8: 67, 9: 75, 10: 83, 11: 91, 12: 105,
                          13: 117, 14: 125, 15: 129, 16: 141, 17: 157, 18: 167, 19: 179, 20: 207, 21: 223, 22: 231,
                          23: 241, 24: 255, 25: 269, 26: 275, 27: 281, 28: 289, 29: 293, 30: 299, 31: 309},
        "lastPrinted": 312,
        "chapterTitles": {1: "Diagnostic Reasoning in Neurology and the Neurologic History and Examination",
                          2: "Introduction to Neuroimaging and Cerebrospinal Fluid Analysis",
                          3: "Overview of the Anatomy of the Nervous System",
                          4: "The Motor and Somatosensory Pathways and Approach to Weakness and Sensory Loss",
                          5: "The Spinal Cord and Approach to Myelopathy",
                          6: "The Visual Pathway and Approach to Visual Loss",
                          7: "The Cerebral Hemispheres and Vascular Syndromes",
                          8: "The Cerebellum and Approach to Ataxia", 9: "The Brainstem and Cranial Nerves",
                          10: "Pupillary Control and Approach to Anisocoria (Cranial Nerves 2 and 3)",
                          11: "Extraocular Movements and Approach to Diplopia (Cranial Nerves 3, 4, and 6)",
                          12: "The Auditory and Vestibular Pathways and Approach to Hearing Loss and Dizziness/Vertigo (Cranial Nerve 8)",
                          13: "Facial Sensation and Movement and Approach to Facial Sensory and Motor Deficits (Cranial Nerves 5 and 7)",
                          14: "Cranial Nerves 1, 9, 10, 11, and 12",
                          15: "The Peripheral Nervous System and Introduction to Electromyography/Nerve Conduction Studies",
                          16: "Radiculopathy, Plexopathy, and Mononeuropathies of the Upper Extremity",
                          17: "Radiculopathy, Plexopathy, and Mononeuropathies of the Lower Extremity",
                          18: "Seizures and Epilepsy", 19: "Vascular Diseases of the Brain and Spinal Cord",
                          20: "Infectious Diseases of the Nervous System",
                          21: "Demyelinating Diseases of the Central Nervous System",
                          22: "Delirium, Dementia, and Rapidly Progressive Dementia", 23: "Movement Disorders",
                          24: "Neoplastic and Paraneoplastic Disorders of the Nervous System and Neurologic Complications of Chemotherapy and Radiation Therapy",
                          25: "Disorders of Intracranial Pressure", 26: "Headache", 27: "Peripheral Neuropathy",
                          28: "Motor Neuron Disease", 29: "Disorders of the Neuromuscular Junction", 30: "Diseases of Muscle",
                          31: "Leukodystrophies and Mitochondrial Disorders"},
    },
}

PAGE_MARK = re.compile(r"^⟦(\w+) p\.(\d+) \| pdf (\d+)⟧$")


def chapter_ranges(book: str) -> dict[int, tuple[int, int]]:
    b = BOOKS[book]
    starts = sorted(b["chapterStarts"].items())
    out = {}
    for i, (n, s) in enumerate(starts):
        e = starts[i + 1][1] - 1 if i + 1 < len(starts) else b["lastPrinted"]
        out[n] = (s, e)
    return out


def chapter_of(book: str, printed: int) -> int | None:
    for n, (s, e) in chapter_ranges(book).items():
        if s <= printed <= e:
            return n
    return None


def page_marker(book: str, printed: int) -> str:
    return f"⟦{book} p.{printed} | pdf {printed + BOOKS[book]['pdfOffset']}⟧"


def load_lexicon() -> set[str]:
    p = REF / "lexicon" / "words.txt"
    if p.exists():
        return set(p.read_text().split())
    return set(Path("/usr/share/dict/words").read_text().lower().split())


def clean_pages(book: str) -> dict[int, str]:
    """printed page -> clean text (from reference/<book>/clean/chNN.txt)."""
    pages: dict[int, str] = {}
    cur = None
    buf: list[str] = []
    for f in sorted((REF / book / "clean").glob("ch*.txt")):
        for line in f.read_text().splitlines():
            m = PAGE_MARK.match(line)
            if m:
                if cur is not None:
                    pages[cur] = "\n".join(buf)
                cur = int(m.group(2)); buf = []
            else:
                buf.append(line)
    if cur is not None:
        pages[cur] = "\n".join(buf)
    return pages
