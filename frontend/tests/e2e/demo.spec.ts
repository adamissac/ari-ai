import { expect, test } from '@playwright/test';
import { evidenceShot, expectNoSideScroll } from './helpers';

// The simulated demo (ADR 0013) needs no backend. These tests prove the flow works end to
// end and that every page keeps the "Simulated demo" marker visible.

test('simulated demo: GitHub sign-in, org, repo, commit, seven agents, review, defense', async ({ page }) => {
  await page.goto('/demo');
  await expect(page.getByTestId('demo-marker').first()).toContainText('Simulated demo');
  await page.getByTestId('demo-github-signin').click();
  await expect(page.getByTestId('demo-orgs')).toBeVisible();
  await page.getByTestId('demo-org-lumen-pay').click();
  await expect(page.getByTestId('demo-repos')).toContainText('payments-api');
  await page.getByTestId('demo-repo-payments-api').click();
  await expect(page.getByTestId('demo-commit-row').first()).toContainText('GET /payments/{payment_id}');
  await expect(page.getByTestId('site-footer')).toContainText('Simulated demo');
  await page.getByTestId('demo-commit-row').first().click();

  await expect(page.getByTestId('demo-analyzing')).toBeVisible();
  await page.getByTestId('demo-tab-agents').click();
  await expect(page.getByTestId('demo-agent-scout')).toBeVisible();
  await page.getByTestId('demo-skip').click();
  await expect(page.getByTestId('demo-verdict')).toContainText('fix verified');
  for (const agent of ['scout', 'probe', 'trace', 'diagnose', 'patch', 'fortify', 'verify']) {
    await expect(page.getByTestId(`demo-agent-${agent}`)).toHaveAttribute('data-status', 'done');
  }
  await page.getByTestId('demo-agent-probe').click();
  await expect(page.getByTestId('demo-agent-outcome')).toContainText('Confirmed H1');
  await expect(page.getByTestId('demo-agent-steps')).toContainText('Blocked by policy');

  await page.getByTestId('demo-tab-review').click();
  await expect(page.getByTestId('demo-review')).toContainText('A customer can only read payments they own.');
  await expect(page.getByTestId('demo-review')).toContainText('require_owner(p.customer_id, customer)');

  // A commit's analysis is review + seven agents; continuous defense is not part of it.
  await expect(page.getByTestId('demo-tab-defense')).toHaveCount(0);

  // The agent map: the run replays, the changed service ends fixed, untouched parts stay out.
  await page.getByTestId('demo-tab-agents').click();
  await expect(page.getByTestId('demo-node-api')).toHaveAttribute('data-state', 'fixed');
  await expect(page.getByTestId('demo-node-refunds')).toHaveAttribute('data-state', 'outside');
  await page.getByTestId('demo-play').click();
  await expect(page.getByTestId('demo-agent-now')).not.toHaveText('All seven agents finished');
  await evidenceShot(page, 'demo-agent-map');

  await page.setViewportSize({ width: 375, height: 800 });
  await page.getByTestId('demo-tab-agents').click();
  await expectNoSideScroll(page);
});

test('simulated demo pages send a signed-out visitor to the sign-in', async ({ page }) => {
  await page.goto('/demo/lumen-pay/payments-api');
  await expect(page.getByTestId('demo-signin')).toBeVisible();
});

test('Defense Lab replays a recorded game from the bundle, labelled as simulation, with held-out scores', async ({ page }) => {
  // The overview command center was merged into the main replay (one game, shown once).
  await page.goto('/lab');
  await expect(page.getByTestId('lab-command')).toHaveCount(0);
  await expect(page.getByText('Replay a recorded game')).toBeVisible();
  await expect(page.getByTestId('lab-mode')).toHaveText('Simulation · recorded evaluation');
  await expect(page.getByTestId('score-compromise_rate')).toContainText(/\d+\.\d%/);
});
