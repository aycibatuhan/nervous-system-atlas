import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: 'e2e', timeout: 90_000, retries: 0, use: { baseURL: 'http://localhost:5173', headless: true, viewport: { width: 1400, height: 900 } },
  webServer: { command: 'npm run dev', url: 'http://localhost:5173', reuseExistingServer: true, timeout: 60_000 },
});
