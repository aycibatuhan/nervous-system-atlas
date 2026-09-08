import type { App } from '../app.ts';
import { h, clear, enTag, secondaryName } from './dom.ts';
import { entryName, meshLabel, t, getLocale, type Key, type NamedEntry, entryOf } from '../i18n/index.ts';
import { selectStructure } from '../state/actions.ts';
import { citeNode } from './cite.ts';
import type { Citation } from '../types/content.ts';
import type { ContentTab } from '../types/state.ts';
import { sourceLine } from './sourceLine.ts';

type Rec = Record<string, unknown>;
const TABS: { id: ContentTab; label: Key }[] = [
  { id: 'overview', label: 'panel.tab.overview' }, { id: 'anatomy', label: 'panel.tab.anatomy' }, { id: 'connections', label: 'panel.tab.connections' }, { id: 'function', label: 'panel.tab.function' },
  { id: 'blood', label: 'panel.tab.blood' }, { id: 'imaging', label: 'panel.tab.imaging' }, { id: 'clinical', label: 'panel.tab.clinical' }, { id: 'pitfalls', label: 'panel.tab.pitfalls' }, { id: 'citations', label: 'panel.tab.citations' },
];
const PLANE_KEY: Record<string, Key> = { axial: 'axis.axial', coronal: 'axis.coronal', sagittal: 'axis.sagittal' };

/** Right panel: authored content for the selected structure (falls back to manifest facts). */
export class ContentPanel {
  private body: HTMLElement;
  /** the entry being rendered, so prose blocks know whether it is translated */
  private current: Rec | undefined;
  constructor(private app: App, container: HTMLElement) {
    this.body = h('div', { class: 'content' });
    container.append(this.body);
    this.render();
    app.store.subscribe((s) => s.selectedId, () => this.render());
    app.store.subscribe((s) => s.selectedStructureId, () => this.render());
    app.store.subscribe((s) => s.contentTab, () => this.render());
    app.store.subscribe((s) => s.loaded.content, () => this.render());
    app.store.subscribe((s) => s.locale, () => this.render());
    app.store.subscribe((s) => s.hoverId, (id) => { const el = this.body.querySelector('.hover-name'); if (el) el.textContent = id ? meshLabel(app, id).primary : ''; });
  }

  private html(s: unknown): HTMLElement {
    const d = h('div', { class: 'prose' }); d.innerHTML = String(s ?? ''); this.linkify(d);
    const tag = enTag(this.current); if (tag) d.prepend(tag);
    return d;
  }
  private linkify(root: HTMLElement): void {
    for (const a of Array.from(root.querySelectorAll('a[href^="#/structure/"]'))) a.addEventListener('click', (e) => { e.preventDefault(); location.hash = (a as HTMLAnchorElement).getAttribute('href')!; });
  }
  private cite(c: Citation): HTMLElement { return citeNode(this.app.content?.bibliography, c); }
  private structLink(id: string): HTMLElement {
    const st = entryOf(this.app, 'structures', id); const mesh = this.app.registry.byId.get(id) ?? this.app.manifest.meshes.find((m) => m.structureId === id);
    const n = entryName(st, mesh?.name ?? id);
    return h('a', { href: '#', class: 'xref', title: n.secondary ?? undefined, onclick: (e: Event) => { e.preventDefault(); if (mesh) selectStructure(this.app, mesh.id); else if (st) location.hash = `#/structure/${id}`; } }, n.primary);
  }

  /** Chip for a pathway / syndrome cross-link: display name, English name in the tooltip. */
  private chip(entry: NamedEntry | undefined, id: string, href: string): HTMLElement {
    const n = entryName(entry, id);
    return h('a', { class: 'chip', href, title: n.secondary ?? undefined }, n.primary);
  }
  /** A connection endpoint or waypoint: an entry id becomes a named cross-link, any other string is prose. */
  private endpoint(v: unknown): Node {
    const id = String(v ?? '');
    if (entryOf(this.app, 'structures', id)) return this.structLink(id);
    const pw = entryOf(this.app, 'pathways', id);
    if (pw) return this.chip(pw, id, `#/pathway/${id}`);
    return document.createTextNode(id);
  }

  /** "<endpoint> via <waypoint> — note", with every id in it named rather than printed raw. */
  private connection(x: Rec, key: 'from' | 'to'): Node {
    const parts: Node[] = [this.endpoint(x[key])];
    if (x['via']) {
      const via = t('content.conn.via', { via: '\u0000' }).split('\u0000');
      parts.push(document.createTextNode(via[0] ?? ''), this.endpoint(x['via']), document.createTextNode(via[1] ?? ''));
    }
    if (x['note']) parts.push(document.createTextNode(` \u2014 ${String(x['note'])}`));
    return h('span', {}, ...parts);
  }

  private list(items: unknown[], fmt: (x: Rec) => Node | string): HTMLElement { return h('ul', {}, ...items.map((x) => h('li', {}, fmt(x as Rec)))); }

  render(): void {
    clear(this.body);
    const s = this.app.store.get();
    const mesh = s.selectedId ? this.app.registry.byId.get(s.selectedId) : undefined;
    const sid = mesh ? (this.app.content?.meshToStructure[mesh.id] ?? mesh.structureId) : s.selectedStructureId;
    const entry = sid ? entryOf(this.app, 'structures', sid) : undefined;
    this.current = entry;
    if (!mesh && !entry) {
      this.body.append(h('div', { class: 'empty' }, h('h2', {}, t('content.empty.title')),
        h('p', {}, t('content.empty.body')),
        h('p', { class: 'muted' }, t('content.hover'), h('span', { class: 'hover-name' }))));
      return;
    }
    const crumbs = mesh ? `${mesh.system}${mesh.subsystem ? ' › ' + mesh.subsystem : ''} · ${mesh.side}` : String(entry!['system'] ?? '');
    const name = entryName(entry as NamedEntry | undefined, mesh?.name ?? '');
    // in Turkish the Latin term is the heading itself, so the crumbs no longer repeat it
    const latin = getLocale() === 'en' && entry?.['latin'] ? ` · ${String(entry['latin'])}` : '';
    const head = h('div', { class: 'content-head' }, h('span', { class: 'swatch big', style: `background:${mesh?.colour ?? '#6b7280'}` }),
      h('div', {}, h('h2', {}, name.primary, secondaryName(name)), h('div', { class: 'crumbs' }, crumbs + latin)));
    this.body.append(head);
    // this edition has the text but not the shape: the atlas the mesh came from may not be redistributed
    if (!mesh) this.body.append(h('p', { class: 'muted no-mesh', 'data-testid': 'no-mesh' }, t('content.noMesh')));
    // where the geometry came from: every mesh of this entry, with its dataset and licence, linked to #/about
    const meshIds = [...(mesh ? [mesh.id] : []), ...(((entry?.['meshIds'] as string[] | undefined) ?? []).filter((m) => m !== mesh?.id))];
    const src = meshIds.length ? sourceLine(this.app, meshIds) : null;
    if (src) this.body.append(src);
    if (!entry) {
      const lic = this.app.manifest.licenses[mesh!.license];
      this.body.append(h('p', { class: 'muted' }, t('content.noContent.before'), h('code', {}, sid ?? ''), t('content.noContent.after')),
        h('dl', { class: 'facts' }, h('dt', {}, t('content.facts.centroid')), h('dd', {}, mesh!.centroid.map((v) => v.toFixed(0)).join(', ')),
          h('dt', {}, t('content.facts.source')), h('dd', {}, `${mesh!.source} · ${mesh!.alignment}`), h('dt', {}, t('content.facts.licence')), h('dd', {}, lic ? h('a', { href: lic.url, target: '_blank' }, lic.name) : mesh!.license)),
        h('p', { class: 'muted' }, t('content.hover'), h('span', { class: 'hover-name' })));
      return;
    }
    const tabs = h('div', { class: 'tabs' }, ...TABS.map((tab) => h('button', { class: tab.id === s.contentTab ? 'active' : '', onclick: () => this.app.store.set({ contentTab: tab.id }) }, t(tab.label))));
    this.body.append(tabs);
    const html = (entry['html'] ?? {}) as Record<string, string>;
    const sec = h('div', { class: 'section' });
    const anat = entry['anatomy'] as Rec; const conn = entry['connections'] as Rec; const blood = entry['bloodSupply'] as Rec; const img = entry['imaging'] as Rec; const clin = entry['clinical'] as Rec; const cn = entry['cranial'] as Rec | undefined;
    switch (s.contentTab) {
      case 'overview':
        sec.append(this.html(html['summary']));
        if (entry['synonyms'] && (entry['synonyms'] as string[]).length) sec.append(h('p', { class: 'muted' }, t('content.also', { list: (entry['synonyms'] as string[]).join(', ') })));
        if (cn) sec.append(h('h3', {}, t('content.cn.title', { roman: String(cn['roman']) })), h('p', {}, t('content.cn.components', { list: (cn['components'] as string[]).join(', ') })),
          h('h4', {}, t('content.cn.nuclei')), this.list(cn['nuclei'] as unknown[], (n) => h('span', {}, this.structLink(String(n['structureId'])), ` — ${n['component']} (${n['level']})`)),
          h('h4', {}, t('content.cn.course')), h('dl', { class: 'facts' }, ...Object.entries(cn['exit'] as Rec).flatMap(([k, v]) => [h('dt', {}, k.replace(/([A-Z])/g, ' $1')), h('dd', {}, String(v))])));
        if (entry['level']) sec.append(h('p', { class: 'muted' }, t('content.level', { text: `${(entry['level'] as Rec)['region']}${(entry['level'] as Rec)['sub'] ? ' · ' + (entry['level'] as Rec)['sub'] : ''}` })));
        if (mesh) sec.append(h('p', { class: 'muted small' }, t('content.centroidLine', { mni: mesh.centroid.map((v) => v.toFixed(0)).join(', '), source: mesh.source })));
        break;
      case 'anatomy':
        sec.append(h('h3', {}, t('content.anatomy.location')), this.html(html['anatomy.location']));
        if (anat['boundaries']) sec.append(h('h3', {}, t('content.anatomy.boundaries')), this.html(html['anatomy.boundaries'] ?? anat['boundaries']));
        if ((anat['subdivisions'] as unknown[]).length) sec.append(h('h3', {}, enTag(this.current), t('content.anatomy.subdivisions')), this.list(anat['subdivisions'] as unknown[], (x) => h('span', {}, h('b', {}, String(x['name'])), ` — ${x['note']}`)));
        if (anat['relations']) sec.append(h('h3', {}, enTag(this.current), t('content.anatomy.relations')), h('dl', { class: 'facts' }, ...Object.entries(anat['relations'] as Rec).flatMap(([k, v]) => [h('dt', {}, k), h('dd', {}, String(v))])));
        if (cn) { sec.append(h('h3', {}, enTag(this.current), t('content.cn.branches')), this.list(cn['branches'] as unknown[], (b) => h('span', {}, h('b', {}, String(b['name'])), ` — ${b['supplies']}`)));
          if ((cn['ganglia'] as unknown[]).length) sec.append(h('h3', {}, t('content.cn.ganglia')), this.list(cn['ganglia'] as unknown[], (g) => `${g['name']} (${g['type']})`)); }
        break;
      case 'connections':
        if ((conn['afferents'] as unknown[]).length) sec.append(h('h3', {}, enTag(this.current), t('content.conn.afferents')), this.list(conn['afferents'] as unknown[], (x) => this.connection(x, 'from')));
        if ((conn['efferents'] as unknown[]).length) sec.append(h('h3', {}, enTag(this.current), t('content.conn.efferents')), this.list(conn['efferents'] as unknown[], (x) => this.connection(x, 'to')));
        if ((conn['pathways'] as string[]).length) sec.append(h('h3', {}, t('content.conn.pathways')), this.list(conn['pathways'] as unknown[], (p) => this.chip(entryOf(this.app, 'pathways', String(p)), String(p), `#/pathway/${String(p)}`)));
        if (cn && (cn['reflexes'] as unknown[]).length) sec.append(h('h3', {}, enTag(this.current), t('content.conn.reflexes')), this.list(cn['reflexes'] as unknown[], (r) => h('span', {}, h('b', {}, String(r['name'])), t('content.conn.reflexLine', { afferent: String(r['afferent']), center: String(r['center']), efferent: String(r['efferent']) }))));
        if (!sec.childElementCount) sec.append(h('p', { class: 'muted' }, t('content.conn.none')));
        break;
      case 'function': sec.append(this.html(html['function'])); break;
      case 'blood':
        sec.append(h('h3', {}, t('content.blood.arteries')), this.list(blood['arteries'] as unknown[], (a) => this.structLink(String(a))));
        if ((blood['territories'] as string[]).length) sec.append(h('h3', {}, t('content.blood.territories')), this.list(blood['territories'] as unknown[], (x) => this.structLink(String(x))),
          h('button', { onclick: () => this.app.store.set({ overlay: { ...this.app.store.get().overlay, territory: !this.app.store.get().overlay.territory } }) }, t('content.blood.toggle')));
        if (blood['venous']) sec.append(h('h3', {}, enTag(this.current), t('content.blood.venous')), h('p', {}, String(blood['venous'])));
        if (blood['note']) sec.append(this.html(html['bloodSupply.note'] ?? blood['note']));
        break;
      case 'imaging': {
        // an MniRef that pointed at a mesh dropped from this edition can arrive without a coordinate: show the
        // note, drop the slice link, never render "axial at NaN mm"
        const axisOf = (plane: unknown) => (plane === 'axial' ? 'z' : plane === 'coronal' ? 'y' : 'x');
        const mmOf = (v: Rec): number => Number((v['mni'] as Rec | undefined)?.[axisOf(v['plane'])]);
        const planeName = (p: unknown) => t(PLANE_KEY[String(p)] ?? 'axis.axial');
        sec.append(h('h3', {}, enTag(this.current), t('content.imaging.where')), this.list(img['bestView'] as unknown[], (v) => {
          const mm = mmOf(v);
          if (!Number.isFinite(mm)) return h('span', { class: 'muted' }, `${planeName(v['plane'])} — ${v['label']}`);
          return h('span', {}, h('a', { href: '#', onclick: (e: Event) => { e.preventDefault(); this.app.store.set({ slices: { ...this.app.store.get().slices, [v['plane'] as string]: Math.round(mm), visible: { ...this.app.store.get().slices.visible, [v['plane'] as string]: true } } }); } }, t('content.imaging.at', { plane: planeName(v['plane']), mm: Math.round(mm) })), ` — ${v['label']}`);
        }),
          h('h3', {}, t('content.imaging.normal')), this.html(html['imaging.normalAppearance']));
        if (img['sequenceOfChoice']) sec.append(h('h3', {}, t('content.imaging.sequence')), this.html(html['imaging.sequenceOfChoice'] ?? img['sequenceOfChoice']));
        sec.append(h('h3', {}, enTag(this.current), t('content.imaging.pathology')), ...(img['pathology'] as Rec[]).map((p) => h('div', { class: 'path' }, h('b', {}, `${p['pathology']} — ${p['modality']}${p['sequence'] && p['sequence'] !== 'n/a' ? ' ' + p['sequence'] : ''}`), h('p', {}, String(p['finding'])),
          p['timing'] ? h('p', { class: 'muted' }, t('content.imaging.timing', { text: String(p['timing']) })) : null, p['pitfalls'] ? h('p', { class: 'muted' }, t('content.imaging.pitfall', { text: String(p['pitfalls']) })) : null)));
        break;
      }
      case 'clinical':
        sec.append(h('h3', {}, enTag(this.current), t('content.clinical.lesionEffects')), h('table', { class: 'tbl' }, h('tr', {}, h('th', {}, t('th.deficit')), h('th', {}, t('th.side')), h('th', {}, t('th.mechanism'))),
          ...(clin['lesionEffects'] as Rec[]).map((x) => h('tr', {}, h('td', {}, String(x['deficit'])), h('td', {}, String(x['side'])), h('td', {}, String(x['mechanism']))))),
          h('h3', {}, enTag(this.current), t('content.clinical.examination')), this.list(clin['examination'] as unknown[], (x) => String(x)));
        if (cn) sec.append(h('h3', {}, enTag(this.current), t('content.clinical.bedside')), ...(cn['tests'] as Rec[]).map((x) => h('div', { class: 'path' }, h('b', {}, String(x['name'])), h('p', {}, String(x['how'])), h('p', { class: 'muted' }, t('content.clinical.normalAbnormal', { normal: String(x['normal']), abnormal: String(x['abnormal']) })))),
          h('h3', {}, enTag(this.current), t('content.clinical.localizing')), this.list(cn['lesionSigns'] as unknown[], (x) => h('span', {}, h('b', {}, String(x['sign'])), ` — ${x['localisingValue']}`)));
        if (cn?.['nuclearVsPeripheral']) sec.append(h('h3', {}, t('content.clinical.nuclearVsPeripheral')), this.html(html['cranial.nuclearVsPeripheral']));
        if (cn?.['supranuclear']) sec.append(h('h3', {}, t('content.clinical.supranuclear')), this.html(html['cranial.supranuclear']));
        if ((clin['syndromes'] as string[]).length) sec.append(h('h3', {}, t('content.clinical.syndromes')), h('div', { class: 'chips' }, ...(clin['syndromes'] as string[]).map((id) => this.chip(entryOf(this.app, 'syndromes', id), id, `#/syndrome/${id}`))));
        sec.append(h('h3', {}, enTag(this.current), t('content.clinical.pearls')), this.list(clin['pearls'] as unknown[], (x) => String(x)));
        break;
      case 'pitfalls':
        sec.append((entry['pitfalls'] as string[]).length ? h('div', {}, h('div', {}, enTag(this.current)), this.list(entry['pitfalls'] as unknown[], (x) => String(x))) : h('p', { class: 'muted' }, t('content.pitfalls.none')));
        break;
      case 'citations':
        sec.append(this.list(entry['citations'] as unknown[], (c) => this.cite(c as unknown as Citation)),
          h('p', { class: 'muted small' }, t('content.citations.note')));
        break;
    }
    this.body.append(sec, h('p', { class: 'muted small' }, t('content.hover'), h('span', { class: 'hover-name' })));
  }
}
