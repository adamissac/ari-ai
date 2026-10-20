import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { HowItWorks, ProblemScene, ProofStats, Walkthrough } from '@/components/story';

beforeEach(() => {
  vi.stubGlobal('matchMedia', (q: string) => ({
    matches: false, media: q, addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, onchange: null, dispatchEvent: () => false,
  }));
});

describe('story a11y in non-sticky mode', () => {
  it('shows all problem beats without aria-hidden', () => {
    const { container } = render(<ProblemScene />);
    const items = container.querySelectorAll('.problem-beat');
    expect(items).toHaveLength(3);
    items.forEach(i => expect(i.hasAttribute('aria-hidden')).toBe(false));
  });
  it('renders key walkthrough labels as real text', () => {
    render(<Walkthrough />);
    fireEvent.click(screen.getByRole('button', { name: /Fix and prove it/ }));
    expect(screen.getByText('root cause · create_refund', { selector: 'span.block' })).toBeTruthy();
    expect(screen.getByText('verified · replay 2 / 2', { selector: 'span.block' })).toBeTruthy();
  });
  it('shows Never rather than a zero counter', () => {
    render(<ProofStats />);
    expect(screen.getByText('Never')).toBeTruthy();
    expect(screen.queryByText('0')).toBeNull();
  });
});


it('lets readers choose a process step and keeps it selected when scrolling', () => {
  render(<HowItWorks />);
  expect(screen.getByRole('heading', { name: 'Learn what it should do' })).toBeTruthy();
  const tab = screen.getByRole('tab', { name: /Review and attack/ });
  fireEvent.click(tab);
  expect(tab.getAttribute('aria-selected')).toBe('true');
  expect(screen.getByRole('heading', { name: 'Test it like an attacker' })).toBeTruthy();
  fireEvent.scroll(window);
  expect(tab.getAttribute('aria-selected')).toBe('true');
  fireEvent.keyDown(tab, { key: 'ArrowRight' });
  expect(screen.getByRole('tab', { name: /Repair and verify/ }).getAttribute('aria-selected')).toBe('true');
  expect(screen.getByRole('heading', { name: 'Fix it, then prove it' })).toBeTruthy();
});
