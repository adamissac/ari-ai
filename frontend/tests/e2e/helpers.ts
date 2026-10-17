import { expect, type Browser, type Page } from '@playwright/test';

export const env = (name: string): string => {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is not set; run through tests/e2e/stack.py`);
  return value;
};

/** Sign in through the real backend dev-login endpoint via the rendered form. */
export async function signIn(page: Page, login: string): Promise<void> {
  await page.goto('/projects'); // the home page is public; console pages show sign-in
  await page.getByLabel('GitHub login').fill(login);
  await page.getByRole('button', { name: 'Development sign-in' }).click();
  await expect(page.getByTestId('signed-in-user')).toHaveText(login);
}

export async function newUser(browser: Browser, login: string): Promise<Page> {
  const context = await browser.newContext();
  const page = await context.newPage();
  await signIn(page, login);
  return page;
}

/** Full-page screenshot of real executed test data (never fixtures), kept with the test results. */
export async function evidenceShot(page: Page, name: string): Promise<void> {
  await page.screenshot({ path: `test-results/evidence/${name}.png`, fullPage: true });
}

/** No sideways scrolling at the current viewport; on failure, name the widest leaf elements. */
export async function expectNoSideScroll(page: Page): Promise<void> {
  const report = await page.evaluate(() => {
    const limit = window.innerWidth + 1;
    const wide = [...document.querySelectorAll('body *')]
      .filter(e => e.getBoundingClientRect().right > limit && ![...e.children].some(c => c.getBoundingClientRect().right > limit))
      .slice(0, 8)
      .map(e => `${e.tagName.toLowerCase()}.${String(e.className).split(' ').slice(0, 4).join('.')} right=${Math.round(e.getBoundingClientRect().right)}`);
    return { width: document.documentElement.scrollWidth, limit, wide };
  });
  expect(report.width, `page is ${report.width}px wide at ${report.limit - 1}px: ${report.wide.join(' | ')}`).toBeLessThanOrEqual(report.limit);
}
