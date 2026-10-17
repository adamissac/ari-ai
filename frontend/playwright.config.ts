import { defineConfig, devices } from '@playwright/test';

// Started by tests/e2e/stack.py, which provides a real backend, worker and Next server.
const baseURL = process.env.E2E_BASE_URL;
if (!baseURL) throw new Error('Run Playwright through tests/e2e/stack.py (E2E_BASE_URL is unset)');

export default defineConfig({
  testDir: 'tests/e2e',
  timeout: 240_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  use: { baseURL, trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  // E2E_BROWSER_CHANNEL=chrome uses an installed Chrome (fresh temporary profile) instead of
  // Playwright's downloaded Chromium build.
  projects: [{
    name: 'chromium',
    use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 1000 }, ...(process.env.E2E_BROWSER_CHANNEL ? { channel: process.env.E2E_BROWSER_CHANNEL } : {}) },
  }],
});
