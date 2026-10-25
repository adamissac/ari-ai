import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { PatchDeliveryStatus } from '@/components/patch-delivery-status';

afterEach(cleanup);

describe('patch delivery status', () => {
  it('links to an opened pull request and shows its branch', () => {
    render(
      <PatchDeliveryStatus
        patchId="pat_one"
        delivery={{
          status: 'pr_opened',
          reason: null,
          url: 'https://github.com/acme/app/pull/1',
          branch: 'ari/fix-one',
          commit_sha: 'a'.repeat(40),
          at: null,
        }}
      />,
    );

    const link = screen.getByRole('link', { name: 'Open pull request' });
    expect(link.getAttribute('href')).toBe('https://github.com/acme/app/pull/1');
    expect(link.getAttribute('target')).toBe('_blank');
    expect(link.getAttribute('rel')).toBe('noreferrer');
    expect(screen.getByTestId('patch-delivery-pat_one').textContent).toContain('ari/fix-one');
  });

  it('shows a failed delivery reason and confirms the repository was unchanged', () => {
    render(
      <PatchDeliveryStatus
        patchId="pat_two"
        delivery={{
          status: 'failed',
          reason: 'repository is not connected through the GitHub App',
          url: null,
          branch: null,
          commit_sha: null,
          at: null,
        }}
      />,
    );

    const line = screen.getByTestId('patch-delivery-pat_two');
    expect(line.textContent).toContain('Delivery failed: repository is not connected through the GitHub App');
    expect(line.textContent).toContain("Ari didn't change your repository.");
  });
});
