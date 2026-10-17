import { expect, type Browser, type Page } from '@playwright/test';

export const env = (name: string): string => {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is not set; run through tests/e2e/stack.py`);
  return value;
};

/** Sign in through the real backend dev-login endpoint via the rendered form. */
export async function signIn(page: Page, login: string): Promise<void> {
  await page.goto('/');
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
