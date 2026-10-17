'use client';

import { useCallback, useEffect, useState } from 'react';

/**
 * Playhead for the simulated run: advances one tool step at a time so the agents appear to
 * work in order. Reduced motion starts at the end. `position === total` means finished.
 */
export function useReplay(total: number, stepMs = 520): { position: number; playing: boolean; done: boolean; skip: () => void; restart: () => void } {
  const [position, setPosition] = useState(0);
  const [playing, setPlaying] = useState(true);

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setPosition(total);
      setPlaying(false);
    }
  }, [total]);

  const running = playing && position < total;
  useEffect(() => {
    if (!running) return;
    const id = setTimeout(() => setPosition(p => p + 1), position === 0 ? 900 : stepMs);
    return () => clearTimeout(id);
  }, [running, position, stepMs]);

  const skip = useCallback(() => { setPosition(total); setPlaying(false); }, [total]);
  const restart = useCallback(() => { setPosition(0); setPlaying(true); }, []);
  return { position: Math.min(position, total), playing: running, done: position >= total, skip, restart };
}
