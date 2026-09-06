import { describe, it, expect } from 'vitest';
import { readFileSync, existsSync } from 'node:fs';

const path = 'public/data/content.json';
const bundle = existsSync(path) ? JSON.parse(readFileSync(path, 'utf8')) : null;

describe.skipIf(!bundle)('content bundle', () => {
  it('has every kind populated', () => {
    for (const k of ['structures', 'pathways', 'syndromes', 'glossary', 'quiz']) expect(Object.keys(bundle[k]).length).toBeGreaterThan(0);
  });
  it('syndrome references resolve', () => {
    const ids = new Set([...Object.keys(bundle.structures), ...Object.keys(bundle.pathways)]);
    for (const s of Object.values(bundle.syndromes) as { localisation: { structures: string[] }; deficits: { substrate?: string }[] }[]) {
      for (const id of s.localisation.structures) expect(ids.has(id), id).toBe(true);
      for (const d of s.deficits) if (d.substrate) expect(ids.has(d.substrate), d.substrate).toBe(true);
    }
  });
  it('pathway waypoints resolve and have at least 3 stations', () => {
    for (const p of Object.values(bundle.pathways) as { id: string; waypoints: { structureId: string }[] }[]) {
      expect(p.waypoints.length, p.id).toBeGreaterThanOrEqual(3);
      for (const w of p.waypoints) expect(bundle.structures[w.structureId], `${p.id}:${w.structureId}`).toBeTruthy();
    }
  });
  it('quiz answers are among the options', () => {
    for (const q of Object.values(bundle.quiz) as { answer: string; options: { key: string }[]; original: boolean }[]) {
      expect(q.options.map((o) => o.key)).toContain(q.answer);
      expect(q.original).toBe(true);
    }
  });
});
