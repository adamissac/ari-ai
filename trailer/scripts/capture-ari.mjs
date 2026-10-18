// Capture real Ari UI from a local demo-mode build (the hosted site is not reachable from the render box).
//   frontend: NEXT_PUBLIC_DEMO_ONLY=1 next build && DEMO_ACCESS_CODE=<code> next start --port 3000
//   node scripts/capture-ari.mjs [baseUrl] [accessCode]
// Writes assets/cap/<name>.png at 1920x1080 CSS px, 2x device pixels (crisp when the camera zooms in).
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';

const BASE = process.argv[2] || 'http://127.0.0.1:3000';
const CODE = process.argv[3] || 'trailer-local';
const OUT = path.resolve('assets/cap');
fs.mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 2, reducedMotion: 'no-preference' });
const page = await ctx.newPage();
const wait = (ms) => page.waitForTimeout(ms);
const shot = async (name, opts = {}) => {
  const f = path.join(OUT, `${name}.png`);
  await page.screenshot({ path: f, ...opts });
  console.log('wrote', path.relative(process.cwd(), f));
};
const go = async (url, settle = 2500) => {
  await page.goto(BASE + url, { waitUntil: 'networkidle' });
  await wait(settle);
};

// Landing: hero after the colony has grown, then each scroll-told chapter at a few progress points.
await go('/', 7000);
await shot('home_hero');
const tracks = await page.$$eval('.story-track, .bleed, section', (els) => els.map((e) => {
  const r = e.getBoundingClientRect();
  return { cls: e.className.slice(0, 60), top: r.top + scrollY, h: r.height };
}));
fs.writeFileSync(path.join(OUT, 'home_layout.json'), JSON.stringify(tracks, null, 1));
const H = await page.evaluate(() => document.documentElement.scrollHeight);
console.log('page height', H);
for (const [i, y] of [0.12, 0.2, 0.28, 0.36, 0.44, 0.52, 0.6, 0.68, 0.76, 0.84, 0.92].entries()) {
  await page.evaluate((y) => window.scrollTo(0, y), Math.round(y * (H - 1080)));
  await wait(900);
  await shot(`home_s${String(i).padStart(2, '0')}`);
}

// Access-code sign-in, then the demo account.
await go('/access', 2500);
await shot('access');
const res = await ctx.request.post(BASE + '/api/demo-session', { data: { code: CODE } });
console.log('demo sign-in', res.status());
await go('/demo', 2500);
await shot('demo_orgs');
await go('/demo/lumen-pay', 2500);
await shot('demo_repos');
const repos = await page.$$eval('a[href^="/demo/lumen-pay/"]', (as) => [...new Set(as.map((a) => a.getAttribute('href')))]);
console.log('repos', repos);
const repo = repos.find((h) => h.endsWith('payments-api')) || repos[0];
await go(repo, 2500);
await shot('demo_commits');
const commits = await page.$$eval('a[href*="/commit/"]', (as) => [...new Set(as.map((a) => a.getAttribute('href') + ' | ' + a.textContent.replace(/\s+/g, ' ').trim().slice(0, 90)))]);
fs.writeFileSync(path.join(OUT, 'commits.txt'), commits.join('\n'));
console.log(commits.slice(0, 12).join('\n'));
for (const [i, c] of commits.slice(0, 3).entries()) {
  const href = c.split(' | ')[0];
  await go(href, 4000);
  await shot(`demo_commit${i}`);
  const h = await page.evaluate(() => document.documentElement.scrollHeight);
  for (const k of [1, 2, 3]) {
    if (k * 900 > h - 1080) break;
    await page.evaluate((y) => window.scrollTo(0, y), k * 900);
    await wait(1200);
    await shot(`demo_commit${i}_s${k}`);
  }
}

// Defense Lab and pricing.
await go('/lab', 4000);
await shot('lab');
const LH = await page.evaluate(() => document.documentElement.scrollHeight);
for (const k of [1, 2, 3, 4]) {
  if (k * 950 > LH - 1080) break;
  await page.evaluate((y) => window.scrollTo(0, y), k * 950);
  await wait(1500);
  await shot(`lab_s${k}`);
}
await go('/pricing', 2000);
await shot('pricing');

await browser.close();
