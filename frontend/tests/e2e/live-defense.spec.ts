import { expect, test } from '@playwright/test';
import { env, evidenceShot, newUser } from './helpers';

const project = () => env('E2E_PROJECT_ID');

function ingestBatch(offsetMs: number, extra: number) {
  const start = Date.now() + offsetMs;
  return {
    source: 'runtime_demo',
    window_start: new Date(start).toISOString(),
    window_end: new Date(start + 60_000).toISOString(),
    routes: [{
      route: 'GET /payments/{payment_id}',
      requests: 20,
      status_4xx: extra,
      auth_failures: extra,
    }],
  };
}

test('Live Defense shadow pilot: staging app, ingest, unknown health, review without enforcement', async ({ browser, request }) => {
  const page = await newUser(browser, 'e2e-alice');
  const pid = project();
  const recId = env('E2E_REC_ID');
  const api = env('E2E_API');

  await page.goto(`/projects/${pid}/live-defense`);
  await expect(page.getByTestId('live-defense')).toHaveAttribute('data-mode', 'live');
  await expect(page.getByTestId('live-defense-preview-banner')).toHaveCount(0);
  await expect(page.getByTestId('live-defense-no-enforcement')).toContainText('does not apply, isolate, rate-limit, or block');
  await expect(page.getByTestId('live-defense-health-unknown')).toContainText('unknown');
  await expect(page.getByTestId('defense-map')).toHaveCount(0);
  await expect(page.getByRole('button', { name: /^(apply|isolate|rate-limit|block source)$/i })).toHaveCount(0);

  await page.getByRole('link', { name: 'Staging apps' }).click();
  await expect(page).toHaveURL(new RegExp(`/projects/${pid}/live-defense/apps`));
  await expect(page.getByTestId('live-defense-shadow-mode')).toContainText('Shadow mode');
  await page.getByLabel('Name').fill('payments-lite staging');
  await page.getByLabel('Environment').selectOption('owned_test');
  await page.getByRole('button', { name: 'Register app' }).click();
  const appCard = page.locator('[data-testid^="live-defense-app-"]').filter({ hasText: 'payments-lite staging' });
  await expect(appCard).toBeVisible();
  await expect(appCard.getByText('owned test')).toBeVisible();
  await appCard.getByRole('button', { name: 'Issue ingest token' }).click();
  const once = page.getByTestId('live-defense-token-once');
  await expect(once).toContainText('will not show it again');
  const token = await once.locator('code').innerText();
  expect(token.startsWith('hkt_ing_')).toBeTruthy();
  await evidenceShot(page, 'live-defense-apps');

  const baseline = await request.post(`${api}/ingest/runtime/${pid}`, {
    headers: { Authorization: `Bearer ${token}` },
    data: ingestBatch(0, 0),
  });
  expect(baseline.ok(), await baseline.text()).toBeTruthy();
  const spike = await request.post(`${api}/ingest/runtime/${pid}`, {
    headers: { Authorization: `Bearer ${token}` },
    data: ingestBatch(120_000, 18),
  });
  expect(spike.ok(), await spike.text()).toBeTruthy();

  const me = await page.request.get(`${api}/me`);
  const csrf = (await me.json() as { csrf_token: string }).csrf_token;
  const eventsPage = await page.request.get(`${api}/projects/${pid}/events`);
  expect(eventsPage.ok()).toBeTruthy();
  const events = (await eventsPage.json() as { items: { id: string }[] }).items;
  const incidentRes = await page.request.post(`${api}/projects/${pid}/incidents`, {
    headers: { 'X-CSRF-Token': csrf },
    data: {
      title: 'Staging ingest spike',
      note: 'Opened from authenticated runtime ingest on the owned staging app.',
      monitoring_event_ids: events.slice(0, 1).map(item => item.id),
      recommendation_ids: [recId],
    },
  });
  expect(incidentRes.ok(), await incidentRes.text()).toBeTruthy();
  const incident = await incidentRes.json() as { id: string };

  await page.getByRole('link', { name: 'Overview' }).click();
  await expect(page.getByTestId('live-defense-summary')).toContainText('staging app');
  await expect(page.getByTestId('live-defense-summary')).toContainText('Authenticated ingest has been recorded');
  await expect(page.getByTestId('live-defense-health')).toContainText('unknown');
  await expect(page.getByRole('button', { name: /^(apply|isolate|rate-limit|block)$/i })).toHaveCount(0);
  await expect(page.getByTestId('live-defense-graph')).toBeVisible();
  await evidenceShot(page, 'live-defense-overview');

  await page.getByRole('link', { name: 'Investigation' }).click();
  await expect(page.getByTestId(`live-defense-incident-${incident.id}`)).toContainText('Staging ingest spike');
  await evidenceShot(page, 'live-defense-investigation');
  await page.getByTestId(`live-defense-incident-${incident.id}`).click();
  if (events.length === 0) {
    await expect(page.getByTestId('incident-event-correlation')).toContainText('unknown');
  } else {
    await expect(page.getByText('Authenticated runtime ingest log anomaly')).toBeVisible();
  }
  await expect(page.getByRole('link', { name: 'raise_monitoring on payments' })).toBeVisible();
  await evidenceShot(page, 'live-defense-incident');

  await page.getByRole('link', { name: 'Explainability' }).click();
  const recCard = page.getByTestId(`live-defense-rec-${recId}`);
  await expect(recCard).toContainText('recommendation only');
  await expect(recCard).toContainText('simulation-derived');
  await expect(recCard).toContainText('not a probability');
  await recCard.getByRole('button', { name: 'Load stored explanation' }).click();
  await expect(recCard).toContainText('occlusion');
  const review = page.getByTestId(`live-defense-review-${recId}`);
  await review.getByLabel('Decision').selectOption('accept');
  await review.getByLabel('Reason (optional)').fill('Shadow-pilot opinion only; do not execute.');
  await review.getByRole('button', { name: 'Record review' }).click();
  await expect(review).toContainText('accept');
  await expect(review).toContainText('did not execute');
  await expect(page.getByRole('button', { name: /^(apply|isolate|rate-limit|block)$/i })).toHaveCount(0);
  await evidenceShot(page, 'live-defense-explain-review');
});
