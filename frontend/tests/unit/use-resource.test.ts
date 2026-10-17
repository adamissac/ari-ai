import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useResource } from '@/lib/use-resource';

afterEach(() => { vi.useRealTimers(); });

describe('useResource', () => {
  it('a failed first load is an error', async () => {
    const { result } = renderHook(() => useResource('k', () => Promise.reject(new Error('boom')), 50));
    await waitFor(() => expect(result.current.status).toBe('error'));
  });

  it('keeps the last good data on a failed poll, exposes the failure, and keeps polling', async () => {
    vi.useFakeTimers();
    let n = 0;
    const load = vi.fn(async () => {
      n++;
      if (n === 2) throw new Error('poll failed');
      return `v${n}`;
    });
    const { result } = renderHook(() => useResource('k', load, 1000));
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(result.current).toMatchObject({ status: 'ready', data: 'v1' });
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    expect(result.current.status).toBe('ready');
    expect(result.current.data).toBe('v1');
    expect((result.current.refreshError as Error).message).toBe('poll failed');
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    expect(load).toHaveBeenCalledTimes(3);
    expect(result.current).toMatchObject({ status: 'ready', data: 'v3', refreshError: undefined });
  });

  it('never returns data from the previous key', async () => {
    let release: (v: string) => void = () => {};
    const { result, rerender } = renderHook(({ k }) => useResource(k, () => (k === 'a' ? Promise.resolve('A') : new Promise<string>(r => { release = r; }))), { initialProps: { k: 'a' } });
    await waitFor(() => expect(result.current.data).toBe('A'));
    rerender({ k: 'b' });
    expect(result.current.status).toBe('loading');
    expect(result.current.data).toBeUndefined();
    await act(async () => { release('B'); });
    await waitFor(() => expect(result.current.data).toBe('B'));
  });
});
