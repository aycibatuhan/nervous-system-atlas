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

// ---- PAM50 spinal levels on the cord slices ------------------------------------
type SpineWin = { atlas: {
  store: { get(): { loaded: { cord: boolean }; selectedId: string | null; cordLevel: number | null }; set(p: Record<string, unknown>): void };
  spine: { byId: Map<number, { name: string; meshId: string; region: string }> } | null;
  uniforms: { uHasSpine: { value: number }; uSpineSel: { value: number }; uSpineHover: { value: number } };
  sm: { camera: { fov: number; up: { set(x: number, y: number, z: number): void }; near: number; far: number; updateProjectionMatrix(): void };
        controls: { target: { set(x: number, y: number, z: number): void }; update(): void };
        moveCamera(p: { x: number; y: number; z: number }, t: { x: number; y: number; z: number }, ms: number): void; requestRender(): void };
} };

/** Point the camera straight down the cord at a world point, near-orthographically (see scripts/shots-cord.mjs). */
async function lookDownCord(page: Page, at: { x: number; y: number; z: number }, half = 22): Promise<void> {
  await page.evaluate(([at, half]) => {
    const a = (window as unknown as SpineWin).atlas;
    a.sm.controls.target.set(at.x, at.y, at.z);
    a.sm.camera.up.set(0, 1, 0);
    a.sm.camera.fov = 6;
    const dist = (half / Math.tan((a.sm.camera.fov * Math.PI) / 360)) * 1.05;
    a.sm.moveCamera({ x: at.x, y: at.y, z: at.z + dist }, at, 0);
    a.sm.camera.near = 1; a.sm.camera.far = 4000; a.sm.camera.updateProjectionMatrix();
    a.sm.controls.update(); a.sm.requestRender();
  }, [at, half] as const);
  await page.waitForTimeout(1200);
}

test('cord slices: the spinal level under the cursor is named, and clicking it selects the cord segment', async ({ page }) => {
  test.setTimeout(180_000);
  const errorsBefore = errors.length;
  await boot(page);
  await page.waitForFunction(() => (window as unknown as { atlas: { store: { get(): { loaded: { volume: boolean } } } } }).atlas.store.get().loaded.volume === true, null, { timeout: 120_000 });
  // the C5 segment on our own centreline, as atlas-pam50 measured it
  const c5 = await page.evaluate(async () => {
    const r = await fetch('data/volumes/cord_levels.json');
    const j = (await r.json()) as { spinalLevels: { name: string; top: number[]; bottom: number[] }[] };
    const l = j.spinalLevels.find((x) => x.name === 'C5')!;
    return { x: (l.top[0]! + l.bottom[0]!) / 2, y: (l.top[1]! + l.bottom[1]!) / 2, z: (l.top[2]! + l.bottom[2]!) / 2 };
  });
  expect(c5.z).toBeLessThan(-110);
  // cord MRI on, only the axial slice, no meshes at all so the raycast can only land on the slice plane
  await page.evaluate((c5) => {
    const a = (window as unknown as SpineWin).atlas;
    a.store.set({ cordMri: true, contrast: 't2w', visibleSystems: new Set(), shownStructures: new Set(), hiddenStructures: new Set(),
      overlay: { opacity: 0.75, showAllLabels: true, territory: false, tracts: false },
      slices: { axial: Math.round(c5.z), coronal: Math.round(c5.y), sagittal: Math.round(c5.x), visible: { axial: true, coronal: false, sagittal: false }, pinned: true } });
  }, c5);
  await page.waitForFunction(() => (window as unknown as SpineWin).atlas.store.get().loaded.cord === true, null, { timeout: 120_000 });
  await page.waitForFunction(() => (window as unknown as SpineWin).atlas.spine !== null, null, { timeout: 60_000 });
  // the level volume and its LUT reached the shader
  expect(await page.evaluate(() => (window as unknown as SpineWin).atlas.uniforms.uHasSpine.value)).toBe(1);
  expect(await page.evaluate(() => (window as unknown as SpineWin).atlas.spine!.byId.size)).toBe(30);

  await lookDownCord(page, c5);
  const box = (await page.locator('#gl').boundingBox())!;
  const cx = box.x + box.width / 2, cy = box.y + box.height / 2;
  await page.mouse.move(cx - 30, cy - 30);
  await page.mouse.move(cx, cy);
  // hovering the cord slice names the level in the MNI readout and lights that level up on the slice
  await expect.poll(() => page.locator('.hud').textContent(), { timeout: 30_000 }).toMatch(/C5 · cervical segment/);
  expect(await page.evaluate(() => (window as unknown as SpineWin).atlas.store.get().cordLevel)).toBe(5);
  expect(await page.evaluate(() => (window as unknown as SpineWin).atlas.uniforms.uSpineHover.value)).toBe(1 << 5);

  // clicking the level selects the cord segment that contains it, and the shader gets its outline mask
  await page.mouse.click(cx, cy);
  await expect.poll(() => page.evaluate(() => (window as unknown as SpineWin).atlas.store.get().selectedId), { timeout: 20_000 }).toBe('spinal-segment-cervical');
  expect(await page.evaluate(() => (window as unknown as SpineWin).atlas.uniforms.uSpineSel.value)).toBe(0b111111110);

  // one level lower down the cord the readout follows the level, not the click
  const t10 = await page.evaluate(async () => {
    const r = await fetch('data/volumes/cord_levels.json');
    const j = (await r.json()) as { spinalLevels: { name: string; top: number[]; bottom: number[] }[] };
    const l = j.spinalLevels.find((x) => x.name === 'T10')!;
    return { x: (l.top[0]! + l.bottom[0]!) / 2, y: (l.top[1]! + l.bottom[1]!) / 2, z: (l.top[2]! + l.bottom[2]!) / 2 };
  });
  await page.evaluate((t10) => {
    const a = (window as unknown as SpineWin).atlas;
    a.store.set({ slices: { axial: Math.round(t10.z), coronal: Math.round(t10.y), sagittal: Math.round(t10.x), visible: { axial: true, coronal: false, sagittal: false }, pinned: true } });
  }, t10);
  await lookDownCord(page, t10);
  await page.mouse.move(cx - 30, cy - 30);
  await page.mouse.move(cx, cy);
  await expect.poll(() => page.locator('.hud').textContent(), { timeout: 30_000 }).toMatch(/T10 · thoracic segment/);
  await page.mouse.click(cx, cy);
  await expect.poll(() => page.evaluate(() => (window as unknown as SpineWin).atlas.store.get().selectedId), { timeout: 20_000 }).toBe('spinal-segment-thoracic');
  expect(errors.slice(errorsBefore).filter((e) => !/favicon/.test(e))).toEqual([]);
});

// ---- about and credits (#/about) -------------------------------------------------
type AboutWin = { atlas: { manifest: { edition?: string; sources: Record<string, { license: string; citation: string }>; licenses: Record<string, unknown> } } };

/** One round trip that reads the whole credits table out of the DOM (a per-row locator loop is far too slow here). */
const auditAbout = (page: Page) => page.evaluate(() => {
  const m = (window as unknown as AboutWin).atlas.manifest;
  const rows = [...document.querySelectorAll('#right .content:not([hidden]) .about-sources tbody tr')];
  return {
    manifestSources: Object.keys(m.sources).sort(),
    manifestLicences: Object.keys(m.licenses).length,
    edition: m.edition ?? 'private',
    rows: rows.map((r) => ({
      id: (r as HTMLElement).dataset['source'] ?? '',
      licenceHref: r.querySelector('.about-lic a')?.getAttribute('href') ?? '',
      licenceName: r.querySelector('.about-lic a')?.textContent ?? '',
      citation: r.querySelector('.cite-text')?.textContent ?? '',
      sourceHref: r.querySelector('.src-link')?.getAttribute('href') ?? '',
      meshes: r.querySelector('.num')?.textContent ?? '',
      badge: !!r.querySelector('.badge-nc'),
    })),
    licenceSections: document.querySelectorAll('#right .content:not([hidden]) .licence-details').length,
    editionTag: document.querySelector('#about-edition')?.textContent ?? '',
    codeLicence: document.querySelector('#about-code-licence')?.getAttribute('href') ?? '',
    dataLicence: document.querySelector('#about-data-licence')?.getAttribute('href') ?? '',
  };
});

test('the About panel credits every data source in the manifest, each with a licence link', async ({ page }) => {
  test.setTimeout(240_000);
  const errorsBefore = errors.length;
  await boot(page, '#/about');
  const panel = page.locator('#right .content:not([hidden])');
  await expect(panel.locator('h2').first()).toContainText('About and credits', { timeout: 60_000 });
  await expect.poll(() => auditAbout(page).then((a) => a.rows.length), { timeout: 30_000 }).toBeGreaterThan(5);

  const a = await auditAbout(page);
  // one row per manifest source, with the same ids
  expect(a.rows.map((r) => r.id).sort()).toEqual(a.manifestSources);
  for (const r of a.rows) {
    expect(r.licenceHref, `licence link of ${r.id}`).toMatch(/^https?:\/\//);
    expect(r.licenceName.length, `licence name of ${r.id}`).toBeGreaterThan(3);
    expect(r.citation.length, `citation of ${r.id}`).toBeGreaterThan(20);
    expect(r.sourceHref, `download link of ${r.id}`).toMatch(/^https?:\/\//);
    expect(Number(r.meshes), `mesh count of ${r.id}`).toBeGreaterThanOrEqual(0);
  }
  expect(a.rows.some((r) => r.badge), 'a restricted source is badged').toBe(a.edition === 'private');
  expect(a.editionTag).toContain(a.edition);
  expect(a.codeLicence).toMatch(/apache\.org\/licenses\/LICENSE-2\.0/);
  expect(a.dataLicence).toMatch(/creativecommons\.org\/licenses\/by-sa\/4\.0/);
  expect(a.licenceSections).toBe(a.manifestLicences);   // one expandable text per licence

  await page.evaluate(() => { document.getElementById('right')!.scrollTop = 0; });
  await page.screenshot({ path: 'qa/shots/about/about-panel.png' });
  await panel.locator('.about-sources').scrollIntoViewIfNeeded();
  await page.screenshot({ path: 'qa/shots/about/about-sources.png' });

  // the verbatim licence text really loads out of public/data/licenses/
  const cc = panel.locator('.licence-details', { hasText: 'Attribution-ShareAlike 4.0' }).first();
  await cc.locator('summary').click();
  await expect(cc.locator('.licence-text')).toContainText(/Creative Commons/i, { timeout: 30_000 });
  await page.screenshot({ path: 'qa/shots/about/about-licence-text.png' });
  expect(errors.slice(errorsBefore).filter((e) => !/favicon/.test(e))).toEqual([]);
});

test('every structure panel shows a Source line that opens the credits', async ({ page }) => {
  test.setTimeout(240_000);
  await boot(page, '#/structure/putamen');
  const panel = page.locator('#right .content:not([hidden])');
  await expect(panel.locator('h2').first()).toContainText(/Putamen/i, { timeout: 60_000 });
  const line = panel.locator('.source-line').first();
  await expect(line).toContainText('Source:', { timeout: 30_000 });
  await expect(line.locator('a.src-credit').first()).toHaveAttribute('href', '#/about');
  await expect(line.locator('.src-lic').first()).toContainText(/\(.+\)/);
  await page.screenshot({ path: 'qa/shots/about/structure-source-line.png' });

  const hash = (h: string) => page.evaluate((x) => { location.hash = x; }, h);
  const sourceText = () => page.evaluate(() => document.querySelector('#right .content:not([hidden]) .source-line')?.textContent ?? '');

  // a derived mesh says so, with the construction method in the tooltip
  await hash('#/structure/spinal-segment-cervical');
  await expect.poll(sourceText, { timeout: 60_000 }).toMatch(/Source:.*derived:/s);
  expect((await page.getAttribute('#right .content:not([hidden]) .derived-tag', 'title'))!.length).toBeGreaterThan(40);

  // a pathway credits its stations' sources too
  await hash('#/pathway/pathway-lateral-corticospinal');
  await expect.poll(sourceText, { timeout: 60_000 }).toContain('Source:');

  // the credit link and the toolbar button both reach the About panel
  await hash('#/structure/putamen');
  await expect.poll(sourceText, { timeout: 60_000 }).toContain('Source:');
  await panel.locator('.source-line a.src-credit').first().click();
  await expect.poll(() => page.evaluate(() => location.hash), { timeout: 30_000 }).toBe('#/about');
  await expect(page.locator('#right .content:not([hidden]) h2').first()).toContainText('About and credits', { timeout: 30_000 });
  await hash('#/slice');
  await page.locator('.about-btn').click();
  await expect.poll(() => page.evaluate(() => location.hash), { timeout: 30_000 }).toBe('#/about');
  await expect(page.locator('#right .content:not([hidden]) h2').first()).toContainText('About and credits', { timeout: 30_000 });
});
