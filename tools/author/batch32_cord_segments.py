"""Stage 4: the four spinal cord segment blocks and the lumbosacral trunk (meshes built by atlas-derived).

Every mesh named here is constructed rather than exported, so each entry carries a DERIVED pitfall saying so.
"""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).parent))
from lib import structure, img, view, pathol, write

R = lambda ref, section=None: ({"ref": ref, "section": section} if section else {"ref": ref})
CORD = [R("sp-spinal-cord"), R("sp-spinal-cord-morphology")]
DERIVED_CORD = (
    "DERIVED MESH: the four cord blocks are not measured on an individual. The Z-Anatomy cord surface was cut by "
    "horizontal planes placed at the classical cord-segment to vertebral-body relationship read off the Z-Anatomy "
    "vertebrae, so the block boundaries teach the rule rather than record a specimen; use them for orientation, "
    "never to read a level off an image."
)
E = []

# ------------------------------------------------------------------ cervical
E.append(structure(
    "spinal-segment-cervical", "Cervical spinal cord (C1-C8)", "spinal-cord",
    "The cervical cord runs from the decussation of the pyramids at the foramen magnum to the lower border of the "
    "seventh cervical vertebra, and it carries every long tract that serves the trunk and both pairs of limbs, which "
    "is why a single lesion here can be catastrophic. Its upper four segments are narrow and supply the neck, the "
    "diaphragm through the phrenic motor pool at C3, C4 and C5, and the trapezius and sternocleidomastoid through the "
    "spinal accessory nucleus that reaches down to C5 or C6. From C5 to T1 the cord swells into the cervical "
    "enlargement, whose large anterior horns hold the motor neurons of the arm and whose dorsal roots build the "
    "brachial plexus. A complete lesion above C4 abolishes spontaneous breathing; a complete lesion at C5 leaves a "
    "patient who can flex the elbow but cannot extend the wrist; at C6 wrist extension returns; at C7 the elbow "
    "extends and at C8 and T1 the small hand muscles are the last to go.",
    "From the level of the pyramidal decussation, where the medulla becomes the cord at the foramen magnum, down to "
    "the lower border of the C7 vertebral body, inside the widest part of the vertebral canal. The cord is oval in "
    "cross-section here, wider from side to side than from front to back, and reaches its greatest width in the "
    "cervical enlargement opposite the C5 and C6 vertebrae. The dentate ligaments anchor it to the dura on each side, "
    "and the vertebral arteries and the anterior spinal artery lie in front of it.",
    "The cervical cord supplies the neck, the diaphragm and the upper limbs and transmits everything below. Its "
    "anterior horns contain the motor pools for the neck, shoulder girdle, arm and hand, arranged so that proximal "
    "muscles lie medially and the intrinsic hand muscles most laterally, and the phrenic pool sits ventromedially at "
    "C3 to C5. Its posterior horns receive the dorsal roots that carry sensation from the back of the head, the neck "
    "and the whole upper limb. The lateral horn is absent above T1, so the sympathetic outflow to the head leaves "
    "through the T1 segment and travels back up the chain; a cervical cord lesion nonetheless interrupts the "
    "descending sympathetic pathway in the lateral funiculus and produces an ipsilateral Horner syndrome. The "
    "corticospinal, spinothalamic and dorsal column pathways are all fully assembled at this level, and their "
    "somatotopy, with sacral fibers lying most laterally in the corticospinal and spinothalamic tracts, explains why "
    "an expanding central lesion spares the sacral dermatomes until late.",
    ["anterior-spinal-artery", "posterior-spinal-arteries", "vertebral arteries", "ascending and deep cervical radicular arteries"],
    img([view("axial", 0, -48, -65, "cross-section of the upper cervical cord at the foramen magnum"),
         view("sagittal", 0, -48, -60, "cervicomedullary junction; the rest of the cervical cord lies below the MNI volume")],
        "On sagittal T2 the cervical cord is a smooth band of intermediate signal within bright CSF, widening between "
        "C4 and C6; on axial T2 the gray matter is a faint butterfly inside the paler white matter. The cord occupies "
        "well under half the canal in a normal adult.",
        [pathol("Cervical spondylotic myelopathy", "MRI",
                "Canal narrowing with cord flattening at one or more disc levels and a pancake of T2 hyperintensity in "
                "the central cord, often with gadolinium enhancement in severe compression.", sequence="T2"),
         pathol("Central cord syndrome", "MRI",
                "Hyperextension injury in a stenotic canal with central cord edema and weakness that is worse in the "
                "hands than the legs, often with preserved sacral sensation.", sequence="STIR"),
         pathol("Traumatic cervical cord injury", "CT",
                "Fracture or facet dislocation on CT with cord swelling and hemorrhage on MRI; the neurological level "
                "is set by the lowest segment with normal power and sensation.", sequence="CT non-contrast")],
        seq="Sagittal and axial T2 of the whole cervical cord, with STIR for cord edema and CT for the bony injury."),
    [("Tetraplegia with respiratory failure", "bilateral", "Complete lesion above C4 removing the phrenic motor pool and all descending motor tracts"),
     ("Weak hands with relatively strong legs", "bilateral", "Central cord injury damaging the medially placed arm fibers of the corticospinal tract first"),
     ("Ipsilateral Horner syndrome", "ipsilateral", "Interruption of the descending sympathetic fibers in the lateral funiculus above T1"),
     ("Loss of pain and temperature in a cape distribution", "bilateral", "Damage to the decussating spinothalamic fibers in the anterior white commissure, as in syringomyelia")],
    ["Test the diaphragm: ask about breathlessness lying flat and watch for paradoxical abdominal movement",
     "Work down the key myotomes C5 elbow flexion, C6 wrist extension, C7 elbow extension, C8 finger flexion, T1 finger abduction",
     "Check the biceps (C5-C6), brachioradialis (C6) and triceps (C7) reflexes and look for an inverted supinator sign",
     "Look for a Horner syndrome and for a sensory level on the trunk"],
    ["A lesion at or above C4 threatens the airway before it threatens the limbs",
     "Hand muscles weaker than legs after a fall in an older person is central cord syndrome until proved otherwise",
     "An inverted supinator jerk localizes to C5-C6 better than any sensory level"],
    CORD + [R("sp-spinal-cord-injuries"), R("sp-cervical-radiculopathy"), R("sp-thorax-phrenic-nerves"), R("sp-back-vertebral-column")],
    subsystem="segments", parent="spinal-cord", meshIds=["spinal-segment-cervical"],
    level={"region": "spinal", "sub": "cervical"},
    subdivisions=[("C1-C4 (high cervical)", "Neck, diaphragm through the phrenic pool at C3-C5, and the spinal accessory nucleus; a complete lesion here is ventilator dependent."),
                  ("C5-T1 (cervical enlargement)", "Large anterior horns for the upper limb; the dorsal roots here form the brachial plexus and the segment gives the classical arm myotomes.")],
    pathways=["tract-corticospinal", "tract-spinothalamic", "tract-dorsal-column-medial-lemniscus"],
    syndromes=["syn-central-cord", "syn-brown-sequard", "syn-syringomyelia"],
    pitfalls=[DERIVED_CORD,
              "The C8 segment lies opposite the C7 vertebra, so the vertebral level of an injury is not its cord level",
              "A cervical cord lesion can present as painless hand wasting and be mistaken for an ulnar neuropathy or motor neuron disease"],
    tags=["spinal cord", "segment", "derived"], synonyms=["cervical cord", "C1-C8 cord segments"]))

# ------------------------------------------------------------------ thoracic
E.append(structure(
    "spinal-segment-thoracic", "Thoracic spinal cord (T1-T12)", "spinal-cord",
    "The thoracic cord is the long, slender middle third of the cord, the part with the smallest cross-section, the "
    "poorest blood supply and the narrowest bony canal, which together make it the segment where compression and "
    "infarction do the most damage for the least warning. It has no limb enlargement, so its anterior horns are small "
    "and supply only the intercostal and abdominal muscles, but its lateral horn runs the entire sympathetic outflow "
    "of the body from T1 to L2, and the T1 segment supplies the sympathetic fibers of the head. Because the thoracic "
    "dermatomes wrap the trunk in neat bands, a lesion here declares itself as a sensory level: the nipple line is "
    "T4, the xiphisternum T6 and the umbilicus T10. A complete thoracic lesion gives spastic paraplegia with a sensory "
    "level and a neurogenic bladder, with normal arms.",
    "From the lower border of the C7 vertebral body to about the T9 or T10 vertebral body, so that the twelve thoracic "
    "cord segments are compressed into nine or ten vertebral levels and each segment lies two to three vertebrae above "
    "the bone of the same number. The canal is at its narrowest and the cord at its thinnest between T4 and T9, and the "
    "cord is held in the middle of the canal by the dentate ligaments with the thoracic aorta and its intercostal "
    "arteries in front of the vertebral bodies.",
    "The thoracic cord carries the whole motor and sensory traffic of the lower limbs and pelvis through, innervates "
    "the intercostal and abdominal muscles for breathing, coughing and posture, and houses the intermediolateral cell "
    "column, the preganglionic sympathetic neurons that reach every blood vessel, sweat gland, viscus and the adrenal "
    "medulla. Its dermatomes are the most reliable segmental map in the body, which is why a sensory level found on "
    "the trunk is the single most useful sign in acute myelopathy. The upper thoracic segments also carry the "
    "sympathetic supply of the heart, and T5 to T9 supply the splanchnic nerves; a lesion above T6 removes descending "
    "control of that outflow and allows autonomic dysreflexia, in which a distended bladder or bowel drives a "
    "dangerous surge of blood pressure with a reflex bradycardia and flushing above the lesion.",
    ["anterior-spinal-artery", "posterior-spinal-arteries", "segmental intercostal radicular arteries", "artery of Adamkiewicz"],
    img([view("axial", 0, -48, -70, "cord cross-section; the thoracic cord itself lies below the MNI volume"),
         view("sagittal", 0, -48, -65, "cervicomedullary junction, the rostral end of the cord shown in the volume")],
        "On sagittal T2 the thoracic cord is a uniform, slender band with no enlargement, narrowing further as it "
        "descends until it swells into the lumbar enlargement; the anterior median fissure and the posterior "
        "septum are not resolved at routine resolution.",
        [pathol("Thoracic cord compression by metastasis", "MRI",
                "Epidural soft tissue from a vertebral body deposit indenting the thecal sac with cord signal change; "
                "the sensory level on examination is usually a few segments below the true lesion.", sequence="T1+Gd"),
         pathol("Spinal cord infarction in the anterior spinal artery territory", "MRI",
                "Pencil-like or owl-eye T2 hyperintensity restricted to the anterior two-thirds of the cord with "
                "restricted diffusion, classically after aortic surgery or dissection.", sequence="DWI"),
         pathol("Transverse myelitis", "MRI",
                "Long central T2 hyperintensity over three or more segments with cord swelling and patchy enhancement, "
                "raising neuromyelitis optica and MOG antibody disease.", sequence="T2")],
        seq="Whole-spine sagittal T2 with axial images through the level, and contrast when a tumor or myelitis is suspected."),
    [("Spastic paraplegia with a sensory level on the trunk", "bilateral", "Interruption of the corticospinal and spinothalamic tracts at one thoracic segment"),
     ("Beevor sign, the umbilicus moving upward on flexing the neck", "bilateral", "Weak lower abdominal muscles (T10-T12) with intact upper ones, placing the lesion around T10"),
     ("Autonomic dysreflexia", "bilateral", "Loss of descending control over the sympathetic outflow below a lesion at or above T6"),
     ("Girdle pain radiating around the chest or abdomen", "ipsilateral", "Irritation of a thoracic dorsal root or of the dorsal root entry zone at the level of the lesion")],
    ["Find the sensory level with a pin, working upward from a numb area to normal skin",
     "Test the abdominal reflexes and look for Beevor sign",
     "Check for spasticity, extensor plantar responses and a neurogenic bladder",
     "Ask about vascular surgery, aortic dissection and back pain of sudden onset"],
    ["A sensory level on the trunk means the cord, not the brain, until imaging says otherwise",
     "Image above the clinical level: the sensory level often sits below the lesion",
     "Sudden painless paraplegia with preserved vibration and joint position sense is anterior spinal artery infarction"],
    CORD + [R("sp-spinal-cord-injuries"), R("sp-spinal-cord-arteries"), R("sp-back-vertebral-column")],
    subsystem="segments", parent="spinal-cord", meshIds=["spinal-segment-thoracic"],
    level={"region": "spinal", "sub": "thoracic"},
    subdivisions=[("T1-T6 (upper thoracic)", "Sympathetic supply to the head, neck and heart, and the upper intercostal muscles; a lesion at or above T6 permits autonomic dysreflexia."),
                  ("T7-T12 (lower thoracic)", "Lower intercostal and abdominal muscles, the splanchnic sympathetic outflow, and the T10 dermatome at the umbilicus.")],
    pathways=["tract-corticospinal", "tract-spinothalamic", "tract-dorsal-column-medial-lemniscus"],
    syndromes=["syn-anterior-spinal-artery", "syn-brown-sequard", "syn-transverse-myelitis"],
    pitfalls=[DERIVED_CORD,
              "Thoracic cord segments lie two to three vertebrae above the bone of the same number, so a T10 sensory level is not a T10 vertebral lesion",
              "The mid-thoracic cord is the watershed of the spinal circulation and infarcts there with little warning"],
    tags=["spinal cord", "segment", "derived"], synonyms=["thoracic cord", "T1-T12 cord segments"]))

# ------------------------------------------------------------------ lumbar
E.append(structure(
    "spinal-segment-lumbar", "Lumbar spinal cord (L1-L5)", "spinal-cord",
    "The five lumbar cord segments are packed into the vertebral canal opposite the T10, T11 and T12 vertebral bodies, "
    "far above the lumbar vertebrae they are named for, and together with the upper sacral segments they form the "
    "lumbosacral enlargement whose broad anterior horns supply the leg. The L1 and L2 segments carry the last of the "
    "sympathetic outflow and the cremasteric reflex, L2 to L4 supply the hip flexors, adductors and quadriceps and the "
    "knee jerk, and L4 and L5 supply ankle dorsiflexion, inversion and eversion. Their long roots have to travel far "
    "down the canal to reach their own foramina, so they run in the cauda equina beside the cord itself. A lesion "
    "confined to these segments, the epiconus syndrome, gives weak hips and knees with a preserved knee jerk pattern "
    "that shifts as the level rises, an absent ankle jerk, and less bladder involvement than a true conus lesion.",
    "In the vertebral canal opposite the T10, T11 and upper T12 vertebral bodies, immediately above the sacral "
    "segments and the conus medullaris. The cord is at its widest from side to side here, the lumbosacral enlargement, "
    "and it is surrounded by the descending roots of the cauda equina, which crowd the subarachnoid space so that a "
    "small mass at this level can compress both cord and roots at once. The great anterior radicular artery of "
    "Adamkiewicz usually enters between T9 and L2 and supplies this part of the cord.",
    "The lumbar cord provides the motor supply of the hip flexors, adductors, quadriceps and ankle dorsiflexors and "
    "receives sensation from the front of the thigh, the medial leg and the dorsum of the foot. Its anterior horns are "
    "large and somatotopically arranged, with the trunk muscles medial and the distal leg muscles lateral, and Clarke "
    "column at L1 and L2 is the origin of the posterior spinocerebellar tract carrying unconscious proprioception from "
    "the leg. The last preganglionic sympathetic neurons of the intermediolateral column lie at L1 and L2 and supply "
    "the pelvic vessels, and the L1 and L2 segments run the cremasteric reflex. Because these segments sit opposite "
    "the low thoracic vertebrae, a burst fracture of T12 damages lumbar cord and not lumbar roots, which is the "
    "commonest reason for the mismatch between the fracture level on a radiograph and the neurological level at the "
    "bedside.",
    ["anterior-spinal-artery", "artery of Adamkiewicz", "lumbar segmental radicular arteries"],
    img([view("axial", 0, -48, -70, "cord cross-section; the lumbar cord segments lie in the low thoracic canal, below the MNI volume"),
         view("sagittal", 0, -48, -65, "rostral cord shown in the volume; the lumbosacral enlargement is far caudal to it")],
        "On sagittal T2 the cord widens into the lumbosacral enlargement opposite the T10 to T12 vertebrae before "
        "tapering to the conus; below it the cauda equina roots hang as fine dark strands in bright CSF.",
        [pathol("Epiconus syndrome after a thoracolumbar fracture", "MRI",
                "Cord signal change opposite T11 or T12 with weak hip extensors and knee flexors, an absent ankle "
                "jerk and a preserved knee jerk, and relatively late bladder involvement.", sequence="T2"),
         pathol("Spinal dural arteriovenous fistula", "MRI",
                "Long T2 hyperintensity of the lower cord with dilated perimedullary flow voids on the dorsal surface, "
                "producing a slowly progressive paraparesis in an older man.", sequence="T2"),
         pathol("Intramedullary metastasis or ependymoma", "MRI",
                "Enhancing expansile lesion of the lumbosacral enlargement with surrounding edema and cord widening.", sequence="T1+Gd")],
        seq="Sagittal T2 of the thoracolumbar junction with axial images, and contrast for tumor or fistula."),
    [("Weak hip flexion and knee extension with a depressed knee jerk", "bilateral", "Loss of the L2-L4 anterior horn cells and of the afferent and efferent limbs of the knee jerk"),
     ("Foot drop with weak inversion and eversion", "bilateral", "Loss of the L4 and L5 anterior horn cells supplying tibialis anterior and the peroneal muscles"),
     ("Absent cremasteric reflex", "ipsilateral", "Interruption of the L1-L2 reflex arc"),
     ("Sensory loss over the front of the thigh and the medial leg", "bilateral", "Loss of the L2-L4 dorsal root entry zones")],
    ["Test hip flexion (L1-L2), knee extension (L3-L4), ankle dorsiflexion (L4-L5) and great toe extension (L5)",
     "Compare the knee jerk (L3-L4) with the ankle jerk (S1) to place the level",
     "Look for the cremasteric reflex in men and for a sensory level on the thigh",
     "Ask about back pain, trauma and progressive walking difficulty"],
    ["Weak legs with a preserved knee jerk and an absent ankle jerk points to the epiconus, not the cauda equina",
     "A T12 fracture injures lumbar cord segments; the vertebral number is not the neurological level",
     "The knee jerk and ankle jerk together separate an L3-L4 from an L5-S1 problem faster than any sensory map"],
    CORD + [R("sp-conus-medullaris"), R("sp-spinal-cord-arteries"), R("sp-back-lumbar-plexus")],
    subsystem="segments", parent="spinal-cord", meshIds=["spinal-segment-lumbar"],
    level={"region": "spinal", "sub": "lumbar"},
    subdivisions=[("L1-L2", "Last of the sympathetic outflow, the cremasteric reflex and Clarke column, the origin of the posterior spinocerebellar tract."),
                  ("L3-L5", "Quadriceps, adductors and ankle dorsiflexors; the knee jerk is L3-L4 and the L5 myotome extends the great toe.")],
    pathways=["tract-corticospinal", "tract-spinothalamic", "tract-spinocerebellar-posterior"],
    syndromes=["syn-conus-medullaris", "syn-cauda-equina", "syn-radiculopathy-lumbosacral"],
    pitfalls=[DERIVED_CORD,
              "The lumbar cord segments lie opposite the T10-T12 vertebrae, several levels above the lumbar vertebrae of the same name",
              "Weakness from lumbar cord segments is bilateral and symmetric; asymmetric weakness with radicular pain is more likely root disease"],
    tags=["spinal cord", "segment", "derived"], synonyms=["lumbar cord", "L1-L5 cord segments", "epiconus"]))

# ------------------------------------------------------------------ sacral and coccygeal
E.append(structure(
    "spinal-segment-sacral", "Sacral and coccygeal spinal cord (S1-S5, Co)", "spinal-cord",
    "The sacral and coccygeal segments make up the conus medullaris, the tapering tip of the cord that lies opposite "
    "the T12 and L1 vertebrae and ends at the L1-L2 disc in most adults. They are the smallest segments but they carry "
    "the reflex machinery of the pelvic floor: the parasympathetic nucleus at S2, S3 and S4 that empties the bladder "
    "and rectum and produces erection, Onuf nucleus that holds the motor neurons of the external urethral and anal "
    "sphincters, and the afferents of the saddle area. A lesion confined to the conus therefore produces early, "
    "symmetric retention with overflow incontinence, saddle anesthesia, impotence and absent anal and bulbocavernosus "
    "reflexes, with little or no leg weakness, and it is separated from a cauda equina lesion by being symmetric, less "
    "painful and less likely to abolish the ankle jerks on one side only.",
    "In the vertebral canal opposite the T12 and L1 vertebral bodies, forming the conus medullaris, which tapers to "
    "the filum terminale at about the L1-L2 intervertebral disc in the adult and one or two levels lower in the "
    "newborn. The conus lies surrounded by the roots of the cauda equina, which fill the lumbar theca below it, and it "
    "is supplied by a fine anastomotic basket rather than by a single feeding artery.",
    "The sacral cord supplies the small muscles of the foot and the pelvic floor, receives sensation from the back of "
    "the thigh, the sole and the perineum, and runs the autonomic control of the bladder, bowel and genitals. Its "
    "parasympathetic preganglionic neurons at S2 to S4 leave in the pelvic splanchnic nerves to contract the detrusor "
    "and relax the internal sphincter, while the somatic motor neurons of Onuf nucleus hold the external sphincters "
    "closed; the balance between them is what continence is. The S1 segment supplies the gastrocnemius and soleus and "
    "the ankle jerk, S2 to S4 the anal and bulbocavernosus reflexes, and the coccygeal segment a small patch of skin "
    "over the coccyx. Because the sacral fibers of the spinothalamic tract lie most laterally, an intramedullary "
    "lesion higher up spares sacral sensation until late, the sacral sparing that separates an intrinsic cord lesion "
    "from an extrinsic compression.",
    ["anterior-spinal-artery", "posterior-spinal-arteries", "lateral sacral and iliolumbar radicular arteries"],
    img([view("axial", 0, -48, -70, "cord cross-section; the conus lies at the thoracolumbar junction, below the MNI volume"),
         view("sagittal", 0, -48, -65, "rostral cord in the volume; the conus is at the L1-L2 disc far caudal to it")],
        "On sagittal T2 the conus tapers smoothly from the lumbosacral enlargement and ends at or above the L1-L2 "
        "disc; the filum terminale continues as a thin midline strand among the cauda equina roots.",
        [pathol("Conus medullaris syndrome", "MRI",
                "Focal lesion of the cord tip at T12-L1 with early symmetric urinary retention, saddle anesthesia and "
                "absent anal reflex; leg power is often preserved.", sequence="T2"),
         pathol("Tethered cord with a low conus", "MRI",
                "Conus ending below the L2 vertebral body with a thickened fatty filum, in a patient with back pain, "
                "urinary symptoms and a cutaneous stigma over the lower back.", sequence="T1"),
         pathol("Conus ependymoma or myxopapillary tumor", "MRI",
                "Enhancing mass of the conus and filum with hemorrhage at its margins and slowly progressive sphincter "
                "failure.", sequence="T1+Gd")],
        seq="Sagittal and axial T2 of the thoracolumbar junction with contrast when a tumor or tethering is suspected."),
    [("Early symmetric urinary retention with overflow incontinence", "bilateral", "Loss of the S2-S4 parasympathetic nucleus that drives the detrusor"),
     ("Saddle anesthesia", "bilateral", "Loss of the S3-S5 dorsal root entry zones serving the perineum"),
     ("Absent anal and bulbocavernosus reflexes", "bilateral", "Interruption of the S2-S4 reflex arcs through Onuf nucleus"),
     ("Absent ankle jerks with preserved knee jerks", "bilateral", "Loss of the S1 reflex arc while the L3-L4 arc above the lesion is spared"),
     ("Impotence", "bilateral", "Loss of the sacral parasympathetic outflow in the pelvic splanchnic nerves")],
    ["Test perianal pinprick and light touch in all four saddle quadrants",
     "Check anal tone, voluntary squeeze, the anal wink and the bulbocavernosus reflex",
     "Measure a post-void bladder scan in anyone with new back pain and leg symptoms",
     "Compare ankle jerks with knee jerks and look for asymmetry that would suggest the cauda equina instead"],
    ["New urinary retention with back pain is a conus or cauda equina emergency and needs imaging the same day",
     "Symmetric, painless and early sphincter failure is the conus; asymmetric, painful and radicular is the cauda equina",
     "Sacral sparing points to an intramedullary lesion, because the sacral fibers run most laterally in the spinothalamic tract"],
    CORD + [R("sp-conus-medullaris"), R("sp-cauda-equina-and-conus-medullaris-syndromes"), R("sp-back-cauda-equina")],
    subsystem="segments", parent="spinal-cord", meshIds=["spinal-segment-sacral"],
    level={"region": "spinal", "sub": "sacral"},
    subdivisions=[("S1-S2", "Plantar flexors and small muscles of the foot, the ankle jerk and sensation of the sole and the back of the thigh."),
                  ("S2-S4", "Pelvic parasympathetic nucleus, Onuf nucleus for the external sphincters, and the saddle dermatomes."),
                  ("S5 and coccygeal", "The last dermatome, a small patch of skin over the coccyx, and the origin of the filum terminale.")],
    pathways=["tract-corticospinal", "tract-spinothalamic"],
    syndromes=["syn-conus-medullaris", "syn-cauda-equina"],
    pitfalls=[DERIVED_CORD,
              "The conus sits at the T12-L1 vertebral level, so a lumbar puncture below L2 is safe in an adult but not in an infant, whose conus lies lower",
              "A normal ankle jerk does not exclude a conus lesion, because the sphincter segments can be hit alone"],
    tags=["spinal cord", "segment", "conus", "derived"], synonyms=["conus medullaris", "sacral cord", "S1-S5 cord segments"]))

# ------------------------------------------------------------------ lumbosacral trunk
E.append(structure(
    "lumbosacral-trunk", "Lumbosacral trunk", "peripheral",
    "The lumbosacral trunk is the thick cord of nerve fibers that carries the lower half of the L4 anterior ramus and "
    "the whole of L5 down over the ala of the sacrum to join the S1 ramus, and it is what makes the lumbar and sacral "
    "plexuses one continuous lumbosacral plexus. Its fibers travel on into the sciatic, superior gluteal and inferior "
    "gluteal nerves, so it carries the L4 and L5 supply of hip abduction, ankle dorsiflexion, foot inversion and "
    "great-toe extension. Because it lies directly on the bone at the pelvic brim with nothing between it and the fetal "
    "head, it is the nerve injured in maternal obstetric palsy, in which a long labor with a large baby leaves a woman "
    "with a unilateral foot drop and weak hip abduction after delivery; it is also compressed by pelvic tumors, by "
    "sacral fractures and by badly placed retractors during pelvic surgery.",
    "The trunk forms at the medial border of psoas major at about the level of the L4-L5 intervertebral disc, where "
    "the descending branch of the L4 ramus joins the whole L5 ramus. It then runs downward and backward over the ala "
    "of the sacrum, crossing the pelvic brim in front of the sacro-iliac joint, and enters the pelvis to meet the S1 "
    "ramus at the upper border of piriformis, where the sacral plexus is formed. It lies deep to the common iliac "
    "vessels and directly on the periosteum, covered only by the parietal pelvic fascia.",
    "The lumbosacral trunk is the conduit through which the L4 and L5 segments reach the sacral plexus, so it supplies "
    "no muscle itself but carries the fibers that will run in the superior gluteal nerve to gluteus medius, minimus "
    "and tensor fasciae latae, in the inferior gluteal nerve to gluteus maximus, and in the sciatic nerve to the "
    "hamstrings and, through the common peroneal division, to the dorsiflexors and evertors of the foot. Its sensory "
    "fibers reach the lateral leg and the dorsum of the foot. Damage to it therefore reproduces an L5 pattern that "
    "crosses the territory of more than one peripheral nerve: weak hip abduction, weak ankle dorsiflexion and eversion, "
    "weak great-toe extension and numbness over the lateral leg, with a preserved ankle jerk. The combination of hip "
    "abduction weakness with foot drop is what separates a lumbosacral trunk lesion from a common peroneal nerve palsy "
    "at the fibular neck, in which hip abduction is normal.",
    ["iliolumbar artery", "lateral sacral arteries", "vasa nervorum from the internal iliac artery"],
    img([view("axial", 0, -48, -70, "cord cross-section; the lumbosacral trunk lies on the pelvic brim, far below the MNI volume"),
         view("sagittal", 0, -48, -65, "rostral cord in the volume; the trunk crosses the ala of the sacrum well caudal to it")],
        "On coronal STIR of the lumbosacral plexus the trunk is a thin band of intermediate signal running over the "
        "sacral ala between the L5 root and the sacral plexus; it is best seen on thin-section three-dimensional "
        "neurography, and computed tomography shows only the bone it lies on.",
        [pathol("Maternal obstetric palsy", "MRI",
                "Increased T2 signal and swelling of the trunk where it crosses the sacral ala after a prolonged "
                "labor, with denervation edema in the tibialis anterior and gluteus medius.", sequence="STIR"),
         pathol("Pelvic tumor or nodal mass", "MRI",
                "Mass on the sacral ala encasing the trunk with progressive painful L5 weakness; contrast helps "
                "separate tumor from postradiation fibrosis.", sequence="T1+Gd"),
         pathol("Sacral or pelvic ring fracture", "CT",
                "Zone II or III sacral fracture crossing the ala with an L5 deficit; the fracture line and the "
                "displacement predict the nerve injury better than the neurological grade.", sequence="CT non-contrast")],
        seq="Coronal and axial STIR neurography of the lumbosacral plexus with contrast when a mass is suspected."),
    [("Foot drop with weak eversion and inversion", "ipsilateral", "Loss of the L4 and L5 fibers destined for the deep and superficial peroneal and tibial nerves"),
     ("Weak hip abduction with a Trendelenburg gait", "ipsilateral", "Loss of the L4-L5 fibers destined for the superior gluteal nerve"),
     ("Numbness of the lateral leg and dorsum of the foot", "ipsilateral", "Loss of the L5 sensory fibers"),
     ("Preserved ankle jerk", "ipsilateral", "The S1 reflex arc travels in the sacral rami and is spared when the trunk alone is injured")]  ,
    ["Test hip abduction as well as ankle dorsiflexion in every patient with a foot drop",
     "Look for a Trendelenburg sign and for wasting of gluteus medius",
     "Map sensation over the lateral leg and the first web space",
     "Ask about a difficult delivery, pelvic surgery, pelvic trauma and pelvic malignancy"],
    ["Foot drop plus weak hip abduction is the lumbosacral trunk or the L5 root, never the peroneal nerve at the knee",
     "Maternal obstetric palsy is nearly always unilateral, on the side of the fetal occiput, and usually recovers over months",
     "A preserved ankle jerk with an L5 pattern keeps the lesion above the sacral plexus"],
    [R("sp-back-lumbar-plexus"), R("sp-sciatic-nerve"), R("sp-back-vertebral-column")],
    subsystem="lower-limb", parent="plexus-lumbosacral",
    meshIds=["lumbosacral-trunk-l", "lumbosacral-trunk-r"],
    level={"region": "peripheral", "sub": "L4-L5"},
    syndromes=["syn-lumbosacral-plexopathy", "syn-radiculopathy-lumbosacral"],
    pitfalls=["DERIVED MESH: Z-Anatomy contains no lumbosacral trunk, so the shape shown is a schematic tube built "
              "along the classical course, from the L4 and L5 anterior rami at the medial border of psoas, over the "
              "ala of the sacrum, to the sacral plexus in front of piriformis; the waypoints were taken from the "
              "Z-Anatomy lumbosacral plexus, obturator, superior gluteal and sciatic nerve geometry and are recorded "
              "in pipeline/config/derived_nerves.yaml. Its caliber and exact path are illustrative, not measured.",
              "An L5 radiculopathy and a lumbosacral trunk lesion look identical at the bedside; the paraspinal "
              "muscles on needle electromyography separate them, because they are denervated only in the root lesion",
              "Do not call an isolated foot drop a peroneal palsy until hip abduction and inversion have been tested"],
    tags=["peripheral nerve", "plexus", "derived"], synonyms=["truncus lumbosacralis", "lumbosacral cord"],
    latin="truncus lumbosacralis"))

write(E)
