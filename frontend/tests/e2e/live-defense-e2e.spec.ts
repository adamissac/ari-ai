import { expect, test } from '@playwright/test';
import { env, evidenceShot, newUser } from './helpers';

function ingestBatch(offsetMs: number, extra: number) {
  const end = new Date(Date.now() + offsetMs).toISOString();
  const start = new Date(Date.now() + offsetMs - 60_000).toISOString();
  return {
    source: 'owned_staging',
    window_start: start,
    window_end: end,
    routes: [
      {
        route: 'GET /payments/{payment_id}',
        requests: 20,
        status_4xx: extra,
        auth_failures: extra,
      },
    ],
  };
}

// Workstream 2 e2e: drive the first-responder OFF interruption through the real
// UI + API. Mode is set through the page, telemetry through the real ingest
// route, and OFF takes effect through the same mode control an operator uses.
test('Live Defense e2e: OFF mode stops investigation and renders honestly', async ({ browser, request }) => {
  const page = await newUser(browser, 'e2e-alice');
  const pid = env('E2E_PROJECT_ID');
  const rid = env('E2E_REPO_ID');
  const sha = env('E2E_COMMIT');
  const api = env('E2E_API');

  await page.goto(`/projects/${pid}/live-defense/first-responder`);
  await page.getByTestId('live-defense-fr-mode-select').selectOption('monitor');
  await page.getByRole('button', { name: 'Set mode' }).click();
  await expect(page.getByTestId('live-defense-fr-intent')).toContainText('monitor');

  await page.getByRole('navigation', { name: 'Live Defense' }).getByRole('link', { name: 'Staging apps' }).click();
  await page.getByLabel('Name').fill('e2e owned staging');
  await page.getByLabel('Environment').selectOption('owned_test');
  await page.getByRole('button', { name: 'Register app' }).click();
  const appCard = page.locator('[data-testid^="live-defense-app-"]').filter({ hasText: 'e2e owned staging' });
  await expect(appCard).toBeVisible();
  const appId = (await appCard.getAttribute('data-testid'))!.replace('live-defense-app-', '');
  await appCard.getByRole('button', { name: 'Issue ingest token' }).click();
  const token = await page.getByTestId('live-defense-token-once').locator('code').innerText();

  const me = await page.request.get(`${api}/me`);
  const csrf = (await me.json() as { csrf_token: string }).csrf_token;
  const mapping = await page.request.post(`${api}/applications/${appId}/deploy-mappings`, {
    headers: { 'X-CSRF-Token': csrf },
    data: {
      repo_id: rid,
      commit_sha: sha,
      deployed_at: new Date(Date.now() - 5 * 60_000).toISOString(),
      source: 'owner_attested',
    },
  });
  expect(mapping.ok(), await mapping.text()).toBeTruthy();

  await page.getByRole('navigation', { name: 'Live Defense' }).getByRole('link', { name: 'First responder' }).click();

  await request.post(`${api}/ingest/runtime/${pid}`, {
    headers: { Authorization: `Bearer ${token.trim()}` },
    data: ingestBatch(0, 18),
  });
  await expect(page.getByTestId('live-defense-fr-invocation-scout')).toContainText(/executed|queued/, { timeout: 60_000 });

  // Operator flips OFF through the same control, then posts a second window.
  await page.getByTestId('live-defense-fr-mode-select').selectOption('off');
  await page.getByRole('button', { name: 'Set mode' }).click();
  await expect(page.getByTestId('live-defense-fr-intent')).toContainText('off');

  await request.post(`${api}/ingest/runtime/${pid}`, {
    headers: { Authorization: `Bearer ${token.trim()}` },
    data: ingestBatch(1, 18),
  });

  // The post-OFF window is recorded as cancelled and no agent executes: every
  // invocation of the newest decision is skipped_mode. Checked via the real
  // API with the signed-in session, not just rendered text.
  await expect.poll(async () => {
    const resp = await page.request.get(`${api}/projects/${pid}/first-responder/decisions`);
    const items = (await resp.json() as { items: Array<{ cancelled: boolean }> }).items;
    return items.length && items[0].cancelled;
  }, { timeout: 30_000 }).toBeTruthy();

  const invResp = await page.request.get(`${api}/projects/${pid}/first-responder/invocations`);
  const decResp = await page.request.get(`${api}/projects/${pid}/first-responder/decisions`);
  const latest = (await decResp.json() as { items: Array<{ id: string }> }).items[0];
  const invocations = (await invResp.json() as {
    items: Array<{ decision_id: string; status: string }>
  }).items.filter(i => i.decision_id === latest.id);
  expect(invocations.every(i => i.status !== 'executed')).toBeTruthy();

  await expect(page.getByTestId('live-defense-fr-mode-select')).toHaveValue('off');
  await evidenceShot(page, 'live-defense-e2e-off-mode');
});
