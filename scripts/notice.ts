// Generates the NOTICE file at the repository root from pipeline/config/sources.yaml (data sources)
// and package.json + node_modules/*/package.json (software notices).
//
//   node scripts/notice.ts            write NOTICE
//   node scripts/notice.ts --check    fail if NOTICE is stale (also run by tests/notice.test.ts)
//   node scripts/notice.ts --print    write nothing, print the rendered text
//
// The sources file is parsed by the small YAML subset reader below (anchors, aliases, the !join tag and
// folded plain scalars are all it uses) so the check needs no dependency beyond what the app already has.
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const SOURCES = resolve(ROOT, 'pipeline/config/sources.yaml');
const NOTICE = resolve(ROOT, 'NOTICE');

// ---------------------------------------------------------------- tiny YAML subset ----
type Y = string | number | boolean | null | Y[] | { [k: string]: Y };
interface Line { indent: number; text: string }

const KEY = /^[A-Za-z0-9_.\-]+:(\s|$)/;
const SEQ = /^-(\s|$)/;

function scan(src: string): Line[] {
  const out: Line[] = [];
  for (const raw of src.split('\n')) {
    const text = raw.replace(/\s+#.*$/, '').trimEnd();     // trailing comment (no '#' appears inside a value here)
    if (!text.trim() || /^\s*#/.test(text)) continue;
    out.push({ indent: text.length - text.trimStart().length, text: text.trim() });
  }
  // fold plain multi-line scalars: a deeper line that is neither a key nor a sequence item continues the one above
  const folded: Line[] = [];
  for (const l of out) {
    const prev = folded[folded.length - 1];
    if (prev && l.indent > prev.indent && !KEY.test(l.text) && !SEQ.test(l.text)) prev.text += ' ' + l.text;
    else folded.push({ ...l });
  }
  return folded;
}

export function parseYaml(src: string): Y {
  const lines = scan(src);
  const anchors: Record<string, Y> = {};

  const scalar = (raw: string): Y => {
    let s = raw.trim();
    if (!s) return null;
    if (s.startsWith('&')) { const [, name, ...rest] = s.match(/^&(\S+)\s*([\s\S]*)$/)!; const v = scalar(rest.join(' ')); anchors[name!] = v; return v; }
    if (s.startsWith('*')) { const v = anchors[s.slice(1)]; if (v === undefined) throw new Error(`unknown anchor ${s}`); return v; }
    if (s.startsWith('!join')) {
      const inner = s.slice(s.indexOf('[') + 1, s.lastIndexOf(']'));
      return inner.split(',').map((p) => String(scalar(p))).join('');
    }
    if ((s.startsWith('"') && s.endsWith('"')) || (s.startsWith("'") && s.endsWith("'"))) return s.slice(1, -1);
    if (s === 'true') return true;
    if (s === 'false') return false;
    if (s === 'null' || s === '~') return null;
    if (/^-?\d+(\.\d+)?$/.test(s)) return Number(s);
    return s;
  };

  // parse a block starting at `i`, every line of which is indented at least `indent`
  const block = (i: number, indent: number): [Y, number] => {
    if (SEQ.test(lines[i]!.text)) {
      const arr: Y[] = [];
      while (i < lines.length && lines[i]!.indent === indent && SEQ.test(lines[i]!.text)) {
        const rest = lines[i]!.text.replace(/^-\s*/, '');
        if (!rest) { const [v, n] = block(i + 1, lines[i + 1]!.indent); arr.push(v); i = n; continue; }
        if (KEY.test(rest)) {
          // "- key: value" opens a mapping whose remaining keys sit deeper on the following lines
          const virt = lines[i]!.indent + 2;
          const sub: Line[] = [{ indent: virt, text: rest }];
          let j = i + 1;
          while (j < lines.length && lines[j]!.indent >= virt) { sub.push(lines[j]!); j++; }
          arr.push(parseYamlLines(sub, virt, scalar));
          i = j;
          continue;
        }
        arr.push(scalar(rest)); i++;
      }
      return [arr, i];
    }
    const map: Record<string, Y> = {};
    while (i < lines.length && lines[i]!.indent === indent && KEY.test(lines[i]!.text)) {
      const m = lines[i]!.text.match(/^([A-Za-z0-9_.\-]+):\s*([\s\S]*)$/)!;
      const key = m[1]!;
      const rest = m[2]!.trim();
      if (rest) { map[key] = scalar(rest); i++; continue; }
      if (i + 1 < lines.length && lines[i + 1]!.indent > indent) { const [v, n] = block(i + 1, lines[i + 1]!.indent); map[key] = v; i = n; }
      else { map[key] = null; i++; }
    }
    return [map, i];
  };

  // sub-blocks of a "- key: value" item are parsed with the same machinery over their own line slice
  function parseYamlLines(sub: Line[], indent: number, sc: (r: string) => Y): Y {
    const map: Record<string, Y> = {};
    let i = 0;
    while (i < sub.length) {
      const l = sub[i]!;
      if (l.indent !== indent || !KEY.test(l.text)) { i++; continue; }
      const m = l.text.match(/^([A-Za-z0-9_.\-]+):\s*([\s\S]*)$/)!;
      const key = m[1]!; const rest = m[2]!.trim();
      if (rest) { map[key] = sc(rest); i++; continue; }
      const childIndent = sub[i + 1]?.indent ?? -1;
      if (childIndent > indent) {
        const child: Line[] = [];
        let j = i + 1;
        while (j < sub.length && sub[j]!.indent >= childIndent) { child.push(sub[j]!); j++; }
        map[key] = parseBlockList(child, childIndent, sc);
        i = j;
      } else { map[key] = null; i++; }
    }
    return map;
  }
  function parseBlockList(sub: Line[], indent: number, sc: (r: string) => Y): Y {
    if (sub.length && SEQ.test(sub[0]!.text)) {
      const arr: Y[] = [];
      let i = 0;
      while (i < sub.length) {
        if (sub[i]!.indent !== indent || !SEQ.test(sub[i]!.text)) { i++; continue; }
        const rest = sub[i]!.text.replace(/^-\s*/, '');
        const virt = indent + 2;
        const item: Line[] = rest ? [{ indent: virt, text: rest }] : [];
        let j = i + 1;
        while (j < sub.length && sub[j]!.indent >= virt) { item.push(sub[j]!); j++; }
        arr.push(rest && !KEY.test(rest) ? sc(rest) : parseYamlLines(item, virt, sc));
        i = j;
      }
      return arr;
    }
    return parseYamlLines(sub, indent, sc);
  }

  const [value] = block(0, lines[0]?.indent ?? 0);
  return value;
}

// ---------------------------------------------------------------- sources ----
export interface SourceEntry { id: string; name?: string; group?: string; license: string; citation: string; manual?: boolean; generated?: boolean; api?: string; files?: { url: string; dest?: string }[] }
export interface LicenseEntry { name: string; url: string; attribution?: string; nc?: boolean; no_redistribution?: boolean }

export function readSources(file = SOURCES): { licenses: Record<string, LicenseEntry>; sources: SourceEntry[] } {
  const y = parseYaml(readFileSync(file, 'utf8')) as unknown as { licenses: Record<string, LicenseEntry>; sources: SourceEntry[] };
  if (!y.sources?.length) throw new Error(`${file}: no sources parsed`);
  return y;
}

// ---------------------------------------------------------------- software ----
interface Pkg { name: string; version?: string; license?: string; licenses?: { type: string }[]; author?: string | { name?: string }; homepage?: string; repository?: string | { url?: string } }

function repoUrl(p: Pkg): string {
  const r = typeof p.repository === 'string' ? p.repository : p.repository?.url;
  const url = p.homepage ?? r ?? '';
  return url.replace(/^git\+/, '').replace(/\.git$/, '').replace(/^git:\/\//, 'https://');
}

export function softwareNotices(root = ROOT): { name: string; version: string; license: string; author: string; url: string; dev: boolean }[] {
  const pkg = JSON.parse(readFileSync(resolve(root, 'package.json'), 'utf8')) as { dependencies?: Record<string, string>; devDependencies?: Record<string, string> };
  const rows: { name: string; version: string; license: string; author: string; url: string; dev: boolean }[] = [];
  for (const [dev, deps] of [[false, pkg.dependencies ?? {}], [true, pkg.devDependencies ?? {}]] as const) {
    for (const name of Object.keys(deps).sort()) {
      const p = resolve(root, 'node_modules', name, 'package.json');
      const meta: Pkg = existsSync(p) ? JSON.parse(readFileSync(p, 'utf8')) : { name };
      const author = typeof meta.author === 'string' ? meta.author.replace(/\s*<[^>]*>/, '').replace(/\s*\([^)]*\)/, '') : (meta.author?.name ?? '');
      rows.push({
        name, version: meta.version ?? deps[name]!.replace(/^[\^~]/, ''),
        license: meta.license ?? meta.licenses?.[0]?.type ?? 'see package',
        author, url: repoUrl(meta), dev,
      });
    }
  }
  return rows;
}

// ---------------------------------------------------------------- render ----
const CHANGES = 'registration into MNI152NLin2009cAsym space, remeshing of the label masks through a signed-distance field, smoothing, decimation to per-class triangle budgets, welding of neighbouring parcels, relabelling and renaming, recolouring, and the construction of derived meshes from source geometry';

const wrap = (text: string, width: number, indent: string): string => {
  const words = text.split(/\s+/);
  const out: string[] = []; let line = '';
  for (const w of words) {
    if (line && (line + ' ' + w).length > width) { out.push(line); line = w; } else line = line ? line + ' ' + w : w;
  }
  if (line) out.push(line);
  return out.map((l, i) => (i ? indent + l : l)).join('\n');
};

export function renderNotice(root = ROOT): string {
  const { licenses, sources } = readSources(resolve(root, 'pipeline/config/sources.yaml'));
  const L: string[] = [];
  const rule = '='.repeat(78);
  L.push('Clinical Neuroanatomy Atlas');
  L.push('Copyright 2026 Batuhan Ayci');
  L.push('');
  L.push('  Code                           Apache License 2.0    LICENSE');
  L.push('  Generated data (public/data/)  CC BY-SA 4.0          public/data/LICENSE');
  L.push('  Authored content (content/)    CC BY-SA 4.0          content/LICENSE');
  L.push('');
  L.push(wrap('This file is generated by `npm run notice` from pipeline/config/sources.yaml and package.json. Do not edit it by hand; `npm run notice -- --check` fails when it is stale.', 78, ''));
  L.push('');
  L.push(rule);
  L.push('DATA SOURCES');
  L.push(rule);
  L.push('');
  L.push(wrap(`Every mesh, volume and label table under public/data/ is a derivative of one or more of the datasets below, used under the licence named with it. Changes made: ${CHANGES}.`, 78, ''));
  L.push('');
  L.push(wrap('Sources whose licence is non-commercial or forbids redistribution are marked below; the meshes and volumes derived from them are flagged `nc` / `noRedistribution` in public/data/manifest.json and are excluded from the public edition of the atlas.', 78, ''));
  L.push('');

  const block = (s: SourceEntry): void => {
    const lic = licenses[s.license];
    if (!lic) throw new Error(`source ${s.id}: unknown licence ${s.license}`);
    L.push(`--- ${s.id} ---`);
    L.push(`  Dataset:     ${s.name ?? s.id}`);
    L.push(`  Citation:    ${wrap(s.citation, 62, '               ')}`);
    L.push(`  Licence:     ${lic.name}`);
    L.push(`               ${lic.url}`);
    if (lic.attribution) L.push(`  Attribution: ${wrap(lic.attribution, 62, '               ')}`);
    const urls = (s.files ?? []).map((f) => f.url);
    if (s.generated) {
      L.push('  Generated:   produced on this machine by the pipeline, not downloaded');
      L.push(`               (pipeline/raw/${s.id}/SOURCE.json records the tool, its version and the command)`);
    } else if (s.api) {
      L.push(`  Accessed:    ${s.api}`);
      L.push('               (live API, read by tools/i18n/terms.py and cached under reference/terms/; nothing is downloaded as a file)');
    } else {
      L.push(`  Download:    ${urls[0] ?? ''}`);
      for (const u of urls.slice(1)) L.push(`               ${u}`);
    }
    if (s.manual) L.push('  Download requires a manual click-through on the provider\'s site.');
    if (lic.nc || lic.no_redistribution) {
      const why = [lic.nc ? 'non-commercial' : null, lic.no_redistribution ? 'no redistribution of derived files' : null].filter(Boolean).join(', ');
      L.push(`  *** ${why.toUpperCase()} - EXCLUDED FROM THE PUBLIC EDITION ***`);
    }
    L.push('');
  };
  for (const s of sources.filter((x) => x.group !== 'terms')) block(s);

  L.push(rule);
  L.push('TERMINOLOGY');
  L.push(rule);
  L.push('');
  L.push(wrap('The Latin structure names (`latin`, and the Turkish display names `names.tr`) and the Turkish search synonyms (`synonymsByLang.tr`) in content/ come from the sources below, matched to the atlas entries by tools/i18n/terms.py and reviewed by hand. The FIPAT terminologies are published as PDFs under CC BY-ND 4.0; only the terms are used, which FIPAT places in the public domain, and the PDFs are not redistributed. Wikidata is CC0. Turkish Wikipedia titles are CC BY-SA 4.0, the licence of the atlas content.', 78, ''));
  L.push('');
  for (const s of sources.filter((x) => x.group === 'terms')) block(s);

  L.push(rule);
  L.push('SOFTWARE');
  L.push(rule);
  L.push('');
  L.push(wrap('The application bundles or builds on the packages below, each under its own licence (read from node_modules/<package>/package.json).', 78, ''));
  L.push('');
  const rows = softwareNotices(root);
  for (const [dev, title] of [[false, 'Runtime dependencies (shipped in the browser bundle)'], [true, 'Build and test dependencies (not shipped)']] as const) {
    L.push(`${title}:`);
    L.push('');
    for (const r of rows.filter((x) => x.dev === dev)) {
      L.push(`  ${r.name} ${r.version} - ${r.license}${r.author ? ` - (c) ${r.author}` : ''}`);
      if (r.url) L.push(`      ${r.url}`);
    }
    L.push('');
  }
  L.push(rule);
  L.push('CONTENT SOURCES');
  L.push(rule);
  L.push('');
  L.push(wrap('The prose in content/ is original. Every non-glossary entry cites open-access sources - StatPearls chapters on the NCBI Bookshelf, open-access articles in PubMed Central and openly licensed textbook or reference pages - recorded one file per source in content/bibliography/ with its licence and canonical free full-text URL. Those works remain under their own licences and are cited, not redistributed.', 78, ''));
  L.push('');
  return L.join('\n');
}

// ---------------------------------------------------------------- cli ----
function cli(argv: string[]): number {
  const text = renderNotice();
  if (argv.includes('--print')) { process.stdout.write(text); return 0; }
  if (argv.includes('--check')) {
    const have = existsSync(NOTICE) ? readFileSync(NOTICE, 'utf8') : '';
    if (have === text) { console.log(`NOTICE is up to date (${text.split('\n').length} lines).`); return 0; }
    console.error('NOTICE is stale. Run `npm run notice` and commit the result.');
    const a = have.split('\n'); const b = text.split('\n');
    for (let i = 0; i < Math.max(a.length, b.length); i++) if (a[i] !== b[i]) { console.error(`  first difference at line ${i + 1}:\n  - ${a[i] ?? '(missing)'}\n  + ${b[i] ?? '(missing)'}`); break; }
    return 1;
  }
  writeFileSync(NOTICE, text);
  console.log(`NOTICE: ${readSources().sources.length} data sources, ${softwareNotices().length} packages -> ${NOTICE}`);
  return 0;
}

if (process.argv[1] && /notice\.ts$/.test(process.argv[1])) process.exit(cli(process.argv.slice(2)));
