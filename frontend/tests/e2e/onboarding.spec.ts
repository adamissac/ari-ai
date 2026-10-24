import { expect, test } from '@playwright/test';
import { env, evidenceShot, expectNoSideScroll, newUser } from './helpers';

const project = () => env('E2E_ONBOARDING_PROJECT_ID');

const step = (page: import('@playwright/test').Page, id: string) =>
  page.getByTestId(`onboarding-step-${id}`);

/**
 * The customer journey through the rendered wizard against the real API:
 * progress computed from real state -> register staging app + ingest token ->
 * owner-attested deploy mapping -> authorized test event -> evidence ->
 * disconnect revokes access. Every step state is backend-derived, never painted.
 */
test('onboarding wizard drives the full customer journey', async ({ browser }) => {
  const alice = await newUser(browser, 'e2e-alice');

  await alice.goto(`/projects/${project()}/onboarding`);
  await expect(alice.getByTestId('onboarding-title')).toBeVisible();
  await expect(step(alice, 'sign_in')).toHaveAttribute('data-state', 'done');
  await expect(step(alice, 'organization')).toHaveAttribute('data-state', 'done');
  // The seeded repository is connected by name only — the App grant is honestly open.
  await expect(step(alice, 'repository')).toHaveAttribute('data-state', 'done');
  await expect(step(alice, 'github_access')).toHaveAttribute('data-state', 'todo');
  await expect(step(alice, 'snapshot')).not.toHaveAttribute('data-state', 'blocked');
  // No owned_staging window has arrived yet, whatever apps the stack seeded.
  await expect(step(alice, 'test_event')).not.toHaveAttribute('data-state', 'done');

  // Permission explanations are explicit before any grant.
  await expect(alice.getByTestId('permission-list')).toContainText('contents:read');
  await expect(alice.getByTestId('permission-list')).toContainText('No autonomous remediation');

  // Register a staging app and mint its ingest token through the real UI.
  await alice.goto(`/projects/${project()}/live-defense/apps`);
  await alice.getByLabel('Name').fill('onboarding-staging');
  await alice.getByLabel('Environment').selectOption('owned_test');
  await alice.getByRole('button', { name: 'Register app' }).click();
  const appCard = alice.locator('li', { hasText: 'onboarding-staging' }).first();
  await expect(appCard).toBeVisible();
  await appCard.getByRole('button', { name: 'Issue ingest token' }).click();
  await expect(appCard.getByTestId('live-defense-token-once')).toBeVisible();

  // Attest the deployment-to-commit mapping for the seeded repo.
  await alice.goto(`/projects/${project()}/live-defense/first-responder`);
  const mapping = alice.locator('section[aria-label="Owner-attested deploy-to-commit mapping"]');
  await mapping.getByLabel('Application').selectOption({ label: 'onboarding-staging' });
  await mapping.getByLabel('Repository id').fill(env('E2E_ONBOARDING_REPO_ID'));
  await mapping.getByLabel('Commit SHA').fill(env('E2E_COMMIT'));
  await mapping.getByRole('button', { name: 'Attest mapping' }).click();
  await expect(mapping.getByRole('button', { name: 'Attest mapping' })).toBeEnabled();

  // Back on the wizard the computed steps moved; the test event is now allowed.
  await alice.goto(`/projects/${project()}/onboarding`);
  await expect(step(alice, 'application')).toHaveAttribute('data-state', 'done');
  await expect(step(alice, 'deploy_mapping')).toHaveAttribute('data-state', 'done');
  await expect(step(alice, 'monitoring')).toHaveAttribute('data-state', 'done');
  await expect(step(alice, 'test_event')).toHaveAttribute('data-state', 'todo');

  await alice.getByTestId('onb-test-event').click();
  await expect(alice.getByTestId('onb-test-event-result')).toBeVisible({ timeout: 30_000 });
  await expect(alice.getByTestId('onb-test-event-result')).toContainText('monitoring event');
  await expect(step(alice, 'test_event')).toHaveAttribute('data-state', 'done', { timeout: 15_000 });
  await expect(step(alice, 'evidence')).toHaveAttribute('data-state', 'done', { timeout: 15_000 });
  await evidenceShot(alice, 'onboarding-complete');

  // Disconnect revokes the access grant and the attested mapping — and says so.
  await alice.getByTestId('onb-disconnect-repo').click();
  await alice.getByTestId('onb-disconnect-repo-confirm').click();
  await expect(step(alice, 'deploy_mapping')).toHaveAttribute('data-state', 'todo', { timeout: 15_000 });
  await evidenceShot(alice, 'onboarding-disconnected');

  await expectNoSideScroll(alice);
});

// Isolation uses the shared seeded project; no windows-dependence there.
test('onboarding progress is project-isolated', async ({ browser }) => {
  const shared = () => env('E2E_PROJECT_ID');
  const alice = await newUser(browser, 'e2e-alice');
  const mallory = await newUser(browser, 'e2e-onboard-outsider');
  await mallory.goto(`/projects/${shared()}/onboarding`);
  await expect(mallory.getByText('Could not load project')).toBeVisible({ timeout: 15_000 });
  await alice.goto(`/projects/${shared()}/onboarding`);
  await expect(alice.getByTestId('onboarding-title')).toBeVisible();
});
