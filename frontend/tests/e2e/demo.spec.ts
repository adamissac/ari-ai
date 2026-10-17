import { expect, test, type Page } from '@playwright/test';
import { evidenceShot, expectNoSideScroll } from './helpers';

// The demo account (ADR 0013) needs no backend: an access code checked on the server opens
// the Lumen Pay sample account. These tests prove the gate, the flow, and that every page
// keeps the small "Demo account · sample data" tag and footer.
const CODE = process.env.DEMO_ACCESS_CODE ?? 'e2e-demo-access-code';

async function signInWithCode(page: Page, code = CODE): Promise<void> {
  await page.getByTestId('access-code').fill(code);
  await page.getByTestId('access-submit').click();
}

test('demo account: access code, Lumen Pay, repo, commit, seven agents, review, defense', async ({ page }) => {
  await page.goto('/demo');
  await expect(page).toHaveURL(/\/access\?next=%2Fdemo$/);
  await signInWithCode(page, 'wrong-code');
  await expect(page.getByTestId('access-error')).toContainText('not valid');
  await signInWithCode(page);
  await expect(page.getByTestId('demo-orgs')).toBeVisible();
  await expect(page.getByTestId('demo-account-tag').first()).toContainText('Demo account');
  await expect(page.getByTestId('header-account')).toContainText('alex-rivera');
  await page.getByTestId('demo-org-lumen-pay').click();
  await expect(page.getByTestId('demo-repos')).toContainText('payments-api');
  await page.getByTestId('demo-repo-payments-api').click();
  await expect(page.getByTestId('demo-commit-row').first()).toContainText('GET /payments/{payment_id}');
  await expect(page.getByTestId('site-footer')).toContainText('sample data');
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

  await page.getByTestId('demo-tab-defense').click();
  await expect(page.getByTestId('defense-map')).toContainText('CRITICAL');
  await expect(page.getByTestId('demo-defense')).toContainText('Raise monitoring');
  await evidenceShot(page, 'demo-defense');

  await page.setViewportSize({ width: 375, height: 800 });
  await page.getByTestId('demo-tab-agents').click();
  await expectNoSideScroll(page);
});

test('demo pages need the access code, then return the visitor where they were going', async ({ page }) => {
  await page.goto('/demo/lumen-pay/payments-api');
  await expect(page.getByTestId('access-signin')).toBeVisible();
  await signInWithCode(page);
  await expect(page).toHaveURL(/\/demo\/lumen-pay\/payments-api$/);
  await expect(page.getByTestId('demo-repos').or(page.getByTestId('demo-commit-row').first())).toBeVisible();
});

test('the access cookie cannot be forged', async ({ page, context, baseURL }) => {
  await context.addCookies([{ name: 'ari_demo_access', value: '1', url: baseURL ?? 'http://127.0.0.1' }]);
  await page.goto('/demo/lumen-pay');
  await expect(page.getByTestId('access-signin')).toBeVisible();
  const session = await page.request.get('/api/demo-session');
  expect(await session.json()).toEqual({ signedIn: false });
});

test('Defense Lab replays a recorded game from the bundle, labelled as simulation, with held-out scores', async ({ page }) => {
  // The overview command center was merged into the main replay (one game, shown once).
  await page.goto('/lab');
  await expect(page.getByTestId('lab-command')).toHaveCount(0);
  await expect(page.getByText('Replay a recorded game')).toBeVisible();
  await expect(page.getByTestId('lab-mode')).toHaveText('Simulation · recorded evaluation');
  await expect(page.getByTestId('score-compromise_rate')).toContainText(/\d+\.\d%/);
});
