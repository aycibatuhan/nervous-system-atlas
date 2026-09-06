import type { App } from '../app.ts';
import { h, clear } from './dom.ts';
import { setSyndromeStep, enterSyndrome } from '../state/syndrome.ts';

type Rec = Record<string, unknown>;

/** Floating bar over the viewport while a syndrome is active: name, lesion side, deficit stepper, exit. */
export class SyndromeBar {
  constructor(private app: App, private el: HTMLElement) {
    app.store.subscribe((s) => [s.syndrome?.id ?? null, s.syndrome?.step ?? -1, s.lesionSide] as const, () => this.render(), (a, b) => a[0] === b[0] && a[1] === b[1] && a[2] === b[2]);
    this.render();
  }
  render(): void {
    const s = this.app.store.get(); clear(this.el);
    if (!s.syndrome) { this.el.hidden = true; return; }
    const syn = this.app.content?.syndromes[s.syndrome.id] as Rec | undefined; if (!syn) { this.el.hidden = true; return; }
    const deficits = (syn['deficits'] as Rec[]) ?? []; const step = s.syndrome.step; const d = deficits[step];
    const side = s.lesionSide ?? 'l';
    const bilateral = ['bilateral', 'midline'].includes(String((syn['localisation'] as Rec)['side']));
    this.el.hidden = false;
    this.el.append(h('span', { class: 'syn-inner' },
      h('span', { class: 'syn-name' }, h('b', {}, String(syn['name'])), bilateral ? '' : h('span', { class: 'muted' }, ` · lesion on the ${side === 'l' ? 'left' : 'right'}`)),
      bilateral ? null : h('button', { class: 'mini', title: 'Mirror the lesion to the other side', onclick: () => { const ns = side === 'l' ? 'r' : 'l'; this.app.store.set({ lesionSide: ns }); enterSyndrome(this.app, s.syndrome!.id, step, ns); } }, 'Mirror'),
      h('span', { class: 'sep' }),
      h('button', { class: 'mini', disabled: step <= 0 ? 'true' : null, onclick: () => setSyndromeStep(this.app, step - 1) }, '◀'),
      h('span', { class: 'syn-step' }, d ? h('span', {}, h('span', { class: 'tag' }, String(d['modality'])), ' ', h('b', {}, String(d['side'])), ` ${d['distribution']}: `, String(d['sign'])) : 'All deficits'),
      h('button', { class: 'mini', disabled: step >= deficits.length - 1 ? 'true' : null, onclick: () => setSyndromeStep(this.app, step + 1) }, '▶'),
      h('span', { class: 'muted small' }, `${step + 1}/${deficits.length}`),
      h('span', { class: 'sep' }),
      h('button', { class: 'mini', onclick: () => { location.hash = '#/slice'; } }, 'Exit'),
    ));
  }
}
