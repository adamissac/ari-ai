import { expect, test } from '@playwright/test';
import { newUser } from './helpers';

// Real backend. The first create reaches the server and commits; only its response is lost.
test('retrying a create whose response was lost does not create a duplicate', async ({ browser }) => {
  const page = await newUser(browser, 'e2e-alice');
  await page.goto('/projects');
  const name = `retry-${Date.now()}`;
  let dropped = false;
  await page.route('**/api/v1/projects', async route => {
    if (route.request().method() !== 'POST' || dropped) return route.continue();
    dropped = true;
    await route.fetch();            // the backend commits the project…
    await route.abort('connectionreset'); // …but the browser never sees the reply
  });
  await page.getByLabel('Name').fill(name);
  await page.getByRole('button', { name: 'Create project' }).click();
  await expect(page.getByTestId('error-state')).toBeVisible();
  // Same action, same inputs: the retry reuses its key and the backend replays the stored result.
  await page.getByRole('button', { name: 'Create project' }).click();
  await expect(page.getByTestId('error-state')).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole('link', { name, exact: true })).toHaveCount(1);
});
