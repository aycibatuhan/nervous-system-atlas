import type { App } from '../app.ts';
import type { Axis } from '../types/state.ts';
import { h } from './dom.ts';
import { t, type Key } from '../i18n/index.ts';
import { axisExtentMm } from '../volume/coords.ts';
import { setContrast, setPeel, setSliceVisible, setSlices } from '../state/actions.ts';

const AXES: { axis: Axis; label: Key; key: string; positive: Key; negative: Key }[] = [
  { axis: 'axial', label: 'slice.axial', key: 'a', positive: 'slice.peel.above', negative: 'slice.peel.below' },
  { axis: 'coronal', label: 'slice.coronal', key: 'c', positive: 'slice.peel.anterior', negative: 'slice.peel.posterior' },
  { axis: 'sagittal', label: 'slice.sagittal', key: 's', positive: 'slice.peel.right', negative: 'slice.peel.left' },
];

export class SliceControls {
  private sliders = new Map<Axis, HTMLInputElement>();
  private nums = new Map<Axis, HTMLInputElement>();
  private checks = new Map<Axis, HTMLInputElement>();
  private peels = new Map<Axis, HTMLSelectElement>();
  /** every element whose text or tooltip comes from the string table, re-read on a language switch */
  private labels: { el: HTMLElement; text?: Key; title?: Key }[] = [];

  constructor(private app: App, container: HTMLElement) {
    const bar = h('div', { class: 'slicebar' });
    // brain-only ranges by default; the cord MRI grid reaches to the conus, so its range is added only once the
    // cord MRI is switched on, which keeps the brain sliders as precise as they were
    const extent = (axis: Axis): [number, number] => axisExtentMm(axis, app.store.get().cordMri ? app.grids : app.grid);
    for (const a of AXES) {
      const [lo, hi] = extent(a.axis);
      const cb = h('input', { type: 'checkbox', onchange: (e: Event) => setSliceVisible(app, a.axis, (e.target as HTMLInputElement).checked) });
      const sl = h('input', { type: 'range', min: lo, max: hi, step: 1, oninput: (e: Event) => setSlices(app, { [a.axis]: Number((e.target as HTMLInputElement).value) }) });
      const num = h('input', { type: 'number', class: 'mm', min: lo, max: hi, step: 1, onchange: (e: Event) => setSlices(app, { [a.axis]: Number((e.target as HTMLInputElement).value) }) });
      const noPeel = h('option', { value: '' }); const posPeel = h('option', { value: 'positive' }); const negPeel = h('option', { value: 'negative' });
      const peel = h('select', { class: 'peel', onchange: (e: Event) => { const v = (e.target as HTMLSelectElement).value; setPeel(app, a.axis, v === '' ? null : (v as 'positive' | 'negative')); } }, noPeel, posPeel, negPeel);
      this.sliders.set(a.axis, sl); this.nums.set(a.axis, num); this.checks.set(a.axis, cb); this.peels.set(a.axis, peel);
      const lbl = h('span', { class: 'lbl' }); const unit = h('span', { class: 'unit' });
      this.labels.push({ el: lbl, text: a.label }, { el: unit, text: 'slice.mm' }, { el: peel, title: 'slice.peel.title' },
        { el: noPeel, text: 'slice.peel.none' }, { el: posPeel, text: a.positive }, { el: negPeel, text: a.negative });
      bar.append(h('label', { class: 'slice-ctl' }, cb, lbl, sl, num, unit, peel));
    }
    const t1 = h('option', { value: 't1w' }); const t2 = h('option', { value: 't2w' });
    const contrast = h('select', { class: 'contrast', onchange: (e: Event) => setContrast(app, (e.target as HTMLSelectElement).value as 't1w' | 't2w') }, t1, t2);
    const opacity = h('input', { type: 'range', min: 0, max: 1, step: 0.05, value: app.store.get().overlay.opacity,
      oninput: (e: Event) => app.store.set({ overlay: { ...app.store.get().overlay, opacity: Number((e.target as HTMLInputElement).value) } }) });
    const all = h('input', { type: 'checkbox', onchange: (e: Event) => app.store.set({ overlay: { ...app.store.get().overlay, showAllLabels: (e.target as HTMLInputElement).checked } }) });
    const terr = h('input', { type: 'checkbox', onchange: (e: Event) => app.store.set({ overlay: { ...app.store.get().overlay, territory: (e.target as HTMLInputElement).checked } }) });
    const pin = h('input', { type: 'checkbox', onchange: (e: Event) => app.store.set({ slices: { ...app.store.get().slices, pinned: (e.target as HTMLInputElement).checked } }) });
    const cord = h('input', { type: 'checkbox', onchange: (e: Event) => app.store.set({ cordMri: (e.target as HTMLInputElement).checked }) });
    const mriLbl = h('span', {}); const overlayLbl = h('span', {}); const allLbl = h('span', {}); const terrLbl = h('span', {}); const pinLbl = h('span', {}); const cordLbl = h('span', {});
    const cordLabel = h('label', { class: 'cord-mri' }, cord, cordLbl);
    cordLabel.hidden = !app.cordGrid;
    this.labels.push({ el: mriLbl, text: 'slice.mri' }, { el: t1, text: 'slice.t1' }, { el: t2, text: 'slice.t2' },
      { el: overlayLbl, text: 'slice.overlay' }, { el: opacity, title: 'slice.overlay.title' },
      { el: allLbl, text: 'slice.allLabels' }, { el: all, title: 'slice.allLabels.title' },
      { el: terrLbl, text: 'slice.territories' }, { el: terr, title: 'slice.territories.title' },
      { el: pinLbl, text: 'slice.pin' }, { el: pin, title: 'slice.pin.title' },
      { el: cordLbl, text: 'slice.cord' }, { el: cord, title: 'slice.cord.title' });
    bar.append(h('div', { class: 'slice-opts' },
      h('label', {}, mriLbl, contrast), h('label', {}, overlayLbl, opacity), h('label', {}, all, allLbl), h('label', {}, terr, terrLbl), h('label', {}, pin, pinLbl), cordLabel));
    container.append(bar);
    this.applyLocale();
    app.store.subscribe((s) => s.locale, () => this.applyLocale());
    app.store.subscribe((s) => s.cordMri, (on) => {
      cord.checked = on;
      for (const a of AXES) {
        const [lo, hi] = extent(a.axis);
        const s = this.sliders.get(a.axis)!; const n = this.nums.get(a.axis)!;
        s.min = String(lo); s.max = String(hi); n.min = String(lo); n.max = String(hi);
        const v = app.store.get().slices[a.axis]; s.value = String(v); n.value = String(v);
      }
    });
    app.store.subscribe((s) => s.slices, (sl) => {
      for (const a of AXES) {
        const v = sl[a.axis]; const s = this.sliders.get(a.axis)!; const n = this.nums.get(a.axis)!;
        if (Number(s.value) !== v) s.value = String(v); if (Number(n.value) !== v) n.value = String(v);
        this.checks.get(a.axis)!.checked = sl.visible[a.axis];
      }
      pin.checked = sl.pinned;
    });
    app.store.subscribe((s) => s.peel, (p) => { for (const a of AXES) this.peels.get(a.axis)!.value = p[a.axis] ?? ''; });
    app.store.subscribe((s) => s.overlay, (o) => { terr.checked = o.territory; all.checked = o.showAllLabels; });
    app.store.subscribe((s) => s.contrast, (c) => { contrast.value = c; });
    // initial sync
    const sl = app.store.get().slices;
    for (const a of AXES) { this.sliders.get(a.axis)!.value = String(sl[a.axis]); this.nums.get(a.axis)!.value = String(sl[a.axis]); this.checks.get(a.axis)!.checked = sl.visible[a.axis]; }
  }

  /** Axis names, peel menus, contrast and the option tooltips, re-read from the string table. */
  private applyLocale(): void {
    for (const l of this.labels) {
      if (l.text) l.el.textContent = t(l.text);
      if (l.title) l.el.title = t(l.title);
    }
  }
}
