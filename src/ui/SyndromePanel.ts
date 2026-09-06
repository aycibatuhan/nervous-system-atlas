import type { App } from '../app.ts';
import { h, clear } from './dom.ts';
import { setSyndromeStep, meshesFor } from '../state/syndrome.ts';
import { selectStructure } from '../state/actions.ts';

type Rec = Record<string, unknown>;

/** Right panel while a syndrome is active. */
export class SyndromePanel {
  private currentId: string | null = null;
  constructor(private app: App, private container: HTMLElement) {
    app.store.subscribe((s) => s.syndrome?.step ?? -1, (step) => { for (const tr of Array.from(this.container.querySelectorAll('tr[data-step]'))) tr.classList.toggle('active', Number((tr as HTMLElement).dataset['step']) === step); });
  }
  private html(s: unknown): HTMLElement { const d = h('div', { class: 'prose' }); d.innerHTML = String(s ?? ''); for (const a of Array.from(d.querySelectorAll('a[href^="#/"]'))) a.addEventListener('click', (e) => { e.preventDefault(); location.hash = (a as HTMLAnchorElement).getAttribute('href')!; }); return d; }
  private cite(c: { book: string; chapter: number; pages: [number, number]; section?: string }): string {
    const src = this.app.content?.sources[c.book]; const p = c.pages[0] === c.pages[1] ? `p. ${c.pages[0]}` : `pp. ${c.pages[0]}–${c.pages[1]}`;
    return `${src?.cite ?? c.book} ch. ${c.chapter}, ${p}`;
  }
  private link(id: string): HTMLElement {
    const c = this.app.content; const st = (c?.structures[id] ?? c?.pathways[id] ?? c?.syndromes[id]) as Rec | undefined;
    const name = (st?.['name'] as string) ?? this.app.registry.byId.get(id)?.name ?? id;
    const kind = c?.pathways[id] ? 'pathway' : c?.syndromes[id] ? 'syndrome' : 'structure';
    return h('a', { class: 'xref', href: `#/${kind}/${id}`, onclick: (e: Event) => {
      if (kind === 'structure') { e.preventDefault(); const side = this.app.store.get().lesionSide ?? 'l'; const ms = meshesFor(this.app, id, side); if (ms[0]) selectStructure(this.app, ms[0], { moveSlices: true }); else location.hash = `#/structure/${id}`; }
    } }, name);
  }
  show(id: string): void {
    if (this.currentId === id && this.container.childElementCount) return;
    this.currentId = id; clear(this.container);
    const syn = this.app.content?.syndromes[id] as Rec | undefined;
    if (!syn) { this.container.append(h('p', { class: 'muted' }, `Syndrome ${id} not found.`)); return; }
    const html = (syn['html'] ?? {}) as Record<string, string>; const loc = syn['localisation'] as Rec; const step = this.app.store.get().syndrome?.step ?? 0;
    const deficits = (syn['deficits'] as Rec[]) ?? [];
    const pill = (t: string) => h('span', { class: 'tag' }, t);
    this.container.append(h('div', {},
      h('div', { class: 'content-head' }, h('span', { class: 'swatch big', style: 'background:#ff3030' }), h('div', {}, h('h2', {}, String(syn['name'])), h('div', { class: 'crumbs' }, `syndrome · ${syn['category']} · ${syn['tier']}` + (((syn['eponyms'] as string[]) ?? []).length ? ` · ${(syn['eponyms'] as string[]).join(', ')}` : '')))),
      h('div', { class: 'loc' }, pill(`side: ${loc['side']}`), loc['level'] ? pill(`level: ${loc['level']}`) : null, loc['arteryId'] ? this.link(String(loc['arteryId'])) : null, loc['territoryId'] ? this.link(String(loc['territoryId'])) : null),
      h('h3', {}, 'Presentation'), this.html(html['presentation'] ?? syn['presentation']),
      h('h3', {}, 'Deficits (click a row to spotlight its substrate)'),
      h('table', { class: 'tbl deficits' }, h('tr', {}, h('th', {}, '#'), h('th', {}, 'Modality'), h('th', {}, 'Side'), h('th', {}, 'Distribution'), h('th', {}, 'Sign'), h('th', {}, 'Substrate')),
        ...deficits.map((d, i) => h('tr', { 'data-step': String(i), class: i === step ? 'active' : '', onclick: () => setSyndromeStep(this.app, i) },
          h('td', {}, String(i + 1)), h('td', {}, pill(String(d['modality']))), h('td', {}, String(d['side'])), h('td', {}, String(d['distribution'])), h('td', {}, String(d['sign'])), h('td', {}, d['substrate'] ? this.link(String(d['substrate'])) : '')))),
      h('h3', {}, 'Localizing reasoning'), this.html(html['reasoning'] ?? syn['reasoning']),
      h('h3', {}, 'Structures involved'), h('div', { class: 'chips' }, ...((loc['structures'] as string[]) ?? []).map((sid) => this.link(sid))),
      h('h3', {}, 'Imaging'), h('table', { class: 'tbl' }, h('tr', {}, h('th', {}, 'Pathology'), h('th', {}, 'Modality'), h('th', {}, 'Finding')),
        ...((syn['imagingFindings'] as Rec[]) ?? []).map((p) => h('tr', {}, h('td', {}, String(p['pathology'])), h('td', {}, `${p['modality']}${p['sequence'] && p['sequence'] !== 'n/a' ? ' · ' + p['sequence'] : ''}`), h('td', {}, String(p['finding']), p['timing'] ? h('div', { class: 'muted small' }, `Timing: ${p['timing']}`) : null, p['pitfalls'] ? h('div', { class: 'muted small' }, `Pitfall: ${p['pitfalls']}`) : null)))),
      h('h3', {}, 'Common causes'), h('ul', {}, ...((syn['commonCauses'] as string[]) ?? []).map((x) => h('li', {}, x))),
      h('h3', {}, 'Mimics'), h('ul', {}, ...((syn['mimics'] as Rec[]) ?? []).map((m) => h('li', {}, h('b', {}, String(m['name'])), ` — ${m['howToDistinguish']}`))),
      ((syn['examSequence'] as string[]) ?? []).length ? h('div', {}, h('h3', {}, 'Bedside sequence'), h('ol', {}, ...(syn['examSequence'] as string[]).map((x) => h('li', {}, x)))) : null,
      h('h3', {}, 'Management pearls'), h('ul', {}, ...((syn['management'] as string[]) ?? []).map((x) => h('li', {}, x))),
      h('h3', {}, 'Sources'), h('ul', {}, ...((syn['citations'] as Rec[]) ?? []).map((c) => h('li', {}, this.cite(c as { book: string; chapter: number; pages: [number, number] })))),
    ));
  }
}
