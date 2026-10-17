import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { BRAND_NAME, LOGO_SRC, LogoMark, Wordmark } from '@/components/brand';
import { Reveal } from '@/components/reveal';
import { Button } from '@/components/ui';

afterEach(cleanup);

describe('Ari AI brand and interactive UI', () => {
  it('keeps one accessible name when the button label is duplicated for the hover roll', () => {
    render(<Button>Development sign-in</Button>);
    const btn = screen.getByRole('button', { name: 'Development sign-in' });
    expect(btn.querySelectorAll('[aria-hidden="true"]').length).toBe(1);
  });

  it('renders non-string button children untouched', () => {
    render(<Button><span data-testid="icon">+</span> Add</Button>);
    expect(screen.getByTestId('icon')).toBeTruthy();
  });

  it('shows the product name once with a decorative supplied mark', () => {
    render(<Wordmark />);
    expect(BRAND_NAME).toBe('Ari AI');
    expect(screen.queryByRole('img')).toBeNull();
    expect(screen.getByTestId('ari-logo').getAttribute('aria-hidden')).toBe('true');
    expect(screen.getByTestId('ari-logo').style.width).toBe('24px');
    expect(screen.getByText('Ari AI')).toBeTruthy();
  });

  it('sizes and names a standalone supplied logo without changing its source', () => {
    render(<LogoMark size={40} />);
    expect(screen.getByRole('img', { name: `${BRAND_NAME} logo` })).toBeTruthy();
    const logo = screen.getByTestId('ari-logo');
    expect(logo.style.width).toBe('40px');
    expect(logo.style.height).toBe('40px');
    expect(logo.querySelector('img')?.getAttribute('src')).toContain(encodeURIComponent(LOGO_SRC));
    expect(logo.querySelector('img')?.getAttribute('alt')).toBe(`${BRAND_NAME} logo`);
  });

  it('reveal content is visible by default (no JS / no IntersectionObserver)', () => {
    const { container } = render(<Reveal><p>visible</p></Reveal>);
    expect(container.firstElementChild?.getAttribute('data-shown')).toBe('true');
    expect(screen.getByText('visible')).toBeTruthy();
  });
});
