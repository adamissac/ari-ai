import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { expect, test } from '@playwright/test';
import { completeSetup, env, newUser } from './helpers';

test('console header and tab band stay stacked while scrolling Analytics', async ({ browser }) => {
  const page = await newUser(browser, 'e2e-alice');
  const projectId = env('E2E_PROJECT_ID');
  const repoId = env('E2E_REPO_ID');
  await completeSetup(page, projectId, repoId);
  const captureDir = process.env.CAPTURE_DIR;
  if (captureDir) await mkdir(captureDir, { recursive: true });

  for (const [width, height] of [[1440, 900], [390, 844]] as const) {
    await page.setViewportSize({ width, height });
    await page.goto(`/projects/${projectId}?repo=${repoId}`);
    await expect(page.getByRole('heading', { name: 'Analytics', exact: true })).toBeVisible();
    await expect(page.getByText('Checks run', { exact: true })).toBeVisible();
    await page.waitForTimeout(300);

    for (const scrollY of [50, 300]) {
      await page.evaluate(y => window.scrollTo(0, y), scrollY);
      await page.waitForTimeout(150);
      await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(scrollY);
      const layout = await page.evaluate(() => {
        const rect = (selector: string) => {
          const element = document.querySelector(selector);
          if (!element) return null;
          const bounds = element.getBoundingClientRect();
          const style = getComputedStyle(element);
          return {
            top: Math.round(bounds.top),
            bottom: Math.round(bounds.bottom),
            height: Math.round(bounds.height),
            position: style.position,
            zIndex: style.zIndex,
            background: style.backgroundColor,
          };
        };
        return {
          scrollY: window.scrollY,
          viewport: [window.innerWidth, window.innerHeight],
          documentWidth: document.documentElement.scrollWidth,
          siteHeader: rect('.site-header'),
          projectHeader: rect('.project-shell > header'),
          tabBand: rect('.project-tabbar'),
        };
      });
      expect(layout.siteHeader?.top).toBe(0);
      expect(layout.siteHeader?.background).not.toBe('rgba(0, 0, 0, 0)');
      expect(Number(layout.siteHeader?.zIndex)).toBeGreaterThan(Number(layout.tabBand?.zIndex));
      expect(layout.tabBand?.position).toBe('sticky');
      expect(layout.tabBand!.top).toBeGreaterThanOrEqual(layout.siteHeader!.bottom);
      expect(layout.tabBand?.background).not.toBe('rgba(0, 0, 0, 0)');
      if (scrollY === 300) {
        expect(Math.abs(layout.tabBand!.top - layout.siteHeader!.bottom)).toBeLessThanOrEqual(1);
      }
      console.log(JSON.stringify({ route: 'analytics', ...layout }));
      if (captureDir) {
        await page.screenshot({
          path: path.join(captureDir, `analytics-${width}-scroll-${scrollY}.png`),
          fullPage: false,
        });
      }
    }
  }

  await page.setViewportSize({ width: 320, height: 700 });
  await page.goto(`/projects/${projectId}/live-defense?repo=${repoId}`);
  await expect(page.getByTestId('live-defense')).toBeVisible();
  const overflow = await page.evaluate(() => {
    const width = document.documentElement.clientWidth;
    const elements = [...document.querySelectorAll('body *')].flatMap(element => {
      const bounds = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      if (bounds.width === 0 || style.display === 'none') return [];
      const rightOverflow = Math.max(0, bounds.right - width);
      const scrollOverflow = Math.max(0, element.scrollWidth - element.clientWidth);
      if (rightOverflow < 1 && scrollOverflow < 1) return [];
      return [{
        tag: element.tagName.toLowerCase(),
        className: typeof element.className === 'string' ? element.className : '',
        testId: element.getAttribute('data-testid'),
        right: Math.round(bounds.right),
        width: Math.round(bounds.width),
        clientWidth: element.clientWidth,
        scrollWidth: element.scrollWidth,
        rightOverflow: Math.round(rightOverflow),
        scrollOverflow: Math.round(scrollOverflow),
        text: (element.textContent ?? '').trim().replace(/\s+/g, ' ').slice(0, 90),
      }];
    }).sort((a, b) => b.rightOverflow - a.rightOverflow || b.scrollOverflow - a.scrollOverflow);
    return { viewport: width, documentWidth: document.documentElement.scrollWidth, elements: elements.slice(0, 20) };
  });
  console.log(JSON.stringify({ route: 'live-defense', ...overflow }));
  expect(overflow.documentWidth).toBeLessThanOrEqual(overflow.viewport);
  if (captureDir) {
    await page.screenshot({ path: path.join(captureDir, 'live-defense-320.png'), fullPage: false });
  }
});
