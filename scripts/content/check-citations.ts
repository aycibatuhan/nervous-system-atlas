// Fails if any content entry still carries a legacy printed-textbook citation, if a citation ref does not
// resolve to content/bibliography/, or if a bibliography entry is not a verified free-to-read source.
//   node scripts/content/check-citations.ts
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { resolve, join } from 'node:path';

const ROOT = resolve(import.meta.dirname, '../..');
const BIB_DIR = join(ROOT, 'content/bibliography');
const DATA_DIR = join(ROOT, 'content/data');
const problems: string[] = [];

const bib = new Map<string, Record<string, unknown>>();
if (existsSync(BIB_DIR)) for (const f of readdirSync(BIB_DIR).filter((x) => x.endsWith('.json'))) {
  const d = JSON.parse(readFileSync(join(BIB_DIR, f), 'utf8')) as Record<string, unknown>;
  const id = f.replace(/\.json$/, '');
  if (d['id'] !== id) problems.push(`content/bibliography/${f}: id ${String(d['id'])} != file name`);
  if (d['verified'] !== true) problems.push(`content/bibliography/${f}: not verified`);
  const url = String(d['url'] ?? '');
  if (!/^https:\/\/\S+$/.test(url)) problems.push(`content/bibliography/${f}: bad url ${url}`);
  bib.set(id, d);
}

let cited = 0;
const used = new Set<string>();
for (const dir of readdirSync(DATA_DIR)) {
  for (const f of readdirSync(join(DATA_DIR, dir)).filter((x) => x.endsWith('.json'))) {
    const file = `content/data/${dir}/${f}`;
    const e = JSON.parse(readFileSync(join(DATA_DIR, dir, f), 'utf8')) as Record<string, unknown>;
    const cites = (e['citations'] as Record<string, unknown>[] | undefined) ?? [];
    for (const c of cites) {
      cited++;
      if ('book' in c || 'pages' in c || 'chapter' in c) { problems.push(`${file}: legacy textbook citation ${JSON.stringify(c)}`); continue; }
      const ref = c['ref'];
      if (typeof ref !== 'string') { problems.push(`${file}: citation without a ref`); continue; }
      if (!bib.has(ref)) problems.push(`${file}: unknown bibliography ref '${ref}'`);
      used.add(ref);
    }
    if (e['kind'] !== 'glossary' && cites.length === 0) problems.push(`${file}: no citation`);
  }
}
for (const id of bib.keys()) if (!used.has(id)) problems.push(`content/bibliography/${id}.json: never cited`);

for (const p of problems) console.error(`ERROR ${p}`);
console.log(`${cited} citations over ${bib.size} open-access sources`);
if (problems.length) { console.error(`${problems.length} citation problem(s)`); process.exit(1); }
