import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const expectations = vi.fn();
const assessment = vi.fn();
vi.mock('@/lib/api', () => ({ api: () => ({ expectations, assessment }) }));

import { ExpectationLinks } from '@/components/expectation-links';

const item = (id: string) => ({ id, statement: `stmt ${id}`, status: 'confirmed' });

beforeEach(() => { expectations.mockReset(); assessment.mockReset(); });
afterEach(cleanup);

describe('ExpectationLinks', () => {
  it('marks unmatched ids as not loaded when paging was truncated', async () => {
    expectations.mockResolvedValue({ items: [item('a')], next_cursor: '1' });
    render(<ExpectationLinks projectId="p" snapshotId="s" assessmentId="as" ids={['a', 'missing']} />);
    await waitFor(() => expect(screen.getByTestId('finding-expectations')).toBeTruthy());
    expect(expectations).toHaveBeenCalledTimes(5);
    expect(screen.getByText('stmt a')).toBeTruthy();
    expect(screen.getByTestId('finding-expectations').textContent).toContain('Not loaded (list truncated)');
    expect(screen.getByTestId('finding-expectations').textContent).not.toContain('No statement in the indexed snapshot');
  });

  it('reports a genuinely absent id when the list was fully read', async () => {
    expectations.mockResolvedValue({ items: [item('a')], next_cursor: null });
    render(<ExpectationLinks projectId="p" snapshotId="s" assessmentId="as" ids={['a', 'missing']} />);
    await waitFor(() => expect(screen.getByTestId('finding-expectations').textContent).toContain('No statement in the indexed snapshot'));
  });

  it('shows loading, not stale rows, when ids change', async () => {
    expectations.mockResolvedValueOnce({ items: [item('a')], next_cursor: null });
    const { rerender } = render(<ExpectationLinks projectId="p" snapshotId="s" assessmentId="as" ids={['a']} />);
    await waitFor(() => expect(screen.getByText('stmt a')).toBeTruthy());
    expectations.mockReturnValueOnce(new Promise(() => {}));
    rerender(<ExpectationLinks projectId="p" snapshotId="s" assessmentId="as" ids={['b']} />);
    expect(screen.queryByText('stmt a')).toBeNull();
    expect(screen.queryByTestId('finding-expectations')).toBeNull();
  });
});
