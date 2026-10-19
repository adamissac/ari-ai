import { expect, test } from '@playwright/test';
import { env, newUser } from './helpers';

// Real backend. The first create reaches the server and commits; only its response is lost.
// The project create form is gone, so the retry is exercised at the mutation boundary the
// transport relies on: same Idempotency-Key replays the stored result instead of duplicating.
test('retrying a create whose response was lost does not create a duplicate', async ({ browser }) => {
  const page = await newUser(browser, 'e2e-alice');
  await page.goto('/connect');
  const name = `retry-${Date.now()}`;
  const action = `e2e-retry-${Date.now()}`;
  const me = await page.request.get(`${env('E2E_API')}/me`);
  const csrf = (await me.json()).csrf_token as string;
  let dropped = false;
  await page.route('**/api/v1/projects', async route => {
    if (route.request().method() !== 'POST' || dropped) return route.continue();
    dropped = true;
    await route.fetch();                  // the backend commits the project…
    await route.abort('connectionreset'); // …but the browser never sees the reply
  });
  const create = () => page.evaluate(async ([name, action, csrf]) => {
    const res = await fetch('/api/v1/projects', {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'x-csrf-token': csrf, 'idempotency-key': action },
      body: JSON.stringify({ name, org_id: null, settings: null }),
    });
    if (!res.ok) throw new Error(`create failed (${res.status})`);
    return (await res.json()) as { id: string };
  }, [name, action, csrf] as const);
  await expect(create()).rejects.toThrow(); // the stored result's reply was lost
  const replayed = await create();          // same action key: backend replays, not a new project
  const list = await page.request.get(`${env('E2E_API')}/projects`);
  const items = ((await list.json()) as { items: { id: string; name: string }[] }).items;
  const named = items.filter(p => p.name === name);
  expect(named).toHaveLength(1);
  expect(named[0]!.id).toBe(replayed.id);
});
