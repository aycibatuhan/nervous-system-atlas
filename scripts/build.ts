// `npm run build`: the PUBLIC edition into dist/ -- Apache-2.0 code with CC BY-SA 4.0 data, carrying only the
// meshes, volumes, label ids and licence texts that may be redistributed. This is the default build, so the
// easy thing to publish is the one the gate has been run over.
//   node scripts/build.ts [--skip-manifest] [--skip-content] [--skip-vite] [--skip-check]
//
// Steps: atlas-manifest → content build → vite build --outDir dist → filter dist/data → check-public.
// The filter matters even here: public/data/ holds whatever this machine has built, so on a machine with the
// restricted atlases it still contains their mesh files, their voxels inside the label volumes and the private
// bundles. Vite copies public/ verbatim, and this removes everything the public manifest does not reference.
//
// The full edition is `npm run build:private` (scripts/build-private.ts), which writes dist-private/.
// A clone with no generated data yet still builds the app bundle; the data steps and the gate are skipped.
import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync, existsSync, readdirSync, statSync, rmSync, mkdirSync, copyFileSync } from 'node:fs';
import { gunzipSync, gzipSync } from 'node:zlib';
import { resolve, join, relative, sep, dirname } from 'node:path';

const ROOT = resolve(import.meta.dirname, '..');
const SRC = join(ROOT, 'public/data');
const OUT = join(ROOT, 'dist');
const DATA = join(OUT, 'data');
const args = new Set(process.argv.slice(2));
const step = (s: string) => console.log(`\n── ${s}`);
const run = (cmd: string, argv: string[]) => execFileSync(cmd, argv, { cwd: ROOT, stdio: 'inherit', env: process.env });
const hasData = existsSync(join(SRC, 'manifest.json'));
if (!hasData) console.log('note: public/data/ has no manifest yet — building the app bundle only (run the pipeline for the data)');

// ---- 1. the manifests
const venv = join(ROOT, 'pipeline/.venv/bin/atlas-manifest');
if (hasData && !args.has('--skip-manifest') && existsSync(venv)) {
  step('atlas-manifest');
  run(venv, []);
}

// ---- 2. the public content bundle
if (!args.has('--skip-content')) {
  step('content build');
  run(process.execPath, ['scripts/content/build.ts']);
}

// ---- 3. vite
if (!args.has('--skip-vite')) {
  step('vite build --outDir dist');
  run(join(ROOT, 'node_modules/.bin/vite'), ['build', '--outDir', 'dist', '--emptyOutDir']);
}
if (!hasData) { console.log('\nbuilt dist/ without data — nothing to filter or gate'); process.exit(0); }
const manifest = JSON.parse(readFileSync(join(SRC, 'manifest.json'), 'utf8')) as Manifest;
const exclusions = JSON.parse(readFileSync(join(SRC, 'manifest.exclusions.json'), 'utf8')) as Exclusions;
const excluded = new Set(exclusions.meshes.map((m) => m.id));

// ---- 4. filter dist/data down to what the public manifest references
// Vite copies the whole of public/ verbatim, so at this point dist/data is whatever this machine has built --
// on a private machine that includes the restricted meshes, the private bundles and label volumes painted with
// the excluded atlases' ids. Keep only what the public manifest names, and repaint the label volumes.
step('filter dist/data');
mkdirSync(DATA, { recursive: true });

// LICENSE is the data folder's own licence (CC BY-SA 4.0), written by atlas-manifest; it ships with the data.
const keep = new Set<string>(['manifest.json', 'content.json', 'content.tr.json', 'search-index.json', 'LICENSE']);
for (const m of manifest.meshes) { keep.add(m.file); if (m.lod) keep.add(m.lod.file); }
for (const v of Object.values(manifest.volumes)) { keep.add(v.file); if (v.lut) keep.add(v.lut); }
for (const l of Object.values(manifest.licenses)) keep.add(l.text);

// 4a. labels.json: drop the lut and byMesh records of meshes this edition does not ship
const labelsRel = 'volumes/labels.json';
let zeroed: Record<string, number> = {};
if (keep.has(labelsRel) && existsSync(join(DATA, labelsRel))) {
  const labels = JSON.parse(readFileSync(join(DATA, labelsRel), 'utf8')) as LabelsJson;
  const drop: Record<string, Set<number>> = {};
  for (const [vol, lut] of Object.entries(labels.lut)) {
    drop[vol] = new Set();
    for (const [id, entry] of Object.entries(lut)) if (excluded.has(entry.meshId)) { drop[vol]!.add(Number(id)); delete lut[id]; }
  }
  for (const id of Object.keys(labels.byMesh)) if (excluded.has(id)) delete labels.byMesh[id];
  labels.volumes = Object.fromEntries(Object.entries(labels.volumes).filter(([k]) => manifest.volumes[k]));
  writeFileSync(join(DATA, labelsRel), JSON.stringify(labels, null, 1));

  // 4b. the label volumes themselves: an excluded atlas must not survive as painted voxels either
  for (const [vol, ids] of Object.entries(drop)) {
    if (!ids.size) continue;
    const key = Object.keys(labels.volumes).find((k) => k === `labels_${vol}`) ?? `labels_${vol}`;
    const v = manifest.volumes[key];
    if (!v) continue;
    const p = join(DATA, v.file);
    const u8 = new Uint8Array(gunzipSync(readFileSync(p)));   // fresh buffer: the uint16 view needs offset 0
    const arr: Uint8Array | Uint16Array = v.dtype === 'uint16' ? new Uint16Array(u8.buffer) : u8;
    let n = 0;
    for (let i = 0; i < arr.length; i++) if (ids.has(arr[i]!)) { arr[i] = 0; n++; }
    const gz = gzipSync(Buffer.from(u8.buffer), { level: 9 });
    writeFileSync(p, gz);
    v.bytes_gz = gz.length;
    zeroed[key] = n;
  }
  writeFileSync(join(DATA, 'manifest.json'), JSON.stringify(manifest, null, 1));
}

// 4c. delete everything the public manifest does not reference
const walk = (dir: string, out: string[] = []): string[] => {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out); else out.push(p);
  }
  return out;
};
let removed = 0, removedBytes = 0, keptBytes = 0;
for (const p of walk(DATA)) {
  const rel = relative(DATA, p).split(sep).join('/');
  if (keep.has(rel)) { keptBytes += statSync(p).size; continue; }
  removedBytes += statSync(p).size; removed++;
  rmSync(p);
}
// prune the directories the deletions emptied
const prune = (dir: string): void => {
  for (const name of readdirSync(dir)) { const p = join(dir, name); if (statSync(p).isDirectory()) prune(p); }
  if (dir !== DATA && !readdirSync(dir).length) rmSync(dir, { recursive: true });
};
prune(DATA);
for (const f of keep) if (!existsSync(join(DATA, f))) throw new Error(`${f} is referenced by the public manifest but is not in the build (looked in ${dirname(join(DATA, f))})`);

const t = exclusions.totals;
console.log(`dist/data: kept ${manifest.meshes.length} meshes and ${Object.keys(manifest.volumes).length} volumes (${(keptBytes / 1e6).toFixed(1)} MB); removed ${removed} files (${(removedBytes / 1e6).toFixed(1)} MB)`);
console.log(`excluded: ${t.meshes} meshes (${(t.meshBytes / 1e6).toFixed(1)} MB), ${t.volumes} volumes (${(t.volumeBytes / 1e6).toFixed(1)} MB), ${t.grids} grid(s), ${t.licenses} licences, ${t.sources} sources`);
for (const [k, n] of Object.entries(zeroed)) console.log(`${k}: ${n.toLocaleString()} voxels of excluded atlases zeroed`);

// the code licence sits next to the build so a published dist/ is self-describing
for (const f of ['LICENSE', 'NOTICE']) if (existsSync(join(ROOT, f))) copyFileSync(join(ROOT, f), join(OUT, f));

// ---- 5. verify
if (!args.has('--skip-check')) {
  step('check-public');
  run(process.execPath, ['scripts/check-public.ts', 'dist']);
}

interface Manifest {
  edition?: string;
  meshes: { id: string; file: string; lod?: { file: string } }[];
  volumes: Record<string, { file: string; dtype: string; lut?: string; bytes_gz?: number }>;
  licenses: Record<string, { text: string }>;
}
interface Exclusions {
  meshes: { id: string; files: string[] }[];
  volumes: { key: string; file: string; lut?: string }[];
  totals: { meshes: number; meshBytes: number; volumes: number; volumeBytes: number; grids: number; licenses: number; sources: number };
}
interface LabelsJson {
  volumes: Record<string, { file: string }>;
  lut: Record<string, Record<string, { meshId: string }>>;
  byMesh: Record<string, unknown>;
}
