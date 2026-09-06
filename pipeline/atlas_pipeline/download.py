"""Step 01: download every dataset in config/sources.yaml with sha256 locking."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
import yaml
from tqdm import tqdm

from .paths import CONFIG, RAW, LICENSES


def _join(loader, node):
    return "".join(loader.construct_sequence(node))


yaml.SafeLoader.add_constructor("!join", _join)


def load_sources() -> dict:
    return yaml.safe_load((CONFIG / "sources.yaml").read_text())


def load_lock() -> dict:
    p = CONFIG / "sources.lock.yaml"
    return yaml.safe_load(p.read_text()) if p.exists() else {}


def save_lock(lock: dict) -> None:
    (CONFIG / "sources.lock.yaml").write_text(yaml.safe_dump(lock, sort_keys=True))


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dest_name(entry: dict) -> str:
    if "dest" in entry:
        return entry["dest"]
    return Path(urlparse(entry["url"]).path).name


def fetch(url: str, dest: Path, client: httpx.Client) -> None:
    tmp = dest.with_suffix(dest.suffix + ".part")
    headers = {}
    pos = 0
    if tmp.exists():
        pos = tmp.stat().st_size
        headers["Range"] = f"bytes={pos}-"
    with client.stream("GET", url, headers=headers, follow_redirects=True, timeout=120) as r:
        if r.status_code == 416:  # already complete
            tmp.rename(dest)
            return
        r.raise_for_status()
        if r.status_code != 206:
            pos = 0
        total = int(r.headers.get("content-length", 0)) + pos
        mode = "ab" if pos else "wb"
        with tmp.open(mode) as f, tqdm(total=total or None, initial=pos, unit="B", unit_scale=True, desc=dest.name, leave=False) as bar:
            for chunk in r.iter_bytes(1 << 18):
                f.write(chunk)
                bar.update(len(chunk))
    tmp.rename(dest)


def run(groups: set[str] | None = None, strict: bool = True) -> int:
    cfg = load_sources()
    lock = load_lock()
    groups = groups or {"core"}
    failures = 0
    with httpx.Client(headers={"User-Agent": "nervous-system-atlas-pipeline/0.1"}) as client:
        for src in cfg["sources"]:
            if src["group"] not in groups and "all" not in groups:
                continue
            folder = RAW / src["id"]
            folder.mkdir(parents=True, exist_ok=True)
            lic = cfg["licenses"][src["license"]]
            (folder / "LICENSE_INFO.txt").write_text(
                f"{lic['name']}\n{lic['url']}\n{lic.get('attribution', '')}\n\nCitation: {src['citation']}\n"
            )
            for entry in src["files"]:
                name = dest_name(entry)
                dest = folder / name
                key = f"{src['id']}/{name}"
                if src.get("manual"):
                    if not dest.exists():
                        print(f"[manual] {key}: place the file at {dest} (download from {entry['url']})")
                        continue
                elif not dest.exists():
                    print(f"[get] {key}  <-  {entry['url']}")
                    try:
                        fetch(entry["url"], dest, client)
                    except Exception as e:  # noqa: BLE001
                        print(f"[FAIL] {key}: {e}", file=sys.stderr)
                        failures += 1
                        continue
                digest = sha256_of(dest)
                rec = lock.get(key)
                if rec and rec["sha256"] != digest:
                    msg = f"[HASH MISMATCH] {key}: lock {rec['sha256'][:12]} != file {digest[:12]}"
                    if strict:
                        print(msg, file=sys.stderr)
                        failures += 1
                        continue
                    print(msg + " (updating lock)")
                lock[key] = {"sha256": digest, "bytes": dest.stat().st_size, "url": entry["url"],
                             "fetched": rec["fetched"] if rec else datetime.now(timezone.utc).isoformat(timespec="seconds")}
                if entry.get("unzip"):
                    marker = folder / f".{name}.unzipped"
                    if not marker.exists():
                        print(f"[unzip] {key}")
                        with zipfile.ZipFile(dest) as z:
                            z.extractall(folder)
                        marker.write_text(digest)
            (folder / "SOURCE.json").write_text(json.dumps({
                "id": src["id"], "license": src["license"], "citation": src["citation"],
                "files": {dest_name(e): e["url"] for e in src["files"]},
            }, indent=2))
    save_lock(lock)
    # licence texts for the manifest (public/data/licenses/<id>.txt, shown in the app's About panel):
    # the name/url/attribution header, followed by the verbatim legal code when config/license_texts/ has it.
    # A licence whose verbatim terms another step wrote from the download itself (Brainstem Navigator) is left alone.
    for lid, lic in cfg["licenses"].items():
        head = f"{lic['name']}\n{lic['url']}\n{lic.get('attribution', '')}\n"
        body = CONFIG / "license_texts" / f"{lid}.txt"
        out = LICENSES / f"{lid}.txt"
        if body.exists():
            out.write_text(head + "\n" + body.read_text())
        elif not (out.exists() and len(out.read_text()) > len(head) + 32):
            out.write_text(head)
    return failures


def main(argv: list[str] | None = None) -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Download atlas sources")
    ap.add_argument("--with", dest="groups", default="core", help="comma list of groups: core,bp3d,vessels,warp,zanatomy,manual,all")
    ap.add_argument("--no-strict", action="store_true", help="update lock on hash mismatch instead of failing")
    a = ap.parse_args(argv)
    n = run(set(a.groups.split(",")), strict=not a.no_strict)
    if n:
        sys.exit(f"{n} download(s) failed")
    print("downloads complete")


if __name__ == "__main__":
    main()
