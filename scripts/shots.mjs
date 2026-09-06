// Capture reference views of the running dev server (npm run dev) into qa/shots/<tag>/.
// Usage: node scripts/shots.mjs <tag> [baseURL]
import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';

const tag = process.argv[2] ?? 'shots';
const base = process.argv[3] ?? 'http://localhost:5173';
const out = `qa/shots/${tag}`; mkdirSync(out, { recursive: true });
const quality = process.env.QUALITY === 'high' ? 'high' : 'low';
const VIEWS = [
  { name: 'lateral-l', hash: '#/slice', preset: 'lateral-l', systems: null },
  { name: 'inferior', hash: '#/slice', preset: 'inferior', systems: null },
  { name: 'medial-l-brainstem', hash: '#/structure/brainstem', preset: 'medial-l', systems: ['brainstem', 'cerebellum', 'cranial-nerves', 'diencephalon', 'basal-ganglia', 'ventricles-csf', 'arteries'] },
  { name: 'syndrome-wallenberg', hash: '#/syndrome/syn-wallenberg-lateral-medullary?step=1&side=l', preset: null, systems: null },
];
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1400, height: 900 }, deviceScaleFactor: 1 });
for (const v of VIEWS) {
  await page.goto(`${base}/${v.hash}`);
  await page.waitForFunction(() => window.atlas?.store.get().loaded.manifest === true, null, { timeout: 60_000 });
  await page.evaluate(async ([v, quality]) => {
    const a = window.atlas;
    a.store.set({ quality });
    if (v.systems) { a.store.set({ visibleSystems: new Set(v.systems), slices: { ...a.store.get().slices, visible: { axial: false, coronal: false, sagittal: false } } }); }
  }, [v, quality]);
  const KEY = { 'lateral-l': '1', 'lateral-r': '2', anterior: '3', posterior: '4', superior: '5', inferior: '6', 'medial-l': '7', 'medial-r': '8' };
  if (v.preset) { await page.evaluate(() => document.getElementById('gl').focus()); await page.keyboard.press(KEY[v.preset]); }
  // wait until nothing is pending in the registry (system loads settle)
  await page.waitForFunction(() => { const a = window.atlas; const st = a.store.get(); const want = [...st.visibleSystems].flatMap((s) => (a.registry.bySystem.get(s) ?? []).map((m) => m.id)); return want.every((id) => a.registry.has(id)); }, null, { timeout: 120_000 });
  await page.waitForFunction(() => [...window.atlas.registry.loaded()].every((m) => !m.userData.lod), null, { timeout: 120_000 });
  await page.waitForTimeout(1500);
  await page.evaluate(() => { const a = window.atlas; a.sm.requestRender(); });
  await page.waitForTimeout(400);
  await page.locator('#gl').screenshot({ path: `${out}/${v.name}.png` });
  console.log('saved', `${out}/${v.name}.png`);
}
await browser.close();
