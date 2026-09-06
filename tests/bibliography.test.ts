import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync, existsSync } from 'node:fs';

const BIB_DIR = 'content/bibliography';
const DATA_DIR = 'content/data';

interface Bib { id: string; type: string; title: string; authors: string[]; year: number; container: string; url: string; nbk?: string; pmcid?: string; doi?: string; verified: boolean; accessed: string }
const bibFiles = existsSync(BIB_DIR) ? readdirSync(BIB_DIR).filter((f) => f.endsWith('.json')) : [];
const bib: Record<string, Bib> = {};
for (const f of bibFiles) bib[f.replace(/\.json$/, '')] = JSON.parse(readFileSync(`${BIB_DIR}/${f}`, 'utf8'));

const entries: { file: string; e: Record<string, unknown> }[] = [];
for (const dir of readdirSync(DATA_DIR)) {
  for (const f of readdirSync(`${DATA_DIR}/${dir}`).filter((x) => x.endsWith('.json'))) {
    entries.push({ file: `${DATA_DIR}/${dir}/${f}`, e: JSON.parse(readFileSync(`${DATA_DIR}/${dir}/${f}`, 'utf8')) });
  }
}

describe('open-access bibliography', () => {
  it('has entries', () => { expect(bibFiles.length).toBeGreaterThan(0); });

  it('every entry is verified, freely readable and well formed', () => {
    for (const [id, b] of Object.entries(bib)) {
      expect(b.id, id).toBe(id);
      expect(b.verified, id).toBe(true);
      expect(b.authors.length, id).toBeGreaterThan(0);
      expect(b.title.length, id).toBeGreaterThan(2);
      expect(b.year, id).toBeGreaterThan(1989);
      expect(b.accessed, id).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(() => new URL(b.url), id).not.toThrow();
      expect(b.url, id).toMatch(/^https:\/\//);
      // the id that identifies the free full text must match the URL it points at
      if (b.nbk) { expect(b.nbk, id).toMatch(/^NBK\d+$/); expect(b.url, id).toContain(b.nbk); }
      if (b.pmcid) { expect(b.pmcid, id).toMatch(/^PMC\d+$/); expect(b.url, id).toContain(b.pmcid); }
      expect(['statpearls', 'journal', 'book', 'web'], id).toContain(b.type);
      if (b.type === 'statpearls') expect(b.nbk, id).toBeTruthy();
    }
  });

  it('no entry cites a printed textbook any more', () => {
    for (const { file, e } of entries) {
      for (const c of (e['citations'] as Record<string, unknown>[] | undefined) ?? []) {
        expect(Object.keys(c), file).not.toContain('book');
        expect(Object.keys(c), file).not.toContain('pages');
        expect(Object.keys(c), file).not.toContain('chapter');
        expect(typeof c['ref'], file).toBe('string');
      }
    }
  });

  it('every citation ref resolves to a bibliography entry', () => {
    for (const { file, e } of entries) {
      for (const c of (e['citations'] as { ref: string }[] | undefined) ?? []) {
        expect(bib[c.ref], `${file} -> ${c.ref}`).toBeTruthy();
      }
    }
  });

  it('every entry that needs a source has one', () => {
    for (const { file, e } of entries) {
      if (e['kind'] === 'glossary') continue;
      expect(((e['citations'] as unknown[]) ?? []).length, file).toBeGreaterThan(0);
    }
  });

  it('no bibliography entry is orphaned', () => {
    const used = new Set<string>();
    for (const { e } of entries) for (const c of (e['citations'] as { ref: string }[] | undefined) ?? []) used.add(c.ref);
    const orphans = Object.keys(bib).filter((id) => !used.has(id));
    expect(orphans, `unused bibliography entries: ${orphans.join(', ')}`).toEqual([]);
  });
});
