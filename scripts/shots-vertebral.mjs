// Reference views of the split + AP-corrected BodyParts3D vertebral arteries into qa/shots/vertebral/.
// Usage: npm run dev, then: node scripts/shots-vertebral.mjs [baseURL]
// Solos the posterior circulation with the brainstem and the cervical cord, so the two arteries can be
// checked separately (they used to be two copies of the whole vertebrobasilar tree) and their course
// checked against the brainstem and the cord (they used to run 15-20 mm behind both).
import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';

const base = process.argv[2] ?? 'http://localhost:5173';
const out = 'qa/shots/vertebral';
mkdirSync(out, { recursive: true });
const CORE = ['artery-vertebral-l', 'artery-vertebral-r', 'artery-basilar'];
const CONTEXT = ['brainstem', 'spinal-white-columns', 'artery-pica-l', 'artery-pica-r', 'artery-aica'];
const VIEWS = [
  { name: 'posterior', preset: '4', show: [...CORE, ...CONTEXT], box: 'core', pad: 30 },
  { name: 'lateral-l', preset: '1', show: [...CORE, ...CONTEXT], box: 'core', pad: 30 },
  { name: 'lateral-r', preset: '2', show: [...CORE, ...CONTEXT], box: 'core', pad: 30 },
  { name: 'anterior', preset: '3', show: [...CORE, ...CONTEXT], box: 'core', pad: 30 },
  { name: 'junction-posterior', preset: '4', show: [...CORE, 'brainstem'], box: 'junction', pad: 18 },
  { name: 'junction-lateral-l', preset: '1', show: [...CORE, 'brainstem'], box: 'junction', pad: 18 },
  { name: 'arteries-only-posterior', preset: '4', show: CORE, box: 'core', pad: 25 },
];
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1400, height: 900 }, deviceScaleFactor: 1 });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
await page.goto(`${base}/`);
await page.waitForFunction(() => window.atlas?.store.get().loaded.manifest === true, null, { timeout: 60_000 });
await page.waitForTimeout(1500);
await page.evaluate(() => window.atlas.sm.resize());
for (const v of VIEWS) {
  await page.evaluate(([v]) => {
    const a = window.atlas;
    a.store.set({ quality: 'low', selectedId: null, visibleSystems: new Set(), hiddenStructures: new Set(),
                  shownStructures: new Set(v.show), peel: {},
                  slices: { ...a.store.get().slices, visible: { axial: false, coronal: false, sagittal: false } } });
  }, [v]);
  try {
    await page.waitForFunction(([show]) => show.every((id) => window.atlas.registry.has(id)), [v.show], { timeout: 60_000 });
    await page.waitForFunction(() => [...window.atlas.registry.loaded()].every((m) => !m.userData.lod), null, { timeout: 60_000 });
  } catch { console.log('  load wait timed out for', v.name); }
  await page.waitForTimeout(900);
  await page.evaluate(() => document.getElementById('gl').focus());
  await page.keyboard.press(v.preset);
  await page.waitForTimeout(600);
  await page.evaluate(([v]) => {
    const a = window.atlas;
    const ids = v.box === 'junction' ? ['artery-basilar'] : ['artery-vertebral-l', 'artery-vertebral-r', 'artery-basilar'];
    const ms = a.manifest.meshes.filter((m) => ids.includes(m.id));
    const lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
    for (const m of ms) for (let k = 0; k < 3; k++) { lo[k] = Math.min(lo[k], m.bbox[0][k]); hi[k] = Math.max(hi[k], m.bbox[1][k]); }
    if (v.box === 'junction') { lo[2] = -75; hi[2] = -30; }
    const b = a.registry.sceneBounds().clone();
    b.min.set(lo[0] - v.pad, lo[1] - v.pad, lo[2] - v.pad);
    b.max.set(hi[0] + v.pad, hi[1] + v.pad, hi[2] + v.pad);
    a.sm.fitToBox(b, false);
  }, [v]);
  await page.waitForTimeout(1000);
  await page.evaluate(() => { window.atlas.sm.resize(); window.atlas.sm.requestRender(); });
  await page.waitForTimeout(800);
  const gb = await page.locator('#gl').boundingBox();
  await page.screenshot({ path: `${out}/${v.name}.png`, clip: gb });
  console.log('saved', `${out}/${v.name}.png`);
}
await browser.close();
if (errors.length) { console.error('page errors:', errors.slice(0, 5)); process.exit(1); }
