import type { App } from '../app.ts';
import { DATA_URL } from '../loader/manifest.ts';
import { h, clear } from './dom.ts';
import { licenceShort } from './sourceLine.ts';
import { getLocale, t } from '../i18n/index.ts';

const CODE_LICENCE = { name: 'Apache License 2.0', url: 'https://www.apache.org/licenses/LICENSE-2.0' };
const DATA_LICENCE = { name: 'CC BY-SA 4.0', url: 'https://creativecommons.org/licenses/by-sa/4.0/' };

/** Right panel: what the atlas is, under which licences, and every dataset it is built from (#/about). */
export class AboutPanel {
  private fetched = new Map<string, string>();
  constructor(private app: App, private container: HTMLElement) {
    app.store.subscribe((s) => s.locale, () => { if (this.container.childElementCount) this.show(); });
  }

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
          s.url ? h('div', { class: 'small' }, h('a', { class: 'src-link', href: s.url, target: '_blank', rel: 'noopener noreferrer' }, t('about.download')),
            s.manual ? h('span', { class: 'muted small' }, t('about.manual')) : null)
            // no file to download: built here, or read live from an API
            : h('div', { class: 'muted small src-origin' }, s.api ? t('about.fromApi', { api: s.api }) : t('about.builtHere'))),
        h('td', { class: 'about-lic' }, licLink(s.license),
          restricted ? h('div', {}, h('span', { class: 'tag badge-nc', title: t(lic?.nc ? 'about.excluded.nc' : 'about.excluded.noRedistribution') }, t('about.excluded'))) : null),
        h('td', { class: 'num' }, String(meshCount.get(id) ?? 0)));
    });

    const licenceSections = Object.entries(man.licenses).map(([id, l]) => {
      const body = h('pre', { class: 'licence-text' }, t('about.loading'));
      const det = h('details', { class: 'licence-details' },
        h('summary', {}, `${l.name}`, h('span', { class: 'muted small' }, ` · ${id}`), l.nc ? h('span', { class: 'tag badge-nc' }, t('about.tag.nc')) : null, l.noRedistribution ? h('span', { class: 'tag badge-nc' }, t('about.tag.noRedistribution')) : null),
        l.attribution ? h('p', { class: 'muted small' }, l.attribution) : null,
        h('p', { class: 'small' }, h('a', { href: l.url, target: '_blank', rel: 'noopener noreferrer' }, l.url)),
        body);
      det.addEventListener('toggle', () => { if (det.open) void this.fill(body, l.text); });
      return det;
    });

    this.container.append(h('div', {},
      h('div', { class: 'content-head' }, h('span', { class: 'swatch big', style: 'background:#c8a24a' }),
        h('div', {}, h('h2', {}, t('about.title')),
          h('div', { class: 'crumbs' }, t('brand.title') + ' · ', h('span', { id: 'about-version' }, `v${__APP_VERSION__}`), ' · ',
            h('span', { class: `tag edition-${edition}`, id: 'about-edition' }, t(edition === 'public' ? 'about.edition.public' : 'about.edition.private')),
            t('about.counts', { meshes: man.meshes.length, sources: sourceIds.length })))),

      h('p', { class: 'prose disclaimer', id: 'about-disclaimer' }, h('b', {}, t('about.disclaimer.lead')), t('about.disclaimer.body')),
      getLocale() === 'tr' ? h('p', { class: 'prose small', id: 'about-tr-notice' }, t('trNotice.body')) : null,
      h('p', { class: 'prose' }, t('about.intro')),

      h('h3', {}, t('about.licences')),
      h('dl', { class: 'facts about-licences' },
        h('dt', {}, t('about.code')), h('dd', {}, h('a', { href: CODE_LICENCE.url, target: '_blank', rel: 'noopener noreferrer', id: 'about-code-licence' }, CODE_LICENCE.name), ' · © 2026 Batuhan Ayci'),
        h('dt', {}, t('about.dataContent')), h('dd', {}, h('a', { href: DATA_LICENCE.url, target: '_blank', rel: 'noopener noreferrer', id: 'about-data-licence' }, DATA_LICENCE.name),
          t('about.dataNote.a'), h('code', {}, 'public/data/'), t('about.dataNote.b'), h('code', {}, 'content/'), t('about.dataNote.c')),
      ),
      h('p', { class: 'prose small' }, t('about.derived.a'), h('b', {}, t('about.derived.word')), t('about.derived.b', { changes: t('about.changes') }),
        t('about.derivedCount', { n: derivedCount })),
      h('p', { class: 'prose small' }, t('about.prose')),
      edition === 'private'
        ? h('p', { class: 'prose small' }, h('b', {}, t('about.private.lead')), t('about.private.body'))
        : h('p', { class: 'prose small' }, h('b', {}, t('about.public.lead')), t('about.public.body')),

      h('h3', {}, t('about.dataSources')),
      h('table', { class: 'tbl about-sources' },
        h('thead', {}, h('tr', {}, h('th', {}, t('about.th.dataset')), h('th', {}, t('about.th.licence')), h('th', { class: 'num' }, t('about.th.meshes')))),
        h('tbody', {}, ...rows)),

      h('h3', {}, t('about.licenceTexts')),
      h('div', { class: 'licences' }, ...licenceSections),

      h('h3', {}, t('about.howToCite')),
      h('p', { class: 'prose small' }, t('about.citation', { date: String(man.generated).slice(0, 10) })),
      h('p', { class: 'muted small' }, t('about.generated', { generated: String(man.generated), space: man.space })),
    ));
  }

  /** Verbatim licence text from public/data/licenses/<id>.txt (manifest.licenses[].text), fetched once. */
  private async fill(body: HTMLElement, path: string): Promise<void> {
    if (this.fetched.has(path)) { body.textContent = this.fetched.get(path)!; return; }
    try {
      const r = await fetch(DATA_URL + path);
      const text = r.ok ? await r.text() : t('about.licenceMissing', { path, status: r.status });
      this.fetched.set(path, text);
      body.textContent = text;
    } catch (e) { body.textContent = t('about.licenceError', { message: (e as Error).message }); }
  }
}
