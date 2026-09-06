import type { App } from '../app.ts';
import { h, clear } from './dom.ts';
import { selectStructure } from '../state/actions.ts';

/** Right panel. Until content entries are authored it shows the manifest facts for the selected mesh. */
export class ContentPanel {
  private body: HTMLElement;
  constructor(private app: App, container: HTMLElement) {
    this.body = h('div', { class: 'content' });
    container.append(this.body);
    this.render();
    app.store.subscribe((s) => s.selectedId, () => this.render());
    app.store.subscribe((s) => s.hoverId, (id) => { const el = this.body.querySelector('.hover-name'); if (el) el.textContent = id ? (app.registry.byId.get(id)?.name ?? '') : ''; });
  }

  render(): void {
    clear(this.body);
    const s = this.app.store.get();
    const m = s.selectedId ? this.app.registry.byId.get(s.selectedId) : undefined;
    if (!m) {
      this.body.append(h('div', { class: 'empty' },
        h('h2', {}, 'Select a structure'),
        h('p', {}, 'Click a mesh in the 3D view, click the MRI slice, or pick a structure from the tree on the left.'),
        h('p', { class: 'muted' }, 'Hover: ', h('span', { class: 'hover-name' }))));
      return;
    }
    const lic = this.app.manifest.licenses[m.license];
    const related = this.app.manifest.meshes.filter((x) => x.structureId === m.structureId && x.id !== m.id);
    const entry = this.app.content?.structures[m.structureId];
    this.body.append(h('div', {},
      h('div', { class: 'content-head' },
        h('span', { class: 'swatch big', style: `background:${m.colour}` }),
        h('div', {}, h('h2', {}, m.name), h('div', { class: 'crumbs' }, `${m.system}${m.subsystem ? ' › ' + m.subsystem : ''} · ${m.side}`))),
      entry ? h('div', { class: 'summary' }, String(entry['summary'] ?? '')) : h('p', { class: 'muted' }, 'No authored content yet for ', h('code', {}, m.structureId), '.'),
      h('dl', { class: 'facts' },
        h('dt', {}, 'Centroid (MNI mm)'), h('dd', {}, m.centroid.map((v) => v.toFixed(0)).join(', ')),
        h('dt', {}, 'Source'), h('dd', {}, `${m.source} · ${m.alignment}`),
        h('dt', {}, 'Licence'), h('dd', {}, lic ? h('a', { href: lic.url, target: '_blank' }, lic.name) : m.license),
        h('dt', {}, 'Mesh'), h('dd', {}, `${m.triangles.toLocaleString()} triangles · ${(m.bytes / 1024).toFixed(0)} KB`)),
      related.length ? h('div', { class: 'related' }, 'Related: ', ...related.map((r) => h('a', { href: '#', onclick: (e: Event) => { e.preventDefault(); selectStructure(this.app, r.id); } }, r.name))) : null,
      h('p', { class: 'muted' }, 'Hover: ', h('span', { class: 'hover-name' })),
    ));
  }
}
