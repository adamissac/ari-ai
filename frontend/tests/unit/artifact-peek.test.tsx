import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const artifactText = vi.fn();
vi.mock('@/lib/api', () => ({ api: () => ({ artifactText }) }));

import { ArtifactPeek } from '@/components/evidence';

beforeEach(() => artifactText.mockReset());
afterEach(cleanup);

describe('ArtifactPeek', () => {
  it('does not keep a loaded artifact when remounted with another id', async () => {
    artifactText.mockResolvedValue({ text: 'BODY-ONE', sha256: 'a'.repeat(64), hashVerified: true });
    const { rerender } = render(<ArtifactPeek key="one" id="one" />);
    fireEvent.click(screen.getByRole('button'));
    await waitFor(() => expect(screen.getByText('BODY-ONE')).toBeTruthy());
    rerender(<ArtifactPeek key="two" id="two" />);
    expect(screen.queryByText('BODY-ONE')).toBeNull();
    expect(screen.getByRole('button').textContent).toContain('two');
  });

  it('aborts and ignores a load that resolves after unmount', async () => {
    let resolve!: (v: unknown) => void;
    artifactText.mockReturnValue(new Promise(r => { resolve = r; }));
    const err = vi.spyOn(console, 'error').mockImplementation(() => {});
    const { unmount } = render(<ArtifactPeek id="one" />);
    fireEvent.click(screen.getByRole('button'));
    const signal = artifactText.mock.calls[0]?.[1]?.signal as AbortSignal;
    unmount();
    expect(signal.aborted).toBe(true);
    resolve({ text: 'late', sha256: 'b'.repeat(64), hashVerified: true });
    await Promise.resolve();
    expect(err).not.toHaveBeenCalled();
    err.mockRestore();
  });
});
