// Second capture pass: the recorded agent run on one commit, as a sequence of real UI states, plus its tabs.
//   node scripts/capture-replay.mjs [baseUrl] [accessCode]
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';

const BASE = process.argv[2] || 'http://127.0.0.1:3000';
const CODE = process.argv[3] || 'trailer-local';
const OUT = path.resolve('assets/cap');
const COMMIT = '/demo/lumen-pay/payments-api/commit/06e06635b39263b2aa777edaaf458165a1d74c89';
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 2 });
await ctx.request.post(BASE + '/api/demo-session', { data: { code: CODE } });
const page = await ctx.newPage();
const shot = async (name) => { await page.screenshot({ path: path.join(OUT, `${name}.jpg`), type: 'jpeg', quality: 92 }); console.log('wrote', name); };

await page.goto(BASE + COMMIT, { waitUntil: 'networkidle' });
const t0 = Date.now();
for (const s of [0.6, 1.6, 2.6, 3.6, 4.6, 5.6, 6.6, 7.6, 8.6, 9.6, 10.6, 11.6, 13]) {
  const dt = s * 1000 - (Date.now() - t0);
  if (dt > 0) await page.waitForTimeout(dt);
  await shot(`run_${String(Math.round(s * 10)).padStart(3, '0')}`);
}
for (const tab of ['Seven agents', 'Code review']) {
  await page.getByRole('button', { name: tab, exact: true }).first().click().catch(async () => page.getByText(tab, { exact: true }).first().click());
  await page.waitForTimeout(2500);
  await shot(`tab_${tab.split(' ')[0].toLowerCase()}`);
  const h = await page.evaluate(() => document.documentElement.scrollHeight);
  console.log(tab, 'height', h);
  if (h > 1500) { await page.evaluate(() => window.scrollTo(0, 800)); await page.waitForTimeout(1200); await shot(`tab_${tab.split(' ')[0].toLowerCase()}_s1`); await page.evaluate(() => window.scrollTo(0, 0)); }
}
await browser.close();
