import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).parent))
from lib import *

def D(modality, side, distribution, sign, substrate=None):
    d = {"modality": modality, "side": side, "distribution": distribution, "sign": sign}
    if substrate: d["substrate"] = substrate
    return d

def sphere(x, y, z, r=8): return {"kind": "sphere", "mni": {"x": x, "y": y, "z": z}, "radiusMm": r}
def terr(*mesh_ids): return {"kind": "territory", "meshIds": list(mesh_ids)}
def structs(*mesh_ids): return {"kind": "structures", "meshIds": list(mesh_ids)}
def nerve(*mesh_ids): return {"kind": "nerve", "meshIds": list(mesh_ids)}
def segment(x, y, z, r=10): return {"kind": "segment", "mni": {"x": x, "y": y, "z": z}, "radiusMm": r}
def hint(plane, x, y, z, label): return {"plane": plane, "mni": {"x": x, "y": y, "z": z}, "label": label}

def syn(id, name, category, structures, side, presentation, deficits, reasoning, imaging, causes, mimics, mgmt, citations, *,
        eponyms=(), level=None, arteryId=None, territoryId=None, marker=None, imagingHint=None, exam=None, preset=None, tier="core"):
    loc = {"structures": list(structures), "side": side}
    if level: loc["level"] = level
    if arteryId: loc["arteryId"] = arteryId
    if territoryId: loc["territoryId"] = territoryId
    d = {"kind": "syndrome", "id": id, "name": name, "eponyms": list(eponyms), "category": category, "tier": tier, "localisation": loc,
         "lesionMarker": marker or {"kind": "structures", "meshIds": []}, "presentation": presentation, "deficits": deficits, "reasoning": reasoning,
         "imagingFindings": imaging, "commonCauses": list(causes), "mimics": [{"name": a, "howToDistinguish": b} for a, b in mimics],
         "management": list(mgmt), "citations": citations, "status": "draft"}
    if imagingHint: d["imagingHint"] = imagingHint
    if exam: d["examSequence"] = list(exam)
    if preset: d["cameraPreset"] = preset
    return d
