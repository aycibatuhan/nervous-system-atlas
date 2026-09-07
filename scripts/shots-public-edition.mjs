// Loads a built public edition and checks it degrades gracefully where the private atlases are missing.
// Serve it first:  npx vite preview --outDir dist-public --port 5183
// Usage:           node scripts/shots-public-edition.mjs [baseURL]
//
// Checks: no console/page errors; the manifest really is the public one; two entries that genuinely have no
// mesh in this edition still open their content and show the "no mesh in this edition" notice; no Harvard-Oxford
// gyrus mesh id survives in the manifest; the cord MRI toggle is hidden because grids.cord is gone.
//
// The "no mesh" probes have to be picked with care, because most of the entries that lost a mesh have since been
// given an openly licensed stand-in: gyrus-precentral has the CerebrA/DKT parcels, the locus coeruleus has the
// Dahl meta mask, the parabrachial, raphe and viscero-sensory-motor entries have landmark-anchored markers, and
// the cord blocks have their vertebral-landmark variant. The two used below have none.
import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';

const base = process.argv[2] ?? 'http://localhost:5183';
const out = 'qa/shots/public-edition';
mkdirSync(out, { recursive: true });

const problems = [];
const errors = [];
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1400, height: 900 }, deviceScaleFactor: 1 });
page.on('console', (m) => { if (m.type() === 'error') errors.push(`console: ${m.text()}`); });
page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`));
page.on('requestfailed', (r) => errors.push(`requestfailed: ${r.url()} ${r.failure()?.errorText ?? ''}`));

const ready = async () => {
  await page.waitForFunction(() => window.atlas?.store.get().loaded.manifest === true, null, { timeout: 60_000 });
  await page.waitForFunction(() => window.atlas?.store.get().loaded.content === true, null, { timeout: 60_000 });
};
const shot = async (name) => { await page.waitForTimeout(600); await page.screenshot({ path: `${out}/${name}.png` }); console.log('saved', `${out}/${name}.png`); };
const check = (ok, msg) => { if (!ok) problems.push(msg); console.log(`${ok ? 'ok  ' : 'FAIL'} ${msg}`); };

// ---- 1. the app starts on the public manifest
await page.goto(`${base}/#/slice`);
await ready();
const facts = await page.evaluate(() => {
  const m = window.atlas.manifest;
  return {
    edition: m.edition, meshes: m.meshes.length, nc: m.meshes.filter((x) => x.nc).length,
    licences: Object.keys(m.licenses), sources: Object.keys(m.sources), volumes: Object.keys(m.volumes),
    cordGrid: !!m.grids?.cord,
    hasHO: m.meshes.some((x) => x.source === 'harvard_oxford'),
    hasBSN: m.meshes.some((x) => x.source === 'brainstem_navigator'),
    authored: Object.keys(window.atlas.content?.structures ?? {}).length,
  };
});
console.log(JSON.stringify(facts, null, 1));
check(facts.edition === 'public', `manifest declares the public edition (${facts.edition})`);
check(facts.nc === 0, `no mesh is flagged nc (${facts.nc})`);
check(!facts.hasHO && !facts.hasBSN, 'no Harvard-Oxford or Brainstem Navigator meshes');
check(!facts.cordGrid, 'grids.cord is absent');
check(!facts.volumes.some((v) => v.startsWith('cord_') || v === 'labels_spine'), 'no cord volumes');
check(facts.authored > 300, `content is still complete (${facts.authored} authored structures)`);
await shot('01-home');

// ---- 2. the cord MRI toggle is hidden when there is no cord grid
const cordVisible = await page.locator('label.cord-mri').isVisible().catch(() => false);
check(!cordVisible, 'the cord MRI toggle is hidden');

// ---- 3. two entries with no mesh in this edition: the content opens, the notice shows.
// Both are Brainstem Navigator nuclei with no open delineation and no landmark-anchored stand-in.
for (const [id, label] of [['reticular-formation-medullary-inferior', '02-reticular-formation-medullary-inferior'],
                           ['nucleus-laterodorsal-tegmental', '03-nucleus-laterodorsal-tegmental']]) {
  await page.goto(`${base}/#/structure/${id}`);
  await ready();
  await page.waitForTimeout(800);
  const seen = await page.evaluate(() => ({
    heading: document.querySelector('.content-head h2')?.textContent ?? '',
    notice: !!document.querySelector('[data-testid="no-mesh"]'),
    tabs: document.querySelectorAll('.tabs button').length,
    prose: (document.querySelector('.section')?.textContent ?? '').length,
    hash: location.hash,
  }));
  check(seen.notice, `${id}: shows the "no mesh in this edition" notice`);
  check(seen.tabs > 5, `${id}: the content tabs are there (${seen.tabs})`);
  check(seen.prose > 200, `${id}: the prose is rendered (${seen.prose} chars)`);
  check(seen.hash.includes(id), `${id}: the hash survives (${seen.hash})`);
  console.log(`      heading: ${seen.heading}`);
  await shot(label);
  // the imaging tab is where MniRefs are rendered; it must not print "NaN"
  await page.evaluate(() => window.atlas.store.set({ contentTab: 'imaging' }));
  await page.waitForTimeout(400);
  const imaging = await page.evaluate(() => document.querySelector('.section')?.textContent ?? '');
  check(!imaging.includes('NaN'), `${id}: the imaging tab has no NaN coordinates`);
  if (label.startsWith('02')) await shot('04-no-mesh-imaging');
  await page.evaluate(() => window.atlas.store.set({ contentTab: 'overview' }));
}

// ---- 4. no excluded gyrus mesh survives, a surviving structure still works.
// Tested on mesh ids, not on tree labels: the CerebrA/DKT parcels that replace the excluded gyri carry the same
// anatomical names ("Precentral gyrus"), so a label test would fail on the replacement rather than the original.
await page.goto(`${base}/#/structure/thalamus-l`);
await ready();
await page.waitForTimeout(1200);
const tree = await page.evaluate(() => ({
  rows: document.querySelectorAll('.tree .row, .tree .leaf').length,
  hoGyri: window.atlas.manifest.meshes.filter((m) => /^gyrus-.*-[lr]$/.test(m.id)).map((m) => m.id),
  selected: window.atlas.store.get().selectedId,
}));
check(tree.hoGyri.length === 0, `no excluded gyrus-*-l/-r mesh id is in the manifest (${tree.hoGyri.slice(0, 3).join(', ')})`);
check(tree.selected === 'thalamus-l', `a shipped structure still selects (${tree.selected})`);
await shot('05-thalamus-selected');

// ---- 5. a syndrome walk-through, the heaviest cross-referencing path
await page.goto(`${base}/#/syndrome/syn-wallenberg-lateral-medullary?step=1&side=l`);
await ready();
await page.waitForTimeout(2000);
await shot('06-syndrome-wallenberg');

await browser.close();
for (const e of errors) console.error(e);
console.log(`\n${problems.length} check(s) failed, ${errors.length} console/page error(s)`);
if (problems.length || errors.length) process.exit(1);
console.log('public edition: runs clean');
