// Reference views of the VENAT deep cerebral veins into qa/shots/veins/ (envelope translucent).
// Usage: npm run dev -- --port 5175, then: node scripts/shots-veins.mjs
// Note: `peel` must be {} to clear it - a peel value of 'none' is treated as a clipping side.
import { chromium } from '@playwright/test';
const base = 'http://localhost:5175';
const out = 'qa/shots/veins';
const SYSTEMS = ['venous', 'envelope', 'ventricles-csf', 'diencephalon'];
const VIEWS = [
  { name: 'icv-medial-l',    id: 'vein-internal-cerebral', preset: '7', pad: 50 },
  { name: 'icv-superior',    id: 'vein-internal-cerebral', preset: '5', pad: 50 },
  { name: 'icv-lateral-l',   id: 'vein-internal-cerebral', preset: '1', pad: 50 },
  { name: 'galen-medial-l',  id: 'vein-great-cerebral',    preset: '7', pad: 55 },
  { name: 'galen-superior',  id: 'vein-great-cerebral',    preset: '5', pad: 55 },
  { name: 'basal-inferior',  id: 'vein-basal',             preset: '6', pad: 40 },
  { name: 'basal-lateral-l', id: 'vein-basal',             preset: '1', pad: 40 },
  { name: 'straight-medial-l', id: 'sinus-straight',       preset: '7', pad: 40 },
  { name: 'deep-veins-medial-l', id: null,                 preset: '7', pad: null },
  { name: 'venat-lateral-l', id: 'veins-venat-atlas',      preset: '1', pad: null },
  { name: 'venat-posterior', id: 'veins-venat-atlas',      preset: '4', pad: null },
];
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1400, height: 900 }, deviceScaleFactor: 1 });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
await page.goto(`${base}/`);
await page.waitForFunction(() => window.atlas?.store.get().loaded.manifest === true, null, { timeout: 60_000 });
console.log('manifest loaded');
await page.waitForTimeout(1500);
await page.evaluate(() => window.atlas.sm.resize());
for (const v of VIEWS) {
  // 1. route first (this expands visibleSystems and fits the camera on its own)
  await page.evaluate(([v]) => { location.hash = v.id ? `#/structure/${v.id}` : '#/slice'; }, [v]);
  await page.waitForTimeout(1800);
  // 2. now force the systems we want, the peel off and the slices off
  await page.evaluate(([sys]) => {
    const a = window.atlas;
    a.store.set({ quality: 'low', visibleSystems: new Set(sys), peel: {},
                  slices: { ...a.store.get().slices, visible: { axial: false, coronal: false, sagittal: false } } });
  }, [SYSTEMS]);
  try {
    await page.waitForFunction(() => { const a = window.atlas; const st = a.store.get(); const want = [...st.visibleSystems].flatMap((s) => (a.registry.bySystem.get(s) ?? []).map((m) => m.id)); return want.every((id) => a.registry.has(id)); }, null, { timeout: 25_000 });
  } catch { console.log('  systems wait timed out for', v.name); }
  await page.waitForTimeout(1200);
  // 3. camera last
  await page.evaluate(() => document.getElementById('gl').focus());
  await page.keyboard.press(v.preset);
  await page.waitForTimeout(600);
  await page.evaluate(([v]) => {
    const a = window.atlas;
    a.store.set({ peel: {} });
    if (v.pad == null || !v.id) { a.sm.fitToBox(a.registry.sceneBounds(), false); return; }
    const ms = a.manifest.meshes.filter((m) => m.structureId === v.id);
    const lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
    for (const m of ms) for (let k = 0; k < 3; k++) { lo[k] = Math.min(lo[k], m.bbox[0][k]); hi[k] = Math.max(hi[k], m.bbox[1][k]); }
    const b = a.registry.sceneBounds().clone();
    b.min.set(lo[0] - v.pad, lo[1] - v.pad, lo[2] - v.pad);
    b.max.set(hi[0] + v.pad, hi[1] + v.pad, hi[2] + v.pad);
    a.sm.fitToBox(b, false);
  }, [v]);
  await page.waitForTimeout(1200);
  await page.evaluate(() => { window.atlas.sm.resize(); window.atlas.sm.requestRender(); });
  await page.waitForTimeout(900);
  await page.evaluate(() => window.atlas.sm.requestRender());
  await page.waitForTimeout(600);
  const gb = await page.locator('#gl').boundingBox();
  await page.screenshot({ path: `${out}/${v.name}.png`, clip: gb });
  const st = await page.evaluate(() => ({ sys: [...window.atlas.store.get().visibleSystems], sel: window.atlas.store.get().selectedId }));
  console.log('saved', `${out}/${v.name}.png`, JSON.stringify(st));
}
console.log('page errors:', JSON.stringify(errors.filter((e) => !/favicon/.test(e))));
await browser.close();
