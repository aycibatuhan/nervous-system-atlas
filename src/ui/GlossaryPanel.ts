import type { App } from '../app.ts';
import { h, clear, enTag } from './dom.ts';
import { t } from '../i18n/index.ts';

type Rec = Record<string, unknown>;

/** Right panel glossary: alphabetical, filterable, with related-term links. */
export class GlossaryPanel {
  private filter = '';
  private currentId: string | undefined;
  constructor(private app: App, private container: HTMLElement) {
    app.store.subscribe((s) => s.locale, () => { if (this.container.childElementCount) this.show(this.currentId); });
  }
  show(id?: string): void {
    this.currentId = id;
    clear(this.container);
    const g = this.app.content?.glossary ?? {};
    const terms = Object.values(g).map((x) => x as Rec).sort((a, b) => String(a['term']).localeCompare(String(b['term'])));
    const input = h('input', { type: 'search', class: 'search', placeholder: t('glossary.filter'), value: this.filter }) as HTMLInputElement;
    input.addEventListener('input', () => { this.filter = input.value; render(); });
    const list = h('div', { class: 'glossary' });
    const render = () => {
      clear(list); const f = this.filter.toLowerCase();
      for (const term of terms) {
        if (f && !String(term['term']).toLowerCase().includes(f) && !String(term['definition']).toLowerCase().includes(f)) continue;
        const rel = (term['related'] as string[]) ?? [];
        list.append(h('div', { class: 'gterm', id: String(term['id']) }, h('h3', {}, String(term['term'])), h('p', {}, enTag(), String(term['definition'])),
          rel.length ? h('div', { class: 'chips' }, ...rel.map((r) => h('a', { class: 'chip', href: `#/glossary/${r}` }, String((g[r] as Rec | undefined)?.['term'] ?? r)))) : null));
      }
    };
    render();
    this.container.append(h('div', {}, h('div', { class: 'content-head' }, h('span', { class: 'swatch big', style: 'background:#59a14f' }), h('div', {}, h('h2', {}, t('glossary.title')), h('div', { class: 'crumbs' }, t('glossary.count', { n: terms.length })))), input, list));
    if (id) { const el = list.querySelector(`#${CSS.escape(id)}`); if (el) { el.classList.add('active'); el.scrollIntoView({ block: 'start' }); } }
  }
}
