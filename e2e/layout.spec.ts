import { test, expect, type Page } from '@playwright/test';

// The three-column layout is 720px of panels before the 3D view gets anything, so a narrow window used to
// squeeze the canvas to a sliver and a phone-width one pushed it off the screen entirely. Below 900px the
// panels leave the grid and float over the canvas instead, closed by default. These tests pin that down at
// both ends, because it is invisible at the 1400x900 the rest of the suite runs at.

const boot = async (page: Page): Promise<void> => {
  await page.goto('/');
  await page.waitForFunction(
    () => (window as unknown as { atlas?: { store: { get(): { loaded: { manifest: boolean } } } } }).atlas?.store.get().loaded.manifest === true,
    null, { timeout: 60_000 });
};
const metrics = (page: Page) => page.evaluate(() => {
  const app = document.getElementById('app')!, tb = document.getElementById('toolbar')!;
  const gl = document.getElementById('gl')!.getBoundingClientRect();
  return {
    canvasW: Math.round(gl.width),
    viewportW: document.documentElement.clientWidth,
    classes: app.className,
    toolbarOverflows: tb.scrollWidth > tb.clientWidth + 1,
    bodyScrollLeft: document.body.scrollLeft,
    leftVisible: getComputedStyle(document.getElementById('left')!).display !== 'none',
    rightVisible: getComputedStyle(document.getElementById('right')!).display !== 'none',
  };
});

test('narrow: the 3D view keeps the full width and the panels start closed', async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 900 });
  await boot(page);
  const m = await metrics(page);
  expect(m.classes).toContain('no-left');
  expect(m.classes).toContain('no-right');
  // the canvas is the whole window, not window minus 720px of panels
  expect(m.canvasW).toBe(m.viewportW);
  expect(m.leftVisible).toBe(false);
  expect(m.rightVisible).toBe(false);
});

test('narrow: the toolbar fits, so it cannot push the page sideways', async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 900 });
  await boot(page);
  const m = await metrics(page);
  expect(m.toolbarOverflows).toBe(false);
  expect(m.bodyScrollLeft).toBe(0);
});

test('narrow: the panel toggles open one panel at a time, over the canvas', async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 900 });
  await boot(page);
  await page.locator('[data-testid="panel-left"]').click();
  let m = await metrics(page);
  expect(m.leftVisible).toBe(true);
  expect(m.canvasW).toBe(m.viewportW);          // an overlay, so the canvas did not shrink

  await page.locator('[data-testid="panel-right"]').click();
  m = await metrics(page);
  expect(m.rightVisible).toBe(true);
  expect(m.leftVisible).toBe(false);            // opening one closes the other
});

test('narrow: selecting a structure opens the detail panel', async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 900 });
  await boot(page);
  expect((await metrics(page)).rightVisible).toBe(false);
  await page.goto('/#/structure/putamen');
  await expect(page.locator('#right .content:not([hidden]) h2').first()).toContainText(/Putamen/i, { timeout: 30_000 });
  expect((await metrics(page)).rightVisible).toBe(true);
});

test('wide: the panels stay in the grid beside the 3D view', async ({ page }) => {
  await page.setViewportSize({ width: 1400, height: 900 });
  await boot(page);
  const m = await metrics(page);
  expect(m.classes).not.toContain('no-left');
  expect(m.classes).not.toContain('no-right');
  expect(m.leftVisible).toBe(true);
  expect(m.rightVisible).toBe(true);
  // the canvas is what is left after the two columns, so distinctly narrower than the window
  expect(m.canvasW).toBeLessThan(m.viewportW - 600);
});
