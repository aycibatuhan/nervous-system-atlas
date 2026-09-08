// The README's screenshot gallery, captured from a built PUBLIC edition at a fixed viewport.
//
//   npm run build                                   # dist/ = the public edition, gate included
//   npx vite preview --outDir dist --port 5183
//   node scripts/shots-docs.mjs [baseURL]           # -> docs/screenshots/*.png
//
// Shooting the built edition rather than the dev server matters: dist/data has been filtered, so the label
// volumes carry no voxels of the atlases the public edition drops and nothing restricted can appear in a
// picture that ends up on a public page. The viewport is fixed at 1600x1000 so every image in the gallery
// lines up and the toolbar keeps its counts (below 1500px it drops them).
//
// Convert to WebP afterwards (cwebp -q 82) — the README embeds the .webp files.
import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';

const base = process.argv[2] ?? 'http://localhost:5183';
const out = 'docs/screenshots';
mkdirSync(out, { recursive: true });

const VIEWS = [
  { name: 'overview', hash: '#/', preset: 'lateral-l', systems: null, wait: 6000,
    note: 'first paint: the cortical surface, the vessels and the tree' },
  { name: 'structure', hash: '#/structure/thalamus', preset: 'anterior', systems: ['diencephalon', 'basal-ganglia', 'ventricles-csf', 'brainstem'], wait: 6000,
    note: 'one structure open, with its panel' },
  { name: 'syndrome-wallenberg', hash: '#/syndrome/syn-wallenberg-lateral-medullary?step=2&side=l', preset: null, systems: null, wait: 7000,
    note: 'syndrome mode: the lesion, the involved structures, the deficit table' },
  { name: 'slices-mri', hash: '#/structure/putamen', preset: 'superior', systems: ['basal-ganglia', 'diencephalon', 'ventricles-csf'], slices: { axial: 2 }, wait: 7000,
    note: 'the axial MRI slice under the deep grey nuclei, label outlines on' },
  { name: 'pathway', hash: '#/pathway/pathway-lateral-corticospinal', preset: 'lateral-l', systems: null, wait: 7000,
    note: 'a pathway and its stations' },
  { name: 'cranial-nerves', hash: '#/structure/cn-05-trigeminal', preset: 'inferior', systems: ['cranial-nerves', 'brainstem', 'arteries'], wait: 7000,
    note: 'the cranial nerve tree and one nerve' },
  { name: 'quiz', hash: '#/quiz', preset: null, systems: null, wait: 5000, note: 'a quiz vignette' },
  { name: 'turkish', hash: '#/structure/red-nucleus?lang=tr', preset: 'anterior', systems: ['brainstem', 'diencephalon', 'basal-ganglia'], wait: 6000,
    note: 'the Turkish interface, Latin structure names, the translation notice' },
  { name: 'turkish-syndrome', hash: '#/syndrome/syn-wallenberg-lateral-medullary?step=2&side=l&lang=tr', preset: null, systems: null, wait: 7000,
    note: 'the same syndrome page in Turkish' },
];

const KEY = { 'lateral-l': '1', 'lateral-r': '2', anterior: '3', posterior: '4', superior: '5', inferior: '6', 'medial-l': '7', 'medial-r': '8' };

const browser = await chromium.launch();
const errors = [];

for (const v of VIEWS) {
  // a fresh page per view: a hash change alone does not reload, so the camera, the visible systems and the
  // slice state of one shot would otherwise leak into the next
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1 });
  page.on('pageerror', (e) => errors.push(`${v.name}: ${e}`));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(`${v.name}: ${m.text()}`); });
  await page.goto(`${base}/${v.hash}`);
  await page.waitForFunction(() => window.atlas?.store.get().loaded.manifest === true, null, { timeout: 90_000 });
  await page.waitForFunction(() => window.atlas?.store.get().loaded.content === true, null, { timeout: 90_000 });
  await page.evaluate(([v]) => {
    const a = window.atlas;
    a.store.set({ quality: 'high' });
    if (v.systems) a.store.set({ visibleSystems: new Set(v.systems) });
    if (v.slices) a.store.set({ slices: { ...a.store.get().slices, axial: v.slices.axial, visible: { axial: true, coronal: false, sagittal: false }, pinned: true },
      overlay: { ...a.store.get().overlay, showAllLabels: true, opacity: 0.65 } });
    else a.store.set({ slices: { ...a.store.get().slices, visible: { axial: false, coronal: false, sagittal: false } } });
  }, [v]);
  if (v.preset) { await page.evaluate(() => document.getElementById('gl').focus()); await page.keyboard.press(KEY[v.preset]); }
  // every mesh of every visible system loaded, and no low-detail stand-in left in the scene
  await page.waitForFunction(() => {
    const a = window.atlas, st = a.store.get();
    const want = [...st.visibleSystems].flatMap((s) => (a.registry.bySystem.get(s) ?? []).map((m) => m.id));
    return want.every((id) => a.registry.has(id));
  }, null, { timeout: 120_000 });
  await page.waitForFunction(() => [...window.atlas.registry.loaded()].every((m) => !m.userData.lod), null, { timeout: 120_000 });
  await page.waitForTimeout(v.wait);
  await page.evaluate(() => window.atlas.sm.requestRender());
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${out}/${v.name}.png` });
  console.log(`saved ${out}/${v.name}.png — ${v.note}`);
  await page.close();
}
if (errors.length) { console.error(`\n${errors.length} page error(s):`); for (const e of errors.slice(0, 10)) console.error(`  ${e}`); }
await browser.close();
