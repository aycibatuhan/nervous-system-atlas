import { describe, expect, it } from 'vitest';
import { readFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { renderNotice, readSources } from '../scripts/notice.ts';

const ROOT = resolve(import.meta.dirname, '..');

describe('NOTICE', () => {
  it('is up to date with sources.yaml and package.json (run `npm run notice`)', () => {
    const file = resolve(ROOT, 'NOTICE');
    expect(existsSync(file), 'NOTICE is missing - run `npm run notice`').toBe(true);
    const have = readFileSync(file, 'utf8').split('\n');
    const want = renderNotice(ROOT).split('\n');
    const i = want.findIndex((l, n) => l !== have[n]);
    expect(i === -1 ? null : { line: i + 1, inFile: have[i] ?? '(missing)', expected: want[i] }).toBeNull();
    expect(have.length).toBe(want.length);
  });

  it('names every data source, its licence and a download URL', () => {
    const { sources, licenses } = readSources(resolve(ROOT, 'pipeline/config/sources.yaml'));
    const text = readFileSync(resolve(ROOT, 'NOTICE'), 'utf8');
    expect(sources.length).toBeGreaterThan(10);
    for (const s of sources) {
      expect(text, `source ${s.id}`).toContain(`--- ${s.id} ---`);
      expect(text, `citation of ${s.id}`).toContain(s.citation.split(/\s+/).slice(0, 4).join(' '));
      const lic = licenses[s.license]!;
      expect(text, `licence of ${s.id}`).toContain(lic.url);
      expect(text, `download url of ${s.id}`).toContain(s.files[0]!.url);
      if (lic.nc || lic.no_redistribution) expect(text).toContain('EXCLUDED FROM THE PUBLIC EDITION');
    }
  });

  it('lists every npm dependency with a licence', () => {
    const pkg = JSON.parse(readFileSync(resolve(ROOT, 'package.json'), 'utf8')) as { dependencies: Record<string, string>; devDependencies: Record<string, string> };
    const text = readFileSync(resolve(ROOT, 'NOTICE'), 'utf8');
    for (const name of [...Object.keys(pkg.dependencies), ...Object.keys(pkg.devDependencies)]) {
      const line = text.split('\n').find((l) => l.trim().startsWith(`${name} `));
      expect(line, `software notice for ${name}`).toBeTruthy();
      expect(line, `licence of ${name}`).toMatch(/ - (MIT|Apache-2\.0|BSD[^ ]*|ISC|CC0-1\.0|0BSD|see package)/);
    }
  });

  it('ships the licence files the notices point at', () => {
    // public/data/LICENSE is written into the generated data folder by atlas-manifest, from the tracked template
    const ccFiles = ['content/LICENSE', 'pipeline/config/data_LICENSE.txt', 'public/data/LICENSE'].filter((f) => existsSync(resolve(ROOT, f)));
    expect(ccFiles.length).toBeGreaterThanOrEqual(2);
    for (const f of ['LICENSE', ...ccFiles]) {
      const text = readFileSync(resolve(ROOT, f), 'utf8');
      expect(text.length, f).toBeGreaterThan(10_000);
      expect(text, f).toContain('Copyright 2026 Batuhan Ayci');
    }
    expect(readFileSync(resolve(ROOT, 'LICENSE'), 'utf8')).toContain('APPENDIX: How to apply the Apache License');
    for (const f of ccFiles) {
      const text = readFileSync(resolve(ROOT, f), 'utf8');
      expect(text, f).toContain('Attribution-ShareAlike 4.0 International');
      expect(text, f).toContain('Section 8');   // the full legal code, not a summary
    }
  });
});
