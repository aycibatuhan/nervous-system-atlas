import { test, expect, type Page } from '@playwright/test';

// The fresh-clone path: someone clones the repository, runs `npm run dev` and has no public/data/ yet.
// The app must say so instead of dying on a parse error, and it must recognise BOTH shapes the miss can take:
// a real 404 from a built site or `vite preview`, and the 200-with-index.html that a dev server's SPA fallback
// used to return (which is what actually happened, and what produced "Unexpected token '<'").
//
// The request is intercepted rather than run against a data-less server, so this test needs no second fixture
// and still exercises the real loader, the real error type and the real overlay.

const FALLBACK_HTML = '<!doctype html><html><head><title>Clinical Neuroanatomy Atlas</title></head><body></body></html>';

async function expectNoDataMessage(page: Page): Promise<void> {
  const panel = page.locator('[data-testid="no-data"]');
  await expect(panel).toBeVisible({ timeout: 30_000 });
  await expect(panel).toContainText('No atlas data found');
  await expect(panel.locator('code')).toHaveText('npm run data');
  await expect(panel.locator('a')).toHaveAttribute('href', /docs\/pipeline\.md$/);
  // and it must not be the old cryptic failure
  await expect(panel).not.toContainText('Unexpected token');
  await expect(page.locator('#overlay-msg')).not.toContainText('Failed to start');
}

test('a missing manifest that 404s shows the setup message, not a parse error', async ({ page }) => {
  await page.route('**/data/manifest.json', (route) => route.fulfill({ status: 404, body: 'not built' }));
  await page.goto('/');
  await expectNoDataMessage(page);
});

test('a dev server answering the manifest with its fallback HTML shows the same message', async ({ page }) => {
  await page.route('**/data/manifest.json', (route) =>
    route.fulfill({ status: 200, contentType: 'text/html', body: FALLBACK_HTML }));
  await page.goto('/');
  await expectNoDataMessage(page);
});

test('the setup message is translated', async ({ page }) => {
  await page.route('**/data/manifest.json', (route) => route.fulfill({ status: 404, body: 'not built' }));
  await page.addInitScript(() => localStorage.setItem('atlas.locale', 'tr'));
  await page.goto('/');
  const panel = page.locator('[data-testid="no-data"]');
  await expect(panel).toBeVisible({ timeout: 30_000 });
  await expect(panel).toContainText('Atlas verisi bulunamadı');
  await expect(panel.locator('code')).toHaveText('npm run data');
});

test('a manifest that is present but corrupt still reports the generic failure', async ({ page }) => {
  await page.route('**/data/manifest.json', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '{"schema":99}' }));
  await page.goto('/');
  await expect(page.locator('#overlay-msg')).toContainText('unexpected schema', { timeout: 30_000 });
  await expect(page.locator('[data-testid="no-data"]')).toHaveCount(0);
});
