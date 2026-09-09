#!/usr/bin/env bash
# Build the data archive that `npm run data` fetches, and pin its checksum.
#
#   scripts/release-data.sh [tag]          # default tag: the version in package.json
#   scripts/release-data.sh v1.0.0 --upload
#
# What goes in is dist/data -- the output of `npm run build`, which is the edition check-public has certified.
# Nothing else is publishable: dist-private/ must never be uploaded, and public/data/ on a machine with the
# restricted atlases still contains them.
set -euo pipefail
cd "$(dirname "$0")/.."

TAG="${1:-v$(node -p "require('./package.json').version")}"
[[ "${TAG}" == --* ]] && { TAG="v$(node -p "require('./package.json').version")"; set -- "" "$@"; }
ASSET="atlas-data-${TAG}.tar.gz"
UPLOAD=false
for a in "$@"; do [[ "$a" == "--upload" ]] && UPLOAD=true; done

# ---- 1. a fresh, gated build
# dist/ is wiped first on purpose. A stale dist/ is how a file the gate forbids reaches an archive: the build
# filters what it copied, but anything that arrived in dist/ by other means outlives it, and packaging by hand
# skips the gate entirely. Build from nothing, then let check-public see the result.
echo "── npm run build (public edition + check-public)"
rm -rf dist
npm run build

# ---- 2. refuse to ship anything the gate did not see
if [[ ! -f dist/data/manifest.json ]]; then
  echo "release-data: dist/data/manifest.json is missing — the build produced no data" >&2
  exit 1
fi
if compgen -G "dist/data/*.private.json" > /dev/null; then
  echo "release-data: dist/data contains a private bundle — refusing to package it" >&2
  exit 1
fi
EDITION=$(node -p "JSON.parse(require('fs').readFileSync('dist/data/manifest.json','utf8')).edition ?? 'public'")
if [[ "${EDITION}" != "public" ]]; then
  echo "release-data: dist/data says edition \"${EDITION}\" — only the public edition may be released" >&2
  exit 1
fi

# ---- 3. pack
#
# COPYFILE_DISABLE=1 is not optional. macOS files carry extended attributes (com.apple.provenance, at least),
# and BSD tar stores each one as a second "AppleDouble" member called ._<name>. Those members are invisible
# from macOS -- `tar -tzf` does not list them and extracting does not create them -- but on Linux they extract
# as 823 real ._* files, which is what made the first Pages deploy fail check-public with 823 errors.
rm -f "${ASSET}"
COPYFILE_DISABLE=1 tar -czf "${ASSET}" -C dist/data .
SHA=$(shasum -a 256 "${ASSET}" | cut -d' ' -f1)
BYTES=$(wc -c < "${ASSET}" | tr -d ' ')

# ---- 3b. verify the archive, with a reader that does not share tar's blind spot
# python's tarfile lists every member literally, including the AppleDouble ones that macOS tar hides, so this
# sees the archive the way the Linux runner will.
python3 - "${ASSET}" <<'PYEOF' || exit 1
import sys, tarfile
from pathlib import Path

members = tarfile.open(sys.argv[1]).getmembers()
rel = lambda n: n[2:] if n.startswith("./") else n
apple = [m.name for m in members if m.name.split("/")[-1].startswith("._")]
if apple:
    print(f"release-data: {len(apple)} AppleDouble member(s) in the archive, e.g. {apple[:3]}", file=sys.stderr)
    print("release-data: repack with COPYFILE_DISABLE=1", file=sys.stderr)
    sys.exit(1)

packed = {rel(m.name) for m in members if m.isfile()}
root = Path("dist/data")
on_disk = {str(q.relative_to(root)) for q in root.rglob("*") if q.is_file()}
missing, extra = sorted(on_disk - packed), sorted(packed - on_disk)
if missing or extra:
    for m in missing[:10]: print(f"release-data: in dist/data but not packed: {m}", file=sys.stderr)
    for e in extra[:10]:   print(f"release-data: packed but not in dist/data: {e}", file=sys.stderr)
    sys.exit(1)
print(f"  archive verified: {len(on_disk)} files, matching the gated dist/data exactly, no AppleDouble members")
PYEOF
echo
echo "${ASSET}"
echo "  sha256 ${SHA}"
echo "  bytes  ${BYTES}"

# ---- 4. pin it, so `npm run data` and the asset cannot drift apart
node - "$TAG" "$ASSET" "$SHA" "$BYTES" <<'NODE'
const fs = require('node:fs');
const [tag, asset, sha, bytes] = process.argv.slice(2);
const p = 'scripts/fetch-data.ts';
const src = fs.readFileSync(p, 'utf8')
  .replace(/tag: '[^']*'/, `tag: '${tag}'`)
  .replace(/asset: '[^']*'/, `asset: '${asset}'`)
  .replace(/sha256: '[^']*'/, `sha256: '${sha}'`)
  .replace(/bytes: \d+/, `bytes: ${bytes}`);
fs.writeFileSync(p, src);
console.log(`pinned ${asset} in ${p}`);
NODE

# ---- 5. attach it to the release
if [[ "${UPLOAD}" == true ]]; then
  echo
  echo "── uploading to the ${TAG} release"
  gh release view "${TAG}" > /dev/null 2>&1 || {
    echo "release-data: no ${TAG} release yet — create it first (gh release create ${TAG})" >&2
    exit 1
  }
  gh release upload "${TAG}" "${ASSET}" --clobber
  echo "attached ${ASSET} to ${TAG}"
else
  echo
  echo "not uploaded. To attach it:  gh release upload ${TAG} ${ASSET} --clobber"
fi
