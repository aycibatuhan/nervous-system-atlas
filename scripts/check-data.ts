// Verifies public/data: every manifest mesh decodes (meshopt), triangle counts, bbox/centroid sanity, label ids exist.
// usage: node scripts/check-data.ts [--deep] [glb paths...]
import { readFileSync, existsSync, statSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { resolve } from 'node:path';
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { MeshoptDecoder } from 'meshoptimizer';

const DATA = resolve(process.cwd(), 'public/data');
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

async function main() {
  const args = process.argv.slice(2);
  const files = args.filter((a) => a.endsWith('.glb'));
  if (files.length) {
    for (const f of files) { const i = await inspect(f); console.log(f, JSON.stringify(i)); }
    return;
  }
  const manifest = JSON.parse(readFileSync(resolve(DATA, 'manifest.json'), 'utf8'));
  const labels = JSON.parse(readFileSync(resolve(DATA, 'volumes/labels.json'), 'utf8'));
  let errors = 0; let bytes = 0; let tris = 0;
  const ids = new Set<string>();
  for (const m of manifest.meshes) {
    if (ids.has(m.id)) { console.error(`duplicate id ${m.id}`); errors++; }
    ids.add(m.id);
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
  type Vol = { file: string; dtype: string; shape: number[]; bytes_raw?: number; space?: string; spacing?: number[]; affine_ras?: number[][] };
  let volBytes = 0;
  for (const [k, v] of Object.entries(manifest.volumes as Record<string, Vol>)) {
    const f = resolve(DATA, v.file);
    if (!existsSync(f)) { console.error(`volume ${k} missing ${v.file}`); errors++; continue; }
    volBytes += statSync(f).size;
    const buf = readFileSync(f);
    const raw = buf[0] === 0x1f && buf[1] === 0x8b ? gunzipSync(buf) : buf;
    const expect = v.shape[0]! * v.shape[1]! * v.shape[2]! * (v.dtype === 'uint16' ? 2 : 1);
    if (raw.length !== expect) { console.error(`volume ${k}: ${raw.length} bytes, expected ${expect} for ${v.shape} ${v.dtype}`); errors++; }
    if (v.bytes_raw !== undefined && v.bytes_raw !== expect) { console.error(`volume ${k}: bytes_raw ${v.bytes_raw} != ${expect}`); errors++; }
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
  if (manifest.grids?.cord) {
    const g = manifest.grids.cord;
    if (!manifest.licenses[g.license]) { console.error(`grids.cord: unknown licence ${g.license}`); errors++; }
    if (!manifest.sources[g.source]) { console.error(`grids.cord: unknown source ${g.source}`); errors++; }
    // the cord grid must actually reach the spinal cord meshes it is reformatted onto
    const zmin = g.origin_ras[2]; const zmax = zmin + (g.shape[2] - 1) * g.spacing[2];
    // it must reach up to the MNI floor (-78 mm, so the two MRIs meet) and down past the conus
    if (zmax < -78 || zmin > -400) { console.error(`grids.cord: z range ${zmin}..${zmax} does not span the foramen magnum to the conus`); errors++; }
    console.log(`cord grid ${g.shape.join('x')} at ${g.spacing[0]} mm, z ${zmin.toFixed(1)}..${zmax.toFixed(1)} mm, source ${g.source}`);
  }
  console.log(`volumes: ${(volBytes / 1e6).toFixed(2)} MB shipped`);
  console.log(`${manifest.meshes.length} meshes, ${(bytes / 1e6).toFixed(1)} MB, ${(tris / 1e6).toFixed(2)} M triangles, ${errors} error(s)`);
  if (errors) process.exit(1);
}
main();
