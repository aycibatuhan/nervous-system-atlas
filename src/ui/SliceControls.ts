import type { App } from '../app.ts';
import type { Axis } from '../types/state.ts';
import { h } from './dom.ts';
import { axisExtentMm } from '../volume/coords.ts';
import { setContrast, setPeel, setSliceVisible, setSlices } from '../state/actions.ts';

const AXES: { axis: Axis; label: string; key: string }[] = [{ axis: 'axial', label: 'Axial (z)', key: 'a' }, { axis: 'coronal', label: 'Coronal (y)', key: 'c' }, { axis: 'sagittal', label: 'Sagittal (x)', key: 's' }];

export class SliceControls {
  private sliders = new Map<Axis, HTMLInputElement>();
  private nums = new Map<Axis, HTMLInputElement>();
  private checks = new Map<Axis, HTMLInputElement>();
  private peels = new Map<Axis, HTMLSelectElement>();

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
      const peel = h('select', { class: 'peel', title: 'Peel: hide meshes on one side of this plane', onchange: (e: Event) => { const v = (e.target as HTMLSelectElement).value; setPeel(app, a.axis, v === '' ? null : (v as 'positive' | 'negative')); } },
        h('option', { value: '' }, 'no peel'), h('option', { value: 'positive' }, a.axis === 'axial' ? 'hide above' : a.axis === 'coronal' ? 'hide anterior' : 'hide right'),
        h('option', { value: 'negative' }, a.axis === 'axial' ? 'hide below' : a.axis === 'coronal' ? 'hide posterior' : 'hide left'));
      this.sliders.set(a.axis, sl); this.nums.set(a.axis, num); this.checks.set(a.axis, cb); this.peels.set(a.axis, peel);
      bar.append(h('label', { class: 'slice-ctl' }, cb, h('span', { class: 'lbl' }, a.label), sl, num, h('span', { class: 'unit' }, 'mm'), peel));
    }
    const contrast = h('select', { class: 'contrast', onchange: (e: Event) => setContrast(app, (e.target as HTMLSelectElement).value as 't1w' | 't2w') },
      h('option', { value: 't1w' }, 'T1'), h('option', { value: 't2w' }, 'T2'));
    const opacity = h('input', { type: 'range', min: 0, max: 1, step: 0.05, value: app.store.get().overlay.opacity, title: 'Overlay opacity',
      oninput: (e: Event) => app.store.set({ overlay: { ...app.store.get().overlay, opacity: Number((e.target as HTMLInputElement).value) } }) });
    const all = h('input', { type: 'checkbox', title: 'Colour every visible structure on the slices', onchange: (e: Event) => app.store.set({ overlay: { ...app.store.get().overlay, showAllLabels: (e.target as HTMLInputElement).checked } }) });
    const terr = h('input', { type: 'checkbox', title: 'Tint arterial territories', onchange: (e: Event) => app.store.set({ overlay: { ...app.store.get().overlay, territory: (e.target as HTMLInputElement).checked } }) });
    const pin = h('input', { type: 'checkbox', title: 'Keep slices where they are when selecting', onchange: (e: Event) => app.store.set({ slices: { ...app.store.get().slices, pinned: (e.target as HTMLInputElement).checked } }) });
    const cord = h('input', { type: 'checkbox', title: 'Continue the MRI below the foramen magnum with the PAM50 spinal cord template (loaded on demand)',
      onchange: (e: Event) => app.store.set({ cordMri: (e.target as HTMLInputElement).checked }) });
    const cordLabel = h('label', { class: 'cord-mri' }, cord, ' cord MRI');
    cordLabel.hidden = !app.cordGrid;
    bar.append(h('div', { class: 'slice-opts' },
      h('label', {}, 'MRI ', contrast), h('label', {}, 'overlay ', opacity), h('label', {}, all, ' all labels'), h('label', {}, terr, ' territories'), h('label', {}, pin, ' pin slices'), cordLabel));
    container.append(bar);
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
}
