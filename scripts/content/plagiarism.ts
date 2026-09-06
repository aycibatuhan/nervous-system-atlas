// 11-word shingle overlap between the authored prose and an optional private reference corpus
// (reference/<corpus>/clean/*.txt, never committed). Skipped entirely when reference/ is absent.
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

const N = 11;   // 11-word shingles: long enough to skip pure anatomical nomenclature
const norm = (s: string): string[] => s.toLowerCase().replace(/[^a-z0-9\s]/g, ' ').split(/\s+/).filter(Boolean);
const shingles = (tokens: string[]): string[] => { const out: string[] = []; for (let i = 0; i + N <= tokens.length; i++) out.push(tokens.slice(i, i + N).join(' ')); return out; };

export interface PlagHit { file: string; corpus: string; page: number; shingle: string }

export function checkPlagiarism(docs: { file: string; texts: string[] }[], refDir: string): { hits: PlagHit[]; skipped: boolean; pages: number } {
  if (!existsSync(refDir)) return { hits: [], skipped: true, pages: 0 };
  const index = new Map<string, { corpus: string; page: number }>();
  let pages = 0;
  // any reference/<corpus>/clean/ directory the operator has prepared locally
  const corpora = readdirSync(refDir, { withFileTypes: true }).filter((d) => d.isDirectory() && existsSync(join(refDir, d.name, 'clean'))).map((d) => d.name);
  for (const corpus of corpora) {
    const dir = join(refDir, corpus, 'clean');
    for (const f of readdirSync(dir).filter((x) => x.endsWith('.txt'))) {
      let page = 0;
      for (const chunk of readFileSync(join(dir, f), 'utf8').split(/^⟦\w+ p\.(\d+) \| pdf \d+⟧$/m)) {
        if (/^\d+$/.test(chunk)) { page = Number(chunk); pages++; continue; }
        for (const s of shingles(norm(chunk))) if (!index.has(s)) index.set(s, { corpus, page });
      }
    }
  }
  const hits: PlagHit[] = [];
  for (const d of docs) for (const t of d.texts) for (const s of shingles(norm(t))) { const hit = index.get(s); if (hit) { hits.push({ file: d.file, corpus: hit.corpus, page: hit.page, shingle: s }); break; } }
  return { hits, skipped: false, pages };
}
