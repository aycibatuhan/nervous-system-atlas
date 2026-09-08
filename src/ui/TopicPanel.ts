import type { App } from '../app.ts';
import { h, clear, enTag, secondaryName } from './dom.ts';
import { entryName, meshLabel, t, type Key, type NamedEntry, entriesOf } from '../i18n/index.ts';
import { citeNode } from './cite.ts';
import type { Citation } from '../types/content.ts';
import { applyStates } from '../state/actions.ts';
import { sourceLine } from './sourceLine.ts';

type Rec = Record<string, unknown>;
const CATEGORY_KEY: Record<string, Key> = {
  development: 'topic.cat.development', physiology: 'topic.cat.physiology', neurochemistry: 'topic.cat.neurochemistry',
  electrophysiology: 'topic.cat.electrophysiology', approach: 'topic.cat.approach', 'disease-pattern': 'topic.cat.disease-pattern',
  imaging: 'topic.cat.imaging', pediatric: 'topic.cat.pediatric', infection: 'topic.cat.infection', neoplasm: 'topic.cat.neoplasm',
};
/** Category label, or the raw category for one the interface does not know yet. */
const categoryLabel = (c: string): string => { const k = CATEGORY_KEY[c]; return k ? t(k) : c; };

/** Right panel for clinical topics (development, CSF physiology, transmitters, EEG, epilepsy, dementia, neuromuscular …).
 *  With no id it lists every topic by category; with an id it renders the sections and spotlights the topic's meshes. */
export class TopicPanel {
  private shown: string[] = [];
  private currentId: string | undefined;
  private current: Rec | undefined;
  constructor(private app: App, private container: HTMLElement) {
    app.store.subscribe((s) => s.locale, () => { if (this.container.childElementCount) this.show(this.currentId); });
  }

  /** A prose block from the content, tagged as still English while the interface is Turkish. */
  private prose(html: string): HTMLElement {
    const d = h('div', { class: 'prose' }); d.innerHTML = html;
    const tag = enTag(this.current); if (tag) d.prepend(tag);
    return d;
  }

  private nameOf(id: string): { primary: string; secondary: string | null } {
    const c = this.app.content;
    const e = (c?.structures[id] ?? c?.pathways[id] ?? c?.syndromes[id] ?? c?.topics?.[id]) as NamedEntry | undefined;
    return entryName(e, this.app.registry.byId.get(id)?.name ?? id);
  }
  private link(id: string): HTMLElement {
    const c = this.app.content;
    const kind = c?.syndromes[id] ? 'syndrome' : c?.pathways[id] ? 'pathway' : c?.topics?.[id] ? 'topic' : 'structure';
    const n = this.nameOf(id);
    return h('a', { class: 'chip', href: `#/${kind}/${id}`, title: n.secondary ?? undefined }, n.primary);
  }

  show(id?: string): void {
    clear(this.container);
    this.exit();
    this.currentId = id;
    const topics = entriesOf(this.app, 'topics');
    if (!id || !topics[id]) { this.index(topics); return; }
    const topic = topics[id] as Rec;
    this.current = topic;
    const title = entryName(topic as unknown as NamedEntry, String(topic['name'] ?? id));
    const html = (topic['html'] as Record<string, string>) ?? {};
    const sections = JSON.parse(html['sections'] ?? '[]') as string[];
    const secs = (topic['sections'] as { heading: string; body: string }[]) ?? [];
    const rel = (topic['related'] as Rec) ?? {};
    const imaging = topic['imaging'] as { normalAppearance?: string; pathology?: { pathology: string; modality: string; sequence?: string; finding: string; timing?: string; pitfalls?: string }[] } | undefined;
    const meshIds = ((topic['meshIds'] as string[]) ?? []).filter((m) => this.app.registry.byId.has(m));
    const cites = (topic['citations'] as unknown as Citation[]) ?? [];
    const bib = this.app.content?.bibliography;
    const el = h('div', {},
      h('div', { class: 'content-head' }, h('span', { class: 'swatch big', style: 'background:#7fb3d5' }),
        h('div', {}, h('h2', {}, title.primary, secondaryName(title)), h('div', { class: 'crumbs' }, t('topic.crumbs', { category: categoryLabel(String(topic['category'])) }), ...(((topic['synonyms'] as string[]) ?? []).length ? [` · ${(topic['synonyms'] as string[]).join(', ')}`] : [])))),
      this.prose(html['summary'] ?? String(topic['summary'])),
      ...secs.map((sec, i) => h('div', { class: 'topic-section' }, h('h3', {}, enTag(this.current), sec.heading), h('div', { class: 'prose', innerHTML: sections[i] ?? sec.body }))),
      h('h3', {}, enTag(this.current), t('topic.keyPoints')), h('ul', {}, ...((topic['keyPoints'] as string[]) ?? []).map((k) => h('li', {}, k))),
      ...(imaging && (imaging.normalAppearance || imaging.pathology?.length) ? [h('h3', {}, enTag(this.current), t('topic.imaging')),
        ...(imaging.normalAppearance ? [h('div', { class: 'prose', innerHTML: html['imaging.normalAppearance'] ?? imaging.normalAppearance })] : []),
        ...(imaging.pathology?.length ? [h('table', { class: 'tbl' }, h('thead', {}, h('tr', {}, h('th', {}, t('th.pathology')), h('th', {}, t('th.modality')), h('th', {}, t('th.finding')))),
          h('tbody', {}, ...imaging.pathology.map((p) => h('tr', {}, h('td', {}, p.pathology), h('td', {}, p.modality + (p.sequence ? ` · ${p.sequence}` : '')), h('td', {}, p.finding, p.timing ? h('div', { class: 'muted small' }, p.timing) : null, p.pitfalls ? h('div', { class: 'muted small' }, t('content.imaging.pitfall', { text: p.pitfalls })) : null)))))] : [])] : []),
      h('h3', {}, enTag(this.current), t('topic.pearls')), h('ul', {}, ...((topic['pearls'] as string[]) ?? []).map((k) => h('li', {}, k))),
      ...(((topic['pitfalls'] as string[]) ?? []).length ? [h('h3', {}, enTag(this.current), t('topic.pitfalls')), h('ul', {}, ...((topic['pitfalls'] as string[]) ?? []).map((k) => h('li', {}, k)))] : []),
      ...(meshIds.length ? [h('h3', {}, t('topic.inAtlas')), h('div', { class: 'chips' }, ...meshIds.map((m) => { const n = meshLabel(this.app, m); return h('a', { class: 'chip', href: `#/structure/${m}`, title: n.secondary ?? undefined }, n.primary); })), sourceLine(this.app, meshIds)] : []),
      ...(['structureIds', 'pathwayIds', 'syndromeIds', 'topicIds'].some((k) => ((rel[k] as string[]) ?? []).length) ? [h('h3', {}, t('topic.related')),
        h('div', { class: 'chips' }, ...['structureIds', 'pathwayIds', 'syndromeIds', 'topicIds'].flatMap((k) => ((rel[k] as string[]) ?? []).map((r) => this.link(r))))] : []),
      h('h3', {}, t('topic.sources')), h('ul', { class: 'cites' }, ...cites.map((c) => h('li', {}, citeNode(bib, c)))),
      h('div', { class: 'muted small' }, h('a', { href: '#/topic' }, t('topic.all'))),
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
    const el = h('div', {}, h('div', { class: 'content-head' }, h('span', { class: 'swatch big', style: 'background:#7fb3d5' }), h('div', {}, h('h2', {}, t('topic.title')), h('div', { class: 'crumbs' }, t('topic.count', { n: list.length })))));
    for (const [cat, items] of [...byCat.entries()].sort()) {
      el.append(h('h3', {}, categoryLabel(cat)));
      el.append(h('ul', { class: 'topic-list' }, ...items.sort((a, b) => String(a['name']).localeCompare(String(b['name']))).map((x) => {
        const n = entryName(x as unknown as NamedEntry, String(x['id']));
        return h('li', {}, h('a', { href: `#/topic/${String(x['id'])}` }, n.primary, secondaryName(n)), h('div', { class: 'muted small' }, enTag(this.current), String(x['summary']).slice(0, 140) + '…'));
      })));
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
