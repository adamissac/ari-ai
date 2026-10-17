import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { BRAND_NAME, LogoPlaceholder, Wordmark } from '@/components/brand';
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

  it('labels the placeholder logo honestly and shows the product name', () => {
    render(<Wordmark />);
    expect(BRAND_NAME).toBe('Ari AI');
    expect(screen.getByRole('img', { name: 'Ari AI logo (placeholder)' })).toBeTruthy();
    expect(screen.getByText('Ari AI')).toBeTruthy();
  });

  it('sizes the placeholder logo', () => {
    render(<LogoPlaceholder size={40} />);
    expect(screen.getByTestId('logo-placeholder').style.width).toBe('40px');
  });

  it('reveal content is visible by default (no JS / no IntersectionObserver)', () => {
    const { container } = render(<Reveal><p>visible</p></Reveal>);
    expect(container.firstElementChild?.getAttribute('data-shown')).toBe('true');
    expect(screen.getByText('visible')).toBeTruthy();
  });
});
