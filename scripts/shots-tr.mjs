// Screenshots of the Turkish interface (locale `tr`) from the running dev server (npm run dev) into qa/shots/<tag>/.
// Usage: node scripts/shots-tr.mjs [tag] [baseURL]      (full-page captures: toolbar, panels, tree, search)
import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';

const tag = process.argv[2] ?? 'tr-ui';
const base = process.argv[3] ?? 'http://localhost:5173';
const out = `qa/shots/${tag}`; mkdirSync(out, { recursive: true });
const VIEWS = [
  { name: 'structure-brainstem', hash: '#/structure/brainstem?lang=tr' },
  { name: 'structure-artery-mca', hash: '#/structure/artery-mca?lang=tr' },
  { name: 'pathway-lateral-corticospinal', hash: '#/pathway/pathway-lateral-corticospinal?lang=tr' },
  { name: 'syndrome-wallenberg', hash: '#/syndrome/syn-wallenberg-lateral-medullary?step=1&side=l&lang=tr' },
  { name: 'about', hash: '#/about?lang=tr' },
  { name: 'search-omurilik', hash: '#/structure/spinal-cord?lang=tr', search: 'omurilik' },
  { name: 'structure-brainstem-en', hash: '#/structure/brainstem?lang=en' },
];
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1400, height: 900 }, deviceScaleFactor: 1 });
for (const v of VIEWS) {
  await page.goto(`${base}/${v.hash}`);
  await page.waitForFunction(() => window.atlas?.store.get().loaded.manifest === true && window.atlas?.store.get().loaded.content === true, null, { timeout: 90_000 });
  await page.waitForTimeout(4000);          // the panels are what matters here; the 3D view may still be refining
  if (v.search) {
    const input = page.locator('input.search');
    await input.fill(v.search);
    await page.waitForTimeout(400);
  }
  await page.evaluate(() => { window.atlas.sm.requestRender(); });
  await page.waitForTimeout(300);
  await page.screenshot({ path: `${out}/${v.name}.png` });
  console.log('saved', `${out}/${v.name}.png`, '| html lang =', await page.evaluate(() => document.documentElement.lang));
}
await browser.close();
