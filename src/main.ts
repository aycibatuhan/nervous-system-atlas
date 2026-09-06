import * as THREE from 'three';
import WebGL from 'three/addons/capabilities/WebGL.js';
import { createApp, type App } from './app.ts';
import { loadLabels, loadManifest } from './loader/manifest.ts';
import { Picker } from './picking/Picker.ts';
import { TreePanel } from './ui/TreePanel.ts';
import { SliceControls } from './ui/SliceControls.ts';
import { ContentPanel } from './ui/ContentPanel.ts';
import { Toolbar } from './ui/Toolbar.ts';
import { h } from './ui/dom.ts';
import { applyStates, selectStructure, setHover, setSlices, syncVisibility } from './state/actions.ts';
import { loadRawVolume } from './volume/VolumeSource.ts';
import { makeIntensityTexture, makeLabelTexture } from './volume/textures.ts';
import { mmToVoxel } from './volume/coords.ts';
import type { SystemId } from './types/manifest.ts';
import type { Axis } from './types/state.ts';
import { PRESETS } from './scene/cameraPresets.ts';
import { applyCameraPreset, setContrast, setSliceVisible, setPeel } from './state/actions.ts';
import { sameSet } from './state/actions.ts';

const msg = document.getElementById('overlay-msg')!;
function showMsg(text: string | null): void { msg.hidden = !text; msg.textContent = text ?? ''; }

async function boot(): Promise<void> {
  if (!WebGL.isWebGL2Available()) { showMsg('This atlas needs WebGL 2 (any current Chrome, Firefox, Safari or Edge).'); return; }
  showMsg('Loading atlas manifest…');
  const manifest = await loadManifest();
  const canvas = document.getElementById('gl') as HTMLCanvasElement;
  const app = createApp(canvas, manifest);
  (window as unknown as { atlas: App }).atlas = app;
  app.picker = new Picker(app.sm, app.registry, {
    onHover: (hit) => { setHover(app, hit.id); canvas.style.cursor = hit.id || hit.onSlice ? 'pointer' : ''; hud(hit.point); },
    onSelect: (hit, ev) => {
      if (hit.onSlice && hit.point) { const id = structureAt(app, hit.point); if (id) { selectStructure(app, id, { moveSlices: false }); return; } }
      if (hit.id) selectStructure(app, hit.id, { moveSlices: !ev.shiftKey });
      else if (!ev.shiftKey) selectStructure(app, null);
    },
  });
  app.picker.extra = Object.values(app.slices).map((s) => s.mesh);

  // ---- UI
  const left = document.getElementById('left')!; const right = document.getElementById('right')!; const bottom = document.getElementById('bottom')!; const top = document.getElementById('toolbar')!;
  const tree = new TreePanel(app, left);
  new SliceControls(app, bottom);
  new ContentPanel(app, right);
  const help = h('div', { class: 'help', hidden: true }, h('b', {}, 'Shortcuts'), h('br'),
    ...PRESETS.map((p) => h('div', {}, h('kbd', {}, p.key), ' ', p.label)),
    h('div', {}, h('kbd', {}, 'a'), '/', h('kbd', {}, 'c'), '/', h('kbd', {}, 's'), ' toggle axial / coronal / sagittal slice'),
    h('div', {}, h('kbd', {}, '↑'), h('kbd', {}, '↓'), ' move the last touched slice'), h('div', {}, h('kbd', {}, 't'), ' T1 / T2'),
    h('div', {}, h('kbd', {}, 'p'), ' peel at the axial slice'), h('div', {}, h('kbd', {}, '['), h('kbd', {}, ']'), ' toggle panels'),
    h('div', {}, h('kbd', {}, 'Esc'), ' clear selection'), h('div', {}, h('kbd', {}, 'Shift'), '+click: select without moving slices'));
  document.getElementById('viewport')!.append(help);
  const toolbar = new Toolbar(app, top, { onSearchFocus: () => (left.querySelector('.tree-filter') as HTMLInputElement)?.focus(), onHelp: () => { help.hidden = !help.hidden; } });
  const hudEl = h('div', { class: 'hud' }); document.getElementById('viewport')!.append(hudEl);
  const progress = h('div', { class: 'progress' }); document.getElementById('viewport')!.append(progress);
  function hud(p: THREE.Vector3 | null): void { hudEl.textContent = p ? `MNI ${p.x.toFixed(0)}, ${p.y.toFixed(0)}, ${p.z.toFixed(0)} mm` : ''; }

  // ---- state → scene wiring
  app.store.subscribe((s) => s.visibleSystems, () => syncVisibility(app), sameSet);
  app.store.subscribe((s) => s.hiddenStructures, () => syncVisibility(app), sameSet);
  app.store.subscribe((s) => s.shownStructures, () => syncVisibility(app), sameSet);
  app.store.subscribe((s) => s.showNc, () => { syncVisibility(app); tree.render(); });
  app.store.subscribe((s) => [s.selectedId, s.hoverId, s.syndrome] as const, () => { applyStates(app); updateLuts(app); }, (a, b) => a[0] === b[0] && a[1] === b[1] && a[2] === b[2]);
  app.store.subscribe((s) => s.slices, (sl) => { for (const ax of ['axial', 'coronal', 'sagittal'] as Axis[]) { app.slices[ax].setPosition(sl[ax]); app.slices[ax].setVisible(sl.visible[ax] && app.store.get().loaded.volume); } applyPeel(app); app.sm.requestRender(); });
  app.store.subscribe((s) => s.peel, () => { applyPeel(app); app.sm.requestRender(); });
  app.store.subscribe((s) => s.overlay, (o) => { app.uniforms.uOverlayOpacity.value = o.opacity; app.uniforms.uShowAllLabels.value = o.showAllLabels ? 1 : 0; updateLuts(app); app.sm.requestRender(); });
  app.store.subscribe((s) => s.windowLevel, (w) => { app.uniforms.uWindow.value = w.window; app.uniforms.uLevel.value = w.level; app.sm.requestRender(); });
  app.store.subscribe((s) => s.contrast, (c) => void loadContrast(app, c, progress));
  app.registry.byId.forEach(() => undefined);
  // reflect newly loaded meshes
  const origOnChange = (app.registry as unknown as { onChange: (id: string) => void }).onChange;
  (app.registry as unknown as { onChange: (id: string) => void }).onChange = (id: string) => { origOnChange(id); app.registry.setVisible(id, meshVisible(app, id)); app.registry.invalidatePickCache(); applyStates(app); };

  // ---- initial visibility: systems flagged defaultVisible
  const defaults = new Set<SystemId>(manifest.systems.filter((s) => s.defaultVisible).map((s) => s.id));
  app.store.set({ visibleSystems: defaults, loaded: { ...app.store.get().loaded, manifest: true } });
  showMsg(null);
  applyCameraPreset(app, 'lateral-l');
  toolbar.status.textContent = `${manifest.meshes.length} structures`;

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
    } catch (e) { console.error(e); toolbar.status.textContent = 'volume load failed: ' + (e as Error).message; }
  })();

  // ---- keyboard
  let lastAxis: Axis = 'axial';
  window.addEventListener('keydown', (e) => {
    if ((e.target as HTMLElement).tagName === 'INPUT' || (e.target as HTMLElement).tagName === 'SELECT') return;
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
      case 'p': setPeel(app, 'axial', s.peel.axial ? null : 'positive'); break;
      case '[': document.getElementById('app')!.classList.toggle('no-left'); app.sm.resize(); break;
      case ']': document.getElementById('app')!.classList.toggle('no-right'); app.sm.resize(); break;
      case 'Escape': selectStructure(app, null); break;
      case '?': help.hidden = !help.hidden; break;
      case 'S': if (e.shiftKey) void toolbar.shot(); break;
    }
  });
}

function meshVisible(app: App, id: string): boolean {
  const s = app.store.get(); const m = app.registry.byId.get(id)!;
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

/** anat label under a world point → mesh id */
function structureAt(app: App, p: THREE.Vector3): string | null {
  const vol = (app as unknown as { anatVolume?: { dims: number[]; data: Uint16Array } }).anatVolume;
  if (!vol || !app.labels) return null;
  const v = mmToVoxel(p, app.grid);
  const i = Math.round(v.x), j = Math.round(v.y), k = Math.round(v.z);
  if (i < 0 || j < 0 || k < 0 || i >= vol.dims[0]! || j >= vol.dims[1]! || k >= vol.dims[2]!) return null;
  const id = vol.data[i + vol.dims[0]! * (j + vol.dims[1]! * k)]!;
  return id ? app.labels.lut.anat[String(id)]?.meshId ?? null : null;
}

/** Rebuild the colour/flag lookup textures from the current state. */
function updateLuts(app: App): void {
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
  if (s.hoverId && s.hoverId !== s.selectedId) mark(s.hoverId, 4, 0.35);
  if (s.selectedId) mark(s.selectedId, 1, 0.6);
  if (s.overlay.territory) for (const [id, e] of Object.entries(lut.vascular)) terr.set(Number(id), e.colour, 0.5);
  if (s.overlay.tracts) for (const [id, e] of Object.entries(lut.tract)) tract.set(Number(id), e.colour, 0.5);
  app.sm.requestRender();
}

function applyPeel(app: App): void {
  const s = app.store.get();
  const planes: THREE.Plane[] = [];
  for (const ax of ['axial', 'coronal', 'sagittal'] as Axis[]) { const side = s.peel[ax]; if (side) planes.push(app.slices[ax].clippingPlane(side)); }
  for (const mesh of app.registry.loaded()) { const mat = mesh.material as THREE.Material; mat.clippingPlanes = planes.length ? planes : null; mat.side = planes.length ? THREE.DoubleSide : THREE.FrontSide; }
}

boot().catch((e) => { console.error(e); showMsg('Failed to start: ' + (e as Error).message); });
