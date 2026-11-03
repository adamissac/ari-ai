import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';

const CODE = process.env.DEMO_ACCESS_CODE ?? 'e2e-demo-access-code';
const fixtures = JSON.parse(readFileSync(new URL('../../lib/demo/console/fixtures.json', import.meta.url), 'utf8')) as {
  project_id: string;
  repo_id: string;
  responses: Record<string, { body: unknown }>;
};
const projectId = fixtures.project_id;
const repoId = fixtures.repo_id;
const responses = fixtures.responses;
const assessments = (responses[`GET /projects/${projectId}/assessments?repo_id=${repoId}`]!.body as { items: Array<{ id: string; state: string }> }).items;
const pendingAssessment = assessments.find(item => item.state === 'AWAITING_APPROVAL')!;

async function signInWithCode(page: Page, code: string) {
  await page.getByTestId('access-code').fill(code);
  await page.getByTestId('access-submit').click();
}

test('access-code demo uses the real console with offline, read-only fixtures', async ({ page }) => {
  const apiRequests: string[] = [];
  page.on('request', request => {
    const url = new URL(request.url());
    if (url.pathname.startsWith('/api/v1')) apiRequests.push(request.url());
  });

  await page.goto('/demo');
  await expect(page).toHaveURL(/\/access/);
  await signInWithCode(page, 'wrong-code');
  await expect(page.getByTestId('access-error')).toContainText('not valid');
  await signInWithCode(page, CODE);

  await expect(page.getByRole('heading', { name: 'Analytics' })).toBeVisible();
  await expect(page.getByText('Demo account · Lumen Pay sample data. Ari reviews each commit, seven security agents try to break it, a person approves the fix, and an independent check proves it. Every repository, commit and result here is illustrative.')).toBeVisible();
  await expect(page.getByTestId('repo-switcher').getByText('lumen-pay/payments-api')).toBeVisible();
  apiRequests.length = 0;

  await page.getByRole('link', { name: 'Commits' }).click();
  await expect(page.getByRole('heading', { name: 'Commits' })).toBeVisible();
  await page.goto(`/projects/${projectId}/assessments/${pendingAssessment.id}?repo=${repoId}`);
  await expect(page.getByRole('heading', { name: 'Review pipeline' })).toBeVisible();

  await page.getByRole('link', { name: 'Findings' }).click();
  await expect(page.locator('h1')).toHaveText('Findings');
  const findingLink = page.locator(`a[href*="/findings/"]`).first();
  await expect(findingLink).toBeVisible();
  await findingLink.click();
  await expect(page.locator('h1')).toContainText(/finding/i);

  await page.goto(`/projects/${projectId}/assessments/${pendingAssessment.id}?repo=${repoId}`);
  await page.getByRole('button', { name: 'Cancel assessment' }).click();
  await expect(page.getByText('This is the demo account: actions are turned off.')).toBeVisible();
  expect(apiRequests).toEqual([]);

  await page.getByRole('button', { name: 'Exit demo' }).first().click();
  await expect(page).toHaveURL('/');
  await page.goto('/projects');
  await expect(page.getByText('Demo account · Lumen Pay sample data. Ari reviews each commit, seven security agents try to break it, a person approves the fix, and an independent check proves it. Every repository, commit and result here is illustrative.')).toHaveCount(0);
  await expect(page.getByText('Lumen Pay · payments-api')).toHaveCount(0);
});

test('the access cookie cannot be forged', async ({ page, context, baseURL }) => {
  await context.addCookies([{ name: 'ari_demo_access', value: '1', url: baseURL ?? 'http://127.0.0.1' }]);
  await page.goto('/demo');
  await expect(page.getByTestId('access-signin')).toBeVisible();
  const session = await page.request.get('/api/demo-session');
  expect(await session.json()).toEqual({ signedIn: false });
});
