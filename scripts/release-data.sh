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
echo "── npm run build (public edition + check-public)"
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
rm -f "${ASSET}"
tar -czf "${ASSET}" -C dist/data .
SHA=$(shasum -a 256 "${ASSET}" | cut -d' ' -f1)
BYTES=$(wc -c < "${ASSET}" | tr -d ' ')
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
