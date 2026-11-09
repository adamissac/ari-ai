import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';

const CODE = process.env.DEMO_ACCESS_CODE ?? 'e2e-demo-access-code';
const fixtures = JSON.parse(readFileSync(new URL('../../lib/demo/console/fixtures.json', import.meta.url), 'utf8')) as {
  project_id: string;
  repo_id: string;
};
const projectId = fixtures.project_id;
const repoId = fixtures.repo_id;
const BANNER = 'Demo account · Lumen Pay sample data.';

async function signInWithCode(page: Page, code: string) {
  await page.getByTestId('access-code').fill(code);
  await page.getByTestId('access-submit').click();
}

test('the access-code demo walks the real signed-in flow on simulated, offline data', async ({ page }) => {
  test.setTimeout(240_000);
  const apiRequests: string[] = [];
  page.on('request', request => {
    const url = new URL(request.url());
    if (url.pathname.startsWith('/api/v1') || url.pathname === '/api/analyze' || url.hostname === 'github.com') apiRequests.push(request.url());
  });

  // Sign-in: access code, then the simulated GitHub authorization, then the organization picker.
  await page.goto('/demo');
  await expect(page).toHaveURL(/\/access/);
  await signInWithCode(page, 'wrong-code');
  await expect(page.getByTestId('access-error')).toContainText('not valid');
  await signInWithCode(page, CODE);
  await expect(page.getByTestId('demo-github-step')).toContainText('lumen-pay');
  // The signed-out account probe on /access is pre-demo.
  apiRequests.length = 0;
  await page.getByTestId('demo-github-authorize').click();
  await expect(page).toHaveURL(/\/connect$/);
  await expect(page.getByText(BANNER)).toBeVisible();
  await page.getByTestId('connect-org-lumen-pay').click();

  // Several repositories; only payments-api is connected. Connecting another opens setup.
  await expect(page.getByTestId('connect-repo-lumen-pay/payments-api')).toContainText('Connected');
  await expect(page.locator('[data-testid^="connect-repo-lumen-pay/"]')).toHaveCount(5);
  await page.getByTestId('connect-repo-lumen-pay/checkout-web').getByRole('button').click();
  await expect(page).toHaveURL(/\/setup\?repo=rep_demo_checkout-web/);
  await expect(page.getByRole('heading', { name: /set up Ari for checkout-web/ })).toBeVisible();
  await expect(page.getByText('PR OPENED')).toBeVisible();
  for (let step = 1; step <= 5; step++) {
    await page.getByRole('button', { name: 'Continue' }).click();
    await expect(page.getByTestId(`setup-step-${step + 1}`)).toBeVisible();
  }
  await page.getByRole('button', { name: /Approve sandbox testing/ }).click();
  await expect(page.getByText('Testing authorized')).toBeVisible();
  await page.getByRole('button', { name: 'Continue' }).click();
  await page.getByRole('button', { name: 'Continue' }).click();
  await page.getByRole('button', { name: 'Start first assessment' }).click();
  await expect(page.getByText('Assessment started.')).toBeVisible();

  // The paused recorded check on payments-api: approve the fix, then watch the agents finish.
  await page.goto(`/projects/${projectId}?repo=${repoId}`);
  await expect(page.getByRole('heading', { name: 'Analytics' })).toBeVisible();
  await page.getByRole('link', { name: 'Review the proposed fix' }).click();
  await expect(page.getByRole('heading', { name: 'Approvals' })).toBeVisible();
  for (let i = 0; i < 2; i++) {
    await page.getByRole('button', { name: 'Approve remediation' }).first().click();
    await page.getByRole('button', { name: 'Confirm approval' }).click();
  }
  await expect(page.getByRole('button', { name: 'Approve remediation' })).toHaveCount(0);
  await page.goto(`/projects/${projectId}/assessments/asm_01M6FV2SMWPFS8PH97GT8X4FB2-r0?repo=${repoId}`);
  await expect(page.getByText('This check finished.')).toBeVisible({ timeout: 90_000 });

  // Findings with evidence and the commit page's quick read stay on sample data.
  await page.getByRole('link', { name: 'Findings' }).click();
  await expect(page.locator('h1')).toHaveText('Findings');
  await page.getByRole('button', { name: 'View fixed findings' }).click();
  await page.locator('a[href*="/findings/fnd_"]').first().click();
  await expect(page.getByText('Before and after the fix')).toBeVisible();
  await page.goto('/connect/lumen-pay/payments-api/commit/94d9195');
  await expect(page.getByTestId('commit-quick-read')).toContainText('sample analysis for the demo account');

  // Actions outside the simulated flow stay off, and nothing reached the backend or GitHub.
  await page.goto(`/projects/${projectId}/assessments/asm_01M6FV2SMWPFS8PH97GT8X4FB2?repo=${repoId}`);
  await expect(page.getByRole('heading', { name: 'Review pipeline' })).toBeVisible();
  expect(apiRequests).toEqual([]);

  await page.getByRole('button', { name: 'Exit demo' }).first().click();
  await expect(page).toHaveURL('/');
  await page.goto('/projects');
  await expect(page.getByText(BANNER)).toHaveCount(0);
});

test('the access cookie cannot be forged', async ({ page, context, baseURL }) => {
  await context.addCookies([{ name: 'ari_demo_access', value: '1', url: baseURL ?? 'http://127.0.0.1' }]);
  await page.goto('/demo');
  await expect(page.getByTestId('access-signin')).toBeVisible();
  const session = await page.request.get('/api/demo-session');
  expect(await session.json()).toEqual({ signedIn: false });
  await page.goto('/access/github');
  await expect(page).toHaveURL(/\/access$/);
});
