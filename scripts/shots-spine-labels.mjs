// Reference views of the PAM50 spinal-level overlay (atlas-pam50 labels_spine + labels_spine.json) into
// qa/shots/spine-labels/.  Usage: npm run dev, then: node scripts/shots-spine-labels.mjs [port]
//
// The level points come from cord_levels.json, so an axial camera can look straight down the cord at the middle
// of a named level.  Meshes are switched off in every view: the subject is the slice itself -- the per-level
// ramp under "all labels", and the 1-voxel outline the shader draws around the selected cord segment.
import { readFileSync } from 'node:fs';
import { mkdirSync } from 'node:fs';
import { chromium } from '@playwright/test';
const base = `http://localhost:${process.argv[2] ?? 5173}`;
const out = 'qa/shots/spine-labels';
mkdirSync(out, { recursive: true });

const levels = JSON.parse(readFileSync('public/data/volumes/cord_levels.json', 'utf8'));
const mid = (name) => {
  const l = levels.spinalLevels.find((x) => x.name === name);
  return { x: (l.top[0] + l.bottom[0]) / 2, y: (l.top[1] + l.bottom[1]) / 2, z: (l.top[2] + l.bottom[2]) / 2 };
};
const c5 = mid('C5'), t10 = mid('T10'), c1 = mid('C1'), s5 = mid('S5');

const VIEWS = [
  { name: 'axial-c5-levels', axis: 'axial', at: c5, dir: [0, 0, 1], half: 20, fov: 6,
    select: 'spinal-segment-cervical', label: 'C5, cervical segment selected' },
  { name: 'axial-t10-levels', axis: 'axial', at: t10, dir: [0, 0, 1], half: 20, fov: 6,
    select: 'spinal-segment-thoracic', label: 'T10, thoracic segment selected' },
  { name: 'sagittal-level-ramp', axis: 'sagittal', at: { x: 0, y: (c1.y + s5.y) / 2, z: (c1.z + s5.z) / 2 },
    dir: [-1, 0, 0], half: (c1.z - s5.z) / 2 + 25, select: null, label: 'C1 to S5, the level ramp along the cord' },
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
await page.waitForFunction(() => window.atlas.spine !== null, null, { timeout: 60_000 });
console.log('cord volume + spinal levels loaded:', await page.evaluate(() => window.atlas.spine.byId.size), 'levels');

for (const v of VIEWS) {
  await page.evaluate(([v]) => {
    const a = window.atlas;
    a.store.set({
      visibleSystems: new Set(), shownStructures: new Set(), hiddenStructures: new Set(), peel: {},
      cordMri: true, contrast: 't2w', selectedId: v.select,
      overlay: { ...a.store.get().overlay, showAllLabels: true, opacity: 0.75, territory: false, tracts: false },
      slices: { axial: Math.round(v.at.z), coronal: Math.round(v.at.y), sagittal: Math.round(v.at.x), pinned: true,
                visible: { axial: v.axis === 'axial', coronal: false, sagittal: v.axis === 'sagittal' } },
    });
  }, [v]);
  await page.waitForTimeout(500);
  await page.evaluate(([v]) => {
    const a = window.atlas;
    const t = a.sm.controls.target; t.set(v.at.x, v.at.y, v.at.z);
    a.sm.camera.up.set(...(v.axis === 'axial' ? [0, 1, 0] : [0, 0, 1]));
    a.sm.camera.fov = v.fov ?? 35;
    const dist = (v.half / Math.tan((a.sm.camera.fov * Math.PI) / 360)) * 1.05;
    const n = Math.hypot(...v.dir);
    a.sm.moveCamera({ x: t.x + (v.dir[0] / n) * dist, y: t.y + (v.dir[1] / n) * dist, z: t.z + (v.dir[2] / n) * dist },
      { x: t.x, y: t.y, z: t.z }, 0);
    a.sm.camera.near = 1; a.sm.camera.far = 4000; a.sm.camera.updateProjectionMatrix();
    a.sm.controls.update(); a.sm.requestRender();
  }, [v]);
  await page.waitForTimeout(900);
  await page.evaluate(() => { window.atlas.sm.resize(); window.atlas.sm.requestRender(); });
  await page.waitForTimeout(900);
  const gb = await page.locator('#gl').boundingBox();
  await page.screenshot({ path: `${out}/${v.name}.png`, clip: gb });
  const sel = await page.evaluate(() => window.atlas.uniforms.uSpineSel.value);
  console.log('saved', `${out}/${v.name}.png`, '·', v.label, '· level mask', sel.toString(2));
}
console.log('page errors:', JSON.stringify(errors.filter((e) => !/favicon/.test(e))));
await browser.close();
