import { test, expect, type Page } from '@playwright/test';

// Smoke tests against the dev server (npm run dev). Run: npx playwright install chromium && npm run e2e
const errors: string[] = [];
async function boot(page: Page, hash = ''): Promise<void> {
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto(`/${hash}`);
  await page.waitForFunction(() => (window as unknown as { atlas?: { store: { get(): { loaded: { manifest: boolean } } } } }).atlas?.store.get().loaded.manifest === true, null, { timeout: 60_000 });
}
const atlas = (page: Page) => page.evaluate(() => { const a = (window as unknown as { atlas: { store: { get(): Record<string, unknown> }; manifest: { meshes: unknown[] }; registry: { loaded(): Iterable<unknown> } } }).atlas; const st = a.store.get(); return { state: st, involved: [...(st['involved'] as Set<string>)], meshes: a.manifest.meshes.length, loaded: [...a.registry.loaded()].length }; });

test('loads without console errors and renders meshes', async ({ page }) => {
  test.setTimeout(180_000);
  await boot(page);
  await page.waitForFunction(() => [...(window as unknown as { atlas: { registry: { loaded(): Iterable<unknown> } } }).atlas.registry.loaded()].length > 20, null, { timeout: 120_000 });
  const a = await atlas(page);
  expect(a.meshes).toBeGreaterThan(400);
  expect(errors.filter((e) => !/favicon/.test(e))).toEqual([]);
});

test('selecting from the tree updates the content panel and the hash', async ({ page }) => {
  await boot(page);
  await page.fill('.tree-filter', 'putamen');
  await page.locator('#left').getByText('Putamen', { exact: false }).first().click();
  await expect(page.locator('#right .content:not([hidden]) h2').first()).toContainText(/Putamen/i, { timeout: 20_000 });
  await expect.poll(() => page.evaluate(() => location.hash)).toMatch(/#\/structure\/putamen/);
});

test('syndrome route dims the scene, marks involved meshes and steps deficits', async ({ page }) => {
  await boot(page, '#/syndrome/syn-wallenberg-lateral-medullary?step=1');
  await expect(page.locator('#syndrome-bar')).toBeVisible({ timeout: 30_000 });
  await expect(page.locator('#syndrome-bar')).toContainText('Wallenberg');
  const a = await atlas(page);
  expect((a.state['syndrome'] as { step: number }).step).toBe(1);
  expect(a.involved.length).toBeGreaterThan(0);
  await page.keyboard.press('Escape');
  await expect(page.locator('#syndrome-bar')).toBeHidden({ timeout: 30_000 });
});

test('quiz answers and glossary render', async ({ page }) => {
  await boot(page, '#/quiz/1');
  await expect(page.locator('#right .content:not([hidden]) h2').first()).toContainText('Clinical vignette 1');
  await page.keyboard.press('b');
  await expect(page.locator('.reveal')).toBeVisible();
  await page.goto('/#/glossary/g-decussation');
  await expect(page.locator('.gterm.active h3')).toContainText('Decussation');
});

test('real mouse input: click selects, drag orbits, nothing hidden covers the canvas', async ({ page }) => {
  test.setTimeout(120_000);
  await boot(page);
  await page.waitForFunction(() => [...(window as unknown as { atlas: { registry: { loaded(): Iterable<unknown> } } }).atlas.registry.loaded()].length > 100, null, { timeout: 90_000 });
  const box = (await page.locator('#gl').boundingBox())!;
  const cx = box.x + box.width / 2, cy = box.y + box.height / 2;
  // no [hidden] element may still be laid out (that was the bug: overlays with display:flex swallowed pointer events)
  const covering = await page.evaluate(([x, y]) => {
    const el = document.elementFromPoint(x!, y!);
    const bad = [...document.querySelectorAll('[hidden]')].filter((e) => getComputedStyle(e).display !== 'none').map((e) => e.id || e.className);
    return { center: el?.id ?? null, bad };
  }, [cx, cy]);
  expect(covering).toEqual({ center: 'gl', bad: [] });
  await page.mouse.click(cx, cy);
  await expect.poll(() => page.evaluate(() => (window as unknown as { atlas: { store: { get(): { selectedId: string | null } } } }).atlas.store.get().selectedId), { timeout: 10_000 }).not.toBeNull();
  const before = await page.evaluate(() => (window as unknown as { atlas: { sm: { camera: { position: { toArray(): number[] } } } } }).atlas.sm.camera.position.toArray());
  await page.mouse.move(cx - 80, cy);
  await page.mouse.down();
  for (let i = 1; i <= 10; i++) await page.mouse.move(cx - 80 + i * 16, cy + i * 4);
  await page.mouse.up();
  await page.waitForTimeout(600);
  const after = await page.evaluate(() => (window as unknown as { atlas: { sm: { camera: { position: { toArray(): number[] } } } } }).atlas.sm.camera.position.toArray());
  const moved = Math.hypot(after[0]! - before[0]!, after[1]! - before[1]!, after[2]! - before[2]!);
  expect(moved).toBeGreaterThan(20);
  // a drag must not count as a click (selection unchanged by the orbit)
  const sel = await page.evaluate(() => (window as unknown as { atlas: { store: { get(): { selectedId: string | null } } } }).atlas.store.get().selectedId);
  expect(sel).not.toBeNull();
});
