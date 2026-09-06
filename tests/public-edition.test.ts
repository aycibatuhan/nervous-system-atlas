// The public edition must contain nothing we may not redistribute, and building it must leave the private
// edition and the authored source JSON exactly as they were.
//
// The exclusion rule is implemented twice: in pipeline/atlas_pipeline/manifest.py (filter_public) and, below,
// in TypeScript. The test runs the TypeScript rule over the real private manifest and requires the two to
// agree, so a change on either side that widens or narrows the public edition shows up here.
import { describe, it, expect } from 'vitest';
import { readFileSync, existsSync, readdirSync } from 'node:fs';
import { resolve, join } from 'node:path';

const ROOT = resolve(import.meta.dirname, '..');
const DATA = join(ROOT, 'public/data');
const read = (p: string) => JSON.parse(readFileSync(join(DATA, p), 'utf8'));
const has = (p: string) => existsSync(join(DATA, p));

const NAME_STRINGS = ['Brainstem Navigator', 'BrainstemNavigator', 'Harvard-Oxford', 'Diedrichsen', 'PAM50'];

interface Mesh { id: string; license: string; source: string; nc?: boolean; derived?: string; structureId: string }
interface Manifest {
  edition?: string;
  meshes: Mesh[];
  volumes: Record<string, { file: string; space?: string; lut?: string }>;
  grids?: Record<string, { license: string; source: string }>;
  licenses: Record<string, { nc?: boolean; noRedistribution?: boolean; text: string }>;
  sources: Record<string, { license: string }>;
}

/** The rule, in TypeScript: a licence that is nc or no-redistribution takes its meshes, sources and volumes out. */
function excludeFrom(man: Manifest) {
  const restricted = new Set(Object.entries(man.licenses).filter(([, l]) => l.nc || l.noRedistribution).map(([k]) => k));
  const sources = new Set(Object.entries(man.sources).filter(([, s]) => restricted.has(s.license)).map(([k]) => k));
  const tokens = [...sources, ...NAME_STRINGS].map((t) => t.toLowerCase());
  const meshes = new Set(man.meshes.filter((m) => restricted.has(m.license) || sources.has(m.source)
    || tokens.some((t) => (m.derived ?? '').toLowerCase().includes(t))).map((m) => m.id));
  const cordDropped = !!man.grids?.['cord'] && restricted.has(man.grids['cord'].license);
  const volumes = new Set(Object.entries(man.volumes)
    .filter(([, v]) => (v.space === 'cord' && cordDropped)).map(([k]) => k));
  return { restricted, sources, meshes, volumes };
}

const priv = read('manifest.json') as Manifest;
const pub = has('manifest.public.json') ? read('manifest.public.json') as Manifest : null;
const exclusions = has('manifest.public.exclusions.json') ? read('manifest.public.exclusions.json') as {
  meshes: { id: string }[]; volumes: { key: string }[]; licenses: Record<string, string>; sources: Record<string, unknown>;
} : null;

describe('public edition — the private edition is untouched', () => {
  it('still carries the restricted licences and their meshes', () => {
    expect(priv.edition ?? 'private').toBe('private');
    for (const id of ['FSL-NC', 'CC-BY-NC-3.0', 'BrainstemNavigator-NC-ND', 'PAM50-unlicensed']) expect(priv.licenses[id]).toBeTruthy();
    expect(priv.meshes.some((m) => m.license === 'FSL-NC')).toBe(true);
    expect(priv.meshes.some((m) => m.license === 'BrainstemNavigator-NC-ND')).toBe(true);
    expect(priv.grids?.['cord']).toBeTruthy();
    expect(priv.volumes['labels_spine']).toBeTruthy();
  });

  it('leaves the authored content JSON referencing the excluded meshes', () => {
    const dir = join(ROOT, 'content/data/structures');
    const files = readdirSync(dir).filter((f) => f.endsWith('.json'));
    const ex = excludeFrom(priv).meshes;
    const stillThere = files.filter((f) => (JSON.parse(readFileSync(join(dir, f), 'utf8')).meshIds ?? []).some((m: string) => ex.has(m)));
    expect(stillThere.length).toBeGreaterThan(50);
  });

  it('leaves the private content bundle referencing them too', () => {
    if (!has('content.json')) return;
    const bundle = read('content.json') as { meshToStructure: Record<string, string> };
    const ex = excludeFrom(priv).meshes;
    expect(Object.keys(bundle.meshToStructure).some((id) => ex.has(id))).toBe(true);
  });
});

describe('public edition — the manifest filter', () => {
  it('excludes every nc / no-redistribution mesh, source, licence and volume', () => {
    const ex = excludeFrom(priv);
    expect(ex.restricted).toEqual(new Set(['FSL-NC', 'CC-BY-NC-3.0', 'BrainstemNavigator-NC-ND', 'PAM50-unlicensed']));
    expect(ex.sources).toEqual(new Set(['harvard_oxford', 'diedrichsen_cerebellum', 'brainstem_navigator', 'pam50']));
    expect(ex.meshes.size).toBeGreaterThan(150);
    expect(ex.volumes).toEqual(new Set(['cord_t2', 'cord_t1', 'labels_spine']));
  });

  it('agrees with what atlas-manifest --public actually dropped', () => {
    if (!exclusions) return;                                        // not built in this checkout
    const ex = excludeFrom(priv);
    expect(new Set(exclusions.meshes.map((m) => m.id))).toEqual(ex.meshes);
    expect(new Set(exclusions.volumes.map((v) => v.key))).toEqual(ex.volumes);
    expect(new Set(Object.keys(exclusions.sources))).toEqual(ex.sources);
    for (const id of ex.restricted) expect(Object.keys(exclusions.licenses)).toContain(id);
  });

  it('produces a manifest with nothing restricted left in it', () => {
    if (!pub) return;
    const ex = excludeFrom(priv);
    expect(pub.edition).toBe('public');
    for (const [id, l] of Object.entries(pub.licenses)) {
      expect(l.nc, `licence ${id}`).toBeFalsy();
      expect(l.noRedistribution, `licence ${id}`).toBeFalsy();
    }
    for (const id of ex.sources) expect(pub.sources[id]).toBeUndefined();
    for (const m of pub.meshes) {
      expect(ex.meshes.has(m.id), `mesh ${m.id}`).toBe(false);
      expect(pub.licenses[m.license], `licence of ${m.id}`).toBeTruthy();
      expect(pub.sources[m.source], `source of ${m.id}`).toBeTruthy();
    }
    for (const [k, v] of Object.entries(pub.volumes)) expect(v.space ? !!pub.grids?.[v.space] : true, `volume ${k}`).toBe(true);
    expect(pub.grids?.['cord']).toBeFalsy();
    const blob = JSON.stringify(pub);
    for (const n of NAME_STRINGS) expect(blob.includes(n), `manifest names ${n}`).toBe(false);
  });

  it('keeps the systems and the bulk of the atlas', () => {
    if (!pub) return;
    expect((pub as unknown as { systems: unknown[] }).systems).toEqual((priv as unknown as { systems: unknown[] }).systems);
    expect(pub.meshes.length).toBeGreaterThan(priv.meshes.length * 0.6);
    expect(pub.volumes['t1w']).toBeTruthy();
    expect(pub.volumes['labels_anat']).toBeTruthy();
  });
});

describe('public edition — the content bundle', () => {
  const bundle = has('content.public.json') ? read('content.public.json') as Record<string, Record<string, unknown>> : null;

  const meshIdsNamedBy = (v: unknown, out = new Set<string>()): Set<string> => {
    if (Array.isArray(v)) { for (const x of v) meshIdsNamedBy(x, out); return out; }
    if (!v || typeof v !== 'object') return out;
    const o = v as Record<string, unknown>;
    if (typeof o['meshId'] === 'string') out.add(o['meshId']);
    for (const k of ['meshIds', 'highlightOnReveal']) if (Array.isArray(o[k])) for (const x of o[k] as unknown[]) if (typeof x === 'string') out.add(x);
    for (const x of Object.values(o)) meshIdsNamedBy(x, out);
    return out;
  };

  it('names no mesh that the public manifest does not ship', () => {
    if (!bundle || !pub) return;
    const shipped = new Set(pub.meshes.map((m) => m.id));
    const known = new Set(priv.meshes.map((m) => m.id));
    const named = meshIdsNamedBy(bundle);
    for (const id of Object.keys(bundle['meshToStructure'] ?? {})) named.add(id);
    // ids that are not meshes in either edition are the content's own business (a few quiz highlights name a
    // structure rather than a mesh); what must not happen is a mesh that exists privately and not publicly
    const strays = Array.from(named).filter((id) => known.has(id) && !shipped.has(id));
    expect(strays, `strays: ${strays.slice(0, 10).join(', ')}`).toEqual([]);
  });

  it('keeps the entries whose mesh was dropped, with their prose', () => {
    if (!bundle) return;
    const structures = bundle['structures'] as Record<string, { meshIds?: string[]; summary?: string }>;
    const shippedIds = new Set(pub!.meshes.map((m) => m.id));
    const restricted = new Set(exclusions!.meshes.map((m) => m.id));
    // Brainstem Navigator / Harvard-Oxford: the restricted meshes are gone; whatever remains (a stand-in, or a
    // public-edition replacement such as the DKT parcel or a coordinate-anchored nucleus) must ship publicly
    for (const id of ['locus-coeruleus', 'gyrus-precentral']) {
      const e = structures[id];
      expect(e, id).toBeTruthy();
      expect((e!.summary ?? '').length).toBeGreaterThan(100);
      for (const m of e!.meshIds ?? []) { expect(restricted.has(m), `${id} still lists restricted ${m}`).toBe(false); expect(shippedIds.has(m), `${id} lists unshipped ${m}`).toBe(true); }
    }
    // some entries keep their prose with no mesh at all, and the app has to open them by id alone
    expect(Object.values(structures).filter((s) => s.meshIds?.length === 0).length).toBeGreaterThan(20);
  });

  it('leaves MNI coordinates usable where an MniRef pointed at a dropped mesh', () => {
    if (!bundle) return;
    const structures = bundle['structures'] as Record<string, { imaging?: { bestView?: { mni?: Record<string, number> }[] } }>;
    const views = Object.values(structures).flatMap((s) => s.imaging?.bestView ?? []);
    expect(views.length).toBeGreaterThan(0);
    // every resolved ref is either a full coordinate or absent; none is half-resolved or names a dropped mesh
    for (const v of views) if (v.mni && 'x' in v.mni) { expect(Number.isFinite(v.mni['y'])).toBe(true); expect(Number.isFinite(v.mni['z'])).toBe(true); }
  });

  it('has a search index that still covers the mesh-less entries', () => {
    if (!has('search-index.public.json')) return;
    const docs = read('search-index.public.json') as { id: string }[];
    const ids = new Set(docs.map((d) => d.id));
    expect(ids.has('locus-coeruleus')).toBe(true);
    expect(ids.has('gyrus-precentral')).toBe(true);
  });
});
