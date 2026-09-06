// Reference views of the Brainstem Navigator nuclei inside a translucent brainstem, into
// qa/shots/brainstem-nav/.  Usage: npm run dev (port 5173), then: node scripts/shots-brainstem-nav.mjs [baseURL]
import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';

const base = process.argv[2] ?? 'http://localhost:5173';
const out = 'qa/shots/brainstem-nav';
mkdirSync(out, { recursive: true });
const LR = (b) => [`${b}-l`, `${b}-r`];
const VIEWS = [
  { name: 'locus-coeruleus-posterior', preset: '4', pad: 32,
    ids: [...LR('locus-coeruleus'), ...LR('nucleus-subcoeruleus'), ...LR('nucleus-laterodorsal-tegmental')] },
  { name: 'locus-coeruleus-lateral-l', preset: '1', pad: 32,
    ids: [...LR('locus-coeruleus'), ...LR('nucleus-subcoeruleus')] },
  { name: 'inferior-olive-anterior', preset: '3', pad: 26,
    ids: [...LR('nucleus-inferior-olivary')] },
  { name: 'inferior-olive-inferior', preset: '6', pad: 30,
    ids: [...LR('nucleus-inferior-olivary'), ...LR('nuclei-viscero-sensory-motor')] },
  { name: 'vestibular-posterior', preset: '4', pad: 30,
    ids: [...LR('nuclei-vestibular'), ...LR('nuclei-viscero-sensory-motor')] },
  { name: 'raphe-medial-l', preset: '7', pad: 36,
    ids: ['raphe-linear-caudal-rostral', 'raphe-paramedian', 'raphe-magnus', 'raphe-obscurus', 'raphe-pallidus'] },
  { name: 'raphe-posterior', preset: '4', pad: 36,
    ids: ['raphe-linear-caudal-rostral', 'raphe-paramedian', 'raphe-magnus', 'raphe-obscurus', 'raphe-pallidus'] },
  { name: 'parabrachial-posterior', preset: '4', pad: 30,
    ids: [...LR('nucleus-parabrachial-lateral'), ...LR('nucleus-parabrachial-medial'), ...LR('nucleus-superior-olivary')] },
  { name: 'reticular-columns-lateral-l', preset: '1', pad: 20,
    ids: [...LR('reticular-formation-mesencephalic'), ...LR('reticular-formation-isthmic'),
          ...LR('reticular-formation-pontine'), ...LR('reticular-formation-medullary-superior'),
          ...LR('reticular-formation-medullary-inferior')] },
  { name: 'midbrain-nuclei-posterior', preset: '4', pad: 30,
    ids: [...LR('nucleus-cuneiform'), ...LR('nucleus-microcellular-tegmental-parabigeminal'),
          ...LR('nucleus-parvicellular-reticular-alpha')] },
  { name: 'subdivisions-lateral-l', preset: '1', pad: 34,
    ids: [...LR('substantia-nigra-bsn-1'), ...LR('substantia-nigra-bsn-2'), ...LR('red-nucleus-bsn-1'),
          ...LR('red-nucleus-bsn-2'), ...LR('subthalamic-nucleus-bsn-1'), ...LR('subthalamic-nucleus-bsn-2')] },
  { name: 'all-lateral-l', preset: '1', pad: 20, all: true, ids: [] },
];

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1400, height: 900 }, deviceScaleFactor: 1 });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
await page.goto(`${base}/#/slice`);
await page.waitForFunction(() => window.atlas?.store.get().loaded.manifest === true, null, { timeout: 60_000 });
const bsn = await page.evaluate(() => window.atlas.manifest.meshes.filter((m) => m.source === 'brainstem_navigator').map((m) => m.id));
console.log('brainstem navigator meshes in manifest:', bsn.length);
await page.evaluate(() => {
  const a = window.atlas;
  a.registry.useLod = false;
  a.store.set({ quality: 'low', peel: {}, visibleSystems: new Set(['brainstem', 'basal-ganglia']),
                slices: { ...a.store.get().slices, visible: { axial: false, coronal: false, sagittal: false } } });
});
await page.waitForTimeout(1500);

for (const v of VIEWS) {
  const ids = v.all ? bsn : v.ids;
  await page.evaluate(async ([ids]) => {
    const a = window.atlas;
    await a.registry.ensure(['brainstem', ...ids]);
    for (const m of a.registry.loaded()) m.visible = false;
    const shell = a.registry.get('brainstem');
    if (shell) {
      shell.visible = true;
      const mat = shell.material;
      mat.transparent = true; mat.opacity = 0.18; mat.depthWrite = false; mat.needsUpdate = true;
    }
    for (const id of ids) { const m = a.registry.get(id); if (m) m.visible = true; }
    a.registry.invalidatePickCache();
    a.sm.requestRender();
  }, [ids]);
  await page.waitForTimeout(700);
  await page.evaluate(() => document.getElementById('gl').focus());
  await page.keyboard.press(v.preset);
  await page.waitForTimeout(500);
  await page.evaluate(([v, ids]) => {
    const a = window.atlas;
    const ms = a.manifest.meshes.filter((m) => ids.includes(m.id));
    const lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
    for (const m of ms) for (let k = 0; k < 3; k++) { lo[k] = Math.min(lo[k], m.bbox[0][k]); hi[k] = Math.max(hi[k], m.bbox[1][k]); }
    const b = a.registry.sceneBounds().clone();
    b.min.set(lo[0] - v.pad, lo[1] - v.pad, lo[2] - v.pad);
    b.max.set(hi[0] + v.pad, hi[1] + v.pad, hi[2] + v.pad);
    a.sm.fitToBox(b, false);
  }, [v, ids]);
  await page.waitForTimeout(900);
  await page.evaluate(() => { window.atlas.sm.resize(); window.atlas.sm.requestRender(); });
  await page.waitForTimeout(700);
  const gb = await page.locator('#gl').boundingBox();
  await page.screenshot({ path: `${out}/${v.name}.png`, clip: gb });
  console.log('saved', `${out}/${v.name}.png`, `(${ids.length} nuclei)`);
}
console.log('page errors:', JSON.stringify(errors.filter((e) => !/favicon/.test(e))));
await browser.close();
