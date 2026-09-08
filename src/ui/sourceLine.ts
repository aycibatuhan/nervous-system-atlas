import type { App } from '../app.ts';
import type { ManifestLicense } from '../types/manifest.ts';
import { h } from './dom.ts';
import { t, type Key } from '../i18n/index.ts';

/** Short form of a licence for the one-line credit ("CC BY-SA 4.0", "FSL, non-commercial"). */
export function licenceShort(id: string, lic: ManifestLicense | undefined): string {
  const special: Record<string, Key> = {
    'FSL-NC': 'licence.fslNc',
    'MNI': 'licence.mni',
    'PAM50-unlicensed': 'licence.pam50',
    'BrainstemNavigator-NC-ND': 'licence.ncNd',
  };
  const key = special[id];
  if (key) return t(key);
  if (/^CC/.test(id)) return id.replace(/^CC-BY/, 'CC BY').replace(/^CC0/, 'CC0').replace(/-(\d[\d.]*)(-JP)?$/, (_m, v: string, jp?: string) => ` ${v}${jp ? ' JP' : ''}`);
  return lic?.name ?? id;
}

/** A mesh's `derived` field is a paragraph; this is the first clause of it, for a tooltip-backed tag. */
function derivedShort(text: string): string {
  const first = text.split(/[,;(]/)[0]!.trim();
  return first.length > 64 ? first.slice(0, 61) + '…' : first;
}

export interface SourceCredit { id: string; name: string; license: string; licenceName: string; url: string; count: number }

/** Unique data sources behind a set of mesh ids, in the order they first appear. */
export function creditsFor(app: App, meshIds: Iterable<string>): { credits: SourceCredit[]; derived: { id: string; note: string }[] } {
  const credits = new Map<string, SourceCredit>();
  const derived: { id: string; note: string }[] = [];
  for (const id of meshIds) {
    const m = app.registry.byId.get(id) ?? app.manifest.meshes.find((x) => x.id === id || x.structureId === id);
    if (!m) continue;
    const src = app.manifest.sources[m.source];
    const lic = app.manifest.licenses[m.license];
    const c = credits.get(m.source) ?? { id: m.source, name: src?.name ?? m.source, license: m.license, licenceName: licenceShort(m.license, lic), url: src?.url ?? lic?.url ?? '', count: 0 };
    c.count++;
    credits.set(m.source, c);
    if (m.derived && !derived.some((d) => d.id === m.id)) derived.push({ id: m.id, note: m.derived });
  }
  return { credits: [...credits.values()], derived };
}

/**
 * "Source: Harvard-Oxford cortical and subcortical structural atlases (FSL, non-commercial) ·
 *  Z-Anatomy open 3D atlas of human anatomy (CC BY-SA 4.0) · derived: …" — every name links to the About panel.
 * Returns null when none of the ids is a mesh in this build.
 */
export function sourceLine(app: App, meshIds: Iterable<string>): HTMLElement | null {
  const { credits, derived } = creditsFor(app, meshIds);
  if (!credits.length) return null;
  const el = h('div', { class: 'source-line muted small' }, t('source.label'));
  credits.forEach((c, i) => {
    if (i) el.append(' · ');
    el.append(h('a', { href: '#/about', title: t('source.credit.title', { name: c.name, licence: c.licenceName }), class: 'src-credit' }, c.name),
      h('span', { class: 'src-lic' }, ` (${c.licenceName})`));
  });
  for (const d of derived) el.append(' · ', h('span', { class: 'tag derived-tag', title: d.note }, t('source.derived', { note: derivedShort(d.note) })));
  return el;
}
