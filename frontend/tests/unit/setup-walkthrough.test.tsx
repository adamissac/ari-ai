import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { SetupDone } from '@/components/onboarding/setup-done';

afterEach(cleanup);

it('links to the five project areas with the selected repository and has no coach dialog', () => {
  render(<SetupDone projectId="prj_12345678" repoId="rep_12345678" onBack={vi.fn()} />);

  const links = [
    ['Analytics', '/projects/prj_12345678?repo=rep_12345678'],
    ['Commits', '/projects/prj_12345678/commits?repo=rep_12345678'],
    ['Findings', '/projects/prj_12345678/findings?repo=rep_12345678'],
    ['Approvals', '/projects/prj_12345678/approvals?repo=rep_12345678'],
    ['Settings', '/projects/prj_12345678/settings?repo=rep_12345678'],
  ];
  for (const [label, href] of links) {
    expect(screen.getByRole('link', { name: label }).getAttribute('href')).toBe(href);
  }

  expect(screen.getByTestId('setup-done').querySelector('[data-testid="coach-spotlight"]')).toBeNull();
  expect(screen.queryByRole('dialog')).toBeNull();
});
