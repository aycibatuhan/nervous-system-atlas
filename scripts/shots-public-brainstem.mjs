// Reference views of the PUBLIC edition's brainstem nuclei inside a translucent brainstem, into
// qa/shots/public-brainstem/.
//
// It drives a built public edition, not the dev server, so a Brainstem Navigator mesh cannot appear in
// the frame even by accident: the manifest it loads has none. The script asserts that before shooting.
//
//   node scripts/build-public.ts
//   npx vite preview --outDir dist-public --port 5183
//   node scripts/shots-public-brainstem.mjs [baseURL]
import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';

const base = process.argv[2] ?? 'http://localhost:5183';
const out = 'qa/shots/public-brainstem';
mkdirSync(out, { recursive: true });

// The only brainstem nuclei the public edition can ship are the two halves of the locus coeruleus meta
// mask; every other Brainstem Navigator nucleus is content-only here (README, "Public and private editions").
const LC = ['locus-coeruleus-meta-l', 'locus-coeruleus-meta-r'];
const VIEWS = [
  { name: '01-locus-coeruleus-posterior', preset: '4', pad: 30, ids: LC },
  { name: '02-locus-coeruleus-lateral-l', preset: '1', pad: 30, ids: LC },
  { name: '03-locus-coeruleus-posterior-close', preset: '4', pad: 10, ids: LC },
  { name: '04-locus-coeruleus-lateral-close', preset: '1', pad: 10, ids: LC },
];

const problems = [];
const errors = [];
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1400, height: 900 }, deviceScaleFactor: 1 });
page.on('pageerror', (e) => errors.push(String(e)));
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
const check = (ok, msg) => { if (!ok) problems.push(msg); console.log(`${ok ? 'ok  ' : 'FAIL'} ${msg}`); };

await page.goto(`${base}/#/slice`);
await page.waitForFunction(() => window.atlas?.store.get().loaded.manifest === true, null, { timeout: 60_000 });

const facts = await page.evaluate(() => {
  const m = window.atlas.manifest;
  return {
    edition: m.edition,
    meshes: m.meshes.length,
    bsn: m.meshes.filter((x) => x.source === 'brainstem_navigator').map((x) => x.id),
    lc: m.meshes.filter((x) => x.structureId === 'locus-coeruleus').map((x) => `${x.id} (${x.source}, ${x.license})`),
  };
});
console.log(JSON.stringify(facts, null, 1));
check(facts.edition === 'public', `the loaded manifest is the public edition (${facts.edition})`);
check(facts.bsn.length === 0, `no Brainstem Navigator mesh is loadable at all (${facts.bsn.length})`);
check(facts.lc.length === LC.length, `the locus coeruleus meta mask is there (${facts.lc.join(', ')})`);
if (problems.length) { for (const p of problems) console.error(p); await browser.close(); process.exit(1); }

await page.evaluate(() => {
  const a = window.atlas;
  a.registry.useLod = false;
  a.store.set({ quality: 'low', peel: {}, visibleSystems: new Set(['brainstem']),
                slices: { ...a.store.get().slices, visible: { axial: false, coronal: false, sagittal: false } } });
});
await page.waitForTimeout(1500);

for (const v of VIEWS) {
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
  }, [v.ids]);
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
  }, [v, v.ids]);
  await page.waitForTimeout(900);
  await page.evaluate(() => { window.atlas.sm.resize(); window.atlas.sm.requestRender(); });
  await page.waitForTimeout(700);
  const gb = await page.locator('#gl').boundingBox();
  await page.screenshot({ path: `${out}/${v.name}.png`, clip: gb });
  console.log('saved', `${out}/${v.name}.png`);
}

await browser.close();
for (const e of errors) console.error(e);
console.log(`\n${problems.length} check(s) failed, ${errors.length} console/page error(s)`);
if (problems.length || errors.length) process.exit(1);
console.log('public brainstem shots: clean');
