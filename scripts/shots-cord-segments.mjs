// Cord segment blocks re-cut at the measured PAM50 spinal levels (atlas-pam50 -> atlas-derived).
// Usage: node scripts/shots-cord-segments.mjs [port]        (dev server: npm run dev -- --port 5181)
//
// Two things are checked:
//   1. the four blocks plus the filum terminale tile the whole cord with no gap and no overlap, lateral view,
//      with the PAM50 cord MRI on the sagittal slice behind them;
//   2. the C8/T1, L5/S1 and S5/filum seams land on the PAM50 level boundaries -- the boundary point is read
//      from cord_levels.json, projected into the render with the page's own camera and marked with a cross,
//      so the seam and the marker have to coincide.
import { readFileSync, mkdirSync } from 'node:fs';
import { chromium } from '@playwright/test';

const base = `http://localhost:${process.argv[2] ?? 5181}`;
const out = 'qa/shots/cord-segments';
mkdirSync(out, { recursive: true });

const levels = JSON.parse(readFileSync('public/data/volumes/cord_levels.json', 'utf8'));
const by = Object.fromEntries(levels.spinalLevels.map((l) => [l.name, l]));
const arc = levels.centreline.arc, pts = levels.centreline.points;
const at = (a) => {                                   // point on the centreline at arc length a
  let i = 1; while (i < arc.length - 1 && arc[i] < a) i++;
  const t = (a - arc[i - 1]) / (arc[i] - arc[i - 1]);
  return pts[i - 1].map((c, k) => c + t * (pts[i][k] - c));
};
const seam = (above, below) => at((by[above].arc_mm[1] + by[below].arc_mm[0]) / 2);
const BOUNDARIES = [
  { name: 'boundary-c8-t1', label: 'PAM50 C8/T1', p: seam('C8', 'T1'), marks: [['C8 bottom', by.C8.bottom], ['T1 top', by.T1.top]] },
  { name: 'boundary-l5-s1', label: 'PAM50 L5/S1', p: seam('L5', 'S1'), marks: [['L5 bottom', by.L5.bottom], ['S1 top', by.S1.top]] },
  { name: 'boundary-s5-filum', label: 'PAM50 S5 caudal end', p: by.S5.bottom, marks: [['S5 top', by.S5.top]] },
];
const BLOCKS = ['spinal-segment-cervical', 'spinal-segment-thoracic', 'spinal-segment-lumbar',
                'spinal-segment-sacral', 'filum-terminale'];

const VIEWS = [
  { name: 'lateral-blocks-mri', ids: BLOCKS, dir: [1, 0, 0], at: { x: 0, y: -140, z: -320 }, half: 290, mri: true, sag: true },
  { name: 'lateral-blocks', ids: BLOCKS, dir: [1, 0, 0], at: { x: 0, y: -140, z: -320 }, half: 290, mri: false, sag: false },
  { name: 'lateral-blocks-enlargements', ids: [...BLOCKS, 'spinal-enlargement-cervical', 'spinal-enlargement-lumbosacral'],
    dir: [1, 0, 0], at: { x: 0, y: -140, z: -320 }, half: 290, mri: false, sag: false },
  ...BOUNDARIES.map((b) => ({ name: b.name, ids: BLOCKS, dir: [1, 0, 0],
    at: { x: b.p[0], y: b.p[1], z: b.p[2] }, half: 40, mri: true, sag: true,
    markers: [[b.label, b.p], ...b.marks] })),
];

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1400, height: 900 }, deviceScaleFactor: 1 });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
await page.goto(`${base}/#/slice`);
await page.waitForFunction(() => window.atlas?.store.get().loaded.manifest === true, null, { timeout: 60_000 });
await page.waitForFunction(() => window.atlas.store.get().loaded.volume === true, null, { timeout: 120_000 });
await page.evaluate(() => window.atlas.store.set({ quality: 'low', cordMri: true, contrast: 't2w' }));
await page.waitForFunction(() => window.atlas.store.get().loaded.cord === true, null, { timeout: 120_000 });
console.log('cord volume loaded');

for (const v of VIEWS) {
  await page.evaluate((v) => {
    const a = window.atlas, s = a.store.get();
    a.store.set({
      visibleSystems: new Set(['spinal-cord']), shownStructures: new Set(v.ids), hiddenStructures: new Set(),
      cordMri: v.mri, contrast: 't2w', peel: {},
      slices: { ...s.slices, sagittal: 0, axial: Math.round(v.at.z), coronal: Math.round(v.at.y),
                visible: { axial: false, coronal: false, sagittal: v.sag } },
    });
  }, v);
  await page.waitForFunction((v) => v.ids.every((id) => window.atlas.registry.has(id)), v, { timeout: 120_000 });
  await page.waitForFunction(() => [...window.atlas.registry.loaded()].every((m) => !m.userData.lod), null, { timeout: 120_000 });
  await page.evaluate((v) => {
    const a = window.atlas, t = a.sm.controls.target;
    t.set(v.at.x, v.at.y, v.at.z);
    a.sm.camera.up.set(0, 0, 1);
    a.sm.camera.fov = 25;
    const d = v.half / Math.tan((a.sm.camera.fov * Math.PI) / 360) * 1.05;
    const n = Math.hypot(...v.dir);
    a.sm.moveCamera({ x: t.x + (v.dir[0] / n) * d, y: t.y + (v.dir[1] / n) * d, z: t.z + (v.dir[2] / n) * d },
                    { x: t.x, y: t.y, z: t.z }, 0);
    a.sm.camera.near = 1; a.sm.camera.far = 4000; a.sm.camera.updateProjectionMatrix();
    a.sm.controls.update(); a.sm.requestRender();
  }, v);
  await page.waitForTimeout(900);
  await page.evaluate(() => { window.atlas.sm.resize(); window.atlas.sm.requestRender(); });
  await page.waitForTimeout(900);

  // markers: project the PAM50 world points with the page's own camera and pin a cross over the canvas
  if (v.markers) {
    await page.evaluate((markers) => {
      document.querySelectorAll('.qa-mark').forEach((n) => n.remove());
      const cam = window.atlas.sm.camera, gl = document.getElementById('gl');
      const r = gl.getBoundingClientRect();
      cam.updateMatrixWorld(); cam.updateProjectionMatrix();
      const V3 = cam.position.constructor;                       // THREE.Vector3, via the live camera
      let n = 0;
      for (const [label, p] of markers) {
        const v = new V3(p[0], p[1], p[2]).project(cam);          // world mm -> normalised device coords
        const x = r.left + (v.x * 0.5 + 0.5) * r.width, y = r.top + (0.5 - v.y * 0.5) * r.height;
        const d = document.createElement('div');
        d.className = 'qa-mark';
        // the svg box starts at (x, y), so its local origin IS the marker point -- no centring transform
        d.style.cssText = `position:fixed;left:${x}px;top:${y}px;z-index:9999;pointer-events:none`;
        const dy = (n++ - (markers.length - 1) / 2) * 18;                       // stagger: the marks are mm apart
        d.innerHTML = `<svg width="1" height="1" style="overflow:visible">`
          + `<line x1="-13" y1="0" x2="13" y2="0" stroke="#28e0ff" stroke-width="1.5"/>`
          + `<line x1="0" y1="-13" x2="0" y2="13" stroke="#28e0ff" stroke-width="1.5"/>`
          + `<line x1="13" y1="0" x2="34" y2="${dy}" stroke="#28e0ff" stroke-width="1"/>`
          + `<text x="38" y="${dy + 4}" fill="#28e0ff" font-family="monospace" font-size="12">${label}  z ${p[2].toFixed(1)}</text></svg>`;
        document.body.appendChild(d);
      }
    }, v.markers);
    await page.waitForTimeout(200);
  }
  const gb = await page.locator('#gl').boundingBox();
  await page.screenshot({ path: `${out}/${v.name}.png`, clip: gb });
  await page.evaluate(() => document.querySelectorAll('.qa-mark').forEach((n) => n.remove()));
  console.log('saved', `${out}/${v.name}.png`);
}
console.log('page errors:', JSON.stringify(errors.filter((e) => !/favicon/.test(e))));
await browser.close();
