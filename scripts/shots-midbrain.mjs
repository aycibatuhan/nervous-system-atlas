// Lateral / oblique views of the Z-Anatomy cranial nerves III-XII against the MNI aseg brainstem, for the
// midbrain half of the Z-Anatomy anteroposterior post-correction (see pipeline/atlas_pipeline/midline.py).
// The AP ramp now runs 0 at the mesencephalic-diencephalic junction -> -5.2 mm at the intercollicular knot
// -> 0 at the pontomesencephalic junction -> +23.3 mm at the cervicomedullary junction, so the midbrain-level
// nerves (III, IV) move posterior onto the aseg midbrain while IX-XII keep the shift they already had.
//
// Usage: node scripts/shots-midbrain.mjs [tag] [baseURL]     (dev server: npm run dev)
//   tag defaults to `midbrain`; pass `midbrain/before` / `midbrain/after` to capture a pair.
import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';

const tag = process.argv[2] ?? 'midbrain';
const base = process.argv[3] ?? 'http://localhost:5173';
const out = `qa/shots/${tag}`;
mkdirSync(out, { recursive: true });

const CN = [
  ['03-oculomotor-course'], ['04-trochlear'], ['05-trigeminal-course'], ['06-abducens'],
  ['07-facial-course'], ['08-vestibulocochlear-course'], ['09-glossopharyngeal'], ['10-vagus'],
  ['11-accessory'], ['12-hypoglossal'],
].flatMap(([n]) => [`cn-${n}-l`, `cn-${n}-r`]);
const CN_UPPER = ['cn-03-oculomotor-course-l', 'cn-03-oculomotor-course-r', 'cn-04-trochlear-l',
  'cn-04-trochlear-r', 'cn-06-abducens-l', 'cn-06-abducens-r'];
const SYSTEMS = ['brainstem', 'cranial-nerves'];

// Camera framing is explicit: the standard presets frame the whole brain and everything here sits in a
// 60 x 90 x 90 mm box around the brainstem.  `dir` is the view direction, the box the MNI region to fit.
const VIEWS = [
  { name: 'lateral-cn-03-12', dir: [1, 0, 0], systems: SYSTEMS,
    ids: ['brainstem', ...CN], box: [[-45, -90, -80], [45, 20, 15]] },
  { name: 'lateral-cn-03-12-left', dir: [-1, 0, 0], systems: SYSTEMS,
    ids: ['brainstem', ...CN], box: [[-45, -90, -80], [45, 20, 15]] },
  { name: 'lateral-midbrain-cn-03-04-06', dir: [1, 0, 0], systems: SYSTEMS,
    ids: ['brainstem', 'cerebral-peduncle-crus-l', 'cerebral-peduncle-crus-r', ...CN_UPPER],
    box: [[-35, -60, -45], [35, 5, 10]] },
  { name: 'anterior-midbrain-cn-03', dir: [0, 1, 0], systems: SYSTEMS,
    ids: ['brainstem', 'cerebral-peduncle-crus-l', 'cerebral-peduncle-crus-r', ...CN_UPPER],
    box: [[-40, -60, -45], [40, 5, 10]] },
  { name: 'oblique-cn-03-12', dir: [0.9, 0.35, 0.2], systems: SYSTEMS,
    ids: ['brainstem', ...CN], box: [[-45, -90, -80], [45, 20, 15]] },
];

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1400, height: 900 }, deviceScaleFactor: 1 });
for (const v of VIEWS) {
  await page.goto(`${base}/#/slice`);
  await page.waitForFunction(() => window.atlas?.store.get().loaded.manifest === true, null, { timeout: 60_000 });
  await page.evaluate(async (v) => {
    const a = window.atlas;
    a.store.set({ quality: 'low' });
    const ids = (v.ids ?? v.systems.flatMap((s) => (a.registry.bySystem.get(s) ?? []).map((m) => m.id)))
      .filter((id) => a.registry.byId?.has?.(id) ?? true);
    a.store.set({
      visibleSystems: new Set(v.systems),
      shownStructures: new Set(ids),
      hiddenStructures: new Set(),
      slices: { ...a.store.get().slices, visible: { axial: false, coronal: false, sagittal: false } },
    });
  }, v);
  await page.evaluate(() => document.getElementById('gl').focus());
  await page.waitForFunction((v) => {
    const a = window.atlas;
    const want = v.ids ?? [...a.store.get().visibleSystems]
      .flatMap((s) => (a.registry.bySystem.get(s) ?? []).map((m) => m.id));
    return want.every((id) => a.registry.has(id) || !a.manifest?.meshes?.some?.((m) => m.id === id));
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
