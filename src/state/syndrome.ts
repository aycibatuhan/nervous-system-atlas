import * as THREE from 'three';
import type { App } from '../app.ts';
import { applyStates, applyCameraPreset, setSlices, setStructureVisible } from './actions.ts';
import type { PresetName } from '../types/state.ts';

type Rec = Record<string, unknown>;
export type LesionSide = 'l' | 'r';

/** Mesh ids for a content id (structure, cranial nerve or pathway), filtered to one side when the meshes are paired. */
export function meshesFor(app: App, id: string, side: LesionSide | 'both'): string[] {
  const c = app.content;
  let ids: string[] = [];
  const st = c?.structures[id] as Rec | undefined;
  const pw = c?.pathways[id] as Rec | undefined;
  if (st) ids = (st['meshIds'] as string[] | undefined) ?? [];
  else if (pw) ids = [...((pw['meshIds'] as string[]) ?? []), ...((pw['waypoints'] as Rec[]) ?? []).map((w) => w['meshId'] as string | undefined).filter((x): x is string => !!x)];
  for (const m of app.manifest.meshes) if (m.structureId === id && !ids.includes(m.id)) ids.push(m.id);
  ids = ids.filter((m) => app.registry.byId.has(m));
  if (side === 'both') return ids;
  const paired = ids.filter((m) => /-[lr]$/.test(m));
  if (!paired.length) return ids;
  return ids.filter((m) => !/-[lr]$/.test(m) || m.endsWith(`-${side}`));
}

export interface ResolvedSyndrome {
  syn: Rec; side: LesionSide | 'both';
  involved: Set<string>;
  lesion: { mni: [number, number, number]; radius: number } | null;
  focus: [number, number, number] | null;
}

function pickSide(syn: Rec, override?: LesionSide): LesionSide | 'both' {
  if (override) return override;
  const s = String((syn['localisation'] as Rec)['side']);
  if (s === 'right') return 'r';
  if (s === 'left') return 'l';
  if (s === 'bilateral' || s === 'midline') return 'both';
  return 'l';
}

function mniOf(app: App, ref: unknown, side: LesionSide | 'both'): [number, number, number] | null {
  if (!ref || typeof ref !== 'object') return null;
  const r = ref as Rec;
  if (typeof r['x'] === 'number') {
    const p: [number, number, number] = [r['x'] as number, r['y'] as number, r['z'] as number];
    if (side === 'r' && p[0] < 0) p[0] = -p[0];            // authored on the left; mirror for a right-sided demo
    if (side === 'l' && p[0] > 0) p[0] = -p[0];
    return p;
  }
  if (typeof r['meshId'] === 'string') { const m = app.registry.byId.get(r['meshId'] as string); if (m) return [m.centroid[0], m.centroid[1], m.centroid[2]]; }
  return null;
}

export function resolveSyndrome(app: App, id: string, override?: LesionSide): ResolvedSyndrome | null {
  const syn = app.content?.syndromes[id] as Rec | undefined;
  if (!syn) return null;
  const side = pickSide(syn, override);
  const involved = new Set<string>();
  const loc = syn['localisation'] as Rec;
  for (const sid of (loc['structures'] as string[]) ?? []) for (const m of meshesFor(app, sid, side)) involved.add(m);
  const marker = (syn['lesionMarker'] as Rec) ?? {};
  const markerMeshes = ((marker['meshIds'] as string[] | undefined) ?? []).map((m) => (side === 'r' ? m.replace(/-l$/, '-r') : side === 'l' ? m.replace(/-r$/, '-l') : m)).filter((m) => app.registry.byId.has(m));
  for (const m of markerMeshes) involved.add(m);
  let lesion: ResolvedSyndrome['lesion'] = null;
  if ((marker['kind'] === 'sphere' || marker['kind'] === 'segment') && marker['mni']) {
    const p = mniOf(app, marker['mni'], side);
    if (p) lesion = { mni: p, radius: (marker['radiusMm'] as number | undefined) ?? 8 };
  }
  let focus = lesion?.mni ?? null;
  if (!focus) { const hintP = mniOf(app, (syn['imagingHint'] as Rec | undefined)?.['mni'], side); focus = hintP; }
  if (!focus && markerMeshes.length) { const m = app.registry.byId.get(markerMeshes[0]!)!; focus = [m.centroid[0], m.centroid[1], m.centroid[2]]; }
  if (!focus && involved.size) { const m = app.registry.byId.get([...involved][0]!)!; focus = [m.centroid[0], m.centroid[1], m.centroid[2]]; }
  return { syn, side, involved, lesion, focus };
}

/** Meshes to spotlight for one deficit step (its substrate), falling back to the whole involved set. */
export function stepMeshes(app: App, res: ResolvedSyndrome, step: number): Set<string> {
  const deficits = (res.syn['deficits'] as Rec[]) ?? [];
  const d = deficits[step];
  if (!d || !d['substrate']) return new Set();
  const sub = String(d['substrate']);
  const dside = String(d['side']);
  let side: LesionSide | 'both' = res.side;
  if (res.side !== 'both') { if (dside === 'contralateral') side = res.side === 'l' ? 'r' : 'l'; else if (dside === 'bilateral' || dside === 'n/a') side = 'both'; }
  return new Set(meshesFor(app, sub, side));
}

let shownForSyndrome: string[] = [];

export function enterSyndrome(app: App, id: string, step = 0, override?: LesionSide): void {
  const cur = app.store.get().syndrome;
  const res = resolveSyndrome(app, id, override);
  if (!res) return;
  const first = !cur || cur.id !== id;
  if (first) {
    exitSyndrome(app, false);
    for (const m of res.involved) if (!app.store.get().shownStructures.has(m)) { setStructureVisible(app, m, true); shownForSyndrome.push(m); }
    const preset = res.syn['cameraPreset'] as PresetName | undefined;
    if (preset) applyCameraPreset(app, preset);
    if (res.focus) setSlices(app, { sagittal: Math.round(res.focus[0]), coronal: Math.round(res.focus[1]), axial: Math.round(res.focus[2]) });
    if (res.lesion) { app.lesion.position.set(...res.lesion.mni); app.lesion.scale.setScalar(res.lesion.radius); app.lesion.visible = true; } else app.lesion.visible = false;
    void app.registry.ensure(res.involved).then(() => applyStates(app));
    if (res.focus) { const c = new THREE.Vector3(...res.focus); app.sm.fitToBox(new THREE.Box3(c.clone().subScalar(45), c.clone().addScalar(45))); }
  }
  const stepSet = stepMeshes(app, res, step);
  void app.registry.ensure(stepSet).then(() => applyStates(app));
  app.store.set({ syndrome: { id, step }, involved: res.involved, stepHighlight: stepSet, selectedId: null, hoverId: null, lesionSide: res.side === 'both' ? null : res.side });
  applyStates(app);
}

export function setSyndromeStep(app: App, step: number): void {
  const s = app.store.get().syndrome; if (!s) return;
  enterSyndrome(app, s.id, step, app.store.get().lesionSide ?? undefined);
}

export function exitSyndrome(app: App, notify = true): void {
  for (const m of shownForSyndrome) setStructureVisible(app, m, false);
  shownForSyndrome = [];
  app.lesion.visible = false;
  if (notify || app.store.get().syndrome) app.store.set({ syndrome: null, involved: new Set(), stepHighlight: new Set() });
  applyStates(app);
}
