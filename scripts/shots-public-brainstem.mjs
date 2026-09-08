// Reference views of the PUBLIC edition's brainstem nuclei inside a translucent brainstem, into
// qa/shots/public-brainstem/.
//
// It drives a built public edition, not the dev server, so a Brainstem Navigator mesh cannot appear in
// the frame even by accident: the manifest it loads has none. The script asserts that before shooting.
//
//   node scripts/build-public.ts
//   npx vite preview --outDir dist --port 5183
//   node scripts/shots-public-brainstem.mjs [baseURL]
import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';

const base = process.argv[2] ?? 'http://localhost:5183';
const out = 'qa/shots/public-brainstem';
mkdirSync(out, { recursive: true });

// Two kinds of brainstem nucleus can ship here. The locus coeruleus comes from the openly licensed Dahl meta
// mask, i.e. it is a real delineation. Everything else is a landmark-anchored location marker built by
// atlas-derived: an ellipsoid of the nucleus's published volume put where a textbook puts it relative to open
// geometry (README, "Public and private editions"; pipeline/config/brainstem_landmarks.yaml). The marker list
// is read off the manifest rather than hard-coded, so a new marker shows up here without editing this file.
const LC = ['locus-coeruleus-meta-l', 'locus-coeruleus-meta-r'];

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
    anchored: m.meshes.filter((x) => (x.derived ?? '').startsWith('landmark-anchored'))
      .map((x) => ({ id: x.id, structureId: x.structureId, centroid: x.centroid })),
  };
});
console.log(JSON.stringify(facts, null, 1));
check(facts.edition === 'public', `the loaded manifest is the public edition (${facts.edition})`);
check(facts.bsn.length === 0, `no Brainstem Navigator mesh is loadable at all (${facts.bsn.length})`);
check(facts.lc.length === LC.length, `the locus coeruleus meta mask is there (${facts.lc.join(', ')})`);
check(facts.anchored.length > 0, `landmark-anchored markers are there (${facts.anchored.length})`);
if (problems.length) { for (const p of problems) console.error(p); await browser.close(); process.exit(1); }

const anchored = facts.anchored.map((a) => a.id);
const pick = (...sids) => anchored.filter((id) => sids.some((s) => id.startsWith(`${s}-anchor`)));
const medulla = pick('raphe-magnus', 'raphe-obscurus', 'raphe-pallidus', 'nuclei-viscero-sensory-motor',
                     'reticular-formation-medullary-superior', 'reticular-formation-medullary-inferior',
                     'nucleus-parvicellular-reticular-alpha');
const upper = pick('nucleus-parabrachial-lateral', 'nucleus-parabrachial-medial', 'superior-olivary-complex',
                   'reticular-formation-mesencephalic', 'reticular-formation-isthmic', 'nucleus-subcoeruleus',
                   'nucleus-cuneiform', 'nucleus-microcellular-tegmental-parabigeminal');
// the reticular columns end to end, and the midline serotonergic column end to end: the two groups whose
// markers are meant to be read as a series rather than one at a time
const reticular = pick('reticular-formation-medullary-inferior', 'reticular-formation-medullary-superior',
                       'reticular-formation-isthmic', 'reticular-formation-mesencephalic');
const raphe = pick('raphe-pallidus', 'raphe-obscurus', 'raphe-magnus', 'raphe-paramedian',
                   'raphe-linear-caudal-rostral');
// the subcoeruleus is placed against the locus coeruleus meta mask, so it is only readable next to it
const coeruleus = [...LC, ...pick('nucleus-subcoeruleus')];
const ALL = [...LC, ...anchored];
const VIEWS = [
  { name: '01-locus-coeruleus-posterior', preset: '4', pad: 30, ids: LC },
  { name: '02-locus-coeruleus-lateral-l', preset: '1', pad: 30, ids: LC },
  { name: '03-locus-coeruleus-posterior-close', preset: '4', pad: 10, ids: LC },
  { name: '04-locus-coeruleus-lateral-close', preset: '1', pad: 10, ids: LC },
  { name: '05-all-public-nuclei-posterior', preset: '4', pad: 12, ids: ALL },
  { name: '06-all-public-nuclei-lateral-l', preset: '1', pad: 12, ids: ALL },
  { name: '07-medullary-markers-posterior', preset: '4', pad: 8, ids: medulla },
  { name: '08-medullary-markers-lateral-l', preset: '1', pad: 8, ids: medulla },
  { name: '09-pontomesencephalic-markers-posterior', preset: '4', pad: 8, ids: upper },
  { name: '10-pontomesencephalic-markers-lateral-l', preset: '1', pad: 8, ids: upper },
  { name: '11-reticular-column-lateral-l', preset: '1', pad: 8, ids: reticular },
  { name: '12-reticular-column-posterior', preset: '4', pad: 8, ids: reticular },
  { name: '13-raphe-column-lateral-l', preset: '1', pad: 8, ids: raphe },
  { name: '14-raphe-column-posterior', preset: '4', pad: 8, ids: raphe },
  { name: '15-subcoeruleus-with-lc-posterior', preset: '4', pad: 8, ids: coeruleus },
  { name: '16-subcoeruleus-with-lc-lateral-l', preset: '1', pad: 8, ids: coeruleus },
];
// every marker the manifest carries has to appear in at least one view, so a new nucleus in
// brainstem_landmarks.yaml cannot be added without a picture of it
const shown = new Set(VIEWS.flatMap((v) => v.ids));
const unshown = anchored.filter((id) => !shown.has(id));
check(unshown.length === 0, `every landmark-anchored marker appears in some view (missing: ${unshown.join(', ') || 'none'})`);
for (const v of VIEWS) check(v.ids.length > 0, `${v.name}: has meshes to show (${v.ids.length})`);
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
