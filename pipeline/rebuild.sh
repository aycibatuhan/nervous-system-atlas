#!/bin/zsh
# Full geometry rebuild after meshing/palette changes. Log: pipeline/work/rebuild.log
set -e
cd "$(dirname "$0")/.."
echo "== blender export $(date)"; blender/.venv/bin/python blender/export_zanatomy.py
cd pipeline
echo "== atlas meshes $(date)"; uv run atlas-atlas-meshes --force
echo "== bp3d meshes $(date)"; uv run atlas-bp3d-meshes
echo "== zanatomy meshes $(date)"; uv run atlas-zanatomy-meshes
echo "== manifest $(date)"; uv run atlas-manifest
echo "== qa $(date)"; uv run atlas-qa || true
cd ..
echo "== check-data $(date)"; node scripts/check-data.ts || true
echo "== done $(date)"
