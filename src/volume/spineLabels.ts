import type * as THREE from 'three';
import type { SpineLabelsJson, SpineLevelEntry } from '../types/manifest.ts';
import { DATA_URL } from '../loader/manifest.ts';
import type { VolumeData } from './VolumeSource.ts';
import { mmToVoxel, type VolumeGrid } from './coords.ts';

/** The PAM50 spinal-level volume plus its lookup table, loaded next to the cord MRI. */
export interface SpineLabels {
  vol: VolumeData;
  json: SpineLabelsJson;
  /** level id -> entry, with the id already parsed */
  byId: Map<number, SpineLevelEntry>;
}

/** Fetch labels_spine.json (manifest.volumes.labels_spine.lut) and index it by id. */
export async function loadSpineLut(lutPath = 'volumes/labels_spine.json'): Promise<SpineLabelsJson> {
  const r = await fetch(DATA_URL + lutPath);
  if (!r.ok) throw new Error(`${lutPath}: ${r.status}`);
  const j = (await r.json()) as SpineLabelsJson;
  if (!j.lut || !j.regions) throw new Error(`${lutPath}: unexpected shape`);
  return j;
}

export function indexSpineLut(json: SpineLabelsJson): Map<number, SpineLevelEntry> {
  return new Map(Object.entries(json.lut).map(([id, e]) => [Number(id), e]));
}

/** The spinal level at a world point, or null when the point is off the cord grid or outside the cord. */
export function spineLevelAt(spine: SpineLabels | null, cordGrid: VolumeGrid | null, p: THREE.Vector3):
  { id: number; entry: SpineLevelEntry } | null {
  if (!spine || !cordGrid) return null;
  const { dims, data } = spine.vol;
  const v = mmToVoxel(p, cordGrid);
  const i = Math.round(v.x), j = Math.round(v.y), k = Math.round(v.z);
  if (i < 0 || j < 0 || k < 0 || i >= dims[0] || j >= dims[1] || k >= dims[2]) return null;
  const id = data[i + dims[0] * (j + dims[1] * k)]!;
  if (!id) return null;
  const entry = spine.byId.get(id);
  return entry ? { id, entry } : null;
}

/** "C5 · cervical segment", plus " (vertebral rule)" for a level placed by the rule rather than measured. */
export function spineLevelLabel(e: SpineLevelEntry): string {
  return `${e.name} · ${e.region} segment` + (e.estimated ? ' (vertebral rule)' : '');
}

/** 32-bit mask of the level ids a predicate selects (ids are 1..30, so one uint carries them all). */
export function spineMask(byId: Map<number, SpineLevelEntry>, pick: (id: number, e: SpineLevelEntry) => boolean): number {
  let m = 0;
  for (const [id, e] of byId) if (id > 0 && id < 32 && pick(id, e)) m |= 1 << id;
  return m >>> 0;
}
