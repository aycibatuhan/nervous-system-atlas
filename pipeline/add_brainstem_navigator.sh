#!/bin/zsh
# Adds the Brainstem Navigator nuclei after you have downloaded the toolkit by hand.
#
#   1. https://www.nitrc.org/projects/brainstemnavig/  -> accept the licence, download
#      BrainstemNavigatorv1.0.zip (NITRC serves a click-through page, so the pipeline cannot fetch it).
#   2. Put the archive at pipeline/raw/manual/BrainstemNavigatorv1.0.zip
#      (or pipeline/raw/brainstem_navigator/BrainstemNavigatorv1.0.zip), or unpack it into
#      pipeline/raw/brainstem_navigator/.
#   3. Run this script.
#
# Mapping (abbreviation -> mesh id, name, side, colour, duplicate-of): pipeline/config/brainstem_navigator.yaml
set -e
cd "$(dirname "$0")/.."
cd pipeline
echo "== inventory $(date)"; uv run atlas-brainstem-nav --inventory
echo "== brainstem navigator meshes $(date)"; uv run atlas-brainstem-nav "$@"
echo "== manifest $(date)"; uv run atlas-manifest
echo "== qa $(date)"; uv run atlas-qa || true
cd ..
echo "== check-data $(date)"; node scripts/check-data.ts || true
echo "== done $(date)"
