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

test('topic route spotlights its meshes and selecting a structure returns to the structure panel', async ({ page }) => {
  await boot(page, '#/topic/topic-epilepsy-localization');
  await expect(page.locator('#right .content:not([hidden]) h2').first()).toContainText(/Epilepsy/i, { timeout: 30_000 });
  await expect.poll(() => page.evaluate(() => [...(window as unknown as { atlas: { store: { get(): { involved: Set<string> } } } }).atlas.store.get().involved].length), { timeout: 30_000 }).toBeGreaterThan(3);
  await page.fill('.tree-filter', 'putamen');
  await page.locator('#left').getByText('Putamen', { exact: false }).first().click();
  await expect(page.locator('#right .content:not([hidden]) h2').first()).toContainText(/Putamen/i, { timeout: 20_000 });
  await expect.poll(() => page.evaluate(() => location.hash)).toMatch(/#\/structure\/putamen/);
});

test('the sources tab lists open-access citations that link to free full text', async ({ page }) => {
  await boot(page, '#/structure/putamen');
  await page.locator('#right .tabs button', { hasText: 'Sources' }).click();
  const link = page.locator('#right .section .cite a').first();
  await expect(link).toBeVisible({ timeout: 20_000 });
  await expect(link).toHaveAttribute('target', '_blank');
  await expect(link).toHaveAttribute('href', /^https:\/\/(www\.ncbi\.nlm\.nih\.gov\/books\/NBK|pmc\.ncbi\.nlm\.nih\.gov\/articles\/PMC)/);
  await expect(page.locator('#right .section')).not.toContainText(/Snell|Berkowitz/i);
});

// ---- left tree: group visibility -------------------------------------------------
type TreeWin = { atlas: { manifest: { systems: { id: string }[]; meshes: { id: string; system: string; subsystem?: string }[] };
  registry: { loaded(): Iterable<{ userData: { id: string }; visible: boolean }>; byId: Map<string, { visible: boolean }> };
  store: { get(): { visibleSystems: Set<string>; shownStructures: Set<string>; hiddenStructures: Set<string> } } } };

/** how many meshes of one tree group are actually visible in the scene right now */
const groupVisible = (page: Page, key: string) => page.evaluate((k) => {
  const a = (window as unknown as TreeWin).atlas;
  const [sys, sub = ''] = k.split('/');
  const ids = new Set(a.manifest.meshes.filter((m) => m.system === sys && (m.subsystem ?? '') === sub).map((m) => m.id));
  let visible = 0;
  for (const m of a.registry.loaded()) if (ids.has(m.userData.id) && m.visible) visible++;
  return { total: ids.size, visible };
}, key);

const sceneVisible = (page: Page) => page.evaluate(() => {
  let n = 0;
  for (const m of (window as unknown as TreeWin).atlas.registry.loaded()) if (m.visible) n++;
  return n;
});

test('tree groups: a subsystem checkbox shows/hides all of its meshes, tri-state and all', async ({ page }) => {
  test.setTimeout(120_000);
  await boot(page);
  await page.waitForFunction(() => [...(window as unknown as { atlas: { registry: { loaded(): Iterable<unknown> } } }).atlas.registry.loaded()].length > 20, null, { timeout: 90_000 });
  await page.locator('.tree-sys .name', { hasText: 'Cerebrum' }).first().click();
  const sub = page.locator('.tree-sub').first();
  const key = (await sub.getAttribute('data-group'))!;
  expect(key).toContain('/');
  const box = sub.locator('input[type=checkbox]');
  const total = (await groupVisible(page, key)).total;
  expect(total).toBeGreaterThan(0);
  // tick → every mesh in the group is on (even the ones the manifest hides by default)
  await box.click();
  await expect.poll(() => groupVisible(page, key).then((g) => g.visible), { timeout: 30_000 }).toBe(total);
  expect(await box.isChecked()).toBe(true);
  expect(await box.evaluate((e: HTMLInputElement) => e.indeterminate)).toBe(false);
  // untick → all of them off
  await box.click();
  await expect.poll(() => groupVisible(page, key).then((g) => g.visible), { timeout: 30_000 }).toBe(0);
  expect(await box.isChecked()).toBe(false);
  // a single structure back on inside the group → the group box goes indeterminate
  await page.locator(`.tree-sub[data-group="${key}"]`).click();          // expand it
  await page.locator('.tree-row input[type=checkbox]').first().click();
  await expect.poll(() => page.locator(`.tree-sub[data-group="${key}"] input`).evaluate((e: HTMLInputElement) => e.indeterminate), { timeout: 20_000 }).toBe(true);
});

test('tree master switch turns every structure on and off, and Defaults restores the start view', async ({ page }) => {
  // "all on" pulls every one of the ~660 meshes in, which saturates the main thread under the
  // software renderer a headless run uses — hence the roomy budget; the store itself changes synchronously.
  test.setTimeout(420_000);
  await boot(page);
  await page.waitForFunction(() => [...(window as unknown as { atlas: { registry: { loaded(): Iterable<unknown> } } }).atlas.registry.loaded()].length > 20, null, { timeout: 90_000 });
  const before = await sceneVisible(page);
  expect(before).toBeGreaterThan(0);
  // first click: everything on (all systems, every mesh forced visible)
  await page.locator('.master-box').click();
  await expect.poll(() => page.evaluate(() => {
    const a = (window as unknown as TreeWin).atlas; const s = a.store.get();
    return s.visibleSystems.size === a.manifest.systems.length && s.shownStructures.size === a.manifest.meshes.length && s.hiddenStructures.size === 0;
  }), { timeout: 90_000 }).toBe(true);
  // let the ~660 meshes finish arriving: while they decode, the main thread starves input and the
  // next click can sit in the queue for a long time
  await page.waitForFunction(() => {
    const a = (window as unknown as TreeWin).atlas;
    return [...a.registry.loaded()].length === a.manifest.meshes.length;
  }, null, { timeout: 240_000 });
  await expect(page.locator('.master-box')).toBeChecked();
  // second click: nothing at all
  await page.locator('.master-box').click();
  await expect.poll(() => page.evaluate(() => {
    const s = (window as unknown as TreeWin).atlas.store.get();
    return s.visibleSystems.size + s.shownStructures.size + s.hiddenStructures.size;
  }), { timeout: 60_000 }).toBe(0);
  await expect.poll(() => sceneVisible(page), { timeout: 60_000 }).toBe(0);
  // Defaults: back to the manifest's own view (more meshes have finished loading by now, so
  // compare the state rather than a count taken while the scene was still filling in)
  await page.locator('.tree-master button').click();
  await expect.poll(() => page.evaluate(() => {
    const a = (window as unknown as TreeWin).atlas; const s = a.store.get();
    return { shown: s.shownStructures.size, hidden: s.hiddenStructures.size, systems: s.visibleSystems.size };
  }), { timeout: 60_000 }).toEqual({ shown: 0, hidden: 0, systems: (await page.evaluate(() => (window as unknown as { atlas: { manifest: { systems: { defaultVisible?: boolean }[] } } }).atlas.manifest.systems.filter((x) => x.defaultVisible).length)) });
  const after = await sceneVisible(page);
  expect(after).toBeGreaterThanOrEqual(before);
  expect(after).toBeLessThan(await page.evaluate(() => (window as unknown as TreeWin).atlas.manifest.meshes.length));
});

// ---- camera interaction budget --------------------------------------------------
type PerfWin = { atlas: { picker: { picks: number }; sm: { renders: number } } };
const counters = (page: Page) => page.evaluate(() => ({ picks: (window as unknown as PerfWin).atlas.picker.picks, renders: (window as unknown as PerfWin).atlas.sm.renders }));

test('interaction budget: a drag runs no hover raycasts, the view settles and the loop idles', async ({ page }) => {
  test.setTimeout(300_000);
  await boot(page);
  await page.waitForFunction(() => [...(window as unknown as { atlas: { registry: { loaded(): Iterable<unknown> } } }).atlas.registry.loaded()].length > 100, null, { timeout: 120_000 });
  await page.waitForTimeout(3000);
  const box = (await page.locator('#gl').boundingBox())!;
  const cx = box.x + box.width / 2, cy = box.y + box.height / 2;
  for (const quality of ['low', 'high'] as const) {
    await page.evaluate((q) => (window as unknown as { atlas: { store: { set(p: { quality: string }): void } } }).atlas.store.set({ quality: q }), quality);
    await page.waitForTimeout(1500);
    await page.mouse.move(cx - 250, cy - 80);
    await page.waitForTimeout(400);
    await page.evaluate(() => { const w = window as unknown as { __frames: number[] }; w.__frames = []; let last = performance.now(); const tick = (): void => { const n = performance.now(); w.__frames.push(n - last); last = n; requestAnimationFrame(tick); }; requestAnimationFrame(tick); });
    const start = await counters(page);
    await page.mouse.down();
    // few steps on purpose: headless Chromium software-renders ~600 meshes at about 1 fps, and every
    // mouse.move waits for a frame. The counters below do not depend on how fast the frames come.
    for (let i = 1; i <= 10; i++) await page.mouse.move(cx - 250 + i * 40, cy - 80 + Math.sin(i / 2) * 40);
    const during = await counters(page);
    await page.mouse.up();
    // a BVH raycast over ~600 meshes must not run while the pointer is steering the camera
    expect(during.picks - start.picks).toBe(0);
    const frames = await page.evaluate(() => { const w = window as unknown as { __frames: number[] }; const f = [...w.__frames]; w.__frames = []; return f; });
    const sorted = [...frames].sort((a, b) => a - b);
    const p95 = sorted[Math.floor(sorted.length * 0.95)] ?? 0;
    console.log(`[${quality}] drag: ${during.renders - start.renders} frames, p50 ${sorted[Math.floor(sorted.length / 2)]?.toFixed(1)} ms, p95 ${p95.toFixed(1)} ms, picks ${during.picks - start.picks}`);
    // the flick coasts briefly and stops instead of drifting
    await page.waitForTimeout(1500);
    const settled = await counters(page);
    const idle0 = settled.renders;
    await page.waitForTimeout(2000);
    const idle1 = (await counters(page)).renders;
    console.log(`[${quality}] coast after release: ${settled.renders - during.renders} frames · idle 2 s: ${idle1 - idle0} renders`);
    expect(settled.renders - during.renders).toBeLessThan(60);   // ~1 s of damping tail at 60 Hz would be 60+
    // render-on-demand: a continuous loop would draw once per animation frame (~120 over 2 s in a
    // real browser). A handful is fine — background LOD upgrades still request the odd frame.
    expect(idle1 - idle0).toBeLessThanOrEqual(10);
  }
});
