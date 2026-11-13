import { expect, test } from '@playwright/test';
import { signIn } from './helpers';

/**
 * The Defense Lab simulation panel talks to the real backend route. Where the simulation
 * engine is installed it runs a real episode; where it is not (the default workspace has no
 * torch) it must say so. Both branches are honest states; a fabricated episode is neither.
 */
test('a signed-out visitor is asked to sign in and gets no simulation', async ({ page }) => {
  await page.goto('/lab');
  const panel = page.getByTestId('lab-simulation');
  await expect(panel.getByTestId('sim-signed-out')).toContainText('Sign in to run a simulation');
  await expect(panel.getByTestId('sim-run')).toHaveCount(0);
  await expect(panel.getByTestId('sim-episode')).toHaveCount(0);
});

test('the simulation runs on the backend or says why it cannot', async ({ page }) => {
  await signIn(page, 'e2e-alice');
  await page.goto('/lab');
  const panel = page.getByTestId('lab-simulation');
  const run = panel.getByTestId('sim-run');
  const unavailable = panel.getByTestId('sim-unavailable');
  await expect(run.or(unavailable)).toBeVisible();

  if (await unavailable.isVisible()) {
    await expect(unavailable).toContainText('Simulation unavailable');
    await expect(unavailable).toContainText('no substitute data is shown');
    await expect(run).toHaveCount(0);
    await expect(panel.getByTestId('sim-episode')).toHaveCount(0);
    return;
  }

  await expect(panel.getByTestId('sim-label')).toContainText('no action is executed');
  await panel.getByLabel('Episode seed').fill('1003');
  const response = page.waitForResponse(r => r.url().endsWith('/api/v1/lab/simulation/episodes') && r.request().method() === 'POST');
  await run.click();
  const body = await (await response).json() as { episode: { steps: { action_label: string; reward: number }[]; policy: { checkpoint_sha256: string; gradient_updates: number } } };
  await panel.getByTestId('sim-pause').click();
  await panel.getByLabel('Episode step').fill('0');

  // What is on screen is what the backend returned for this request.
  await expect(panel.getByTestId('sim-policy')).toContainText('Learned checkpoint');
  await expect(panel.getByTestId('sim-provenance')).toContainText(body.episode.policy.checkpoint_sha256.slice(0, 12));
  await expect(panel.getByTestId('sim-provenance')).toContainText('seed 1003');
  await expect(panel.getByTestId('sim-progress')).toContainText(`Step 1 of ${body.episode.steps.length}`);
  await expect(panel.getByTestId('sim-action')).toHaveText(body.episode.steps[0]!.action_label);
  await expect(panel.getByTestId('sim-return')).toHaveText(body.episode.steps[0]!.reward.toFixed(2));
  await panel.getByTestId('sim-step').click();
  await expect(panel.getByTestId('sim-progress')).toContainText('Step 2 of');
  await expect(panel.getByTestId('sim-action')).toHaveText(body.episode.steps[1]!.action_label);

  // A reload drops the episode instead of showing a stale one; running again reproduces it.
  await page.reload();
  await expect(page.getByTestId('lab-simulation').getByTestId('sim-run')).toBeVisible();
  await expect(page.getByTestId('lab-simulation').getByTestId('sim-episode')).toHaveCount(0);

  // An untrained network is labelled as one.
  await page.getByTestId('lab-simulation').getByLabel('Simulation policy').selectOption('ddqn_untrained');
  await page.getByTestId('lab-simulation').getByTestId('sim-run').click();
  await expect(page.getByTestId('sim-policy')).toContainText('Untrained network');
  await expect(page.getByTestId('sim-provenance')).toContainText('0 gradient updates');
});
