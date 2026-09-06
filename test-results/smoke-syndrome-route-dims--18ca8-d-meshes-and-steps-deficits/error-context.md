# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: smoke.spec.ts >> syndrome route dims the scene, marks involved meshes and steps deficits
- Location: e2e/smoke.spec.ts:30:1

# Error details

```
Error: expect(locator).toBeHidden() failed

Locator:  locator('#syndrome-bar')
Expected: hidden
Received: visible
Timeout:  30000ms

Call log:
  - Expect "toBeHidden" locator('#syndrome-bar') with timeout 30000ms
  - waiting for locator('#syndrome-bar')
    32 × locator resolved to <div hidden="" id="syndrome-bar"></div>
       - unexpected value "visible"

```

# Page snapshot

```yaml
- generic [ref=e2]:
  - banner [ref=e3]:
    - generic [ref=e4]:
      - strong [ref=e5]: Clinical Neuroanatomy Atlas
      - text: MNI152 · 3D + MRI
    - generic [ref=e6]:
      - button "Lateral (L)" [ref=e7] [cursor=pointer]
      - button "Lateral (R)" [ref=e8] [cursor=pointer]
      - button "Anterior" [ref=e9] [cursor=pointer]
      - button "Posterior" [ref=e10] [cursor=pointer]
      - button "Superior" [ref=e11] [cursor=pointer]
      - button "Inferior" [ref=e12] [cursor=pointer]
      - button "Medial (L)" [ref=e13] [cursor=pointer]
      - button "Medial (R)" [ref=e14] [cursor=pointer]
    - searchbox "Search structures, pathways, syndromes… ( > syndromes )" [ref=e16]
    - generic [ref=e17]:
      - button "Tree filter" [ref=e18] [cursor=pointer]
      - button "Quiz" [ref=e19] [cursor=pointer]
      - button "Glossary" [ref=e20] [cursor=pointer]
      - button "Screenshot" [ref=e21] [cursor=pointer]
      - button "?" [ref=e22] [cursor=pointer]
      - generic [ref=e23]: 540 structures · 209 authored
  - complementary [ref=e24]:
    - generic [ref=e25]: Structures
    - searchbox "Filter structures…" [ref=e26]
    - generic [ref=e27]:
      - generic [ref=e28] [cursor=pointer]:
        - generic [ref=e29]: ▸
        - checkbox [checked] [ref=e30]
        - generic [ref=e32]: Cerebrum
        - generic [ref=e33]: "126"
      - generic [ref=e34] [cursor=pointer]:
        - generic [ref=e35]: ▸
        - checkbox [checked] [ref=e36]
        - generic [ref=e38]: Basal ganglia
        - generic [ref=e39]: "14"
      - generic [ref=e40] [cursor=pointer]:
        - generic [ref=e41]: ▸
        - checkbox [checked] [ref=e42]
        - generic [ref=e44]: Diencephalon
        - generic [ref=e45]: "54"
      - generic [ref=e46] [cursor=pointer]:
        - generic [ref=e47]: ▸
        - checkbox [checked] [ref=e48]
        - generic [ref=e50]: Brainstem
        - generic [ref=e51]: "43"
      - generic [ref=e52] [cursor=pointer]:
        - generic [ref=e53]: ▸
        - checkbox [checked] [ref=e54]
        - generic [ref=e56]: Cerebellum
        - generic [ref=e57]: "43"
      - generic [ref=e58] [cursor=pointer]:
        - generic [ref=e59]: ▸
        - checkbox [checked] [ref=e60]
        - generic [ref=e62]: Cranial nerves
        - generic [ref=e63]: "49"
      - generic [ref=e64] [cursor=pointer]:
        - generic [ref=e65]: ▸
        - checkbox [ref=e66]
        - generic [ref=e68]: Spinal cord
        - generic [ref=e69]: "6"
      - generic [ref=e70] [cursor=pointer]:
        - generic [ref=e71]: ▸
        - checkbox [ref=e72]
        - generic [ref=e74]: Peripheral nerves
        - generic [ref=e75]: "38"
      - generic [ref=e76] [cursor=pointer]:
        - generic [ref=e77]: ▸
        - checkbox [ref=e78]
        - generic [ref=e80]: Autonomic
        - generic [ref=e81]: "4"
      - generic [ref=e82] [cursor=pointer]:
        - generic [ref=e83]: ▸
        - checkbox [checked] [ref=e84]
        - generic [ref=e86]: Ventricles & CSF
        - generic [ref=e87]: "10"
      - generic [ref=e88] [cursor=pointer]:
        - generic [ref=e89]: ▸
        - checkbox [ref=e90]
        - generic [ref=e92]: Meninges
        - generic [ref=e93]: "4"
      - generic [ref=e94] [cursor=pointer]:
        - generic [ref=e95]: ▸
        - checkbox [checked] [ref=e96]
        - generic [ref=e98]: Arteries
        - generic [ref=e99]: "30"
      - generic [ref=e100] [cursor=pointer]:
        - generic [ref=e101]: ▸
        - checkbox [ref=e102]
        - generic [ref=e104]: Arterial territories
        - generic [ref=e105]: "38"
      - generic [ref=e106] [cursor=pointer]:
        - generic [ref=e107]: ▸
        - checkbox [ref=e108]
        - generic [ref=e110]: Venous sinuses
        - generic [ref=e111]: "17"
      - generic [ref=e112] [cursor=pointer]:
        - generic [ref=e113]: ▸
        - checkbox [ref=e114]
        - generic [ref=e116]: White-matter tracts
        - generic [ref=e117]: "60"
      - generic [ref=e118] [cursor=pointer]:
        - generic [ref=e119]: ▸
        - checkbox [checked] [ref=e120]
        - generic [ref=e122]: Brain surface
        - generic [ref=e123]: "4"
  - main [ref=e124]
  - complementary [ref=e128]:
    - generic [ref=e130]:
      - heading "Select a structure" [level=2] [ref=e131]
      - paragraph [ref=e132]: Click a mesh in the 3D view, click the MRI slice, or pick a structure from the tree on the left.
      - paragraph [ref=e133]: "Hover:"
  - contentinfo [ref=e134]:
    - generic [ref=e135]:
      - generic [ref=e136]:
        - checkbox "Axial (z) mm no peel" [checked] [ref=e137]
        - generic [ref=e138]: Axial (z)
        - slider [ref=e139]: "-46"
        - spinbutton [ref=e140]: "-46"
        - generic [ref=e141]: mm
        - 'combobox "Peel: hide meshes on one side of this plane" [ref=e142]':
          - option "no peel" [selected]
          - option "hide above"
          - option "hide below"
      - generic [ref=e143]:
        - checkbox "Coronal (y) mm no peel" [ref=e144]
        - generic [ref=e145]: Coronal (y)
        - slider [ref=e146]: "-42"
        - spinbutton [ref=e147]: "-42"
        - generic [ref=e148]: mm
        - 'combobox "Peel: hide meshes on one side of this plane" [ref=e149]':
          - option "no peel" [selected]
          - option "hide anterior"
          - option "hide posterior"
      - generic [ref=e150]:
        - checkbox "Sagittal (x) mm no peel" [ref=e151]
        - generic [ref=e152]: Sagittal (x)
        - slider [ref=e153]: "-10"
        - spinbutton [ref=e154]: "-10"
        - generic [ref=e155]: mm
        - 'combobox "Peel: hide meshes on one side of this plane" [ref=e156]':
          - option "no peel" [selected]
          - option "hide right"
          - option "hide left"
      - generic [ref=e157]:
        - generic [ref=e158]:
          - text: MRI
          - combobox "MRI" [ref=e159]:
            - option "T1" [selected]
            - option "T2"
        - generic [ref=e160]:
          - text: overlay
          - slider "overlay" [ref=e161]: "0.75"
        - generic [ref=e162]:
          - checkbox "all labels" [ref=e163]
          - text: all labels
        - generic [ref=e164]:
          - checkbox "territories" [ref=e165]
          - text: territories
        - generic [ref=e166]:
          - checkbox "pin slices" [ref=e167]
          - text: pin slices
```

# Test source

```ts
  1  | import { test, expect, type Page } from '@playwright/test';
  2  | 
  3  | // Smoke tests against the dev server (npm run dev). Run: npx playwright install chromium && npm run e2e
  4  | const errors: string[] = [];
  5  | async function boot(page: Page, hash = ''): Promise<void> {
  6  |   page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  7  |   page.on('pageerror', (e) => errors.push(e.message));
  8  |   await page.goto(`/${hash}`);
  9  |   await page.waitForFunction(() => (window as unknown as { atlas?: { store: { get(): { loaded: { manifest: boolean } } } } }).atlas?.store.get().loaded.manifest === true, null, { timeout: 60_000 });
  10 | }
  11 | const atlas = (page: Page) => page.evaluate(() => { const a = (window as unknown as { atlas: { store: { get(): Record<string, unknown> }; manifest: { meshes: unknown[] }; registry: { loaded(): Iterable<unknown> } } }).atlas; const st = a.store.get(); return { state: st, involved: [...(st['involved'] as Set<string>)], meshes: a.manifest.meshes.length, loaded: [...a.registry.loaded()].length }; });
  12 | 
  13 | test('loads without console errors and renders meshes', async ({ page }) => {
  14 |   test.setTimeout(180_000);
  15 |   await boot(page);
  16 |   await page.waitForFunction(() => [...(window as unknown as { atlas: { registry: { loaded(): Iterable<unknown> } } }).atlas.registry.loaded()].length > 20, null, { timeout: 120_000 });
  17 |   const a = await atlas(page);
  18 |   expect(a.meshes).toBeGreaterThan(400);
  19 |   expect(errors.filter((e) => !/favicon/.test(e))).toEqual([]);
  20 | });
  21 | 
  22 | test('selecting from the tree updates the content panel and the hash', async ({ page }) => {
  23 |   await boot(page);
  24 |   await page.fill('.tree-filter', 'putamen');
  25 |   await page.locator('#left').getByText('Putamen', { exact: false }).first().click();
  26 |   await expect(page.locator('#right .content:not([hidden]) h2').first()).toContainText(/Putamen/i, { timeout: 20_000 });
  27 |   await expect.poll(() => page.evaluate(() => location.hash)).toMatch(/#\/structure\/putamen/);
  28 | });
  29 | 
  30 | test('syndrome route dims the scene, marks involved meshes and steps deficits', async ({ page }) => {
  31 |   await boot(page, '#/syndrome/syn-wallenberg-lateral-medullary?step=1');
  32 |   await expect(page.locator('#syndrome-bar')).toBeVisible({ timeout: 30_000 });
  33 |   await expect(page.locator('#syndrome-bar')).toContainText('Wallenberg');
  34 |   const a = await atlas(page);
  35 |   expect((a.state['syndrome'] as { step: number }).step).toBe(1);
  36 |   expect(a.involved.length).toBeGreaterThan(0);
  37 |   await page.keyboard.press('Escape');
> 38 |   await expect(page.locator('#syndrome-bar')).toBeHidden({ timeout: 30_000 });
     |                                               ^ Error: expect(locator).toBeHidden() failed
  39 | });
  40 | 
  41 | test('quiz answers and glossary render', async ({ page }) => {
  42 |   await boot(page, '#/quiz/1');
  43 |   await expect(page.locator('#right .content:not([hidden]) h2').first()).toContainText('Clinical vignette 1');
  44 |   await page.keyboard.press('b');
  45 |   await expect(page.locator('.reveal')).toBeVisible();
  46 |   await page.goto('/#/glossary/g-decussation');
  47 |   await expect(page.locator('.gterm.active h3')).toContainText('Decussation');
  48 | });
  49 | 
```