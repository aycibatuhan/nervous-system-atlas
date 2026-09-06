import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import * as THREE from 'three';
import type { Manifest, SpineLabelsJson } from '../src/types/manifest.ts';
import { indexSpineLut, spineLevelAt, spineLevelLabel, spineMask } from '../src/volume/spineLabels.ts';
import { makeGrid } from '../src/volume/coords.ts';

const spine = JSON.parse(readFileSync('public/data/volumes/labels_spine.json', 'utf8')) as SpineLabelsJson;
const manifest = JSON.parse(readFileSync('public/data/manifest.json', 'utf8')) as Manifest;
const byId = indexSpineLut(spine);
const NAMES = [...Array.from({ length: 8 }, (_, i) => `C${i + 1}`), ...Array.from({ length: 12 }, (_, i) => `T${i + 1}`),
  ...Array.from({ length: 5 }, (_, i) => `L${i + 1}`), ...Array.from({ length: 5 }, (_, i) => `S${i + 1}`)];

describe('labels_spine.json (atlas-pam50)', () => {
  it('holds the 30 PAM50 spinal levels, ids 1..30 in rostrocaudal order', () => {
    expect(spine.volume).toBe('labels_spine');
    expect([...byId.keys()]).toEqual(NAMES.map((_, i) => i + 1));
    expect(NAMES.map((_, i) => byId.get(i + 1)!.name)).toEqual(NAMES);
  });

  it('groups the levels into the four cord regions and their segment meshes', () => {
    expect(Object.keys(spine.regions).sort()).toEqual(['cervical', 'lumbar', 'sacral', 'thoracic']);
    const meshIds = new Set(manifest.meshes.map((m) => m.id));
    const counts: Record<string, number> = {};
    for (const [, e] of byId) {
      const region = spine.regions[e.region];
      expect(region, e.name).toBeDefined();
      expect(e.meshId).toBe(region!.meshId);
      expect(e.structureId).toBe(e.meshId);
      expect(e.system).toBe('spinal-cord');
      expect(meshIds.has(e.meshId), `${e.meshId} is a manifest mesh`).toBe(true);
      counts[e.region] = (counts[e.region] ?? 0) + 1;
    }
    expect(counts).toEqual({ cervical: 8, thoracic: 12, lumbar: 5, sacral: 5 });
    for (const r of Object.values(spine.regions)) expect(r.levels.length).toBe(counts[r.levels[0]![0] === 'C' ? 'cervical' : r.levels[0]![0] === 'T' ? 'thoracic' : r.levels[0]![0] === 'L' ? 'lumbar' : 'sacral']);
  });

  it('gives every level a distinct colour on its region ramp, and every region one hue', () => {
    const colours = [...byId.values()].map((e) => e.colour);
    expect(colours.every((c) => /^#[0-9A-F]{6}$/.test(c))).toBe(true);
    expect(new Set(colours).size).toBe(30);
    const hue = (c: string) => { const h = { h: 0, s: 0, l: 0 }; new THREE.Color(c).getHSL(h); return h.h; };
    // one hue family per region (blues / greens / oranges / reds), and it moves less than a quarter turn inside it
    for (const key of Object.keys(spine.regions)) {
      const hs = [...byId.values()].filter((e) => e.region === key).map((e) => hue(e.colour));
      expect(Math.max(...hs) - Math.min(...hs), key).toBeLessThan(0.25);
    }
    const mid = (k: string) => { const hs = [...byId.values()].filter((e) => e.region === k).map((e) => hue(e.colour)); return hs[Math.floor(hs.length / 2)]!; };
    expect(mid('cervical')).toBeGreaterThan(0.5);                       // blue
    expect(mid('thoracic')).toBeGreaterThan(0.2); expect(mid('thoracic')).toBeLessThan(0.45);   // green
    expect(mid('lumbar')).toBeLessThan(0.12);                           // orange
    expect(Math.min(mid('sacral'), 1 - mid('sacral'))).toBeLessThan(0.05); // red
  });

  it('carries measured world z ranges that descend without gaps', () => {
    let prev = Infinity;
    for (let id = 1; id <= 30; id++) {
      const e = byId.get(id)!;
      expect(e.zMm, e.name).toBeDefined();
      const [lo, hi] = e.zMm!;
      expect(lo).toBeLessThan(hi);
      expect(hi).toBeLessThanOrEqual(prev + 0.5);
      prev = lo;
    }
    // the whole cord: C1 starts just under the foramen magnum, S5 ends at the conus
    expect(byId.get(1)!.zMm![1]).toBeGreaterThan(-80);
    expect(byId.get(30)!.zMm![0]).toBeLessThan(-450);
  });

  it('reads the level out of the label volume and names it for the readout', () => {
    // a 3x3x3 toy grid at 1 mm from the origin, with C5 (id 5) in the middle voxel
    const grid = makeGrid([3, 3, 3], [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]);
    const data = new Uint8Array(27);
    data[1 + 3 * (1 + 3 * 1)] = 5;
    const labels = { vol: { dims: [3, 3, 3] as [number, number, number], data }, json: spine, byId };
    const hit = spineLevelAt(labels, grid, new THREE.Vector3(1, 1, 1));
    expect(hit?.id).toBe(5);
    expect(hit?.entry.name).toBe('C5');
    expect(spineLevelLabel(hit!.entry)).toBe('C5 · cervical segment');
    expect(spineLevelAt(labels, grid, new THREE.Vector3(0, 0, 0))).toBeNull();   // id 0 = outside the cord
    expect(spineLevelAt(labels, grid, new THREE.Vector3(9, 9, 9))).toBeNull();   // off the grid
    expect(spineLevelAt(null, grid, new THREE.Vector3(1, 1, 1))).toBeNull();
  });

  it('packs a segment selection into one 32-bit level mask', () => {
    const cervical = spineMask(byId, (_id, e) => e.meshId === 'spinal-segment-cervical');
    expect(cervical).toBe(0b111111110);          // bits 1..8 = C1..C8
    for (let id = 1; id <= 30; id++) expect(((cervical >>> id) & 1) === 1).toBe(byId.get(id)!.region === 'cervical');
    expect(spineMask(byId, () => false)).toBe(0);
    expect(spineMask(byId, (id) => id === 30) >>> 0).toBe(2 ** 30);
  });
});
