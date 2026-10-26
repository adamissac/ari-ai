import { act, renderHook, waitFor } from '@testing-library/react';
import { ApiError } from '@hackatl/frontend-transport';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useResource } from '@/lib/use-resource';

afterEach(() => { vi.useRealTimers(); });

describe('useResource', () => {
  it('a failed first load is an error', async () => {
    const { result } = renderHook(() => useResource('k', () => Promise.reject(new Error('boom')), 50));
    await waitFor(() => expect(result.current.status).toBe('error'));
  });

  it('keeps polling after a 500 ApiError refresh failure', async () => {
    vi.useFakeTimers();
    let n = 0;
    const load = vi.fn(async () => {
      n++;
      if (n === 2) throw new ApiError(500, { code: 'INTERNAL', message: 'poll failed', details: {}, request_id: null });
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

  it('stops polling after a 401 refresh failure until reloaded', async () => {
    vi.useFakeTimers();
    let n = 0;
    const load = vi.fn(async () => {
      n++;
      if (n === 2) throw new ApiError(401, { code: 'UNAUTHENTICATED', message: 'Not signed in', details: {}, request_id: null });
      return `v${n}`;
    });
    const { result } = renderHook(() => useResource('k', load, 1000));

    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(result.current).toMatchObject({ status: 'ready', data: 'v1' });
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    expect(load).toHaveBeenCalledTimes(2);
    expect(result.current).toMatchObject({ status: 'ready', data: 'v1' });
    expect((result.current.refreshError as Error).message).toBe('Not signed in');

    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(load).toHaveBeenCalledTimes(2);

    await act(async () => { result.current.reload(); });
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
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
