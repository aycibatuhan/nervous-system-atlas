import type { LabelsJson, Manifest } from '../types/manifest.ts';

export const DATA_URL = 'data/';

export async function loadManifest(): Promise<Manifest> {
  const r = await fetch(DATA_URL + 'manifest.json');
  if (!r.ok) throw new Error(`manifest.json: ${r.status}`);
  const m = (await r.json()) as Manifest;
  if (m.schema !== 1 || !Array.isArray(m.meshes)) throw new Error('manifest.json: unexpected schema');
  return m;
}

export async function loadLabels(): Promise<LabelsJson> {
  const r = await fetch(DATA_URL + 'volumes/labels.json');
  if (!r.ok) throw new Error(`labels.json: ${r.status}`);
  return (await r.json()) as LabelsJson;
}
