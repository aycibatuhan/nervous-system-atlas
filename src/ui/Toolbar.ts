import type { App } from '../app.ts';
import { h } from './dom.ts';
import { PRESETS } from '../scene/cameraPresets.ts';
import { applyCameraPreset } from '../state/actions.ts';

export class Toolbar {
  readonly status: HTMLElement;
  constructor(private app: App, container: HTMLElement, opts: { onSearchFocus(): void; onHelp(): void }) {
    const presets = h('div', { class: 'presets' }, ...PRESETS.map((p) => h('button', { title: `${p.label} [${p.key}]`, onclick: () => applyCameraPreset(app, p.id) }, p.label)));
    this.status = h('span', { class: 'status' });
    container.append(
      h('div', { class: 'brand' }, h('strong', {}, 'Clinical Neuroanatomy Atlas'), h('span', { class: 'sub' }, ' MNI152 · 3D + MRI')),
      presets,
      h('div', { class: 'tools' },
        h('button', { title: 'Search [f]', onclick: () => opts.onSearchFocus() }, 'Search'),
        h('button', { title: 'Screenshot [Shift+S]', onclick: () => this.shot() }, 'Screenshot'),
        h('button', { title: 'Keyboard shortcuts [?]', onclick: () => opts.onHelp() }, '?'),
        this.status),
    );
  }
  async shot(): Promise<void> {
    const blob = await this.app.sm.screenshot(); if (!blob) return;
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `atlas-${Date.now()}.png`; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  }
}
