// Reference views of the PUBLIC edition's spinal cord MRI (atlas-spine-generic) into qa/shots/public-cord-mri/.
// Serve the built public edition first:  npx vite preview --outDir dist-public --port 5183
// Usage:                                 node scripts/shots-public-cord.mjs [port]
//
// The private counterpart is scripts/shots-cord.mjs; this one proves the same thing for the edition that may
// actually be published: that grids.cord is there at all, that it is the spine-generic template and not the
// PAM50 one, that the cord MRI meets the MNI brain volume at the foramen magnum on a sagittal slice, and that
// the spinal levels the rootlets measured (C2..T1) are painted on the cord and name themselves under the
// cursor. Levels come from cord_levels_public.json, so the axial camera looks straight down the cord at C5.
import { readFileSync } from 'node:fs';
import { chromium } from '@playwright/test';
const base = `http://localhost:${process.argv[2] ?? 5183}`;
const out = 'qa/shots/public-cord-mri';

const levels = JSON.parse(readFileSync('public/data/volumes/cord_levels_public.json', 'utf8'));
const mid = (name) => {
  const l = levels.spinalLevels.find((x) => x.name === name);
  if (!l) throw new Error(`cord_levels_public.json has no level ${name}`);
  return { x: (l.top[0] + l.bottom[0]) / 2, y: (l.top[1] + l.bottom[1]) / 2, z: (l.top[2] + l.bottom[2]) / 2 };
};
const c5 = mid('C5'), t1 = mid('T1');

// axial views use a long lens (fov 6 deg) so the projection is near-orthographic and the cord mesh, which runs
// far above and below the slice, lands on top of the MRI cord instead of splaying out in perspective
const VIEWS = [
  { name: 'sagittal-brain-to-cord', axis: 'sagittal', at: { x: -1, y: -100, z: -140 }, dir: [-1, 0, 0], half: 150, label: 'brain into cord' },
  { name: 'sagittal-brain-to-cord-mri', axis: 'sagittal', at: { x: -1, y: -100, z: -140 }, dir: [-1, 0, 0], half: 150, systems: [], label: 'brain into cord, MRI only' },
  { name: 'sagittal-craniocervical', axis: 'sagittal', at: { x: -1, y: -70, z: -105 }, dir: [-1, 0, 0], half: 70, label: 'craniocervical junction' },
  { name: 'axial-c5', axis: 'axial', at: c5, dir: [0, 0, 1], half: 24, fov: 6, label: 'C5' },
  { name: 'axial-c5-mri', axis: 'axial', at: c5, dir: [0, 0, 1], half: 22, fov: 6, systems: [], label: 'C5, MRI only' },
  { name: 'axial-t1', axis: 'axial', at: t1, dir: [0, 0, 1], half: 24, fov: 6, label: 'T1' },
  // the level bands the rootlets measured, painted on the cord and lit up by the selected cervical block
  { name: 'sagittal-levels-selected', axis: 'sagittal', at: { x: -1, y: -72, z: -125 }, dir: [-1, 0, 0], half: 80,
    select: 'spinal-segment-cervical-vert', label: 'cervical block selected, C2-T1 level bands' },
];

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1400, height: 900 }, deviceScaleFactor: 1 });
const errors = [];
const problems = [];
const check = (ok, msg) => { if (!ok) problems.push(msg); console.log(`${ok ? 'ok  ' : 'FAIL'} ${msg}`); };
page.on('pageerror', (e) => errors.push(String(e)));
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
await page.goto(`${base}/#/structure/spinal-segment-cervical`);
await page.waitForFunction(() => window.atlas?.store.get().loaded.manifest === true, null, { timeout: 60_000 });
await page.waitForFunction(() => window.atlas.store.get().loaded.volume === true, null, { timeout: 120_000 });

const facts = await page.evaluate(() => {
  const m = window.atlas.manifest;
  const g = m.grids?.cord;
  return { edition: m.edition, grid: g ?? null, cordT2: m.volumes.cord_t2 ?? null, cordT1: m.volumes.cord_t1 ?? null,
           spine: m.volumes.labels_spine ?? null, source: g ? m.sources[g.source] ?? null : null };
});
check(facts.edition === 'public', `manifest edition is "${facts.edition}"`);
check(!!facts.grid, 'the public manifest declares grids.cord');
check(facts.grid?.source === 'spine_generic', `grids.cord source is ${facts.grid?.source}`);
check(facts.grid?.license === 'CC-BY-4.0', `grids.cord licence is ${facts.grid?.license}`);
check(!!facts.source, 'the cord grid names a source the manifest carries');
check(facts.cordT2?.file === 'volumes/cord_t2_public.u8.bin', `cord_t2 file is ${facts.cordT2?.file}`);
check(facts.cordT1 === null, 'the public edition ships no cord_t1 (the template is T2w only)');
check(facts.spine?.lut === 'volumes/labels_spine_public.json', `labels_spine lut is ${facts.spine?.lut}`);

await page.evaluate(() => window.atlas.store.set({ quality: 'low', cordMri: true, contrast: 't2w' }));
await page.waitForFunction(() => window.atlas.store.get().loaded.cord === true, null, { timeout: 120_000 });
console.log('public cord volume loaded');

// the T1w contrast has no cord volume in this edition: the cord must stay on screen, not blink out
await page.evaluate(() => window.atlas.store.set({ contrast: 't1w' }));
await page.waitForTimeout(1200);
check(await page.evaluate(() => window.atlas.uniforms.uHasCord.value === 1),
      'the cord MRI survives switching to the T1w contrast (it falls back to the T2w template)');
await page.evaluate(() => window.atlas.store.set({ contrast: 't2w' }));
await page.waitForTimeout(600);

// the spinal levels the rootlets measured must be readable off the volume
const lvl = await page.evaluate(([p]) => {
  const a = window.atlas;
  const v = new (Object.getPrototypeOf(a.sm.controls.target).constructor)(p.x, p.y, p.z);
  return a.spine ? { has: true, names: [...a.spine.byId.values()].map((e) => e.name).slice(0, 3), at: (() => {
    const dims = a.spine.vol.dims, g = a.cordGrid;
    const inv = g.inverse.clone(); const q = v.clone().applyMatrix4(inv);
    const i = Math.round(q.x), j = Math.round(q.y), k = Math.round(q.z);
    const id = a.spine.vol.data[i + dims[0] * (j + dims[1] * k)];
    return { id, name: a.spine.byId.get(id)?.name ?? null, mesh: a.spine.byId.get(id)?.meshId ?? null };
  })() } : { has: false };
}, [c5]);
check(lvl.has, 'the spinal-level volume and LUT loaded next to the cord MRI');
check(lvl.at?.name === 'C5', `the level at the mid-C5 point reads back as ${lvl.at?.name}`);
check(lvl.at?.mesh === 'spinal-segment-cervical-vert', `it names the cord block ${lvl.at?.mesh}`);

// the entry the task asks about: the cervical cord block, opened by URL, with the cord MRI on
await page.evaluate(() => window.atlas.sm.requestRender());
await page.waitForTimeout(1200);
await page.screenshot({ path: `${out}/structure-spinal-segment-cervical.png` });
console.log('saved', `${out}/structure-spinal-segment-cervical.png`);
// the structure route pins its mesh into `shownStructures`; clear that so the reference views below show
// exactly what the private scripts/shots-cord.mjs shows
await page.evaluate(() => window.atlas.store.set({ selectedId: null, shownStructures: new Set(), hiddenStructures: new Set() }));
await page.waitForTimeout(400);

for (const v of VIEWS) {
  await page.evaluate(([v]) => {
    const a = window.atlas;
    const pos = { axial: v.at.z, coronal: v.at.y, sagittal: v.at.x };
    a.store.set({
      visibleSystems: new Set(v.systems ?? ['spinal-cord']), peel: {}, cordMri: true, contrast: 't2w',
      selectedId: v.select ?? null,
      slices: { ...a.store.get().slices, axial: Math.round(pos.axial), coronal: Math.round(pos.coronal), sagittal: Math.round(pos.sagittal),
                visible: { axial: v.axis === 'axial', coronal: false, sagittal: v.axis === 'sagittal' } },
    });
  }, [v]);
  try {
    await page.waitForFunction(() => { const a = window.atlas; const want = [...a.store.get().visibleSystems].flatMap((s) => (a.registry.bySystem.get(s) ?? []).map((m) => m.id)); return want.every((id) => a.registry.has(id)); }, null, { timeout: 30_000 });
  } catch { console.log('  mesh wait timed out for', v.name); }
  await page.waitForTimeout(600);
  await page.evaluate(([v]) => {
    const a = window.atlas;
    const t = a.sm.controls.target; t.set(v.at.x, v.at.y, v.at.z);
    a.sm.camera.up.set(...(v.up ?? (v.axis === 'axial' ? [0, 1, 0] : [0, 0, 1])));
    a.sm.camera.fov = v.fov ?? 35;
    const dist = v.half / Math.tan((a.sm.camera.fov * Math.PI) / 360) * 1.05;
    const n = Math.hypot(...v.dir);
    a.sm.moveCamera(
      { x: t.x + (v.dir[0] / n) * dist, y: t.y + (v.dir[1] / n) * dist, z: t.z + (v.dir[2] / n) * dist },
      { x: t.x, y: t.y, z: t.z }, 0);
    a.sm.camera.near = 1; a.sm.camera.far = 4000; a.sm.camera.updateProjectionMatrix();
    a.sm.controls.update();
    a.sm.requestRender();
  }, [v]);
  await page.waitForTimeout(900);
  await page.evaluate(() => { window.atlas.sm.resize(); window.atlas.sm.requestRender(); });
  await page.waitForTimeout(900);
  const gb = await page.locator('#gl').boundingBox();
  await page.screenshot({ path: `${out}/${v.name}.png`, clip: gb });
  console.log('saved', `${out}/${v.name}.png`, v.label, JSON.stringify(v.at));
}
const real = errors.filter((e) => !/favicon/.test(e));
console.log('page errors:', JSON.stringify(real));
if (real.length) problems.push(`${real.length} page/console error(s)`);
await browser.close();
console.log(problems.length ? `FAILED: ${problems.length} problem(s)` : 'public cord MRI: all checks passed');
process.exit(problems.length ? 1 : 0);
