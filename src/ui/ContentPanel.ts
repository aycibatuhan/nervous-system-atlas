import type { App } from '../app.ts';
import { h, clear } from './dom.ts';
import { selectStructure } from '../state/actions.ts';
import { citeNode } from './cite.ts';
import type { Citation } from '../types/content.ts';
import type { ContentTab } from '../types/state.ts';

type Rec = Record<string, unknown>;
const TABS: { id: ContentTab; label: string }[] = [
  { id: 'overview', label: 'Overview' }, { id: 'anatomy', label: 'Anatomy' }, { id: 'connections', label: 'Connections' }, { id: 'function', label: 'Function' },
  { id: 'blood', label: 'Blood supply' }, { id: 'imaging', label: 'Imaging' }, { id: 'clinical', label: 'Clinical' }, { id: 'pitfalls', label: 'Pitfalls' }, { id: 'citations', label: 'Sources' },
];

/** Right panel: authored content for the selected structure (falls back to manifest facts). */
export class ContentPanel {
  private body: HTMLElement;
  constructor(private app: App, container: HTMLElement) {
    this.body = h('div', { class: 'content' });
    container.append(this.body);
    this.render();
    app.store.subscribe((s) => s.selectedId, () => this.render());
    app.store.subscribe((s) => s.contentTab, () => this.render());
    app.store.subscribe((s) => s.loaded.content, () => this.render());
    app.store.subscribe((s) => s.hoverId, (id) => { const el = this.body.querySelector('.hover-name'); if (el) el.textContent = id ? (app.registry.byId.get(id)?.name ?? '') : ''; });
  }

  private html(s: unknown): HTMLElement { const d = h('div', { class: 'prose' }); d.innerHTML = String(s ?? ''); this.linkify(d); return d; }
  private linkify(root: HTMLElement): void {
    for (const a of Array.from(root.querySelectorAll('a[href^="#/structure/"]'))) a.addEventListener('click', (e) => { e.preventDefault(); location.hash = (a as HTMLAnchorElement).getAttribute('href')!; });
  }
  private cite(c: Citation): HTMLElement { return citeNode(this.app.content?.bibliography, c); }
  private structLink(id: string): HTMLElement {
    const st = this.app.content?.structures[id] as Rec | undefined; const mesh = this.app.registry.byId.get(id) ?? this.app.manifest.meshes.find((m) => m.structureId === id);
    const name = (st?.['name'] as string) ?? mesh?.name ?? id;
    return h('a', { href: '#', class: 'xref', onclick: (e: Event) => { e.preventDefault(); if (mesh) selectStructure(this.app, mesh.id); else if (st) location.hash = `#/structure/${id}`; } }, name);
  }
  private list(items: unknown[], fmt: (x: Rec) => Node | string): HTMLElement { return h('ul', {}, ...items.map((x) => h('li', {}, fmt(x as Rec)))); }

  render(): void {
    clear(this.body);
    const s = this.app.store.get();
    const mesh = s.selectedId ? this.app.registry.byId.get(s.selectedId) : undefined;
    const sid = mesh ? (this.app.content?.meshToStructure[mesh.id] ?? mesh.structureId) : null;
    const entry = sid ? (this.app.content?.structures[sid] as Rec | undefined) : undefined;
    if (!mesh) {
      this.body.append(h('div', { class: 'empty' }, h('h2', {}, 'Select a structure'),
        h('p', {}, 'Click a mesh in the 3D view, click the MRI slice, or pick a structure from the tree on the left.'),
        h('p', { class: 'muted' }, 'Hover: ', h('span', { class: 'hover-name' }))));
      return;
    }
    const head = h('div', { class: 'content-head' }, h('span', { class: 'swatch big', style: `background:${mesh.colour}` }),
      h('div', {}, h('h2', {}, (entry?.['name'] as string) ?? mesh.name), h('div', { class: 'crumbs' }, `${mesh.system}${mesh.subsystem ? ' › ' + mesh.subsystem : ''} · ${mesh.side}` + (entry?.['latin'] ? ` · ${entry['latin']}` : ''))));
    this.body.append(head);
    if (!entry) {
      const lic = this.app.manifest.licenses[mesh.license];
      this.body.append(h('p', { class: 'muted' }, 'No authored content yet for ', h('code', {}, sid ?? ''), '.'),
        h('dl', { class: 'facts' }, h('dt', {}, 'Centroid (MNI mm)'), h('dd', {}, mesh.centroid.map((v) => v.toFixed(0)).join(', ')),
          h('dt', {}, 'Source'), h('dd', {}, `${mesh.source} · ${mesh.alignment}`), h('dt', {}, 'Licence'), h('dd', {}, lic ? h('a', { href: lic.url, target: '_blank' }, lic.name) : mesh.license)),
        h('p', { class: 'muted' }, 'Hover: ', h('span', { class: 'hover-name' })));
      return;
    }
    const tabs = h('div', { class: 'tabs' }, ...TABS.map((t) => h('button', { class: t.id === s.contentTab ? 'active' : '', onclick: () => this.app.store.set({ contentTab: t.id }) }, t.label)));
    this.body.append(tabs);
    const html = (entry['html'] ?? {}) as Record<string, string>;
    const sec = h('div', { class: 'section' });
    const anat = entry['anatomy'] as Rec; const conn = entry['connections'] as Rec; const blood = entry['bloodSupply'] as Rec; const img = entry['imaging'] as Rec; const clin = entry['clinical'] as Rec; const cn = entry['cranial'] as Rec | undefined;
    switch (s.contentTab) {
      case 'overview':
        sec.append(this.html(html['summary']));
        if (entry['synonyms'] && (entry['synonyms'] as string[]).length) sec.append(h('p', { class: 'muted' }, 'Also: ' + (entry['synonyms'] as string[]).join(', ')));
        if (cn) sec.append(h('h3', {}, `Cranial nerve ${cn['roman']}`), h('p', {}, `Components: ${(cn['components'] as string[]).join(', ')}`),
          h('h4', {}, 'Nuclei'), this.list(cn['nuclei'] as unknown[], (n) => h('span', {}, this.structLink(String(n['structureId'])), ` — ${n['component']} (${n['level']})`)),
          h('h4', {}, 'Course'), h('dl', { class: 'facts' }, ...Object.entries(cn['exit'] as Rec).flatMap(([k, v]) => [h('dt', {}, k.replace(/([A-Z])/g, ' $1')), h('dd', {}, String(v))])));
        if (entry['level']) sec.append(h('p', { class: 'muted' }, `Level: ${(entry['level'] as Rec)['region']}${(entry['level'] as Rec)['sub'] ? ' · ' + (entry['level'] as Rec)['sub'] : ''}`));
        sec.append(h('p', { class: 'muted small' }, `Centroid MNI ${mesh.centroid.map((v) => v.toFixed(0)).join(', ')} mm · ${mesh.source}`));
        break;
      case 'anatomy':
        sec.append(h('h3', {}, 'Location'), this.html(html['anatomy.location']));
        if (anat['boundaries']) sec.append(h('h3', {}, 'Boundaries'), this.html(html['anatomy.boundaries'] ?? anat['boundaries']));
        if ((anat['subdivisions'] as unknown[]).length) sec.append(h('h3', {}, 'Subdivisions'), this.list(anat['subdivisions'] as unknown[], (x) => h('span', {}, h('b', {}, String(x['name'])), ` — ${x['note']}`)));
        if (anat['relations']) sec.append(h('h3', {}, 'Relations'), h('dl', { class: 'facts' }, ...Object.entries(anat['relations'] as Rec).flatMap(([k, v]) => [h('dt', {}, k), h('dd', {}, String(v))])));
        if (cn) { sec.append(h('h3', {}, 'Branches'), this.list(cn['branches'] as unknown[], (b) => h('span', {}, h('b', {}, String(b['name'])), ` — ${b['supplies']}`)));
          if ((cn['ganglia'] as unknown[]).length) sec.append(h('h3', {}, 'Ganglia'), this.list(cn['ganglia'] as unknown[], (g) => `${g['name']} (${g['type']})`)); }
        break;
      case 'connections':
        if ((conn['afferents'] as unknown[]).length) sec.append(h('h3', {}, 'Afferents'), this.list(conn['afferents'] as unknown[], (x) => `${x['from']}${x['via'] ? ' via ' + x['via'] : ''}${x['note'] ? ' — ' + x['note'] : ''}`));
        if ((conn['efferents'] as unknown[]).length) sec.append(h('h3', {}, 'Efferents'), this.list(conn['efferents'] as unknown[], (x) => `${x['to']}${x['via'] ? ' via ' + x['via'] : ''}${x['note'] ? ' — ' + x['note'] : ''}`));
        if ((conn['pathways'] as string[]).length) sec.append(h('h3', {}, 'Pathways'), this.list(conn['pathways'] as unknown[], (p) => h('a', { href: `#/pathway/${p}` }, String((this.app.content?.pathways[String(p)] as Rec | undefined)?.['name'] ?? p))));
        if (cn && (cn['reflexes'] as unknown[]).length) sec.append(h('h3', {}, 'Reflexes'), this.list(cn['reflexes'] as unknown[], (r) => h('span', {}, h('b', {}, String(r['name'])), `: afferent ${r['afferent']} → ${r['center']} → efferent ${r['efferent']}`)));
        if (!sec.childElementCount) sec.append(h('p', { class: 'muted' }, 'No connections listed.'));
        break;
      case 'function': sec.append(this.html(html['function'])); break;
      case 'blood':
        sec.append(h('h3', {}, 'Arteries'), this.list(blood['arteries'] as unknown[], (a) => this.structLink(String(a))));
        if ((blood['territories'] as string[]).length) sec.append(h('h3', {}, 'Territories'), this.list(blood['territories'] as unknown[], (t) => this.structLink(String(t))),
          h('button', { onclick: () => this.app.store.set({ overlay: { ...this.app.store.get().overlay, territory: !this.app.store.get().overlay.territory } }) }, 'Toggle territory tint on slices'));
        if (blood['venous']) sec.append(h('h3', {}, 'Venous drainage'), h('p', {}, String(blood['venous'])));
        if (blood['note']) sec.append(this.html(html['bloodSupply.note'] ?? blood['note']));
        break;
      case 'imaging':
        sec.append(h('h3', {}, 'Where to look'), this.list(img['bestView'] as unknown[], (v) => { const m = v['mni'] as Rec; return h('span', {}, h('a', { href: '#', onclick: (e: Event) => { e.preventDefault(); this.app.store.set({ slices: { ...this.app.store.get().slices, [v['plane'] as string]: Math.round(Number(m[v['plane'] === 'axial' ? 'z' : v['plane'] === 'coronal' ? 'y' : 'x'])), visible: { ...this.app.store.get().slices.visible, [v['plane'] as string]: true } } }); } }, `${v['plane']} at ${Math.round(Number(m[v['plane'] === 'axial' ? 'z' : v['plane'] === 'coronal' ? 'y' : 'x']))} mm`), ` — ${v['label']}`); }),
          h('h3', {}, 'Normal appearance'), this.html(html['imaging.normalAppearance']));
        if (img['sequenceOfChoice']) sec.append(h('h3', {}, 'Sequence of choice'), this.html(html['imaging.sequenceOfChoice'] ?? img['sequenceOfChoice']));
        sec.append(h('h3', {}, 'Pathology'), ...(img['pathology'] as Rec[]).map((p) => h('div', { class: 'path' }, h('b', {}, `${p['pathology']} — ${p['modality']}${p['sequence'] && p['sequence'] !== 'n/a' ? ' ' + p['sequence'] : ''}`), h('p', {}, String(p['finding'])),
          p['timing'] ? h('p', { class: 'muted' }, 'Timing: ' + p['timing']) : null, p['pitfalls'] ? h('p', { class: 'muted' }, 'Pitfall: ' + p['pitfalls']) : null)));
        break;
      case 'clinical':
        sec.append(h('h3', {}, 'Lesion effects'), h('table', { class: 'tbl' }, h('tr', {}, h('th', {}, 'Deficit'), h('th', {}, 'Side'), h('th', {}, 'Mechanism')),
          ...(clin['lesionEffects'] as Rec[]).map((x) => h('tr', {}, h('td', {}, String(x['deficit'])), h('td', {}, String(x['side'])), h('td', {}, String(x['mechanism']))))),
          h('h3', {}, 'Examination'), this.list(clin['examination'] as unknown[], (x) => String(x)));
        if (cn) sec.append(h('h3', {}, 'Bedside tests'), ...(cn['tests'] as Rec[]).map((t) => h('div', { class: 'path' }, h('b', {}, String(t['name'])), h('p', {}, String(t['how'])), h('p', { class: 'muted' }, `Normal: ${t['normal']} · Abnormal: ${t['abnormal']}`))),
          h('h3', {}, 'Localizing signs'), this.list(cn['lesionSigns'] as unknown[], (x) => h('span', {}, h('b', {}, String(x['sign'])), ` — ${x['localisingValue']}`)));
        if (cn?.['nuclearVsPeripheral']) sec.append(h('h3', {}, 'Nuclear vs peripheral'), this.html(html['cranial.nuclearVsPeripheral']));
        if (cn?.['supranuclear']) sec.append(h('h3', {}, 'Supranuclear control'), this.html(html['cranial.supranuclear']));
        if ((clin['syndromes'] as string[]).length) sec.append(h('h3', {}, 'Syndromes'), h('div', { class: 'chips' }, ...(clin['syndromes'] as string[]).map((id) => h('a', { class: 'chip', href: `#/syndrome/${id}` }, String((this.app.content?.syndromes[id] as Rec | undefined)?.['name'] ?? id)))));
        sec.append(h('h3', {}, 'Pearls'), this.list(clin['pearls'] as unknown[], (x) => String(x)));
        break;
      case 'pitfalls':
        sec.append((entry['pitfalls'] as string[]).length ? this.list(entry['pitfalls'] as unknown[], (x) => String(x)) : h('p', { class: 'muted' }, 'No pitfalls listed.'));
        break;
      case 'citations':
        sec.append(this.list(entry['citations'] as unknown[], (c) => this.cite(c as unknown as Citation)),
          h('p', { class: 'muted small' }, 'Original prose written from these open-access sources; every link opens the free full text.'));
        break;
    }
    this.body.append(sec, h('p', { class: 'muted small' }, 'Hover: ', h('span', { class: 'hover-name' })));
  }
}
