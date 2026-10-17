import { expect, test } from '@playwright/test';
import { evidenceShot } from './helpers';

// These tests intercept the network on purpose: they prove the UI shows honest
// failure states instead of substituting data when the backend misbehaves.

test('backend unreachable is an explicit error, never fake content', async ({ page }) => {
  await page.route('**/api/v1/**', route => route.abort('connectionrefused'));
  await page.goto('/');
  await expect(page.getByTestId('error-state')).toContainText('Backend unreachable');
  await expect(page.getByTestId('error-state')).toContainText('Nothing shown here is cached or simulated');
  await expect(page.getByText('Your projects')).toHaveCount(0);
});

test('a response that violates the shared contract is rejected, not rendered', async ({ page }) => {
  await page.route('**/api/v1/me', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ user: { id: 'not-an-id' }, memberships: [], csrf_token: 'x' }) }));
  await page.goto('/');
  await expect(page.getByTestId('error-state')).toContainText('Backend response rejected');
});

test('signed-out users see sign-in, not data', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Continue with GitHub' })).toHaveAttribute('href', '/api/v1/auth/github/login');
});

test('Defense Lab plots only the committed, schema-validated evaluation bundle', async ({ page }) => {
  await page.goto('/lab');
  await expect(page.getByTestId('lab-caveat')).toContainText('Simulation only');
  await expect(page.getByText(/rl-defense\/results\/protocol-v\d+\/defense_lab\.json/)).toBeVisible();
  const chart = page.getByTestId('metric-chart');
  await expect(chart).toContainText('ddqn');
  await expect(chart).toContainText('threshold_rules');
  await expect(chart).toContainText(/n = |Axis/);
  await expect(page.getByText(/Mean with 95% confidence interval over n = [\d,]+ evaluation episodes/)).toBeVisible();
  await expect(page.getByTestId('topology')).toBeVisible();
  await expect(page.getByText('Ground truth (simulation) — hidden attacker stage, never observed by the policy')).toBeVisible();
  const slider = page.getByLabel('Step');
  await slider.fill('50');
  await expect(page.getByText('t = 50 /', { exact: false })).toBeVisible();
  await evidenceShot(page, 'defense-lab');
});

test('a malformed bundle name is refused by the server', async ({ request }) => {
  const res = await request.get('/lab/bundles/..%2F..%2Fetc');
  expect([400, 404]).toContain(res.status());
});
