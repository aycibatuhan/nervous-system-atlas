// 8-word shingle overlap between authored prose and the private reference corpus (reference/<book>/clean/*.txt).
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

const N = 11;   // 11-word shingles: long enough to skip pure anatomical nomenclature
const norm = (s: string): string[] => s.toLowerCase().replace(/[^a-z0-9\s]/g, ' ').split(/\s+/).filter(Boolean);
const shingles = (tokens: string[]): string[] => { const out: string[] = []; for (let i = 0; i + N <= tokens.length; i++) out.push(tokens.slice(i, i + N).join(' ')); return out; };

export interface PlagHit { file: string; book: string; page: number; shingle: string }

export function checkPlagiarism(docs: { file: string; texts: string[] }[], refDir: string): { hits: PlagHit[]; skipped: boolean; pages: number } {
  if (!existsSync(refDir)) return { hits: [], skipped: true, pages: 0 };
  const index = new Map<string, { book: string; page: number }>();
  let pages = 0;
  for (const book of ['snell', 'berkowitz']) {
    const dir = join(refDir, book, 'clean');
    if (!existsSync(dir)) continue;
    for (const f of readdirSync(dir).filter((x) => x.endsWith('.txt'))) {
      let page = 0;
      for (const chunk of readFileSync(join(dir, f), 'utf8').split(/^⟦\w+ p\.(\d+) \| pdf \d+⟧$/m)) {
        if (/^\d+$/.test(chunk)) { page = Number(chunk); pages++; continue; }
        for (const s of shingles(norm(chunk))) if (!index.has(s)) index.set(s, { book, page });
      }
    }
  }
  const hits: PlagHit[] = [];
  for (const d of docs) for (const t of d.texts) for (const s of shingles(norm(t))) { const hit = index.get(s); if (hit) { hits.push({ file: d.file, book: hit.book, page: hit.page, shingle: s }); break; } }
  return { hits, skipped: false, pages };
}
