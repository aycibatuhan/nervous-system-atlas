import type { App } from '../app.ts';
import { h, clear, enTag, secondaryName } from './dom.ts';
import { entryName, t, type NamedEntry } from '../i18n/index.ts';
import { citeNode } from './cite.ts';
import type { Citation } from '../types/content.ts';
import { setSyndromeStep, meshesFor } from '../state/syndrome.ts';
import { selectStructure } from '../state/actions.ts';

type Rec = Record<string, unknown>;

/** Right panel while a syndrome is active. */
export class SyndromePanel {
  private currentId: string | null = null;
  constructor(private app: App, private container: HTMLElement) {
    app.store.subscribe((s) => s.syndrome?.step ?? -1, (step) => { for (const row of Array.from(this.container.querySelectorAll('tr[data-step]'))) row.classList.toggle('active', Number((row as HTMLElement).dataset['step']) === step); });
    // a language switch rebuilds the open syndrome in place
    app.store.subscribe((s) => s.locale, () => { const id = this.currentId; if (id && this.container.childElementCount) { this.currentId = null; this.show(id); } });
  }
  private html(s: unknown): HTMLElement {
    const d = h('div', { class: 'prose' }); d.innerHTML = String(s ?? '');
    for (const a of Array.from(d.querySelectorAll('a[href^="#/"]'))) a.addEventListener('click', (e) => { e.preventDefault(); location.hash = (a as HTMLAnchorElement).getAttribute('href')!; });
    const tag = enTag(); if (tag) d.prepend(tag);
    return d;
  }
  private cite(c: Citation): HTMLElement { return citeNode(this.app.content?.bibliography, c); }
  private link(id: string): HTMLElement {
    const c = this.app.content; const st = (c?.structures[id] ?? c?.pathways[id] ?? c?.syndromes[id]) as NamedEntry | undefined;
    const n = entryName(st, this.app.registry.byId.get(id)?.name ?? id);
    const kind = c?.pathways[id] ? 'pathway' : c?.syndromes[id] ? 'syndrome' : 'structure';
    return h('a', { class: 'xref', href: `#/${kind}/${id}`, title: n.secondary ?? undefined, onclick: (e: Event) => {
      if (kind === 'structure') { e.preventDefault(); const side = this.app.store.get().lesionSide ?? 'l'; const ms = meshesFor(this.app, id, side); if (ms[0]) selectStructure(this.app, ms[0], { moveSlices: true }); else location.hash = `#/structure/${id}`; }
    } }, n.primary);
  }
  show(id: string): void {
    if (this.currentId === id && this.container.childElementCount) return;
    this.currentId = id; clear(this.container);
    const syn = this.app.content?.syndromes[id] as Rec | undefined;
    if (!syn) { this.container.append(h('p', { class: 'muted' }, t('syndrome.notFound', { id }))); return; }
    const html = (syn['html'] ?? {}) as Record<string, string>; const loc = syn['localisation'] as Rec; const step = this.app.store.get().syndrome?.step ?? 0;
    const deficits = (syn['deficits'] as Rec[]) ?? [];
    const pill = (text: string) => h('span', { class: 'tag' }, text);
    const name = entryName(syn as unknown as NamedEntry, id);
    this.container.append(h('div', {},
      h('div', { class: 'content-head' }, h('span', { class: 'swatch big', style: 'background:#ff3030' }), h('div', {}, h('h2', {}, name.primary, secondaryName(name)), h('div', { class: 'crumbs' }, t('syndrome.crumbs', { category: String(syn['category']), tier: String(syn['tier']) }) + (((syn['eponyms'] as string[]) ?? []).length ? ` · ${(syn['eponyms'] as string[]).join(', ')}` : '')))),
      h('div', { class: 'loc' }, pill(t('syndrome.loc.side', { side: String(loc['side']) })), loc['level'] ? pill(t('syndrome.loc.level', { level: String(loc['level']) })) : null, loc['arteryId'] ? this.link(String(loc['arteryId'])) : null, loc['territoryId'] ? this.link(String(loc['territoryId'])) : null),
      h('h3', {}, t('syndrome.presentation')), this.html(html['presentation'] ?? syn['presentation']),
      h('h3', {}, enTag(), t('syndrome.deficits')),
      h('table', { class: 'tbl deficits' }, h('tr', {}, h('th', {}, t('th.num')), h('th', {}, t('th.modality')), h('th', {}, t('th.side')), h('th', {}, t('th.distribution')), h('th', {}, t('th.sign')), h('th', {}, t('th.substrate'))),
        ...deficits.map((d, i) => h('tr', { 'data-step': String(i), class: i === step ? 'active' : '', onclick: () => setSyndromeStep(this.app, i) },
          h('td', {}, String(i + 1)), h('td', {}, pill(String(d['modality']))), h('td', {}, String(d['side'])), h('td', {}, String(d['distribution'])), h('td', {}, String(d['sign'])), h('td', {}, d['substrate'] ? this.link(String(d['substrate'])) : '')))),
      h('h3', {}, t('syndrome.reasoning')), this.html(html['reasoning'] ?? syn['reasoning']),
      h('h3', {}, t('syndrome.structures')), h('div', { class: 'chips' }, ...((loc['structures'] as string[]) ?? []).map((sid) => this.link(sid))),
      h('h3', {}, enTag(), t('syndrome.imaging')), h('table', { class: 'tbl' }, h('tr', {}, h('th', {}, t('th.pathology')), h('th', {}, t('th.modality')), h('th', {}, t('th.finding'))),
        ...((syn['imagingFindings'] as Rec[]) ?? []).map((p) => h('tr', {}, h('td', {}, String(p['pathology'])), h('td', {}, `${p['modality']}${p['sequence'] && p['sequence'] !== 'n/a' ? ' · ' + p['sequence'] : ''}`), h('td', {}, String(p['finding']), p['timing'] ? h('div', { class: 'muted small' }, t('content.imaging.timing', { text: String(p['timing']) })) : null, p['pitfalls'] ? h('div', { class: 'muted small' }, t('content.imaging.pitfall', { text: String(p['pitfalls']) })) : null)))),
      h('h3', {}, enTag(), t('syndrome.causes')), h('ul', {}, ...((syn['commonCauses'] as string[]) ?? []).map((x) => h('li', {}, x))),
      h('h3', {}, enTag(), t('syndrome.mimics')), h('ul', {}, ...((syn['mimics'] as Rec[]) ?? []).map((m) => h('li', {}, h('b', {}, String(m['name'])), ` — ${m['howToDistinguish']}`))),
      ((syn['examSequence'] as string[]) ?? []).length ? h('div', {}, h('h3', {}, enTag(), t('syndrome.examSequence')), h('ol', {}, ...(syn['examSequence'] as string[]).map((x) => h('li', {}, x)))) : null,
      h('h3', {}, enTag(), t('syndrome.management')), h('ul', {}, ...((syn['management'] as string[]) ?? []).map((x) => h('li', {}, x))),
      h('h3', {}, t('syndrome.sources')), h('ul', {}, ...((syn['citations'] as Rec[]) ?? []).map((c) => h('li', {}, this.cite(c as unknown as Citation)))),
    ));
  }
}
