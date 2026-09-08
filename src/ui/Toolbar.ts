import type { App } from '../app.ts';
import { h } from './dom.ts';
import { PRESETS } from '../scene/cameraPresets.ts';
import { applyCameraPreset } from '../state/actions.ts';
import { getLocale, otherLocale, setLocale, t, type Key } from '../i18n/index.ts';

const PRESET_KEY: Record<string, Key> = {
  'lateral-l': 'preset.lateral-l', 'lateral-r': 'preset.lateral-r', 'medial-l': 'preset.medial-l', 'medial-r': 'preset.medial-r',
  'anterior': 'preset.anterior', 'posterior': 'preset.posterior', 'superior': 'preset.superior', 'inferior': 'preset.inferior',
};

export class Toolbar {
  readonly status: HTMLElement;
  readonly searchHost: HTMLElement;
  readonly qualityBtn: HTMLButtonElement;
  readonly localeBtn: HTMLButtonElement;
  private helpBtn: HTMLButtonElement;
  private brandTitle: HTMLElement;
  private brandSub: HTMLElement;
  private presetBtns: HTMLButtonElement[];
  private buttons: { el: HTMLButtonElement; label: Key; title: Key }[] = [];
  /** what the status line says, kept as data so it can be re-rendered in the other language */
  private counts: { meshes: number; authored: number | null } = { meshes: 0, authored: null };
  private error: string | null = null;

  constructor(private app: App, container: HTMLElement, opts: { onSearchFocus(): void; onHelp(): void }) {
    this.searchHost = h('div', { class: 'search-host' });
    this.presetBtns = PRESETS.map((p) => h('button', { dataset: { preset: p.id }, onclick: () => applyCameraPreset(app, p.id) }));
    const presets = h('div', { class: 'presets' }, ...this.presetBtns);
    this.status = h('span', { class: 'status' });
    this.qualityBtn = h('button', { onclick: () => app.store.set({ quality: app.store.get().quality === 'high' ? 'low' : 'high' }) });
    this.localeBtn = h('button', { id: 'locale-switch', onclick: () => setLocale(otherLocale()) });
    this.helpBtn = h('button', { id: 'help-btn', onclick: () => opts.onHelp() }, '?');
    const btn = (label: Key, title: Key, extra: Record<string, unknown>): HTMLButtonElement => {
      const el = h('button', extra) as HTMLButtonElement;
      this.buttons.push({ el, label, title });
      return el;
    };
    this.brandTitle = h('strong', {});
    this.brandSub = h('span', { class: 'sub' });
    container.append(
      h('div', { class: 'brand' }, this.brandTitle, this.brandSub),
      presets,
      this.searchHost,
      h('div', { class: 'tools' },
        btn('toolbar.treeFilter', 'toolbar.treeFilter.title', { onclick: () => opts.onSearchFocus() }),
        btn('toolbar.quiz', 'toolbar.quiz.title', { onclick: () => { location.hash = '#/quiz'; } }),
        btn('toolbar.topics', 'toolbar.topics.title', { onclick: () => { location.hash = '#/topic'; } }),
        btn('toolbar.glossary', 'toolbar.glossary.title', { onclick: () => { location.hash = '#/glossary'; } }),
        btn('toolbar.about', 'toolbar.about.title', { class: 'about-btn', onclick: () => { location.hash = '#/about'; } }),
        this.qualityBtn,
        btn('toolbar.screenshot', 'toolbar.screenshot.title', { onclick: () => this.shot() }),
        this.localeBtn,
        this.helpBtn,
        this.status),
    );
    this.applyLocale();
    app.store.subscribe((s) => s.locale, () => this.applyLocale());
  }

  /** Every label, title and the status line, re-read from the string table. */
  applyLocale(): void {
    const loc = getLocale(), other = otherLocale(loc);
    this.brandTitle.textContent = t('brand.title');
    this.brandSub.textContent = t('brand.sub');
    for (const b of this.presetBtns) {
      const id = b.dataset['preset']!;
      const p = PRESETS.find((x) => x.id === id)!;
      b.textContent = t(PRESET_KEY[id] ?? 'preset.anterior');
      b.title = `${b.textContent} [${p.key}]`;
    }
    for (const { el, label, title } of this.buttons) { el.textContent = t(label); el.title = t(title); }
    this.qualityBtn.title = t('toolbar.quality.title');
    this.localeBtn.textContent = t(other === 'tr' ? 'locale.short.tr' : 'locale.short.en');
    this.localeBtn.title = t(other === 'tr' ? 'locale.name.tr' : 'locale.name.en');
    this.helpBtn.title = t('toolbar.help.title');
    this.setQuality(this.app.store.get().quality);
    this.renderStatus();
  }

  /** "662 structures · 391 authored" — kept as numbers so the language switch can restate it. */
  setCounts(meshes: number, authored: number | null = this.counts.authored): void {
    this.counts = { meshes, authored };
    this.error = null;
    this.renderStatus();
  }

  setError(message: string): void { this.error = message; this.renderStatus(); }

  private renderStatus(): void {
    if (this.error !== null) { this.status.textContent = t('status.volumeFailed', { message: this.error }); return; }
    const { meshes, authored } = this.counts;
    this.status.textContent = t('status.structures', { n: meshes }) + (authored !== null ? ` · ${t('status.authored', { n: authored })}` : '');
  }

  setQuality(q: 'low' | 'high'): void { this.qualityBtn.textContent = t(q === 'high' ? 'toolbar.quality.high' : 'toolbar.quality.low'); this.qualityBtn.classList.toggle('active', q === 'high'); }

  async shot(): Promise<void> {
    const blob = await this.app.sm.screenshot(); if (!blob) return;
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `atlas-${Date.now()}.png`; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  }
}
