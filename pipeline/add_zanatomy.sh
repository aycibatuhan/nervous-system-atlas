#!/bin/zsh
set -e
cd "$(dirname "$0")/.."
IDS="lumbosacral-plexus,medial-antebrachial-cutaneous-nerve,lateral-antebrachial-cutaneous-nerve,posterior-antebrachial-cutaneous-nerve,medial-brachial-cutaneous-nerve,superficial-radial-nerve,dorsal-scapular-nerve,thoracodorsal-nerve,pectoral-nerves,posterior-femoral-cutaneous-nerve,genitofemoral-nerve,iliohypogastric-nerve,ilioinguinal-nerve,superior-gluteal-nerve,dorsal-cutaneous-nerves-foot,spinal-grey-anterior-horn,spinal-grey-posterior-horn,spinal-white-columns"
echo "== blender export $(date)"; blender/.venv/bin/python blender/export_zanatomy.py --only "$IDS"
cd pipeline
echo "== zanatomy midline fit $(date)"; uv run atlas-zanatomy-midline
echo "== zanatomy meshes $(date)"; uv run atlas-zanatomy-meshes --only "$IDS"
echo "== manifest $(date)"; uv run atlas-manifest
echo "== qa $(date)"; uv run atlas-qa || true
cd ..
echo "== check-data $(date)"; node scripts/check-data.ts || true
echo "== done $(date)"
