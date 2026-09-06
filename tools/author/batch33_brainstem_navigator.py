"""Stage 5: the brainstem nuclei added by the Brainstem Navigator 7 T atlas (Bianciardi lab).

One entry per nucleus that the atlas did not already describe. The meshes are local-only
(licence BrainstemNavigator-NC-ND, nc + noRedistribution in the manifest), so every entry
carries a pitfall saying the outline is a 7 T probabilistic template, not a clinical boundary.
"""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).parent))
from corlib import *

E = []
BSN = ("SEVEN-TESLA TEMPLATE: the outline shown here is the group probability map of the Brainstem "
       "Navigator thresholded at 0.35, not a boundary you can trace on a clinical scan. At 3 T the "
       "nucleus is invisible, and in an individual brain its true edge may sit a millimeter or two "
       "outside the surface drawn.")
MID = ["artery-basilar", "artery-sca", "arteries-pontine"]
MED = ["artery-vertebral", "anterior-spinal-artery", "artery-pica"]
PONS = ["artery-basilar", "arteries-pontine", "artery-aica"]


def bsn(id, name, sub, summary, location, function, arteries, views, normal, paths, lesion, exam,
        pearls, cites, **kw):
    kw.setdefault("parent", "brainstem")
    kw.setdefault("territories", ["territory-basilar"])
    pit = list(kw.pop("pitfalls", ())) + [BSN]
    return cortex(id, name, "x", summary, location, function, arteries, views, normal, paths, lesion,
                  exam, pearls, cites, system="brainstem", subsystem=sub, pitfalls=pit, **kw)


# ================================================================= midbrain
E.append(bsn(
    "nucleus-cuneiform", "Cuneiform nucleus", "midbrain",
    "The cuneiform nucleus is a glutamatergic cell group in the dorsolateral tegmentum of the caudal "
    "midbrain, packed between the periaqueductal gray and the lateral lemniscus and sitting just above "
    "and behind the pedunculopontine nucleus. Together with that neighbor it forms the mesencephalic "
    "locomotor region, the small patch of midbrain whose stimulation makes an animal walk and whose "
    "firing rate sets how fast. Where the pedunculopontine nucleus is cholinergic and concerned with "
    "starting and permitting movement, the cuneiform nucleus is the speed and urgency control: it "
    "drives fast, goal-directed and escape locomotion through the medullary reticulospinal system, and "
    "it is coupled to the defensive circuitry of the periaqueductal gray. Interest in it is clinical as "
    "well as physiological, because freezing of gait and falls in Parkinson disease resist dopamine and "
    "the mesencephalic locomotor region has become a deep brain stimulation target for them.",
    "Caudal midbrain tegmentum at the level of the inferior colliculus, immediately lateral to the "
    "periaqueductal gray and dorsal to the pedunculopontine nucleus, with the lateral lemniscus and the "
    "brachium of the inferior colliculus on its lateral side and the decussation of the superior "
    "cerebellar peduncles below and in front. It extends caudally toward the isthmus, where it merges "
    "with the isthmic reticular formation, and rostrally it thins out beneath the inferior collicular "
    "plate. Its blood comes from perforators of the superior cerebellar and posterior cerebral arteries.",
    "The cuneiform nucleus converts a decision to move into a locomotor command. Glutamatergic neurons "
    "project caudally to the gigantocellular and magnocellular reticular formation of the pons and "
    "medulla, which in turn drive the spinal pattern generators through the medial reticulospinal "
    "tract; the strength of that drive grades locomotor speed and gait pattern rather than simply "
    "switching walking on. Inputs arrive from the motor and premotor cortex, from the internal pallidum "
    "and the substantia nigra pars reticulata, whose tonic inhibition rises in parkinsonism, from the "
    "subthalamic nucleus, and from the lateral hypothalamus and the periaqueductal gray, which is why "
    "the same region drives escape running and the freezing that precedes it. The nucleus also "
    "contributes to postural set and to the autonomic adjustments that accompany effort, raising heart "
    "rate and ventilation before the first step is taken. Because its output is glutamatergic and "
    "reticulospinal rather than dopaminergic, its dysfunction produces axial motor failure that "
    "levodopa cannot correct, and stimulating it in animals restores locomotion after nigral lesions.",
    MID,
    [mview("axial", "nucleus-cuneiform-l", "cuneiform nucleus lateral to the periaqueductal gray at the inferior collicular level"),
     mview("coronal", "nucleus-cuneiform-r", "dorsolateral tegmentum of the caudal midbrain")],
    "Not resolvable on clinical MRI: the region appears as undifferentiated tegmental gray lateral to "
    "the aqueduct on axial T2 at the level of the inferior colliculus. On 7 T images with heavy "
    "T2-weighting it can be separated from the pedunculopontine nucleus, and diffusion tractography is "
    "used to place stimulating electrodes.",
    [pathol("Freezing of gait in Parkinson disease", "MRI",
            "Structural MRI is normal or shows nonspecific midbrain atrophy; tractography of the "
            "mesencephalic locomotor region is used for electrode targeting and shows reduced "
            "connectivity with the medullary reticular formation.", sequence="T1"),
     pathol("Midbrain tegmental infarct", "MRI",
            "Restricted diffusion in the dorsolateral tegmentum with gait failure, postural instability "
            "and hypersomnolence out of proportion to limb weakness.", sequence="DWI"),
     pathol("Progressive supranuclear palsy", "MRI",
            "Midbrain atrophy with a concave superior profile; early falls reflect failure of the "
            "brainstem locomotor and postural systems rather than of the corticospinal tract.", sequence="T1")],
    [("Freezing of gait and slow, short-stepped walking", "bilateral", "Loss of glutamatergic drive to the pontomedullary reticulospinal system"),
     ("Postural instability with backward falls", "bilateral", "Failure of anticipatory postural adjustment"),
     ("Reduced escape and defensive responses", "bilateral", "Disconnection from the periaqueductal gray")],
    ["Watch gait initiation, turning and walking through a doorway, the classic freezing provocations",
     "Pull test for postural instability",
     "Ask whether levodopa helps the legs; axial failure that ignores the drug points below the striatum"],
    ["The mesencephalic locomotor region is two nuclei: the pedunculopontine permits walking, the cuneiform sets the pace",
     "Gait that does not respond to dopamine is a brainstem problem, not an underdosed one",
     "Escape running and freezing come from the same neighborhood, which is why fear changes gait"],
    [R("oa-bianciardi-mesopontine-tegmental-template"), R("sp-reticular-formation"), R("sp-gait-disturbances")],
    synonyms=["CnF", "nucleus cuneiformis", "mesencephalic locomotor region (with the pedunculopontine nucleus)"],
    pathways=["pathway-reticulospinal"], syndromes=["syn-parkinsonism"],
    afferents=[("Motor and premotor cortex", "corticotegmental fibers"),
               ("Substantia nigra pars reticulata and internal pallidum", "inhibitory nigrotegmental and pallidotegmental fibers"),
               ("Periaqueductal gray and lateral hypothalamus", "defensive and appetitive drive")],
    efferents=[("Gigantocellular reticular formation of the pons and medulla", "descending glutamatergic fibers"),
               ("Spinal locomotor networks", "medial reticulospinal tract"),
               ("Pedunculopontine nucleus and substantia nigra pars compacta", "local tegmental fibers")],
    tags=["locomotion", "gait", "deep brain stimulation"]))

E.append(bsn(
    "nucleus-microcellular-tegmental-parabigeminal", "Microcellular tegmental and parabigeminal nuclei", "midbrain",
    "The microcellular tegmental nucleus and the parabigeminal nucleus are two small, closely apposed "
    "cell groups at the lateral edge of the caudal midbrain tegmentum, drawn as one label because 7 T "
    "imaging cannot reliably separate them. The parabigeminal nucleus is the primate equivalent of the "
    "nucleus isthmi of lower vertebrates: a thin cholinergic shell lying against the lateral lemniscus "
    "that is reciprocally and topographically wired with the superior colliculus, and that sharpens "
    "which point in space the colliculus selects for the next orienting movement. The microcellular "
    "tegmental nucleus lies just medial to it and belongs to the isthmic reticular territory, "
    "contributing to arousal and to the premotor control of eye and head movements. Both are far too "
    "small to see clinically, but they matter for the physiology of covert attention and of "
    "collicular target selection.",
    "Lateral tegmentum of the caudal midbrain at and just below the level of the inferior colliculus, "
    "sandwiched between the lateral lemniscus laterally, the brachium of the inferior colliculus above "
    "and the cuneiform and pedunculopontine territory medially. The parabigeminal component hugs the "
    "outer surface of the lemniscus as a curved lamina; the microcellular tegmental component sits a "
    "little deeper and more medially, at the transition from midbrain to isthmus. Perforators from the "
    "superior cerebellar artery and the quadrigeminal branch of the posterior cerebral artery supply the region.",
    "The parabigeminal nucleus receives a dense topographic projection from the superficial layers of "
    "the superior colliculus and sends cholinergic fibers back to the same collicular point and, more "
    "weakly, to the opposite colliculus. That loop behaves as a winner-take-all circuit: it amplifies "
    "the collicular representation of the currently selected target and suppresses competing locations, "
    "so it is treated as a substrate of covert spatial attention and of stimulus salience. It also "
    "projects to the lateral geniculate nucleus and the pretectum, coupling attentional selection to "
    "the earliest stages of the visual pathway. The microcellular tegmental nucleus shares the "
    "connections of the surrounding isthmic reticular formation, projecting to the oculomotor and "
    "pontine gaze structures and receiving collicular and cortical eye-field input, so the pair sits at "
    "the junction of orienting, arousal and premotor gaze control. Their cholinergic output means that "
    "the same neuromodulator that supports cortical arousal is used locally to bias which part of the "
    "visual world is acted upon next.",
    MID,
    [mview("axial", "nucleus-microcellular-tegmental-parabigeminal-l", "parabigeminal lamina against the lateral lemniscus"),
     mview("coronal", "nucleus-microcellular-tegmental-parabigeminal-r", "lateral tegmentum below the inferior colliculus")],
    "Invisible on clinical MRI; the location corresponds to the lateral tegmental margin just inside "
    "the surface of the midbrain at the inferior collicular level, where the lateral lemniscus turns "
    "upward into its brachium.",
    [pathol("Dorsolateral midbrain infarct", "MRI",
            "Restricted diffusion in the lateral tegmentum with contralateral hearing change, ataxia "
            "and impaired orienting to visual targets.", sequence="DWI"),
     pathol("Tectal or pineal region tumor", "MRI",
            "Mass effect on the quadrigeminal plate and the adjacent lateral tegmentum with aqueductal "
            "obstruction and dorsal midbrain eye signs.", sequence="T1+Gd"),
     pathol("Progressive supranuclear palsy", "MRI",
            "Midbrain and tegmental atrophy accompanying slow vertical saccades and impaired visual "
            "search.", sequence="T1")],
    [("Impaired covert attention and slowed target selection", "contralateral", "Loss of the cholinergic collicular feedback loop"),
     ("Reduced orienting saccades to novel stimuli", "contralateral", "Weakened salience signal in the superior colliculus"),
     ("Reduced arousal to sensory events", "bilateral", "Loss of isthmic cholinergic tone")],
    ["Test visual search and extinction to double simultaneous stimulation",
     "Time reflexive saccades to a suddenly appearing target on each side",
     "Look for accompanying dorsal midbrain signs, since nothing here occurs in isolation"],
    ["The parabigeminal nucleus is the mammalian nucleus isthmi: a spotlight amplifier for the superior colliculus",
     "Attention has an anatomy in the midbrain, not only in the parietal cortex",
     "This label holds two nuclei because 7 T cannot yet separate them; treat it as a territory, not a border"],
    [R("oa-singh-mesencephalic-reticular-formation-atlas"), R("sp-mesencephalon-midbrain"), R("sp-acetylcholine")],
    synonyms=["MiTg", "PBG", "nucleus isthmi", "parabigeminal nucleus"],
    pathways=["pathway-visual", "pathway-tectospinal"], syndromes=["syn-parinaud-dorsal-midbrain"],
    afferents=[("Superficial superior colliculus", "topographic tectoparabigeminal fibers"),
               ("Frontal eye field and cortical eye fields", "corticotegmental fibers"),
               ("Lateral lemniscus territory and inferior colliculus", "local connections")],
    efferents=[("Superior colliculus of both sides", "cholinergic parabigeminotectal fibers"),
               ("Lateral geniculate nucleus and pretectum", "cholinergic fibers"),
               ("Pontine gaze centers", "isthmic premotor fibers")],
    tags=["attention", "cholinergic", "superior colliculus"]))

E.append(bsn(
    "raphe-linear-caudal-rostral", "Caudal-rostral linear raphe nucleus complex", "midbrain",
    "The caudal and rostral linear raphe nuclei form a slender midline column in the midbrain "
    "tegmentum, running from just behind the interpeduncular fossa up toward the posterior "
    "hypothalamus between the two red nuclei. They are the most rostral of the raphe nuclei and are "
    "unusual in being chemically mixed: serotonergic neurons of the B8 group are interleaved with "
    "dopaminergic neurons that belong to the same continuum as the ventral tegmental area, so the "
    "column contributes to both the serotonergic and the mesolimbic ascending systems. Its projections "
    "reach the ventral striatum, the amygdala, the septum and the interpeduncular nucleus, and it is of "
    "interest in reward, motivation and the sleep-wake control of REM. Like all the raphe nuclei it is "
    "invisible on clinical imaging and is known in living humans only from 7 T templates.",
    "Midline of the midbrain tegmentum between the medial longitudinal fasciculi and above the "
    "interpeduncular nucleus, extending from the level of the trochlear nucleus caudally to the "
    "posterior hypothalamic border rostrally, with the red nuclei on either side and the ventral "
    "tegmental area lying just ventrolateral. The caudal linear nucleus lies below and behind, the "
    "rostral linear nucleus above and in front, and the two are continuous. Thalamoperforating and "
    "posterior communicating perforators supply the column, which is why paramedian midbrain infarcts "
    "involve it together with the red nucleus and the oculomotor fascicles.",
    "The linear raphe complex sends serotonergic and dopaminergic fibers rostrally through the medial "
    "forebrain bundle to the nucleus accumbens, olfactory tubercle, amygdala, septum and prefrontal "
    "cortex, and it projects heavily to the interpeduncular nucleus, which links it to the habenular "
    "system that signals disappointment and aversive outcomes. Its dopaminergic neurons form part of "
    "the A10 group and are recruited by reward prediction and by novelty; its serotonergic neurons "
    "modulate the same targets with an opposing, patience-promoting influence, so the column is a place "
    "where two ascending modulatory systems are physically intermingled. Descending and local "
    "projections reach the dorsal raphe, the ventral tegmental area and the pontine reticular "
    "formation. Activity is highest in waking, falls in non-REM sleep and is lowest in REM, a pattern "
    "shared with the other serotonergic raphe nuclei and required for the orderly release of REM sleep. "
    "Because it is small and midline, both linear nuclei are usually damaged together or not at all.",
    ["arteries-thalamoperforating", "artery-pca", "artery-basilar"],
    [mview("sagittal", "raphe-linear-caudal-rostral", "midline linear raphe column above the interpeduncular fossa"),
     mview("axial", "raphe-linear-caudal-rostral", "paramedian midbrain tegmentum between the red nuclei")],
    "Not separable from the surrounding paramedian tegmentum on clinical MRI; the column occupies the "
    "midline strip between the red nuclei on axial images at the level of the oculomotor nucleus.",
    [pathol("Paramedian midbrain infarct", "MRI",
            "Restricted diffusion in the midline tegmentum, often bilateral from a single artery of "
            "Percheron, with hypersomnolence, vertical gaze palsy and apathy.", sequence="DWI"),
     pathol("Parkinson disease and related synucleinopathy", "PET",
            "Reduced serotonin transporter and dopamine transporter binding in the midbrain raphe and "
            "its forebrain targets, associated with apathy, depression and fatigue; MRI is normal.", sequence="n/a"),
     pathol("Wernicke encephalopathy", "MRI",
            "Periaqueductal and paramedian midbrain FLAIR hyperintensity extending into the midline "
            "tegmentum with confusion and ophthalmoplegia.", sequence="FLAIR")],
    [("Apathy and loss of motivation", "bilateral", "Loss of mixed serotonergic and dopaminergic drive to the ventral striatum"),
     ("Hypersomnolence", "bilateral", "Damage to the paramedian ascending arousal system"),
     ("Disturbed REM regulation", "bilateral", "Loss of the wake-active serotonergic tone that gates REM sleep")],
    ["Screen for apathy and anhedonia separately from depressed mood",
     "Assess daytime sleepiness and sleep-wake reversal",
     "Look for accompanying vertical gaze and third nerve signs that localize the paramedian midbrain"],
    ["The linear raphe is where the serotonergic and dopaminergic ascending systems physically overlap",
     "A paramedian midbrain infarct takes the raphe with the red nucleus, so apathy accompanies the tremor",
     "Midline nuclei are damaged bilaterally by single paramedian arteries"],
    [R("oa-singh-mesencephalic-reticular-formation-atlas"), R("sp-nucleus-raphe"), R("sp-mesencephalon-midbrain")],
    synonyms=["CLi", "RLi", "caudal linear nucleus", "rostral linear nucleus", "B8 group"],
    mesh_ids=["raphe-linear-caudal-rostral"],
    pathways=["pathway-papez-limbic"], syndromes=["syn-top-of-basilar", "syn-parkinsonism"],
    afferents=[("Lateral habenula", "fasciculus retroflexus"),
               ("Prefrontal cortex", "corticofugal fibers"),
               ("Hypothalamus and ventral tegmental area", "medial forebrain bundle")],
    efferents=[("Nucleus accumbens and olfactory tubercle", "medial forebrain bundle"),
               ("Interpeduncular nucleus", "raphe-interpeduncular fibers"),
               ("Amygdala, septum and prefrontal cortex", "ascending serotonergic and dopaminergic fibers")],
    tags=["serotonin", "dopamine", "reward", "raphe"]))

E.append(bsn(
    "reticular-formation-isthmic", "Isthmic reticular formation", "midbrain",
    "The isthmic reticular formation occupies the narrow waist between the midbrain and the pons, the "
    "isthmus rhombencephali, where the tegmentum is squeezed between the superior cerebellar peduncles "
    "as they turn medially to decussate. It is a transition zone rather than a nucleus with a sharp "
    "border: rostrally it becomes the mesencephalic reticular formation, caudally the oral pontine "
    "reticular nucleus, and embedded in it are the cholinergic pedunculopontine and laterodorsal "
    "tegmental cell groups. Functionally it is a critical link of the ascending arousal system, and its "
    "position explains why small lesions at the mesopontine junction produce coma out of proportion to "
    "their size. It also contributes premotor neurons to vertical gaze and to the startle response.",
    "Tegmentum of the isthmus, between the caudal border of the inferior colliculus above and the "
    "rostral pons below, bounded laterally by the superior cerebellar peduncle and the lateral "
    "lemniscus, dorsally by the periaqueductal gray as it becomes the central gray of the pons, and "
    "ventrally by the decussation of the superior cerebellar peduncles and the medial lemniscus. The "
    "trochlear nucleus and the anterior medullary velum lie at its dorsal margin. Blood supply is from "
    "the superior cerebellar artery and short circumferential branches of the upper basilar artery.",
    "The isthmic reticular formation is a relay of the ascending arousal system. Its glutamatergic and "
    "cholinergic neurons project rostrally to the intralaminar and reticular nuclei of the thalamus, to "
    "the basal forebrain and to the hypothalamus, keeping the thalamocortical system in the "
    "desynchronized state that permits waking consciousness; this is the narrowest part of that pathway, "
    "and it is here that bilateral tegmental damage abolishes arousal while the cortex remains intact. "
    "Descending projections join the pontine reticular formation and the reticulospinal system, "
    "contributing to postural tone, to the acoustic startle reflex and to autonomic adjustment. "
    "Locally the isthmus houses premotor neurons for vertical and torsional eye movements that "
    "communicate with the trochlear and oculomotor nuclei and with the rostral interstitial nucleus of "
    "the medial longitudinal fasciculus. It receives the prefrontal and cingulate cortex, the "
    "hypothalamus, the periaqueductal gray, the superior colliculus and the spinoreticular fibers that "
    "carry nociceptive information, so pain and threat can raise arousal directly.",
    MID,
    [mview("axial", "reticular-formation-isthmic-l", "isthmic tegmentum between the superior cerebellar peduncles"),
     mview("sagittal", "reticular-formation-isthmic-r", "waist between the midbrain and the pons")],
    "On sagittal T1 the isthmus is the narrowing between the midbrain and the bulging pons, behind the "
    "interpeduncular cistern and in front of the anterior medullary velum; the reticular formation "
    "itself is not distinguishable from surrounding tegmental gray at clinical field strength.",
    [pathol("Mesopontine tegmental infarct", "MRI",
            "Small paramedian tegmental infarct at the midbrain-pons junction causing coma or "
            "hypersomnolence with preserved brainstem reflexes early.", sequence="DWI"),
     pathol("Top of the basilar syndrome", "MRI",
            "Bilateral rostral brainstem and thalamic infarction with fluctuating consciousness, "
            "vertical gaze failure and visual hallucinations.", sequence="DWI"),
     pathol("Diffuse axonal injury of the brainstem", "MRI",
            "Petechial hemorrhage in the dorsolateral upper brainstem on susceptibility-weighted "
            "imaging in a comatose patient after high-energy trauma.", sequence="SWI")],
    [("Coma or hypersomnolence", "bilateral", "Interruption of the ascending arousal pathway at its narrowest point"),
     ("Vertical gaze disturbance", "bilateral", "Damage to isthmic premotor neurons connected with the trochlear and oculomotor nuclei"),
     ("Loss of startle and reduced postural tone", "bilateral", "Loss of descending reticulospinal drive")],
    ["Level of arousal graded against stimulus intensity, not a single Glasgow score",
     "Brainstem reflexes: pupils, corneal, oculocephalic and cold caloric responses",
     "Vertical saccades and the response to an optokinetic drum"],
    ["A lesion the size of a pea at the isthmus can abolish consciousness while the hemispheres are intact",
     "Coma with intact pupils and corneal reflexes points above the pons, coma without them below it",
     "The isthmus is a transition, so its label is a territory rather than a nucleus"],
    [R("oa-singh-mesencephalic-reticular-formation-atlas"), R("sp-reticular-activating-system"), R("sp-reticular-formation")],
    synonyms=["isRt", "isthmus rhombencephali reticular formation"],
    pathways=["pathway-reticulospinal", "pathway-vertical-gaze"],
    syndromes=["syn-top-of-basilar", "syn-basilar-occlusion", "syn-central-transtentorial-herniation"],
    afferents=[("Prefrontal and cingulate cortex", "corticoreticular fibers"),
               ("Spinal cord and trigeminal system", "spinoreticular and trigeminoreticular fibers"),
               ("Superior colliculus and periaqueductal gray", "tectoreticular and periaqueductal fibers")],
    efferents=[("Intralaminar and reticular thalamic nuclei", "ascending arousal projection"),
               ("Basal forebrain and hypothalamus", "ascending reticular fibers"),
               ("Pontomedullary reticular formation", "descending reticuloreticular fibers")],
    tags=["arousal", "coma", "reticular formation"]))

E.append(bsn(
    "reticular-formation-mesencephalic", "Mesencephalic reticular formation", "midbrain",
    "The mesencephalic reticular formation is the diffuse core of the midbrain tegmentum, lying between "
    "the periaqueductal gray behind, the red nucleus and substantia nigra in front and the medial "
    "lemniscus laterally. It is the rostral end of the ascending reticular activating system, the point "
    "at which brainstem arousal signals hand over to the thalamus, the hypothalamus and the basal "
    "forebrain, and lesions here cause coma more reliably than lesions anywhere else in the brainstem. "
    "Embedded within it are the premotor structures for vertical gaze, the interstitial nucleus of "
    "Cajal and the rostral interstitial nucleus of the medial longitudinal fasciculus, so the same "
    "region controls upward and downward saccades, ocular torsion and head-eye coordination. The 7 T "
    "atlas divides it into anterior, dorsal and lateral parts, which the atlas offers as hidden "
    "subdivisions of this structure.",
    "Central tegmentum of the midbrain from the level of the superior colliculus to the isthmus, "
    "bounded dorsally by the periaqueductal gray, ventrally by the red nucleus and the substantia "
    "nigra, medially by the midline raphe and the medial longitudinal fasciculus and laterally by the "
    "medial lemniscus and the spinothalamic tract. The oculomotor and trochlear nuclei and their "
    "fascicles run through it, as do the superior cerebellar peduncle fibers on their way to the red "
    "nucleus and thalamus. Perfusion comes from paramedian midbrain perforators of the basilar tip and "
    "posterior cerebral arteries and from short circumferential branches.",
    "This region is where arousal is generated and gaze is composed. Glutamatergic and cholinergic "
    "reticular neurons project to the intralaminar, midline and reticular nuclei of the thalamus and to "
    "the basal forebrain and posterior hypothalamus, and their tonic firing keeps the cortex "
    "desynchronized and responsive; the projection is bilateral, so unilateral damage rarely causes "
    "coma while bilateral paramedian damage does. Within the same territory the rostral interstitial "
    "nucleus of the medial longitudinal fasciculus generates vertical and torsional saccades and the "
    "interstitial nucleus of Cajal holds vertical gaze position and coordinates eye and head torsion "
    "through the posterior commissure, so lesions here produce upgaze or downgaze palsy, skew deviation "
    "and ocular tilt reactions. Descending fibers join the reticulospinal and tectospinal systems to "
    "orient the head, and reciprocal connections with the superior colliculus, the frontal eye field, "
    "the cerebellum and the periaqueductal gray tie orienting, arousal and defensive behavior together. "
    "Spinoreticular and trigeminoreticular afferents let pain wake the brain.",
    ["arteries-thalamoperforating", "artery-pca", "artery-basilar"],
    [mview("axial", "reticular-formation-mesencephalic-l", "tegmental core of the midbrain behind the red nucleus"),
     mview("sagittal", "reticular-formation-mesencephalic-r", "midbrain tegmentum from the superior colliculus to the isthmus")],
    "The midbrain tegmentum is uniform intermediate signal on T1 and T2, bounded by the darker "
    "substantia nigra and red nucleus in front and the aqueduct behind; the reticular formation cannot "
    "be resolved as a separate structure at clinical field strength.",
    [pathol("Bilateral paramedian midbrain infarct", "MRI",
            "Restricted diffusion in the paramedian tegmentum, often with medial thalamic infarction "
            "from an artery of Percheron, producing coma, vertical gaze palsy and amnesia.", sequence="DWI"),
     pathol("Central transtentorial herniation", "CT",
            "Downward displacement of the midbrain with effacement of the perimesencephalic cisterns "
            "and Duret hemorrhages; progressive loss of arousal with midposition fixed pupils.", sequence="CT non-contrast"),
     pathol("Wernicke encephalopathy", "MRI",
            "Symmetric FLAIR hyperintensity of the periaqueductal gray, medial thalami and mammillary "
            "bodies with confusion, ophthalmoplegia and ataxia.", sequence="FLAIR")],
    [("Coma", "bilateral", "Interruption of the bilateral ascending arousal projection to thalamus and basal forebrain"),
     ("Vertical gaze palsy and skew deviation", "bilateral", "Damage to the vertical saccade generator in the rostral interstitial nucleus of the medial longitudinal fasciculus, and to Cajal's interstitial nucleus"),
     ("Ocular tilt reaction with head tilt and torsion", "ipsilateral", "Loss of the graviceptive pathway through the interstitial nucleus of Cajal"),
     ("Akinetic mutism and abulia", "bilateral", "Loss of ascending drive to the thalamus and cingulate cortex")],
    ["Grade arousal by the stimulus needed to elicit a response and by what the eyes do",
     "Vertical saccades up and down, then the oculocephalic maneuver",
     "Look for skew deviation and ocular counter-roll, which localize to this tegmentum"],
    ["Coma is a midbrain and upper pontine sign until proved otherwise: the cortex needs both sides of this tegmentum",
     "Vertical gaze lives in the midbrain, horizontal gaze in the pons",
     "An artery of Percheron infarct gives coma, upgaze palsy and amnesia from one small vessel"],
    [R("oa-singh-mesencephalic-reticular-formation-atlas"), R("sp-reticular-activating-system"), R("sp-coma")],
    synonyms=["mRt", "midbrain reticular formation", "mesencephalic tegmental reticular field"],
    mesh_ids=["reticular-formation-mesencephalic-l", "reticular-formation-mesencephalic-r",
              "reticular-formation-mesencephalic-anterior-l", "reticular-formation-mesencephalic-anterior-r",
              "reticular-formation-mesencephalic-dorsal-l", "reticular-formation-mesencephalic-dorsal-r",
              "reticular-formation-mesencephalic-lateral-l", "reticular-formation-mesencephalic-lateral-r"],
    subdivisions=[("Anterior part (mRta)", "Ventral tegmental field next to the red nucleus, closely tied to the descending and oculomotor systems"),
                  ("Dorsal part (mRtd)", "Field beneath the periaqueductal gray holding the vertical gaze premotor neurons"),
                  ("Lateral part (mRtl)", "Field alongside the medial lemniscus receiving spinoreticular and collicular input")],
    pathways=["pathway-reticulospinal", "pathway-vertical-gaze", "pathway-tectospinal"],
    syndromes=["syn-top-of-basilar", "syn-parinaud-dorsal-midbrain", "syn-central-transtentorial-herniation", "syn-wernicke-korsakoff"],
    afferents=[("Prefrontal, cingulate and frontal eye field cortex", "corticoreticular fibers"),
               ("Spinal cord and trigeminal nuclei", "spinoreticular and trigeminoreticular fibers"),
               ("Superior colliculus, cerebellum and periaqueductal gray", "tectoreticular, cerebelloreticular and periaqueductal fibers")],
    efferents=[("Intralaminar, midline and reticular thalamic nuclei", "ascending arousal projection"),
               ("Basal forebrain and posterior hypothalamus", "ascending reticular fibers"),
               ("Oculomotor and trochlear nuclei", "vertical gaze premotor fibers"),
               ("Spinal cord", "reticulospinal and tectospinal tracts")],
    tags=["arousal", "coma", "vertical gaze", "reticular formation"]))

# ================================================================= pons
E.append(bsn(
    "nucleus-subcoeruleus", "Subcoeruleus nucleus", "pons",
    "The subcoeruleus nucleus is a small group of glutamatergic and noradrenergic neurons lying just "
    "ventral and lateral to the locus coeruleus in the dorsal tegmentum of the upper pons. In humans it "
    "corresponds to the sublaterodorsal nucleus of the rat, and it is the generator of the muscle "
    "atonia of REM sleep: its glutamatergic neurons fire during REM and excite inhibitory neurons of "
    "the ventromedial medulla and the spinal cord, which hyperpolarize motor neurons so that dreams are "
    "not acted out. Loss of these neurons produces REM sleep behavior disorder, in which patients "
    "punch, kick and shout during dreaming, and that disorder is the earliest reliable clinical marker "
    "of Parkinson disease, dementia with Lewy bodies and multiple system atrophy, often preceding the "
    "movement disorder by a decade or more.",
    "Dorsolateral tegmentum of the rostral pons immediately below and lateral to the locus coeruleus, "
    "in the angle between the superior cerebellar peduncle laterally, the medial longitudinal "
    "fasciculus medially and the floor of the fourth ventricle above. It merges caudally with the "
    "pontine reticular formation and rostrally with the laterodorsal tegmental territory. It lies in "
    "the territory of short circumferential branches of the basilar artery and of the superior "
    "cerebellar artery, and it is close enough to the locus coeruleus that the two are nearly always "
    "affected together.",
    "During REM sleep the subcoeruleus is one of the few brainstem regions that becomes more active "
    "rather than less. Its glutamatergic neurons project to glycinergic and GABAergic premotor neurons "
    "in the ventromedial medulla and directly to the spinal ventral horn, and the resulting postsynaptic "
    "inhibition of alpha motor neurons produces the near-complete skeletal atonia that defines REM. The "
    "same population is held in check during waking by GABAergic neurons of the ventrolateral "
    "periaqueductal gray and adjacent tegmentum, and it is released when those neurons fall silent at "
    "REM onset; the switch is reciprocal, so damage on either side of it produces either REM without "
    "atonia or a failure to enter REM at all. Ascending fibers reach the thalamus and basal forebrain "
    "and contribute to cortical activation, and noradrenergic neurons intermingled with the "
    "glutamatergic ones share the projections of the locus coeruleus. In the synucleinopathies the "
    "subcoeruleus degenerates early, at Braak stage 2, before the substantia nigra.",
    PONS,
    [mview("axial", "nucleus-subcoeruleus-l", "subcoeruleus below the locus coeruleus in the dorsal pontine tegmentum"),
     mview("coronal", "nucleus-subcoeruleus-r", "dorsolateral pontine tegmentum beneath the fourth ventricle")],
    "Not resolvable at 3 T. Neuromelanin-sensitive sequences show the locus coeruleus as a bright dot "
    "in the dorsal pons; the subcoeruleus lies immediately ventrolateral to it and reduced signal in "
    "that region has been reported in REM sleep behavior disorder.",
    [pathol("REM sleep behavior disorder", "MRI",
            "Conventional MRI is normal; neuromelanin imaging shows reduced locus coeruleus and "
            "subcoeruleus signal and diffusion imaging shows altered dorsal pontine connectivity.", sequence="T1"),
     pathol("Multiple system atrophy", "MRI",
            "Pontine atrophy with a hot cross bun sign and middle cerebellar peduncle T2 "
            "hyperintensity, with dream enactment often preceding the diagnosis.", sequence="T2"),
     pathol("Dorsal pontine infarct or demyelination", "MRI",
            "Tegmental lesion with internuclear ophthalmoplegia and loss of REM atonia on "
            "polysomnography.", sequence="FLAIR")],
    [("REM sleep without atonia and dream enactment", "bilateral", "Loss of glutamatergic drive to medullary and spinal inhibitory premotor neurons"),
     ("Excessive daytime sleepiness and disturbed sleep architecture", "bilateral", "Disruption of the REM switch"),
     ("Cataplexy-like episodes", "bilateral", "Inappropriate activation of the same atonia circuit during waking")],
    ["Ask the bed partner about kicking, punching and shouting during sleep, not the patient",
     "Screen for the other prodromal features of synucleinopathy: hyposmia, constipation, orthostatic symptoms",
     "Polysomnography with chin and limb electromyography to document REM without atonia"],
    ["Dream enactment is a brainstem sign that arrives years before the tremor",
     "The subcoeruleus paralyses you so you can dream safely; when it fails, dreams get out",
     "Neuromelanin imaging looks at the locus coeruleus, but the clinically important neighbor is just below it"],
    [R("oa-garcia-gomar-rbd-brainstem-connectivity"), R("sp-rem-sleep"), R("sp-rapid-eye-movement-sleep-behavior-disorder"), R("sp-norepinephrine")],
    synonyms=["SubC", "subcoeruleus", "sublaterodorsal nucleus", "peri-locus coeruleus alpha"],
    pathways=["pathway-reticulospinal"], syndromes=["syn-parkinsonism"],
    afferents=[("Ventrolateral periaqueductal gray and adjacent tegmentum", "GABAergic REM-off input"),
               ("Laterodorsal tegmental and pedunculopontine nuclei", "cholinergic fibers"),
               ("Lateral hypothalamus (orexin neurons)", "hypothalamotegmental fibers")],
    efferents=[("Ventromedial medullary reticular formation", "glutamatergic drive to glycinergic premotor neurons"),
               ("Spinal ventral horn", "descending atonia pathway"),
               ("Thalamus and basal forebrain", "ascending activating fibers")],
    tags=["REM sleep", "atonia", "synucleinopathy"]))

E.append(bsn(
    "nucleus-laterodorsal-tegmental", "Laterodorsal tegmental nucleus and central gray of the pons", "pons",
    "The laterodorsal tegmental nucleus is a cholinergic cell group in the central gray of the upper "
    "pons, lying in the floor of the fourth ventricle just medial to the locus coeruleus. With the "
    "pedunculopontine nucleus it makes up the Ch5-Ch6 cholinergic system of the brainstem, the source "
    "of acetylcholine for the thalamus, and it is one of the two engines of the ascending arousal "
    "system that switch the thalamocortical loop from burst firing to the tonic mode of waking and REM "
    "sleep. Its neurons are REM-on: they fire fastest during REM sleep and during waking and fall "
    "silent in non-REM sleep. The label used here also contains the surrounding central gray of the "
    "rhombencephalon, because 7 T imaging cannot separate the nucleus from the periventricular gray it "
    "sits in.",
    "Central gray of the rostral pons in the floor of the fourth ventricle, medial and slightly dorsal "
    "to the locus coeruleus, lateral to the medial longitudinal fasciculus and above the level of the "
    "abducens nucleus, extending rostrally into the isthmus where it becomes continuous with the "
    "periaqueductal gray and with the pedunculopontine territory. The superior cerebellar peduncle "
    "bounds it laterally. Blood supply is from the superior cerebellar artery and dorsal perforators of "
    "the basilar artery, and its periventricular position makes it vulnerable in thiamine deficiency.",
    "Cholinergic neurons of the laterodorsal tegmental nucleus project densely to the thalamus, "
    "including the intralaminar and reticular nuclei and the specific relay nuclei, and to the lateral "
    "hypothalamus, the basal forebrain, the ventral tegmental area and the medial prefrontal cortex. "
    "Acetylcholine released on thalamic neurons depolarizes them out of the burst firing that produces "
    "sleep spindles and slow waves and into the single-spike mode required for cortical arousal, so "
    "this nucleus is a switch between sleep and waking rather than a carrier of specific information. "
    "Its projection to the ventral tegmental area gates dopamine burst firing and therefore reward "
    "signaling, giving cholinergic brainstem control over motivation and drug reinforcement. During REM "
    "sleep the same neurons drive the pontine reticular formation to generate rapid eye movements and "
    "the cortical activation of dreaming, while the noradrenergic and serotonergic systems are silent. "
    "Afferents come from the prefrontal cortex, the lateral hypothalamus including the orexin neurons, "
    "the periaqueductal gray and the nucleus of the solitary tract, tying arousal to appetite, threat "
    "and visceral state.",
    PONS,
    [mview("axial", "nucleus-laterodorsal-tegmental-l", "laterodorsal tegmental nucleus in the central gray of the pons"),
     mview("sagittal", "nucleus-laterodorsal-tegmental-r", "periventricular gray of the upper pontine tegmentum")],
    "The central gray of the pons is a thin band of slightly higher T2 signal under the floor of the "
    "fourth ventricle; the nucleus itself is not separable on clinical images and is defined here by a "
    "7 T probabilistic template.",
    [pathol("Wernicke encephalopathy", "MRI",
            "Symmetric FLAIR hyperintensity of the periventricular gray around the fourth ventricle and "
            "aqueduct together with the medial thalami and mammillary bodies.", sequence="FLAIR"),
     pathol("Dementia with Lewy bodies and Parkinson disease dementia", "PET",
            "Reduced cortical and thalamic cholinergic markers with fluctuating attention and visual "
            "hallucinations; MRI is often unremarkable.", sequence="n/a"),
     pathol("Dorsal pontine infarct", "MRI",
            "Tegmental restricted diffusion with hypersomnolence, internuclear ophthalmoplegia and "
            "disturbed REM sleep.", sequence="DWI")],
    [("Hypersomnolence and reduced arousal", "bilateral", "Loss of cholinergic drive to the thalamus"),
     ("Fluctuating attention and visual hallucinations", "bilateral", "Cholinergic deafferentation of thalamus and cortex"),
     ("Disordered REM sleep", "bilateral", "Loss of REM-on cholinergic neurons")],
    ["Ask about fluctuating alertness across the day and well-formed visual hallucinations",
     "Sleep history including dream enactment and daytime sleepiness",
     "Test attention with serial tasks rather than orientation questions"],
    ["Acetylcholine from the pons is what lets the thalamus pass information to the cortex",
     "Fluctuating attention with hallucinations is a cholinergic pattern, and cholinesterase inhibitors help",
     "REM-on cholinergic neurons and REM-off monoaminergic neurons sit millimeters apart in the same tegmentum"],
    [R("oa-garcia-gomar-rbd-brainstem-connectivity"), R("sp-acetylcholine"), R("sp-reticular-activating-system")],
    synonyms=["LDTg", "CGPn", "Ch6 cholinergic group", "central gray of the rhombencephalon"],
    pathways=["pathway-reticulospinal"], syndromes=["syn-wernicke-korsakoff", "syn-parkinsonism"],
    afferents=[("Prefrontal cortex", "corticotegmental fibers"),
               ("Lateral hypothalamus (orexin neurons)", "hypothalamotegmental fibers"),
               ("Nucleus of the solitary tract and periaqueductal gray", "visceral and defensive input")],
    efferents=[("Thalamus (intralaminar, reticular and relay nuclei)", "ascending cholinergic projection"),
               ("Ventral tegmental area", "cholinergic gating of dopamine bursts"),
               ("Basal forebrain and lateral hypothalamus", "ascending cholinergic fibers"),
               ("Pontine reticular formation", "REM-generating fibers")],
    tags=["acetylcholine", "arousal", "REM sleep"]))

E.append(bsn(
    "nucleus-parabrachial-lateral", "Lateral parabrachial nucleus", "pons",
    "The lateral parabrachial nucleus wraps around the superior cerebellar peduncle in the dorsolateral "
    "tegmentum of the upper pons and is the brain's alarm relay for the body's internal state. Visceral "
    "and nociceptive signals that reach the nucleus of the solitary tract and the spinal dorsal horn are "
    "passed here, and the parabrachial neurons distribute them to the amygdala, the bed nucleus of the "
    "stria terminalis, the hypothalamus and the thalamus, generating the unpleasantness of pain, the "
    "aversiveness of nausea, air hunger, thirst and the arousal that follows a rise in carbon dioxide. "
    "Its calcitonin gene-related peptide neurons form a general alarm system that interrupts ongoing "
    "behavior and produces the affective, motivational side of a bodily threat rather than its sensory "
    "detail.",
    "Dorsolateral tegmentum of the rostral pons, forming a collar around the superior cerebellar "
    "peduncle lateral to the medial parabrachial nucleus and below the inferior colliculus, with the "
    "locus coeruleus medially and the mesencephalic trigeminal nucleus nearby. It extends from the "
    "isthmus down to the level of the motor trigeminal nucleus, and the Kölliker-Fuse nucleus lies at "
    "its ventrolateral edge. Superior cerebellar artery and long circumferential basilar branches "
    "supply it, so it is included in the dorsolateral pontine infarct that produces a superior "
    "cerebellar artery syndrome.",
    "The lateral parabrachial nucleus is the second-order station of the ascending interoceptive and "
    "nociceptive pathway. It receives the caudal, viscerosensory part of the nucleus of the solitary "
    "tract, lamina I of the spinal and trigeminal dorsal horns and the area postrema, and projects to "
    "the central nucleus of the amygdala, the bed nucleus of the stria terminalis, the paraventricular "
    "and lateral hypothalamus, the periaqueductal gray and the midline and ventromedial posterior "
    "thalamus. Distinct neuronal populations carry distinct messages: calcitonin gene-related peptide "
    "neurons signal threat and suppress feeding, other groups drive thirst, sodium appetite, "
    "thermoregulatory behavior and the arousal response to hypercapnia that wakes a sleeping person "
    "whose airway has obstructed. Because the same nucleus links visceral afference to the amygdala, "
    "it is the anatomical basis of conditioned taste aversion and of the fear that accompanies "
    "breathlessness. Descending projections modulate the respiratory rhythm generator and the "
    "autonomic outflow of the medulla, closing the loop between sensation and reflex control.",
    PONS,
    [mview("axial", "nucleus-parabrachial-lateral-l", "lateral parabrachial nucleus around the superior cerebellar peduncle"),
     mview("coronal", "nucleus-parabrachial-lateral-r", "dorsolateral pontine tegmentum")],
    "The superior cerebellar peduncle is visible as a paired white-matter bundle in the dorsolateral "
    "upper pons on axial T2; the parabrachial nuclei form the gray collar around it and are not "
    "individually resolvable at clinical field strength.",
    [pathol("Superior cerebellar artery territory infarct", "MRI",
            "Dorsolateral pontine and superior cerebellar restricted diffusion with ipsilateral ataxia, "
            "Horner syndrome, contralateral sensory loss and sometimes loss of taste and of arousal to "
            "dyspnea.", sequence="DWI"),
     pathol("Central hypoventilation and obstructive sleep apnea", "MRI",
            "Imaging is usually normal; failure of arousal to hypercapnia is a functional lesion of "
            "this pathway.", sequence="T2"),
     pathol("Pontine glioma or demyelination", "MRI",
            "Tegmental T2 hyperintensity involving the parabrachial region with intractable nausea, "
            "hiccups and altered taste.", sequence="FLAIR")],
    [("Loss of the affective dimension of pain", "contralateral", "Interruption of the spinoparabrachio-amygdaloid pathway"),
     ("Failure to arouse from sleep in response to hypercapnia", "bilateral", "Loss of the parabrachial chemosensory arousal projection"),
     ("Intractable nausea, altered taste and loss of appetite", "bilateral", "Interruption of the visceral relay from the solitary nucleus"),
     ("Disordered thirst and sodium appetite", "bilateral", "Loss of parabrachial hypothalamic projections")],
    ["Ask about the unpleasantness of pain separately from its intensity and location",
     "Sleep history: does the patient wake when the airway obstructs, or only in the morning with headache",
     "Taste testing on the anterior and posterior tongue, and a nausea and appetite history"],
    ["The lateral parabrachial nucleus makes pain unpleasant; the spinothalamic tract only says where it is",
     "Waking up when carbon dioxide rises is a parabrachial reflex, and losing it is dangerous",
     "Nausea, thirst, taste aversion and dyspnea share one pontine relay"],
    [R("oa-singh-parabrachial-vestibular-vsm-atlas"), R("sp-nucleus-solitarius"), R("sp-physiology-pain")],
    synonyms=["LPB", "lateral parabrachial area", "Kölliker-Fuse region (adjacent)"],
    pathways=["pathway-lateral-spinothalamic", "pathway-gustatory"],
    syndromes=["syn-sca-infarct", "syn-aica-lateral-pontine"],
    afferents=[("Nucleus of the solitary tract (caudal visceral part)", "solitarioparabrachial fibers"),
               ("Lamina I of the spinal and trigeminal dorsal horns", "spinoparabrachial and trigeminoparabrachial tracts"),
               ("Area postrema", "chemoreceptive fibers")],
    efferents=[("Central nucleus of the amygdala and bed nucleus of the stria terminalis", "parabrachio-amygdaloid fibers"),
               ("Paraventricular and lateral hypothalamus", "parabrachiohypothalamic fibers"),
               ("Midline and ventromedial posterior thalamus", "ascending interoceptive projection"),
               ("Medullary respiratory and autonomic nuclei", "descending fibers")],
    tags=["interoception", "pain affect", "arousal", "nausea"]))

E.append(bsn(
    "nucleus-parabrachial-medial", "Medial parabrachial nucleus", "pons",
    "The medial parabrachial nucleus lies against the medial face of the superior cerebellar peduncle, "
    "just inside its lateral partner, and is the pontine taste and respiratory relay. In primates the "
    "gustatory information that reaches the rostral nucleus of the solitary tract is passed mainly "
    "straight to the thalamus, but the medial parabrachial nucleus remains part of the visceral "
    "afferent chain and carries taste, gastric and cardiorespiratory signals toward the hypothalamus "
    "and the amygdala. Together with the neighboring Kölliker-Fuse nucleus it forms the classical "
    "pneumotaxic centre, the pontine group that limits the length of inspiration and smooths the "
    "switch from breathing in to breathing out; damage in this region produces apneustic breathing, a "
    "pattern of prolonged inspiratory gasps that localizes a lesion to the upper pons.",
    "Dorsolateral tegmentum of the rostral pons medial to the superior cerebellar peduncle and to the "
    "lateral parabrachial nucleus, below the inferior colliculus and lateral to the locus coeruleus, "
    "extending from the isthmus to the level of the motor trigeminal nucleus. The Kölliker-Fuse nucleus "
    "lies at its ventrolateral corner and the mesencephalic trigeminal tract runs nearby. It is "
    "supplied by the superior cerebellar artery and long circumferential branches of the basilar artery.",
    "The medial parabrachial nucleus receives the rostral, gustatory part of the nucleus of the "
    "solitary tract and the visceral afferents that report gastric distension, airway irritation and "
    "blood pressure, and projects to the ventral posteromedial thalamus, the lateral hypothalamus, the "
    "central amygdala and the insular cortex. Through these connections it contributes to the "
    "hedonic evaluation of food, to satiety and to conditioned taste aversion. Its respiratory role is "
    "exerted through dense reciprocal connections with the ventral respiratory column of the medulla "
    "and the pre-Bötzinger complex: parabrachial and Kölliker-Fuse neurons fire in phase with "
    "inspiration and terminate it, setting respiratory rate and the inspiratory to expiratory ratio, "
    "and they coordinate breathing with swallowing, vocalization and airway protection. Loss of this "
    "control with an intact medullary rhythm generator yields apneusis, while its ascending arm "
    "contributes to the sensation of dyspnea. The nucleus also receives descending input from the "
    "insula, the amygdala and the hypothalamus, which is how emotion changes the breathing pattern.",
    PONS,
    [mview("axial", "nucleus-parabrachial-medial-l", "medial parabrachial nucleus inside the superior cerebellar peduncle"),
     mview("coronal", "nucleus-parabrachial-medial-r", "upper pontine tegmentum at the pneumotaxic level")],
    "Not separable from the lateral parabrachial nucleus or from surrounding tegmental gray on clinical "
    "MRI; the landmark is the medial edge of the superior cerebellar peduncle on axial T2 in the upper pons.",
    [pathol("Upper pontine infarct or hemorrhage", "MRI",
            "Tegmental lesion with apneustic or cluster breathing, impaired taste and autonomic "
            "instability; breathing pattern is a bedside localizer.", sequence="DWI"),
     pathol("Central hypoventilation syndromes", "MRI",
            "Structural imaging is typically normal; the abnormality is functional in the pontomedullary "
            "respiratory network.", sequence="T2"),
     pathol("Brainstem encephalitis", "MRI",
            "Patchy FLAIR hyperintensity of the pontine tegmentum with respiratory irregularity, "
            "dysgeusia and cranial nerve signs.", sequence="FLAIR")],
    [("Apneustic breathing with prolonged inspiratory pauses", "bilateral", "Loss of the pontine inspiratory off-switch"),
     ("Loss or distortion of taste", "bilateral", "Interruption of the ascending gustatory relay"),
     ("Impaired coordination of breathing with swallowing", "bilateral", "Loss of parabrachial control over the ventral respiratory column")],
    ["Watch the breathing pattern for a full minute before touching the patient",
     "Test taste with sweet and salt solutions on each side of the tongue",
     "Observe a swallow and listen for a wet voice afterward"],
    ["Breathing pattern localizes: apneusis is upper pons, ataxic breathing is medulla, Cheyne-Stokes is hemispheric or diencephalic",
     "The pneumotaxic centre is a pair of parabrachial nuclei, not a single spot",
     "Taste and breathing share a relay because both report on what is entering the airway"],
    [R("oa-singh-parabrachial-vestibular-vsm-atlas"), R("sp-pons"), R("sp-nucleus-solitarius")],
    synonyms=["MPB", "medial parabrachial area", "pneumotaxic centre (with the Kölliker-Fuse nucleus)"],
    pathways=["pathway-gustatory"], syndromes=["syn-sca-infarct", "syn-locked-in"],
    afferents=[("Rostral (gustatory) nucleus of the solitary tract", "solitarioparabrachial fibers"),
               ("Insular and infralimbic cortex", "descending corticofugal fibers"),
               ("Amygdala and hypothalamus", "descending limbic fibers")],
    efferents=[("Ventral posteromedial thalamus and insular cortex", "ascending gustatory and visceral projection"),
               ("Ventral respiratory column and pre-Bötzinger complex", "descending respiratory fibers"),
               ("Lateral hypothalamus and central amygdala", "visceral limbic projection")],
    tags=["taste", "respiration", "apneusis"]))

E.append(bsn(
    "raphe-paramedian", "Paramedian raphe nucleus", "pons",
    "The paramedian raphe nucleus is a serotonergic group lying just off the midline of the pontine "
    "tegmentum, immediately lateral to the median raphe nucleus with which it is usually considered "
    "together as the B8 cell group. Its distinguishing feature is its output to the hippocampus and the "
    "septum: through the fornix and the cingulum it supplies the septohippocampal system with "
    "serotonin, and by doing so it desynchronizes the hippocampal theta rhythm. Where the median raphe "
    "suppresses theta, the paramedian group contributes to the same control, so this small nucleus is "
    "part of the machinery that decides whether the hippocampus is in an exploratory, theta-dominated "
    "state or a quiet one. It is also part of the ascending serotonergic system that regulates mood, "
    "anxiety and sleep.",
    "Paramedian pontine tegmentum immediately lateral to the midline raphe at the level of the rostral "
    "pons, between the median raphe nucleus medially and the pontine reticular nucleus laterally, "
    "ventral to the medial longitudinal fasciculus and dorsal to the pontine base. It extends from the "
    "isthmus down toward the level of the abducens nucleus. Paramedian perforating branches of the "
    "basilar artery supply it, so it is caught in the same paramedian pontine infarcts that produce "
    "pure motor hemiparesis from damage to the pontine base a few millimeters in front of it.",
    "The paramedian raphe sends serotonergic axons rostrally through the medial forebrain bundle to the "
    "medial septum, the hippocampus, the interpeduncular nucleus and the medial prefrontal cortex, and "
    "it receives the prefrontal cortex, the lateral habenula and the hypothalamus. Its hippocampal "
    "projection acts on the septohippocampal pacemaker: increased serotonergic tone suppresses the "
    "theta rhythm and shifts the hippocampus toward a desynchronized state, while a fall in tone allows "
    "theta to emerge during exploration and REM sleep. This gives the nucleus a role in the switching "
    "between encoding and consolidation states and, through the same targets, in anxiety and behavioral "
    "inhibition; drugs that raise synaptic serotonin change hippocampal rhythmicity through this route. "
    "Like the other serotonergic nuclei it is wake-active and REM-off, so its silence at REM onset "
    "helps permit the cholinergic activation of dreaming. Descending fibers reach the pontine and "
    "medullary reticular formation and modulate motor tone and pain transmission.",
    PONS,
    [mview("axial", "raphe-paramedian", "paramedian raphe beside the midline of the pontine tegmentum"),
     mview("sagittal", "raphe-paramedian", "paramedian pontine tegmentum above the base of the pons")],
    "Not visible on clinical MRI; the location is the paramedian tegmental strip on axial images at the "
    "level of the upper pons, just behind the transverse pontine fibers.",
    [pathol("Paramedian pontine infarct", "MRI",
            "Restricted diffusion in the paramedian pons, usually involving the base as well, with "
            "hemiparesis and often apathy or emotional change.", sequence="DWI"),
     pathol("Depression and anxiety in neurodegenerative disease", "PET",
            "Reduced serotonin transporter binding in the brainstem raphe and hippocampus; MRI normal.", sequence="n/a"),
     pathol("Osmotic demyelination", "MRI",
            "Central pontine T2 hyperintensity sparing the periphery, involving the paramedian "
            "tegmentum in severe cases.", sequence="T2")],
    [("Anxiety and behavioral inhibition", "bilateral", "Loss of serotonergic projection to the septohippocampal system and prefrontal cortex"),
     ("Altered hippocampal rhythmicity and memory encoding", "bilateral", "Loss of serotonergic control of theta"),
     ("Sleep fragmentation", "bilateral", "Loss of wake-active serotonergic tone")],
    ["Ask about anxiety and rumination as well as low mood",
     "Sleep history focused on fragmentation and early waking",
     "Look for paramedian pontine long-tract signs that would place a lesion here"],
    ["The paramedian raphe writes to the hippocampus and turns the theta rhythm down",
     "Serotonergic nuclei are wake-active and REM-off; their silence is what permits dreaming",
     "Midline pontine nuclei are supplied by paramedian perforators, so mood change can accompany a lacunar hemiparesis"],
    [R("oa-bianciardi-mesopontine-tegmental-template"), R("sp-nucleus-raphe"), R("sp-serotonin-2")],
    synonyms=["PMnR", "nucleus raphes paramedianus", "paramedian nucleus"],
    mesh_ids=["raphe-paramedian"],
    pathways=["pathway-papez-limbic"], syndromes=["syn-lacunar-pure-motor"],
    afferents=[("Prefrontal cortex", "corticofugal fibers"),
               ("Lateral habenula", "fasciculus retroflexus"),
               ("Hypothalamus and periaqueductal gray", "medial forebrain bundle and local fibers")],
    efferents=[("Medial septum and hippocampus", "ascending serotonergic fibers through the fornix and cingulum"),
               ("Interpeduncular nucleus and prefrontal cortex", "medial forebrain bundle"),
               ("Pontomedullary reticular formation", "descending serotonergic fibers")],
    tags=["serotonin", "theta rhythm", "raphe"]))

E.append(bsn(
    "reticular-formation-pontine", "Pontine reticular nucleus, oral and caudal parts", "pons",
    "The oral and caudal pontine reticular nuclei form the large medial reticular column of the pons, "
    "the region traditionally called the paramedian pontine reticular formation. It does four things "
    "that matter at the bedside: it generates horizontal saccades and drives the abducens nucleus for "
    "conjugate gaze to its own side, it is the obligatory relay of the acoustic startle reflex, it "
    "supplies the medial reticulospinal tract that sets axial and antigravity tone, and it is the "
    "effector arm of the REM atonia circuit. Because it also carries the ascending arousal projection "
    "through the upper pons, destructive lesions here produce coma, ipsilateral gaze palsy and, when "
    "the ventral pons is spared, the locked-in state.",
    "Medial tegmentum of the pons on both sides of the midline raphe, from the isthmus to the "
    "pontomedullary junction. The oral part occupies the rostral half around and above the level of the "
    "trigeminal motor nucleus; the caudal part lies below it, next to the abducens nucleus and the "
    "genu of the facial nerve. The medial longitudinal fasciculus and the tectospinal tract run along "
    "its medial edge, the medial lemniscus lies ventrally and the transverse pontine fibers and "
    "corticospinal tract are in front. Paramedian perforating branches of the basilar artery supply it, "
    "so its lesions accompany basilar branch occlusion and pontine hemorrhage.",
    "Excitatory burst neurons in the paramedian pontine reticular formation fire a high-frequency burst "
    "immediately before every ipsilateral horizontal saccade and drive the abducens nucleus, whose "
    "motor neurons move the ipsilateral lateral rectus while its interneurons cross in the medial "
    "longitudinal fasciculus to the contralateral medial rectus subnucleus; omnipause neurons in the "
    "midline raphe hold the bursters silent between saccades. A lesion therefore produces an "
    "ipsilateral conjugate gaze palsy that, unlike a frontal lesion, cannot be overcome by the "
    "oculocephalic maneuver. The caudal part contains giant reticular neurons that relay the acoustic "
    "startle response from the cochlear nuclei to the spinal cord within a few synapses and that give "
    "rise to the medial reticulospinal tract, which facilitates extensor and axial muscles; loss of "
    "this drive contributes to the decerebrate posture. During REM sleep the same region, driven by the "
    "subcoeruleus and the cholinergic tegmental nuclei, produces rapid eye movements and, through the "
    "ventromedial medulla, muscle atonia. Ascending collaterals contribute to the reticular activating "
    "system.",
    PONS,
    [mview("axial", "reticular-formation-pontine-l", "paramedian pontine reticular formation beside the midline"),
     mview("sagittal", "reticular-formation-pontine-r", "pontine tegmentum from the isthmus to the pontomedullary junction")],
    "The pontine tegmentum lies behind the transverse pontine fibers and in front of the fourth "
    "ventricle and is homogeneous on clinical T1 and T2; the reticular nuclei are defined by position "
    "rather than by signal.",
    [pathol("Paramedian pontine infarct", "MRI",
            "Restricted diffusion beside the midline with ipsilateral horizontal gaze palsy, "
            "contralateral hemiparesis and sometimes a one-and-a-half syndrome.", sequence="DWI"),
     pathol("Pontine hemorrhage", "CT",
            "Central pontine hematoma with coma, pinpoint reactive pupils, absent horizontal eye "
            "movements and extensor posturing.", sequence="CT non-contrast"),
     pathol("Basilar occlusion with locked-in syndrome", "MRI",
            "Bilateral ventral pontine infarction sparing the tegmentum, leaving the patient awake with "
            "only vertical eye movements and blinking.", sequence="DWI")],
    [("Ipsilateral conjugate horizontal gaze palsy", "ipsilateral", "Loss of excitatory burst neurons driving the abducens nucleus"),
     ("One-and-a-half syndrome when the medial longitudinal fasciculus is included", "ipsilateral", "Combined gaze palsy and internuclear ophthalmoplegia"),
     ("Loss of the startle reflex", "bilateral", "Interruption of the caudal pontine relay"),
     ("Coma and extensor posturing", "bilateral", "Loss of the ascending arousal projection and of reticulospinal tone control")],
    ["Horizontal saccades and pursuit to each side, then the oculocephalic maneuver: a pontine gaze palsy does not budge",
     "Cold caloric testing when the patient is unresponsive",
     "Startle to a sudden loud sound, and posture at rest and to pain"],
    ["The eyes look toward a pontine lesion's paralysed side and away from a hemispheric one",
     "A gaze palsy that the doll's eye maneuver overcomes is above the pons; one that it cannot is in it",
     "Pinpoint reactive pupils with absent horizontal gaze is a pontine hemorrhage until proved otherwise"],
    [R("oa-garcia-gomar-rbd-brainstem-connectivity"), R("sp-reticular-formation"), R("sp-pons")],
    synonyms=["PnO", "PnC", "paramedian pontine reticular formation", "PPRF", "pontine gaze centre"],
    pathways=["pathway-horizontal-gaze", "pathway-reticulospinal"],
    syndromes=["syn-horizontal-gaze-palsy-pontine", "syn-one-and-a-half", "syn-foville", "syn-pontine-hemorrhage", "syn-locked-in"],
    afferents=[("Frontal eye field and superior colliculus", "corticoreticular and tectoreticular fibers"),
               ("Cochlear nuclei", "startle pathway"),
               ("Cerebellar fastigial nucleus and vestibular nuclei", "fastigioreticular and vestibuloreticular fibers")],
    efferents=[("Abducens nucleus", "excitatory burst neuron projection for horizontal saccades"),
               ("Spinal cord", "medial reticulospinal tract"),
               ("Ventromedial medulla", "REM atonia pathway"),
               ("Thalamus", "ascending arousal collaterals")],
    tags=["horizontal gaze", "startle", "reticulospinal", "PPRF"]))

# ================================================================= medulla
E.append(bsn(
    "nuclei-viscero-sensory-motor", "Viscero-sensory-motor nuclei complex", "medulla",
    "The viscero-sensory-motor complex is the block of gray matter in the dorsal medulla that holds the "
    "visceral afferent and efferent machinery of the vagus and glossopharyngeal nerves together with "
    "the hypoglossal nucleus. It is drawn as a single label because 7 T imaging cannot separate the "
    "nucleus of the solitary tract, the dorsal motor nucleus of the vagus and the hypoglossal nucleus "
    "in a living brain, and because functionally they act as a unit: taste and visceral afferents "
    "arrive in the solitary nucleus, and the reflex responses leave through the adjacent "
    "parasympathetic and motor columns. This is the floor of the fourth ventricle at the level of the "
    "vagal trigone, and it is where blood pressure, heart rate, gastric secretion, swallowing, coughing "
    "and vomiting are put together.",
    "Dorsal medulla under the floor of the fourth ventricle and, more caudally, around the central "
    "canal, from the level of the striae medullares down to the obex and a little below it. The "
    "solitary tract and its nucleus lie laterally, the dorsal motor nucleus of the vagus makes the "
    "vagal trigone medial to it, and the hypoglossal nucleus forms the hypoglossal trigone next to the "
    "midline; the area postrema sits at the obex on the ventricular surface outside the blood-brain "
    "barrier. Posterior spinal and medial branches of the vertebral and posterior inferior cerebellar "
    "arteries supply the complex.",
    "Afferents from the vagus and glossopharyngeal nerves carrying taste, arterial baroreceptor and "
    "chemoreceptor signals, airway irritant information and gastrointestinal distension enter the "
    "solitary tract and end in a topographic order along the solitary nucleus, taste rostrally and "
    "cardiorespiratory and gastrointestinal input caudally. From there short axons reach the dorsal "
    "motor nucleus of the vagus, which supplies preganglionic parasympathetic fibers to the heart, "
    "airway and gut, and the nucleus ambiguus in the ventrolateral medulla, which drives the pharynx "
    "and larynx; ascending fibers travel to the parabrachial nuclei, the hypothalamus, the amygdala and "
    "the insular cortex. The hypoglossal nucleus, immediately medial, supplies the tongue and is "
    "recruited in swallowing, chewing and airway maintenance during sleep. The reflexes assembled here "
    "include the baroreflex, the chemoreflex, the cough and gag reflexes, the swallowing sequence and "
    "emesis, and the area postrema adds a chemosensitive trigger zone that samples the blood directly.",
    MED,
    [mview("axial", "nuclei-viscero-sensory-motor-l", "vagal and hypoglossal trigones in the floor of the fourth ventricle"),
     mview("sagittal", "nuclei-viscero-sensory-motor-r", "dorsal medulla from the striae medullares to the obex")],
    "The dorsal medulla is a narrow band of gray under the floor of the fourth ventricle on sagittal "
    "T2; the individual nuclei are not resolvable, but the region can be identified by the obex and the "
    "vagal and hypoglossal trigones on high-resolution imaging.",
    [pathol("Area postrema syndrome in neuromyelitis optica", "MRI",
            "Linear T2 hyperintensity of the dorsal medulla around the area postrema with intractable "
            "nausea, vomiting and hiccups.", sequence="T2"),
     pathol("Lateral medullary (Wallenberg) infarct", "MRI",
            "Dorsolateral medullary restricted diffusion involving the solitary nucleus and nucleus "
            "ambiguus with dysphagia, hoarseness, loss of taste and autonomic instability.", sequence="DWI"),
     pathol("Brainstem compression by a Chiari malformation or foramen magnum mass", "MRI",
            "Distortion of the dorsal medulla with sleep apnea, syncope and swallowing failure.", sequence="T2")],
    [("Dysphagia with nasal regurgitation and a wet voice", "bilateral", "Loss of the solitary-ambiguus swallowing circuit"),
     ("Intractable nausea, vomiting and hiccups", "bilateral", "Involvement of the area postrema and caudal solitary nucleus"),
     ("Labile blood pressure and syncope", "bilateral", "Interruption of the baroreflex arc"),
     ("Tongue weakness with deviation to the weak side", "ipsilateral", "Damage to the hypoglossal nucleus")],
    ["Watch a swallow of water, listen for a wet voice and test the gag and cough",
     "Lying and standing blood pressure and heart rate variability",
     "Inspect the tongue at rest for wasting and fasciculation, then ask for protrusion"],
    ["Intractable hiccups and vomiting with a normal abdomen should send you to the dorsal medulla and to aquaporin-4 antibodies",
     "Taste, blood pressure, cough and vomiting all report to one nucleus a few millimeters long",
     "The area postrema has no blood-brain barrier, which is why circulating emetics act there"],
    [R("oa-singh-parabrachial-vestibular-vsm-atlas"), R("sp-nucleus-solitarius"), R("sp-nucleus-ambiguus")],
    synonyms=["VSM", "viscero-sensory-motor complex", "solitary, dorsal vagal and hypoglossal nuclear complex"],
    subdivisions=[("Nucleus of the solitary tract", "Visceral and gustatory afferent column, topographically ordered from taste rostrally to gut caudally"),
                  ("Dorsal motor nucleus of the vagus", "Preganglionic parasympathetic column for heart, airway and gut"),
                  ("Hypoglossal nucleus", "Motor column for the tongue, adjacent to the midline")],
    pathways=["pathway-gustatory"],
    syndromes=["syn-wallenberg-lateral-medullary", "syn-vagal-palsy", "syn-hypoglossal-palsy", "syn-bulbar-vs-pseudobulbar"],
    afferents=[("Vagus and glossopharyngeal nerves", "solitary tract"),
               ("Insular and infralimbic cortex", "descending visceral corticofugal fibers"),
               ("Area postrema", "chemosensitive fibers")],
    efferents=[("Heart, airway and gastrointestinal tract", "preganglionic vagal fibers"),
               ("Nucleus ambiguus and the pharyngeal and laryngeal muscles", "local medullary connections"),
               ("Parabrachial nuclei, hypothalamus, amygdala and insula", "ascending visceral projection"),
               ("Tongue muscles", "hypoglossal nerve")],
    tags=["autonomic", "swallowing", "baroreflex", "vomiting"]))

E.append(bsn(
    "nucleus-parvicellular-reticular-alpha", "Parvicellular reticular nucleus, alpha part", "medulla",
    "The parvicellular reticular nucleus is the small-celled lateral part of the medullary reticular "
    "formation, and its alpha subdivision lies at the rostral end of that column just behind the "
    "trigeminal complex. It is the premotor organizer of the cranial motor nuclei: it receives "
    "trigeminal, gustatory and cortical input and distributes it to the trigeminal motor, facial, "
    "ambiguus and hypoglossal nuclei, coordinating the muscle sequences of chewing, licking, "
    "swallowing, facial expression and airway protection. It is the lateral, sensory-driven counterpart "
    "of the giant-celled medial column that projects to the spinal cord, and it is the reason a lesion "
    "in the lateral medulla can disorganize swallowing even when each individual motor nucleus is "
    "intact.",
    "Lateral medullary tegmentum at and just below the pontomedullary junction, dorsal to the inferior "
    "olivary nucleus, ventromedial to the spinal trigeminal nucleus and tract and lateral to the "
    "gigantocellular reticular nucleus, extending rostrally into the caudal pontine reticular "
    "territory. It lies within the field supplied by the posterior inferior cerebellar artery and by "
    "lateral perforating branches of the vertebral artery, which is why it is damaged in the lateral "
    "medullary syndrome.",
    "Parvicellular reticular neurons receive the spinal and principal trigeminal nuclei, the nucleus of "
    "the solitary tract, the cerebral cortex through corticoreticular fibers and the cerebellum, and "
    "project short axons to the motor nuclei of the trigeminal, facial, glossopharyngeal, vagus and "
    "hypoglossal nerves. They therefore act as pattern generators and premotor interneurons for "
    "orofacial behavior: the rhythmic jaw movements of chewing, the sequenced pharyngeal contraction of "
    "swallowing, the coordinated closure and expulsion of coughing and vomiting, and the reflex "
    "responses of the face to trigeminal stimulation such as the corneal blink and the jaw jerk "
    "modulation. Because the same neurons carry cortical commands to the bulbar motor nuclei, they form "
    "part of the corticobulbar route that produces pseudobulbar palsy when interrupted bilaterally "
    "above the medulla. The alpha subdivision is the part most closely tied to the trigeminal system "
    "and to chewing. Its output is bilateral for most muscles, which is why unilateral lesions "
    "typically cause incoordination rather than paralysis.",
    MED,
    [mview("axial", "nucleus-parvicellular-reticular-alpha-l", "parvicellular reticular field behind the inferior olive"),
     mview("coronal", "nucleus-parvicellular-reticular-alpha-r", "lateral medullary tegmentum below the pontomedullary junction")],
    "Not resolvable on clinical MRI; the region is the lateral tegmental strip between the spinal "
    "trigeminal nucleus and the medial reticular column on axial images of the upper medulla.",
    [pathol("Lateral medullary (Wallenberg) infarct", "MRI",
            "Wedge-shaped dorsolateral medullary restricted diffusion with severe dysphagia and "
            "dysarthria out of proportion to limb findings.", sequence="DWI"),
     pathol("Amyotrophic lateral sclerosis with bulbar onset", "MRI",
            "Imaging is normal or shows corticospinal T2 hyperintensity; tongue wasting, fasciculation "
            "and a brisk jaw jerk reflect combined bulbar and corticobulbar involvement.", sequence="FLAIR"),
     pathol("Brainstem encephalitis", "MRI",
            "Patchy tegmental FLAIR hyperintensity with disorganized swallowing and facial "
            "weakness.", sequence="FLAIR")],
    [("Dysphagia and dysarthria out of proportion to weakness", "bilateral", "Loss of premotor coordination of the bulbar motor nuclei"),
     ("Impaired chewing rhythm", "bilateral", "Loss of the trigeminal premotor pattern generator"),
     ("Weak or disorganized cough", "bilateral", "Loss of coordination between the laryngeal and respiratory motor pools")],
    ["Watch a swallow and time it; listen to speech for both slurring and nasality",
     "Test jaw opening and closing against resistance and observe chewing",
     "Assess cough strength and the ability to clear the throat on command"],
    ["Swallowing fails when the coordinator fails, even if every motor nucleus is intact",
     "The lateral reticular column organizes the face and pharynx; the medial column organizes the limbs and trunk",
     "Severe dysphagia with modest limb findings should raise the lateral medulla"],
    [R("oa-garcia-gomar-rbd-brainstem-connectivity"), R("sp-reticular-formation"), R("sp-medulla-oblongata")],
    synonyms=["PCRtA", "parvicellular reticular nucleus alpha part", "lateral reticular premotor field"],
    pathways=["pathway-corticobulbar", "pathway-reticulospinal"],
    syndromes=["syn-wallenberg-lateral-medullary", "syn-bulbar-vs-pseudobulbar", "syn-als-pattern"],
    afferents=[("Spinal and principal trigeminal nuclei", "trigeminoreticular fibers"),
               ("Cerebral cortex", "corticoreticular fibers of the corticobulbar system"),
               ("Nucleus of the solitary tract and cerebellum", "visceral and cerebellar input")],
    efferents=[("Trigeminal motor and facial nuclei", "premotor reticular fibers"),
               ("Nucleus ambiguus and hypoglossal nucleus", "premotor reticular fibers"),
               ("Adjacent medullary reticular formation", "local connections")],
    tags=["swallowing", "chewing", "premotor", "reticular formation"]))

E.append(bsn(
    "raphe-magnus", "Raphe magnus nucleus", "medulla",
    "The raphe magnus nucleus is the serotonergic midline nucleus of the rostral medulla and the "
    "output stage of the descending pain control system. Together with the surrounding gigantocellular "
    "and paragigantocellular cells it forms the rostral ventromedial medulla, the relay through which "
    "the periaqueductal gray suppresses or facilitates transmission in the spinal and trigeminal dorsal "
    "horns. Opioid analgesia, stimulation-produced analgesia and the analgesia of stress all work "
    "through this link, and the same neurons can facilitate rather than inhibit nociception, which is "
    "why the system is implicated in the maintenance of chronic pain and in opioid-induced "
    "hyperalgesia. It is a midline structure, so it is nearly always affected on both sides at once.",
    "Midline of the rostral medulla in front of the fourth ventricle floor and behind the pyramids, at "
    "and just below the pontomedullary junction, between the two medial lemnisci and above the raphe "
    "obscurus and pallidus. The nucleus ambiguus and the ventrolateral medulla lie laterally, and the "
    "gigantocellular reticular nucleus surrounds it. Median perforating branches of the vertebral and "
    "basilar arteries supply it, which links it to medial medullary rather than lateral medullary "
    "infarction.",
    "Serotonergic and enkephalinergic neurons of the raphe magnus project down the dorsolateral "
    "funiculus to laminae I, II and V of the spinal dorsal horn and to the spinal trigeminal nucleus, "
    "where they suppress the transmission of nociceptive signals from primary afferents to projection "
    "neurons. The pathway is driven by the periaqueductal gray, which itself is engaged by the "
    "hypothalamus, the amygdala and the anterior cingulate cortex, so attention, expectation and fear "
    "can change how much pain reaches consciousness; placebo analgesia and the relief produced by "
    "systemic opioids both require this descending arm. Two functional classes of neuron have been "
    "described, one that pauses just before a nocifensive reflex and facilitates pain and one that "
    "fires before it and inhibits, and a shift toward facilitation is thought to help maintain chronic "
    "and neuropathic pain states. The nucleus also modulates the trigeminovascular system in migraine "
    "and contributes serotonergic tone to motor neurons and to the respiratory network.",
    MED,
    [mview("axial", "raphe-magnus", "raphe magnus in the midline of the rostral medulla"),
     mview("sagittal", "raphe-magnus", "midline medullary raphe column")],
    "Not visible on clinical MRI; the midline of the rostral medulla in front of the fourth ventricle "
    "is the landmark, and functional imaging studies localize descending pain modulation to this region.",
    [pathol("Chronic pain and opioid-induced hyperalgesia", "MRI",
            "Structural imaging is normal; functional imaging shows altered engagement of the "
            "periaqueductal gray and rostral ventromedial medulla.", sequence="n/a"),
     pathol("Medial medullary infarct", "MRI",
            "Paramedian medullary restricted diffusion involving the midline raphe with contralateral "
            "hemiparesis, tongue weakness and altered pain modulation.", sequence="DWI"),
     pathol("Migraine", "MRI",
            "Interictal imaging is normal; brainstem activation in the raphe and periaqueductal region "
            "has been reported during attacks.", sequence="n/a")],
    [("Loss of descending pain inhibition with widespread hyperalgesia", "bilateral", "Interruption of the serotonergic projection to the dorsal horn"),
     ("Reduced opioid analgesia", "bilateral", "Loss of the periaqueductal-ventromedial medullary relay"),
     ("Altered respiratory chemosensitivity", "bilateral", "Loss of medullary serotonergic tone")],
    ["Ask whether pain is widespread and disproportionate to the injury",
     "Test conditioned pain modulation: does a distant painful stimulus reduce local pain",
     "Review opioid dose escalation with worsening pain, the signature of hyperalgesia"],
    ["Pain is not simply received; the medulla decides how much of it gets through",
     "Opioids work partly by recruiting this descending pathway, and the same pathway can turn pain up",
     "Midline nuclei are bilateral by definition, so their signs are never lateralized"],
    [R("oa-bianciardi-brainstem-nuclei-template"), R("sp-nucleus-raphe"), R("sp-physiology-pain")],
    synonyms=["RMg", "nucleus raphes magnus", "B3 group", "rostral ventromedial medulla"],
    mesh_ids=["raphe-magnus"],
    pathways=["pathway-lateral-spinothalamic", "pathway-trigeminothalamic"],
    syndromes=["syn-dejerine-medial-medullary", "syn-central-post-stroke-pain-syndrome"],
    afferents=[("Periaqueductal gray", "descending pain modulatory fibers"),
               ("Hypothalamus and amygdala", "descending limbic fibers"),
               ("Spinal dorsal horn", "spinoreticular feedback")],
    efferents=[("Spinal dorsal horn laminae I, II and V", "raphespinal fibers in the dorsolateral funiculus"),
               ("Spinal trigeminal nucleus", "descending serotonergic fibers"),
               ("Ventral horn motor neurons", "serotonergic modulation of excitability")],
    tags=["pain", "serotonin", "descending modulation", "raphe"]))

E.append(bsn(
    "raphe-obscurus", "Raphe obscurus nucleus", "medulla",
    "The raphe obscurus is a serotonergic midline nucleus of the caudal medulla, lying between the "
    "hypoglossal nuclei and the inferior olives and extending down toward the cervical cord. Its "
    "neurons are central chemoreceptors: they are directly sensitive to carbon dioxide and to the "
    "resulting fall in pH, and they excite the respiratory rhythm generator and the motor neurons of "
    "the airway and the diaphragm, so the nucleus is part of the system that keeps ventilation matched "
    "to metabolism and that arouses a sleeping person when carbon dioxide rises. It also supplies "
    "serotonin to the motor neurons of the ventral horn and the cranial motor nuclei, where it sets "
    "their background excitability. Abnormalities of medullary serotonergic nuclei including this one "
    "have been reported in the sudden infant death syndrome.",
    "Midline of the caudal medulla behind the inferior olivary nuclei and beneath the hypoglossal "
    "nuclei, from below the level of the raphe magnus to the cervicomedullary junction, continuous "
    "caudally with the midline raphe of the upper cervical cord. The medial lemnisci lie on either "
    "side and the pyramids in front. Median perforating branches of the vertebral and anterior spinal "
    "arteries supply it, so it shares its blood with the medial medullary territory.",
    "Raphe obscurus neurons sense carbon dioxide and pH directly, and their firing rate rises steeply "
    "with hypercapnia. They project to the ventral respiratory column including the pre-Bötzinger "
    "complex, to the phrenic and intercostal motor pools and to the hypoglossal nucleus, increasing "
    "respiratory drive and stiffening the upper airway; this last projection matters in obstructive "
    "sleep apnea, since serotonergic tone to the genioglossus falls during sleep and especially during "
    "REM. Ascending and local fibers reach the nucleus of the solitary tract and the ventrolateral "
    "medulla, coupling the chemoreflex to cardiovascular control, and descending fibers to the spinal "
    "ventral horn provide the serotonergic facilitation that allows motor neurons to sustain "
    "repetitive firing. The nucleus is also engaged in thermoregulation together with the raphe "
    "pallidus. Because it is wake-active and REM-off like the other serotonergic groups, its output "
    "falls exactly when the airway is most vulnerable.",
    MED,
    [mview("axial", "raphe-obscurus", "raphe obscurus in the midline of the caudal medulla"),
     mview("sagittal", "raphe-obscurus", "midline caudal medulla toward the cervicomedullary junction")],
    "Not visible on clinical MRI; the location is the midline of the caudal medulla behind the "
    "pyramids on sagittal images, near the cervicomedullary junction.",
    [pathol("Central hypoventilation and sleep-disordered breathing", "MRI",
            "Structural imaging is usually normal; the defect is functional in the medullary "
            "chemoreceptive network.", sequence="T2"),
     pathol("Medial medullary infarct", "MRI",
            "Paramedian medullary restricted diffusion with contralateral hemiparesis, tongue weakness "
            "and, when bilateral, respiratory failure.", sequence="DWI"),
     pathol("Foramen magnum compression", "MRI",
            "Cervicomedullary distortion by a Chiari malformation or mass with central apnea and "
            "impaired arousal from sleep.", sequence="T2")],
    [("Blunted ventilatory response to carbon dioxide", "bilateral", "Loss of medullary serotonergic chemoreception"),
     ("Sleep-disordered breathing with upper airway collapse", "bilateral", "Loss of serotonergic drive to the hypoglossal motor pool"),
     ("Reduced motor neuron excitability and fatigue", "bilateral", "Loss of descending serotonergic facilitation")],
    ["Ask about morning headache, witnessed apneas and daytime sleepiness",
     "Measure oxygen saturation and end-tidal carbon dioxide during sleep when suspicion is high",
     "Look for tongue and airway tone during sleep on polysomnography"],
    ["Breathing has a chemical thermostat in the midline of the medulla",
     "Serotonergic neurons are quiet in REM sleep, which is when obstructive apnea is worst",
     "Midline medullary serotonergic abnormalities have been described in sudden infant death syndrome"],
    [R("oa-bianciardi-brainstem-nuclei-template"), R("sp-nucleus-raphe"), R("sp-medulla-oblongata")],
    synonyms=["ROb", "nucleus raphes obscurus", "B2 group"],
    mesh_ids=["raphe-obscurus"],
    pathways=["pathway-reticulospinal"], syndromes=["syn-dejerine-medial-medullary"],
    afferents=[("Arterial and central chemoreceptor pathways", "solitary and local medullary fibers"),
               ("Hypothalamus and periaqueductal gray", "descending fibers"),
               ("Nucleus of the solitary tract", "visceral afferent relay")],
    efferents=[("Ventral respiratory column and pre-Bötzinger complex", "serotonergic fibers"),
               ("Hypoglossal nucleus and phrenic motor pool", "descending serotonergic drive"),
               ("Spinal ventral horn", "raphespinal facilitation")],
    tags=["chemoreception", "respiration", "serotonin", "raphe"]))

E.append(bsn(
    "raphe-pallidus", "Raphe pallidus nucleus", "medulla",
    "The raphe pallidus is the most ventral of the midline serotonergic nuclei, a thin sheet lying just "
    "behind the pyramids in the rostral and middle medulla. It is the sympathetic premotor nucleus for "
    "thermoregulation: neurons here receive the hypothalamic command for heat production and relay it "
    "to the sympathetic preganglionic neurons of the thoracic cord that drive brown adipose tissue, "
    "cutaneous vasoconstriction, shivering and the tachycardia of a febrile response. The pathway from "
    "the preoptic hypothalamus through the raphe pallidus is the final common route by which fever, "
    "cold defense and psychological stress raise body temperature, which is why it is invoked in "
    "explanations of stress-induced hyperthermia and of the autonomic storms seen after brain injury.",
    "Midline of the medulla immediately dorsal to the pyramids and ventral to the raphe magnus, from "
    "the pontomedullary junction down to the middle of the medulla, spreading a little laterally over "
    "the pyramidal surface. The inferior olivary nuclei lie dorsolaterally and the medial lemnisci "
    "behind. Its blood supply is from median perforators of the vertebral and anterior spinal arteries, "
    "the same vessels that serve the pyramids, so a medial medullary infarct can include it.",
    "Sympathetic premotor neurons of the raphe pallidus receive a disynaptic command from the median "
    "preoptic and dorsomedial hypothalamus that carries both the thermoregulatory set point and the "
    "prostaglandin-mediated signal of fever, and they project directly to the intermediolateral cell "
    "column of the thoracic spinal cord. Their firing raises sympathetic outflow to brown adipose "
    "tissue, producing non-shivering thermogenesis, constricts cutaneous vessels to conserve heat, "
    "recruits shivering through connections with somatic motor pathways and accelerates the heart. The "
    "same neurons are engaged by psychological stress, producing the rise in core temperature and heart "
    "rate that accompanies acute anxiety, and by inflammatory signals reaching the brain through "
    "prostaglandin E2. Serotonergic and glutamatergic subpopulations are intermingled, and the "
    "descending projection also modulates spinal nociception in parallel with the raphe magnus. "
    "Cooling the body, blocking prostaglandin synthesis or interrupting this pathway all reduce fever "
    "by acting at successive points along the same chain.",
    MED,
    [mview("axial", "raphe-pallidus", "raphe pallidus behind the pyramids in the midline medulla"),
     mview("sagittal", "raphe-pallidus", "ventral midline of the medulla")],
    "Not visible on clinical MRI; the landmark is the midline immediately behind the medullary pyramids "
    "on axial images of the rostral medulla.",
    [pathol("Paroxysmal sympathetic hyperactivity after brain injury", "MRI",
            "Diffuse axonal injury or hypoxic damage with episodic fever, tachycardia, hypertension, "
            "sweating and posturing; the medulla itself often looks normal.", sequence="SWI"),
     pathol("Medial medullary infarct", "MRI",
            "Paramedian restricted diffusion behind the pyramids with contralateral hemiparesis and "
            "sometimes disturbed thermoregulation.", sequence="DWI"),
     pathol("Central fever", "CT",
            "No infective source with a temperature that does not follow the usual diurnal pattern in a "
            "patient with brainstem or hypothalamic injury.", sequence="CT non-contrast")],
    [("Impaired thermoregulation with poikilothermia", "bilateral", "Loss of the descending sympathetic premotor drive to brown fat and skin vessels"),
     ("Absent shivering and cutaneous vasoconstriction in the cold", "bilateral", "Interruption of the hypothalamic-raphe-spinal pathway"),
     ("Episodic hyperthermia and tachycardia after brain injury", "bilateral", "Disinhibited sympathetic premotor activity")],
    ["Measure core temperature and compare it with the ambient temperature and the skin",
     "Look for sweating, skin color and shivering during a temperature change",
     "Record heart rate and blood pressure during episodes of fever without infection"],
    ["Fever is produced, not merely permitted: the hypothalamus commands and the raphe pallidus executes",
     "A febrile patient with no source and a brainstem injury may have central fever from this pathway",
     "Stress raises core temperature through the same neurons that raise it in infection"],
    [R("oa-bianciardi-brainstem-nuclei-template"), R("sp-nucleus-raphe"), R("sp-autonomic-nervous-system")],
    synonyms=["RPa", "nucleus raphes pallidus", "B1 group"],
    mesh_ids=["raphe-pallidus"],
    pathways=["pathway-oculosympathetic"], syndromes=["syn-dejerine-medial-medullary", "syn-hypothalamic-syndromes"],
    afferents=[("Median preoptic and dorsomedial hypothalamus", "descending thermoregulatory command"),
               ("Periaqueductal gray", "descending defensive fibers"),
               ("Nucleus of the solitary tract", "visceral afferent relay")],
    efferents=[("Intermediolateral cell column of the thoracic cord", "raphespinal sympathetic premotor fibers"),
               ("Spinal ventral horn", "shivering-related serotonergic drive"),
               ("Spinal dorsal horn", "descending nociceptive modulation")],
    tags=["thermoregulation", "fever", "sympathetic", "raphe"]))

E.append(bsn(
    "reticular-formation-medullary-inferior", "Inferior medullary reticular formation", "medulla",
    "The inferior medullary reticular formation is the caudal half of the medullary reticular core, the "
    "field that lies between the inferior olive in front and the dorsal nuclei behind and that runs "
    "down to become continuous with the reticular gray of the cervical cord. Its medial, large-celled "
    "part gives rise to the lateral reticulospinal tract, which inhibits extensor tone and shapes "
    "posture and locomotion, while its lateral, small-celled part organizes the bulbar motor nuclei. "
    "It also contains the ventromedial region through which REM sleep atonia is imposed on spinal motor "
    "neurons, and it holds the caudal parts of the respiratory and cardiovascular networks, so lesions "
    "here mix disorders of posture, breathing and blood pressure. The 7 T atlas separates a medial and "
    "a lateral part, offered here as hidden subdivisions.",
    "Central tegmentum of the caudal medulla from about the level of the obex down to the "
    "cervicomedullary junction, between the inferior olivary nucleus and pyramid in front and the "
    "hypoglossal, vagal and gracile and cuneate nuclei behind, with the spinal trigeminal complex "
    "laterally and the midline raphe medially. It is continuous rostrally with the superior medullary "
    "reticular formation and caudally with the intermediate gray of the upper cervical cord. Median and "
    "lateral perforating branches of the vertebral artery and the posterior inferior cerebellar artery "
    "supply it.",
    "The medial column of large cells here gives rise to the lateral reticulospinal tract, which "
    "descends in the lateral funiculus and inhibits extensor motor neurons and gamma motor neurons; "
    "with the medial reticulospinal tract from the pons it forms the pair of systems whose imbalance "
    "explains decerebrate and decorticate posturing and much of the spasticity that follows a "
    "hemispheric lesion, since the corticoreticular fibers that drive it run in the internal capsule "
    "and corona radiata. The ventromedial part receives the pontine subcoeruleus and contains the "
    "glycinergic and GABAergic premotor neurons that produce REM sleep atonia and, when abnormally "
    "recruited in waking, cataplexy. Lateral small-celled neurons coordinate the pharyngeal, laryngeal "
    "and tongue muscles for swallowing, coughing and vomiting. Ascending collaterals contribute to "
    "arousal, and spinoreticular afferents carrying diffuse nociceptive information terminate "
    "throughout, giving this region a role in the affective response to pain and in the reflex "
    "cardiovascular and respiratory answer to injury.",
    MED,
    [mview("axial", "reticular-formation-medullary-inferior-l", "reticular core of the caudal medulla behind the olive"),
     mview("sagittal", "reticular-formation-medullary-inferior-r", "medullary tegmentum from the obex to the cervicomedullary junction")],
    "The medullary tegmentum is homogeneous intermediate signal between the olives and the dorsal "
    "column nuclei on axial T2; the reticular formation is defined by position and is not separately "
    "visible at clinical field strength.",
    [pathol("Medullary infarct", "MRI",
            "Restricted diffusion in the medial or lateral medulla with a mixture of long-tract, "
            "cranial nerve and autonomic signs; small lesions are easily missed on early DWI.", sequence="DWI"),
     pathol("Cervicomedullary compression", "MRI",
            "Chiari malformation, foramen magnum meningioma or basilar invagination distorting the "
            "lower medulla with central apnea, syncope and quadriparesis.", sequence="T2"),
     pathol("Narcolepsy with cataplexy", "MRI",
            "Structural imaging is normal; the atonia circuit of the ventromedial medulla is "
            "inappropriately activated during waking.", sequence="T2")],
    [("Decerebrate posturing and altered tone", "bilateral", "Imbalance between medial and lateral reticulospinal drive"),
     ("Cataplexy and REM sleep atonia intruding into waking", "bilateral", "Inappropriate activation of ventromedial inhibitory premotor neurons"),
     ("Irregular ataxic breathing", "bilateral", "Damage to the caudal respiratory network"),
     ("Labile blood pressure", "bilateral", "Interruption of medullary cardiovascular control")],
    ["Posture at rest and to noxious stimulus, then tone in the limbs",
     "Breathing pattern watched over a full minute for irregularity",
     "Ask about knee-buckling with laughter or surprise when cataplexy is suspected"],
    ["Spasticity after a capsular stroke is largely a reticulospinal phenomenon, not a pyramidal one",
     "Ataxic, irregular breathing localizes to the medulla and warns of impending arrest",
     "The same medullary neurons that paralyse you in REM sleep produce cataplexy when they fire while you are awake"],
    [R("oa-garcia-gomar-rbd-brainstem-connectivity"), R("sp-reticular-formation"), R("sp-medulla-oblongata")],
    synonyms=["iMRt", "caudal medullary reticular formation", "ventromedial medulla"],
    mesh_ids=["reticular-formation-medullary-inferior-l", "reticular-formation-medullary-inferior-r",
              "reticular-formation-medullary-inferior-lateral-l", "reticular-formation-medullary-inferior-lateral-r",
              "reticular-formation-medullary-inferior-medial-l", "reticular-formation-medullary-inferior-medial-r"],
    subdivisions=[("Medial part (iMRtm)", "Large-celled column giving rise to the lateral reticulospinal tract and to the REM atonia pathway"),
                  ("Lateral part (iMRtl)", "Small-celled premotor field for the bulbar motor nuclei and the reflexes of the airway")],
    pathways=["pathway-reticulospinal", "pathway-lateral-corticospinal"],
    syndromes=["syn-wallenberg-lateral-medullary", "syn-dejerine-medial-medullary", "syn-tonsillar-herniation"],
    afferents=[("Cerebral cortex", "corticoreticular fibers"),
               ("Spinal cord", "spinoreticular fibers"),
               ("Subcoeruleus and pontine reticular formation", "descending REM atonia drive"),
               ("Cerebellar fastigial nucleus and vestibular nuclei", "fastigioreticular and vestibuloreticular fibers")],
    efferents=[("Spinal cord", "lateral reticulospinal tract"),
               ("Spinal motor neurons", "glycinergic and GABAergic atonia pathway"),
               ("Bulbar motor nuclei", "premotor reticular fibers"),
               ("Thalamus and basal forebrain", "ascending arousal collaterals")],
    tags=["reticulospinal", "posture", "atonia", "reticular formation"]))

E.append(bsn(
    "reticular-formation-medullary-superior", "Superior medullary reticular formation", "medulla",
    "The superior medullary reticular formation is the rostral half of the medullary reticular core, "
    "occupying the tegmentum from the pontomedullary junction down to about the level of the obex. It "
    "contains the gigantocellular nucleus and, in its ventrolateral corner, the rostral ventrolateral "
    "medulla, the cluster of sympathetic premotor neurons that sets resting arterial pressure. This is "
    "where the baroreflex is completed, where the respiratory rhythm is generated in the pre-Bötzinger "
    "complex a little more laterally, and where the descending pain modulatory pathway from the "
    "periaqueductal gray is relayed to the spinal cord alongside the raphe magnus. Its ascending "
    "projections contribute to arousal and its descending ones to postural tone, so a lesion here can "
    "produce coma, hemodynamic collapse and abnormal breathing at once. The 7 T atlas separates a "
    "medial and a lateral part.",
    "Tegmentum of the rostral medulla from the pontomedullary junction to about the obex, dorsal to the "
    "inferior olivary nucleus and the pyramid, ventral to the vagal and hypoglossal nuclear column, "
    "lateral to the midline raphe and medial to the spinal trigeminal complex. The nucleus ambiguus and "
    "the rostral ventrolateral medulla lie in its ventrolateral part. It is supplied by median and "
    "lateral perforators of the vertebral artery, by the anterior spinal artery and by the posterior "
    "inferior cerebellar artery, so both medial and lateral medullary syndromes encroach on it.",
    "Sympathetic premotor neurons of the rostral ventrolateral medulla project directly to the "
    "intermediolateral cell column and maintain the tonic vasoconstrictor drive that produces resting "
    "blood pressure; they are inhibited through the caudal ventrolateral medulla by baroreceptor "
    "signals arriving in the nucleus of the solitary tract, which is the whole of the baroreflex arc. "
    "Neighboring neurons of the ventral respiratory column generate the inspiratory rhythm and pattern "
    "it with the pontine parabrachial nuclei. Gigantocellular neurons give rise to reticulospinal "
    "fibers that modulate axial and limb tone and relay corticoreticular commands for posture and "
    "locomotion, and the same territory relays descending analgesia from the periaqueductal gray to "
    "the dorsal horn. Ascending fibers reach the thalamus, hypothalamus and basal forebrain and "
    "contribute to the reticular activating system, while spinoreticular and trigeminoreticular "
    "afferents make pain and visceral distress raise arousal, blood pressure and ventilation together. "
    "This convergence is why the rostral medulla is the most autonomically dangerous few cubic "
    "centimeters in the nervous system.",
    MED,
    [mview("axial", "reticular-formation-medullary-superior-l", "reticular core of the rostral medulla with the ventrolateral medulla"),
     mview("sagittal", "reticular-formation-medullary-superior-r", "medullary tegmentum from the pontomedullary junction to the obex")],
    "Homogeneous tegmental gray between the olive and the fourth ventricle floor on axial T2 of the "
    "upper medulla; the functional subregions are not separable at clinical field strength.",
    [pathol("Lateral medullary (Wallenberg) infarct", "MRI",
            "Dorsolateral restricted diffusion with dysphagia, Horner syndrome, crossed sensory loss "
            "and, when extensive, failure of automatic breathing.", sequence="DWI"),
     pathol("Medullary compression or herniation", "CT",
            "Tonsillar descent through the foramen magnum with bradycardia, hypertension and irregular "
            "breathing, the Cushing response.", sequence="CT non-contrast"),
     pathol("Baroreflex failure", "MRI",
            "Structural imaging may be normal after surgery or radiation to the neck; volatile "
            "hypertension with tachycardia reflects loss of the afferent arm of the same reflex.", sequence="T2")],
    [("Hypertension or hemodynamic collapse", "bilateral", "Damage to the sympathetic premotor neurons of the rostral ventrolateral medulla"),
     ("Loss of automatic breathing with preserved voluntary breathing", "bilateral", "Damage to the ventral respiratory column, Ondine's curse"),
     ("Coma", "bilateral", "Interruption of the ascending reticular projection"),
     ("Loss of descending pain inhibition", "bilateral", "Interruption of the relay from the periaqueductal gray to the dorsal horn")],
    ["Blood pressure and heart rate lying and standing, and their variability over time",
     "Watch breathing during sleep as well as awake; automatic breathing fails first",
     "Full brainstem reflex examination when consciousness is impaired"],
    ["Resting blood pressure is generated by a few thousand neurons in the ventrolateral medulla",
     "Ondine's curse is the loss of automatic breathing while voluntary breathing survives, and it kills during sleep",
     "The Cushing response of hypertension, bradycardia and irregular breathing means the medulla is being compressed"],
    [R("oa-garcia-gomar-rbd-brainstem-connectivity"), R("sp-reticular-formation"), R("sp-autonomic-nervous-system")],
    synonyms=["sMRt", "rostral medullary reticular formation", "gigantocellular reticular nucleus", "rostral ventrolateral medulla"],
    mesh_ids=["reticular-formation-medullary-superior-l", "reticular-formation-medullary-superior-r",
              "reticular-formation-medullary-superior-lateral-l", "reticular-formation-medullary-superior-lateral-r",
              "reticular-formation-medullary-superior-medial-l", "reticular-formation-medullary-superior-medial-r"],
    subdivisions=[("Medial part (sMRtm)", "Gigantocellular column giving rise to reticulospinal fibers and to ascending arousal collaterals"),
                  ("Lateral part (sMRtl)", "Ventrolateral field holding the sympathetic premotor neurons and the ventral respiratory column")],
    pathways=["pathway-reticulospinal", "pathway-oculosympathetic"],
    syndromes=["syn-wallenberg-lateral-medullary", "syn-tonsillar-herniation", "syn-basilar-occlusion"],
    afferents=[("Nucleus of the solitary tract", "baroreflex and chemoreflex input"),
               ("Cerebral cortex and hypothalamus", "corticoreticular and hypothalamoreticular fibers"),
               ("Periaqueductal gray", "descending pain modulatory fibers"),
               ("Spinal cord and trigeminal nuclei", "spinoreticular and trigeminoreticular fibers")],
    efferents=[("Intermediolateral cell column", "sympathetic premotor projection"),
               ("Phrenic and intercostal motor pools", "respiratory drive"),
               ("Spinal cord", "reticulospinal tract"),
               ("Thalamus, hypothalamus and basal forebrain", "ascending arousal projection")],
    tags=["blood pressure", "respiration", "arousal", "reticular formation"]))

write(E)
