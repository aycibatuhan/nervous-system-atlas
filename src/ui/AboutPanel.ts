import type { App } from '../app.ts';
import { DATA_URL } from '../loader/manifest.ts';
import { h, clear } from './dom.ts';
import { licenceShort } from './sourceLine.ts';

const CODE_LICENCE = { name: 'Apache License 2.0', url: 'https://www.apache.org/licenses/LICENSE-2.0' };
const DATA_LICENCE = { name: 'CC BY-SA 4.0', url: 'https://creativecommons.org/licenses/by-sa/4.0/' };
const CHANGES = 'registration into MNI152NLin2009cAsym space, remeshing of the label masks through a signed-distance field, smoothing, decimation to per-class triangle budgets, welding of neighbouring parcels, relabelling and recolouring, and the construction of derived meshes from geometry that no source atlas provides';

/** Right panel: what the atlas is, under which licences, and every dataset it is built from (#/about). */
export class AboutPanel {
  private fetched = new Map<string, string>();
  constructor(private app: App, private container: HTMLElement) {}

  show(): void {
    clear(this.container);
    const man = this.app.manifest;
    const edition = man.edition ?? 'private';
    const meshCount = new Map<string, number>();
    for (const m of man.meshes) meshCount.set(m.source, (meshCount.get(m.source) ?? 0) + 1);
    const derivedCount = man.meshes.filter((m) => m.derived).length;
    const sourceIds = Object.keys(man.sources);

    const licLink = (id: string): HTMLElement => {
      const l = man.licenses[id];
      return l ? h('a', { href: l.url, target: '_blank', rel: 'noopener noreferrer' }, l.name) : h('span', {}, id);
    };

    const rows = sourceIds.map((id) => {
      const s = man.sources[id]!;
      const lic = man.licenses[s.license];
      const restricted = !!(lic?.nc || lic?.noRedistribution);
      return h('tr', { class: 'about-source', dataset: { source: id, license: s.license } },
        h('td', {},
          h('div', {}, h('b', {}, s.name ?? id), h('span', { class: 'muted small' }, ` · ${id}`)),
          h('div', { class: 'muted small cite-text' }, s.citation),
          s.url ? h('div', { class: 'small' }, h('a', { class: 'src-link', href: s.url, target: '_blank', rel: 'noopener noreferrer' }, 'download'),
            s.manual ? h('span', { class: 'muted small' }, ' (manual click-through)') : null) : null),
        h('td', { class: 'about-lic' }, licLink(s.license),
          restricted ? h('div', {}, h('span', { class: 'tag badge-nc', title: lic?.nc ? 'non-commercial licence' : 'redistribution of derived files is not allowed' }, 'excluded from the public edition')) : null),
        h('td', { class: 'num' }, String(meshCount.get(id) ?? 0)));
    });

    const licenceSections = Object.entries(man.licenses).map(([id, l]) => {
      const body = h('pre', { class: 'licence-text' }, 'Loading…');
      const det = h('details', { class: 'licence-details' },
        h('summary', {}, `${l.name}`, h('span', { class: 'muted small' }, ` · ${id}`), l.nc ? h('span', { class: 'tag badge-nc' }, 'NC') : null, l.noRedistribution ? h('span', { class: 'tag badge-nc' }, 'no redistribution') : null),
        l.attribution ? h('p', { class: 'muted small' }, l.attribution) : null,
        h('p', { class: 'small' }, h('a', { href: l.url, target: '_blank', rel: 'noopener noreferrer' }, l.url)),
        body);
      det.addEventListener('toggle', () => { if (det.open) void this.fill(body, l.text); });
      return det;
    });

    this.container.append(h('div', {},
      h('div', { class: 'content-head' }, h('span', { class: 'swatch big', style: 'background:#c8a24a' }),
        h('div', {}, h('h2', {}, 'About and credits'),
          h('div', { class: 'crumbs' }, 'Clinical Neuroanatomy Atlas · ', h('span', { class: `tag edition-${edition}`, id: 'about-edition' }, `${edition} edition`),
            ` · ${man.meshes.length} meshes · ${sourceIds.length} data sources`))),

      h('p', { class: 'prose disclaimer', id: 'about-disclaimer' }, h('b', {}, 'Not for clinical use. '),
        'This atlas is an educational reference. Its structures are group-average templates and a registered specimen, not any patient\'s anatomy, and its syndrome, imaging and management text is a teaching summary written from the cited sources that may be incomplete, out of date or wrong. Nothing here is medical advice; do not use it to diagnose, treat or make decisions about a patient. Those decisions belong to qualified clinicians using current guidelines and the patient\'s own findings and imaging.'),
      h('p', { class: 'prose' }, 'A local 3D atlas of clinical neuroanatomy with synchronized MRI slices, pathway tracing, a syndrome mode, clinical topics, a glossary and a quiz. Everything is expressed in one coordinate frame, MNI152NLin2009cAsym RAS millimetres.'),

      h('h3', {}, 'Licences'),
      h('dl', { class: 'facts about-licences' },
        h('dt', {}, 'Code'), h('dd', {}, h('a', { href: CODE_LICENCE.url, target: '_blank', rel: 'noopener noreferrer', id: 'about-code-licence' }, CODE_LICENCE.name), ' · © 2026 Batuhan Ayci'),
        h('dt', {}, 'Data and content'), h('dd', {}, h('a', { href: DATA_LICENCE.url, target: '_blank', rel: 'noopener noreferrer', id: 'about-data-licence' }, DATA_LICENCE.name),
          ' — the generated meshes, volumes and manifest in ', h('code', {}, 'public/data/'), ' and the authored text in ', h('code', {}, 'content/')),
      ),
      h('p', { class: 'prose small' }, 'The meshes and volumes are ', h('b', {}, 'derivatives'), ' of the datasets listed below, used under their own licences, with changes: ', CHANGES, '. ',
        `${derivedCount} meshes have no counterpart in any source atlas at all and were constructed from geometry that does exist; each carries the construction method in the manifest and is flagged as schematic in its entry.`),
      h('p', { class: 'prose small' }, 'The prose is original and cites open-access sources only (StatPearls, PubMed Central, openly licensed reference pages); each entry lists them under its Sources tab.'),
      edition === 'private'
        ? h('p', { class: 'prose small' }, h('b', {}, 'This is the private edition.'), ' It contains data whose licence is non-commercial or forbids passing derived files on. Those meshes and volumes are marked below and must be excluded from any build that is published or shared.')
        : h('p', { class: 'prose small' }, h('b', {}, 'This is the public edition.'), ' Every dataset in it may be redistributed.'),

      h('h3', {}, 'Data sources'),
      h('table', { class: 'tbl about-sources' },
        h('thead', {}, h('tr', {}, h('th', {}, 'Dataset and citation'), h('th', {}, 'Licence'), h('th', { class: 'num' }, 'Meshes'))),
        h('tbody', {}, ...rows)),

      h('h3', {}, 'Licence texts'),
      h('div', { class: 'licences' }, ...licenceSections),

      h('h3', {}, 'How to cite'),
      h('p', { class: 'prose small' }, 'Ayci B. Clinical Neuroanatomy Atlas. ', String(man.generated).slice(0, 10), '. Code under Apache 2.0, data and content under CC BY-SA 4.0, derived from the datasets listed above. Cite the source datasets themselves as well when you use the meshes.'),
      h('p', { class: 'muted small' }, `Manifest generated ${man.generated} · space ${man.space}`),
    ));
  }

  /** Verbatim licence text from public/data/licenses/<id>.txt (manifest.licenses[].text), fetched once. */
  private async fill(body: HTMLElement, path: string): Promise<void> {
    if (this.fetched.has(path)) { body.textContent = this.fetched.get(path)!; return; }
    try {
      const r = await fetch(DATA_URL + path);
      const text = r.ok ? await r.text() : `Licence text not in this build (${path}: ${r.status}).`;
      this.fetched.set(path, text);
      body.textContent = text;
    } catch (e) { body.textContent = `Licence text could not be loaded: ${(e as Error).message}`; }
  }
}
