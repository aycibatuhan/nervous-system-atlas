import * as THREE from 'three';
import WebGL from 'three/addons/capabilities/WebGL.js';
import { createApp, type App } from './app.ts';
import { loadLabels, loadManifest } from './loader/manifest.ts';
import { Picker } from './picking/Picker.ts';
import { TreePanel } from './ui/TreePanel.ts';
import { SliceControls } from './ui/SliceControls.ts';
import { ContentPanel } from './ui/ContentPanel.ts';
import { Toolbar } from './ui/Toolbar.ts';
import { PathwayPanel } from './ui/PathwayPanel.ts';
import { SyndromeBar } from './ui/SyndromeBar.ts';
import { SyndromePanel } from './ui/SyndromePanel.ts';
import { SearchBox } from './ui/SearchBox.ts';
import { QuizPanel } from './ui/QuizPanel.ts';
import { GlossaryPanel } from './ui/GlossaryPanel.ts';
import { TopicPanel } from './ui/TopicPanel.ts';
import { AboutPanel } from './ui/AboutPanel.ts';
import { enterSyndrome, exitSyndrome } from './state/syndrome.ts';
import { clear, h } from './ui/dom.ts';
import { applyStates, selectStructure, setHover, setSlices, syncVisibility } from './state/actions.ts';
import { loadRawVolume } from './volume/VolumeSource.ts';
import { makeIntensityTexture, makeLabelTexture } from './volume/textures.ts';
import { gridBoxMm, mmToVoxel } from './volume/coords.ts';
import { indexSpineLut, loadSpineLut, spineLevelAt, spineLevelLabel, spineMask } from './volume/spineLabels.ts';
import type { SystemId } from './types/manifest.ts';
import type { Axis } from './types/state.ts';
import { PRESETS } from './scene/cameraPresets.ts';
import { applyCameraPreset, setContrast, setSliceVisible, setPeel } from './state/actions.ts';
import { sameSet } from './state/actions.ts';
import { bindRouter } from './router/hashRouter.ts';
import type { ContentBundle } from './types/content.ts';
import { getLocale, onLocaleChange, otherLocale, setLocale, t } from './i18n/index.ts';

const msg = document.getElementById('overlay-msg')!;
function showMsg(text: string | null): void { msg.hidden = !text; msg.textContent = text ?? ''; }

async function boot(): Promise<void> {
  if (!WebGL.isWebGL2Available()) { showMsg(t('boot.webgl')); return; }
  showMsg(t('boot.manifest'));
  const manifest = await loadManifest();
  const canvas = document.getElementById('gl') as HTMLCanvasElement;
  const app = createApp(canvas, manifest);
  (window as unknown as { atlas: App }).atlas = app;
  app.picker = new Picker(app.sm, app.registry, {
    onHover: (hit) => { setHover(app, hit.id); canvas.style.cursor = hit.id || hit.onSlice ? 'pointer' : ''; hud(hit.onSlice ? hit.point : null, hit.point); },
    onSelect: (hit, ev) => {
      if (hit.onSlice && hit.point) { const id = structureAt(app, hit.point); if (id) { selectStructure(app, id, { moveSlices: false }); return; } }
      if (hit.id) selectStructure(app, hit.id, { moveSlices: !ev.shiftKey });
      else if (!ev.shiftKey) selectStructure(app, null);
    },
    onFocus: (hit) => {
      // double-click: frame the clicked structure (or the structure under the MRI slice); empty space re-centres on the brain
      const id = hit.id ?? (hit.onSlice && hit.point ? structureAt(app, hit.point) : null);
      if (id) selectStructure(app, id, { moveSlices: false, fit: true });
      else app.sm.fitToBox(app.registry.sceneBounds());
    },
  });
  app.picker.extra = Object.values(app.slices).map((s) => s.mesh);

  // ---- UI
  const left = document.getElementById('left')!; const right = document.getElementById('right')!; const bottom = document.getElementById('bottom')!; const top = document.getElementById('toolbar')!;
  const tree = new TreePanel(app, left);
  new SliceControls(app, bottom);
  const contentPanel = new ContentPanel(app, right);
  const pathwayHost = h('div', { class: 'content', hidden: true }); right.append(pathwayHost);
  const pathwayPanel = new PathwayPanel(app, pathwayHost);
  const syndromeHost = h('div', { class: 'content', hidden: true }); right.append(syndromeHost);
  const syndromePanel = new SyndromePanel(app, syndromeHost);
  new SyndromeBar(app, document.getElementById('syndrome-bar')!);
  const quizHost = h('div', { class: 'content', hidden: true }); right.append(quizHost); const quizPanel = new QuizPanel(app, quizHost);
  const glossaryHost = h('div', { class: 'content', hidden: true }); right.append(glossaryHost); const glossaryPanel = new GlossaryPanel(app, glossaryHost);
  const topicHost = h('div', { class: 'content', hidden: true }); right.append(topicHost); const topicPanel = new TopicPanel(app, topicHost);
  const aboutHost = h('div', { class: 'content', hidden: true }); right.append(aboutHost); const aboutPanel = new AboutPanel(app, aboutHost);
  const mainPanel = right.firstElementChild as HTMLElement;
  const showPanel = (which: 'main' | 'pathway' | 'syndrome' | 'quiz' | 'glossary' | 'topic' | 'about') => { mainPanel.hidden = which !== 'main'; pathwayHost.hidden = which !== 'pathway'; syndromeHost.hidden = which !== 'syndrome'; quizHost.hidden = which !== 'quiz'; glossaryHost.hidden = which !== 'glossary'; topicHost.hidden = which !== 'topic'; aboutHost.hidden = which !== 'about'; if (which !== 'quiz') quizPanel.exit(); if (which !== 'topic') topicPanel.exit(); if (which !== 'quiz' && which !== 'glossary' && which !== 'topic' && which !== 'about' && app.store.get().panel) app.store.set({ panel: null }); };
  const showPathway = (id: string | null) => { if (id) { pathwayPanel.show(id); showPanel('pathway'); } else { pathwayPanel.exit(); if (!pathwayHost.hidden) showPanel('main'); } };
  void contentPanel;
  const help = h('div', { class: 'help', hidden: true });
  const renderHelp = (): void => {
    const wasHidden = help.hidden;
    help.replaceChildren(h('b', {}, t('help.title')), h('br'),
      ...PRESETS.map((p) => h('div', {}, h('kbd', {}, p.key), ' ', t(`preset.${p.id}` as Parameters<typeof t>[0]))),
      h('div', {}, h('kbd', {}, 'a'), '/', h('kbd', {}, 'c'), '/', h('kbd', {}, 's'), ' ' + t('help.slices')),
      h('div', {}, h('kbd', {}, '↑'), h('kbd', {}, '↓'), ' ' + t('help.move')), h('div', {}, h('kbd', {}, 't'), ' ' + t('help.contrast')),
      h('div', {}, h('kbd', {}, 'p'), ' ' + t('help.peel')), h('div', {}, h('kbd', {}, '['), h('kbd', {}, ']'), ' ' + t('help.panels')),
      h('div', {}, h('kbd', {}, 'f'), ' ' + t('help.search')), h('div', {}, h('kbd', {}, 'A'), '–', h('kbd', {}, 'E'), ' ' + t('help.quiz')),
      h('div', {}, h('kbd', {}, 'L'), ' ' + t('help.language')),
      h('div', {}, h('kbd', {}, 'Esc'), ' ' + t('help.escape')), h('div', {}, h('kbd', {}, 'Shift'), t('help.shiftClick')),
      h('div', {}, h('kbd', {}, 'Alt'), t('help.altClick')));
    help.hidden = wasHidden;
  };
  renderHelp();
  document.getElementById('viewport')!.append(help);
  const toolbar = new Toolbar(app, top, { onSearchFocus: () => (left.querySelector('.tree-filter') as HTMLInputElement)?.focus(), onHelp: () => { help.hidden = !help.hidden; } });
  const search = new SearchBox(toolbar.searchHost, (doc) => {
    if (doc.kind === 'syndrome') location.hash = `#/syndrome/${doc.id}`;
    else if (doc.kind === 'pathway') location.hash = `#/pathway/${doc.id}`;
    else if (doc.kind === 'topic') location.hash = `#/topic/${doc.id}`;
    else if (doc.kind === 'glossary') location.hash = `#/glossary/${doc.id}`;
    else if (doc.kind === 'mesh') selectStructure(app, doc.id, { moveSlices: true, fit: true });
    else location.hash = `#/structure/${doc.id}`;
  }, app);
  // the locale lives in the store: setLocale tells us, every panel re-renders from its own subscription
  // the Turkish bundle (translated prose) is fetched the first time Turkish is wanted, before the panels re-render
  async function ensureTr(): Promise<void> {
    if (app.contentTr) return;
    try { const r = await fetch('data/content.tr.json'); if (r.ok) app.contentTr = (await r.json()) as ContentBundle; } catch (e) { console.warn('no Turkish bundle', e); }
  }
  onLocaleChange((l) => { if (l === 'tr' && !app.contentTr) void ensureTr().then(() => app.store.set({ locale: l })); else app.store.set({ locale: l }); });
  app.store.subscribe((s) => s.locale, () => renderHelp());
  // The Turkish clinical prose is a machine-assisted translation: say so where it cannot be missed, until
  // the reader dismisses it. The same sentence is repeated, undismissable, in the About panel.
  const trNotice = h('div', { class: 'tr-notice', id: 'tr-notice' });
  document.getElementById('viewport')!.append(trNotice);
  function renderTrNotice(): void {
    clear(trNotice);
    let dismissed = false;
    try { dismissed = localStorage.getItem('atlas.trNotice.dismissed') === '1'; } catch { /* storage blocked */ }
    trNotice.hidden = getLocale() !== 'tr' || dismissed;
    if (trNotice.hidden) return;
    trNotice.append(h('span', {}, t('trNotice.body')),
      h('button', { class: 'mini', onclick: () => { try { localStorage.setItem('atlas.trNotice.dismissed', '1'); } catch { /* storage blocked */ } renderTrNotice(); } }, t('trNotice.dismiss')));
  }
  renderTrNotice();
  app.store.subscribe((s) => s.locale, () => renderTrNotice());
  const hudEl = h('div', { class: 'hud' }); document.getElementById('viewport')!.append(hudEl);
  const progress = h('div', { class: 'progress' }); document.getElementById('viewport')!.append(progress);
  /** MNI readout; over a cord slice it also names the PAM50 spinal level under the cursor ("C5 · cervical segment"). */
  function hud(onSlice: THREE.Vector3 | null, p: THREE.Vector3 | null): void {
    const lvl = onSlice ? spineLevelAt(app.spine, app.cordGrid, onSlice) : null;
    if (app.store.get().cordLevel !== (lvl?.id ?? null)) app.store.set({ cordLevel: lvl?.id ?? null });
    hudEl.textContent = p ? t('hud.mni', { x: p.x.toFixed(0), y: p.y.toFixed(0), z: p.z.toFixed(0) }) + (lvl ? ` · ${spineLevelLabel(lvl.entry)}` : '') : '';
  }

  // ---- state → scene wiring
  app.store.subscribe((s) => s.visibleSystems, () => syncVisibility(app), sameSet);
  app.store.subscribe((s) => s.hiddenStructures, () => syncVisibility(app), sameSet);
  app.store.subscribe((s) => s.shownStructures, () => syncVisibility(app), sameSet);
  app.store.subscribe((s) => s.showNc, () => { syncVisibility(app); tree.render(); });
  // picking a structure while a quiz / glossary / topic panel is open returns to the structure panel
  app.store.subscribe((s) => s.selectedId, (id) => { if (id && app.store.get().panel && !app.store.get().syndrome) { app.store.set({ panel: null }); showPanel('main'); } });
  app.store.subscribe((s) => [s.selectedId, s.hoverId, s.syndrome, s.involved, s.stepHighlight] as const, () => { applyStates(app); updateLuts(app); }, (a, b) => a[0] === b[0] && a[1] === b[1] && a[2] === b[2] && a[3] === b[3] && a[4] === b[4]);
  app.store.subscribe((s) => s.slices, (sl) => { for (const ax of ['axial', 'coronal', 'sagittal'] as Axis[]) { app.slices[ax].setPosition(sl[ax]); app.slices[ax].setVisible(sl.visible[ax] && app.store.get().loaded.volume); } applyPeel(app); app.sm.requestRender(); });
  app.store.subscribe((s) => s.peel, (peel) => { applyPeel(app); app.sm.aoSuppressed = Object.keys(peel).length > 0; app.sm.requestRender(); });
  // render quality (persisted): composer + AO + shadows in 'high'; the slice shader switches to linear output there
  app.sm.onOutputModeChange.add((linear) => { app.uniforms.uLinearOut.value = linear ? 1 : 0; });
  app.store.subscribe((s) => s.quality, (q) => { app.sm.setQuality(q); toolbar.setQuality(q); try { localStorage.setItem('atlas.quality', q); } catch { /* private mode */ } });
  try { const q = localStorage.getItem('atlas.quality'); app.store.set({ quality: q === 'high' ? 'high' : 'low' }); } catch { /* ignore */ }
  toolbar.setQuality(app.store.get().quality);
  app.store.subscribe((s) => s.overlay, (o) => { app.uniforms.uOverlayOpacity.value = o.opacity; app.uniforms.uShowAllLabels.value = o.showAllLabels ? 1 : 0; updateLuts(app); app.sm.requestRender(); });
  app.store.subscribe((s) => s.windowLevel, (w) => { app.uniforms.uWindow.value = w.window; app.uniforms.uLevel.value = w.level; app.sm.requestRender(); });
  app.store.subscribe((s) => s.contrast, (c) => { void loadContrast(app, c, progress); void ensureCord(); });

  // ---- spinal cord MRI (curved reformat onto our cord centreline, its own grid below the MNI box), loaded
  // on demand. The private edition reformats PAM50 and has T2 and T1; the public edition reformats the atlas'
  // own spine-generic average and has T2 only, so the contrast choice falls back to whatever the grid ships.
  const cordTex: Record<string, THREE.Data3DTexture> = {};
  let cordInflight: Promise<void> | null = null;
  let spineInflight: Promise<void> | null = null;
  const mniFloorZ = gridBoxMm(app.grid).min.z;
  /** The spinal-level volume + LUT of whichever cord template this edition ships, fetched once with it. */
  async function ensureSpineLabels(): Promise<void> {
    if (app.spine || spineInflight || !app.cordGrid) return spineInflight ?? undefined;
    const meta = app.manifest.volumes['labels_spine'];
    if (!meta) return;
    const job = (async () => {
      const [vol, json] = await Promise.all([loadRawVolume(meta), loadSpineLut(meta.lut)]);
      app.spine = { vol, json, byId: indexSpineLut(json) };
      app.uniforms.uSpine.value = makeLabelTexture(vol);
      app.uniforms.uHasSpine.value = 1;
      updateLuts(app);
      app.sm.requestRender();
    })();
    spineInflight = job;
    try { await job; } catch (e) { console.error('spine labels', e); } finally { if (spineInflight === job) spineInflight = null; }
  }
  async function ensureCord(): Promise<void> {
    if (!app.cordGrid) return;
    if (!app.store.get().cordMri) { app.uniforms.uHasCord.value = 0; app.sm.requestRender(); return; }
    const want = app.store.get().contrast === 't2w' ? 'cord_t2' : 'cord_t1';
    const key = app.manifest.volumes[want] ? want : app.manifest.volumes['cord_t2'] ? 'cord_t2' : 'cord_t1';
    const meta = app.manifest.volumes[key];
    if (!meta) return;
    if (!cordTex[key]) {
      const job = (async () => {
        const vol = await loadRawVolume(meta, (f) => (progress.style.transform = `scaleX(${f})`));
        cordTex[key] = makeIntensityTexture(vol);
        progress.style.transform = 'scaleX(0)';
      })();
      cordInflight = job;
      try { await job; } catch (e) { console.error('cord volume', e); return; } finally { if (cordInflight === job) cordInflight = null; }
    }
    if (!app.store.get().cordMri) return;
    app.uniforms.uCord.value = cordTex[key]!;
    app.uniforms.uHasCord.value = 1;
    void ensureSpineLabels();
    if (!app.store.get().loaded.cord) app.store.set({ loaded: { ...app.store.get().loaded, cord: true } });
    app.sm.requestRender();
  }
  app.store.subscribe((s) => s.cordLevel, () => { updateSpineLut(app); app.sm.requestRender(); });
  app.store.subscribe((s) => s.cordMri, (on) => {
    for (const ax of ['axial', 'coronal', 'sagittal'] as Axis[]) app.slices[ax].setExtended(on && !!app.cordGrid);
    void ensureCord();
  });
  // switch it on by itself once a slice reaches the cord, or a structure below the foramen magnum is selected
  const wantCord = () => { if (app.cordGrid && !app.store.get().cordMri) app.store.set({ cordMri: true }); };
  app.store.subscribe((s) => s.slices, (sl) => { if (sl.axial < mniFloorZ + 2 || sl.coronal < gridBoxMm(app.grid).min.y + 2) wantCord(); });
  app.store.subscribe((s) => s.selectedId, (id) => { const m = id ? app.registry.byId.get(id) : null; if (m && m.bbox[0][2] < mniFloorZ) wantCord(); });
  app.registry.byId.forEach(() => undefined);
  // reflect newly loaded meshes
  const origOnChange = (app.registry as unknown as { onChange: (id: string) => void }).onChange;
  (app.registry as unknown as { onChange: (id: string) => void }).onChange = (id: string) => { origOnChange(id); app.registry.setVisible(id, meshVisible(app, id)); app.registry.invalidatePickCache(); applyStates(app); if (Object.keys(app.store.get().peel).length) applyPeel(app); };

  // ---- initial visibility: systems flagged defaultVisible
  const defaults = new Set<SystemId>(manifest.systems.filter((s) => s.defaultVisible).map((s) => s.id));
  app.store.set({ visibleSystems: defaults, loaded: { ...app.store.get().loaded, manifest: true } });
  showMsg(null);
  applyCameraPreset(app, 'lateral-l');
  toolbar.setCounts(manifest.meshes.length);

  // ---- content bundle (optional until authored) then router
  try {
    const r = await fetch('data/content.json');
    if (r.ok) { app.content = (await r.json()) as ContentBundle; app.store.set({ loaded: { ...app.store.get().loaded, content: true } }); toolbar.setCounts(manifest.meshes.length, Object.keys(app.content.structures).length); }
  } catch (e) { console.warn('no content bundle', e); }
  if (getLocale() === 'tr') await ensureTr();
  void search.load('data/search-index.json', manifest.meshes.filter((m) => !app.content?.structures[m.structureId]).map((m) => ({ id: m.id, kind: 'mesh', name: m.name, aliases: [], summary: t('search.unauthored', { system: m.system, side: m.side }) })));
  bindRouter(app.store, {
    onRoute(route, params) {
      if (params.lang && params.lang !== getLocale()) setLocale(params.lang);
      if (params.ax !== undefined || params.cor !== undefined || params.sag !== undefined) setSlices(app, { ...(params.ax !== undefined ? { axial: params.ax } : {}), ...(params.cor !== undefined ? { coronal: params.cor } : {}), ...(params.sag !== undefined ? { sagittal: params.sag } : {}) });
      if (params.c) setContrast(app, params.c);
      if (route.kind === 'quiz') { if (app.store.get().syndrome) exitSyndrome(app); pathwayPanel.exit(); showPanel('quiz'); app.store.set({ panel: { kind: 'quiz', index: route.index ?? 0 } }); quizPanel.show(route.index ?? 0); return; }
      if (route.kind === 'glossary') { if (app.store.get().syndrome) exitSyndrome(app); pathwayPanel.exit(); showPanel('glossary'); app.store.set({ panel: { kind: 'glossary', id: route.id ?? null } }); glossaryPanel.show(route.id); return; }
      if (route.kind === 'topic') { if (app.store.get().syndrome) exitSyndrome(app); pathwayPanel.exit(); showPanel('topic'); app.store.set({ panel: { kind: 'topic', id: route.id ?? null } }); topicPanel.show(route.id); return; }
      if (route.kind === 'about') { if (app.store.get().syndrome) exitSyndrome(app); pathwayPanel.exit(); showPanel('about'); app.store.set({ panel: { kind: 'about' } }); aboutPanel.show(); return; }
      if (route.kind === 'syndrome') { showPathway(null); enterSyndrome(app, route.id, route.step ?? 0, params.side); if (params.side) app.store.set({ lesionSide: params.side }); syndromePanel.show(route.id); showPanel('syndrome'); return; }
      if (app.store.get().syndrome) { exitSyndrome(app); showPanel('main'); }
      if (route.kind === 'pathway') { showPathway(route.id); return; }
      showPathway(null);
      // Leaving the topic, glossary, quiz or about panel for a structure or the plain view. The selectedId
      // subscription below does this too, but only when the selection actually changes: opening a structure,
      // reading About and following a link back to that same structure would otherwise leave About on screen
      // (and the router would then keep rewriting the hash back to #/about).
      if ((route.kind === 'structure' || route.kind === 'slice' || route.kind === 'home') && app.store.get().panel) {
        app.store.set({ panel: null });
        showPanel('main');
      }
      if (route.kind === 'structure') {
        // route ids may be structure ids or mesh ids
        const meshId = app.registry.byId.has(route.id) ? route.id : (app.manifest.meshes.find((m) => m.structureId === route.id)?.id ?? null);
        if (meshId) { if (app.store.get().selectedId !== meshId) selectStructure(app, meshId, { moveSlices: params.ax === undefined, fit: true }); }
        // no mesh: in the public edition the source atlas of this structure may not be redistributed, so the
        // content is there and the geometry is not. Open the panel anyway rather than silently doing nothing.
        else if (app.content?.structures[route.id]) app.store.set({ selectedId: null, selectedStructureId: route.id });
      } else if (route.kind === 'home') { /* keep state */ }
    },
  });

  // ---- volumes (T1 first, then labels) in the background
  void (async () => {
    try {
      await loadContrast(app, 't1w', progress);
      app.store.set({ loaded: { ...app.store.get().loaded, volume: true } });
      const sl = app.store.get().slices; app.store.set({ slices: { ...sl } }); for (const ax of ['axial', 'coronal', 'sagittal'] as Axis[]) app.slices[ax].setVisible(sl.visible[ax]);
      app.sm.requestRender();
      app.labels = await loadLabels();
      const anat = await loadRawVolume(app.labels.volumes['labels_anat']!, (f) => (progress.style.transform = `scaleX(${f})`));
      app.uniforms.uLabels.value = makeLabelTexture(anat); app.uniforms.uHasLabels.value = 1;
      (app as unknown as { anatVolume: typeof anat }).anatVolume = anat;
      const terr = await loadRawVolume(app.labels.volumes['labels_vascular']!);
      app.uniforms.uTerritories.value = makeLabelTexture(terr); app.uniforms.uHasTerritories.value = 1;
      const tract = await loadRawVolume(app.labels.volumes['labels_tract']!);
      app.uniforms.uTracts.value = makeLabelTexture(tract); app.uniforms.uHasTracts.value = 1;
      app.store.set({ loaded: { ...app.store.get().loaded, labels: true } });
      updateLuts(app); app.sm.requestRender();
      progress.style.transform = 'scaleX(0)';
    } catch (e) { console.error(e); toolbar.setError((e as Error).message); }
  })();

  // ---- keyboard
  let lastAxis: Axis = 'axial';
  window.addEventListener('keydown', (e) => {
    if ((e.target as HTMLElement).tagName === 'INPUT' || (e.target as HTMLElement).tagName === 'SELECT') return;
    if (app.store.get().panel?.kind === 'quiz' && /^([a-eA-E]|ArrowLeft|ArrowRight)$/.test(e.key)) { quizPanel.key(e.key); e.preventDefault(); return; }
    const preset = PRESETS.find((p) => p.key === e.key);
    if (preset) { applyCameraPreset(app, preset.id); return; }
    const s = app.store.get();
    switch (e.key) {
      case 'a': lastAxis = 'axial'; setSliceVisible(app, 'axial', !s.slices.visible.axial); break;
      case 'c': lastAxis = 'coronal'; setSliceVisible(app, 'coronal', !s.slices.visible.coronal); break;
      case 's': lastAxis = 'sagittal'; setSliceVisible(app, 'sagittal', !s.slices.visible.sagittal); break;
      case 'ArrowUp': setSlices(app, { [lastAxis]: s.slices[lastAxis] + (e.shiftKey ? 5 : 1) }); e.preventDefault(); break;
      case 'ArrowDown': setSlices(app, { [lastAxis]: s.slices[lastAxis] - (e.shiftKey ? 5 : 1) }); e.preventDefault(); break;
      case 't': setContrast(app, s.contrast === 't1w' ? 't2w' : 't1w'); break;
      case 'p': setPeel(app, lastAxis, s.peel[lastAxis] ? null : 'positive'); break;   // the slice last toggled with a / c / s
      case '[': document.getElementById('app')!.classList.toggle('no-left'); app.sm.resize(); break;
      case ']': document.getElementById('app')!.classList.toggle('no-right'); app.sm.resize(); break;
      case 'Escape': if (s.syndrome) location.hash = '#/slice'; else selectStructure(app, null); break;
      case 'f': search.input.focus(); e.preventDefault(); break;
      case '?': help.hidden = !help.hidden; break;
      case 'S': if (e.shiftKey) void toolbar.shot(); break;
      case 'l': case 'L': setLocale(otherLocale()); break;
    }
  });
}

function meshVisible(app: App, id: string): boolean {
  const s = app.store.get(); const m = app.registry.byId.get(id);
  // A label table can name a mesh this edition does not ship (public/data/ holds whatever the pipeline built,
  // and the label volumes are only filtered when the edition is packaged), so an unknown id is simply not shown.
  if (!m) return false;
  if (!s.showNc && m.nc) return false;
  if (s.hiddenStructures.has(id)) return false;
  if (s.shownStructures.has(id)) return true;
  return s.visibleSystems.has(m.system) && m.visible;
}

async function loadContrast(app: App, c: 't1w' | 't2w', progress: HTMLElement): Promise<void> {
  const cache = (app as unknown as { texCache?: Record<string, THREE.Texture> });
  cache.texCache ??= {};
  if (!cache.texCache[c]) {
    const meta = app.manifest.volumes[c]!;
    const vol = await loadRawVolume(meta, (f) => (progress.style.transform = `scaleX(${f})`));
    cache.texCache[c] = makeIntensityTexture(vol);
    progress.style.transform = 'scaleX(0)';
  }
  app.uniforms.uIntensity.value = cache.texCache[c]!;
  app.sm.requestRender();
}

/** anat label under a world point → mesh id; below the MNI box, the PAM50 spinal level → its cord segment */
function structureAt(app: App, p: THREE.Vector3): string | null {
  const vol = (app as unknown as { anatVolume?: { dims: number[]; data: Uint16Array } }).anatVolume;
  const v = vol && app.labels ? mmToVoxel(p, app.grid) : null;
  const i = v ? Math.round(v.x) : -1, j = v ? Math.round(v.y) : -1, k = v ? Math.round(v.z) : -1;
  if (!vol || !v || i < 0 || j < 0 || k < 0 || i >= vol.dims[0]! || j >= vol.dims[1]! || k >= vol.dims[2]!) {
    // outside the MNI grid the slice is showing the cord volume: name the segment that owns this level
    return spineLevelAt(app.spine, app.cordGrid, p)?.entry.meshId ?? null;
  }
  const id = vol.data[i + vol.dims[0]! * (j + vol.dims[1]! * k)]!;
  return id ? app.labels!.lut.anat[String(id)]?.meshId ?? null : null;
}

/** Rebuild the colour/flag lookup textures from the current state. */
function updateLuts(app: App): void {
  updateSpineLut(app);              // independent of the anat labels: the cord volume can arrive first
  if (!app.labels) return;
  const s = app.store.get();
  const { struct, tract, terr, flags } = app.luts;
  struct.clear(); flags.clear(); terr.clear(); tract.clear();
  const lut = app.labels.lut;
  for (const [id, e] of Object.entries(lut.anat)) if (meshVisible(app, e.meshId)) struct.set(Number(id), e.colour, s.overlay.showAllLabels ? 0.55 : 0);
  const mark = (meshId: string, bit: number, alpha: number) => {
    const l = app.labels!.byMesh[meshId]; if (!l) return;
    for (const id of l.anat ?? []) { const e = lut.anat[String(id)]!; struct.set(id, e.colour, alpha); flags.or(id, bit); }
    for (const id of l.tract ?? []) { const e = lut.tract[String(id)]!; tract.set(id, e.colour, alpha); }
    for (const id of l.vascular ?? []) { const e = lut.vascular[String(id)]!; terr.set(id, e.colour, alpha); }
  };
  if (s.hoverId && s.hoverId !== s.selectedId && !s.syndrome) mark(s.hoverId, 4, 0.35);
  if (s.selectedId) mark(s.selectedId, 1, 0.6);
  if (s.syndrome) { for (const id of s.involved) mark(id, 2, 0.45); for (const id of s.stepHighlight) mark(id, 1, 0.65); }
  if (s.overlay.territory) for (const [id, e] of Object.entries(lut.vascular)) terr.set(Number(id), e.colour, 0.5);
  if (s.overlay.tracts) for (const [id, e] of Object.entries(lut.tract)) tract.set(Number(id), e.colour, 0.5);
  app.sm.requestRender();
}

/** Spinal-level ramp colours plus the selected / hovered level masks the slice shader outlines with. */
function updateSpineLut(app: App): void {
  if (!app.spine) return;
  const s = app.store.get();
  const { spine } = app.luts;
  spine.clear();
  const selected = (e: { meshId: string }) => s.selectedId !== null && e.meshId === s.selectedId;
  for (const [id, e] of app.spine.byId) {
    const hovered = s.cordLevel === id;
    spine.set(id, e.colour, selected(e) ? 0.6 : hovered ? 0.35 : s.overlay.showAllLabels ? 0.55 : 0);
  }
  app.uniforms.uSpineSel.value = spineMask(app.spine.byId, (_id, e) => selected(e));
  app.uniforms.uSpineHover.value = spineMask(app.spine.byId, (id) => id === s.cordLevel);
}

function applyPeel(app: App): void {
  const s = app.store.get();
  const planes: THREE.Plane[] = [];
  for (const ax of ['axial', 'coronal', 'sagittal'] as Axis[]) { const side = s.peel[ax]; if (side) planes.push(app.slices[ax].clippingPlane(side)); }
  for (const mesh of app.registry.loaded()) { const mat = mesh.material as THREE.Material; mat.clippingPlanes = planes.length ? planes : null; mat.side = planes.length ? THREE.DoubleSide : THREE.FrontSide; }
}

boot().catch((e) => { console.error(e); showMsg(t('boot.failed', { message: (e as Error).message })); });
