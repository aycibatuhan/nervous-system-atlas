import type { App } from '../app.ts';
import { h, clear } from './dom.ts';
import { applyStates, setStructureVisible } from '../state/actions.ts';

type Rec = Record<string, unknown>;

/** Right panel quiz: original vignettes; answering reveals the explanation and spotlights the target meshes. */
export class QuizPanel {
  private index = 0;
  private answered = new Map<number, string>();
  private shown: string[] = [];
  private ids: string[] = [];
  constructor(private app: App, private container: HTMLElement) {}
  private items(): Rec[] { return this.ids.map((id) => this.app.content!.quiz[id] as Rec); }
  private clearHighlight(): void {
    for (const m of this.shown) setStructureVisible(this.app, m, false);
    this.shown = [];
    if (this.app.store.get().involved.size) this.app.store.set({ involved: new Set(), stepHighlight: new Set() });
    applyStates(this.app);
  }
  exit(): void { this.clearHighlight(); }
  private highlight(ids: string[]): void {
    this.clearHighlight();
    const valid = ids.filter((m) => this.app.registry.byId.has(m));
    for (const m of valid) if (!this.app.store.get().shownStructures.has(m)) { setStructureVisible(this.app, m, true); this.shown.push(m); }
    this.app.store.set({ involved: new Set(valid), stepHighlight: new Set() });
    void this.app.registry.ensure(valid).then(() => { applyStates(this.app); const first = valid[0] && this.app.registry.byId.get(valid[0]); if (first) { const c = first.centroid; this.app.store.set({ slices: { ...this.app.store.get().slices, sagittal: Math.round(c[0]), coronal: Math.round(c[1]), axial: Math.round(c[2]) } }); } });
  }
  private link(id: string, kind: 'structure' | 'syndrome' | 'pathway'): HTMLElement {
    const c = this.app.content!; const e = (kind === 'structure' ? c.structures[id] : kind === 'syndrome' ? c.syndromes[id] : c.pathways[id]) as Rec | undefined;
    return h('a', { class: 'chip', href: `#/${kind}/${id}` }, String(e?.['name'] ?? id));
  }
  show(index?: number): void {
    if (!this.app.content) { clear(this.container); this.container.append(h('p', { class: 'muted' }, 'Content not loaded.')); return; }
    if (!this.ids.length) this.ids = Object.keys(this.app.content.quiz).sort();
    if (index !== undefined) this.index = Math.max(0, Math.min(this.ids.length - 1, index));
    this.render();
  }
  private choose(key: string): void {
    if (this.answered.has(this.index)) return;
    this.answered.set(this.index, key);
    const q = this.items()[this.index]!;
    this.highlight((q['highlightOnReveal'] as string[]) ?? []);
    this.render();
  }
  private go(delta: number): void { this.clearHighlight(); this.index = Math.max(0, Math.min(this.ids.length - 1, this.index + delta)); this.app.store.set({ panel: { kind: 'quiz', index: this.index } }); this.render(); }
  private render(): void {
    clear(this.container);
    const items = this.items(); const q = items[this.index]; if (!q) return;
    const given = this.answered.get(this.index); const correct = String(q['answer']);
    const score = [...this.answered.entries()].filter(([i, k]) => String(items[i]?.['answer']) === k).length;
    const targets = q['targets'] as Rec;
    this.container.append(h('div', {},
      h('div', { class: 'content-head' }, h('span', { class: 'swatch big', style: 'background:#4e79a7' }), h('div', {}, h('h2', {}, `Clinical vignette ${this.index + 1} of ${items.length}`), h('div', { class: 'crumbs' }, `${q['type']} · difficulty ${q['difficulty']}/3 · score ${score}/${this.answered.size}`))),
      h('p', { class: 'vignette' }, String(q['vignette'])),
      h('p', {}, h('b', {}, String(q['stem']))),
      h('div', { class: 'options' }, ...(q['options'] as Rec[]).map((o) => { const k = String(o['key']); const cls = given ? (k === correct ? 'opt right' : k === given ? 'opt wrong' : 'opt') : 'opt'; return h('button', { class: cls, onclick: () => this.choose(k) }, h('b', {}, k), ' ', String(o['text'])); })),
      given ? h('div', { class: given === correct ? 'reveal ok' : 'reveal bad' }, h('b', {}, given === correct ? 'Correct.' : `Not quite: the answer is ${correct}.`), h('p', {}, String(q['explanation'])),
        h('div', { class: 'chips' }, ...((targets['structureIds'] as string[]) ?? []).map((id) => this.link(id, 'structure')), ...((targets['syndromeIds'] as string[]) ?? []).map((id) => this.link(id, 'syndrome')), ...((targets['pathwayIds'] as string[]) ?? []).map((id) => this.link(id, 'pathway'))),
        h('p', { class: 'muted small' }, 'Sources: ' + ((q['citations'] as Rec[]) ?? []).map((c) => `${this.app.content!.sources[String(c['book'])]?.cite ?? c['book']} ch. ${c['chapter']} pp. ${(c['pages'] as number[]).join('–')}`).join('; '))) : h('p', { class: 'muted small' }, 'Choose an answer (keys A–E). The relevant structures are highlighted in 3D after you answer.'),
      h('div', { class: 'quiz-nav' }, h('button', { disabled: this.index === 0 ? 'true' : null, onclick: () => this.go(-1) }, '◀ Previous'), h('button', { disabled: this.index >= items.length - 1 ? 'true' : null, onclick: () => this.go(1) }, 'Next ▶'), h('button', { onclick: () => { this.answered.clear(); this.go(-this.index); } }, 'Restart')),
    ));
  }
  key(k: string): void { if (/^[a-eA-E]$/.test(k)) this.choose(k.toUpperCase()); else if (k === 'ArrowRight') this.go(1); else if (k === 'ArrowLeft') this.go(-1); }
}
