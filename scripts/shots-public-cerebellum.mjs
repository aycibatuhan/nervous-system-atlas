// Reference views of the PUBLIC edition's cerebellar lobules, into qa/shots/public-cerebellum/.
//
// Like shots-public-brainstem.mjs it drives a *built* public edition rather than the dev server, so a
// non-commercial cerebellar-atlas mesh cannot appear in the frame even by accident: the manifest it loads
// has none. The script asserts that before it shoots anything.
//
//   node scripts/build-public.ts
//   npx vite preview --outDir dist --port 5183
//   node scripts/shots-public-cerebellum.mjs [baseURL]
//
// What is on screen is our own derivative: FastSurfer's CerebNet run on the MNI152NLin2009cAsym template
// (source `fastsurfer_cerebellum`, CC BY-SA 4.0). The lobule list is read off the manifest rather than
// hard-coded, so a change in the catalogue shows up here without editing this file.
import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';

const base = process.argv[2] ?? 'http://localhost:5183';
const out = 'qa/shots/public-cerebellum';
mkdirSync(out, { recursive: true });

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
  const cereb = m.meshes.filter((x) => x.source === 'fastsurfer_cerebellum');
  return {
    edition: m.edition,
    meshes: m.meshes.length,
    nc: m.meshes.filter((x) => x.nc).map((x) => x.id),
    restricted: m.meshes.filter((x) => x.source === 'diedrichsen_cerebellum').map((x) => x.id),
    lobules: cereb.filter((x) => x.subsystem === 'lobules').map((x) => x.id),
    vermis: cereb.filter((x) => x.subsystem === 'vermis').map((x) => x.id),
    licence: [...new Set(cereb.map((x) => x.license))],
    alignment: [...new Set(cereb.map((x) => x.alignment))],
    structures: [...new Set(cereb.map((x) => x.structureId))].sort(),
  };
});
console.log(JSON.stringify(facts, null, 1));
check(facts.edition === 'public', `the loaded manifest is the public edition (${facts.edition})`);
check(facts.restricted.length === 0, `no non-commercial cerebellar-atlas mesh is loadable at all (${facts.restricted.length})`);
check(facts.nc.length === 0, `nothing in the manifest is flagged nc (${facts.nc.length})`);
check(facts.lobules.length === 20, `20 lobule meshes, 10 per side (${facts.lobules.length})`);
check(facts.vermis.length === 5, `5 vermian meshes, CerebNet's coarser vermis (${facts.vermis.length})`);
check(facts.licence.join() === 'CC-BY-SA-4.0', `they ship as our CC BY-SA 4.0 derivative (${facts.licence.join()})`);
check(facts.alignment.join() === 'native-mni', `segmented on the template itself, so native (${facts.alignment.join()})`);
if (problems.length) { for (const p of problems) console.error(p); await browser.close(); process.exit(1); }

const LOB = facts.lobules;
const VERM = facts.vermis;
const LEFT = LOB.filter((id) => id.endsWith('-l'));
const VIEWS = [
  { name: '01-lobules-inferior', preset: '6', pad: 6, ids: [...LOB, ...VERM] },
  { name: '02-lobules-posterior', preset: '4', pad: 6, ids: [...LOB, ...VERM] },
  // medial views: the left hemisphere without the vermis in front of it, then the vermis on its own. `fit`
  // keeps the frame on the meshes that matter -- a box spanning both would be mostly depth along the view
  // axis, and the camera would end up too far back to read either.
  { name: '03-lobules-medial-l', preset: '7', pad: 3, ids: LEFT, fit: LEFT, flatAxis: 0 },
  { name: '04-vermis-medial-l', preset: '7', pad: 2, ids: VERM, fit: VERM, flatAxis: 0 },
];
for (const v of VIEWS) check(v.ids.length > 0, `${v.name}: has meshes to show (${v.ids.length})`);
if (problems.length) { for (const p of problems) console.error(p); await browser.close(); process.exit(1); }

await page.evaluate(() => {
  const a = window.atlas;
  a.registry.useLod = false;
  a.store.set({ quality: 'low', peel: {}, visibleSystems: new Set(['cerebellum']),
                slices: { ...a.store.get().slices, visible: { axial: false, coronal: false, sagittal: false } } });
});
await page.waitForTimeout(1500);

for (const v of VIEWS) {
  await page.evaluate(async ([ids]) => {
    const a = window.atlas;
    await a.registry.ensure(ids);
    for (const m of a.registry.loaded()) m.visible = false;
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
    // fitToBox sizes the camera off the box *diagonal*, so an axis that only adds depth along the line of
    // sight (x for a medial view) pushes the camera back and leaves the frame mostly empty: collapse it.
    if (v.flatAxis !== undefined) {
      const k = v.flatAxis, mid = (lo[k] + hi[k]) / 2;
      lo[k] = mid - 1; hi[k] = mid + 1;
    }
    const b = a.registry.sceneBounds().clone();
    b.min.set(lo[0] - v.pad, lo[1] - v.pad, lo[2] - v.pad);
    b.max.set(hi[0] + v.pad, hi[1] + v.pad, hi[2] + v.pad);
    a.sm.fitToBox(b, false);
  }, [v, v.fit ?? v.ids]);
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
console.log('public cerebellum shots: clean');
