import type { App } from '../app.ts';
import type { ManifestMesh, SystemId } from '../types/manifest.ts';
import { h, clear } from './dom.ts';
import { meshShouldBeVisible, resetSystems, selectStructure, setAllSystems, setStructureVisible, soloGroup, toggleGroup } from '../state/actions.ts';
import { sameSet } from '../state/actions.ts';

type GroupBox = { box: HTMLInputElement; ids: string[] };

/** Left panel: systems → subsystems → structures with tri-state checkboxes; click a name to select. */
export class TreePanel {
  private root: HTMLElement;
  private rows = new Map<string, HTMLElement>();
  /** every group row (system or subsystem) with the mesh ids it governs, for the tri-state sync */
  private groups = new Map<string, GroupBox>();
  private master: HTMLInputElement;
  private open = new Set<string>();
  private filter = '';

  constructor(private app: App, container: HTMLElement) {
    this.root = h('div', { class: 'tree' });
    const search = h('input', { class: 'tree-filter', type: 'search', placeholder: 'Filter structures…', oninput: (e: Event) => { this.filter = (e.target as HTMLInputElement).value.toLowerCase(); this.render(); } });
    this.master = h('input', { type: 'checkbox', class: 'master-box', title: 'Show or hide every structure in the atlas',
      onclick: (e: Event) => { e.stopPropagation(); setAllSystems(this.app, (e.target as HTMLInputElement).checked); } });
    const masterRow = h('div', { class: 'tree-master' }, this.master,
      h('span', { class: 'name', onclick: () => { this.master.checked = !this.master.checked; setAllSystems(this.app, this.master.checked); } }, 'All structures'),
      h('button', { class: 'mini', title: 'Back to the default view', onclick: (e: Event) => { e.stopPropagation(); resetSystems(this.app); } }, 'Defaults'));
    container.append(h('div', { class: 'panel-head' }, 'Structures'), masterRow, search, this.root);
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

  /** how much of a group is on right now: all / none / some (→ indeterminate) */
  private groupState(ids: readonly string[]): 'all' | 'none' | 'some' {
    let on = 0;
    for (const id of ids) if (meshShouldBeVisible(this.app, id)) on++;
    return on === 0 ? 'none' : on === ids.length ? 'all' : 'some';
  }

  private setBox(box: HTMLInputElement, state: 'all' | 'none' | 'some'): void {
    box.checked = state === 'all';
    box.indeterminate = state === 'some';
  }

  /** the checkbox + solo handler shared by system and subsystem rows */
  private groupBox(key: string, ids: string[], system?: SystemId): HTMLInputElement {
    const box = h('input', { type: 'checkbox', onclick: (e: Event) => { e.stopPropagation(); toggleGroup(this.app, ids, (e.target as HTMLInputElement).checked, system); } });
    this.setBox(box, this.groupState(ids));
    this.groups.set(key, { box, ids });
    return box;
  }

  render(): void {
    clear(this.root); this.rows.clear(); this.groups.clear();
    const s = this.app.store.get();
    for (const sys of this.app.manifest.systems) {
      const meshes = (this.app.registry.bySystem.get(sys.id) ?? []).filter((m) => s.showNc || !m.nc);
      const matching = this.filter ? meshes.filter((m) => (m.name + ' ' + m.structureId).toLowerCase().includes(this.filter)) : meshes;
      if (!matching.length) continue;
      const isOpen = this.open.has(sys.id) || !!this.filter;
      const ids = matching.map((m) => m.id);
      const box = this.groupBox(sys.id, ids, sys.id);
      const head = h('div', { class: 'tree-sys', title: 'Click to expand · Alt-click to show only this system',
        onclick: (e: MouseEvent) => {
          if (e.altKey) { soloGroup(this.app, ids); return; }
          if (this.open.has(sys.id)) this.open.delete(sys.id); else this.open.add(sys.id);
          this.render();
        } },
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
          const subIds = list.map((m) => m.id);
          this.root.append(h('div', { class: 'tree-sub', dataset: { group: key }, title: 'Click to expand · Alt-click to show only this group',
            onclick: (e: MouseEvent) => {
              if (e.altKey) { soloGroup(this.app, subIds); return; }
              if (this.open.has(key)) this.open.delete(key); else this.open.add(key);
              this.render();
            } },
            h('span', { class: 'caret' }, subOpen ? '▾' : '▸'), this.groupBox(key, subIds), h('span', { class: 'name' }, sub.replace(/-/g, ' ')), h('span', { class: 'count' }, String(list.length))));
          if (!subOpen) continue;
        }
        for (const m of list) this.root.append(this.row(m));
      }
    }
    this.syncMaster();
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

  private syncMaster(): void {
    const s = this.app.store.get();
    const all = this.app.manifest.meshes.filter((m) => s.showNc || !m.nc).map((m) => m.id);
    this.setBox(this.master, this.groupState(all));
  }

  private syncChecks(): void {
    for (const { box, ids } of this.groups.values()) this.setBox(box, this.groupState(ids));
    for (const [id, row] of this.rows) (row.querySelector('input') as HTMLInputElement).checked = meshShouldBeVisible(this.app, id);
    this.syncMaster();
  }
}
