// Verifies public/data: every manifest mesh decodes (meshopt), triangle counts, bbox/centroid sanity, label ids exist.
// usage: node scripts/check-data.ts [--deep] [--manifest <file>] [--all] [glb paths...]
//   --manifest  check this manifest instead of public/data/manifest.json. A bare name resolves inside
//               public/data (manifest.public.json), a path anywhere (dist-public/data/manifest.json); the data
//               directory is taken from wherever the manifest sits.
//   --all       check every manifest in public/data (private, then public if it has been built).
import { readFileSync, existsSync, statSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { resolve, dirname } from 'node:path';
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { MeshoptDecoder } from 'meshoptimizer';

const DATA_DEFAULT = resolve(process.cwd(), 'public/data');
let DATA = DATA_DEFAULT;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ 'meshopt.decoder': MeshoptDecoder });

interface GlbInfo { name: string; verts: number; tris: number; normals: boolean; min: number[]; max: number[]; ext: string[] }

async function inspect(file: string): Promise<GlbInfo> {
  const doc = await io.read(file);
  const root = doc.getRoot();
  const ext = root.listExtensionsUsed().map((e) => e.extensionName);
  const meshes = root.listMeshes();
  if (meshes.length !== 1) throw new Error(`${file}: expected 1 mesh, got ${meshes.length}`);
  const prims = meshes[0]!.listPrimitives();
  if (prims.length !== 1) throw new Error(`${file}: expected 1 primitive, got ${prims.length}`);
  const prim = prims[0]!;
  const pos = prim.getAttribute('POSITION')!;
  const idx = prim.getIndices();
  // KHR_mesh_quantization stores normalised positions; the node matrix dequantises them
  const node = root.listNodes().find((n) => n.getMesh() === meshes[0]);
  const M = node ? node.getWorldMatrix() : [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
  const min = [Infinity, Infinity, Infinity]; const max = [-Infinity, -Infinity, -Infinity]; const el = [0, 0, 0];
  for (let i = 0; i < pos.getCount(); i++) {
    pos.getElement(i, el);
    const x = M[0]! * el[0]! + M[4]! * el[1]! + M[8]! * el[2]! + M[12]!;
    const y = M[1]! * el[0]! + M[5]! * el[1]! + M[9]! * el[2]! + M[13]!;
    const z = M[2]! * el[0]! + M[6]! * el[1]! + M[10]! * el[2]! + M[14]!;
    const w = [x, y, z];
    for (let k = 0; k < 3; k++) { min[k] = Math.min(min[k]!, w[k]!); max[k] = Math.max(max[k]!, w[k]!); }
  }
  return { name: meshes[0]!.getName(), verts: pos.getCount(), tris: idx ? idx.getCount() / 3 : 0, normals: !!prim.getAttribute('NORMAL'), min, max, ext };
}

async function check(manifestPath: string): Promise<number> {
  DATA = dirname(manifestPath);
  const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
  const labels = JSON.parse(readFileSync(resolve(DATA, 'volumes/labels.json'), 'utf8'));
  let errors = 0; let bytes = 0; let tris = 0;
  const meshIds = new Set<string>();
  for (const m of manifest.meshes) {
    if (meshIds.has(m.id)) { console.error(`duplicate id ${m.id}`); errors++; }
    meshIds.add(m.id);
    const f = resolve(DATA, m.file);
    if (!existsSync(f)) { console.error(`missing file ${m.file}`); errors++; continue; }
    bytes += statSync(f).size; tris += m.triangles;
    try {
      const info = await inspect(f);
      if (Math.abs(info.tris - m.triangles) > 2) { console.error(`${m.id}: triangles ${info.tris} != manifest ${m.triangles}`); errors++; }
      const c = m.centroid as number[];
      for (let k = 0; k < 3; k++) if (c[k]! < info.min[k]! - 1 || c[k]! > info.max[k]! + 1) { console.error(`${m.id}: centroid outside bbox`); errors++; break; }
      if (info.min[0]! < -110 || info.max[0]! > 110 || info.min[1]! < -150 || info.max[1]! > 110 || info.min[2]! < -100 || info.max[2]! > 130) { if (m.alignment === 'native-mni' || m.alignment === 'nlin6-identity') { console.error(`${m.id}: outside MNI FOV ${info.min} ${info.max}`); errors++; } else console.warn(`${m.id}: extends beyond the MNI volume (registered source)`); }
    } catch (e) { console.error(`${m.id}: ${(e as Error).message}`); errors++; }
    for (const [vol, list] of Object.entries(m.labels as Record<string, number[]>)) {
      for (const id of list) if (!labels.lut[vol]?.[String(id)]) { console.error(`${m.id}: label ${vol}:${id} missing in labels.json`); errors++; }
    }
    if (!manifest.licenses[m.license]) { console.error(`${m.id}: unknown licence ${m.license}`); errors++; }
  }
  // volumes: the payload must gunzip to exactly shape[0]*shape[1]*shape[2] samples of the declared dtype
  type Vol = { file: string; dtype: string; shape: number[]; bytes_raw?: number; space?: string; spacing?: number[]; affine_ras?: number[][]; lut?: string; edition?: string };
  let volBytes = 0;
  const spineIdsInVolume = new Set<number>();
  for (const [k, v] of Object.entries(manifest.volumes as Record<string, Vol>)) {
    const f = resolve(DATA, v.file);
    if (!existsSync(f)) { console.error(`volume ${k} missing ${v.file}`); errors++; continue; }
    volBytes += statSync(f).size;
    const buf = readFileSync(f);
    const raw = buf[0] === 0x1f && buf[1] === 0x8b ? gunzipSync(buf) : buf;
    const expect = v.shape[0]! * v.shape[1]! * v.shape[2]! * (v.dtype === 'uint16' ? 2 : 1);
    if (raw.length !== expect) { console.error(`volume ${k}: ${raw.length} bytes, expected ${expect} for ${v.shape} ${v.dtype}`); errors++; }
    if (v.bytes_raw !== undefined && v.bytes_raw !== expect) { console.error(`volume ${k}: bytes_raw ${v.bytes_raw} != ${expect}`); errors++; }
    if (k === 'labels_spine') for (const b of raw) if (b) spineIdsInVolume.add(b);
    // volumes off the brain grid must carry their own affine and match the grid they name
    const cordGrid = manifest.grids?.cord;
    if (v.space === 'cord') {
      if (!cordGrid) { console.error(`volume ${k}: space "cord" but manifest.grids.cord is missing`); errors++; }
      else {
        if (JSON.stringify(v.shape) !== JSON.stringify(cordGrid.shape)) { console.error(`volume ${k}: shape ${v.shape} != grids.cord ${cordGrid.shape}`); errors++; }
        if (JSON.stringify(v.affine_ras) !== JSON.stringify(cordGrid.affine_ras)) { console.error(`volume ${k}: affine != grids.cord affine`); errors++; }
      }
    } else if (JSON.stringify(v.shape) !== JSON.stringify(manifest.grid.shape) && !v.spacing) {
      console.error(`volume ${k}: shape ${v.shape} is neither the brain grid nor a declared second grid`); errors++;
    }
  }
  // the spinal-level LUT: every id in labels_spine.u8.bin must resolve to a level whose cord segment block is
  // a real mesh, so a level painted on a slice can be clicked into a selection. Both editions ship one -- the
  // private edition's from atlas-pam50, the public edition's from atlas-spine-generic, which paints only the
  // levels it measured on the nerve rootlets but keeps the same 1..30 id space and the same LUT shape.
  const spineVol = (manifest.volumes as Record<string, Vol>)['labels_spine'];
  if (spineVol) {
    const expectLut = spineVol.edition === 'public' ? 'volumes/labels_spine_public.json' : 'volumes/labels_spine.json';
    if (spineVol.lut !== expectLut) { console.error(`volume labels_spine: lut is ${spineVol.lut}, expected ${expectLut}`); errors++; }
    const f = resolve(DATA, spineVol.lut ?? 'volumes/labels_spine.json');
    if (!existsSync(f)) { console.error(`labels_spine.json missing (${spineVol.lut})`); errors++; }
    else {
      type Level = { name: string; region: string; regionName: string; meshId: string; structureId: string; colour: string; zMm?: number[] };
      const sj = JSON.parse(readFileSync(f, 'utf8')) as { regions: Record<string, { name: string; meshId: string; levels: string[] }>; lut: Record<string, Level> };
      const ids = Object.keys(sj.lut).map(Number).sort((a, b) => a - b);
      if (ids.length !== 30 || ids[0] !== 1 || ids[29] !== 30) { console.error(`labels_spine.json: expected ids 1..30, got ${ids.length} (${ids[0]}..${ids[ids.length - 1]})`); errors++; }
      for (let n = 1; n < ids.length; n++) if (ids[n] !== ids[n - 1]! + 1) { console.error(`labels_spine.json: id gap at ${ids[n - 1]} -> ${ids[n]}`); errors++; break; }
      const names = new Set<string>(); const colours = new Set<string>();
      let prevTop = Infinity;
      for (const id of ids) {
        const e = sj.lut[String(id)]!;
        if (!/^[CTLS]\d+$/.test(e.name)) { console.error(`labels_spine.json ${id}: odd level name ${e.name}`); errors++; }
        if (names.has(e.name)) { console.error(`labels_spine.json: duplicate level ${e.name}`); errors++; }
        names.add(e.name);
        if (!/^#[0-9A-Fa-f]{6}$/.test(e.colour)) { console.error(`labels_spine.json ${e.name}: bad colour ${e.colour}`); errors++; }
        if (colours.has(e.colour)) { console.error(`labels_spine.json ${e.name}: colour ${e.colour} repeats`); errors++; }
        colours.add(e.colour);
        if (!sj.regions[e.region]) { console.error(`labels_spine.json ${e.name}: unknown region ${e.region}`); errors++; }
        else if (sj.regions[e.region]!.meshId !== e.meshId) { console.error(`labels_spine.json ${e.name}: meshId ${e.meshId} != region ${e.region}`); errors++; }
        if (!meshIds.has(e.meshId)) { console.error(`labels_spine.json ${e.name}: meshId ${e.meshId} is not a manifest mesh`); errors++; }
        // levels run rostral -> caudal, so each level's top must sit at or below the previous one's
        if (e.zMm) { if (e.zMm[1]! > prevTop + 0.5) { console.error(`labels_spine.json ${e.name}: z ${e.zMm} is above the level before it`); errors++; } prevTop = e.zMm[1]!; }
      }
      for (const id of spineIdsInVolume) if (!sj.lut[String(id)]) { console.error(`labels_spine.u8.bin: id ${id} has no LUT entry`); errors++; }
      if (!spineIdsInVolume.size) { console.error('labels_spine.u8.bin: no level is painted anywhere in the volume'); errors++; }
      console.log(`spinal levels: ${ids.length} in ${Object.keys(sj.regions).length} regions, ${spineIdsInVolume.size} present in the volume`
        + (spineIdsInVolume.size < ids.length ? ` (${[...spineIdsInVolume].sort((a, b) => a - b).map((i) => sj.lut[String(i)]!.name).join(', ')})` : ''));
    }
  }
  if (manifest.grids?.cord) {
    const g = manifest.grids.cord;
    if (!manifest.licenses[g.license]) { console.error(`grids.cord: unknown licence ${g.license}`); errors++; }
    if (!manifest.sources[g.source]) { console.error(`grids.cord: unknown source ${g.source}`); errors++; }
    // the cord grid must actually reach the spinal cord meshes it is reformatted onto.
    const zmin = g.origin_ras[2]; const zmax = zmin + (g.shape[2] - 1) * g.spacing[2];
    // Both editions must reach up to the MNI floor (-78 mm), so the brain MRI and the cord MRI meet on a
    // sagittal slice. Below that they differ by construction: the private edition's template is the whole
    // cord past the conus, while the public edition's is built from an openly licensed source that only
    // images the cervical and upper thoracic cord, so it only has to reach the upper thoracic levels.
    const floor = manifest.edition === 'public' ? -200 : -400;
    if (zmax < -78) { console.error(`grids.cord: z range ${zmin}..${zmax} does not reach the MNI floor at -78 mm`); errors++; }
    if (zmin > floor) { console.error(`grids.cord: z range ${zmin}..${zmax} stops above ${floor} mm (${manifest.edition ?? 'private'} edition)`); errors++; }
    const cov: string[] = g.coverage?.spinal_levels ?? [];
    console.log(`cord grid ${g.shape.join('x')} at ${g.spacing[0]} mm, z ${zmin.toFixed(1)}..${zmax.toFixed(1)} mm, source ${g.source}`
      + (g.edition ? ` (${g.edition} edition${cov.length ? `, ${cov[0]}-${cov[cov.length - 1]}` : ''})` : ''));
  }
  console.log(`volumes: ${(volBytes / 1e6).toFixed(2)} MB shipped`);
  console.log(`${manifestPath.replace(process.cwd() + '/', '')} (${manifest.edition ?? 'private'} edition): ${manifest.meshes.length} meshes, ${(bytes / 1e6).toFixed(1)} MB, ${(tris / 1e6).toFixed(2)} M triangles, ${errors} error(s)`);
  return errors;
}

async function main() {
  const args = process.argv.slice(2);
  const files = args.filter((a) => a.endsWith('.glb'));
  if (files.length) {
    for (const f of files) { const i = await inspect(f); console.log(f, JSON.stringify(i)); }
    return;
  }
  const at = args.indexOf('--manifest');
  const wanted = at >= 0 && args[at + 1] ? [args[at + 1]!] : args.includes('--all') ? ['manifest.json', 'manifest.public.json'] : ['manifest.json'];
  let errors = 0;
  for (const w of wanted) {
    const p = w.includes('/') ? resolve(process.cwd(), w) : resolve(DATA_DEFAULT, w);
    if (!existsSync(p)) {
      if (args.includes('--all')) { console.log(`skipping ${w}: not built`); continue; }
      console.error(`missing manifest ${p}`); process.exit(1);
    }
    errors += await check(p);
  }
  if (errors) process.exit(1);
}
main();
