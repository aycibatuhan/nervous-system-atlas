import type { App } from '../app.ts';
import { h, clear } from './dom.ts';
import { citeNode } from './cite.ts';
import type { Citation } from '../types/content.ts';
import { applyStates } from '../state/actions.ts';

type Rec = Record<string, unknown>;
const CATEGORY_LABEL: Record<string, string> = {
  development: 'Development', physiology: 'Physiology', neurochemistry: 'Neurotransmitters', electrophysiology: 'EEG & sleep', approach: 'Clinical approach',
  'disease-pattern': 'Disease patterns', imaging: 'Imaging', pediatric: 'Pediatric', infection: 'Infection', neoplasm: 'Neoplasm',
};

/** Right panel for clinical topics (development, CSF physiology, transmitters, EEG, epilepsy, dementia, neuromuscular …).
 *  With no id it lists every topic by category; with an id it renders the sections and spotlights the topic's meshes. */
export class TopicPanel {
  private shown: string[] = [];
  constructor(private app: App, private container: HTMLElement) {}

  private nameOf(id: string): string {
    const c = this.app.content; if (!c) return id;
    const e = c.structures[id] ?? c.pathways[id] ?? c.syndromes[id] ?? c.topics?.[id];
    return e ? String(e.name) : (this.app.registry.byId.get(id)?.name ?? id);
  }
  private link(id: string): HTMLElement {
    const c = this.app.content;
    const kind = c?.syndromes[id] ? 'syndrome' : c?.pathways[id] ? 'pathway' : c?.topics?.[id] ? 'topic' : 'structure';
    return h('a', { class: 'chip', href: `#/${kind}/${id}` }, this.nameOf(id));
  }

  show(id?: string): void {
    clear(this.container);
    this.exit();
    const topics = this.app.content?.topics ?? {};
    if (!id || !topics[id]) { this.index(topics); return; }
    const t = topics[id] as Rec;
    const html = (t['html'] as Record<string, string>) ?? {};
    const sections = JSON.parse(html['sections'] ?? '[]') as string[];
    const secs = (t['sections'] as { heading: string; body: string }[]) ?? [];
    const rel = (t['related'] as Rec) ?? {};
    const imaging = t['imaging'] as { normalAppearance?: string; pathology?: { pathology: string; modality: string; sequence?: string; finding: string; timing?: string; pitfalls?: string }[] } | undefined;
    const meshIds = ((t['meshIds'] as string[]) ?? []).filter((m) => this.app.registry.byId.has(m));
    const cites = (t['citations'] as unknown as Citation[]) ?? [];
    const bib = this.app.content?.bibliography;
    const el = h('div', {},
      h('div', { class: 'content-head' }, h('span', { class: 'swatch big', style: 'background:#7fb3d5' }),
        h('div', {}, h('h2', {}, String(t['name'])), h('div', { class: 'crumbs' }, `Topic · ${CATEGORY_LABEL[String(t['category'])] ?? String(t['category'])}`, ...(((t['synonyms'] as string[]) ?? []).length ? [` · ${(t['synonyms'] as string[]).join(', ')}`] : [])))),
      h('div', { class: 'prose', innerHTML: html['summary'] ?? String(t['summary']) }),
      ...secs.map((s, i) => h('div', { class: 'topic-section' }, h('h3', {}, s.heading), h('div', { class: 'prose', innerHTML: sections[i] ?? s.body }))),
      h('h3', {}, 'Key points'), h('ul', {}, ...((t['keyPoints'] as string[]) ?? []).map((k) => h('li', {}, k))),
      ...(imaging && (imaging.normalAppearance || imaging.pathology?.length) ? [h('h3', {}, 'Imaging'),
        ...(imaging.normalAppearance ? [h('div', { class: 'prose', innerHTML: html['imaging.normalAppearance'] ?? imaging.normalAppearance })] : []),
        ...(imaging.pathology?.length ? [h('table', { class: 'tbl' }, h('thead', {}, h('tr', {}, h('th', {}, 'Pathology'), h('th', {}, 'Modality'), h('th', {}, 'Finding'))),
          h('tbody', {}, ...imaging.pathology.map((p) => h('tr', {}, h('td', {}, p.pathology), h('td', {}, p.modality + (p.sequence ? ` · ${p.sequence}` : '')), h('td', {}, p.finding, p.timing ? h('div', { class: 'muted small' }, p.timing) : null, p.pitfalls ? h('div', { class: 'muted small' }, `Pitfall: ${p.pitfalls}`) : null)))))] : [])] : []),
      h('h3', {}, 'Pearls'), h('ul', {}, ...((t['pearls'] as string[]) ?? []).map((k) => h('li', {}, k))),
      ...(((t['pitfalls'] as string[]) ?? []).length ? [h('h3', {}, 'Pitfalls'), h('ul', {}, ...((t['pitfalls'] as string[]) ?? []).map((k) => h('li', {}, k)))] : []),
      ...(meshIds.length ? [h('h3', {}, 'In the atlas'), h('div', { class: 'chips' }, ...meshIds.map((m) => h('a', { class: 'chip', href: `#/structure/${m}` }, this.app.registry.byId.get(m)!.name)))] : []),
      ...(['structureIds', 'pathwayIds', 'syndromeIds', 'topicIds'].some((k) => ((rel[k] as string[]) ?? []).length) ? [h('h3', {}, 'Related'),
        h('div', { class: 'chips' }, ...['structureIds', 'pathwayIds', 'syndromeIds', 'topicIds'].flatMap((k) => ((rel[k] as string[]) ?? []).map((r) => this.link(r))))] : []),
      h('h3', {}, 'Sources'), h('ul', { class: 'cites' }, ...cites.map((c) => h('li', {}, citeNode(bib, c)))),
      h('div', { class: 'muted small' }, h('a', { href: '#/topic' }, '← all topics')),
    );
    this.container.append(el);
    // spotlight the topic's meshes in the 3D view
    if (meshIds.length) {
      this.shown = meshIds;
      void this.app.registry.ensure(meshIds).then(() => {
        const st = this.app.store.get();
        const shown = new Set(st.shownStructures); for (const m of meshIds) shown.add(m);
        this.app.store.set({ shownStructures: shown, involved: new Set(meshIds) });
        applyStates(this.app);
      });
    }
  }

  private index(topics: Record<string, unknown>): void {
    const list = Object.values(topics).map((x) => x as Rec);
    const byCat = new Map<string, Rec[]>();
    for (const t of list) { const c = String(t['category']); byCat.set(c, [...(byCat.get(c) ?? []), t]); }
    const el = h('div', {}, h('div', { class: 'content-head' }, h('span', { class: 'swatch big', style: 'background:#7fb3d5' }), h('div', {}, h('h2', {}, 'Clinical topics'), h('div', { class: 'crumbs' }, `${list.length} topics`))));
    for (const [cat, items] of [...byCat.entries()].sort()) {
      el.append(h('h3', {}, CATEGORY_LABEL[cat] ?? cat));
      el.append(h('ul', { class: 'topic-list' }, ...items.sort((a, b) => String(a['name']).localeCompare(String(b['name']))).map((t) => h('li', {}, h('a', { href: `#/topic/${t['id']}` }, String(t['name'])), h('div', { class: 'muted small' }, String(t['summary']).slice(0, 140) + '…')))));
    }
    this.container.append(el);
  }

  /** Clear the spotlight when leaving a topic (never touch an active syndrome). */
  exit(): void {
    if (!this.shown.length) return;
    const st = this.app.store.get();
    if (!st.syndrome) {
      const shown = new Set(st.shownStructures); for (const m of this.shown) shown.delete(m);
      this.app.store.set({ shownStructures: shown, involved: new Set() });
      applyStates(this.app);
    }
    this.shown = [];
  }
}
