import { expect, test } from '@playwright/test';
import { env, evidenceShot, newUser } from './helpers';

const project = () => env('E2E_PROJECT_ID');

test('Live Defense shadow pilot: staging app, unknown health, no enforcement', async ({ browser }) => {
  const page = await newUser(browser, 'e2e-alice');
  await page.goto(`/projects/${project()}/live-defense`);
  await expect(page.getByTestId('live-defense')).toHaveAttribute('data-mode', 'live');
  await expect(page.getByTestId('live-defense-preview-banner')).toHaveCount(0);
  await expect(page.getByTestId('live-defense-no-enforcement')).toContainText('does not apply, isolate, rate-limit, or block');
  await expect(page.getByTestId('live-defense-health-unknown')).toContainText('unknown');
  await expect(page.getByTestId('defense-map')).toHaveCount(0);
  await expect(page.getByRole('button', { name: /^(apply|isolate|rate-limit|block source)$/i })).toHaveCount(0);

  await page.getByRole('link', { name: 'Staging apps' }).click();
  await expect(page).toHaveURL(new RegExp(`/projects/${project()}/live-defense/apps`));
  await expect(page.getByTestId('live-defense-shadow-mode')).toContainText('Shadow mode');
  await page.getByLabel('Name').fill('payments-lite staging');
  await page.getByLabel('Environment').selectOption('owned_test');
  await page.getByRole('button', { name: 'Register app' }).click();
  await expect(page.getByText('payments-lite staging')).toBeVisible();
  await expect(page.getByText('owned test')).toBeVisible();
  await page.getByRole('button', { name: 'Issue ingest token' }).click();
  const once = page.getByTestId('live-defense-token-once');
  await expect(once).toContainText('will not show it again');
  const token = await once.locator('code').innerText();
  expect(token.startsWith('hkt_ing_')).toBeTruthy();

  await page.getByRole('link', { name: 'Overview' }).click();
  await expect(page.getByTestId('live-defense-summary')).toContainText('staging app');
  await expect(page.getByTestId('live-defense-health')).toContainText('unknown');
  await expect(page.getByRole('button', { name: /^(apply|isolate|rate-limit|block)$/i })).toHaveCount(0);
  await evidenceShot(page, 'live-defense-overview');
});
