import type { App } from '../app.ts';
import { h, clear } from './dom.ts';

type Rec = Record<string, unknown>;

/** Right panel glossary: alphabetical, filterable, with related-term links. */
export class GlossaryPanel {
  private filter = '';
  constructor(private app: App, private container: HTMLElement) {}
  show(id?: string): void {
    clear(this.container);
    const g = this.app.content?.glossary ?? {};
    const terms = Object.values(g).map((x) => x as Rec).sort((a, b) => String(a['term']).localeCompare(String(b['term'])));
    const input = h('input', { type: 'search', class: 'search', placeholder: 'Filter terms…', value: this.filter }) as HTMLInputElement;
    input.addEventListener('input', () => { this.filter = input.value; render(); });
    const list = h('div', { class: 'glossary' });
    const render = () => {
      clear(list); const f = this.filter.toLowerCase();
      for (const t of terms) {
        if (f && !String(t['term']).toLowerCase().includes(f) && !String(t['definition']).toLowerCase().includes(f)) continue;
        const rel = (t['related'] as string[]) ?? [];
        list.append(h('div', { class: 'gterm', id: String(t['id']) }, h('h3', {}, String(t['term'])), h('p', {}, String(t['definition'])),
          rel.length ? h('div', { class: 'chips' }, ...rel.map((r) => h('a', { class: 'chip', href: `#/glossary/${r}` }, String((g[r] as Rec | undefined)?.['term'] ?? r)))) : null));
      }
    };
    render();
    this.container.append(h('div', {}, h('div', { class: 'content-head' }, h('span', { class: 'swatch big', style: 'background:#59a14f' }), h('div', {}, h('h2', {}, 'Glossary'), h('div', { class: 'crumbs' }, `${terms.length} terms`))), input, list));
    if (id) { const el = list.querySelector(`#${CSS.escape(id)}`); if (el) { el.classList.add('active'); el.scrollIntoView({ block: 'start' }); } }
  }
}
