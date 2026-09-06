// Anterior/posterior views of the cord, roots and plexuses, for the Z-Anatomy sub-cranial midline check.
// Usage: node scripts/shots-midline.mjs [tag] [baseURL]     (dev server: npm run dev)
import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';

const tag = process.argv[2] ?? 'midline';
const base = process.argv[3] ?? 'http://localhost:5173';
const out = `qa/shots/${tag}`;
mkdirSync(out, { recursive: true });
const SYSTEMS = ['spinal-cord', 'peripheral', 'autonomic'];
const CN_LOWER = ['09-glossopharyngeal', '10-vagus', '11-accessory', '12-hypoglossal']
  .flatMap((n) => [`cn-${n}-l`, `cn-${n}-r`]);
// Camera framing is explicit: the standard presets frame the brain, and everything measured here sits
// 100-600 mm below it.  `dir` is the view direction, the box is the MNI region to fit.
// `ids`, when given, names the meshes to show instead of every mesh of the listed systems -- the ap-* views
// need the aseg brainstem next to the Z-Anatomy cord, and the `brainstem` system also holds ~200 nuclei.
const VIEWS = [
  { name: 'anterior-cord-roots-plexuses', dir: [0, 1, 0], systems: SYSTEMS, box: [[-190, -320, -640], [190, -40, -40]] },
  { name: 'posterior-cord-roots-plexuses', dir: [0, -1, 0], systems: SYSTEMS, box: [[-190, -320, -640], [190, -40, -40]] },
  { name: 'anterior-cord-roots', dir: [0, 1, 0], systems: ['spinal-cord', 'autonomic'], box: [[-60, -320, -640], [60, -40, -40]] },
  { name: 'anterior-cervical-cord-roots', dir: [0, 1, 0], systems: ['spinal-cord', 'autonomic'], box: [[-45, -180, -240], [45, -40, -50]] },
  // the anteroposterior post-correction: the Z-Anatomy cord must run out of the MNI aseg brainstem, not
  // behind it.  Lateral, so the AP relationship is the one thing the view shows.
  { name: 'ap-lateral-brainstem-cord', dir: [1, 0, 0], systems: ['brainstem', 'spinal-cord'],
    ids: ['brainstem', 'spinal-white-columns', 'spinal-segment-cervical', 'spinal-segment-thoracic'],
    box: [[-40, -140, -300], [40, 20, 10]] },
  { name: 'ap-lateral-cmj', dir: [1, 0, 0], systems: ['brainstem', 'spinal-cord'],
    ids: ['brainstem', 'spinal-white-columns', 'spinal-grey-anterior-horn', 'spinal-segment-cervical'],
    box: [[-30, -90, -140], [30, -10, -10]] },
  { name: 'ap-lateral-cmj-cranial-nerves', dir: [1, 0, 0], systems: ['brainstem', 'spinal-cord', 'cranial-nerves'],
    ids: ['brainstem', 'spinal-white-columns', 'spinal-segment-cervical', ...CN_LOWER],
    box: [[-40, -100, -160], [40, 0, -5]] },
  { name: 'ap-posterior-cmj', dir: [0, -1, 0], systems: ['brainstem', 'spinal-cord'],
    ids: ['brainstem', 'spinal-white-columns', 'spinal-segment-cervical'],
    box: [[-40, -90, -160], [40, -10, -10]] },
];
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1400, height: 900 }, deviceScaleFactor: 1 });
for (const v of VIEWS) {
  await page.goto(`${base}/#/slice`);
  await page.waitForFunction(() => window.atlas?.store.get().loaded.manifest === true, null, { timeout: 60_000 });
  await page.evaluate(async (v) => {
    const a = window.atlas;
    a.store.set({ quality: 'low' });
    // most Z-Anatomy meshes are off by default in the manifest, so name them explicitly
    const ids = v.ids ?? v.systems.flatMap((s) => (a.registry.bySystem.get(s) ?? []).map((m) => m.id));
    a.store.set({
      visibleSystems: new Set(v.systems),
      shownStructures: new Set(ids),
      hiddenStructures: new Set(),
      slices: { ...a.store.get().slices, visible: { axial: false, coronal: false, sagittal: false } },
    });
  }, v);
  await page.evaluate(() => document.getElementById('gl').focus());
  await page.waitForFunction((v) => {
    const a = window.atlas; const st = a.store.get();
    const want = v.ids ?? [...st.visibleSystems].flatMap((s) => (a.registry.bySystem.get(s) ?? []).map((m) => m.id));
    return want.every((id) => a.registry.has(id));
  }, v, { timeout: 180_000 });
  await page.waitForFunction(() => [...window.atlas.registry.loaded()].every((m) => !m.userData.lod), null, { timeout: 180_000 });
  await page.waitForTimeout(1200);
  await page.evaluate((v) => {
    const a = window.atlas;
    const [lo, hi] = v.box;
    const c = [0, 1, 2].map((i) => (lo[i] + hi[i]) / 2);
    const r = Math.max(...[0, 1, 2].map((i) => (hi[i] - lo[i]) / 2));
    const fov = (a.sm.camera.fov * Math.PI) / 180;
    const d = (r / Math.tan(fov / 2)) * 1.15;
    const n = Math.hypot(...v.dir);
    const pos = [0, 1, 2].map((i) => c[i] + (v.dir[i] / n) * d);
    a.sm.moveCamera(new a.sm.camera.position.constructor(pos[0], pos[1], pos[2]),
                    new a.sm.camera.position.constructor(c[0], c[1], c[2]), 0);
  }, v);
  await page.waitForTimeout(600);
  await page.evaluate(() => window.atlas.sm.requestRender());
  await page.waitForTimeout(400);
  await page.locator('#gl').screenshot({ path: `${out}/${v.name}.png` });
  console.log('saved', `${out}/${v.name}.png`);
}
await browser.close();
