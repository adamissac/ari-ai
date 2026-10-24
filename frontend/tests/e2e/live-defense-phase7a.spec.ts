import { expect, test } from '@playwright/test';
import { env, evidenceShot, newUser } from './helpers';

test('Live Defense Phase 7A: first-responder modes, states, no auto-execute', async ({ browser }) => {
  const page = await newUser(browser, 'e2e-alice');
  const pid = env('E2E_PROJECT_ID');

  await page.goto(`/projects/${pid}/live-defense`);
  await expect(page.getByTestId('live-defense')).toHaveAttribute('data-mode', 'live');
  await expect(page.getByRole('button', { name: /^(apply|isolate|rate-limit|block source|auto-execute)$/i })).toHaveCount(0);

  await page.getByRole('navigation', { name: 'Live Defense' }).getByRole('link', { name: 'First responder' }).click();
  await expect(page).toHaveURL(new RegExp(`/projects/${pid}/live-defense/first-responder`));
  await expect(page.getByTestId('live-defense-first-responder-copy')).toContainText('AUTO-EXECUTE does not exist');
  await expect(page.getByTestId('live-defense-evidence-states')).toContainText('Observed');
  await expect(page.getByTestId('live-defense-evidence-states')).toContainText('Recommended is not Executed');
  await expect(page.getByTestId('live-defense-fr-mode-select')).toBeVisible();
  await expect(page.getByTestId('live-defense-fr-mode-select').locator('option[value="auto_execute"]')).toHaveCount(0);

  await page.getByTestId('live-defense-fr-mode-select').selectOption('monitor');
  await page.getByRole('button', { name: 'Set mode' }).click();
  await expect(page.getByTestId('live-defense-fr-intent')).toContainText('monitor');
  await evidenceShot(page, 'live-defense-phase7a-mode');

  await expect(page.getByTestId('live-defense-fr-capabilities')).toContainText('scout');
  await expect(page.getByTestId('live-defense-fr-capabilities')).toContainText('probe');
  await expect(page.getByTestId('live-defense-fr-capabilities')).toContainText('patch');
  await expect(page.getByTestId('live-defense-fr-capabilities')).toContainText('verify');
  await evidenceShot(page, 'live-defense-phase7a-capabilities');
});
