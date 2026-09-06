import type { App } from '../app.ts';
import { h } from './dom.ts';
import { PRESETS } from '../scene/cameraPresets.ts';
import { applyCameraPreset } from '../state/actions.ts';

export class Toolbar {
  readonly status: HTMLElement;
  readonly searchHost: HTMLElement;
  readonly qualityBtn: HTMLButtonElement;
  constructor(private app: App, container: HTMLElement, opts: { onSearchFocus(): void; onHelp(): void }) {
    this.searchHost = h('div', { class: 'search-host' });
    const presets = h('div', { class: 'presets' }, ...PRESETS.map((p) => h('button', { title: `${p.label} [${p.key}]`, onclick: () => applyCameraPreset(app, p.id) }, p.label)));
    this.status = h('span', { class: 'status' });
    this.qualityBtn = h('button', { title: 'Render quality: high adds ambient occlusion, soft shadows and anti-aliasing', onclick: () => app.store.set({ quality: app.store.get().quality === 'high' ? 'low' : 'high' }) }, 'Quality');
    container.append(
      h('div', { class: 'brand' }, h('strong', {}, 'Clinical Neuroanatomy Atlas'), h('span', { class: 'sub' }, ' MNI152 · 3D + MRI')),
      presets,
      this.searchHost,
      h('div', { class: 'tools' },
        h('button', { title: 'Filter tree', onclick: () => opts.onSearchFocus() }, 'Tree filter'),
        h('button', { title: 'Clinical vignette quiz', onclick: () => { location.hash = '#/quiz'; } }, 'Quiz'),
        h('button', { title: 'Clinical topics (development, CSF, transmitters, EEG, epilepsy, dementia, neuromuscular …)', onclick: () => { location.hash = '#/topic'; } }, 'Topics'),
        h('button', { title: 'Glossary', onclick: () => { location.hash = '#/glossary'; } }, 'Glossary'),
        this.qualityBtn,
        h('button', { title: 'Screenshot [Shift+S]', onclick: () => this.shot() }, 'Screenshot'),
        h('button', { title: 'Keyboard shortcuts [?]', onclick: () => opts.onHelp() }, '?'),
        this.status),
    );
  }
  setQuality(q: 'low' | 'high'): void { this.qualityBtn.textContent = q === 'high' ? 'Quality: high' : 'Quality: low'; this.qualityBtn.classList.toggle('active', q === 'high'); }
  async shot(): Promise<void> {
    const blob = await this.app.sm.screenshot(); if (!blob) return;
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `atlas-${Date.now()}.png`; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  }
}
