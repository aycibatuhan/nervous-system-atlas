"""Step 06d: brainstem and diencephalic nuclei from the Brainstem Navigator toolkit (Bianciardi lab).

WHAT YOU MUST DOWNLOAD BY HAND
------------------------------
The pipeline cannot fetch this dataset: NITRC serves a login / click-through licence page rather than the
file, so `atlas-download` lists it as manual (config/sources.yaml, id `brainstem_navigator`, group
`manual`). To add it:

  1. Open https://www.nitrc.org/projects/brainstemnavig/ and, under "Download", accept the terms and
     download the toolkit archive **BrainstemNavigatorv1.0.zip** (about 1 GB; a NITRC account may be
     required). The direct link recorded in sources.yaml is
     https://www.nitrc.org/frs/download.php/17380/BrainstemNavigatorv1.0.zip - it only works after the
     click-through, so use a browser.
  2. Put the archive at either

         pipeline/raw/manual/BrainstemNavigatorv1.0.zip
         pipeline/raw/brainstem_navigator/BrainstemNavigatorv1.0.zip

     or unpack it yourself into pipeline/raw/brainstem_navigator/.
  3. Run `pipeline/add_brainstem_navigator.sh`, or by hand:

         pipeline/.venv/bin/atlas-brainstem-nav --inventory     # what was found, nothing written
         pipeline/.venv/bin/atlas-brainstem-nav                 # mesh the mapped nuclei
         pipeline/.venv/bin/atlas-manifest && pipeline/.venv/bin/atlas-qa

Nothing here downloads, scrapes or reconstructs the data; without the archive every entry point prints
what is missing and exits cleanly.

WHAT THE TOOLKIT CONTAINS
-------------------------
Bianciardi's Brainstem Navigator v1.0 unpacks to `BrainstemNavigatorv1.0/1.0/` with four label trees: the
same nuclei drawn on the IIT template (1a, 1b) and in MNI space (2a.BrainstemNucleiAtlas_MNI,
2b.DiencephalicNucleiAtlas_MNI). Only the two MNI trees are used - discovery requires "mni" somewhere in
the path. Each tree holds `labels_probabilistic/`, `labels_thresholded_probabilistic_0.35/` and
`labels_thresholded_binary_0.35/`; the binary set is preferred and the probabilistic maps are meshed at
`probability_threshold` when only they are present.

The v1.0 MNI release ships 42 brainstem abbreviations (31 numbered nuclei plus the SN/RN/mRt/iMRt/sMRt
subdivisions) and 5 diencephalic ones (LG, MG, STh, STh1, STh2). File names are `<ABBREV>.nii.gz` for the
midline nuclei and `<ABBREV>_l.nii.gz` / `<ABBREV>_r.nii.gz` for the bilateral ones, so a file stem is
matched by stripping a trailing side token and comparing the remainder to a key of
config/brainstem_navigator.yaml **exactly**. That matters: a substring match would let `PnO` shadow the
combined `PnO_PnC` file and `LDTg` shadow `LDTg_CGPn`, meshing the wrong volume under the wrong name.
Every abbreviation that is not in the YAML is logged and skipped rather than guessed at, and any file
that fails to load is reported and skipped - this step never raises. macOS AppleDouble sidecars
(`__MACOSX/…` and `._*`) are ignored.

SPACE
-----
The MNI label sets are 182x218x182 at 1 mm with affine [[1,0,0,-91],[0,1,0,-126],[0,0,1,-72]], i.e. the
FSL MNI152 (6th generation, NLin6-like) box that the shipped Readme names, so the meshes are tagged
"nlin6-identity" exactly like the other NLin6 atlases in this pipeline. Nothing in the MNI trees is
0.5 mm, so `prefer_resolution` is only a tie-break; the voxel size is read from the NIfTI header, never
from the file name. If a future release states that the labels are in MNI152NLin2009cAsym, set
`space: mni2009` in config/brainstem_navigator.yaml and the meshes become "native-mni".

DUPLICATES
----------
Several of these nuclei already exist in the atlas from MASSP20, CIT168 or the Neudorfer hypothalamus
atlas (substantia nigra, red nucleus, PAG, VTA, colliculi, dorsal and median raphe, pedunculopontine
nucleus, subthalamic nucleus, and the geniculate bodies). Those entries carry a `duplicates:` key in the
YAML and are skipped unless `--with-duplicates` is given, so the default run only adds nuclei the atlas
does not already have. The 7 T *subdivisions* of those same nuclei (SN1/SN2, RN1/RN2, STh1/STh2 and the
reticular-formation parts) are NOT duplicates: they are meshed, hidden by default, and carry a
`structureId` pointing at the parent structure so they inherit its content entry.
"""
from __future__ import annotations

import argparse
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

from . import catalog
from .atlas_meshes import record
from .catalog import BUDGET, LOD_FACES, LOD_MIN_FACES, MeshSpec
from .meshing import export_with_lod, mesh_from_mask
from .paths import CONFIG, LICENSES, MESHES, RAW, WORK
from .spaces import load_ras

SOURCE_ID = "brainstem_navigator"
ROOT_DIR = RAW / SOURCE_ID
ZIP_CANDIDATES = [RAW / "manual" / "BrainstemNavigatorv1.0.zip", ROOT_DIR / "BrainstemNavigatorv1.0.zip"]
CONFIG_FILE = CONFIG / "brainstem_navigator.yaml"
LABEL_DIRS = ("labels_thresholded_binary", "labels_probabilistic")
SIDE_TOKENS = {"l": "left", "left": "left", "lh": "left", "lft": "left",
               "r": "right", "right": "right", "rh": "right", "rgt": "right"}
NIFTI = re.compile(r"\.nii(\.gz)?$", re.I)
# macOS puts AppleDouble resource forks (__MACOSX/…/._Name.nii.gz) into archives it re-zips; they are
# 4 kB of metadata, not NIfTI, and would otherwise show up as a second copy of every abbreviation.
APPLEDOUBLE = re.compile(r"(^|/)__MACOSX(/|$)")


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {"space": "nlin6", "nuclei": {}, "skip_duplicates": True,
                "prefer_resolution": "0.5", "prefer_labels": LABEL_DIRS[0], "probability_threshold": 0.35}
    cfg = yaml.safe_load(CONFIG_FILE.read_text()) or {}
    cfg.setdefault("space", "nlin6")
    cfg.setdefault("nuclei", {})
    cfg.setdefault("skip_duplicates", True)
    cfg.setdefault("prefer_resolution", "0.5")
    cfg.setdefault("prefer_labels", LABEL_DIRS[0])
    cfg.setdefault("probability_threshold", 0.35)
    return cfg


# ---------------------------------------------------------------- discovery


@dataclass
class Found:
    path: Path
    abbrev: str            # the token matched against the YAML (or the raw stem when unknown)
    side: str | None       # "left" | "right" | None
    kind: str              # "thresholded" | "probabilistic"
    resolution: str        # "0.5" | "1" | "?"
    known: bool


def unzip_if_needed() -> Path | None:
    """Return the folder holding the toolkit, unzipping a hand-placed archive first. Never raises."""
    if ROOT_DIR.exists() and any(p for p in ROOT_DIR.rglob("*") if NIFTI.search(p.name)):
        return ROOT_DIR
    for z in ZIP_CANDIDATES:
        if not z.exists():
            continue
        ROOT_DIR.mkdir(parents=True, exist_ok=True)
        marker = ROOT_DIR / f".{z.name}.unzipped"
        if marker.exists():
            return ROOT_DIR
        print(f"  [unzip] {z} -> {ROOT_DIR}")
        try:
            with zipfile.ZipFile(z) as zf:
                zf.extractall(ROOT_DIR)
            marker.write_text(z.name)
        except Exception as e:  # noqa: BLE001
            print(f"  [FAIL] could not unzip {z}: {e}")
            return ROOT_DIR if ROOT_DIR.exists() else None
        return ROOT_DIR
    return ROOT_DIR if ROOT_DIR.exists() else None


def _junk(path: Path) -> bool:
    """AppleDouble sidecars and the __MACOSX shadow tree an OS X re-zip leaves behind."""
    return path.name.startswith("._") or APPLEDOUBLE.search("/".join(path.parts)) is not None


def _resolution_of(path: Path) -> str:
    """Voxel size from the NIfTI header. The toolkit does not put the resolution in the file name, and
    the 1 mm and 0.5 mm label sets live in identically named folders, so the header is the only source."""
    try:
        import nibabel as nib
        z = [abs(float(v)) for v in nib.load(str(path)).header.get_zooms()[:3]]
    except Exception:  # noqa: BLE001 - a header that will not parse is reported as unknown, not fatal
        return "?"
    if not z or max(z) <= 0:
        return "?"
    v = sum(z) / len(z)
    return f"{v:g}" if abs(v - round(v, 1)) < 1e-3 else f"{v:.2f}"


def _split_side(stem: str) -> tuple[str, str | None]:
    """"LDTg_CGPn_l" -> ("LDTg_CGPn", "left"). Only a trailing side token is stripped, so a compound
    abbreviation keeps every part of its name and cannot be shadowed by a shorter key (PnO_PnC by PnO)."""
    m = re.match(r"^(.*?)[_\-.]([A-Za-z]+)$", stem)
    if m and m.group(1) and m.group(2).lower() in SIDE_TOKENS:
        return m.group(1), SIDE_TOKENS[m.group(2).lower()]
    return stem, None


def _match_abbrev(stem: str, keys) -> tuple[str | None, str | None]:
    """Exact (case-insensitive) match of the side-stripped file stem against a YAML key."""
    base, side = _split_side(stem)
    if base in keys:
        return base, side
    low = {k.lower(): k for k in keys}
    if base.lower() in low:
        return low[base.lower()], side
    return None, side


def discover(root: Path, cfg: dict) -> list[Found]:
    """Every MNI-space label NIfTI under the toolkit, tagged with its abbreviation, side and kind."""
    keys = list(cfg["nuclei"].keys())
    out: list[Found] = []
    try:
        paths = sorted(p for p in root.rglob("*") if p.is_file() and NIFTI.search(p.name))
    except OSError as e:
        print(f"  [FAIL] cannot walk {root}: {e}")
        return out
    for p in paths:
        if _junk(p):
            continue
        parts = [x.lower() for x in p.parts]
        kind = None
        for d in LABEL_DIRS:
            if any(d in x for x in parts):
                kind = "thresholded" if d == LABEL_DIRS[0] else "probabilistic"
        if kind is None:
            continue
        # the toolkit ships the same nuclei twice: once on the IIT template and once in MNI space
        # (2a.BrainstemNucleiAtlas_MNI / 2b.DiencephalicNucleiAtlas_MNI). Only the MNI sets are used.
        if not any("mni" in x for x in parts):
            continue
        stem = NIFTI.sub("", p.name)
        ab, side = _match_abbrev(stem, keys)
        base = ab or _split_side(stem)[0]
        out.append(Found(p, base, side, kind, _resolution_of(p), ab is not None))
    return out


def select(found: list[Found], cfg: dict) -> list[Found]:
    """One file per (abbreviation, side): preferred label kind first, then preferred resolution."""
    want_kind = "thresholded" if cfg["prefer_labels"] == LABEL_DIRS[0] else "probabilistic"
    best: dict[tuple[str, str | None], Found] = {}
    for f in found:
        key = (f.abbrev, f.side)
        cur = best.get(key)
        if cur is None or _rank(f, want_kind, cfg["prefer_resolution"]) > _rank(cur, want_kind, cfg["prefer_resolution"]):
            best[key] = f
    return sorted(best.values(), key=lambda f: (f.abbrev, f.side or ""))


def _rank(f: Found, want_kind: str, want_res: str) -> tuple[int, int, int]:
    # preferred label kind, then preferred resolution, then the shortest file name (so a file that merely
    # contains the abbreviation cannot shadow the file that *is* the label)
    return (1 if f.kind == want_kind else 0, 1 if f.resolution == want_res else 0, -len(f.path.name))


# ---------------------------------------------------------------- specs


def spec_for(f: Found, entry: dict) -> MeshSpec:
    base = entry["id"]
    system = entry.get("system") or "brainstem"
    sub = entry.get("subsystem")
    colour = entry.get("colour") or catalog.jitter(catalog.SYSTEM_COLOUR[system], base)
    budget = entry.get("budget", "tiny")
    visible = bool(entry.get("visible", False))
    if f.side is None:
        return MeshSpec(base, entry["name"], system, subsystem=sub, side="midline", budget=budget,
                        colour=colour, visible=visible, structure_id=entry.get("structureId") or base)
    sfx = "-l" if f.side == "left" else "-r"
    return MeshSpec(base + sfx, f"{entry['name']} ({'L' if f.side == 'left' else 'R'})", system, subsystem=sub,
                    side=f.side, budget=budget, colour=colour, visible=visible,
                    structure_id=entry.get("structureId") or base)


def palette_specs() -> dict[str, MeshSpec]:
    """mesh id -> spec for every mapped nucleus, so manifest.palette() can refresh colours without data."""
    cfg = load_config()
    out: dict[str, MeshSpec] = {}
    for entry in cfg["nuclei"].values():
        for side in (("left", "right") if entry.get("paired") else (None,)):
            f = Found(Path("."), "", side, "thresholded", "?", True)
            s = spec_for(f, entry)
            out[s.id] = s
    return out


# ---------------------------------------------------------------- build


# The smallest nuclei here are a handful of 1 mm voxels one voxel thick (the locus coeruleus is 12
# voxels in a 4x4x11 box, raphe magnus 11 in 2x4x4). The default 2x / sigma 0.6 signed-distance
# smoothing either wipes such a sheet out completely - the smoothed field never crosses zero and
# marching cubes finds nothing - or shrinks it to a bead a tenth of its true size. So each mask is
# meshed on a ladder of finer grids with gentler smoothing and the first rung is kept only if the
# surface it produces still spans most of the mask.
SMOOTHING_LADDER = ((2, None), (4, 0.35), (4, 0.15))
MIN_EXTENT_FRAC = 0.85     # mesh bounding-box diagonal / mask bounding-box diagonal


def _mask_diagonal_mm(mask: np.ndarray, affine: np.ndarray) -> float:
    idx = np.argwhere(mask)
    lo, hi = idx.min(0), idx.max(0) + 1          # +1: a single voxel still spans one voxel
    corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])], float)
    mm = corners @ affine[:3, :3].T + affine[:3, 3]
    return float(np.linalg.norm(mm.max(0) - mm.min(0)))


def _mesh_tiny(mask: np.ndarray, affine: np.ndarray, target_faces: int, vox: float):
    """mesh_from_mask with a fallback ladder for sub-voxel-thin nuclei. Returns (mesh|None, extra)."""
    default = 0.6 if vox >= 0.9 else 1.0
    want = MIN_EXTENT_FRAC * _mask_diagonal_mm(mask, affine)
    best, best_extra, best_span = None, {}, -1.0
    for up, sigma in SMOOTHING_LADDER:
        sig = default if sigma is None else sigma
        mesh = mesh_from_mask(mask, affine, target_faces, sigma=sig, upsample=up)
        if mesh is None or len(mesh.faces) < 40:
            continue
        span = float(np.linalg.norm(mesh.bounds[1] - mesh.bounds[0]))
        extra = {} if (up, sigma) == SMOOTHING_LADDER[0] else {"smoothing": {"upsample": up, "sigma": sig}}
        if span > best_span:
            best, best_extra, best_span = mesh, extra, span
        if span >= want:
            return mesh, extra
    return best, best_extra


def build(sel: list[Found], cfg: dict, only: set[str] | None, with_duplicates: bool) -> list[dict]:
    alignment = "native-mni" if cfg["space"] == "mni2009" else "nlin6-identity"
    thr = float(cfg["probability_threshold"])
    out: list[dict] = []
    for f in sel:
        if not f.known:
            print(f"  [skip] unknown abbreviation '{f.abbrev}' ({f.path.name})")
            continue
        entry = cfg["nuclei"][f.abbrev]
        dup = entry.get("duplicates")
        if dup and cfg["skip_duplicates"] and not with_duplicates:
            print(f"  [skip] {f.abbrev}: duplicates the existing mesh '{dup}'")
            continue
        spec = spec_for(f, entry)
        if only and spec.id not in only and spec.structure_id not in only and f.abbrev not in only:
            continue
        try:
            img = load_ras(f.path)
            data = np.asanyarray(img.dataobj).astype(np.float32)
            data = data[..., 0] if data.ndim == 4 else data
            mask = data >= (0.5 if f.kind == "thresholded" else thr)
            if not mask.any():
                print(f"  [skip] {spec.id}: empty at threshold")
                continue
            vox = float(np.cbrt(abs(np.linalg.det(img.affine[:3, :3]))))
            mesh, smoothing = _mesh_tiny(mask, img.affine, BUDGET[spec.budget], vox)
            if mesh is None:
                print(f"  [skip] {spec.id}: no surface ({int(mask.sum())} voxels)")
                continue
            path = MESHES / spec.system / f"{spec.id}.glb"
            nbytes, lod = export_with_lod(mesh, path, spec.id, LOD_FACES, LOD_MIN_FACES)
            out.append(record(spec, SOURCE_ID, None, alignment, mesh, path, nbytes, int(mask.sum()),
                              {"labelVolume": "anat", "abbrev": f.abbrev, "labelKind": f.kind,
                               "sourceFile": f.path.name, "lod": lod, **smoothing}))
            print(f"  {spec.id:44s} {len(mesh.faces):6d} tris {nbytes / 1024:7.1f} KB  ({f.abbrev}, {f.kind})")
        except Exception as e:  # noqa: BLE001 - one bad file must not stop the run
            print(f"  [FAIL] {f.path.name}: {type(e).__name__}: {e}")
    return out


LICENSE_ID = "BrainstemNavigator-NC-ND"
LICENSE_NOTE = """
--------------------------------------------------------------------------------
Note for this atlas: the meshes built from the Brainstem Navigator carry the source
id "brainstem_navigator" and are marked nc: true / noRedistribution: true in
public/data/manifest.json. Under clause 2 above they are local-only and must be
excluded from any build that leaves the organisation.
"""


def copy_license(root: Path) -> None:
    """Put the toolkit's own Copyright.txt into public/data/licenses/ (clause 1 requires the original
    notices to travel with every copy). atlas-download writes a 3-line stub for every licence id, so
    this runs after every ingest rather than once."""
    src = next((p for p in root.rglob("Copyright.txt") if not _junk(p)), None)
    if src is None:
        print("  [warn] Documentation/Copyright.txt not found; licence text left as is")
        return
    try:
        LICENSES.mkdir(parents=True, exist_ok=True)
        (LICENSES / f"{LICENSE_ID}.txt").write_text(src.read_text().rstrip() + "\n" + LICENSE_NOTE)
        print(f"  licence: {src} -> {LICENSES / (LICENSE_ID + '.txt')}")
    except OSError as e:
        print(f"  [warn] could not write the licence text: {e}")


def print_inventory(root: Path, found: list[Found], sel: list[Found], cfg: dict) -> None:
    print(f"root: {root}")
    print(f"label files found: {len(found)}  ({len({f.abbrev for f in found})} distinct abbreviations)")
    kinds = sorted({(f.kind, f.resolution) for f in found})
    print("label kinds / resolutions present:", ", ".join(f"{k} @ {r} mm" for k, r in kinds) or "none")
    known = [f for f in sel if f.known]
    unknown = sorted({f.abbrev for f in sel if not f.known})
    dup = [f for f in known if cfg["nuclei"][f.abbrev].get("duplicates")]
    print(f"selected: {len(sel)} files -> {len(known)} mapped, {len(unknown)} unmapped abbreviations, "
          f"{len(dup)} mapped-but-duplicate (skipped by default)")
    for f in sel:
        if f.known:
            e = cfg["nuclei"][f.abbrev]
            tag = f"  DUPLICATE of {e['duplicates']}" if e.get("duplicates") else ""
            print(f"  {f.abbrev:12s} {f.side or 'midline':7s} {f.kind:13s} {f.resolution:>3s} mm  -> {spec_for(f, e).id}{tag}")
    if unknown:
        print("unmapped (logged and skipped; add them to config/brainstem_navigator.yaml if wanted):")
        for a in unknown:
            print("  ", a)
    if found:
        try:
            img = load_ras(found[0].path)
            print(f"first file header: {found[0].path.name} shape {img.shape} affine\n{np.round(img.affine, 3)}")
            print(f"space in config: {cfg['space']} -> alignment "
                  f"{'native-mni' if cfg['space'] == 'mni2009' else 'nlin6-identity'}")
        except Exception as e:  # noqa: BLE001
            print("could not read the first file:", e)
    rms = [p for p in root.rglob("*") if p.is_file() and p.name.lower().startswith("readme")][:3]
    if rms:
        print("readme files shipped with the toolkit (check the stated MNI version):")
        for p in rms:
            print("  ", p)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Brainstem Navigator nuclei -> meshes (manual download required)")
    ap.add_argument("--inventory", action="store_true", help="list what was found and stop")
    ap.add_argument("--only", help="comma list of mesh ids / structure ids / abbreviations")
    ap.add_argument("--with-duplicates", action="store_true", help="also mesh nuclei the atlas already has")
    a = ap.parse_args(argv)
    print("[brainstem_navigator]")
    cfg = load_config()
    root = unzip_if_needed()
    if root is None or not root.exists():
        print("  [skip] the Brainstem Navigator toolkit is not present. Download BrainstemNavigatorv1.0.zip")
        print("         from https://www.nitrc.org/projects/brainstemnavig/ (click-through licence) and put it at")
        for z in ZIP_CANDIDATES:
            print(f"           {z}")
        print(f"         or unpack it into {ROOT_DIR}. See the module docstring for the full instructions.")
        return
    found = discover(root, cfg)
    if not found:
        print(f"  [skip] no MNI-space label NIfTI found under {root}")
        print(f"         expected NIfTI files below a directory whose path contains 'MNI', under "
              f"{' or '.join(LABEL_DIRS)}/")
        return
    sel = select(found, cfg)
    if a.inventory:
        print_inventory(root, found, sel, cfg)
        return
    print_inventory(root, found, sel, cfg)
    copy_license(root)
    only = set(a.only.split(",")) if a.only else None
    results = build(sel, cfg, only, a.with_duplicates)
    if not results:
        print("  nothing built")
        return
    out_path = WORK / "meshes.json"
    existing = {m["id"]: m for m in json.loads(out_path.read_text())} if out_path.exists() else {}
    for r in results:
        existing[r["id"]] = r
    out_path.write_text(json.dumps(list(existing.values()), indent=1))
    print(f"brainstem navigator: {len(results)} meshes, {sum(r['bytes'] for r in results) / 1e6:.2f} MB -> {out_path}")


if __name__ == "__main__":
    main()
