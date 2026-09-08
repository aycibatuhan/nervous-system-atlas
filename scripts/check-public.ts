// Gate for the public edition: proves that a built dist-public/ carries nothing we may not redistribute.
//   node scripts/check-public.ts [dir=dist-public]
//
// It fails on: an excluded mesh id anywhere in the build; a restricted licence id or source id in the data; a
// mesh/volume/licence file that should have been dropped but is still on disk; a data file the public manifest
// does not reference; and the names of the restricted datasets ("Harvard-Oxford", "Diedrichsen", "Brainstem
// Navigator", "PAM50") in the manifest or the volume metadata.
//
// The id and name scans run over dist-public/data (the shipped data), where a hit means leaked atlas data. The
// app bundle is scanned for excluded mesh ids only: it names licence ids and datasets in code and comments
// (src/ui/sourceLine.ts labels every licence; the cord toggle says "PAM50 spinal cord template"), which is
// vocabulary, not data.
//
// Ids are matched on whole tokens, never as bare substrings: `"<id>"` (a quoted id) or `/<id>` followed by
// something that is not another id character. The public edition ships ids that *extend* an excluded one --
// `spinal-segment-cervical-vert` for the excluded `spinal-segment-cervical`, `raphe-magnus-anchor` for the
// excluded `raphe-magnus` -- and a bare substring test would fail on their file paths.
//
// Deliberate, reported exceptions, all for ids that name both an excluded mesh and an authored entry:
//  * inside content.json / search-index.json (authored prose): filum-terminale, the cord segment blocks and
//    the midline raphe nuclei. The entry keeps its own id; the structural pass proves no mesh field points
//    at them.
//  * inside data/manifest.json, the quoted form only: a shipped mesh names its content entry in
//    `structureId`, and for those structures that id is also the excluded mesh's id. The structural pass
//    above (manifest.meshes carries no excluded id) is what proves the mesh itself is gone; file paths are
//    still matched in full.
//  * the dataset names occur as citations and teaching notes ("the group probability map of the Brainstem
//    Navigator..."). Naming a dataset is attribution, not redistribution.
//  * a bibliography entry is tagged "pam50", which happens to equal a restricted source id. The content bundle
//    has no source or licence fields at all, so an id can only appear there as a word in prose.
import { readFileSync, existsSync, readdirSync, statSync } from 'node:fs';
import { resolve, join, relative, sep } from 'node:path';

const ROOT = resolve(import.meta.dirname, '..');
const DIR = resolve(ROOT, process.argv[2] ?? 'dist-public');
const DATA = join(DIR, 'data');

/** Dataset names that must not survive in the manifest or volume metadata. Mirrors NAME_STRINGS in manifest.py. */
const NAME_STRINGS = ['Brainstem Navigator', 'BrainstemNavigator', 'Harvard-Oxford', 'Diedrichsen', 'PAM50'];
const TEXT_EXT = ['.json', '.js', '.mjs', '.css', '.html', '.txt', '.map'];
const PROSE_FILES = ['data/content.json', 'data/content.tr.json', 'data/search-index.json'];

const fail: string[] = [];
const note: string[] = [];
const bad = (m: string) => fail.push(m);

// Whole-token id matching. `spinal-segment-cervical-vert` and `raphe-magnus-anchor` are public ids that
// begin with an excluded one, so an id only counts as present when nothing that could continue it follows.
const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const quotedId = (text: string, id: string) => text.includes(`"${id}"`);
const pathId = (text: string, id: string) => new RegExp(`/${esc(id)}(?![A-Za-z0-9_-])`).test(text);

if (!existsSync(DATA)) { console.error(`check-public: ${DIR} has no data/ — run npm run build:public first`); process.exit(1); }

// ---- what must not be there, straight from the pipeline's own exclusion record
type Exclusions = {
  meshes: { id: string; files: string[]; bytes: number }[];
  volumes: { key: string; file: string; lut?: string }[];
  licenses: Record<string, string>;
  sources: Record<string, { license: string }>;
  grids: Record<string, unknown>;
};
const exPath = resolve(ROOT, 'public/data/manifest.public.exclusions.json');
if (!existsSync(exPath)) { console.error('check-public: public/data/manifest.public.exclusions.json is missing — run `atlas-manifest --public` first'); process.exit(1); }
const ex = JSON.parse(readFileSync(exPath, 'utf8')) as Exclusions;
const exMeshIds = new Set(ex.meshes.map((m) => m.id));
const exLicenceIds = new Set(Object.keys(ex.licenses));
const exSourceIds = new Set(Object.keys(ex.sources));
const exFiles = new Set([...ex.meshes.flatMap((m) => m.files), ...ex.volumes.flatMap((v) => [v.file, ...(v.lut ? [v.lut] : [])]), ...Array.from(exLicenceIds, (l) => `licenses/${l}.txt`)]);

// ---- the shipped manifest decides which data files may exist at all
type Manifest = {
  edition?: string;
  meshes: { id: string; file: string; license: string; source: string; nc?: boolean; lod?: { file: string } }[];
  volumes: Record<string, { file: string; lut?: string; space?: string }>;
  grids?: Record<string, { license: string }>;
  licenses: Record<string, { text: string; nc?: boolean; noRedistribution?: boolean }>;
  sources: Record<string, { license: string }>;
};
const mPath = join(DATA, 'manifest.json');
if (!existsSync(mPath)) { console.error(`check-public: ${mPath} is missing`); process.exit(1); }
const man = JSON.parse(readFileSync(mPath, 'utf8')) as Manifest;

if (man.edition !== 'public') bad(`data/manifest.json declares edition "${man.edition ?? '(none)'}" — expected "public"`);
for (const [id, l] of Object.entries(man.licenses)) if (l.nc || l.noRedistribution) bad(`manifest.licenses.${id} is still marked nc / noRedistribution`);
for (const m of man.meshes) {
  if (exMeshIds.has(m.id)) bad(`manifest.meshes still contains the excluded mesh ${m.id}`);
  if (m.nc) bad(`mesh ${m.id} is flagged nc`);
  if (!man.licenses[m.license]) bad(`mesh ${m.id} references a licence that is not in the manifest (${m.license})`);
  if (!man.sources[m.source]) bad(`mesh ${m.id} references a source that is not in the manifest (${m.source})`);
}
for (const [k, v] of Object.entries(man.volumes)) if (v.space && !man.grids?.[v.space]) bad(`volume ${k} sits on the dropped grid "${v.space}"`);

const allowed = new Set<string>(['manifest.json', 'content.json', 'content.tr.json', 'search-index.json', 'LICENSE']);
for (const m of man.meshes) { allowed.add(m.file); if (m.lod) allowed.add(m.lod.file); }
for (const v of Object.values(man.volumes)) { allowed.add(v.file); if (v.lut) allowed.add(v.lut); }
for (const l of Object.values(man.licenses)) allowed.add(l.text);

// ---- ids that name both an excluded mesh and an authored entry (the entry keeps its own id)
const contentPath = join(DATA, 'content.json');
const content = existsSync(contentPath) ? JSON.parse(readFileSync(contentPath, 'utf8')) as Record<string, Record<string, unknown>> : null;
const entryIds = new Set<string>();
if (content) for (const k of ['structures', 'pathways', 'syndromes', 'glossary', 'quiz', 'topics']) for (const id of Object.keys(content[k] ?? {})) entryIds.add(id);
const sharedIds = new Set(Array.from(exMeshIds).filter((id) => entryIds.has(id)));

// content.json (and the Turkish bundle, the same entries translated) must not *point* at an excluded mesh from any field that holds mesh ids
const trPath = join(DATA, 'content.tr.json');
const contentTr = existsSync(trPath) ? JSON.parse(readFileSync(trPath, 'utf8')) as Record<string, Record<string, unknown>> : null;
for (const [bundleName, bundle] of [['content.json', content], ['content.tr.json', contentTr]] as const) if (bundle) {
  const content = bundle;
  const named = new Set<string>();
  const walk = (v: unknown): void => {
    if (Array.isArray(v)) { for (const x of v) walk(x); return; }
    if (!v || typeof v !== 'object') return;
    const o = v as Record<string, unknown>;
    if (typeof o['meshId'] === 'string') named.add(o['meshId']);
    for (const key of ['meshIds', 'highlightOnReveal']) if (Array.isArray(o[key])) for (const x of o[key] as unknown[]) if (typeof x === 'string') named.add(x);
    for (const x of Object.values(o)) walk(x);
  };
  walk(content);
  for (const id of Object.keys(content['meshToStructure'] ?? {})) named.add(id);
  for (const id of named) if (exMeshIds.has(id)) bad(`data/${bundleName} still points at the excluded mesh ${id}`);
}

// ---- walk the build
const walkFiles = (dir: string, out: string[] = []): string[] => {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walkFiles(p, out); else out.push(p);
  }
  return out;
};
const files = walkFiles(DIR);
let dataBytes = 0;
for (const p of files) {
  const rel = relative(DIR, p).split(sep).join('/');
  const inData = rel.startsWith('data/');
  const dataRel = inData ? rel.slice('data/'.length) : '';
  if (inData) {
    dataBytes += statSync(p).size;
    if (exFiles.has(dataRel)) bad(`${rel} is an excluded file and must not ship`);
    if (!allowed.has(dataRel)) bad(`${rel} is not referenced by the public manifest`);
  }
  const base = rel.slice(rel.lastIndexOf('/') + 1);
  if (!TEXT_EXT.some((e) => rel.endsWith(e)) && base !== 'LICENSE' && base !== 'NOTICE') continue;
  const text = readFileSync(p, 'utf8');
  const prose = PROSE_FILES.includes(rel);
  const isManifest = rel === 'data/manifest.json';
  for (const id of exMeshIds) {
    // a shared id in prose is the authored entry; in the manifest it is a shipped mesh's structureId
    const quotedOk = sharedIds.has(id) && (prose || isManifest);
    if (!quotedOk && quotedId(text, id)) bad(`${rel} mentions the excluded mesh id ${id}`);
    if (pathId(text, id)) bad(`${rel} references the excluded mesh file ${id}`);
  }
  if (!inData) continue;                                            // the app bundle names licences in code, not data
  for (const id of exLicenceIds) if (text.includes(`"${id}"`) || text.includes(`${id}.txt`)) bad(`${rel} mentions the restricted licence ${id}`);
  for (const id of exSourceIds) {
    if (!text.includes(`"${id}"`)) continue;
    if (prose) { note.push(`${rel} contains the word "${id}" in authored prose (the bundle has no source fields)`); continue; }
    bad(`${rel} mentions the restricted source ${id}`);
  }
  for (const n of NAME_STRINGS) {
    if (!text.includes(n)) continue;
    if (prose) { note.push(`${rel} names "${n}" in authored prose (citation / teaching note, not data)`); continue; }
    bad(`${rel} contains the string "${n}"`);
  }
}
for (const f of allowed) if (!existsSync(join(DATA, f))) bad(`data/${f} is referenced by the public manifest but missing from the build`);

// ---- report
for (const n of note) console.log(`note  ${n}`);
for (const f of fail) console.error(`FAIL  ${f}`);
console.log(`check-public: ${DIR} — ${man.meshes.length} meshes, ${Object.keys(man.volumes).length} volumes, ${Object.keys(man.licenses).length} licences, ${Object.keys(man.sources).length} sources, ${(dataBytes / 1e6).toFixed(1)} MB of data`);
console.log(`check-public: excluded ${exMeshIds.size} meshes, ${ex.volumes.length} volumes, ${exLicenceIds.size} licences, ${exSourceIds.size} sources; ${sharedIds.size} shared ids kept as authored entries; ${note.length} prose mention(s)`);
if (fail.length) { console.error(`check-public: ${fail.length} problem(s) — this build must not be published`); process.exit(1); }
console.log('check-public: clean');
