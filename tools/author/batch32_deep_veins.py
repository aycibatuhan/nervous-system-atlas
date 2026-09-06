"""Deep cerebral veins meshed from the VENAT 7 T venous atlas (internal cerebral vein, basal vein of
Rosenthal) plus the whole-atlas venous iso-surface. Open-access citations only (content/bibliography/)."""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).parent))
from corlib import *

E = []
R = lambda ref, section=None: ({"ref": ref, "section": section} if section else {"ref": ref})

BRAIN_VEINS = R("sp-brain-veins")
SINUSES = R("sp-dural-venous-sinuses")
CVT = R("sp-cerebral-venous-sinus-thrombosis")
MRV = R("mr-venography-normal-anatomy")
ICV_CTA = R("internal-cerebral-vein-cta")
GALEN = R("great-vein-of-galen-morphometry")
ROSENTHAL = R("basal-vein-rosenthal-drainage")
BASAL_CIRCLE = R("basal-venous-circle")
DEEP_CVT = R("deep-cerebral-venous-thrombosis")
POSTFOSSA = R("posterior-fossa-venous-drainage")

# ---------------------------------------------------------------- internal cerebral vein
E.append(structure(
    "vein-internal-cerebral", "Internal cerebral vein", "venous",
    "The internal cerebral vein is the paired collector of the deep white matter, the basal ganglia and the "
    "thalamus. It begins behind the foramen of Monro at the venous angle, where the anterior septal vein meets "
    "the thalamostriate vein, and runs backward for three to four centimeters as a straight paramedian channel "
    "in the roof of the third ventricle, inside the two layers of tela choroidea that form the velum "
    "interpositum. Under the splenium of the corpus callosum the two internal cerebral veins converge and join "
    "the two basal veins of Rosenthal to make the great cerebral vein of Galen. Because it lies within a "
    "millimeter or two of the midline and drains structures on both sides through the choroidal and "
    "subependymal veins, occlusion of one internal cerebral vein rarely stays unilateral: the classic result is "
    "bilateral thalamic swelling with a deep coma out of proportion to the size of the lesion.",
    "In the roof of the third ventricle, paired and paramedian, between about 2 and 6 mm from the midline, "
    "running from the foramen of Monro (roughly y = 0, z = +10 in MNI coordinates) posteriorly to the "
    "quadrigeminal cistern under the splenium (roughly y = -38). The vein lies in the velum interpositum "
    "between the fornix above and the roof of the third ventricle and the internal medullary lamina of the "
    "thalamus below; the medial posterior choroidal artery accompanies it, and the choroid plexus of the third "
    "ventricle hangs beneath it.",
    "The internal cerebral vein carries the deep venous return of the hemisphere: the anterior septal vein from "
    "the septum pellucidum and the anterior corpus callosum, the thalamostriate vein from the caudothalamic "
    "groove draining the caudate nucleus, the internal capsule and the deep periventricular white matter, the "
    "superior choroidal vein from the choroid plexus of the lateral ventricle, the direct lateral vein and the "
    "posterior thalamic (internal occipital) tributaries. Its territory is therefore the paraventricular white "
    "matter, the caudate, the internal capsule and most of the thalamus. Unlike the cortical veins, which have "
    "many surface anastomoses, the deep system is close to an end-drainage arrangement, so obstruction raises "
    "pressure quickly in a region with no collateral outlet. Flow is slow and pressure is low in health, which "
    "is why the vein is only faintly seen without contrast and why a thrombus in it produces venous congestion "
    "rather than immediate infarction: edema first, then petechial hemorrhage as the capillary bed fails.",
    ["artery-posterior-choroidal", "arteries-thalamoperforating", "medial posterior choroidal artery"],
    img([mview("axial", "vein-internal-cerebral-l", "paired internal cerebral veins in the roof of the third ventricle"),
         mview("sagittal", "vein-internal-cerebral-r", "internal cerebral vein under the body of the corpus callosum"),
         mview("coronal", "vein-internal-cerebral-l", "velum interpositum between the fornix and the thalamus")],
        "On MR venography the internal cerebral veins are two thin parallel lines that run straight back below "
        "the corpus callosum and meet the basal veins at the great cerebral vein; the venous angle behind the "
        "foramen of Monro is the landmark used to measure the position of the deep gray matter on an angiogram. "
        "On contrast-enhanced T1 and on CT venography they enhance uniformly; on susceptibility-weighted imaging "
        "they are dark because of deoxyhemoglobin, and asymmetry of that signal is a sensitive early sign of "
        "slowed deep venous flow.",
        [pathol("Deep cerebral venous thrombosis", "MRI",
                "Symmetric swelling and T2 or FLAIR hyperintensity of both thalami, sometimes the basal ganglia and the "
                "internal capsules, with loss of the normal flow void in the internal cerebral veins and an absent "
                "signal on MR venography; restricted diffusion is patchy rather than territorial.",
                sequence="FLAIR", timing="Symptoms evolve over hours to days, unlike an arterial stroke",
                pitfalls="Bilateral thalamic edema is also seen in top-of-the-basilar infarction, Wernicke encephalopathy, "
                         "acute necrotizing encephalopathy and deep glioma; the venous cause is settled by the venogram"),
         pathol("Straight sinus and deep vein thrombosis on unenhanced CT", "CT",
                "Hyperdense internal cerebral veins, great cerebral vein and straight sinus (the cord sign in the deep "
                "system) with hypodense thalami; a normal density in a dehydrated or polycythemic patient can mimic it.",
                sequence="CT non-contrast"),
         pathol("Venous congestion from a deep arteriovenous shunt", "DSA",
                "Early filling and dilatation of the internal cerebral vein during the arterial phase, with a "
                "vein of Galen malformation or a choroidal arteriovenous malformation as the shunt.",
                sequence="n/a"),
         pathol("Displacement by a mass", "MRI",
                "Elevation or lateral bowing of the internal cerebral vein by a pineal region tumor, a colloid cyst at "
                "the foramen of Monro or a thalamic glioma; the vein marks the plane a surgeon must not cross.",
                sequence="T1+Gd")],
        seq="Contrast-enhanced MR venography, with susceptibility-weighted imaging when deep venous thrombosis is suspected"),
    [("Depressed consciousness with bilateral thalamic edema", "bilateral",
      "Obstruction of the deep venous outflow congests both thalami through the paired internal cerebral veins"),
     ("Amnesia and abulia", "bilateral", "Congestion of the anterior and mediodorsal thalamic nuclei and the fornix"),
     ("Vertical gaze palsy", "bilateral", "Edema tracking to the posterior commissure and the rostral midbrain"),
     ("Hemorrhagic transformation of the basal ganglia", "n/a",
      "Sustained venous pressure ruptures the congested capillary bed")],
    ["Assess level of consciousness serially: deep venous thrombosis presents as an encephalopathy, not as a hemiparesis",
     "Test vertical gaze and pupillary light-near dissociation for rostral midbrain involvement",
     "Ask about the prothrombotic setting: puerperium, oral contraceptives, dehydration, malignancy, thrombophilia"],
    ["Two thin veins on either side of the midline under the corpus callosum: nothing else runs there",
     "Bilateral thalamic edema in a young patient means look at the deep veins before anything else",
     "The venous angle behind the foramen of Monro is the anterior end of the vein and a fixed angiographic landmark",
     "Anticoagulate deep venous thrombosis even when the imaging already shows hemorrhage"],
    [BRAIN_VEINS, ICV_CTA, MRV, DEEP_CVT, CVT],
    synonyms=["ICV", "vena interna cerebri", "deep paramedian vein"],
    latin="vena interna cerebri", subsystem="deep veins", parent="veins-deep-cerebral",
    meshIds=["vein-internal-cerebral-l", "vein-internal-cerebral-r"],
    afferents=[("Anterior septal vein", "venous angle"), ("Thalamostriate vein", "caudothalamic groove"),
               ("Superior choroidal vein", "choroid plexus of the lateral ventricle"),
               ("Direct lateral and posterior thalamic veins", "roof of the third ventricle")],
    efferents=[("Great cerebral vein of Galen", "under the splenium"), ("Straight sinus", "through the vein of Galen")],
    venous="Drains into the great cerebral vein of Galen and thence the straight sinus, the torcular and the transverse sinuses",
    syndromes=["syn-cerebral-venous-sinus-thrombosis"],
    pitfalls=["A hypoplastic or duplicated internal cerebral vein is a normal variant; asymmetry alone is not thrombosis",
              "The mesh is an iso-surface of a group-average susceptibility atlas, so it is smoother and a little "
              "thicker than the vein in any one person"],
    tags=["venous", "deep venous system", "thalamus", "VENAT"]))

# ---------------------------------------------------------------- basal vein of Rosenthal
E.append(structure(
    "vein-basal", "Basal vein (of Rosenthal)", "venous",
    "The basal vein of Rosenthal is the paired deep vein of the base of the brain. It forms under the anterior "
    "perforated substance where the deep middle cerebral vein from the insula meets the anterior cerebral and "
    "striate veins, then curves backward around the cerebral peduncle through the crural and ambient cisterns, "
    "climbs over the lateral surface of the midbrain beside the posterior cerebral artery and the trochlear "
    "nerve, and ends in the great cerebral vein of Galen behind the pineal gland. Its course makes it the venous "
    "equivalent of an arterial circle at the skull base, linking the sylvian, deep and posterior fossa drainage; "
    "for the surgeon it is the vein that must be preserved when working in the ambient cistern, and for the "
    "radiologist it is the channel whose congestion explains temporal and midbrain edema in deep venous "
    "thrombosis.",
    "From the anterior perforated substance below the anterior commissure (about x = 13, y = 2, z = -16 in MNI "
    "coordinates) backward and medially through the crural cistern between the uncus and the cerebral peduncle, "
    "then through the ambient cistern lateral to the midbrain and medial to the parahippocampal gyrus, and "
    "finally over the pulvinar into the quadrigeminal cistern, where it joins the internal cerebral vein and its "
    "fellow to form the great cerebral vein. It runs with the posterior cerebral artery, above the trochlear "
    "nerve and below the optic tract.",
    "The basal vein drains the medial temporal lobe including the hippocampus and the amygdala, the insula and "
    "the deep sylvian region through the deep middle cerebral vein, the anterior perforated substance and the "
    "striatum through the inferior striate veins, the hypothalamus, the midbrain and the choroid plexus of the "
    "temporal horn. Because it is assembled from three embryological segments (striate, peduncular and "
    "mesencephalic), it is one of the most variable veins in the skull: any of the three may be absent, and the "
    "vein may drain forward into the cavernous or sphenoparietal sinus, laterally into the superior petrosal "
    "sinus or backward into the transverse sinus rather than into the vein of Galen. That variability matters "
    "clinically, because a basal vein that empties into the vein of Galen makes the deep system the only outlet "
    "for the medial temporal lobe, whereas one that drains anteriorly gives it an escape route. In "
    "the ambient cistern the vein also forms the posterior half of the anastomotic venous ring around the "
    "midbrain that connects the two sides.",
    ["artery-pca", "artery-anterior-choroidal", "posterior communicating perforators"],
    img([mview("axial", "vein-basal-l", "basal vein in the ambient cistern beside the midbrain"),
         mview("coronal", "vein-basal-r", "basal vein below the optic tract and lateral to the peduncle"),
         mview("sagittal", "vein-basal-l", "curve from the anterior perforated substance to the vein of Galen")],
        "On MR and CT venography the basal vein is a smooth curve that hugs the midbrain, seen best on axial "
        "images at the level of the cerebral peduncles, and it is a normal finding for it to be visible on only "
        "one side. Its junction with the great cerebral vein sits just behind and above the pineal gland. On "
        "susceptibility-weighted imaging it is a dark line in the ambient cistern that should be symmetric with "
        "its fellow.",
        [pathol("Deep cerebral venous thrombosis involving the basal veins", "MRI",
                "Absent flow in one or both basal veins with swelling of the medial temporal lobe, the thalamus and the "
                "midbrain; the picture may be mistaken for herpes encephalitis when it is unilateral and temporal.",
                sequence="FLAIR",
                pitfalls="Non-visualization of a basal vein is common as a normal variant; call it thrombosis only with a "
                         "matching parenchymal abnormality or direct clot signal"),
         pathol("Venous drainage of a temporal arteriovenous malformation", "DSA",
                "Early arterial-phase filling of a dilated basal vein, which becomes the route of hemorrhage and the "
                "vessel that must be left until last at surgery.",
                sequence="n/a"),
         pathol("Displacement in uncal herniation", "CT",
                "The basal vein and the posterior cerebral artery are pushed medially across the ambient cistern by the "
                "herniating uncus, and the cistern is effaced.",
                sequence="CT non-contrast"),
         pathol("Vein of Galen malformation", "MRA",
                "Enlarged basal veins feeding a dilated median prosencephalic vein, with hydrocephalus and, in the "
                "neonate, high-output cardiac failure.",
                sequence="TOF")],
        seq="Contrast-enhanced MR venography in the axial plane through the midbrain"),
    [("Medial temporal and thalamic swelling with confusion or seizures", "ipsilateral",
      "Occlusion congests the hippocampus, amygdala and thalamus, which drain only through this vein"),
     ("Midbrain edema with a vertical gaze palsy", "bilateral",
      "The mesencephalic segment drains the tectum and the periaqueductal region"),
     ("Temporal lobe hemorrhage", "ipsilateral",
      "Sustained venous hypertension in a territory without a collateral outlet"),
     ("No deficit", "n/a",
      "An absent or hypoplastic segment is common and is compensated by the sphenoparietal or petrosal route")],
    ["Look for a temporal or thalamic abnormality that crosses arterial territory boundaries: that pattern is venous",
     "Check both basal veins on the venogram before calling one of them thrombosed",
     "In a neonate with heart failure and a big head, listen for a cranial bruit and image the deep veins"],
    ["Rosenthal's vein is the deep companion of the posterior cerebral artery around the midbrain",
     "Three embryological segments means three chances for a variant: absence of any one is normal",
     "A medial temporal lesion that does not fit the PCA territory should raise the basal vein as the culprit",
     "It forms the posterior part of the venous ring around the brainstem, so one side can drain the other"],
    [BRAIN_VEINS, ROSENTHAL, BASAL_CIRCLE, GALEN, MRV, DEEP_CVT],
    synonyms=["basal vein of Rosenthal", "vena basalis", "BVR"],
    latin="vena basalis", subsystem="deep veins", parent="veins-deep-cerebral",
    meshIds=["vein-basal-l", "vein-basal-r"],
    afferents=[("Deep middle cerebral vein", "insula and sylvian fissure"),
               ("Anterior cerebral and inferior striate veins", "anterior perforated substance"),
               ("Inferior ventricular and hippocampal veins", "temporal horn"),
               ("Peduncular and mesencephalic veins", "crural and ambient cisterns")],
    efferents=[("Great cerebral vein of Galen", "quadrigeminal cistern"),
               ("Superior petrosal, sphenoparietal or cavernous sinus", "variant routes")],
    venous="Normally into the great cerebral vein; variants drain forward to the cavernous or sphenoparietal sinus or laterally to the superior petrosal sinus",
    syndromes=["syn-cerebral-venous-sinus-thrombosis", "syn-uncal-herniation"],
    pitfalls=["The vein is often visible on one side only; asymmetry is not disease",
              "The mesh is cut from a group-average atlas and shows the peduncular and ambient segments; the "
              "anterior striate segment is too variable to appear reliably in the average"],
    tags=["venous", "deep venous system", "ambient cistern", "VENAT"]))

# ---------------------------------------------------------------- whole VENAT iso-surface
E.append(structure(
    "veins-venat-atlas", "Cerebral veins and sinuses (VENAT atlas iso-surface)", "venous",
    "This mesh is the intracranial venous tree extracted from a population atlas of the cerebral veins built "
    "from 7 T quantitative susceptibility maps: the iso-surface of the average venous partial-volume map, "
    "thresholded inside the brain, so that it shows the channels that are present in almost everyone. It "
    "contains the superior sagittal sinus along the attached margin of the falx, the transverse and sigmoid "
    "sinuses, the torcular, the straight sinus in the tentorium, the great cerebral vein, the paired internal "
    "cerebral veins in the roof of the third ventricle, the basal veins around the midbrain and the larger "
    "cortical and medullary veins. It is the venous counterpart of the arterial iso-surface in this atlas: "
    "it sits exactly on the template MRI, so the veins can be read against the slices without any registration "
    "error, and it shows what a normal venogram should contain.",
    "The whole intracranial venous compartment inside the template brain mask, from the vertex where the "
    "superior sagittal sinus begins to the torcular and the transverse and sigmoid sinuses at the skull base, "
    "including the deep veins in the roof of the third ventricle and the ambient cisterns.",
    "Read as an anatomical reference, the surface answers the questions a venogram raises: where a sinus should "
    "run, how the deep veins relate to the ventricles and the corpus callosum, and which cortical veins reach "
    "which sinus. Because it is an average of many people, its channels are smoother and slightly wider than "
    "any individual's, the small cortical veins that vary from person to person fall below the threshold and "
    "are missing, and normal variants such as a hypoplastic left transverse sinus are averaged away. That is "
    "exactly what makes it useful as a template: a vessel that is present here is present in almost everyone, "
    "so its absence on a patient's venogram is worth explaining, while a vessel missing here may still be normal "
    "in an individual. The venous tree also explains the two rules that separate venous from arterial disease: "
    "venous lesions cross arterial territory boundaries, and they are usually edematous before they are "
    "hemorrhagic.",
    ["Cerebral arteries feed the capillary bed drained by these veins", "artery-mca", "artery-pca"],
    img([mview("sagittal", "veins-venat-atlas", "midline sinuses, deep veins and the straight sinus"),
         mview("axial", "veins-venat-atlas", "transverse sinuses and the torcular"),
         mview("coronal", "veins-venat-atlas", "superior sagittal sinus and the deep venous system")],
        "On MR and CT venography the normal venous tree looks like this surface: a continuous superior sagittal "
        "sinus, two transverse sinuses that are commonly asymmetric, a straight sinus running from the vein of "
        "Galen to the torcular, and two thin internal cerebral veins under the corpus callosum. Susceptibility-"
        "weighted imaging adds the medullary and cortical veins that are too variable to survive averaging.",
        [pathol("Cerebral venous sinus thrombosis", "MRV",
                "A filling defect or absent flow in a sinus that the atlas shows should be continuous, with the empty "
                "delta sign after contrast and, on unenhanced CT, a hyperdense cord along the expected course.",
                sequence="n/a",
                pitfalls="Flow gaps, arachnoid granulations and a hypoplastic transverse sinus all mimic thrombosis on "
                         "time-of-flight venography; confirm with contrast-enhanced or susceptibility imaging"),
         pathol("Venous infarction", "MRI",
                "Edema and petechial hemorrhage that do not respect arterial territory borders, in the drainage field of "
                "the occluded channel rather than in a cortical wedge.",
                sequence="FLAIR"),
         pathol("Dural arteriovenous fistula", "DSA",
                "Arterialized flow in a sinus or a cortical vein with retrograde cortical venous drainage, which is the "
                "feature that predicts hemorrhage.",
                sequence="n/a")],
        seq="Contrast-enhanced MR venography, with susceptibility-weighted imaging for the small veins"),
    [("No deficit: reference surface", "n/a", "This is an imaging-derived reference, not a structure with a lesion syndrome"),
     ("Shows where an absent channel should have been", "n/a",
      "The averaged tree marks the expected course of every constant sinus and deep vein")],
    ["Compare a patient's venogram with the atlas surface before calling a sinus absent",
     "Follow each sinus from the vertex to the jugular bulb rather than looking at one slice"],
    ["A vessel present in the average atlas is present in nearly everybody: its absence needs an explanation",
     "The atlas is thicker than a real vein; use it for course, not for caliber",
     "The deep veins and the straight sinus are the constant part of the map; the cortical veins are the variable part"],
    [BRAIN_VEINS, SINUSES, MRV, POSTFOSSA, CVT],
    synonyms=["VENAT venous atlas", "average intracranial venous tree", "venogram template"],
    subsystem="venat", meshIds=["veins-venat-atlas"],
    afferents=[("Cortical, medullary and deep cerebral veins", "inflow")],
    efferents=[("Internal jugular veins", "sigmoid sinuses and jugular bulbs")],
    venous="The whole intracranial venous outflow, ending at the jugular bulbs and the vertebral venous plexus",
    syndromes=["syn-cerebral-venous-sinus-thrombosis", "syn-cavernous-sinus-thrombosis"],
    pitfalls=["Averaging removes normal variants; a channel absent here can still be normal in one person",
              "The threshold that keeps the sinuses clean also removes the smallest cortical veins"],
    tags=["reference", "venous", "MRV", "atlas", "VENAT"]))

write(E)
