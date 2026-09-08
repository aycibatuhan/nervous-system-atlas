// Guard for the public branch: proves that the *tracked tree* carries nothing that may not be published.
//   node scripts/check-tree.ts [--verbose]
//
// check-public.ts gates the built dist/ — the data a visitor downloads. This gates the repository
// itself, which is the other way a restricted file could get out, and it runs without any generated data,
// so it works in a fresh clone, in CI and in a pre-commit hook (`npm run hooks:install`).
//
// It fails on:
//   1. a tracked file under a path that must never be committed (source/, reference/, pipeline/raw/,
//      pipeline/work/, public/data/, dist/, dist-private/, qa/shots/, blender/work/, pipeline/qa/report.json);
//   2. a tracked binary or volumetric data file (.nii, .glb, .zip, .pdf, …), or any tracked file over
//      MAX_BYTES that is not on the small, named allowlist;
//   3. a restricted licence id or source id (read from pipeline/config/sources.yaml: any licence marked
//      `nc: true` or `no_redistribution: true`) used as a *field value* in a committed data file;
//   4. an excluded mesh id in a committed manifest-shaped file — a file with a `meshes` array whose entries
//      carry `file` paths. Rule 1 already keeps manifests out; this is the belt to that braces;
//   5. a trace of the private book corpus: its page markers, or the pre-migration `{"book": …, "pages": …}`
//      citation records that named a printed textbook;
//   6. (public branch only) a restricted dataset sitting in a default `atlas-download` group, which would
//      make a plain pipeline run build the private edition.
//
// One deliberate, reported exception. The authored content in content/ is shared by both editions and
// legitimately names mesh ids from both — a gyrus entry lists its Harvard-Oxford mesh and its CerebrA
// stand-in — and its prose names the restricted datasets in citations and teaching notes. Filtering that is
// the content build's job, and check-public proves the result. Those mentions are counted and printed, never
// failed on. Rule 3 therefore looks only at *field values* in data files, never at prose.
import { readFileSync, existsSync, statSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { resolve, join } from 'node:path';

const ROOT = resolve(import.meta.dirname, '..');
const verbose = process.argv.includes('--verbose');

const fail: string[] = [];
const note: string[] = [];
const bad = (m: string) => fail.push(m);

// ---- what is tracked on this branch (the index, not the working tree)
const tracked = execFileSync('git', ['ls-files', '-z'], { cwd: ROOT, maxBuffer: 64 << 20 })
  .toString('utf8').split('\0').filter(Boolean);
if (!tracked.length) { console.error('check-tree: `git ls-files` returned nothing — not a git repository?'); process.exit(1); }

// ---- 1. paths that must never be committed
const FORBIDDEN_PREFIX = [
  'source/', 'reference/', 'pipeline/raw/', 'pipeline/work/', 'public/data/', 'dist/', 'dist-private/',
  'qa/shots/', 'blender/work/', 'node_modules/', 'test-results/', 'playwright-report/',
];
const FORBIDDEN_FILE = ['pipeline/qa/report.json'];
for (const f of tracked) {
  const p = FORBIDDEN_PREFIX.find((x) => f.startsWith(x));
  if (p) bad(`${f} is tracked, but ${p} must never be committed (private material or generated data)`);
  if (FORBIDDEN_FILE.includes(f)) bad(`${f} is tracked, but it is a generated report of a private build`);
}

// ---- 2. binaries and oversized files
const BINARY_EXT = ['.nii', '.nii.gz', '.mgz', '.mnc', '.glb', '.gltf', '.ply', '.obj', '.stl', '.vtk', '.zip',
  '.gz', '.tar', '.7z', '.bin', '.npy', '.npz', '.pdf', '.epub', '.mobi', '.mp4', '.mov', '.psd', '.blend'];
const IMAGE_EXT = ['.png', '.jpg', '.jpeg', '.webp', '.gif', '.avif'];
const MAX_BYTES = 600_000;                       // a documentation screenshot; nothing else is near this
const SIZE_ALLOW = ['package-lock.json', 'content/i18n/review/terms-review.csv', 'content/i18n/review/terms-review.md'];
for (const f of tracked) {
  const lower = f.toLowerCase();
  const ext = BINARY_EXT.find((e) => lower.endsWith(e));
  if (ext) bad(`${f} is a ${ext} file — atlas data, archives and documents are never committed`);
  const abs = join(ROOT, f);
  if (!existsSync(abs)) continue;                // deleted in the working tree but still in the index
  const size = statSync(abs).size;
  if (size > MAX_BYTES && !SIZE_ALLOW.includes(f)) {
    bad(`${f} is ${(size / 1e6).toFixed(1)} MB — over the ${(MAX_BYTES / 1e6).toFixed(1)} MB cap for a tracked file`);
  }
  if (IMAGE_EXT.some((e) => lower.endsWith(e)) && !f.startsWith('docs/')) {
    bad(`${f} is an image outside docs/ — screenshots of a private-edition build must not be committed`);
  }
}

// ---- the source registry: which licences and sources may not be redistributed
// A tolerant reader for the fixed shape of pipeline/config/sources.yaml (which uses a custom `!join` tag, so
// a general YAML parser is not worth a dependency here). It asserts it found something, so a format change
// fails loudly rather than silently passing this check.
const yamlText = readFileSync(join(ROOT, 'pipeline/config/sources.yaml'), 'utf8');
const restrictedLicences = new Set<string>();
{
  const lines = yamlText.split('\n');
  const start = lines.findIndex((l) => l.startsWith('licenses:'));
  const end = lines.findIndex((l, i) => i > start && l.startsWith('sources:'));
  let current = '';
  for (const line of lines.slice(start + 1, end === -1 ? undefined : end)) {
    const head = /^ {2}([A-Za-z0-9_.-]+):\s*$/.exec(line);
    if (head) { current = head[1]!; continue; }
    if (/^ {4}(nc|no_redistribution):\s*true\s*$/.test(line) && current) restrictedLicences.add(current);
  }
}
type Src = { id: string; group: string; license: string };
const sources: Src[] = [];
{
  let cur: Partial<Src> | null = null;
  for (const line of yamlText.split('\n')) {
    const id = /^ {2}- id:\s*(\S+)\s*$/.exec(line);
    if (id) { if (cur?.id && cur.group && cur.license) sources.push(cur as Src); cur = { id: id[1]! }; continue; }
    if (!cur) continue;
    const g = /^ {4}group:\s*(\S+)\s*$/.exec(line); if (g) cur.group = g[1]!;
    const l = /^ {4}license:\s*(\S+)\s*$/.exec(line); if (l) cur.license = l[1]!;
  }
  if (cur?.id && cur.group && cur.license) sources.push(cur as Src);
}
if (restrictedLicences.size < 2 || sources.length < 10) {
  console.error(`check-tree: could not read pipeline/config/sources.yaml (${restrictedLicences.size} restricted licences, ${sources.length} sources) — the reader in this script needs updating`);
  process.exit(1);
}
const restrictedSources = new Set(sources.filter((s) => restrictedLicences.has(s.license)).map((s) => s.id));

// ---- 3. restricted ids as field values in committed data
// `"license": "FSL-NC"` or `"source": "pam50"` in a JSON file is a data record; the same words in prose are not.
const FIELD_KEYS = ['license', 'licence', 'source', 'sources', 'dataset', 'atlas'];
const fieldValue = (text: string, id: string) =>
  FIELD_KEYS.some((k) => new RegExp(`"${k}"\\s*:\\s*(\\[[^\\]]*)?"${id.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}"`).test(text));
const TEXT_EXT = ['.json', '.ts', '.js', '.mjs', '.py', '.css', '.html', '.md', '.txt', '.yaml', '.yml', '.sh', '.csv'];
// Only committed *data* is scanned. Source code names these datasets because it builds them
// (pipeline/atlas_pipeline/pam50.py writes `"source": "pam50"` into a record it produces at run time), and
// pipeline/config/ plus NOTICE are the registry and the attribution file, where the ids belong.
const DATA_EXT = ['.json', '.csv', '.yaml', '.yml'];
const isConfig = (f: string) => f.startsWith('pipeline/config/') || f === 'NOTICE';
let contentMentions = 0;
for (const f of tracked) {
  if (!DATA_EXT.some((e) => f.endsWith(e)) || isConfig(f)) continue;
  const abs = join(ROOT, f);
  if (!existsSync(abs)) continue;
  const text = readFileSync(abs, 'utf8');
  for (const id of [...restrictedLicences, ...restrictedSources]) {
    if (!text.includes(id)) continue;
    if (fieldValue(text, id)) bad(`${f} records the restricted id "${id}" as a data field`);
    else if (f.startsWith('content/')) contentMentions++;
  }
}

// ---- 4. a committed manifest naming meshes
for (const f of tracked) {
  if (!f.endsWith('.json')) continue;
  const abs = join(ROOT, f);
  if (!existsSync(abs)) continue;
  let doc: unknown;
  try { doc = JSON.parse(readFileSync(abs, 'utf8')); } catch { continue; }
  const meshes = (doc as { meshes?: unknown }).meshes;
  if (Array.isArray(meshes) && meshes.some((m) => m && typeof m === 'object' && 'file' in (m as object))) {
    bad(`${f} looks like a built manifest (a meshes[] with file paths) — generated data is never committed`);
  }
}

// ---- 5. the private book corpus
const PAGE_MARKER = /⟦\w+ p\.\d+ \| pdf \d+⟧/;
const BOOK_CITATION = /"book"\s*:\s*"(snell|berkowitz)"/i;
for (const f of tracked) {
  if (!TEXT_EXT.some((e) => f.endsWith(e))) continue;
  const abs = join(ROOT, f);
  if (!existsSync(abs)) continue;
  const text = readFileSync(abs, 'utf8');
  if (PAGE_MARKER.test(text)) bad(`${f} contains a page marker of the private reference corpus`);
  if (BOOK_CITATION.test(text) && !f.startsWith('tools/')) bad(`${f} cites a printed textbook; every shipped citation is open access`);
}

// ---- 6. public branch: nothing restricted in a default download group
const DEFAULT_GROUPS = new Set(['core']);
const branch = (() => {
  try { return execFileSync('git', ['rev-parse', '--abbrev-ref', 'HEAD'], { cwd: ROOT }).toString().trim(); }
  catch { return ''; }
})();
const publicBranch = branch !== 'private';
if (publicBranch) {
  for (const s of sources) {
    if (DEFAULT_GROUPS.has(s.group) && restrictedLicences.has(s.license)) {
      bad(`pipeline/config/sources.yaml puts the restricted source "${s.id}" (${s.license}) in the default download group "${s.group}" — a plain \`atlas-download\` would build the private edition`);
    }
  }
} else {
  note.push('branch "private": the default-download-group rule is not applied here');
}

// ---- report
note.push(`${tracked.length} tracked files; ${restrictedLicences.size} restricted licences and ${restrictedSources.size} restricted sources in the registry`);
if (contentMentions) note.push(`${contentMentions} mention(s) of a restricted dataset in authored content (citations and teaching notes, not data)`);
for (const n of note) if (verbose || !n.startsWith(String(tracked.length))) console.log(`note  ${n}`);
for (const f of fail) console.error(`FAIL  ${f}`);
if (fail.length) { console.error(`check-tree: ${fail.length} problem(s) — this tree must not be published`); process.exit(1); }
console.log(`check-tree: clean (${tracked.length} tracked files, branch ${branch || 'unknown'})`);
