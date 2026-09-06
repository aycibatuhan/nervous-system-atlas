import type { App } from '../app.ts';
import type { ManifestMesh, SystemId } from '../types/manifest.ts';
import { h, clear } from './dom.ts';
import { meshShouldBeVisible, selectStructure, setStructureVisible, toggleSystem } from '../state/actions.ts';
import { sameSet } from '../state/actions.ts';

/** Left panel: systems → subsystems → structures with tri-state checkboxes; click a name to select. */
export class TreePanel {
  private root: HTMLElement;
  private rows = new Map<string, HTMLElement>();
  private sysBoxes = new Map<SystemId, HTMLInputElement>();
  private open = new Set<string>();
  private filter = '';

  constructor(private app: App, container: HTMLElement) {
    this.root = h('div', { class: 'tree' });
    const search = h('input', { class: 'tree-filter', type: 'search', placeholder: 'Filter structures…', oninput: (e: Event) => { this.filter = (e.target as HTMLInputElement).value.toLowerCase(); this.render(); } });
    container.append(h('div', { class: 'panel-head' }, 'Structures'), search, this.root);
    this.render();
    app.store.subscribe((s) => s.visibleSystems, () => this.syncChecks(), sameSet);
    app.store.subscribe((s) => s.hiddenStructures, () => this.syncChecks(), sameSet);
    app.store.subscribe((s) => s.shownStructures, () => this.syncChecks(), sameSet);
    app.store.subscribe((s) => s.selectedId, (id, prev) => { this.mark(prev, false); this.mark(id, true); if (id) this.reveal(id); });
  }

  private mark(id: string | null, on: boolean): void { const r = id ? this.rows.get(id) : null; r?.classList.toggle('selected', on); }

  private reveal(id: string): void {
    const m = this.app.registry.byId.get(id); if (!m) return;
    this.open.add(m.system); this.open.add(`${m.system}/${m.subsystem ?? ''}`);
    this.render();
    this.rows.get(id)?.scrollIntoView({ block: 'nearest' });
  }

  render(): void {
    clear(this.root); this.rows.clear(); this.sysBoxes.clear();
    const s = this.app.store.get();
    for (const sys of this.app.manifest.systems) {
      const meshes = (this.app.registry.bySystem.get(sys.id) ?? []).filter((m) => s.showNc || !m.nc);
      const matching = this.filter ? meshes.filter((m) => (m.name + ' ' + m.structureId).toLowerCase().includes(this.filter)) : meshes;
      if (!matching.length) continue;
      const isOpen = this.open.has(sys.id) || !!this.filter;
      const box = h('input', { type: 'checkbox', checked: s.visibleSystems.has(sys.id), onclick: (e: Event) => { e.stopPropagation(); toggleSystem(this.app, sys.id, (e.target as HTMLInputElement).checked); } });
      this.sysBoxes.set(sys.id, box);
      const head = h('div', { class: 'tree-sys', onclick: () => { if (this.open.has(sys.id)) this.open.delete(sys.id); else this.open.add(sys.id); this.render(); } },
        h('span', { class: 'caret' }, isOpen ? '▾' : '▸'), box, h('span', { class: 'swatch', style: `background:${sys.colour}` }), h('span', { class: 'name' }, sys.name),
        h('span', { class: 'count' }, String(matching.length)));
      this.root.append(head);
      if (!isOpen) continue;
      // group by subsystem
      const groups = new Map<string, ManifestMesh[]>();
      for (const m of matching) { const k = m.subsystem ?? ''; (groups.get(k) ?? groups.set(k, []).get(k)!).push(m); }
      for (const [sub, list] of groups) {
        const key = `${sys.id}/${sub}`;
        if (sub && groups.size > 1) {
          const subOpen = this.open.has(key) || !!this.filter;
          this.root.append(h('div', { class: 'tree-sub', onclick: () => { if (this.open.has(key)) this.open.delete(key); else this.open.add(key); this.render(); } },
            h('span', { class: 'caret' }, subOpen ? '▾' : '▸'), h('span', { class: 'name' }, sub.replace(/-/g, ' ')), h('span', { class: 'count' }, String(list.length))));
          if (!subOpen) continue;
        }
        for (const m of list) this.root.append(this.row(m));
      }
    }
  }

  private row(m: ManifestMesh): HTMLElement {
    const vis = meshShouldBeVisible(this.app, m.id);
    const cb = h('input', { type: 'checkbox', checked: vis, onclick: (e: Event) => { e.stopPropagation(); setStructureVisible(this.app, m.id, (e.target as HTMLInputElement).checked); } });
    const row = h('div', { class: 'tree-row' + (this.app.store.get().selectedId === m.id ? ' selected' : ''), dataset: { id: m.id },
      onclick: () => selectStructure(this.app, m.id, { fit: false }), ondblclick: () => selectStructure(this.app, m.id, { fit: true }) },
      cb, h('span', { class: 'swatch', style: `background:${m.colour}` }), h('span', { class: 'name', title: `${m.source} · ${m.alignment}` }, m.name),
      m.nc ? h('span', { class: 'tag', title: 'non-commercial licence' }, 'NC') : null);
    this.rows.set(m.id, row);
    return row;
  }

  private syncChecks(): void {
    const s = this.app.store.get();
    for (const [sys, box] of this.sysBoxes) box.checked = s.visibleSystems.has(sys);
    for (const [id, row] of this.rows) (row.querySelector('input') as HTMLInputElement).checked = meshShouldBeVisible(this.app, id);
  }
}
