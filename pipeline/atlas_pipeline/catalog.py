"""Curated catalogue: which atlas labels become which meshes, with stable ids, names, systems, colours.

Mesh id = content structure id (+ "-l"/"-r" for paired structures). Never expose raw atlas ints.
"""
from __future__ import annotations

import colorsys
import hashlib
from dataclasses import dataclass, field

# ---------------------------------------------------------------- systems (shared with content + UI)
# Anatomical palette (fresh-tissue tones): cortex pinkish-grey, white matter cream, deep nuclei muted tan/rose,
# brainstem/cord pale tan, cerebellum a shade darker, arteries saturated red, veins deep blue, nerves pale yellow,
# CSF light blue, dura grey. Per-mesh overrides live in the entries below and in the BP3D/Z-Anatomy selection yaml.
SYSTEMS = [
    ("cerebrum", "Cerebrum", "#D0AB9E", True),
    ("basal-ganglia", "Basal ganglia", "#C4948C", True),
    ("diencephalon", "Diencephalon", "#C9A27E", True),
    ("brainstem", "Brainstem", "#D2B79A", True),
    ("cerebellum", "Cerebellum", "#B89C86", True),
    ("cranial-nerves", "Cranial nerves", "#EFE3A8", True),
    ("spinal-cord", "Spinal cord", "#D6BFA2", False),
    ("peripheral", "Peripheral nerves", "#F0E4B0", False),
    ("autonomic", "Autonomic", "#E8D9A0", False),
    ("ventricles-csf", "Ventricles & CSF", "#9CC8E6", True),
    ("meninges", "Meninges", "#B9BCC2", False),
    ("arteries", "Arteries", "#C42B2B", True),
    ("arterial-territories", "Arterial territories", "#E07B5A", False),
    ("venous", "Venous sinuses", "#2F4C8F", False),
    ("tracts", "White-matter tracts", "#EDE3D2", False),
    ("envelope", "Brain surface", "#DCBFAE", True),
]
SYSTEM_COLOUR = {s[0]: s[2] for s in SYSTEMS}

# subtle per-lobe tints on a pinkish-grey cortex so lobes stay tellable without looking painted
LOBE_COLOUR = {"frontal": "#D4AA9C", "parietal": "#CBA8A8", "temporal": "#D6B29A", "occipital": "#C7A3A9",
               "insula": "#D09E97", "limbic": "#D2A6A3"}

# triangle budgets per size class
BUDGET = {"huge": 60000, "large": 40000, "cortical": 20000, "medium": 8000, "small": 4000, "tiny": 2000,
          "tract": 20000, "territory": 16000, "vessel": 60000}
# one class up for vessels and nerves (bifurcations and thin tubes lose shape first under decimation)
BUDGET_BUMP = {"tiny": "small", "small": "medium", "medium": "large", "large": "huge"}
LOD_FACES = 3000          # stand-in size for the first paint
LOD_MIN_FACES = 12000     # meshes at or above this get a stand-in


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
    alignment: str | None = None   # overrides the alignment string recorded per mesh (see atlas_meshes)
    edition: str | None = None     # "public" -> the mesh exists only in the public edition (see manifest.py)


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
    e.update(LR("ventricle-lateral", "Lateral ventricle", "ventricles-csf", 4, 43, visible=True, budget="large", colour="#9CC8E6", opacity=0.6))
    e.update(LR("ventricle-lateral-inferior-horn", "Lateral ventricle, inferior (temporal) horn", "ventricles-csf", 5, 44, budget="small", colour="#A6CFEA", opacity=0.6))
    e[14] = MeshSpec("ventricle-third", "Third ventricle", "ventricles-csf", visible=True, budget="small", colour="#8FC0E2", opacity=0.6)
    e[15] = MeshSpec("ventricle-fourth", "Fourth ventricle", "ventricles-csf", visible=True, budget="small", colour="#86B9DE", opacity=0.6)
    e[16] = MeshSpec("brainstem", "Brainstem", "brainstem", visible=True, budget="large", colour="#D2B79A")
    e.update(LR("cerebellar-hemisphere", "Cerebellar hemisphere (cortex)", "cerebellum", 8, 47, visible=True, budget="large", colour="#B5978A"))
    e.update(LR("cerebellar-white-matter", "Cerebellar white matter", "cerebellum", 7, 46, budget="large", colour="#EDE3D3"))
    e.update(LR("hippocampus", "Hippocampus", "cerebrum", 17, 53, subsystem="limbic", visible=True, budget="medium", colour="#CFA095"))
    e.update(LR("cerebral-white-matter", "Cerebral white matter", "cerebrum", 2, 41, subsystem="white-matter", budget="huge", colour="#F1E9DA", opacity=0.9))
    for lab in (251, 252, 253, 254, 255):
        e[lab] = MeshSpec("corpus-callosum", "Corpus callosum", "cerebrum", subsystem="white-matter", visible=True, budget="medium", colour="#F4EEE2")
    e.update(LR("ventral-diencephalon", "Ventral diencephalon (FreeSurfer)", "diencephalon", 28, 60, budget="medium", colour="#C9A27E"))
    return e


# ---------------------------------------------------------------- MASSP (63)
def massp_entries() -> dict[int, MeshSpec]:
    e = {}
    e.update(LR("caudate-nucleus", "Caudate nucleus", "basal-ganglia", 1, 2, visible=True, budget="medium", colour="#C99089"))
    e.update(LR("subthalamic-nucleus", "Subthalamic nucleus", "basal-ganglia", 3, 4, visible=True, budget="tiny", colour="#B27A78"))
    e.update(LR("substantia-nigra", "Substantia nigra", "brainstem", 5, 6, subsystem="midbrain", visible=True, budget="small", colour="#5A4450"))
    e.update(LR("red-nucleus", "Red nucleus", "brainstem", 7, 8, subsystem="midbrain", visible=True, budget="tiny", colour="#C4665A"))
    e.update(LR("globus-pallidus-internus", "Globus pallidus, internal segment", "basal-ganglia", 9, 10, visible=True, budget="small", colour="#B8857F"))
    e.update(LR("globus-pallidus-externus", "Globus pallidus, external segment", "basal-ganglia", 11, 12, visible=True, budget="small", colour="#C08C86"))
    e.update(LR("thalamus", "Thalamus", "diencephalon", 13, 14, visible=True, budget="medium", colour="#C9A27E"))
    e.update(LR("amygdala", "Amygdala", "cerebrum", 19, 20, subsystem="limbic", visible=True, budget="small", colour="#C69A8E"))
    e.update(LR("internal-capsule", "Internal capsule", "cerebrum", 21, 22, subsystem="white-matter", visible=True, budget="medium", colour="#EEE6D6"))
    e.update(LR("ventral-tegmental-area", "Ventral tegmental area", "brainstem", 23, 24, subsystem="midbrain", budget="tiny", colour="#8E6E7E"))
    e[25] = MeshSpec("fornix", "Fornix", "cerebrum", subsystem="limbic", visible=True, budget="small", colour="#EFE2CC")
    e.update(LR("periaqueductal-grey", "Periaqueductal grey", "brainstem", 26, 27, subsystem="midbrain", budget="tiny", colour="#A08A96"))
    e.update(LR("pedunculopontine-nucleus", "Pedunculopontine nucleus", "brainstem", 28, 29, subsystem="pons", budget="tiny", colour="#AC9AA4"))
    e.update(LR("claustrum", "Claustrum", "basal-ganglia", 30, 31, budget="small", colour="#CDA098"))
    e.update(LR("inferior-colliculus", "Inferior colliculus", "brainstem", 32, 33, subsystem="midbrain", visible=True, budget="tiny", colour="#C4A6A0"))
    e.update(LR("superior-colliculus", "Superior colliculus", "brainstem", 34, 35, subsystem="midbrain", visible=True, budget="tiny", colour="#CCB0A8"))
    e.update(LR("habenula", "Lateral habenula", "diencephalon", 36, 37, budget="tiny", colour="#C8A882"))
    e.update(LR("putamen", "Putamen", "basal-ganglia", 38, 39, visible=True, budget="medium", colour="#C98E86"))
    e.update(LR("nucleus-accumbens", "Nucleus accumbens", "basal-ganglia", 40, 41, budget="tiny", colour="#CFA09A"))
    e.update(LR("hippocampus-ca1", "Hippocampus CA1", "cerebrum", 42, 43, subsystem="limbic", budget="small", colour="#D2A69B"))
    e.update(LR("hippocampus-ca23", "Hippocampus CA2/CA3", "cerebrum", 44, 45, subsystem="limbic", budget="tiny", colour="#CC9E93"))
    e.update(LR("dentate-gyrus", "Dentate gyrus", "cerebrum", 46, 47, subsystem="limbic", budget="tiny", colour="#C6968C"))
    e.update(LR("presubiculum", "Presubiculum", "cerebrum", 48, 49, subsystem="limbic", budget="tiny", colour="#DAB3A8"))
    e.update(LR("subiculum", "Subiculum", "cerebrum", 50, 51, subsystem="limbic", budget="tiny", colour="#DDB8AE"))
    e.update(LR("uncus", "Uncus", "cerebrum", 52, 53, subsystem="limbic", visible=True, budget="small", colour="#D3ACA2"))
    e[54] = MeshSpec("anterior-commissure", "Anterior commissure", "cerebrum", subsystem="white-matter", budget="tiny", colour="#F0E6D6")
    e[55] = MeshSpec("posterior-commissure", "Posterior commissure", "brainstem", subsystem="midbrain", budget="tiny", colour="#F0E6D6")
    e.update(LR("basal-forebrain-cholinergic", "Basal forebrain cholinergic nuclei", "cerebrum", 56, 57, subsystem="limbic", budget="tiny", colour="#CDB090"))
    e[58] = MeshSpec("raphe-dorsal", "Dorsal raphe nucleus", "brainstem", subsystem="midbrain", budget="tiny", colour="#A48C90")
    e[59] = MeshSpec("raphe-median", "Median raphe nucleus", "brainstem", subsystem="pons", budget="tiny", colour="#AE979C")
    e.update(LR("lateral-geniculate-nucleus", "Lateral geniculate nucleus", "diencephalon", 60, 61, visible=True, budget="tiny", colour="#C9A27E"))
    e.update(LR("medial-geniculate-nucleus", "Medial geniculate nucleus", "diencephalon", 62, 63, visible=True, budget="tiny", colour="#C29A78"))
    return e


# ---------------------------------------------------------------- MIAL thalamic nuclei (7 groups per side)
def mial_entries() -> dict[int, MeshSpec]:
    groups = [("thalamus-pulvinar", "Pulvinar"), ("thalamus-ventral-anterior", "Ventral anterior nucleus"),
              ("thalamus-mediodorsal", "Mediodorsal nucleus"), ("thalamus-lateral-posterior-ventral-posterior", "Lateral posterior / ventral posterior group"),
              ("thalamus-pulvinar-medial-centrolateral", "Medial pulvinar / centrolateral group"), ("thalamus-ventrolateral", "Ventrolateral nucleus"),
              ("thalamus-ventral-posterior-ventrolateral", "Ventral posterior / ventrolateral group (VPL/VPM)")]
    e = {}
    for k, (sid, name) in enumerate(groups):
        e.update(LR(sid, name, "diencephalon", k + 1, k + 8, subsystem="thalamic-nuclei", budget="tiny", colour=jitter("#C9A27E", sid, 0.18)))
    return e


# ---------------------------------------------------------------- CIT168 (unlateralised labels; split by x sign)
CIT168 = {6: ("substantia-nigra-pars-compacta", "Substantia nigra, pars compacta", "brainstem", "midbrain", "#4E3A48"),
          8: ("substantia-nigra-pars-reticulata", "Substantia nigra, pars reticulata", "brainstem", "midbrain", "#6E5A66")}


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
        e.update(LR(sid, name, sys_, l, r, subsystem="hypothalamus", budget="tiny", colour=jitter("#CDA880", sid, 0.16)))
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
        e.update(LR(sid, name, "cerebellum", l, r, subsystem="lobules", budget="medium", colour=jitter("#B5978A", sid, 0.16)))
        if v:
            e[v] = MeshSpec(f"cerebellar-vermis-{key.lower()}", f"Vermis {name.replace('Lobule ', '')}", "cerebellum", subsystem="vermis",
                            budget="small", colour=jitter("#A88B7E", sid, 0.16), structure_id="cerebellar-vermis")
    e.update(LR("dentate-nucleus", "Dentate nucleus", "cerebellum", 29, 30, subsystem="deep-nuclei", visible=True, budget="small", colour="#8A6E64"))
    e.update(LR("interposed-nucleus", "Interposed nuclei (emboliform + globose)", "cerebellum", 31, 32, subsystem="deep-nuclei", budget="tiny", colour="#957A70"))
    e.update(LR("fastigial-nucleus", "Fastigial nucleus", "cerebellum", 33, 34, subsystem="deep-nuclei", budget="tiny", colour="#9F857B"))
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
    "projection/ML": ("tract-medial-lemniscus", "Medial lemniscus", "tracts", "projection", False, "medial-lemniscus"),
    "projection/DRTT": ("tract-dentatorubrothalamic", "Dentatorubrothalamic tract", "tracts", "cerebellar", False),
    "projection/RST": ("tract-reticulospinal", "Reticulospinal tract", "tracts", "projection", False),
    "projection/OR": ("tract-optic-radiation", "Optic radiation", "tracts", "projection", False),
    "projection/AR": ("tract-acoustic-radiation", "Acoustic radiation", "tracts", "projection", False),
    "projection/F": ("tract-fornix", "Fornix (HCP)", "tracts", "limbic", False, "fornix"),
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
    "commissural/AC": ("tract-anterior-commissure", "Anterior commissure (HCP)", "tracts", "commissural", False, "anterior-commissure"),
    "commissural/CC": ("tract-corpus-callosum", "Corpus callosum fibres (HCP)", "tracts", "commissural", False, "corpus-callosum"),
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
    for key, row in HCP.items():
        sid, name, system, sub, vis = row[:5]
        structure_id = row[5] if len(row) > 5 else sid   # some tract meshes belong to an already-authored structure
        colour = "#EFE3A8" if system == "cranial-nerves" else jitter("#EDE3D2", sid, 0.35)
        if key.startswith("commissural/") or key in ("cerebellum/MCP", "cerebellum/SCP"):
            e[key] = MeshSpec(sid, name, system, subsystem=sub, side="midline", visible=vis, budget="tract", colour=colour, opacity=0.9, structure_id=structure_id)
            continue
        for side, sfx in (("left", "_L"), ("right", "_R")):
            f = key + sfx
            e[f] = MeshSpec(f"{sid}-{sfx[1].lower()}", f"{name} ({sfx[1]})", system, subsystem=sub, side=side, visible=vis,
                            budget="tract" if system == "tracts" or "peduncle" in sid else "small", colour=colour, structure_id=structure_id, opacity=0.9)
    return e


# ================================================================ CerebrA / DKT31 cortex (PUBLIC edition only)
# Harvard-Oxford is FSL non-commercial, so the public edition cannot ship the 48 HO gyri. CerebrA
# (Manera et al., Sci Data 2020; G-Node doi:10.12751/g-node.be5e62, CC0 1.0) is the Mindboggle-101 DKT
# labelling non-linearly registered and hand-corrected onto MNI-ICBM152 2009c, and is free to redistribute.
# It is defined on the *symmetric* 2009c template on the same 193x229x193 1 mm grid as ours; atlas_meshes
# warps it onto our asymmetric grid when antspyx is installed and otherwise takes it as-is (see
# atlas_meshes.cerebra_source), which is what `alignment` on each record then says.
#
# Only the 62 cortical parcels are meshed here: CerebrA's subcortical and cerebellar labels are already
# covered, in our own space, by the FreeSurfer aseg meshes (MNI licence, so they ship in both editions).
#
# label ints = the `label` column of raw/cerebra/tpl-MNI152NLin2009cSym_atlas-CerebA_dseg.tsv; the tsv's
# "mindboggle mapping" column is the FreeSurfer aparc.DKTatlas id of the right-hemisphere region.
# structure id = the content entry this parcel belongs to, so both editions keep every mesh described
# (the same entries the HO gyri point at; see pipeline/config/ho_to_dkt.yaml for the full mapping).
DKT31 = [
    # key, name, lobe (LOBE_COLOUR), content structure id, CerebrA label L, CerebrA label R
    ("caudal-anterior-cingulate", "Caudal anterior cingulate cortex", "limbic", "gyrus-cingulate-anterior", 81, 30),
    ("caudal-middle-frontal", "Caudal middle frontal gyrus", "frontal", "gyrus-middle-frontal", 93, 42),
    ("cuneus", "Cuneus", "occipital", "cuneus", 94, 43),
    ("entorhinal", "Entorhinal cortex", "limbic", "gyrus-parahippocampal-anterior", 87, 36),
    ("fusiform", "Fusiform gyrus", "temporal", "cortex-temporal-fusiform-posterior", 75, 24),
    ("inferior-parietal", "Inferior parietal lobule (angular gyrus)", "parietal", "gyrus-angular", 61, 10),
    ("inferior-temporal", "Inferior temporal gyrus", "temporal", "gyrus-inferior-temporal-posterior", 54, 3),
    ("isthmus-cingulate", "Isthmus of the cingulate gyrus", "limbic", "gyrus-cingulate-posterior", 84, 33),
    ("lateral-occipital", "Lateral occipital cortex", "occipital", "cortex-lateral-occipital-superior", 85, 34),
    ("lateral-orbitofrontal", "Lateral orbitofrontal cortex", "frontal", "cortex-orbitofrontal", 58, 7),
    ("lingual", "Lingual gyrus", "occipital", "gyrus-lingual", 63, 12),
    ("medial-orbitofrontal", "Medial orbitofrontal cortex", "frontal", "cortex-frontal-medial", 66, 15),
    ("middle-temporal", "Middle temporal gyrus", "temporal", "gyrus-middle-temporal-posterior", 79, 28),
    ("paracentral", "Paracentral lobule", "frontal", "cortex-supplementary-motor", 67, 16),
    ("parahippocampal", "Parahippocampal gyrus", "limbic", "gyrus-parahippocampal-posterior", 69, 18),
    ("pars-opercularis", "Inferior frontal gyrus, pars opercularis", "frontal", "gyrus-inferior-frontal-opercularis", 83, 32),
    ("pars-orbitalis", "Inferior frontal gyrus, pars orbitalis", "frontal", "cortex-orbitofrontal", 95, 44),
    ("pars-triangularis", "Inferior frontal gyrus, pars triangularis", "frontal", "gyrus-inferior-frontal-triangularis", 73, 22),
    ("pericalcarine", "Pericalcarine cortex", "occipital", "cortex-intracalcarine", 57, 6),
    ("postcentral", "Postcentral gyrus", "parietal", "gyrus-postcentral", 64, 13),
    ("posterior-cingulate", "Posterior cingulate cortex", "limbic", "gyrus-cingulate-posterior", 98, 47),
    ("precentral", "Precentral gyrus", "frontal", "gyrus-precentral", 86, 35),
    ("precuneus", "Precuneus", "parietal", "precuneus", 82, 31),
    ("rostral-anterior-cingulate", "Rostral anterior cingulate cortex", "limbic", "gyrus-cingulate-anterior", 59, 8),
    ("rostral-middle-frontal", "Rostral middle frontal gyrus", "frontal", "gyrus-middle-frontal", 52, 1),
    ("superior-frontal", "Superior frontal gyrus", "frontal", "gyrus-superior-frontal", 89, 38),
    ("superior-parietal", "Superior parietal lobule", "parietal", "lobule-superior-parietal", 60, 9),
    ("superior-temporal", "Superior temporal gyrus", "temporal", "gyrus-superior-temporal-posterior", 96, 45),
    ("supramarginal", "Supramarginal gyrus", "parietal", "gyrus-supramarginal", 102, 51),
    ("transverse-temporal", "Transverse temporal gyrus (Heschl)", "temporal", "gyrus-heschl", 65, 14),
    ("insula", "Insular cortex", "insula", "insula", 74, 23),
]
CEREBRA_FILE = "cerebra/tpl-MNI152NLin2009cSym_res-1_atlas-CerebrA_dseg.nii.gz"


def cerebra_entries() -> dict[int, MeshSpec]:
    """CerebrA label -> mesh. Not LR(), because the content structure id is not the mesh id here."""
    e = {}
    for key, name, lobe, sid, lab_l, lab_r in DKT31:
        for lab, side, sfx in ((lab_l, "left", "-l"), (lab_r, "right", "-r")):
            e[lab] = MeshSpec(id=f"dkt-{key}{sfx}", name=f"{name} ({'L' if side == 'left' else 'R'})",
                              system="cerebrum", subsystem=f"lobe-{lobe}", side=side, visible=True,
                              budget="cortical", colour=jitter(LOBE_COLOUR[lobe], f"dkt-{key}"),
                              opacity=1.0, structure_id=sid)
    return e


def cerebra_atlas(file: str | None = None, alignment: str = "nlin2009csym-identity") -> AtlasSpec:
    """The CerebrA cortex as an atlas spec. `file` overrides the raw path (used for the warped copy)."""
    return AtlasSpec("cerebra", file or CEREBRA_FILE, "mni2009", priority=2, alignment=alignment,
                     edition="public", entries=cerebra_entries())


# ================================================================ FastSurfer CerebNet cerebellum (PUBLIC edition only)
# The Diedrichsen cerebellar atlas is CC BY-NC 3.0, so the public edition cannot ship the 34 lobule meshes.
# The stand-in is not another atlas but a segmentation of our own template: FastSurfer v2.5.4 (Apache-2.0,
# Henschel 2020) was run on raw/mni_t1w/tpl-MNI152NLin2009cAsym_res-01_T1w.nii.gz -- FastSurferVINN for the
# aseg/DKT prior, then the CerebNet module (Faber 2022) for the cerebellum -- and the label volume that came
# out is our own derivative of the MNI template, released here under CC BY-SA 4.0. The exact commands, the
# tool commit and the checkpoint licences are in raw/fastsurfer_cerebellum/SOURCE.json.
#
# The labels are FreeSurfer ids 601-631 (FastSurferCNN/config/FreeSurferColorLUT.txt, "Cbm_*"). CerebNet's
# vermis is coarser than the Diedrichsen one: it has VI, VII (crus I + crus II + VIIb together), VIII
# (VIIIa + VIIIb), IX and X -- five vermian parcels where the private edition has eight. The deep nuclei are
# not segmented at all, so dentate/interposed/fastigial keep the aseg cerebellar white matter as their
# public-edition fallback, exactly as before.
#
# ids are suffixed "-fs" so they never collide with the private-edition ids, and the colours are the same
# jitter of the cerebellum tone keyed on the same structure id, so a lobule looks the same in both editions.
FASTSURFER_CEREB_FILE = "fastsurfer_cerebellum/tpl-MNI152NLin2009cAsym_res-01_atlas-CerebNet_dseg.nii.gz"

# key, display name, FreeSurfer label L, R, vermis label (None when CerebNet has no vermian parcel for it)
CEREBNET_LOBULES = [
    ("i-iv", "Lobules I\u2013IV", 601, 602, None), ("v", "Lobule V", 603, 604, None),
    ("vi", "Lobule VI", 605, 607, 606), ("crus-i", "Crus I", 608, 610, None),
    ("crus-ii", "Crus II", 611, 613, None), ("viib", "Lobule VIIb", 614, 616, None),
    ("viiia", "Lobule VIIIa", 617, 619, None), ("viiib", "Lobule VIIIb", 620, 622, None),
    ("ix", "Lobule IX", 623, 625, 624), ("x", "Lobule X (flocculonodular)", 626, 628, 627),
]
# vermian parcels CerebNet reports as a group rather than per lobule
CEREBNET_VERMIS_GROUPS = [("vii", "Vermis VII (crus I, crus II and VIIb)", 630),
                          ("viii", "Vermis VIII (VIIIa and VIIIb)", 631)]


def fastsurfer_cerebellum_entries() -> dict[int, MeshSpec]:
    """CerebNet FreeSurfer label -> mesh. Not LR(), because the content structure id is not the mesh id here."""
    e: dict[int, MeshSpec] = {}
    for key, name, lab_l, lab_r, lab_v in CEREBNET_LOBULES:
        sid = f"cerebellar-lobule-{key}"
        for lab, side, sfx in ((lab_l, "left", "-l"), (lab_r, "right", "-r")):
            e[lab] = MeshSpec(id=f"{sid}-fs{sfx}", name=f"{name} ({'L' if side == 'left' else 'R'})",
                              system="cerebellum", subsystem="lobules", side=side, budget="medium",
                              colour=jitter("#B5978A", sid, 0.16), structure_id=sid)
        if lab_v:
            e[lab_v] = MeshSpec(f"cerebellar-vermis-{key}-fs", f"Vermis {name.replace('Lobule ', '')}", "cerebellum",
                                subsystem="vermis", budget="small", colour=jitter("#A88B7E", sid, 0.16),
                                structure_id="cerebellar-vermis")
    for key, name, lab in CEREBNET_VERMIS_GROUPS:
        e[lab] = MeshSpec(f"cerebellar-vermis-{key}-fs", name, "cerebellum", subsystem="vermis", budget="small",
                          colour=jitter("#A88B7E", f"cerebellar-lobule-{key}", 0.16), structure_id="cerebellar-vermis")
    return e


def fastsurfer_cerebellum_atlas(file: str | None = None) -> AtlasSpec:
    """The CerebNet cerebellum as an atlas spec (segmented on our own template, so it is already native)."""
    return AtlasSpec("fastsurfer_cerebellum", file or FASTSURFER_CEREB_FILE, "mni2009", priority=3,
                     alignment="native-mni", edition="public", entries=fastsurfer_cerebellum_entries())


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


ENVELOPE = MeshSpec("brain-envelope", "Brain surface (mask)", "envelope", visible=True, budget="huge", colour="#DCBFAE", opacity=0.12)
ARTERIES_MRA = MeshSpec("arteries-mra-atlas", "Cerebral arteries (MRA atlas iso-surface)", "arteries", subsystem="mra", visible=True, budget="vessel", colour="#C42B2B")


# ================================================================ VENAT venous atlas (Huck et al. 2019)
# Meshes cut out of the thresholded venous partial-volume map by atlas_pipeline.venat. The whole
# iso-surface is the venous counterpart of ARTERIES_MRA; the named deep veins are region cuts of the
# same voxel mask. Venous palette = the "venous" system colour (#2F4C8F) with small deliberate shifts
# so the deep veins stay tellable from the dural sinus meshes that come from Z-Anatomy.
# NOTE: the mesh id `sinus-straight` is already used by the Z-Anatomy dural sinus, so the VENAT surface
# is `sinus-straight-venat` and keeps `sinus-straight` as its content structure id.
VEINS_VENAT = MeshSpec("veins-venat-atlas", "Cerebral veins and sinuses (VENAT atlas iso-surface)", "venous",
                       subsystem="venat", visible=True, budget="vessel", colour="#2F4C8F")


def venat_entries() -> dict[str, MeshSpec]:
    """mesh id -> spec for every VENAT-derived mesh (whole iso-surface + named deep veins)."""
    e: dict[str, MeshSpec] = {VEINS_VENAT.id: VEINS_VENAT}
    for base, name, colour, budget in (
        ("vein-internal-cerebral", "Internal cerebral vein", "#33528F", "medium"),
        ("vein-basal", "Basal vein (of Rosenthal)", "#3A5A9B", "medium"),
    ):
        for side, sfx in (("left", "-l"), ("right", "-r")):
            e[base + sfx] = MeshSpec(id=base + sfx, name=f"{name} ({'L' if side == 'left' else 'R'})", system="venous",
                                     subsystem="deep veins", side=side, structure_id=base, budget=budget, colour=colour)
    e["vein-great-cerebral"] = MeshSpec("vein-great-cerebral", "Great cerebral vein (of Galen)", "venous",
                                        subsystem="deep veins", side="midline", budget="small", colour="#2F4C8F")
    e["sinus-straight-venat"] = MeshSpec("sinus-straight-venat", "Straight sinus (VENAT atlas)", "venous",
                                         subsystem="dural sinuses", side="midline", budget="medium",
                                         colour="#2A4480", structure_id="sinus-straight")
    return e



# ================================================================ Harvard AAN atlas (PUBLIC edition only)
# The Brainstem Navigator delineations of these four nuclei may not be redistributed, so the public
# edition carries the Harvard Ascending Arousal Network atlas v2.0 instead (source id `aan_atlas`,
# CC0 1.0; Dryad doi:10.5061/dryad.zw3r228d2). Only the nodes with no open mesh yet are listed: the
# locus coeruleus has the Dahl meta mask, and PAG, VTA, DR, MnR and PTg (this atlas's name for the
# pedunculopontine nucleus) come from MASSP20, which ships in both editions.
#
# PBC is one node covering the whole parabrachial complex, so it hangs off the lateral parabrachial
# entry; the medial parabrachial entry gets the landmark-anchored ellipsoid from `atlas-derived`.
# Colours are the ones pipeline/config/brainstem_navigator.yaml gives the same structures, so the two
# editions look alike. Built by atlas_pipeline.aan (`atlas-aan`).
AAN_NODES = [
    # node, content structure id, display name, subsystem, colour
    ("PBC", "nucleus-parabrachial-lateral", "Parabrachial complex", "pons", "#AC949A"),
    ("LDTg", "nucleus-laterodorsal-tegmental", "Laterodorsal tegmental nucleus", "pons", "#A99BA6"),
    ("PnO", "reticular-formation-pontine", "Oral pontine reticular nucleus", "pons", "#BCA69C"),
    ("mRt", "reticular-formation-mesencephalic", "Mesencephalic reticular formation", "midbrain", "#B8A39B"),
]
# mesh id -> AAN node abbreviation (the file name stem), filled in by aan_entries()
AAN_NODE_OF: dict[str, str] = {}


def aan_entries() -> dict[str, MeshSpec]:
    """mesh id -> spec for every AAN node meshed into the public edition (both sides)."""
    e: dict[str, MeshSpec] = {}
    for node, sid, name, sub, colour in AAN_NODES:
        for side, sfx in (("left", "-l"), ("right", "-r")):
            # `<entry-id>-aan-l`, never `<entry-id>-l`: scripts/check-public.ts rejects any text holding an
            # excluded mesh id, and the private edition already owns `<entry-id>-l`.
            mid = f"{sid}-aan{sfx}"
            AAN_NODE_OF[mid] = node
            e[mid] = MeshSpec(id=mid, name=f"{name} ({'L' if side == 'left' else 'R'}, AAN atlas)",
                              system="brainstem", subsystem=sub, side=side, budget="tiny", colour=colour,
                              visible=False, structure_id=sid)
    return e


aan_entries()   # populate AAN_NODE_OF at import time

# ================================================================ locus coeruleus meta mask (PUBLIC edition only)
# The Brainstem Navigator LC label may not be redistributed, so the public edition carries the openly
# licensed Dahl et al. 2022 LC "meta mask" instead (source id `lc_metamask`, CC BY 4.0; OSF sf2ky).
# It is a *consensus* volume of interest aggregated across six published LC maps, not a delineation of
# one nucleus in one template, so it is deliberately a little larger than the LC itself -- the content
# entry says so. Colour is the same #6E7FA0 the private LC uses, so the two editions look alike, and
# the structure id is `locus-coeruleus` so both hang off the same content entry.
# Built by atlas_pipeline.lc_metamask (`atlas-lc-metamask`).
LC_METAMASK_COLOUR = "#6E7FA0"


def lc_metamask_entries() -> dict[str, MeshSpec]:
    """mesh id -> spec for the two sides of the open locus coeruleus meta mask."""
    e: dict[str, MeshSpec] = {}
    for side, sfx in (("left", "-l"), ("right", "-r")):
        # NOT "locus-coeruleus-lc<side>": scripts/check-public.ts rejects any text containing an excluded
        # mesh id, and "locus-coeruleus-lc-l" has the private edition's "locus-coeruleus-l" inside it.
        mid = "locus-coeruleus-meta" + sfx
        e[mid] = MeshSpec(id=mid, name=f"Locus coeruleus ({'L' if side == 'left' else 'R'})", system="brainstem",
                          subsystem="pons", side=side, budget="tiny", colour=LC_METAMASK_COLOUR,
                          visible=False, structure_id="locus-coeruleus")
    return e
