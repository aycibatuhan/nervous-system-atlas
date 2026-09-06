import type { App } from '../app.ts';
import { h, clear } from './dom.ts';
import { citeNode } from './cite.ts';
import type { Citation } from '../types/content.ts';
import { selectStructure, setStructureVisible } from '../state/actions.ts';
import { applyVisualState } from '../scene/materials.ts';

type Rec = Record<string, unknown>;

/** Renders a pathway entry into the right panel and highlights its waypoint meshes in order. */
export class PathwayPanel {
  private cleanup: (() => void) | null = null;
  constructor(private app: App, private container: HTMLElement) {}

  private html(s: unknown): HTMLElement { const d = h('div', { class: 'prose' }); d.innerHTML = String(s ?? ''); return d; }
  private cite(c: Citation): HTMLElement { return citeNode(this.app.content?.bibliography, c); }
  private meshForStructure(sid: string, preferred?: string): string | null {
    if (preferred && this.app.registry.byId.has(preferred)) return preferred;
    const st = this.app.content?.structures[sid] as Rec | undefined;
    const ids = (st?.['meshIds'] as string[] | undefined) ?? [];
    for (const id of ids) if (this.app.registry.byId.has(id)) return id;
    const m = this.app.manifest.meshes.find((x) => x.structureId === sid);
    return m ? m.id : null;
  }

  exit(): void { this.cleanup?.(); this.cleanup = null; }

  show(id: string): void {
    this.exit();
    const p = this.app.content?.pathways[id] as Rec | undefined;
    clear(this.container);
    if (!p) { this.container.append(h('p', { class: 'muted' }, `Pathway ${id} not found.`)); return; }
    const html = (p['html'] ?? {}) as Record<string, string>;
    const wps = p['waypoints'] as Rec[];
    // highlight waypoint meshes
    const shown: string[] = [];
    const meshIds = new Set<string>([...((p['meshIds'] as string[]) ?? []), ...wps.map((w) => this.meshForStructure(String(w['structureId']), w['meshId'] as string | undefined)).filter((x): x is string => !!x)]);
    for (const mid of meshIds) { if (!this.app.store.get().shownStructures.has(mid)) { setStructureVisible(this.app, mid, true); shown.push(mid); } }
    void this.app.registry.ensure(meshIds).then((meshes) => { for (const m of meshes) applyVisualState(m, 'involved'); this.app.sm.requestRender(); });
    this.cleanup = () => { for (const mid of shown) setStructureVisible(this.app, mid, false); for (const mid of meshIds) { const m = this.app.registry.get(mid); if (m) applyVisualState(m, 'normal'); } this.app.sm.requestRender(); };

    const stepList = h('ol', { class: 'waypoints' }, ...wps.map((w, i) => {
      const sid = String(w['structureId']); const st = this.app.content?.structures[sid] as Rec | undefined;
      const mid = this.meshForStructure(sid, w['meshId'] as string | undefined);
      const side = String(w['sideRelativeToOrigin']);
      return h('li', { class: `wp side-${side}`, onclick: () => { if (mid) selectStructure(this.app, mid, { moveSlices: true }); } },
        h('span', { class: 'wp-n' }, String(i + 1)), h('b', {}, String(st?.['name'] ?? sid)), h('span', { class: 'tag' }, side), w['note'] ? h('div', { class: 'muted small' }, String(w['note'])) : null);
    }));
    const dec = p['decussation'] as Rec | null;
    this.container.append(h('div', {},
      h('div', { class: 'content-head' }, h('span', { class: 'swatch big', style: 'background:#EDE3D2' }), h('div', {}, h('h2', {}, String(p['name'])), h('div', { class: 'crumbs' }, `pathway · ${p['type']} · ${p['modality']}`))),
      this.html(html['summary']),
      h('h3', {}, 'Neuron chain'), h('ol', {}, ...(p['neuronChain'] as Rec[]).map((n) => h('li', {}, h('b', {}, String(n['cellBody'])), ` → ${n['synapse']}`))),
      h('h3', {}, 'Decussation'), dec ? h('p', {}, h('b', {}, String(dec['level'])), `: ${dec['note']}`) : h('p', { class: 'muted' }, 'Uncrossed.'),
      h('h3', {}, 'Course (click a station to select it)'), stepList,
      h('h3', {}, 'Termination'), this.html(html['termination'] ?? p['termination']),
      p['somatotopy'] ? h('div', {}, h('h3', {}, 'Somatotopy'), this.html(html['somatotopy'] ?? p['somatotopy'])) : null,
      h('h3', {}, 'Lesion effects by level'), h('table', { class: 'tbl' }, h('tr', {}, h('th', {}, 'Level'), h('th', {}, 'Effects'), h('th', {}, 'Side')),
        ...(p['lesionEffectsByLevel'] as Rec[]).map((x) => h('tr', {}, h('td', {}, String(x['level'])), h('td', {}, String(x['effects'])), h('td', {}, String(x['side']))))),
      h('h3', {}, 'Pearls'), h('ul', {}, ...((p['clinical'] as Rec)['pearls'] as string[]).map((x) => h('li', {}, x))),
      ((p['clinical'] as Rec)['syndromes'] as string[]).length ? h('div', {}, h('h3', {}, 'Syndromes'), h('div', { class: 'chips' }, ...((p['clinical'] as Rec)['syndromes'] as string[]).map((sid) => h('a', { class: 'chip', href: `#/syndrome/${sid}` }, String((this.app.content?.syndromes[sid] as Rec | undefined)?.['name'] ?? sid))))) : null,
      h('h3', {}, 'Sources'), h('ul', {}, ...(p['citations'] as Rec[]).map((c) => h('li', {}, this.cite(c as unknown as Citation)))),
    ));
  }
}
