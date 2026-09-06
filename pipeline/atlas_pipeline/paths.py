from pathlib import Path

PIPELINE = Path(__file__).resolve().parent.parent
ROOT = PIPELINE.parent
CONFIG = PIPELINE / "config"
RAW = PIPELINE / "raw"
WORK = PIPELINE / "work"
QA = PIPELINE / "qa"
OUT = ROOT / "public" / "data"
MESHES = OUT / "meshes"
VOLUMES = OUT / "volumes"
LICENSES = OUT / "licenses"

for _p in (RAW, WORK, QA, OUT, MESHES, VOLUMES, LICENSES):
    _p.mkdir(parents=True, exist_ok=True)
