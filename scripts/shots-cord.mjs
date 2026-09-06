// Reference views of the PAM50 spinal cord MRI (atlas-pam50) into qa/shots/cord-mri/.
// Usage: npm run dev -- --port 5179, then: node scripts/shots-cord.mjs [port]
//
// Levels are read from cord_levels.json, which atlas-pam50 writes: `mid` gives the world point on our cord
// centreline halfway down a PAM50 spinal level, so the axial camera can look straight down the cord there.
// The axial views use a long lens (fov 6 deg) so the projection is near-orthographic; the opaque slice plane
// hides every mesh on its far side, so only the cord above the slice is visible in an axial shot.
import { readFileSync } from 'node:fs';
import { chromium } from '@playwright/test';
const base = `http://localhost:${process.argv[2] ?? 5179}`;
const out = 'qa/shots/cord-mri';

const levels = JSON.parse(readFileSync('public/data/volumes/cord_levels.json', 'utf8'));
const mid = (name) => {
  const l = levels.spinalLevels.find((x) => x.name === name);
  return { z: (l.top[2] + l.bottom[2]) / 2, x: (l.top[0] + l.bottom[0]) / 2, y: (l.top[1] + l.bottom[1]) / 2 };
};
const c5 = mid('C5'), t10 = mid('T10');

// axial views use a long lens (fov 6 deg at ~500 mm) so the projection is near-orthographic and the cord mesh,
// which runs 60 mm above and below the slice, lands on top of the MRI cord instead of splaying out in perspective
const VIEWS = [
  { name: 'axial-c5', axis: 'axial', at: c5, dir: [0, 0, 1], half: 24, fov: 6, label: 'C5' },
  { name: 'axial-c5-mri', axis: 'axial', at: c5, dir: [0, 0, 1], half: 22, fov: 6, systems: [], label: 'C5, MRI only' },
  { name: 'axial-t10', axis: 'axial', at: t10, dir: [0, 0, 1], half: 24, fov: 6, label: 'T10' },
  { name: 'axial-t10-mri', axis: 'axial', at: t10, dir: [0, 0, 1], half: 22, fov: 6, systems: [], label: 'T10, MRI only' },
  { name: 'sagittal-brain-to-cord', axis: 'sagittal', at: { x: -1, y: -140, z: -170 }, dir: [-1, 0, 0], half: 200, label: 'brain into cord' },
  { name: 'sagittal-cervical', axis: 'sagittal', at: { x: -1, y: -78, z: -110 }, dir: [-1, 0, 0], half: 70, label: 'craniocervical junction' },
];

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1400, height: 900 }, deviceScaleFactor: 1 });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
await page.goto(`${base}/`);
await page.waitForFunction(() => window.atlas?.store.get().loaded.manifest === true, null, { timeout: 60_000 });
await page.waitForFunction(() => window.atlas.store.get().loaded.volume === true, null, { timeout: 120_000 });
await page.evaluate(() => window.atlas.store.set({ quality: 'low', cordMri: true, contrast: 't2w' }));
await page.waitForFunction(() => window.atlas.store.get().loaded.cord === true, null, { timeout: 120_000 });
console.log('cord volume loaded');

for (const v of VIEWS) {
  await page.evaluate(([v]) => {
    const a = window.atlas;
    const pos = { axial: v.at.z, coronal: v.at.y, sagittal: v.at.x };
    a.store.set({
      visibleSystems: new Set(v.systems ?? ['spinal-cord']), peel: v.peel ? { [v.axis]: v.peel } : {}, cordMri: true, contrast: 't2w',
      slices: { ...a.store.get().slices, axial: Math.round(pos.axial), coronal: Math.round(pos.coronal), sagittal: Math.round(pos.sagittal),
                visible: { axial: v.axis === 'axial', coronal: false, sagittal: v.axis === 'sagittal' } },
    });
  }, [v]);
  try {
    await page.waitForFunction(() => { const a = window.atlas; const want = [...a.store.get().visibleSystems].flatMap((s) => (a.registry.bySystem.get(s) ?? []).map((m) => m.id)); return want.every((id) => a.registry.has(id)); }, null, { timeout: 30_000 });
  } catch { console.log('  mesh wait timed out for', v.name); }
  await page.waitForTimeout(600);
  // re-assert the peel: applyPeel only touches meshes already loaded, and these arrive lazily
  await page.evaluate(([v]) => window.atlas.store.set({ peel: v.peel ? { [v.axis]: v.peel } : {} }), [v]);
  await page.waitForTimeout(300);
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
console.log('page errors:', JSON.stringify(errors.filter((e) => !/favicon/.test(e))));
await browser.close();
