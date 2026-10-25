import { expect, test } from '@playwright/test';

const stages = 'commit trace flag check patch verify';

for (const viewport of [{ width: 1440, height: 900 }, { width: 1024, height: 768 }, { width: 390, height: 844 }]) {
  test(`landing contract, navigation and layout at ${viewport.width}px`, async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.setViewportSize(viewport);
    await page.goto('/');

    await expect(page).toHaveTitle('ARI Console');
    await expect(page.locator('meta[property="og:site_name"]')).toHaveAttribute('content', 'ARI');
    await expect(page.locator('.hero-full')).toBeVisible();
    await expect(page.locator('#hero-title')).toHaveText(/Ship fast\.\s*Know what you shipped\./);

    const demoOnly = process.env.NEXT_PUBLIC_DEMO_ONLY === '1';
    const primaryCta = page.locator('.hero-full').getByRole('link', {
      name: demoOnly ? 'Sign in' : 'Go to projects',
      exact: true,
    });
    await expect(primaryCta).toHaveAttribute('href', demoOnly ? '/access' : '/projects');
    const howCta = page.getByRole('link', { name: 'How it works', exact: true });
    await expect(howCta).toHaveAttribute('href', '#how');

    const field = page.getByTestId('signal-field');
    await expect(field).toBeVisible();
    await expect(field.locator('.sf-log-row')).toHaveCount(6);
    await expect(field.locator('.sf-note')).toHaveText('Illustration · not a recorded run');
    await expect(page.locator('#how')).toHaveCount(1);
    await expect(page.locator('#control')).toHaveCount(1);

    const nav = page.getByRole('navigation', { name: 'Primary', exact: true });
    const secondary = nav.locator('.nav-secondary');
    await expect(secondary).toHaveAttribute('inert', '');
    const account = nav.locator('[data-testid="header-signin"], [data-testid="header-account"]');
    await expect(account).toBeVisible();
    await secondary.locator('a').first().evaluate(el => (el as HTMLAnchorElement).focus());
    expect(await page.evaluate(() => document.activeElement?.closest('.nav-secondary') !== null)).toBe(false);

    if (viewport.width < 640) {
      await nav.getByRole('button', { name: 'Menu', exact: true }).click();
      for (const name of ['Projects', 'Defense Lab', 'Pricing']) {
        await expect(nav.getByRole('link', { name, exact: true })).toBeVisible();
      }
      await nav.getByRole('link', { name: 'Projects', exact: true }).focus();
      await page.keyboard.press('Escape');
      await expect(nav.getByRole('button', { name: 'Menu', exact: true })).toBeFocused();
      await expect(secondary).toHaveAttribute('inert', '');
    }

    await expect(page.getByRole('link', { name: 'ARI home', exact: true })).toBeVisible();
    await page.evaluate(() => window.scrollTo(0, 120));
    await expect(secondary).toHaveAttribute('aria-hidden', 'false');
    await expect(nav.getByRole('link', { name: 'Projects', exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(viewport.width);

    await howCta.click();
    await expect(page).toHaveURL(/#how$/);
    await nav.getByRole('link', { name: 'Pricing', exact: true }).click();
    await expect(page).toHaveURL(/\/pricing$/);
    await expect(page.getByRole('heading', { level: 1, name: /Pilot first/ })).toBeVisible();
    await expect(page.locator('nextjs-portal')).toHaveCount(0);
    expect(errors).toEqual([]);
  });
}

test('reduced motion shows every signal-field stage', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  await expect(page.locator('#hero-title')).toBeVisible();
  await expect(page.getByTestId('signal-field')).toHaveAttribute('data-s', stages);
});

test('landing footer fits desktop and mobile', async ({ page }) => {
  await page.goto('/');
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 844 });
    const footer = page.getByTestId('landing-footer');
    await footer.scrollIntoViewIfNeeded();
    await expect(footer.getByRole('navigation', { name: 'Footer' })).toBeVisible();
    expect((await footer.boundingBox())!.height).toBeLessThan(500);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  }
});
