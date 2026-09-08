// Content build: validate every entry (zod), check cross-links against the manifest, run quality rules,
// render Markdown fields to HTML and emit the bundles in public/data/.
//   node scripts/content/build.ts [--validate-only] [--report] [--strict] [--private]
//
// By default it bundles against public/data/manifest.json -- the PUBLIC edition -- and writes content.json,
// search-index.json and content.tr.json under those plain names, so the shareable bundle is the one every
// other tool picks up by default. Mesh ids the public edition does not ship are dropped from meshIds /
// meshToStructure, and an MniRef that pointed at one keeps its MNI coordinate but loses the mesh id.
//
// --private bundles against public/data/manifest.private.json instead and writes content.private.json,
// search-index.private.json and content.tr.private.json. It only means anything on a machine that has built
// the restricted data. The authored files under content/ are never touched by either.
import { readFileSync, readdirSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { marked } from 'marked';
import { Entry, KIND_DIRS, BibEntry } from '../../content/schema/index.ts';
import { checkPlagiarism } from './plagiarism.ts';

const ROOT = resolve(import.meta.dirname, '../..');
const DATA_DIR = join(ROOT, 'content/data');
const OUT = join(ROOT, 'public/data');
const args = new Set(process.argv.slice(2));
const strict = args.has('--strict');
const privateEdition = args.has('--private') || process.env['ATLAS_EDITION'] === 'private';

interface Problem { file: string; msg: string; level: 'error' | 'warn' }
const problems: Problem[] = [];
const err = (file: string, msg: string) => problems.push({ file, msg, level: 'error' });
const warn = (file: string, msg: string) => problems.push({ file, msg, level: 'warn' });

// open-access bibliography: one file per source in content/bibliography/
const BIB_DIR = join(ROOT, 'content/bibliography');
const bibliography: Record<string, BibEntry> = {};
if (existsSync(BIB_DIR)) for (const f of readdirSync(BIB_DIR).filter((x) => x.endsWith('.json')).sort()) {
  const file = `content/bibliography/${f}`;
  try {
    const parsed = BibEntry.safeParse(JSON.parse(readFileSync(join(BIB_DIR, f), 'utf8')));
    if (!parsed.success) { for (const i of parsed.error.issues) problems.push({ file, msg: `${i.path.join('.')}: ${i.message}`, level: 'error' }); continue; }
    if (parsed.data.id !== f.replace(/\.json$/, '')) problems.push({ file, msg: `id ${parsed.data.id} != file name`, level: 'error' });
    bibliography[parsed.data.id] = parsed.data;
  } catch (e) { problems.push({ file, msg: `invalid JSON: ${(e as Error).message}`, level: 'error' }); }
}
type MiniManifest = { meshes: { id: string; structureId: string; centroid: number[] }[] };
const readManifest = (name: string): MiniManifest | null => {
  const p = join(OUT, name);
  return existsSync(p) ? JSON.parse(readFileSync(p, 'utf8')) as MiniManifest : null;
};
// Validation runs against the UNION of the two manifests, so the authored JSON is judged on its own terms and
// an entry never becomes "wrong" just because one edition drops its mesh. The editions do not ship the same
// cortex — the private one has the Harvard-Oxford gyri, the public one the CerebrA/DKT parcels standing in for
// them — so a gyrus entry legitimately names mesh ids from both.
const publicManifest = readManifest('manifest.json') ?? { meshes: [] };
const privateManifest = readManifest('manifest.private.json');
if (privateEdition && !privateManifest) { console.error('--private: public/data/manifest.private.json is missing — this build has no restricted data, so there is no private edition'); process.exit(1); }
const allMeshes = [...publicManifest.meshes, ...(privateManifest?.meshes ?? [])];
// Both editions' mesh ids are known only on a machine that has built both. Elsewhere -- a public clone, which
// is the normal case -- an id from the other edition is indistinguishable from a typo, so the mesh-id check
// reports rather than fails. See `unknownMeshId` below.
const bothEditions = privateManifest !== null && publicManifest.meshes.length > 0;
const meshIds = new Set(allMeshes.map((m) => m.id));
const meshCentroid = new Map(allMeshes.map((m) => [m.id, m.centroid] as const));
const meshStructure = new Map(allMeshes.map((m) => [m.id, m.structureId] as const));
// The bundle, though, may only mention meshes that ship in THIS edition.
const shippedIds = new Set((privateEdition ? privateManifest!.meshes : publicManifest.meshes).map((m) => m.id));
const droppedIds = new Set(Array.from(meshIds).filter((id) => !shippedIds.has(id)));
const ships = (id: string): boolean => !droppedIds.has(id);


// ---- load
const entries: { file: string; e: Entry }[] = [];
for (const [kind, dir] of Object.entries(KIND_DIRS)) {
  const d = join(DATA_DIR, dir);
  if (!existsSync(d)) continue;
  for (const f of readdirSync(d).filter((x) => x.endsWith('.json')).sort()) {
    const file = `content/data/${dir}/${f}`;
    let raw: unknown;
    try { raw = JSON.parse(readFileSync(join(d, f), 'utf8')); } catch (e) { err(file, `invalid JSON: ${(e as Error).message}`); continue; }
    const parsed = Entry.safeParse(raw);
    if (!parsed.success) { for (const i of parsed.error.issues) err(file, `${i.path.join('.')}: ${i.message}`); continue; }
    if (parsed.data.kind !== kind) err(file, `kind ${parsed.data.kind} in ${dir}/`);
    if (parsed.data.id !== f.replace(/\.json$/, '')) err(file, `id ${parsed.data.id} != file name`);
    entries.push({ file, e: parsed.data });
  }
}
const byId = new Map(entries.map((x) => [x.e.id, x.e]));
const dup = new Set<string>();
for (const { file, e } of entries) { if (dup.has(e.id)) err(file, `duplicate id ${e.id}`); dup.add(e.id); }

// ---- helpers
const WORD = /[A-Za-z][A-Za-z'’-]*/g;
const words = (s: unknown): number => typeof s === 'string' ? (s.match(WORD) ?? []).length : 0;
function proseOf(e: Entry): string[] {
  const out: string[] = [];
  const walk = (v: unknown): void => {
    if (typeof v === 'string') { if (v.length > 30) out.push(v); }
    else if (Array.isArray(v)) v.forEach(walk);
    else if (v && typeof v === 'object') for (const [k, x] of Object.entries(v)) if (!['id', 'kind', 'meshIds', 'citations', 'status', 'tags'].includes(k)) walk(x);
  };
  walk(e);
  return out;
}
const refIds = (e: Entry): string[] => {
  const ids: string[] = [];
  const grab = (v: unknown, key: string) => { if (typeof v === 'string') ids.push(v); else if (Array.isArray(v)) for (const x of v) if (typeof x === 'string') ids.push(x); else if (x && typeof x === 'object' && key in x) ids.push(String((x as Record<string, unknown>)[key])); };
  const r = e as unknown as Record<string, unknown>;
  if (e.kind === 'structure' || e.kind === 'cranial-nerve') {
    grab((r['connections'] as Record<string, unknown>)?.['pathways'], '');
    grab((r['clinical'] as Record<string, unknown>)?.['syndromes'], '');
    if (r['parent']) ids.push(String(r['parent']));
  }
  if (e.kind === 'syndrome') { grab((r['localisation'] as Record<string, unknown>)['structures'], ''); for (const d of e.deficits) if (d.substrate) ids.push(d.substrate); }
  if (e.kind === 'pathway') { grab(e.clinical.syndromes, ''); for (const w of e.waypoints) ids.push(w.structureId); }
  if (e.kind === 'quiz') { ids.push(...e.targets.structureIds, ...e.targets.syndromeIds, ...e.targets.pathwayIds); }
  if (e.kind === 'topic') { ids.push(...e.related.structureIds, ...e.related.pathwayIds, ...e.related.syndromeIds, ...e.related.topicIds); }
  return ids;
};
const isKnown = (id: string) => byId.has(id) || meshIds.has(id) || (meshStructure.size && Array.from(meshStructure.values()).includes(id));
const structureIdsFromManifest = new Set(Array.from(meshStructure.values()));

// ---- per-entry checks
const minWords: Record<string, number> = { structure: 250, 'cranial-nerve': 350, pathway: 200, syndrome: 300, glossary: 0, quiz: 0, topic: 300 };
const wc: Record<string, number> = {};
for (const { file, e } of entries) {
  const total = proseOf(e).reduce((n, s) => n + words(s), 0);
  wc[e.id] = total;
  if (total < (minWords[e.kind] ?? 0)) err(file, `only ${total} words (min ${minWords[e.kind]})`);
  for (const c of e.citations ?? []) if (!bibliography[c.ref]) err(file, `unknown bibliography ref '${c.ref}'`);
  for (const id of refIds(e)) if (!isKnown(id)) (strict ? err : warn)(file, `unresolved reference '${id}'`);
  // A mesh id neither manifest knows is a typo when both editions are on this machine, and merely the other
  // edition's when only one is (the usual case for a clone of the public branch), so it is reported instead.
  if (e.kind === 'structure' || e.kind === 'cranial-nerve' || e.kind === 'topic') for (const m of e.meshIds) if (meshIds.size && !meshIds.has(m)) (bothEditions ? err : warn)(file, `meshId '${m}' not in manifest`);
  if (e.kind === 'syndrome') {
    if (!/\b(decussat|cross|uncrossed|ipsilateral|contralateral)/i.test(e.reasoning)) err(file, 'reasoning must state the crossing / side logic');
    if (!e.deficits.some((d) => d.substrate)) warn(file, 'no deficit names its substrate');
  }
  for (const p of proseOf(e)) {
    if (/\b(Fig(ure)?\.?|Table)\s*\d/.test(p)) err(file, `references a book figure/table: "${p.slice(0, 60)}"`);
    if (/\bsame side\b/i.test(p)) warn(file, 'use ipsilateral/contralateral instead of "same side"');
    if (/\b(localis|colour|haemorrhag|oedema|anaemi|paediatric|foetal|tumour|centre|fibre)/i.test(p)) warn(file, `British spelling in "${p.slice(0, 50)}"`);
  }
}

// ---- plagiarism (needs reference/; skipped otherwise)
const plag = checkPlagiarism(entries.map(({ file, e }) => ({ file, texts: proseOf(e) })), join(ROOT, 'reference'));
const hitsByFile = new Map<string, typeof plag.hits>();
for (const p of plag.hits) hitsByFile.set(p.file, [...(hitsByFile.get(p.file) ?? []), p]);
for (const [file, hits] of hitsByFile) for (const p of hits) (hits.length >= 2 ? err : warn)(file, `11-word overlap with ${p.corpus} p.${p.page}: "${p.shingle}"`);

// ---- coverage
const covPath = join(ROOT, 'content/coverage.json');
const coverage = existsSync(covPath) ? JSON.parse(readFileSync(covPath, 'utf8')) as { entries: { id: string; kind: string; tier: string }[] } : { entries: [] };
const authored = new Set(entries.map((x) => x.e.id));
const missingCore = coverage.entries.filter((c) => c.tier === 'core' && !authored.has(c.id));
const missingExt = coverage.entries.filter((c) => c.tier === 'extended' && !authored.has(c.id));
const unplanned = entries.filter((x) => x.e.kind !== 'glossary' && x.e.kind !== 'quiz' && x.e.kind !== 'topic' && !coverage.entries.some((c) => c.id === x.e.id)).map((x) => x.e.id);
const structuresWithoutMesh = entries.filter((x) => (x.e.kind === 'structure' || x.e.kind === 'cranial-nerve') && (x.e as { meshIds: string[] }).meshIds.length === 0).map((x) => x.e.id);
const meshesWithoutContent = Array.from(structureIdsFromManifest).filter((sid) => !byId.has(sid));

// ---- report
const errors = problems.filter((p) => p.level === 'error');
for (const p of problems) console[p.level === 'error' ? 'error' : 'warn'](`${p.level.toUpperCase()} ${p.file}: ${p.msg}`);
const counts: Record<string, number> = {};
for (const { e } of entries) counts[e.kind] = (counts[e.kind] ?? 0) + 1;
console.log(`entries: ${JSON.stringify(counts)}; total words ${Object.values(wc).reduce((a, b) => a + b, 0)}`);
console.log(`coverage: ${coverage.entries.length - missingCore.length - missingExt.length}/${coverage.entries.length} planned entries authored (${missingCore.length} core missing, ${missingExt.length} extended missing); ${meshesWithoutContent.length} manifest structures without content; plagiarism ${plag.skipped ? 'skipped' : `${plag.hits.length} hits over ${plag.pages} pages`}`);
if (args.has('--report')) {
  console.log('\nmissing core:', missingCore.map((c) => c.id).join(', '));
  console.log('\nunplanned:', unplanned.join(', '));
  console.log('\nvirtual structures (no mesh):', structuresWithoutMesh.join(', '));
  console.log('\nmanifest structures without content:', meshesWithoutContent.join(', '));
  console.log('\nword counts:'); for (const [id, n] of Object.entries(wc).sort((a, b) => a[1] - b[1])) console.log(`  ${n.toString().padStart(5)} ${id}`);
}
if (errors.length) { console.error(`${errors.length} error(s)`); process.exit(1); }
if (args.has('--validate-only') || args.has('--report')) process.exit(0);

// ---- bundle: render markdown-ish prose to HTML for the main text fields
marked.setOptions({ gfm: true, breaks: false });
const render = (s: string): string => marked.parse(s, { async: false }) as string;
const htmlFields: Record<string, string[]> = {
  structure: ['summary', 'function', 'anatomy.location', 'anatomy.boundaries', 'imaging.normalAppearance', 'imaging.sequenceOfChoice', 'bloodSupply.note'],
  'cranial-nerve': ['summary', 'function', 'anatomy.location', 'anatomy.boundaries', 'imaging.normalAppearance', 'imaging.sequenceOfChoice', 'bloodSupply.note', 'cranial.nuclearVsPeripheral', 'cranial.supranuclear'],
  pathway: ['summary', 'origin.note', 'termination', 'somatotopy', 'imaging.normalAppearance'],
  syndrome: ['presentation', 'reasoning'],
  glossary: ['definition'], quiz: ['vignette', 'explanation'],
  topic: ['summary', 'imaging.normalAppearance'],
};
const get = (o: Record<string, unknown>, path: string): unknown => path.split('.').reduce<unknown>((v, k) => (v && typeof v === 'object' ? (v as Record<string, unknown>)[k] : undefined), o);

// ---- Turkish prose: overlays in content/i18n/tr/<kind>/<id>.json map a flattened path ("deficits[0].sign") of the
// English entry to its translation (tools/i18n/prose.py writes and checks them). Each translated entry is emitted
// in full, English fields replaced, into content.tr.json, which the app fetches only in Turkish mode.
const TR_DIR = join(ROOT, 'content/i18n/tr');
const overlays = new Map<string, Record<string, string>>();
if (existsSync(TR_DIR)) for (const dir of readdirSync(TR_DIR)) {
  const kdir = join(TR_DIR, dir);
  if (!existsSync(join(DATA_DIR, dir))) { err(`content/i18n/tr/${dir}`, 'not a content kind'); continue; }
  for (const f of readdirSync(kdir).filter((x) => x.endsWith('.json'))) {
    const file = `content/i18n/tr/${dir}/${f}`;
    try {
      const ov = JSON.parse(readFileSync(join(kdir, f), 'utf8')) as { id: string; lang: string; fields: Record<string, string> };
      if (ov.id !== f.replace(/\.json$/, '') || ov.lang !== 'tr' || !ov.fields) { err(file, 'overlay must carry id (= file name), lang "tr" and fields'); continue; }
      overlays.set(ov.id, ov.fields);
    } catch (e) { err(file, `invalid JSON: ${(e as Error).message}`); }
  }
}
/** Set a flattened path ("anatomy.subdivisions[2].note") on an object; false when it does not lead to a string. */
function setPath(o: unknown, path: string, value: string): boolean {
  const keys = path.replace(/\[(\d+)\]/g, '.$1').split('.');
  let cur: unknown = o;
  for (let i = 0; i < keys.length - 1; i++) { if (!cur || typeof cur !== 'object') return false; cur = (cur as Record<string, unknown>)[keys[i]!]; }
  if (!cur || typeof cur !== 'object') return false;
  const last = keys[keys.length - 1]!;
  if (typeof (cur as Record<string, unknown>)[last] !== 'string') return false;
  (cur as Record<string, unknown>)[last] = value;
  return true;
}
const bundleTr = { generated: '', lang: 'tr', structures: {} as Record<string, unknown>, pathways: {} as Record<string, unknown>, syndromes: {} as Record<string, unknown>, glossary: {} as Record<string, unknown>, quiz: {} as Record<string, unknown>, topics: {} as Record<string, unknown> };
let translated = 0;
let mniRefsStripped = 0, meshIdsDropped = 0;
const emptied: string[] = [];
/** Every field that holds manifest mesh ids: arrays of them, and the single-id form on waypoints / MniRefs. */
const MESH_ID_ARRAYS = ['meshIds', 'highlightOnReveal'] as const;
/** Drop mesh ids that name a mesh this edition does not ship (pathway waypoints, quiz reveals, lesion markers). */
function walkMeshIdKeys(v: unknown, drop: (id: string) => void): void {
  if (Array.isArray(v)) { for (const x of v) walkMeshIdKeys(x, drop); return; }
  if (!v || typeof v !== 'object') return;
  const o = v as Record<string, unknown>;
  if (typeof o['meshId'] === 'string' && !ships(o['meshId'])) { drop(o['meshId']); delete o['meshId']; }
  for (const key of MESH_ID_ARRAYS) {
    if (!Array.isArray(o[key])) continue;
    const before = o[key] as string[];
    const after = before.filter((x) => typeof x !== 'string' || ships(x));
    for (const x of before) if (typeof x === 'string' && !ships(x)) drop(x);
    o[key] = after;
  }
  for (const x of Object.values(o)) walkMeshIdKeys(x, drop);
}
/** Collect every mesh id the bundle still names, so the gate below can be structural and not just a text search. */
function collectMeshIds(v: unknown, out: Set<string>): void {
  if (Array.isArray(v)) { for (const x of v) collectMeshIds(x, out); return; }
  if (!v || typeof v !== 'object') return;
  const o = v as Record<string, unknown>;
  if (typeof o['meshId'] === 'string') out.add(o['meshId']);
  for (const key of MESH_ID_ARRAYS) if (Array.isArray(o[key])) for (const x of o[key] as unknown[]) if (typeof x === 'string') out.add(x);
  for (const x of Object.values(o)) collectMeshIds(x, out);
}
const bundle = { generated: new Date().toISOString(), bibliography, structures: {} as Record<string, unknown>, pathways: {} as Record<string, unknown>, syndromes: {} as Record<string, unknown>, glossary: {} as Record<string, unknown>, quiz: {} as Record<string, unknown>, topics: {} as Record<string, unknown>, meshToStructure: {} as Record<string, string>, wordCounts: wc };
const searchDocs: { id: string; kind: string; name: string; names?: { tr?: string }; latin?: string; aliases: string[]; summary: string }[] = [];
for (const { e } of entries) {
  const html: Record<string, string> = {};
  for (const f of htmlFields[e.kind] ?? []) { const v = get(e as unknown as Record<string, unknown>, f); if (typeof v === 'string') html[f] = render(v); }
  // resolve MniRef.meshId → centroid
  const resolved = JSON.parse(JSON.stringify(e), (k, v) => (k === 'mni' && v && typeof v === 'object' && 'meshId' in v && !('x' in v) && meshCentroid.has(String((v as { meshId: string }).meshId)))
    ? (() => {
        const meshId = String((v as { meshId: string }).meshId);
        const c = meshCentroid.get(meshId)!; const o = (v as { offset?: { x: number; y: number; z: number } }).offset ?? { x: 0, y: 0, z: 0 };
        const p = { x: c[0]! + o.x, y: c[1]! + o.y, z: c[2]! + o.z };
        // a ref through a mesh this edition does not ship keeps the MNI point (a coordinate, not atlas data) and
        // loses the id, so "where to look" still works and nothing names a mesh that is not there
        if (!ships(meshId)) { mniRefsStripped++; return p; }
        return { ...p, meshId };
      })() : v);
  if (e.kind === 'topic') html['sections'] = JSON.stringify(e.sections.map((sec) => render(sec.body)));
  if (droppedIds.size) {
    const had = Array.isArray((resolved as { meshIds?: unknown }).meshIds) && (resolved as { meshIds: string[] }).meshIds.length > 0;
    walkMeshIdKeys(resolved, () => { meshIdsDropped++; });
    // An entry that had shapes and lost every one of them to this edition's licence filter says so, so the
    // panel can tell "the atlas this was segmented from may not be redistributed" apart from "no atlas has
    // ever segmented this", which is a different sentence and true of about twenty entries in both editions.
    if (had && !(resolved as { meshIds: string[] }).meshIds.length) {
      emptied.push(e.id);
      (resolved as { meshesDropped?: boolean }).meshesDropped = true;
    }
  }
  const entry = { ...resolved, html };
  const target = e.kind === 'structure' || e.kind === 'cranial-nerve' ? bundle.structures : e.kind === 'pathway' ? bundle.pathways : e.kind === 'syndrome' ? bundle.syndromes : e.kind === 'glossary' ? bundle.glossary : e.kind === 'topic' ? bundle.topics : bundle.quiz;
  target[e.id] = entry;
  const ov = overlays.get(e.id);
  let trName: string | undefined;
  if (ov) {
    const tr = JSON.parse(JSON.stringify(resolved)) as Record<string, unknown>;
    for (const [p, v] of Object.entries(ov)) if (!setPath(tr, p, v)) err(`content/i18n/tr/${KIND_DIRS[e.kind]}/${e.id}.json`, `no string at ${p}`);
    const htmlTr: Record<string, string> = {};
    for (const f of htmlFields[e.kind] ?? []) { const v = get(tr, f); if (typeof v === 'string') htmlTr[f] = render(v); }
    if (e.kind === 'topic') htmlTr['sections'] = JSON.stringify((tr['sections'] as { body: string }[]).map((sec) => render(sec.body)));
    const targetTr = e.kind === 'structure' || e.kind === 'cranial-nerve' ? bundleTr.structures : e.kind === 'pathway' ? bundleTr.pathways : e.kind === 'syndrome' ? bundleTr.syndromes : e.kind === 'glossary' ? bundleTr.glossary : e.kind === 'topic' ? bundleTr.topics : bundleTr.quiz;
    targetTr[e.id] = { ...tr, html: htmlTr, lang: 'tr' };
    translated++;
    trName = ov['name'] ?? ov['term'];
  }
  // mesh -> entry: the manifest's own structureId wins when that entry exists (a mesh may be listed by several
  // entries, e.g. an aseg cerebellar hemisphere by every lobule entry); otherwise the first entry listing it
  if (e.kind === 'structure' || e.kind === 'cranial-nerve') for (const m of e.meshIds) if (ships(m)) {
    const owner = meshStructure.get(m);
    if (owner && byId.has(owner)) bundle.meshToStructure[m] = owner;
    else if (!(m in bundle.meshToStructure)) bundle.meshToStructure[m] = e.id;
  }
  const name = 'name' in e ? e.name : (e as { term?: string }).term ?? e.id;
  const latin = 'latin' in e ? e.latin : undefined;
  const names = 'names' in e && e.names && Object.keys(e.names).length ? e.names : trName ? { tr: trName } : undefined;
  // the Latin term and the Turkish synonyms are searchable in every locale; the locale only changes what is displayed
  const aliases = [...('synonyms' in e ? e.synonyms : 'eponyms' in e ? e.eponyms : []), ...(latin ? [latin] : []), ...('synonymsByLang' in e ? e.synonymsByLang?.tr ?? [] : []), ...(trName ? [trName] : [])];
  const summary = 'summary' in e ? e.summary : 'presentation' in e ? (e as { presentation: string }).presentation : 'definition' in e ? (e as { definition: string }).definition : '';
  searchDocs.push({ id: e.id, kind: e.kind, name, ...(names ? { names } : {}), ...(latin ? { latin } : {}), aliases, summary: summary.slice(0, 200) });
}
// structures referenced by syndromes get a back-link
for (const s of Object.values(bundle.syndromes) as { id: string; localisation: { structures: string[] } }[]) {
  for (const sid of s.localisation.structures) for (const b of [bundle, bundleTr]) { const st = b.structures[sid] as { clinical?: { syndromes: string[] } } | undefined; if (st?.clinical && !st.clinical.syndromes.includes(s.id)) st.clinical.syndromes.push(s.id); }
}
mkdirSync(OUT, { recursive: true });
const contentName = privateEdition ? 'content.private.json' : 'content.json';
const searchName = privateEdition ? 'search-index.private.json' : 'search-index.json';
bundleTr.generated = bundle.generated;
const bundleText = JSON.stringify(bundle);
const bundleTrText = JSON.stringify(bundleTr);
const searchText = JSON.stringify(searchDocs);
if (!privateEdition) {
  // hard gate, structural first: no field that holds a mesh id may name one this edition does not ship
  const named = new Set<string>();
  collectMeshIds(bundle, named);
  for (const id of Object.keys(bundle.meshToStructure)) named.add(id);
  collectMeshIds(bundleTr, named);
  const structural = Array.from(named).filter((id) => !ships(id));
  if (structural.length) { console.error(`excluded mesh ids: ${structural.length} of them still named mesh id(s) still named by the bundle: ${structural.slice(0, 12).join(', ')}`); process.exit(1); }
  // then as text, so a stray mention in prose or a rendered link is caught too. A handful of ids are shared by a
  // mesh and the content entry that describes it (filum-terminale, the cord segment blocks); those entries keep
  // their own id — the structural pass above already proved no mesh field points at them.
  const alsoAnEntryId = new Set(Array.from(droppedIds).filter((id) => byId.has(id)));
  const leaked = Array.from(droppedIds).filter((id) => !alsoAnEntryId.has(id) && (bundleText.includes(`"${id}"`) || bundleText.includes(`/${id}`) || bundleTrText.includes(`"${id}"`) || bundleTrText.includes(`/${id}`) || searchText.includes(`"${id}"`)));
  if (leaked.length) { console.error(`excluded mesh ids: ${leaked.length} of them survive mesh id(s) survive in the bundle text: ${leaked.slice(0, 12).join(', ')}`); process.exit(1); }
  if (alsoAnEntryId.size) console.log(`public edition: ${alsoAnEntryId.size} ids are both an excluded mesh and an authored entry, kept as entry ids: ${Array.from(alsoAnEntryId).sort().join(', ')}`);
}
writeFileSync(join(OUT, contentName), bundleText);
writeFileSync(join(OUT, searchName), searchText);
const trName_ = privateEdition ? 'content.tr.private.json' : 'content.tr.json';
writeFileSync(join(OUT, trName_), bundleTrText);
console.log(`wrote public/data/${contentName} (${(bundleText.length / 1024).toFixed(0)} KB), ${searchName} (${searchDocs.length} docs) and ${trName_} (${translated} translated entries, ${(bundleTrText.length / 1024).toFixed(0)} KB)`);
if (droppedIds.size) console.log(`${privateEdition ? 'private' : 'public'} edition: ${droppedIds.size} meshes not shipped; ${meshIdsDropped} mesh references dropped from the bundle, ${mniRefsStripped} MNI refs kept their coordinate without a mesh id, ${emptied.length} entries left with no mesh`);
