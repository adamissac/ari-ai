import { expect, test } from '@playwright/test';
import { env, evidenceShot, newUser } from './helpers';

const project = () => env('E2E_PROJECT_ID');

test('owner edits project settings and they persist on reload', async ({ browser }) => {
  const page = await newUser(browser, 'e2e-alice');
  await page.goto(`/projects/${project()}/settings`);
  const form = page.getByRole('form', { name: 'Project settings' });
  const interval = form.getByLabel('Minimum interval between reassessments (s)');
  await expect(interval).toHaveValue(/\d+/);
  await expect(form.getByRole('button', { name: 'Save settings' })).toBeDisabled();
  await interval.fill('abc');
  await expect(form.getByRole('alert')).toContainText('Minimum interval');
  await interval.fill('900');
  await form.getByRole('button', { name: 'Save settings' }).click();
  await expect(form.getByRole('status')).toContainText('Saved.');
  await page.reload();
  await expect(page.getByLabel('Minimum interval between reassessments (s)')).toHaveValue('900');
  await evidenceShot(page, 'settings');
});

test('simulated incident: triage, owner, two-person containment approval', async ({ browser }) => {
  const alice = await newUser(browser, 'e2e-alice');
  const bob = await newUser(browser, 'e2e-bob');
  const title = `drill-${Date.now()}`;
  await alice.goto(`/projects/${project()}/incidents`);
  await alice.getByLabel('Title').fill(title);
  await alice.getByLabel('Initial report').fill('Monitoring flagged cross-customer payment reads');
  await alice.getByRole('button', { name: 'Open incident' }).click();
  const note = alice.getByLabel('Note / rationale');
  await expect(alice.getByText('Simulated drill', { exact: true })).toBeVisible();

  await note.fill('Reproduced in sandbox');
  await alice.getByLabel('Category').fill('broken access control');
  await alice.getByRole('button', { name: 'Record triage' }).click();
  await expect(alice.getByRole('list', { name: 'Lifecycle' }).locator('[aria-current="step"]')).toHaveText('Triaged');

  await alice.getByRole('button', { name: 'Move to Analysis' }).click();
  await expect(alice.getByText('assign an incident owner before analysis')).toBeVisible();
  await alice.getByRole('button', { name: 'Assign to me' }).click();
  await alice.getByRole('button', { name: 'Move to Analysis' }).click();
  await expect(alice.getByRole('list', { name: 'Lifecycle' }).locator('[aria-current="step"]')).toHaveText('Analysis');

  await note.fill('Block cross-tenant read path');
  await alice.getByRole('button', { name: 'Request containment approval' }).click();
  await expect(alice.getByRole('button', { name: 'Approve' })).toBeDisabled();

  await bob.goto(`/projects/${project()}/incidents`);
  await bob.locator('[data-testid^="incident-"]').filter({ hasText: title }).click();
  await bob.getByRole('button', { name: 'Approve' }).click();
  await expect(bob.getByRole('button', { name: 'Move to Containment' })).toBeVisible();
  await bob.getByRole('button', { name: 'Move to Containment' }).click();
  await expect(bob.getByRole('list', { name: 'Lifecycle' }).locator('[aria-current="step"]')).toHaveText('Containment');
  await evidenceShot(bob, 'incident');
});

test('incident closure: link verified finding, criteria with evidence, communication', async ({ browser }) => {
  // Runs after journey.spec (workers: 1, file order), which leaves a finding with an accepted Verify.
  const alice = await newUser(browser, 'e2e-alice');
  const title = `closure-${Date.now()}`;
  await alice.goto(`/projects/${project()}/incidents`);
  await alice.getByLabel('Title').fill(title);
  await alice.getByRole('button', { name: 'Open incident' }).click();
  const closure = alice.locator('#closure');
  await expect(closure.getByText('Before closure')).toBeVisible();

  const finding = closure.getByLabel('Finding to link');
  await finding.selectOption({ index: 1 });
  await closure.getByRole('button', { name: 'Link finding' }).click();
  await expect(alice.getByText(/1 findings · 0 events · 0 verifications/)).toBeVisible();
  await closure.getByRole('button', { name: 'Link verification' }).click();
  await expect(alice.getByText(/1 findings · 0 events · 1 verifications/)).toBeVisible();

  await closure.getByLabel('Criterion key').fill('patch-verified');
  await closure.getByLabel('Criterion description').fill('Independent Verify accepted the patch');
  await closure.getByRole('button', { name: 'Add criterion' }).click();
  const criterion = closure.getByTestId('criterion-patch-verified');
  await expect(criterion.getByText('Open')).toBeVisible();
  await criterion.getByRole('button', { name: 'Mark satisfied' }).click();
  await expect(criterion.getByText('Satisfied')).toBeVisible();

  await closure.getByLabel('Channel').fill('#sec-incidents');
  await closure.getByLabel('Summary').fill('Engineering notified of containment plan');
  await closure.getByRole('button', { name: 'Record communication' }).click();
  await expect(closure.getByText('Engineering notified of containment plan')).toBeVisible();
  await expect(closure.getByText(/No Fortify regression-test artifact/)).toBeVisible();
  await expect(closure.getByRole('list').filter({ hasText: 'Satisfy with evidence' })).toHaveCount(0);
  await evidenceShot(alice, 'incident-closure');
});

test('expectations page shows the version-pinned snapshot view', async ({ browser }) => {
  const page = await newUser(browser, 'e2e-alice');
  await page.goto(`/projects/${project()}/expectations`);
  await expect(page.getByRole('link', { name: 'Expectations' })).toHaveAttribute('aria-current', 'page');
  await expect(page.getByText(/No indexed snapshot|awaiting a human decision/)).toBeVisible();
  await evidenceShot(page, 'expectations');
});
