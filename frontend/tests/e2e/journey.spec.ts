import { createHmac, randomUUID } from 'node:crypto';
import { expect, test } from '@playwright/test';
import { env, evidenceShot, newUser } from './helpers';

const project = () => env('E2E_PROJECT_ID');

/**
 * One assessed change, end to end, through the rendered UI against the real API:
 * scope request -> second-person approval -> assessment -> live timeline over SSE ->
 * human remediation approval -> seven security agents + reviewer -> finding
 * evidence chain -> hash-checked patch diff -> independent Verify -> persists on reload.
 */
test('one real assessment from scope approval to verified patch', async ({ browser }) => {
  const alice = await newUser(browser, 'e2e-alice');
  const bob = await newUser(browser, 'e2e-bob');

  // Alice requests a sandbox scope; she cannot approve her own request.
  await alice.goto(`/projects/${project()}/scopes`);
  await alice.getByLabel('Name').fill('payments-lite sandbox');
  await alice.getByLabel('Repository (sandbox build target)').selectOption({ label: env('E2E_REPO') });
  await alice.getByRole('button', { name: 'Request scope' }).click();
  const scopeRow = alice.locator('[data-testid^="scope-"]').filter({ hasText: 'payments-lite sandbox' });
  await expect(scopeRow.getByText('Pending approval')).toBeVisible();
  await expect(scopeRow.getByRole('button', { name: 'Approve scope' })).toBeDisabled();

  // Bob approves it.
  await bob.goto(`/projects/${project()}/scopes`);
  const bobRow = bob.locator('[data-testid^="scope-"]').filter({ hasText: 'payments-lite sandbox' });
  await bobRow.getByRole('button', { name: 'Approve scope' }).click();
  await expect(bobRow.getByText('Active')).toBeVisible();

  // Alice starts the assessment at the exact commit.
  await alice.goto(`/projects/${project()}`);
  await alice.getByLabel('Repository', { exact: true }).selectOption({ label: env('E2E_REPO') });
  await alice.getByLabel('Authorized scope').selectOption({ label: 'payments-lite sandbox' });
  await alice.getByLabel('Commit SHA').fill(env('E2E_COMMIT'));
  await alice.getByRole('button', { name: 'Start assessment' }).click();
  await alice.waitForURL(/\/assessments\/asm_/);
  const asmUrl = alice.url();

  // The timeline is fed by the persisted SSE stream and pauses for a human.
  await expect(alice.getByTestId('event-log')).toBeVisible();
  await expect(alice.getByRole('heading', { name: 'Human approval required' })).toBeVisible({ timeout: 180_000 });
  await expect(alice.getByTestId('agent-reviewer').getByText('Succeeded')).toBeVisible();
  await evidenceShot(alice, 'assessment-awaiting-approval');

  // Bob approves remediation from his inbox (with the will / will-not summary): one for the
  // security fix and one for the reviewer's functional repair. The run resumes when both are decided.
  await bob.goto(`/projects/${project()}/approvals`);
  const pending = bob.locator('[data-testid^="approval-"]').filter({ hasText: 'remediation approval' }).filter({ hasText: 'Pending' });
  await expect(pending).toHaveCount(2);
  await expect(pending.first().getByText('Merge, push, deploy, or change the repository.')).toBeVisible();
  for (let i = 0; i < 2; i++) {
    await pending.first().getByRole('button', { name: 'Approve remediation' }).click();
    await expect(pending).toHaveCount(1 - i);
  }
  await expect(bob.locator('[data-testid^="approval-"]').filter({ hasText: 'remediation approval' }).getByText('Approved')).toHaveCount(2);

  // Alice's open page receives the rest of the run live.
  await expect(alice.getByRole('heading', { name: /Assessment/ }).getByText('Completed')).toBeVisible({ timeout: 180_000 });
  await expect(alice.getByTestId('stream-state')).toContainText('terminal state');
  for (const agent of ['reviewer', 'scout', 'probe', 'trace', 'diagnose', 'patch', 'verify', 'fortify']) {
    await expect(alice.getByTestId(`agent-${agent}`).getByText('Succeeded').first()).toBeVisible();
  }
  // Honest provider labelling: scripted model turns are never presented as live.
  await expect(alice.getByTestId('provider-summary')).toContainText('Not a live-provider run');
  // review + seven agents + the reviewer's functional repair + its independent Verify
  await expect(alice.getByTestId('provider-summary')).toContainText('Test provider (scripted) × 9, Deterministic (no model call) × 1');
  await evidenceShot(alice, 'assessment-completed');

  // Security finding evidence chain, patch diff and Verify verdict from persisted records.
  const findingLinks = alice.locator('a[href*="/findings/fnd_"]');
  await expect(findingLinks).toHaveCount(2);
  const security = alice.locator('li').filter({ has: alice.getByText('security', { exact: true }) }).locator('a[href*="/findings/"]').first();
  await security.click();
  await alice.waitForURL(/\/findings\/fnd_/);
  await expect(alice.getByRole('heading', { name: 'Evidence chain' })).toBeVisible();
  await expect(alice.getByText('Confirmed by Probe')).toBeVisible();
  await expect(alice.getByText('Verify: accepted').first()).toBeVisible();
  await alice.getByRole('button', { name: /View diff/ }).first().click();
  await expect(alice.getByTestId('diff-view').first()).toBeVisible();
  await expect(alice.getByText('matches server hash')).toBeVisible();
  await evidenceShot(alice, 'finding-evidence-chain');

  // Everything survives a full reload: it is persisted state, not client memory.
  await alice.goto(asmUrl);
  await expect(alice.getByRole('heading', { name: /Assessment/ }).getByText('Completed')).toBeVisible();
  await expect(alice.getByTestId('event-log').locator('li')).not.toHaveCount(0);
  await alice.reload();
  await expect(alice.getByTestId('agent-verify').getByText('Succeeded').first()).toBeVisible();
});

test('signed GitHub push appears in the monitoring feed', async ({ browser, request }) => {
  const page = await newUser(browser, 'e2e-alice');
  const payload = {
    // A docs-only push: monitoring must record it, and the default policy skips re-assessment.
    ref: 'refs/heads/main', before: env('E2E_COMMIT'), after: env('E2E_COMMIT'), forced: false, deleted: false,
    repository: { full_name: env('E2E_REPO'), id: 1 }, sender: { login: 'dev' },
    head_commit: { timestamp: new Date().toISOString(), message: 'e2e push' },
    commits: [{ added: [], modified: ['docs/notes.md'], removed: [] }],
  };
  const raw = JSON.stringify(payload);
  const signature = `sha256=${createHmac('sha256', env('E2E_WEBHOOK_SECRET')).update(raw).digest('hex')}`;
  const res = await request.post(`${env('E2E_API')}/webhooks/github`, {
    data: raw,
    headers: { 'Content-Type': 'application/json', 'X-GitHub-Event': 'push', 'X-GitHub-Delivery': randomUUID(), 'X-Hub-Signature-256': signature },
  });
  expect(res.status()).toBe(202);
  await page.goto(`/projects/${project()}/monitoring`);
  const feed = page.getByTestId('monitoring-feed');
  await expect(feed).toContainText('github');
  await expect(feed).toContainText('push');
  await expect(feed).toContainText('refs/heads/main');
  await evidenceShot(page, 'monitoring');
  await expect(page.getByTestId('rl-caveat')).toHaveText('Recommendation from a policy trained in simulation. Not applied automatically.');
});

test('create a project and connect a repository through the UI', async ({ browser }) => {
  const page = await newUser(browser, 'e2e-alice');
  const name = `ui-project-${Date.now()}`;
  await page.getByLabel('Name').fill(name);
  await page.getByRole('button', { name: 'Create project' }).click();
  await page.getByRole('link', { name }).click();
  await expect(page.getByText('No repository connected.')).toBeVisible();
  await page.getByLabel('owner/name').fill('acme/another-repo');
  await page.getByRole('button', { name: 'Connect' }).click();
  await expect(page.getByRole('region', { name: 'Repositories' }).getByText('acme/another-repo')).toBeVisible();
  await expect(page.getByText('No assessments yet.')).toBeVisible();
});
