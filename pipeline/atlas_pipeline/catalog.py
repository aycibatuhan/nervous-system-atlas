"""Curated catalogue: which atlas labels become which meshes, with stable ids, names, systems, colours.

Mesh id = content structure id (+ "-l"/"-r" for paired structures). Never expose raw atlas ints.
"""
from __future__ import annotations

import colorsys
import hashlib
from dataclasses import dataclass, field

# ---------------------------------------------------------------- systems (shared with content + UI)
SYSTEMS = [
    ("cerebrum", "Cerebrum", "#E8B89D", True),
    ("basal-ganglia", "Basal ganglia", "#C97B84", True),
    ("diencephalon", "Diencephalon", "#D9A066", True),
    ("brainstem", "Brainstem", "#B9A0C9", True),
    ("cerebellum", "Cerebellum", "#9BC49B", True),
    ("cranial-nerves", "Cranial nerves", "#F2E394", True),
    ("spinal-cord", "Spinal cord", "#C7B299", False),
    ("peripheral", "Peripheral nerves", "#D8C27A", False),
    ("autonomic", "Autonomic", "#E0B070", False),
    ("ventricles-csf", "Ventricles & CSF", "#7FB3D5", True),
    ("meninges", "Meninges", "#D0D0D0", False),
    ("arteries", "Arteries", "#C0392B", True),
    ("arterial-territories", "Arterial territories", "#E07B5A", False),
    ("venous", "Venous sinuses", "#4A69BD", False),
    ("tracts", "White-matter tracts", "#EDE3D2", False),
    ("envelope", "Brain surface", "#E6D5C3", True),
]
SYSTEM_COLOUR = {s[0]: s[2] for s in SYSTEMS}

LOBE_COLOUR = {"frontal": "#F2C1A0", "parietal": "#C9D8F0", "temporal": "#F0D9A0", "occipital": "#D6C2F0",
               "insula": "#E0A8A8", "limbic": "#F0C8D8"}

# triangle budgets per size class
BUDGET = {"huge": 60000, "large": 25000, "cortical": 10000, "medium": 6000, "small": 3000, "tiny": 1500,
          "tract": 15000, "territory": 12000, "vessel": 40000}


def jitter(colour: str, key: str, amount: float = 0.06) -> str:
    """Deterministic small lightness/hue variation so neighbouring structures are distinguishable."""
    h = int(hashlib.md5(key.encode()).hexdigest()[:8], 16)
    r, g, b = (int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5))
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
    hh = (hh + ((h % 1000) / 1000 - 0.5) * amount) % 1.0
    ll = min(0.92, max(0.25, ll + (((h >> 10) % 1000) / 1000 - 0.5) * amount * 1.5))
    r, g, b = colorsys.hls_to_rgb(hh, ll, ss)
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


@dataclass
class MeshSpec:
    id: str
    name: str
    system: str
    subsystem: str | None = None
    side: str = "midline"           # left | right | midline | bilateral
    colour: str | None = None
    visible: bool = False
    budget: str = "medium"
    structure_id: str | None = None  # content id (defaults to id without side suffix)
    opacity: float = 1.0
    labels: dict = field(default_factory=dict)   # {"anat": [...], "vascular": [...], "tract": [...]} filled by pipeline
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.structure_id is None:
            self.structure_id = self.id[:-2] if self.id.endswith(("-l", "-r")) else self.id
        if self.colour is None:
            self.colour = jitter(SYSTEM_COLOUR[self.system], self.structure_id)


@dataclass
class AtlasSpec:
    id: str                 # source id (matches sources.yaml)
    file: str               # path relative to raw/
    space: str              # 'mni2009' | 'nlin6'
    kind: str = "labels"    # labels | binary | probability
    priority: int = 0       # higher wins when painting the composite label volume
    label_volume: str = "anat"   # anat | vascular | tract
    fix: str | None = None       # 'arterial' -> replace affine; 'squeeze' -> drop 4th dim
    threshold: float | None = None
    entries: dict[int, MeshSpec] = field(default_factory=dict)   # atlas label -> mesh
    files: dict[str, MeshSpec] = field(default_factory=dict)     # per-file binary masks (HCP1065)


def LR(base_id: str, name: str, system: str, lab_l: int, lab_r: int, **kw) -> dict[int, MeshSpec]:
    """Paired structure helper: returns {label: MeshSpec} for left and right."""
    out = {}
    for lab, side, sfx in ((lab_l, "left", "-l"), (lab_r, "right", "-r")):
        out[lab] = MeshSpec(id=f"{base_id}{sfx}", name=f"{name} ({'L' if side == 'left' else 'R'})", system=system,
                            side=side, structure_id=base_id, **kw)
    return out


# ---------------------------------------------------------------- Harvard-Oxford cortical (48, FSL order, 0-based)
HOCPA = [
    ("frontal-pole", "Frontal pole", "frontal"), ("insula", "Insular cortex", "insula"),
    ("gyrus-superior-frontal", "Superior frontal gyrus", "frontal"), ("gyrus-middle-frontal", "Middle frontal gyrus", "frontal"),
    ("gyrus-inferior-frontal-triangularis", "Inferior frontal gyrus, pars triangularis", "frontal"),
    ("gyrus-inferior-frontal-opercularis", "Inferior frontal gyrus, pars opercularis", "frontal"),
    ("gyrus-precentral", "Precentral gyrus", "frontal"), ("temporal-pole", "Temporal pole", "temporal"),
    ("gyrus-superior-temporal-anterior", "Superior temporal gyrus, anterior division", "temporal"),
    ("gyrus-superior-temporal-posterior", "Superior temporal gyrus, posterior division", "temporal"),
    ("gyrus-middle-temporal-anterior", "Middle temporal gyrus, anterior division", "temporal"),
    ("gyrus-middle-temporal-posterior", "Middle temporal gyrus, posterior division", "temporal"),
    ("gyrus-middle-temporal-temporooccipital", "Middle temporal gyrus, temporo-occipital part", "temporal"),
    ("gyrus-inferior-temporal-anterior", "Inferior temporal gyrus, anterior division", "temporal"),
    ("gyrus-inferior-temporal-posterior", "Inferior temporal gyrus, posterior division", "temporal"),
    ("gyrus-inferior-temporal-temporooccipital", "Inferior temporal gyrus, temporo-occipital part", "temporal"),
    ("gyrus-postcentral", "Postcentral gyrus", "parietal"), ("lobule-superior-parietal", "Superior parietal lobule", "parietal"),
    ("gyrus-supramarginal-anterior", "Supramarginal gyrus, anterior division", "parietal"),
    ("gyrus-supramarginal-posterior", "Supramarginal gyrus, posterior division", "parietal"),
    ("gyrus-angular", "Angular gyrus", "parietal"),
    ("cortex-lateral-occipital-superior", "Lateral occipital cortex, superior division", "occipital"),
    ("cortex-lateral-occipital-inferior", "Lateral occipital cortex, inferior division", "occipital"),
    ("cortex-intracalcarine", "Intracalcarine cortex", "occipital"), ("cortex-frontal-medial", "Frontal medial cortex", "frontal"),
    ("cortex-supplementary-motor", "Supplementary motor cortex (juxtapositional lobule)", "frontal"),
    ("cortex-subcallosal", "Subcallosal cortex", "limbic"), ("gyrus-paracingulate", "Paracingulate gyrus", "limbic"),
    ("gyrus-cingulate-anterior", "Cingulate gyrus, anterior division", "limbic"),
    ("gyrus-cingulate-posterior", "Cingulate gyrus, posterior division", "limbic"),
    ("precuneus", "Precuneus", "parietal"), ("cuneus", "Cuneus", "occipital"),
    ("cortex-orbitofrontal", "Frontal orbital cortex", "frontal"),
    ("gyrus-parahippocampal-anterior", "Parahippocampal gyrus, anterior division", "limbic"),
    ("gyrus-parahippocampal-posterior", "Parahippocampal gyrus, posterior division", "limbic"),
    ("gyrus-lingual", "Lingual gyrus", "occipital"),
    ("cortex-temporal-fusiform-anterior", "Temporal fusiform cortex, anterior division", "temporal"),
    ("cortex-temporal-fusiform-posterior", "Temporal fusiform cortex, posterior division", "temporal"),
    ("cortex-temporo-occipital-fusiform", "Temporal occipital fusiform cortex", "temporal"),
    ("gyrus-occipital-fusiform", "Occipital fusiform gyrus", "occipital"),
    ("cortex-frontal-operculum", "Frontal operculum cortex", "frontal"),
    ("cortex-central-operculum", "Central opercular cortex", "frontal"),
    ("cortex-parietal-operculum", "Parietal operculum cortex", "parietal"),
    ("planum-polare", "Planum polare", "temporal"), ("gyrus-heschl", "Heschl's gyrus (primary auditory cortex)", "temporal"),
    ("planum-temporale", "Planum temporale", "temporal"), ("cortex-supracalcarine", "Supracalcarine cortex", "occipital"),
    ("occipital-pole", "Occipital pole", "occipital"),
]


def hocpal_entries() -> dict[int, MeshSpec]:
    out = {}
    for k, (sid, name, lobe) in enumerate(HOCPA):
        # lateralised index = 2k (L) / 2k+1 (R); voxel value = index + 1
        out.update(LR(sid, name, "cerebrum", 2 * k + 1, 2 * k + 2, subsystem=f"lobe-{lobe}", visible=True,
                      budget="cortical", colour=jitter(LOBE_COLOUR[lobe], sid), opacity=1.0))
    return out


# ---------------------------------------------------------------- FreeSurfer aseg
def aseg_entries() -> dict[int, MeshSpec]:
    e = {}
    e.update(LR("ventricle-lateral", "Lateral ventricle", "ventricles-csf", 4, 43, visible=True, budget="large", colour="#7FB3D5"))
    e.update(LR("ventricle-lateral-inferior-horn", "Lateral ventricle, inferior (temporal) horn", "ventricles-csf", 5, 44, budget="small", colour="#8CC0E0"))
    e[14] = MeshSpec("ventricle-third", "Third ventricle", "ventricles-csf", visible=True, budget="small", colour="#6FA8D0")
    e[15] = MeshSpec("ventricle-fourth", "Fourth ventricle", "ventricles-csf", visible=True, budget="small", colour="#5F9CC8")
    e[16] = MeshSpec("brainstem", "Brainstem", "brainstem", visible=True, budget="large", colour="#B9A0C9")
    e.update(LR("cerebellar-hemisphere", "Cerebellar hemisphere (cortex)", "cerebellum", 8, 47, visible=True, budget="large", colour="#9BC49B"))
    e.update(LR("cerebellar-white-matter", "Cerebellar white matter", "cerebellum", 7, 46, budget="large", colour="#D5E8D0"))
    e.update(LR("hippocampus", "Hippocampus", "cerebrum", 17, 53, subsystem="limbic", visible=True, budget="medium", colour="#E8A0B8"))
    e.update(LR("cerebral-white-matter", "Cerebral white matter", "cerebrum", 2, 41, subsystem="white-matter", budget="huge", colour="#F3EEE6", opacity=0.9))
    for lab in (251, 252, 253, 254, 255):
        e[lab] = MeshSpec("corpus-callosum", "Corpus callosum", "cerebrum", subsystem="white-matter", visible=True, budget="medium", colour="#F5F0E8")
    e.update(LR("ventral-diencephalon", "Ventral diencephalon (FreeSurfer)", "diencephalon", 28, 60, budget="medium", colour="#D9A066"))
    return e


# ---------------------------------------------------------------- MASSP (63)
def massp_entries() -> dict[int, MeshSpec]:
    e = {}
    e.update(LR("caudate-nucleus", "Caudate nucleus", "basal-ganglia", 1, 2, visible=True, budget="medium", colour="#C97B84"))
    e.update(LR("subthalamic-nucleus", "Subthalamic nucleus", "basal-ganglia", 3, 4, visible=True, budget="tiny", colour="#B05A7A"))
    e.update(LR("substantia-nigra", "Substantia nigra", "brainstem", 5, 6, subsystem="midbrain", visible=True, budget="small", colour="#5A3E5A"))
    e.update(LR("red-nucleus", "Red nucleus", "brainstem", 7, 8, subsystem="midbrain", visible=True, budget="tiny", colour="#D04040"))
    e.update(LR("globus-pallidus-internus", "Globus pallidus, internal segment", "basal-ganglia", 9, 10, visible=True, budget="small", colour="#A86070"))
    e.update(LR("globus-pallidus-externus", "Globus pallidus, external segment", "basal-ganglia", 11, 12, visible=True, budget="small", colour="#BF7A8A"))
    e.update(LR("thalamus", "Thalamus", "diencephalon", 13, 14, visible=True, budget="medium", colour="#D9A066"))
    e.update(LR("amygdala", "Amygdala", "cerebrum", 19, 20, subsystem="limbic", visible=True, budget="small", colour="#D08090"))
    e.update(LR("internal-capsule", "Internal capsule", "cerebrum", 21, 22, subsystem="white-matter", visible=True, budget="medium", colour="#EFE6D8"))
    e.update(LR("ventral-tegmental-area", "Ventral tegmental area", "brainstem", 23, 24, subsystem="midbrain", budget="tiny", colour="#7A5A8A"))
    e[25] = MeshSpec("fornix", "Fornix", "cerebrum", subsystem="limbic", visible=True, budget="small", colour="#F0DCC0")
    e.update(LR("periaqueductal-grey", "Periaqueductal grey", "brainstem", 26, 27, subsystem="midbrain", budget="tiny", colour="#8A7A9A"))
    e.update(LR("pedunculopontine-nucleus", "Pedunculopontine nucleus", "brainstem", 28, 29, subsystem="pons", budget="tiny", colour="#9A8AAA"))
    e.update(LR("claustrum", "Claustrum", "basal-ganglia", 30, 31, budget="small", colour="#D8A0A8"))
    e.update(LR("inferior-colliculus", "Inferior colliculus", "brainstem", 32, 33, subsystem="midbrain", visible=True, budget="tiny", colour="#A080B0"))
    e.update(LR("superior-colliculus", "Superior colliculus", "brainstem", 34, 35, subsystem="midbrain", visible=True, budget="tiny", colour="#B090C0"))
    e.update(LR("habenula", "Lateral habenula", "diencephalon", 36, 37, budget="tiny", colour="#C8A070"))
    e.update(LR("putamen", "Putamen", "basal-ganglia", 38, 39, visible=True, budget="medium", colour="#D48C8C"))
    e.update(LR("nucleus-accumbens", "Nucleus accumbens", "basal-ganglia", 40, 41, budget="tiny", colour="#E0A0A0"))
    e.update(LR("hippocampus-ca1", "Hippocampus CA1", "cerebrum", 42, 43, subsystem="limbic", budget="small", colour="#E8A8C0"))
    e.update(LR("hippocampus-ca23", "Hippocampus CA2/CA3", "cerebrum", 44, 45, subsystem="limbic", budget="tiny", colour="#E098B8"))
    e.update(LR("dentate-gyrus", "Dentate gyrus", "cerebrum", 46, 47, subsystem="limbic", budget="tiny", colour="#D888B0"))
    e.update(LR("presubiculum", "Presubiculum", "cerebrum", 48, 49, subsystem="limbic", budget="tiny", colour="#F0B8C8"))
    e.update(LR("subiculum", "Subiculum", "cerebrum", 50, 51, subsystem="limbic", budget="tiny", colour="#F0C0D0"))
    e.update(LR("uncus", "Uncus", "cerebrum", 52, 53, subsystem="limbic", visible=True, budget="small", colour="#E8B0B8"))
    e[54] = MeshSpec("anterior-commissure", "Anterior commissure", "cerebrum", subsystem="white-matter", budget="tiny", colour="#F5EAD8")
    e[55] = MeshSpec("posterior-commissure", "Posterior commissure", "brainstem", subsystem="midbrain", budget="tiny", colour="#F5EAD8")
    e.update(LR("basal-forebrain-cholinergic", "Basal forebrain cholinergic nuclei", "cerebrum", 56, 57, subsystem="limbic", budget="tiny", colour="#D8B890"))
    e[58] = MeshSpec("raphe-dorsal", "Dorsal raphe nucleus", "brainstem", subsystem="midbrain", budget="tiny", colour="#8A6A9A")
    e[59] = MeshSpec("raphe-median", "Median raphe nucleus", "brainstem", subsystem="pons", budget="tiny", colour="#9A7AAA")
    e.update(LR("lateral-geniculate-nucleus", "Lateral geniculate nucleus", "diencephalon", 60, 61, visible=True, budget="tiny", colour="#E0B070"))
    e.update(LR("medial-geniculate-nucleus", "Medial geniculate nucleus", "diencephalon", 62, 63, visible=True, budget="tiny", colour="#D0A060"))
    return e


# ---------------------------------------------------------------- MIAL thalamic nuclei (7 groups per side)
def mial_entries() -> dict[int, MeshSpec]:
    groups = [("thalamus-pulvinar", "Pulvinar"), ("thalamus-ventral-anterior", "Ventral anterior nucleus"),
              ("thalamus-mediodorsal", "Mediodorsal nucleus"), ("thalamus-lateral-posterior-ventral-posterior", "Lateral posterior / ventral posterior group"),
              ("thalamus-pulvinar-medial-centrolateral", "Medial pulvinar / centrolateral group"), ("thalamus-ventrolateral", "Ventrolateral nucleus"),
              ("thalamus-ventral-posterior-ventrolateral", "Ventral posterior / ventrolateral group (VPL/VPM)")]
    e = {}
    for k, (sid, name) in enumerate(groups):
        e.update(LR(sid, name, "diencephalon", k + 1, k + 8, subsystem="thalamic-nuclei", budget="tiny", colour=jitter("#E0A860", sid, 0.25)))
    return e


# ---------------------------------------------------------------- CIT168 (unlateralised labels; split by x sign)
CIT168 = {6: ("substantia-nigra-pars-compacta", "Substantia nigra, pars compacta", "brainstem", "midbrain", "#4A2E4A"),
          8: ("substantia-nigra-pars-reticulata", "Substantia nigra, pars reticulata", "brainstem", "midbrain", "#6A4E6A")}


# ---------------------------------------------------------------- Neudorfer hypothalamus (lateralised, 0.5 mm)
def hypothalamus_entries() -> dict[int, MeshSpec]:
    rows = [(9, 10, "mammillary-body", "Mammillary body"), (19, 20, "hypothalamus-medial-preoptic", "Medial preoptic nucleus"),
            (21, 22, "hypothalamus-paraventricular", "Paraventricular nucleus"), (25, 26, "hypothalamus-lateral", "Lateral hypothalamic area"),
            (27, 28, "hypothalamus-ventromedial", "Ventromedial nucleus"), (29, 30, "hypothalamus-arcuate", "Arcuate nucleus"),
            (33, 34, "bed-nucleus-stria-terminalis", "Bed nucleus of the stria terminalis"), (35, 36, "nucleus-basalis-meynert", "Nucleus basalis of Meynert"),
            (37, 38, "hypothalamus-dorsomedial", "Dorsomedial nucleus"), (41, 42, "zona-incerta", "Zona incerta"),
            (45, 46, "hypothalamus-supraoptic", "Supraoptic nucleus"), (47, 48, "hypothalamus-suprachiasmatic", "Suprachiasmatic nucleus"),
            (49, 50, "hypothalamus-tuberomammillary", "Tuberomammillary nucleus"), (51, 52, "hypothalamus-posterior", "Posterior hypothalamic nucleus"),
            (53, 54, "hypothalamus-anterior-area", "Anterior hypothalamic area"), (7, 8, "mammillothalamic-tract", "Mammillothalamic tract")]
    e = {}
    for r, l, sid, name in rows:
        sys_ = "cerebrum" if sid in ("bed-nucleus-stria-terminalis", "nucleus-basalis-meynert") else "diencephalon"
        e.update(LR(sid, name, sys_, l, r, subsystem="hypothalamus", budget="tiny", colour=jitter("#E6C27A", sid, 0.2)))
    return e


# ---------------------------------------------------------------- Diedrichsen cerebellum (34)
def diedrichsen_entries() -> dict[int, MeshSpec]:
    lob = [("I-IV", "Lobules I–IV", 1, 2, None), ("V", "Lobule V", 3, 4, None), ("VI", "Lobule VI", 5, 7, 6),
           ("crus-i", "Crus I", 8, 10, 9), ("crus-ii", "Crus II", 11, 13, 12), ("VIIb", "Lobule VIIb", 14, 16, 15),
           ("VIIIa", "Lobule VIIIa", 17, 19, 18), ("VIIIb", "Lobule VIIIb", 20, 22, 21), ("IX", "Lobule IX", 23, 25, 24),
           ("X", "Lobule X (flocculonodular)", 26, 28, 27)]
    e = {}
    for key, name, l, r, v in lob:
        sid = "cerebellar-lobule-" + key.lower().replace("–", "-")
        e.update(LR(sid, name, "cerebellum", l, r, subsystem="lobules", budget="medium", colour=jitter("#9BC49B", sid, 0.3)))
        if v:
            e[v] = MeshSpec(f"cerebellar-vermis-{key.lower()}", f"Vermis {name.replace('Lobule ', '')}", "cerebellum", subsystem="vermis",
                            budget="small", colour=jitter("#78B078", sid, 0.3), structure_id="cerebellar-vermis")
    e.update(LR("dentate-nucleus", "Dentate nucleus", "cerebellum", 29, 30, subsystem="deep-nuclei", visible=True, budget="small", colour="#4C6E4C"))
    e.update(LR("interposed-nucleus", "Interposed nuclei (emboliform + globose)", "cerebellum", 31, 32, subsystem="deep-nuclei", budget="tiny", colour="#5E805E"))
    e.update(LR("fastigial-nucleus", "Fastigial nucleus", "cerebellum", 33, 34, subsystem="deep-nuclei", budget="tiny", colour="#709270"))
    return e


# ---------------------------------------------------------------- arterial territories (Liu 2023)
TERR_COLOUR = {"ACA": "#F28E2B", "MCA": "#E15759", "PCA": "#76B7B2", "VB": "#59A14F", "LS": "#EDC948", "CH": "#B07AA1"}
ARTERIAL_L1 = [(1, 2, "territory-aca", "ACA territory", "ACA"), (3, 4, "territory-medial-lenticulostriate", "Medial lenticulostriate territory", "LS"),
               (5, 6, "territory-lateral-lenticulostriate", "Lateral lenticulostriate territory", "LS"),
               (7, 8, "territory-mca-frontal", "MCA territory, frontal", "MCA"), (9, 10, "territory-mca-parietal", "MCA territory, parietal", "MCA"),
               (11, 12, "territory-mca-temporal", "MCA territory, temporal", "MCA"), (13, 14, "territory-mca-occipital", "MCA territory, occipital", "MCA"),
               (15, 16, "territory-mca-insular", "MCA territory, insular", "MCA"), (17, 18, "territory-pca-temporal", "PCA territory, temporal", "PCA"),
               (19, 20, "territory-pca-occipital", "PCA territory, occipital", "PCA"),
               (21, 22, "territory-posterior-choroidal-thalamoperforating", "Posterior choroidal & thalamoperforating territory", "CH"),
               (23, 24, "territory-anterior-choroidal-thalamoperforating", "Anterior choroidal & thalamoperforating territory", "CH"),
               (25, 26, "territory-basilar", "Basilar (pontine) territory", "VB"), (27, 28, "territory-superior-cerebellar", "Superior cerebellar artery territory", "VB"),
               (29, 30, "territory-inferior-cerebellar", "Inferior cerebellar (PICA/AICA) territory", "VB")]
ARTERIAL_L2 = [(1, 2, "territory-aca-major", "ACA major territory", "ACA"), (3, 4, "territory-mca-major", "MCA major territory", "MCA"),
               (5, 6, "territory-pca-major", "PCA major territory", "PCA"), (7, 8, "territory-vertebrobasilar-major", "Vertebrobasilar major territory", "VB")]


def arterial_entries(level: int) -> dict[int, MeshSpec]:
    e = {}
    for l, r, sid, name, grp in (ARTERIAL_L1 if level == 1 else ARTERIAL_L2):
        e.update(LR(sid, name, "arterial-territories", l, r, subsystem=f"level{level}", budget="territory",
                    colour=jitter(TERR_COLOUR[grp], sid, 0.12), opacity=0.55))
    return e


# ---------------------------------------------------------------- HCP1065 tracts + cranial nerves (binary files)
HCP = {
    "cranial nerve/CNII": ("cn-02-optic", "Optic nerve / tract (CN II)", "cranial-nerves", None, True),
    "cranial nerve/CNIII": ("cn-03-oculomotor", "Oculomotor nerve (CN III), cisternal", "cranial-nerves", None, True),
    "cranial nerve/CNV": ("cn-05-trigeminal", "Trigeminal nerve (CN V), cisternal", "cranial-nerves", None, True),
    "cranial nerve/CNVII": ("cn-07-facial", "Facial nerve (CN VII), cisternal", "cranial-nerves", None, True),
    "cranial nerve/CNVIII": ("cn-08-vestibulocochlear", "Vestibulocochlear nerve (CN VIII), cisternal", "cranial-nerves", None, True),
    "projection/CST": ("tract-corticospinal", "Corticospinal tract", "tracts", "projection", False),
    "projection/CBT": ("tract-corticobulbar", "Corticobulbar tract", "tracts", "projection", False),
    "projection/ML": ("tract-medial-lemniscus", "Medial lemniscus", "tracts", "projection", False),
    "projection/DRTT": ("tract-dentatorubrothalamic", "Dentatorubrothalamic tract", "tracts", "cerebellar", False),
    "projection/RST": ("tract-reticulospinal", "Reticulospinal tract", "tracts", "projection", False),
    "projection/OR": ("tract-optic-radiation", "Optic radiation", "tracts", "projection", False),
    "projection/AR": ("tract-acoustic-radiation", "Acoustic radiation", "tracts", "projection", False),
    "projection/F": ("tract-fornix", "Fornix (HCP)", "tracts", "limbic", False),
    "projection/TR_A": ("tract-thalamic-radiation-anterior", "Anterior thalamic radiation", "tracts", "projection", False),
    "projection/TR_P": ("tract-thalamic-radiation-posterior", "Posterior thalamic radiation", "tracts", "projection", False),
    "projection/TR_S": ("tract-thalamic-radiation-superior", "Superior thalamic radiation", "tracts", "projection", False),
    "projection/CPT_F": ("tract-corticopontine-frontal", "Frontopontine tract", "tracts", "projection", False),
    "projection/CPT_P": ("tract-corticopontine-parietal", "Parietopontine tract", "tracts", "projection", False),
    "projection/CPT_O": ("tract-corticopontine-occipital", "Occipitopontine tract", "tracts", "projection", False),
    "projection/CS_A": ("tract-corticostriatal-anterior", "Corticostriatal tract, anterior", "tracts", "projection", False),
    "projection/CS_P": ("tract-corticostriatal-posterior", "Corticostriatal tract, posterior", "tracts", "projection", False),
    "projection/CS_S": ("tract-corticostriatal-superior", "Corticostriatal tract, superior", "tracts", "projection", False),
    "cerebellum/ICP": ("inferior-cerebellar-peduncle", "Inferior cerebellar peduncle", "cerebellum", "peduncles", False),
    "cerebellum/MCP": ("middle-cerebellar-peduncle", "Middle cerebellar peduncle", "cerebellum", "peduncles", False),
    "cerebellum/SCP": ("superior-cerebellar-peduncle", "Superior cerebellar peduncle", "cerebellum", "peduncles", False),
    "commissural/AC": ("tract-anterior-commissure", "Anterior commissure (HCP)", "tracts", "commissural", False),
    "commissural/CC": ("tract-corpus-callosum", "Corpus callosum fibres (HCP)", "tracts", "commissural", False),
    "association/AF": ("tract-arcuate-fasciculus", "Arcuate fasciculus", "tracts", "association", False),
    "association/IFOF": ("tract-inferior-fronto-occipital-fasciculus", "Inferior fronto-occipital fasciculus", "tracts", "association", False),
    "association/ILF": ("tract-inferior-longitudinal-fasciculus", "Inferior longitudinal fasciculus", "tracts", "association", False),
    "association/UF": ("tract-uncinate-fasciculus", "Uncinate fasciculus", "tracts", "association", False),
    "association/SLF1": ("tract-superior-longitudinal-fasciculus-i", "Superior longitudinal fasciculus I", "tracts", "association", False),
    "association/SLF2": ("tract-superior-longitudinal-fasciculus-ii", "Superior longitudinal fasciculus II", "tracts", "association", False),
    "association/SLF3": ("tract-superior-longitudinal-fasciculus-iii", "Superior longitudinal fasciculus III", "tracts", "association", False),
    "association/MdLF": ("tract-middle-longitudinal-fasciculus", "Middle longitudinal fasciculus", "tracts", "association", False),
    "association/FAT": ("tract-frontal-aslant", "Frontal aslant tract", "tracts", "association", False),
    "association/C_FP": ("tract-cingulum-frontoparietal", "Cingulum, fronto-parietal", "tracts", "limbic", False),
    "association/C_PH": ("tract-cingulum-parahippocampal", "Cingulum, parahippocampal", "tracts", "limbic", False),
}


def hcp_entries() -> dict[str, MeshSpec]:
    e = {}
    for key, (sid, name, system, sub, vis) in HCP.items():
        colour = "#F2E394" if system == "cranial-nerves" else jitter("#EDE3D2", sid, 0.35)
        if key.startswith("commissural/") or key in ("cerebellum/MCP", "cerebellum/SCP"):
            e[key] = MeshSpec(sid, name, system, subsystem=sub, side="midline", visible=vis, budget="tract", colour=colour, opacity=0.9)
            continue
        for side, sfx in (("left", "_L"), ("right", "_R")):
            f = key + sfx
            e[f] = MeshSpec(f"{sid}-{sfx[1].lower()}", f"{name} ({sfx[1]})", system, subsystem=sub, side=side, visible=vis,
                            budget="tract" if system == "tracts" or "peduncle" in sid else "small", colour=colour, structure_id=sid, opacity=0.9)
    return e


# ---------------------------------------------------------------- atlases in build order
def atlases() -> list[AtlasSpec]:
    return [
        AtlasSpec("mni_aseg", "mni_aseg/tpl-MNI152NLin2009cAsym_res-01_seg-aseg_dseg.nii.gz", "mni2009", priority=1, entries=aseg_entries()),
        AtlasSpec("harvard_oxford", "harvard_oxford/tpl-MNI152NLin2009cAsym_res-01_atlas-HOCPAL_desc-th25_dseg.nii.gz", "mni2009", priority=2, entries=hocpal_entries()),
        AtlasSpec("diedrichsen_cerebellum", "diedrichsen_cerebellum/atl-Anatom_space-MNI_dseg.nii", "nlin6", priority=3, entries=diedrichsen_entries()),
        AtlasSpec("hypothalamus_neudorfer", "hypothalamus_neudorfer/MNI152b_atlas_labels_0.5mm.nii.gz", "mni2009", priority=4, entries=hypothalamus_entries()),
        AtlasSpec("cit168", "cit168/CIT168toMNI152-2009c_det.nii.gz", "mni2009", priority=5,
                  entries={k: MeshSpec(v[0], v[1], v[2], subsystem=v[3], colour=v[4], budget="tiny", side="bilateral") for k, v in CIT168.items()}),
        AtlasSpec("mial_thalamus", "mial_thalamus/tpl-MNI152NLin2009cAsym_res-01_atlas-MIAL67ThalamicNuclei_dseg.nii.gz", "mni2009", priority=6, entries=mial_entries()),
        AtlasSpec("massp", "massp/tpl-MNI152NLin2009cAsym_res-01_atlas-MASSP20_dseg.nii.gz", "mni2009", priority=7, entries=massp_entries()),
        AtlasSpec("arterial_l2", "arterial_territories/ArterialAtlas_level2.nii", "nlin6", priority=1, label_volume="vascular2", fix="arterial", entries=arterial_entries(2)),
        AtlasSpec("arterial_l1", "arterial_territories/ArterialAtlas.nii", "nlin6", priority=2, label_volume="vascular", fix="arterial", entries=arterial_entries(1)),
        AtlasSpec("hcp1065_tracts", "hcp1065_tracts/nifti", "mni2009", kind="binary", priority=1, label_volume="tract", files=hcp_entries()),
    ]


ENVELOPE = MeshSpec("brain-envelope", "Brain surface (mask)", "envelope", visible=True, budget="large", colour="#E6D5C3", opacity=0.18)
ARTERIES_MRA = MeshSpec("arteries-mra-atlas", "Cerebral arteries (MRA atlas iso-surface)", "arteries", subsystem="mra", visible=True, budget="vessel", colour="#C0392B")
