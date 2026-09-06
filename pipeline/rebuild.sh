#!/bin/zsh
# Full geometry rebuild after meshing/palette changes. Log: pipeline/work/rebuild.log
set -e
cd "$(dirname "$0")/.."
echo "== blender export $(date)"; blender/.venv/bin/python blender/export_zanatomy.py
cd pipeline
echo "== atlas meshes $(date)"; uv run atlas-atlas-meshes --force
echo "== venat veins $(date)"; uv run atlas-venat
echo "== bp3d meshes $(date)"; uv run atlas-bp3d-meshes
echo "== zanatomy midline fit $(date)"; uv run atlas-zanatomy-midline
echo "== zanatomy meshes $(date)"; uv run atlas-zanatomy-meshes
# order matters: atlas-pam50 reads the shipped cord surface (zanatomy-meshes) and writes cord_levels.json;
# atlas-derived reads cord_levels.json to cut the cord segment blocks at the measured PAM50 levels.
echo "== cord MRI (PAM50 curved reformat) $(date)"; uv run atlas-pam50
echo "== derived meshes $(date)"; uv run atlas-derived
echo "== manifest $(date)"; uv run atlas-manifest
echo "== qa $(date)"; uv run atlas-qa || true
cd ..
echo "== check-data $(date)"; node scripts/check-data.ts || true
echo "== done $(date)"
